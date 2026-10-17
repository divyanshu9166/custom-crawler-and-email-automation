# Public-source discovery resilience

12 October 2026. The crawler now combines bounded search-engine failover, observed official navigation and an independent Common Crawl URL-index path. This improves public-source coverage; it does not establish Apollo database parity, unrestricted platform access or universally available personal emails.

## Implemented behavior

- SearXNG default results are followed by a configurable Yahoo/Mojeek engine group when results are empty, irrelevant to a supported segment, or engines report limitations. Each result retains its actual engine names, and the run records provider health, rejected constraints and cache state. Both engine groups depend on the same configured SearXNG service; they are not independent hosting providers. Yahoo can also share an underlying index with other engines.
- Site operators and quoted company/domain constraints are checked locally because engines can ignore them. Professional enrichment separately checks company relevance before fetching a person's profile. Indexed snippets never create a contact or trigger verification.
- Public-index requests are serialized and paced, identical requests coalesce, successful searches cache for 15 minutes by default, empty searches for at most one minute, and transport failures have a provider cooldown. A Retry-After response can extend the hold. Cache entries are bounded to 256 and live only in the current process; provider cooldowns reset on restart. Existing company-crawl checkpoints and site retry times remain durable.
- Common Crawl uses its latest published collection, one bounded first-page exact-domain query, a 1 MB decoded-body budget and a 24-hour cache. It retains at most 20 Contact/About/Team/leadership-type URL hints, excluding catalog/editorial/private/cross-domain routes. Archived timestamps remain visible. No archived page contents or emails are imported. A missing domain is an empty result, not a global provider outage. Coverage can be incomplete because only one index page/collection is queried.
- Contact recovery fetches hinted URLs through the existing robots, public-DNS, redirect, resource and cooldown gates. Current publication and ownership are required before a contact import. Reacher and buyer/eligibility review remain separate.
- Professional research reuses hash-matched saved company links, optionally refreshes up to three observed official routes, then makes up to six company/domain query variants within its profile budget. Other observed business-profile links remain separate from LinkedIn/X professional captures. The dashboard distinguishes current company links from indexed identity-review hints.
- Bounded overfetch happens before company-domain deduplication and directory filtering. The live check exposed missing directory/listicle exclusions and a marketing CTA used as the company query name; these were corrected without rewriting existing operational records or qualifications.

## Configuration

The new defaults are documented in `.env.example`:

```dotenv
SEARCH_FALLBACK_ENGINES=yahoo,mojeek
SEARCH_CACHE_SECONDS=900
SEARCH_FAILURE_COOLDOWN_SECONDS=60
COMMONCRAWL_HINTS_ENABLED=true
PROFESSIONAL_REFRESH_OFFICIAL_LINKS=true
```

An empty fallback engine value disables the alternate group. Turning off Common Crawl or official-link refresh preserves the earlier search-only path. Engine availability still depends on SearXNG's installed engine configuration. No paid keys, browser-cookie transfers, proxy rotation, CAPTCHA solvers or private-profile panels are required by these changes.

## Live evidence

[Release-safe live report](multisource-live-check.json). Searches covered UK Bristol florists, US Portland coffee, UK London dental and US Austin roofing. After the final filtering/deduplication pass they yielded **13 indexed company candidates: 5 / 3 / 3 / 2**. These are not qualified buyers or verified addresses. The report preserves the earlier raw search pass separately, including results subsequently excluded as directories/editorial sources.

Two previously known companies were checked in an isolated database, starting with their real earlier saved pages:

| Known company | Newly fetched contact-recovery pages | Current sourced company emails | Professional result |
|---|---:|---:|---|
| Bouquets For Days, UK | 2 | 1 | No matching LinkedIn/X professional capture; official Instagram link and separate indexed Facebook/Instagram hints |
| Portland Coffee Roasters, US | 2 | 0 | Professional lookup not run in this check |

For Bouquets, Common Crawl supplied Contact/About URL hints and the company pages were fetched currently. Since these routes were also present in earlier saved evidence, this run establishes provider/route compatibility, not an incremental-contact-yield claim for Common Crawl. A fresh three-page navigation check recorded the official Instagram link. Search engines returned unrelated LinkedIn/X results for simpler queries; all were rejected. These observations do not prove that no LinkedIn/X account exists.

**Real personal-profile email extraction remains unverified.** Capturing a public company email and finding social URLs does not establish access to a professional bio or private/unpublished email. Google/Brave/DuckDuckGo/Qwant limitations remain in the report. A restricted profile still holds while accessible public company research can continue.

No paid API keys, recipient probes or outbound messages were used. The main operational database was unchanged, and sending remained paused/disabled. The two known companies are not fresh discovery-to-buyer acceptance, and this small test is not a representative vendor comparison or VPS deployment acceptance.

Reproduce with `scripts/verify_multisource_live.py`; it requires the real saved lead IDs 12 and 11, fresh earlier company evidence, a paused operational database and no pending/running operational jobs. It records limits and keeps all recipient evidence in an isolated local database with no running worker.

## Primary references

[SearXNG Search API](https://docs.searxng.org/dev/search_api.html) documents configurable engine selection and notes that engines can interpret operators differently. [Common Crawl index](https://index.commoncrawl.org/) documents the public URL index and cautions against overloading it. [Crawlee concurrency/rate-limit guidance](https://crawlee.dev/python/docs/guides/scaling-crawlers) informed the comparison of pacing, bounded concurrency and resource admission; using those techniques is not evidence of equivalent data coverage.

A separate Bing RSS compatibility experiment returned HTTP 200 with unrelated results. It was rejected as a lead source rather than counted as successful discovery.

Verification: **820 tests passed**, including 25 new provider/quality cases; Ruff, Python compilation and JavaScript syntax passed. Real Chromium exercised the source-summary panel and existing professional review on fictional fixtures, on desktop/mobile, with zero JavaScript errors. The only test warning was the existing Starlette/httpx deprecation.
