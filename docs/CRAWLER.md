# Current recipient-source gate

Extracted or manually saved company-domain addresses require current saved official-page publication before verification or outreach. Public mailto/structured contact extraction is bound to the page HTML hash. The dashboard exposes source holds, and recipient-page changes invalidate approval. See [implementation and acceptance limits](CONTACT_PUBLICATION.md).

# Website research quality

Latest source comparison and recovery acceptance: [Crawlee / Scrapy / Crawl4AI comparison](CRAWLER_REPO_COMPARISON.md). Durable retry/in-flight checkpoints, gzip sitemaps and cooldown indicators supplement the process below; direct restricted-platform email coverage remains unverified.

[Unattended upgrades](CRAWLER_AUTOMATION.md) add automatic bounded continuation, delayed sitemap recovery, latency pacing and resource-aware admission. Visual/contact fallback jobs run once after a worker-driven cycle; default Chromium quality and source-review gates remain in force.

Crawler capability is independent of the VPS size. Default research uses HTTPX, Beautiful Soup and real Playwright Chromium rendering. A small host starts one website job at a time; a larger host can increase `CRAWL_CONCURRENCY` and container resource budgets without changing extraction behavior.

## Research process

1. Normalize the official website and check public DNS. Pin every HTTP connection to a checked global address; browser requests pass through the same fetcher. Private/reserved targets, platform crawling, credentials in URLs and nonstandard ports are rejected.
2. Fetch robots and respect allowed paths, declared crawl delays and request rates. Default page pacing applies between research pages; asset requests use bounded parallelism when robots declares no delay/rate. Cached assets do not cause an artificial network delay. Read declared sitemaps, including nested sitemap indexes. A missing default sitemap is normal; sitemap errors are recorded.
3. Deduplicate tracking URL variants. Prioritize contact, team, about, services, booking, FAQ, product and announcement pages. Category quotas prevent a large catalog from consuming the entire research budget before news is visited. Do not submit forms or enter account/checkout/cart pages.
4. Fetch source HTML and render every selected page by default, including hash-based SPA routes. Load public CDN scripts, fonts, CSS, images and GET APIs. Reuse TLS connections in separate hostname pools and public asset responses during the site job. Stabilize content, scroll to trigger lazy loading, and include visible open shadow-root content.
5. Extract business-domain emails from visible text, mailto links, published JSON-LD Person records, Cloudflare email encoding and explicit `[at]` / `[dot]` notation. Preserve other-domain addresses separately as unapproved candidates, with exact page URL/hash and methods; do not auto-import or probe them. Keep name/role only when explicitly present in structured public data. Ignore arbitrary executable-script strings and hidden rendered content. Never generate guessed email patterns.
6. Save exact source URLs, text hashes, timestamps, extraction methods and contact identity as each page finishes. Record page coverage, renderer failures, resource failures and remaining/depth-limited URLs. Pending resource requests at snapshot time are reported and cancelled before page close, avoiding orphan requests and closed-target callback errors. A late failure or shutdown preserves completed page evidence. Qualification cannot race with research still in progress.
7. Automatically queue full-page desktop and mobile screenshots after research; repeat on demand. Record observed viewport overflow, CTA positions and fields without explicit labels. These are review inputs, not a complete accessibility audit, proof of conversion loss or a claim that a form is broken.

## Controls

| Setting | Default | Meaning |
|---|---|---|
| `CRAWL_MAX_PAGES` | 30 | Per-company page/attempt budget; can increase to 500 |
| `CRAWL_MAX_DEPTH` | 3 | Link depth; remaining URLs are reported |
| `CRAWL_MAX_SITEMAPS` | 6 | Sitemap fetch budget |
| `CRAWL_RENDER_MODE` | always | Browser-render all pages; `auto` renders app shells, short pages and contact/about/team pages; `never` is explicit HTTP-only research |
| `BROWSER_ENABLED` | true | Browser capability enabled |
| `AUTO_VISUAL_AUDIT` | true | Queue desktop/mobile screenshot job after research |
| `CRAWL_CONCURRENCY` | 1 | Simultaneous company research/screenshot jobs, 1–8 |
| `JOB_TIMEOUT_SECONDS` | 1800 | Durable job timeout; increase for sites requesting long crawl delays |
| `BROWSER_RESOURCE_BYTES` | 8 MB | Per-resource bound |
| `BROWSER_PAGE_BYTES` | 60 MB | Per-page transferred resource bound and shared asset-cache bound |
| `BROWSER_RESOURCE_CONCURRENCY` | 6 | Maximum in-flight mediated network requests per rendering session; explicit same-site robots pacing still applies |
| `APP_MEMORY_LIMIT` | 2560m | Compose budget; adjust for the host, not a measured consumption claim |
| `APP_CPU_LIMIT` | 1.5 | Compose CPU budget |

