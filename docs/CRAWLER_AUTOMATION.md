# Unattended crawler upgrades and acceptance

12 October 2026. This extends [the public-repository comparison](CRAWLER_REPO_COMPARISON.md). It implements specific crawler infrastructure improvements; it does not establish Apollo/Apify product parity, a proprietary contact database, or unrestricted platform access.

## Implemented behavior

**Automatic continuation.** The existing durable research job is rescheduled against the same crawl ID instead of refreshing the prospect and replacing current evidence. It carries an automatic pass counter and waits for saved per-request/origin retry times. Defaults are six passes and 180 total page attempts, including failures/interrupted attempts. Both bounds are configurable. An exhausted cycle remains partial/reviewable; a finished job does not mean the entire website was inspected.

Recovered interrupted jobs resume their saved frontier. Superseded checkpoints cannot alter a newer research run. Automatic continuation stops after business qualification or outreach holds. Qualification is rechecked inside the research write transaction, so a review completed during scheduling is preserved. A competing manual research request supersedes the automatic cycle.

Temporary sitemap failures now retain delayed, bounded retry state as company pages do. Uncaptured in-flight sitemap requests also survive interruption. Successful recovery retains failure history with resolution timestamps. Robots-denied requests are removed from retry lanes rather than repeatedly attempted.

**Adaptive pacing.** Following [Scrapy's documented throttling principles](https://docs.scrapy.org/en/latest/topics/autothrottle.html), successful response-header latency adjusts the next page interval by averaging the current interval with a bounded latency target. Error responses cannot decrease that interval. Configured page delay and declared robots pacing remain lower bounds; Retry-After is handled separately. This controls page/sitemap pacing, while browser assets retain their bounded concurrency and declared robots limits. It is our implementation, not Scrapy's extension running inside the application.

**Resource-aware admission.** A shared controller starts at one crawl slot and can scale within `CRAWL_CONCURRENCY`. It samples CPU, memory and available headroom, reduces admission under pressure and pauses new jobs under critical pressure. Active jobs finish rather than being killed. Missing/invalid metrics fall back to serial admission. A separate monitor samples while all slots are busy; inbox monitoring remains a separate lane.

[Crawlee documents resource-based scaling](https://crawlee.dev/python/docs/guides/scaling-crawlers), and [Crawl4AI documents memory-aware dispatch](https://docs.crawl4ai.com/advanced/multi-url-crawling/). Our controller uses [psutil](https://psutil.io/) for host metrics and reads common mounted Linux cgroup limits. An optional process-tree memory budget includes browser descendants. This is admission control with a per-task headroom estimate, not a hard per-browser memory guarantee. Nested/unusual cgroup layouts, Windows job-object limits, actual Linux deployment and the user's future VPS still require deployment acceptance.

**Fairness and supplementary work.** Within existing job priorities, earlier due jobs run before later continuations. Prospects already waiting do not stay behind the oldest prospect's repeated passes. Worker-driven automatic research defers visual audits and contact-search fallback until the bounded research cycle finishes; it does not repeat these expensive jobs after every pass. Current published contact proof avoids an unnecessary fallback search. Supplementary contact research has its own existing page bound.

**Dashboard.** Research results show automatic cycle state/pass, failed-page and sitemap retries, cooldown and resolved-error history. Worker status shows active/desired/maximum crawl slots and the admission reason when telemetry is fresh. Manual Continue remains available for eligible checkpoints; explicit review remains required before outreach.

## Configuration

```dotenv
CRAWL_AUTO_CONTINUE=true
CRAWL_AUTO_MAX_PASSES=6
CRAWL_AUTO_MAX_PAGES=180
CRAWL_ADAPTIVE_PACING=true
CRAWL_ADAPTIVE_MAX_DELAY_SECONDS=10
CRAWL_ADAPTIVE_CONCURRENCY=true
CRAWL_CONCURRENCY=1
CRAWL_MEMORY_BUDGET_MB=0
CRAWL_TASK_MEMORY_MB=512
```

The concurrency setting is a ceiling. A ceiling of one stays serial; a larger configured ceiling permits scaling when headroom is available. Quality remains Chromium `always` rendering by default. No learned HTTP/browser predictor or cross-company browser pool was introduced.

## Evidence

The final implementation passed **652 tests**, including eighteen new automation/admission checks beyond the previous 634-test release. Tests exercise automatic same-job continuation, source-ID preservation, pass/page bounds, delayed retry, interrupted restart, superseded checkpoints, human-review races, due-job fairness, sitemap recovery, continuous resource monitoring, invalid-metric fallback and supplementary-work deferral. Ruff and dependency checks passed. The existing Starlette/httpx deprecation warning remains.

Recovery UI and 17/11/35-node workflow browser checks passed on desktop/mobile with no JavaScript errors and unchanged main operational records. Simulated response states verify automatic-pass and adaptive-slot display; these browser checks do not themselves start live jobs.

`scripts/verify_crawler_autonomy_live.py` used real HTTP and Chromium against four known official sites in an isolated database. The final diagnostic used five page attempts per pass, three passes, a 15-attempt per-prospect cap, a two-slot ceiling and a 360-second overall observation window. Only research workers ran: **no mailbox lane, no verification lane, zero email probes and zero sends**. The normal database's lead/contact/evidence/crawl/job/message/suppression records stayed unchanged.

| Market sample / segment | Saved pages | Company-domain contacts with current publication proof | Other-domain candidates requiring review | Result |
| --- | ---: | ---: | ---: | --- |
| UK / flowers: Bouquets For Days | 15 | 1 | 0 | Partial; three-pass budget exhausted |
| US / coffee: Portland Coffee Roasters | 15 | 0 | 1 | Partial; three-pass budget exhausted |
| UK / dental: Dental Clinic London | 15 | 1 | 0 | Partial; three-pass budget exhausted |
| US / roofing: SmartRoof | 14 | 0 | 0 | Interrupted by the overall diagnostic deadline; sources/checkpoint preserved |

All four prospects entered continuation without manual clicks. Three jobs reached their configured terminal budget; the fourth was interrupted during its last pass. **59 pages, two company-domain contacts and one other-domain candidate** were preserved. A candidate is not an ownership-reviewed buyer or a verified mailbox. Render issues and remaining URLs keep these captures partial.

An earlier diagnostic on the same four sites admitted one slot under the initial headroom rule and saved 31 pages during its overall 360-second window. The later diagnostic admitted two slots and saved 59. Its pass cap also changed from four to three, and system/site load varied. This is a directional throughput observation, not a controlled performance benchmark or a vendor comparison. The earlier six-page two-site smoke and this larger diagnostic also have different total budgets; increased page counts do not establish improved email recall.

Live diagnostic scripts were run while the admission/recovery improvements were being tuned. The final independent telemetry-monitor helper and supplementary-work deferral are verified by the final tests/browser checks; that final helper was not part of the already-running four-site diagnostic. Runtime artifacts are referenced by `data/crawler-autonomy-live-latest.json` and `data/crawler-recovery-ui-check.json`. Runtime databases, credentials and extracted data are excluded from the source release.

## Remaining limits

Reliable direct email extraction from restricted LinkedIn/X/PeoplePerHour profiles remains unestablished. The system can use public search signals and independently matched official websites; unavailable/unpublished information cannot be turned into verified contacts by an optimization. Broader discovery consistency, real website-less contact acceptance, relevant-buyer coverage and actual VPS throughput remain separate acceptance requirements. Apollo's contributor/provider dataset and Apify's hosted actors/platform coverage were not reproduced or benchmarked.
