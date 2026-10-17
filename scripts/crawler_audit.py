"""Benchmark website research without creating leads, verifying contacts, or sending mail."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from outreach.config import Settings
from outreach.web import PublicWeb


async def audit(args):
    settings = Settings(crawl_max_pages=args.pages)
    crawler = PublicWeb(settings)
    start = time.monotonic()
    pages = await crawler.crawl(args.url)
    result = {"website": args.url, "elapsed_seconds": round(time.monotonic() - start, 2),
              "report": crawler.report, "pages": pages,
              "note": "Research only. No contact verification, database imports, or email sends performed."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["report"]["status"], "pages": len(pages),
                      "rendered_pages": sum(p.get("rendered", False) for p in pages),
                      "elapsed_seconds": result["elapsed_seconds"], "output": str(args.output.resolve())}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--pages", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("data/crawler-audit.json"))
    asyncio.run(audit(parser.parse_args()))
