"""Render historical offline template previews, not live AI writing; no DB or providers."""
import argparse
import html
import json
import time
from pathlib import Path

from outreach.campaigns import CAMPAIGN_SERVICES, draft_sequence
from outreach.web import crawl_url, domain_of


def build_review(run, annotations, output):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    completed = {row["detail_file"]: row for row in summary["companies"]}
    records, seen = [], set()
    for annotation in annotations:
        name = annotation["detail_file"]
        if name not in completed or name in seen:
            raise ValueError("Choose distinct completed company reports from this benchmark")
        seen.add(name)
        company = json.loads((run / name).read_text(encoding="utf-8"))
        service = annotation["service"]
        if service not in CAMPAIGN_SERVICES[company["campaign"]]:
            raise ValueError("Offer does not belong to the company's campaign")
        pages = {crawl_url(page["url"]): (index, page) for index, page in enumerate(company["pages"], 1)}
        source = crawl_url(annotation["evidence_url"])
        if source not in pages or domain_of(source) != domain_of(company["website"]):
            raise ValueError("Observation source must be a saved official page")
        index, page = pages[source]
        reviewed_company = annotation.get("company", company["company"]).strip()
        company_source = crawl_url(annotation.get("company_source", source))
        if (company_source not in pages or len(reviewed_company) < 2
                or reviewed_company.casefold() not in pages[company_source][1]["text"].casefold()):
            raise ValueError("Company name must appear on a saved official page")
        quote = annotation["quote"].strip()
        if len(quote) < 8 or quote not in page["text"]:
            raise ValueError("Observation quote must exactly match saved evidence")
        country_source = crawl_url(annotation["country_source"])
        country_quote = annotation["country_quote"].strip()
        if (country_source not in pages or len(country_quote) < 3
                or country_quote not in pages[country_source][1]["text"]):
            raise ValueError("Country review requires an exact quote from a saved official page")
        if annotation["country"] not in {"US", "UK"}:
            raise ValueError("Country must be US or UK; a hint alone is insufficient")
        for field in ("observation", "suggestion", "review_notes"):
            if len(annotation[field].strip()) < 12:
                raise ValueError(f"Provide a specific {field}")
        if service.startswith("whatsapp_") and len(annotation.get("channel_fit_notes", "").strip()) < 20:
            raise ValueError("Record WhatsApp fit and permission unknowns")
        finding = {"evidence_id": index, "observation": annotation["observation"], "suggestion": annotation["suggestion"]}
        sequence = draft_sequence(reviewed_company, service, finding, source)
        records.append({"company": reviewed_company, "company_source": company_source,
                        "website": company["website"], "campaign": company["campaign"],
                        "country": annotation["country"], "country_source": country_source, "country_quote": country_quote,
                        "detail_file": name, "crawl_status": completed[name]["status"], "service": service,
                        "evidence_url": source, "quote": quote, "evidence_sha256": page["sha256"],
                        "observation": annotation["observation"], "suggestion": annotation["suggestion"],
                        "review_notes": annotation["review_notes"], "channel_fit_notes": annotation.get("channel_fit_notes", ""),
                        "sequence": sequence, "buyer_identity": "unconfirmed", "recipient_email": None,
                        "email_verification": "not performed", "operator_approval": "pending", "send_ready": False})
    if not records:
        raise ValueError("Provide at least one company annotation")
    report = {"created_at": time.time(), "benchmark": run.name, "scope": summary["scope"],
              "reviewer": "Codex source/copy review; independent operator approval pending",
              "method": "offline_template_preview",
              "note": "Historical offline template previews only; not the live AI writer. Exact quote checks cannot prove the interpretation or business need. No contacts imported, addresses guessed, providers called or mail sent.",
              "company_count": len(records), "message_count": len(records) * 4, "records": records}
    output.mkdir(parents=True, exist_ok=False)
    (output / "draft-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    esc = html.escape
    cards = []
    for row in records:
        messages = "".join(f'<details {"open" if item["step"] == 0 else ""}><summary>Touch {item["step"] + 1}: {esc(item["subject"])}</summary><pre>{esc(item["body"])}</pre></details>' for item in row["sequence"])
        cards.append(f'<article><h2>{esc(row["company"])}</h2><p>Campaign {row["campaign"]} · {row["country"]} · {esc(row["service"])}</p>'
                     f'<p>Observed source: <a href="{esc(row["evidence_url"], quote=True)}">{esc(row["evidence_url"])}</a></p><blockquote>{esc(row["quote"])}</blockquote>'
                     f'<p>Country source: <a href="{esc(row["country_source"], quote=True)}">{esc(row["country_source"])}</a></p><blockquote>{esc(row["country_quote"])}</blockquote>'
                     f'<p class="notes">Review: {esc(row["review_notes"])}</p>{messages}</article>')
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Evidence and draft review</title><style>body{font:16px/1.55 system-ui;background:#f5f5f2;color:#17292a;margin:0;padding:24px}main{max-width:950px;margin:auto}article{background:white;padding:24px;margin:24px 0;border-radius:12px}pre{white-space:pre-wrap;font:inherit}blockquote{border-left:3px solid #267c72;padding-left:16px;margin-left:0}.notes{color:#47585a}summary{cursor:pointer;padding:12px 0}a{overflow-wrap:anywhere}</style>'
                f'<main><h1>{len(records)} company draft reviews</h1><p>{esc(report["note"])}</p><p>Buyer identity and email validity remain unconfirmed. All drafts require operator approval.</p>'
                + "".join(cards) + '</main></html>')
    (output / "draft-review.html").write_text(document, encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_review(args.run, json.loads(args.annotations.read_text(encoding="utf-8")), args.output)
    print(f"Saved {result['company_count']} company previews / {result['message_count']} messages. No send-ready contacts.")
