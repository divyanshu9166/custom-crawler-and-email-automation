"""Batch website-research benchmark with a human-review sheet. No verification, imports or sends."""
import argparse
import asyncio
import csv
import hashlib
import io
import importlib.metadata
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from outreach.config import Settings
from outreach.web import PublicWeb, crawl_url, domain_of, BLOCKED_SOURCES


def read_candidates(path, limit):
    if not 1 <= limit <= 500 or path.stat().st_size > 1_000_000:
        raise ValueError("Use 1–500 companies and a CSV under 1 MB")
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    if not {"company", "website", "campaign", "country_hint"}.issubset(reader.fieldnames or []):
        raise ValueError("CSV needs company, website, campaign and country_hint columns")
    seen, rows, errors = set(), [], []
    for number, row in enumerate(reader, 2):
        try:
            website = crawl_url(row["website"])
            domain = domain_of(website)
            if row["campaign"] not in {"A", "B"} or row["country_hint"] not in {"US", "UK"} or not row["company"].strip():
                raise ValueError("Provide company, A/B campaign and US/UK hint")
            if any(domain == d or domain.endswith("." + d) for d in BLOCKED_SOURCES):
                raise ValueError("Use an official website, not a platform page")
            if domain in seen:
                continue
            seen.add(domain)
            rows.append({"company": row["company"], "website": website, "campaign": row["campaign"], "country_hint": row["country_hint"]})
        except (ValueError, KeyError, AttributeError) as exc:
            errors.append({"row": number, "reason": str(exc)})
    if not rows:
        raise ValueError("No valid official website candidates")
    return rows[:limit], errors


async def benchmark(args):
    rows, errors = read_candidates(args.input, args.limit)
    concurrency = getattr(args, "concurrency", 1)
    if not 1 <= concurrency <= 8:
        raise ValueError("Use one to eight independent company workers")
    overrides = {"crawl_max_pages": args.pages, "worker_enabled": False, "sending_enabled": False}
    if getattr(args, "timeout", None) is not None:
        overrides["job_timeout_seconds"] = args.timeout
    settings = Settings(**overrides)
    run = args.output / (datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-UTC-") + uuid.uuid4().hex[:6])
    run.mkdir(parents=True, exist_ok=False)
    summary = {"created_at": time.time(), "input_errors": errors, "companies": [], "run_status": "running",
               "source_files_at_start": {name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                                         for name in ("outreach/web.py", "outreach/browser.py", "outreach/config.py", "scripts/benchmark.py", "requirements.lock")},
               "runtime_versions": {"python": sys.version.split()[0], "playwright": importlib.metadata.version("playwright")},
               "scope": {"company_count": len(rows), "max_pages": settings.crawl_max_pages,
                         "max_depth": settings.crawl_max_depth, "render_mode": settings.crawl_render_mode,
                         "company_concurrency": concurrency, "job_timeout_seconds": settings.job_timeout_seconds},
               "note": "Website research only. Country/company/buyer fit and observation accuracy need independent review. No imports, email verification or sends.",
               "email_verification": "not performed", "peak_full_stack_memory": None,
               "memory_note": "Measure the full app/browser/provider stack with deployment monitoring; timings here are not a 4 GB throughput guarantee."}
    async def save_manifest():
        (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    await save_manifest()
    slots = asyncio.Semaphore(concurrency)
    async def research_company(index, row):
        saved = []
        slug = re.sub(r"[^a-z0-9.-]", "_", domain_of(row["website"]))
        detail = f"company-{index:03d}-{slug}.json"
        async def capture(page, report):
            saved.append(page)
            (run / detail).write_text(json.dumps({**row, "pages": saved, "report": report, "error": ""}, indent=2), encoding="utf-8")
        crawler = PublicWeb(settings, on_page=capture)
        start = time.monotonic()
        failure = ""
        try:
            pages = await asyncio.wait_for(crawler.crawl(row["website"]), settings.job_timeout_seconds)
            if not saved:
                saved.extend(pages)
        except Exception as exc:
            failure = type(exc).__name__
            crawler.report["status"] = "partial" if saved else "failed"
        contacts = {entry["email"]: entry for page in saved for entry in page.get("contacts", [])}
        (run / detail).write_text(json.dumps({**row, "pages": saved, "report": crawler.report, "error": failure}, indent=2), encoding="utf-8")
        summary["companies"].append({**row, "status": crawler.report["status"], "pages": len(saved),
            "unique_page_urls": len({crawl_url(page["url"]) for page in saved}),
            "rendered_pages": sum(bool(p.get("rendered")) for p in saved), "published_emails": len(contacts),
            "other_domain_candidates": len({entry["email"] for page in saved for entry in page.get("review_candidates", [])}),
            "published_named_contacts": sum(bool(c.get("name")) for c in contacts.values()),
            "elapsed_seconds": round(time.monotonic() - start, 2), "detail_file": detail, "error": failure,
            "verified_emails": None, "company_match": None, "buyer_match": None, "observation_accuracy": None})
        summary["companies"].sort(key=lambda item: item["detail_file"])
        await save_manifest()
        print(f"{len(summary['companies'])}/{len(rows)} completed · {slug} · {crawler.report['status']} · {len(saved)} pages", flush=True)
    async def bounded_company(index, row):
        async with slots:
            await research_company(index, row)
    await asyncio.gather(*(bounded_company(index, row) for index, row in enumerate(rows, 1)))
    fields = ["company", "website", "campaign", "country_hint", "company_match", "country_confirmed", "buyer_match", "observation_accuracy", "fit_notes", "verified_email_count", "verification_source", "draft_review", "measured_cost", "currency", "reviewer", "reviewed_at"]
    with (run / "review.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            safe = {key: ("'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text) for key, text in row.items()}
            writer.writerow({**safe, **{key: "" for key in fields if key not in row}})
    summary["finished_at"] = time.time()
    summary["run_status"] = "finished"
    summary["campaign_counts"] = {campaign: sum(row["campaign"] == campaign for row in rows) for campaign in ("A", "B")}
    await save_manifest()
    print("Saved private benchmark and independent review sheet:", run.resolve())
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--pages", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=None,
                        help="Per-company deadline in seconds (60-14400); omitted uses JOB_TIMEOUT_SECONDS/default")
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks"))
    asyncio.run(benchmark(parser.parse_args()))
