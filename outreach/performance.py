"""On-demand PageSpeed lab evidence. Never interpret scores as conversion or revenue loss."""
import time

import httpx

from .web import PublicWeb, crawl_url, domain_of


async def performance_audit(db, settings, lead_id):
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if lead.get("lead_kind") == "profile":
        raise ValueError("PageSpeed needs an official company website")
    url = crawl_url(lead["website"])
    web = PublicWeb(settings)
    robots, _, _ = await web.robots(url)
    if not robots.can_fetch(settings.crawler_user_agent, url):
        raise ValueError("Robots denies auditing this page")
    report = {"lead_id": lead_id, "url": url, "requested_at": time.time(), "strategies": {},
              "errors": [], "kind": "Lighthouse lab measurements",
              "limitations": "Emulated lab results vary by run; these are not visitor analytics or proof of lost sales."}
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        for strategy in ("mobile", "desktop"):
            try:
                params = {"url": url, "strategy": strategy, "category": "performance"}
                if settings.pagespeed_api_key:
                    params["key"] = settings.pagespeed_api_key
                response = await client.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params)
                response.raise_for_status()
                if len(response.content) > 8_000_000:
                    raise ValueError("Performance response exceeds report budget")
                result = response.json().get("lighthouseResult") or {}
                if result.get("runtimeError"):
                    raise ValueError("Lighthouse could not finish this page")
                final_url = crawl_url(result.get("finalUrl", ""))
                if domain_of(final_url) != lead["domain"]:
                    raise ValueError("Performance report redirected to a different business domain")
                score = (result.get("categories", {}).get("performance") or {}).get("score")
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
                    raise ValueError("Performance report is missing a valid score")
                audits = result.get("audits", {})
                metrics = {key: {field: audits[key].get(field) for field in ("displayValue", "numericValue", "numericUnit")}
                           for key in ("first-contentful-paint", "largest-contentful-paint", "speed-index", "total-blocking-time", "cumulative-layout-shift")
                           if isinstance(audits.get(key), dict)}
                opportunities = [{"id": key, "title": value.get("title"), "displayValue": value.get("displayValue")}
                                 for key, value in audits.items() if isinstance(value, dict)
                                 and value.get("scoreDisplayMode") == "numeric"
                                 and isinstance(value.get("score"), (int, float)) and value["score"] < 1][:12]
                report["strategies"][strategy] = {"final_url": final_url, "score": round(score * 100),
                    "fetch_time": result.get("fetchTime"), "lighthouse_version": result.get("lighthouseVersion"),
                    "metrics": metrics, "opportunities": opportunities, "warnings": result.get("runWarnings", [])[:12]}
            except Exception as exc:
                # Provider request URLs may contain a private key; save only a controlled reason.
                reason = f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                report["errors"].append({"strategy": strategy, "reason": reason[:160]})
    report["status"] = "complete" if not report["errors"] else "partial" if report["strategies"] else "failed"
    db.event("performance", report)
    if not report["strategies"]:
        raise ValueError("PageSpeed audit failed; inspect the performance event and provider quota/key")
    return report
