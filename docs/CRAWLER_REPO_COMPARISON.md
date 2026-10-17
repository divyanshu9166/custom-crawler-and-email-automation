# Public crawler comparison and recovery verification

**Later implementation:** [unattended crawler upgrades](CRAWLER_AUTOMATION.md) supersede the manual-only retry, absent adaptive pacing/concurrency and sitemap-recovery gaps recorded in this earlier comparison. Its 634-test/two-site results remain historical evidence; use the linked report for current verification.

Checked on 12 October 2026. This is a source/documentation capability comparison plus local regression and live compatibility checks. We did **not** benchmark our crawler against running Apollo, Apify actors, Crawlee, Scrapy or Crawl4AI on identical workloads. No parity or universal email-coverage claim is supported.

## What the comparison means

Apollo is a contact-data product, not just a public-page crawler. Its [official data description](https://www.apollo.io/product/b2b-data) includes a contributor network, third-party providers and public-web collection. A crawler that extracts currently published business emails cannot reproduce that dataset simply by adopting another repository.

[Crawlee Python](https://github.com/apify/crawlee-python), [Scrapy](https://github.com/scrapy/scrapy) and [Crawl4AI](https://github.com/unclecode/crawl4ai) are relevant open-source comparisons. Their infrastructure capabilities are useful; they do not make a platform publish an email, establish the buyer's identity, or prove a mailbox exists. We inspected the upstream retry/reclaim logic in Scrapy's `downloadermiddlewares/retry.py`, Crawlee's `_basic_crawler.py`, and the rate/memory dispatchers in Crawl4AI's `async_dispatcher.py`. Upstream code was read, not installed or executed.

| Capability | Public project reference | Our current implementation and limits |
| --- | --- | --- |
| HTTP and Chromium research | [Crawlee adaptive crawler](https://crawlee.dev/python/docs/guides/adaptive-playwright-crawler) | Both paths exist, with checked HTML reuse and asset caching. Default still renders all selected pages. `auto` is a heuristic, not Crawlee's learned predictor or output-equivalence sampling. |
| Saved frontier and duplicate filtering | [Scrapy resumable jobs](https://docs.scrapy.org/en/latest/topics/jobs.html), [Apify request queues](https://docs.apify.com/storage/request-queue) | Persisted company frontier, captured-page deduplication and source evidence. Added durable in-flight URL recovery and bounded per-URL retry state. This is one local worker controller with SQLite, not a distributed crawl service. |
| Temporary failures and throttling | [Scrapy retry middleware](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html), [AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html) | Bounded inner HTTP retries, robots pacing and request deadlines already existed. Added delayed continuation retries and origin cooldown. No latency-driven AutoThrottle equivalent. |
| Adaptive concurrency | [Crawl4AI multi-URL dispatcher](https://docs.crawl4ai.com/advanced/multi-url-crawling/) | Configurable company concurrency and bounded browser requests. No memory/CPU-adaptive dispatcher; VPS throughput and memory usage remain unverified. |
| Email-source evidence | Our publication gate | Visible text, mailto and structured/obfuscated published contacts are saved with official-source proof. Other-domain addresses require ownership review. Buyer relevance and Reacher results remain separate gates. |
| LinkedIn, X and marketplace coverage | Existing live acceptance reports | Search signals and independently matched official websites are supported. Reliable direct email extraction from restricted platform profiles has **not** been established. PeoplePerHour job/category pages cannot be treated as company prospects. |

## Changes implemented

1. A transiently failed URL is no longer permanently lost merely because it was marked seen before fetching. The checkpoint retains its depth, failure count and next eligible time. Captured pages remain intact during continuation.
2. `CRAWL_RESUME_MAX_RETRIES=2` allows at most two additional continuation attempts after the first failed page attempt. Existing `CRAWL_HTTP_RETRIES` limits inner requests separately. Exhaustion remains a visible unresolved issue; 403, missing pages and access challenges are not automatically retried.
3. Origin-level Retry-After cooldown from robots, pages or sitemap fetches blocks additional crawl-page requests and later continuation until eligible. Pending per-URL retries do not delay unrelated queued pages unless an origin cooldown applies. Checkpoint/API checks run before the next robots request.
4. Checkpoints persist before a page starts and after it finishes. Cancellation or process interruption preserves an uncaptured in-flight URL for continuation; current evidence IDs survive recovery. Successful retry capture marks historical retryable errors resolved rather than deleting them.
5. `.xml.gz` and gzip-typed sitemap files support bounded decompression, including concatenated members. Malformed, truncated, CRC-invalid, oversized or trailing garbage data is rejected. HTTP-level gzip already decoded by HTTPX is not decompressed a second time.
6. Customer authentication/sign-in paths are excluded from company research. The live US site exposed a customer-login redirect consuming a page attempt; filtering it freed that attempt for research.
7. Explicit `never` rendering mode no longer reports a missing renderer as an error. Default remains `always`.
8. The dashboard shows retry counts, site cooldown and resolved issue history. Continue is disabled during the wait. Retry entries currently use **Continue crawl**; no new unattended scheduler for partial-crawl continuation was introduced in this change.

## Verification

- **634 tests passed**, with the existing Starlette/httpx deprecation warning. Seventeen new crawler recovery tests cover failed contact recovery, retry exhaustion, permanent denials, cancellation, pre-network cooldown, gzip limits and authentication-path filtering. Ruff passed for `outreach`, `tests` and `scripts`.
- Recovery UI checks passed for future/due retry states, origin cooldown overriding a pending frontier, displayed issue history, mobile overflow and zero JavaScript errors. These states were injected into read-only browser responses; no real crawl job was started by this UI test.
- Existing 17/11/35-node workflow browser checks passed after the server restart. Main operational records stayed unchanged; sending remained disabled and paused.
- `scripts/verify_crawler_recovery_live.py` ran real HTTP and Chromium research on two known official sites in an isolated database, with six page attempts and a 120-second deadline per site. Verification workers were off: **zero email probes and zero sends**.

| Final live sample | Saved pages | Stored published emails | Current publication proofs | Capture status |
| --- | ---: | ---: | ---: | --- |
| Bouquets For Days, UK | 6 | 1 | 1 | Partial; 15 URLs remain and render issues require review |
| Portland Coffee Roasters, US | 6 | 0 | 0 | Partial; 112 URLs remain and render issues require review |

After filtering the observed customer-authentication URL, the same US six-attempt smoke saved six pages rather than five. This is a small compatibility observation, not a general performance benchmark. The published-email count stayed zero for that US sample. Local reports are referenced by `data/crawler-recovery-live-latest.json` and `data/crawler-recovery-ui-check.json`; runtime data is excluded from the source release.

## Remaining acceptance gaps

The improvements do not remove partial browser renders, protected pages or unpublished emails. Failed sitemaps remain recorded for review/fresh research; this new delayed retry lane recovers company pages rather than every sitemap failure. A real website-less prospect contact path, relevant decision-maker consistency, broader segment coverage, adaptive resource scaling and deployment acceptance still need evidence.

Keep the source/provenance and email-verification gates in our custom pipeline. Crawlee's self-hosted adaptive crawler is a reasonable candidate for a future measured adapter experiment; it does not require adopting paid Apify actors. Before replacing the fetch layer, compare source/contact recall, supported page captures, latency and memory on the same representative sites, preserving the existing network and publication gates.