The page/depth/resource bounds prevent unbounded catalogs or hostile sites from occupying the system indefinitely. Reaching a bound yields partial coverage, never a claim that the whole website was inspected. A complete report describes its stated scope; it does not prove the absence of an unlinked feature.

The page budget counts attempted research URLs, including fetch failures, rather than the size of the alias/canonical seen set. Final redirected URLs are captured once; seen aliases are excluded from remaining coverage. A failed browser fulfill operation attempts one terminal abort to settle the request and preserve the useful DOM. If a terminal abort also fails, the page is closed and partial-render evidence recorded, without a pending handler or direct-network fallback. An unowned abort failure closes its browser context. See [the longer live sample](BENCHMARK.md) for the failures that motivated these corrections.

Official pages sometimes publish a Gmail or related-company domain. The dashboard retains these as candidates: publishing alone does not prove company ownership or buyer relevance. An operator must review the current saved official-page extraction and record ownership evidence before adding such a contact. The review is tied to that source hash; changed/removed evidence invalidates it. Ownership checks run before recipient verification, sequence approval/resume and SMTP submission. Shared inboxes already attached to another company cannot be silently reassigned. Fresh conservative verification and outreach eligibility remain separate requirements.

Read-only GET pages/APIs are supported. POST-based GraphQL/search, login-only content, closed shadow roots, challenge pages and external documents need a separately reviewed adapter/source. Mutating requests, sockets, downloads and challenge bypass are not performed. A blocked request or rendering error is surfaced. Screenshots can still be saved with issues, but cannot be treated as a complete render without reviewing the report.

## Independent benchmark

```powershell
.\.venv\Scripts\python.exe scripts/crawler_audit.py https://your-official-test-website --pages 30 --output data/crawler-audit.json
```

This command researches only; it never imports prospects, verifies emails or sends mail. Benchmark several representative service, SaaS, Shopify and JavaScript sites on the actual VPS. Observe `docker stats` and job latency. Raise concurrency only after measuring headroom. The workstation's live JavaScript smoke check does not establish performance on a 4 GB host.

Chromium is installed by the normal Windows startup script and Docker build. If the browser cannot launch, static evidence is retained and the report explicitly says rendering was unavailable. Fix the installation and rerun before making visual/dynamic-content claims.

If a terminal unowned request fails, its original context closes before another page is rendered. The next page recreates a context with the same mediation, socket blocks and sandbox; callbacks cannot close a replacement context. Page-creation failure preserves static evidence and is explicitly reported. Playwright 1.63.0 is required for its upstream interception-update cleanup fix. Windows Chromium regressions pass; current live recovery and actual Linux/container acceptance are distinct checks.

A cleanup task can fail after Chromium has already closed its context. The renderer records that failure and permits recreation only after a confirmed close event; an unconfirmed closure remains a render-start failure. Historical pages survive re-crawls, but only pages refreshed in the latest attempt support new suggestions or qualification. The dashboard labels older captures as history and omits them from qualification source selectors. Selected source hashes/freshness are rechecked in the review transaction, including country, announcement and extra follow-up evidence.

Benchmark deadlines can be set explicitly with `scripts/benchmark.py --timeout 3600`; the manifest records the effective value. This does not change render/page/depth scope or robots pacing. A 10-second declared delay on an asset-heavy site may require a longer research job even on a larger host; deadline/resource limitations stay explicit. Actual cleanup-task recovery has now been observed on live Austin Studio Architects and Yafa Queen pages; see `crawler-recovery-check.json`. The separate extended Goldstein run finished with 30 unique/rendered captures in 2098.21 seconds and no job error; four context recreations preserved subsequent rendering. Resource coverage remains partial. This is full-budget capture/recovery evidence, not complete website or deployment acceptance.
