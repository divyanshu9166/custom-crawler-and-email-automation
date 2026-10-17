# Outreach Workbench

A cold email system for US/UK prospects. Campaign A covers website development/improvement and inquiry/booking chatbots. Campaign B covers new/existing D2C stores, shopping/support chatbots and permission-based WhatsApp opportunities. Crawler quality takes priority; host size controls concurrency and throughput.

**Pre-VPS platform updates:** managed LinkedIn/X search now supports bounded
scroll/Next snapshots, deduplicated partial results and visible search coverage.
FxEmbed bio caches, rate-limit holds and pacing survive app restarts without
renewing source timestamps. [Implementation and acceptance limits](docs/PRE_VPS_PLATFORM_UPDATES.md).
Latest complete-suite results are in VALIDATION.md; older counts below retain
their historical scopes. Authenticated VPS access remains pending.

**Email-writing correction:** operational emails now require research-based AI writing from current reviewed business evidence and one selected offer. There is no template fallback. Legacy drafts are visibly held and cannot be approved. Settings includes an AI email writer section. Controlled provider and browser checks passed, while live model quality remains unverified because no endpoint/key/model is configured. Sending remains disabled/paused. See [the correction and acceptance limits](docs/AI_EMAIL_WRITING.md).

**Current crawler verification: 652 tests passed.** Automatic checkpoint continuation, bounded sitemap recovery, adaptive pacing, resource-aware job admission and fair scheduling are implemented. A four-site US/UK diagnostic preserved 59 pages, two company-domain contacts and one other-domain review candidate; captures remain partial/interrupted. No Apollo/Apify parity claim is supported. See [the upgrades, live results and remaining limits](docs/CRAWLER_AUTOMATION.md), and [the public-repository comparison](docs/CRAWLER_REPO_COMPARISON.md).

**Later free-source verification: 666 tests passed.** Profile-backlink/organization matching and indexed contact-page seeds improve the public-source path. Three recorded LinkedIn/X signals resolved to website candidates and preserved 12 pages plus two ownership-review email candidates. Direct platform snapshots remain denied; unpublished contacts and vendor parity are not achieved. See [current platform-access progress and the incomplete goal](docs/PLATFORM_ACCESS_PROGRESS.md).

**Browser-reference intake: 680 tests passed.** Save a visible public business-profile website link with its source/time in Find prospects. New companies enter normal website research; existing reviews stay intact. A live Fonte reference yielded six partial pages and one ownership-review candidate; a Sonria booking link failed DNS. These are operator-observed references, not automatic server profile captures. Sending remains disabled/paused.

**Public X post adapter: 705 tests passed.** Automatic discovery can process known public X/Twitter status URLs through X's official publishing service without an API key/session. Three real known business posts were captured; none contained email addresses. Author/post matching, bounded responses, source hashes and current website corroboration are enforced; denials/rate limits are held. This does not fetch profiles, enumerate timelines, reveal unpublished emails or establish consistent fresh discovery. See [the access audit](docs/PLATFORM_ACCESS_PROGRESS.md).

**Browser connector: 720 tests passed.** The local extension can collect supported visible business website fields automatically on a tab you explicitly enable. Export and reviewed dashboard import replace manual copying. Source provenance remains unverified until normal company research/review. The connector is prepared, not installed in the normal browser; site/permission reliability and unrestricted server access are not established. [Setup and verification](docs/BROWSER_CONNECTOR.md).

**Previous UI regression run:** **581 tests passed** after the execution-visibility update. Chromium checked 17/11/35-node maps, actual idle state, selected research navigation, review-gate navigation, simulated active work/stale heartbeat and failed-refresh recovery on desktop/mobile. Operational data was unchanged and sending remained disabled. See [the workspace guide](docs/UI_WORKSPACE.md).

**Previous complete-workflow node audit:** all 35 nodes and 46 connections mapped to code and passing checks at that audit; **575 tests passed**, including 18 complete-workflow cases and four connected Campaign A/B website/profile journeys using real loopback TLS SMTP/IMAP, plus 22 pilot regressions, 27 recovery regressions, four learning-freshness regressions, 17 contact-publication regressions, ten priority-readiness regressions, 15 offer-source-quality regressions, thirteen native-backend setup regressions, thirteen verification-dispatch regressions and five draft-source regressions. Full Chromium UI checks passed. Expired ownership evidence, changed approval context, stale artifact/proposal readiness and missing call next-action checks are corrected. See [the node-by-node report](docs/COMPLETE_WORKFLOW_AUDIT.md) and [source/test evidence](docs/complete-workflow-check.json). External provider/deployment/client acceptance remains separate; sending stays disabled.

**Latest live lead check:** two real discovery waves across eight US/UK campaign/segment cells reused 16 candidate company records. Eight researched representatives preserved 205 current official pages and nine company-domain contacts plus one reviewed owner Gmail. Seven of eight had a published email. All captures remain partial/interrupted; qualified-buyer consistency and a real website-less contact are not yet accepted. Actual restricted-source probes, exclusions and fixes are documented in [the live acceptance report](docs/LIVE_LEAD_ACCEPTANCE.md). Sending stays disabled/paused.

Company-domain contacts now need current saved publication proof before verification or outreach. The dashboard explains source holds; recipient-page changes invalidate approval. Manual/CSV intake remains available for pending research. See [publication checks and live limits](docs/CONTACT_PUBLICATION.md).

**What is built:** profile-first prospects without a known website, public-web discovery and recurring searches, company CSV imports, sitemap-based website research with real JavaScript rendering, source-backed contact/identity extraction, desktop/mobile screenshots, crawl coverage reports, Reacher verification, an authenticated review dashboard, optional AI research suggestions, research-based AI email writing with four reviewed touches, SMTP sending, independent IMAP reply/bounce handling, unsubscribe/suppression, durable jobs, audit history, CSV export and database backups.

The workflow manager also records shared manual outreach history, client qualification, calls/next-action dates, proposal review/delivery, agreement/payment references and project acceptance/outcomes. It prepares source-backed audit, annotated screenshot, homepage concept, interactive FAQ prototype and WhatsApp-flow artifacts for review/export. External conversations, actual bookings, payments and client delivery are recorded by the operator; no fictional test is presented as a real client action.

Pipeline now orders review work using an explainable current-evidence/contact score. Ranking shares the workflowâ€™s current Campaign A/B offer guard, including separate D2C commerce proof, canonical country-source URLs and US/UK scope. Future-dated research cannot earn source credit. See [the ranking recheck](docs/PRIORITY_READINESS.md). Company details record actual USD/GBP costs, payments and refunds with correction history, plus post-delivery maintenance/expansion plans and permission-reviewed case studies. Learning shows recorded economics and dated client plans. These features preserve review/send gates and do not imply verified revenue, causal ROI or automatic client publication. See [feature details](docs/PRIORITY_FINANCE_AFTERCARE.md).

Learning now counts current business qualification through the workflowâ€™s fresh evidence and reviewed-offer guard. Expired, future-dated or superseded sources cannot inflate current qualification; historical approval and SMTP acceptance remain preserved.

The **Learning** view calculates campaign/service/country/industry results from saved SMTP acceptance, human email replies and recorded sales milestones. Approval freezes the sending context; repeated messages/replies cannot inflate business-record conversion counts. Missing samples and legacy attribution stay unknown. See [LEARNING.md](docs/LEARNING.md) and [the README/original-workflow comparison](docs/README_WORKFLOW_CHECK.md).

**Live boundaries:** VPS access, production sender identity and mailbox credentials remain user-owned. The actual native Reacher backend now passes API/auth checks; an earlier sourced SMTP test returned catch-all/risky; a newly discovered official-site contact now returned safe/non-catch-all. One result does not establish general accuracy or guaranteed mailbox existence. Sending is disabled and globally paused. Individual mailbox existence, broader provider accuracy and delivery remain unproven. See [native backend proof and startup instructions](docs/NATIVE_REACHER.md). See [VALIDATION.md](VALIDATION.md) for exactly what was tested.

**Workspace UI:** Workflow offers an eleven-stage overview and the complete 35-node / 46-connection map with saved status, execution modes, conditional routes, per-prospect filtering and node drag/pan/zoom. Running now reports actual active jobs separately from the recommended next step. Saved research counts and a direct prospect-data action are visible in all three map views; review gates open their node inspector. Worker freshness and failed refreshes are explicit. Settings saves business identity, SMTP/IMAP connections, sending limits and sign-in credentials. See [workflow and settings instructions](docs/UI_WORKSPACE.md). Moving nodes changes the visual layout only.

**Every-node audit:** the earlier 35-node map audit is preserved in [EVERY_NODE_AUDIT.md](docs/EVERY_NODE_AUDIT.md); [COMPLETE_WORKFLOW_AUDIT.md](docs/COMPLETE_WORKFLOW_AUDIT.md) is the current 537-test verification. The full graph is displayed alongside Overview. Domain/VPS/mailbox setup is user-owned; local development continues independently of later live provider/client acceptance.

Offer suggestions now exclude legal boilerplate, rejected marketplaces, foreign pages and bare contact/FAQ menu labels. Stronger booking/product evidence takes precedence; unqualified legacy suggestions are rechecked before form prefill. Eleven saved candidates produced eight reviewable offer sets and 32 unsent preview messages without any normal-record changes. This is saved-source replay, not new qualified lead yield. See [source-quality verification](docs/OFFER_SOURCE_QUALITY.md) and [draft previews](docs/OFFER_DRAFT_PREVIEWS.md).

**Second business workflow:** every campaign/service branch has executed checks. Company details show 15 service-selection statuses, sourced offer choices, D2C stage/model review and explicit WhatsApp fit/permission states. Current source snapshots gate artifact creation/review; changed or historical sources are held. Real candidates still need business review. See [the second-workflow audit](docs/SECOND_WORKFLOW_AUDIT.md).

**Third business workflow:** all 23 diagram boxes have passing behavioral evidence. Approval freezes sources, recipient, sender and copy; queued sends and reviewed resumes recheck this context. Unsent pilots can return to draft review without erasing history. Calls/proposals record a baseline or measurement plan, proposal review rejects changed client needs, and project completion requires existing delivery tasks to close. See [the third-workflow audit](docs/THIRD_WORKFLOW_AUDIT.md) for each node's automated/manual boundary and local test evidence.

**Earlier contact-source optimization:** recovery now uses saved official contact/team routes and crawl-checkpoint links when search fails, with a bounded homepage-navigation fallback. The real isolated check recovered four previously known published inboxes from two Skindays pages and none from two SmartRoof pages; both captures remain partial. Full suite: 460 passing tests. This is existing-candidate recovery, not new lead yield, buyer qualification or private social-email access. See [the implementation, results and limits](docs/CONTACT_SOURCE_FALLBACK.md).

**Earlier research recovery:** automatic official contact/team source research follows full website research. **Continue crawl** preserves current evidence and processes another page batch; older partial records can reconstruct a frontier from fresh official-page links. Actual normal-dashboard continuation grew SmartRoof from 30 to 41 saved pages, with overall coverage still partial. Three contact-research passes across SmartRoof/Portland captured 18 pages, including repeated refreshes, and found no new published inboxes. The wrong Reacher endpoint is held before real-recipient submission; free syntax/DNS fallback never establishes a safe mailbox verdict. That earlier run lacked a backend; the current native runtime and live recipient checks are documented above. See [recovery behavior and real results](docs/RECOVERY_PATHS.md).

**Earlier live no-send pilot:** four real US/UK Campaign A/B searches issued 36 queries through the native SearXNG backend. The normal worker saved/rendered **112 official-site pages across four website candidates**, with desktop/mobile screenshots and **five published email candidates after excluding a dedicated privacy inbox**. A noisy marketplace match was rejected. All four crawls are partial and all candidates remain unqualified; no drafts were approved and no email was sent. See [the historical results, fixes and boundaries](docs/NO_SEND_PILOT.md).

**Earlier crawler comparison:** homepage-first scheduling, bounded temporary retries, checked HTML reuse in Chromium and clearer coverage diagnostics are implemented. On the same four sites under the same 180-second diagnostic, saved pages increased from 35 to 36; three sites yielded captures, one remained blocked by HTTP 403, and the published inbox count stayed at one. See [the comparison and limits](docs/CRAWLER_OPTIMIZATION.md).

## Architecture

```text
SearXNG / optional SerpApi / CSV with official business URLs
  -> indexed LinkedIn/X/PeoplePerHour/business-directory signals + deduplicated company candidates
  -> robots-permitted public snapshots + official-site resolution; ambiguous matches held
  -> matched website: robots + sitemaps + HTTPX + Beautiful Soup + Playwright Chromium
  -> no known website: public-profile evidence + website search + held contact candidates
  -> saved evidence + business-domain emails + held ownership-review candidates
  -> Reacher: safe / catch_all / risky / invalid / disposable / unknown
  -> review company, country, buyer and ONE service
  -> generate and edit 4 source-grounded email drafts
  -> approve eligible contact + all messages
  -> SMTP -> IMAP replies / bounces -> stop, hold or suppress
```

The Python app is the sole owner of job and email state. SQLite WAL uses a persistent volume; an OS lock permits only one worker controller. That controller runs separate mailbox, provider and configurable browser job lanes. This is a single-operator deployment. See [the complete workflow](docs/WORKFLOW.md) and [crawler capabilities and limits](docs/CRAWLER.md).

n8n is optional: it can schedule discovery via API, but must not also schedule outbound messages. The app includes recurring discovery already, so the cheapest/smallest deployment can omit n8n. Hermes is not required.

## Start locally on Windows

Run in this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/init_env.py
.\.venv\Scripts\python.exe -m uvicorn outreach.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open http://localhost:8000. Use the normal sign-in form with `ADMIN_USER` and the generated `ADMIN_PASSWORD` from your local `.env`; browser Basic-auth popups are no longer required. The signed session cookie is HttpOnly, SameSite Strict, expires after eight hours, and is Secure on HTTPS. Writes require the configured Origin. Basic and Bearer authentication remain available to API clients. The initialization script never prints passwords and refuses to overwrite an existing file. Treat `.env`, database files and backups as private. On Windows, use your user account's private folder and ACLs; POSIX `chmod` does not enforce Windows permissions.

To explore the dashboard before configuring a VPS or mailbox, run this from the project folder:

```powershell
.\scripts\start.ps1 -Demo
```

This launcher installs dependencies/Chromium if needed and opens an isolated `data/demo` database with clearly labelled fictional companies and sample drafts. Visit http://localhost:8000 using the local `.env` login. Demo jobs can be queued to inspect the interface, but provider/research/mailbox workers never run and sending cannot be resumed. The database stays offline even if live credentials are configured later. Close the server with Ctrl+C; use the launcher without `-Demo` for the separate normal database.

Use the hostname that matches `PUBLIC_URL` exactly: browser writes are protected by an Origin check. For example, `http://127.0.0.1:8000` is a different origin from `http://localhost:8000`.

## Configure the system

Use **Settings** in the sidebar for sender identity, SMTP/IMAP, sending limits and username/password changes. Initial setup and infrastructure/provider settings still use `.env` locally. Saved workspace settings override matching `.env` fields on application restart. After changing sign-in details in Settings, use the new credentials. Saving email settings pauses sending; it does not verify the provider or enable sending. Do not paste passwords into chats or commit them. Back up private `data/workspace-settings.json` separately alongside `.env` and the database.

| Setting group | What to provide |
|---|---|
| Sender identity | Name, business name, real sending email, website and postal address |
| Mailbox | SMTP/IMAP hosts, ports and account credentials; supported provider app password if needed |
| Public URL | HTTPS URL with working DNS/TLS so unsubscribe links are reachable |
| Authentication | Configure SPF/DKIM/DMARC with your mailbox provider; set `DOMAIN_AUTH_CONFIRMED=true` only after checking |
| Reacher | Backend URL/secret, real EHLO hostname and MAIL FROM address matching your verification infrastructure |
| Search | SearXNG URL, or `SEARCH_PROVIDER=serpapi` plus `SERPAPI_KEY` |
| AI research, optional | `OPENAI_API_KEY` and `OPENAI_MODEL` for research suggestions only |
| AI email writing, required for drafts | Settings â†’ AI email writer, or `DRAFT_API_URL`, `DRAFT_API_KEY`, `DRAFT_MODEL`; a chat-completions endpoint whose terms permit the intended use |

Without an AI key, research still extracts evidence/emails and proposes services from explicit public inquiry, shopping, support, new-service/store-launch or WhatsApp signals. Each proposal preserves an exact current quote and requires review. Weak or negative evidence stays in the research/review queue; no absent feature, lost sales or channel permission is inferred. A profile-only launch proposal requires a completed website search with no match. The reviewer confirms business/buyer fit and one useful offer before drafting. With AI configured, the model proposes additional quote-grounded opportunities; interpretation still needs review, and free proposals remain a fallback when usable AI findings are absent. The model gets no sending tools or credentials. See [service proposal limits](docs/SERVICE_PROPOSALS.md).

SMTP/IMAP in this version uses TLS and password/app-password authentication. OAuth-only accounts need an adapter or an SMTP/IMAP-capable account before live use. No bulk-email provider subscription is required. All SMTP acceptance is labelled **accepted**, never **delivered to inbox**.

## VPS deployment

Track pending upload, TLS/provider/browser-session, research acceptance, mailbox,
resource and restore tasks in [the VPS checklist](docs/VPS_DEPLOYMENT_CHECKLIST.md)
and [the implementation plan](PLAN.md). Local tests do not complete server acceptance.

Start with app + Chromium + Reacher + SearXNG. Browser research is enabled by default; n8n is optional because recurring search is already built in. On a 4 GB host start with `CRAWL_CONCURRENCY=1`. The default app budget is 2560 MB plus 512 MB for Reacher and 384 MB for SearXNG, leaving limited OS headroom. These are **budgets, not measured consumption or a smooth-performance guarantee**. Benchmark representative sites using `scripts/crawler_audit.py` and inspect `docker stats`. If the host struggles, increase the host/worker budget; retain rendering and extraction capabilities.

For a larger VPS, raise `APP_MEMORY_LIMIT`, `APP_CPU_LIMIT` and then `CRAWL_CONCURRENCY` after measurement. Crawl page/depth budgets are independent of RAM. A full Rust build can require more memory than steady-state runtime; build Reacher on a larger build machine when needed.

1. Install Docker Engine + Compose on a Linux VPS. Point a hostname to it.
2. Copy the repository and generate/edit `.env` on that server. Set `PUBLIC_URL=https://your-hostname`.
3. Configure verification identity and confirm that the provider permits outbound TCP/25.
4. Build and start:

```sh
python3 scripts/init_env.py
docker compose --profile verify --profile search config --quiet
docker compose --profile verify --profile search up -d --build
docker compose ps
docker stats --no-stream
```

The initialization step is needed only if `.env` does not exist. API keys are not required for it. The app's internal provider URLs are overridden by Compose to `http://reacher:8080` and `http://searxng:8080`. To use externally hosted providers, change those two Compose environment values explicitly.

Use the example Caddy reverse-proxy configuration in `deploy/Caddyfile.example` for HTTPS. Only app port 8000 is published to loopback; Reacher and SearXNG are internal. Restrict SSH and keep the server patched. Caddy installation/domain provisioning depends on the VPS and is not done by this repository.

Chromium launches with its sandbox enabled and without inheriting mailbox/API secrets. Compose includes the official Playwright seccomp profile with namespace permissions and a 512 MB shared-memory allocation. Linux user namespaces must work on the actual VPS/container kernel. A sandbox startup failure is reported as incomplete rendering; the code does not silently disable it. Docker/browser runtime validation remains part of deployment.

**Reacher build:** `deploy/reacher.Dockerfile` pins source commit `681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67`, whose root and backend declare MIT. It runs SMTP-only without embedded Chrome, RabbitMQ or Postgres. Building Rust may exceed the small VPS's resources: build this image on a larger machine/CI, then transfer it with `docker save` / `docker load`. The source-build recipe must be validated in Docker before production; Docker was unavailable on the implementation workstation. Historical release/image licenses can differâ€”do not substitute an arbitrary old image assuming it has this commit's license.

The pinned SearXNG and n8n digests were resolved during implementation. Base build images still use maintained language/OS tags. Review updates and re-test deliberately. n8n uses its own license; availability to self-host does not mean all redistribution/hosting uses are unrestricted.

## Reacher verification is not proof that a mailbox exists

The adapter calls the documented synchronous `/v0/check_email` endpoint with `x-reacher-secret` when configured. It requires consistent syntax, MX and SMTP checks, no catch-all/disposable/disabled/full-inbox flags, and `is_reachable=safe` before approval. Missing fields, timeout, blocked SMTP or ambiguous responses remain held. Results expire after 72 hours by default and are refreshed before a due send.

The `/v0` endpoint does not apply the newer Reacher queue throttle. This app serializes checks and spaces them by at least 10 seconds. A valid result neither establishes identity nor grants outreach permission. Some mail servers conceal mailbox existence or block probes. Port 25, reverse DNS/EHLO, IP reputation and recipient server behaviour affect results. Hosting/proxy costs can still apply even when software is free. Do not use repeated retries or proxies to evade a provider's restrictions.

## Daily operating flow

1. In **Find prospects**, search for a specific business type and US/UK location, import `examples/leads.csv` adapted to real companies, or add an official website. Searches automatically expand to configured platform domains, including LinkedIn company profiles, X, PeoplePerHour, Clutch and Crunchbase. The app resolves public signals to candidate company websites, queues website research and extracts published contacts. Search/indexed results and name/domain correlations remain unqualified candidates. Progress, ambiguous matches and engine failures are saved in Operations; matched platform evidence appears on company details. Newly found candidates/signals are streamed to the database, so a later cancellation does not discard earlier findings.
2. Open a company in **Pipeline**. Inspect saved source pages and extracted company-domain emails. Officially published addresses at another domain appear separately as ownership-review candidates; they are not imported or probed automatically. Before adding one, review the current source and record why it belongs to this business and is relevant. An unknown personal/freemail address is not a fallback. The system never fabricates name-pattern emails.
3. Confirm company name, country evidence, prospect timezone, business type and fit. Country qualification now requires an exact location quote from a saved official page. Record industry when established; choose one campaign-supported service, an exact source quote, a factual observation and a useful suggestion. WhatsApp offers require channel-fit notes distinguishing observations from permission/workflow questions. A website crawl cannot establish private traffic/conversion losses or WhatsApp consent.
   Optionally add a reviewed announcement and an extra follow-up idea, each with its own saved source and exact quote. The writer receives reviewed observations and source context; all four touches need exact source-support metadata. Draft text and distinct follow-up value require operator review.
4. Choose the relevant contact; enter their sourced name/role, review Reacher's result, then write research-based AI drafts. Missing configuration or provider/validation failure preserves existing copy and produces no template fallback. Legacy template drafts cannot be approved. Anonymous `info@` or `hello@` inboxes require a reason for using them; they are not silently treated as founders.
5. Read/edit all four messages. Record outreach eligibility and buyer relevance; approve the sequence. Real identity and unsubscribe instructions are added to every email.
6. When the mailbox and infrastructure are ready, set `SENDING_ENABLED=true`, restart the app, then choose **Resume sending**. An up-to-date, fully caught-up IMAP monitor is required; missing/failed monitoring stops sending.
7. Review replies in the activity log/mailbox. Any reply stops the sequence. Out-of-office and temporary delivery notices hold it. Opt-outs and permanent failures suppress the address across imports and campaigns.

Default touches are day 1, 4, 9, 15, with actual send spacing of 3, 5, 6 days and local weekday 09:00â€“17:00 windows. Delays never cause multiple overdue touches to fire together. The default daily quota is 20 across all sequence touches, not a promised safe volume; tune to mailbox/provider limits and actual results. US timezone is confirmed per prospect; the system does not assume all US businesses share one timezone.

This version is deliberately review-first. It automates acquisition operations but cannot guarantee a named decision-maker's public email, a correct pain-point interpretation, replies or clients.

## Continue a conversation and manage the sales workflow

Open a company and expand **Shared history and sales workflow**:

1. Record existing manual LinkedIn/email/X/call activity. An actual outreach/reply/opt-out applies a company hold, preventing a parallel cold-email sequence. A note alone does not. Unanswered manual outreach can be explicitly released after review; replies, opt-outs and sales conversations stay stopped. Held email contacts still need their separate reviewed resume.
2. An IMAP human reply creates one next-action task and a shared hold. Review the actual reply; the app does not classify every reply as interest. Record the confirmed problem, goal, metric, buyer, timing and budget context before qualifying an opportunity.
3. Prepare a promised value artifact from reviewed saved findings. Audit/concept/FAQ/WhatsApp-flow output is standalone HTML. Extra audit points require exact source quotes; optional callouts reference an existing company PNG. Inspect the exported file before approving it. FAQ prototypes return approved excerpts and are explicitly labelled as prototypes, not live AI/support integrations.
4. Add dated audit/demo/call/proposal/delivery tasks and record what actually happened when closing them. Nurture requires a future next-action date; won/completed records need agreement, initial-payment and acceptance/outcome references.
5. Create a scoped proposal from client-confirmed qualification: problem, scope, deliverables, timeline, exclusions, acceptance criteria, payment/support and ownership/revision/change terms. Each proposal is a preserved Markdown draft. Review it, deliver it through your real conversation, then record the delivery reference. Proposal/won/delivery/completed stages require a reviewed, delivered proposal.
6. Use Operations for stage counts, due tasks and contract values by currency. Those values are operator-recorded contracts, not independently verified revenue or payment receipts.

Database schema version 4 includes the workflow, profile, finance and post-client tables; additive migrations preserve existing lead/contact/message history. Back up the database before deploying a new release. Proposal and artifact downloads require dashboard authentication.

## Safety and recovery behaviour

- Repeated jobs are deduplicated. Research failures have bounded retry/backoff; permanent validation errors go to the failed-job list.
- One active/held conversation per company. Global email suppression survives re-imports.
- Connection/TLS/login or message-construction failures before submission pause sending and leave the message queued. Explicit SMTP rejection holds the contact. A lost response after submission is **uncertain**, never retried automatically. Check provider logs using the stored Message-ID, reconcile as sent/not sent, then separately review a held contact before resuming. A disconnect during QUIT after acceptance does not resend the message.
- A crash during send marks the attempt uncertain on restart. Exactly-once email delivery cannot be guaranteed across SMTP/network failure; this design favours avoiding duplicate sends.
- Approval freezes drafts. Re-research cannot overwrite a company's active conversation evidence.
- Approval, review and draft generation recheck state within a database transaction. Concurrent requests cannot approve the same sequence twice or overwrite activated messages. Late automatic replies, temporary SMTP errors and restart recovery preserve a human reply or opt-out.
- Unsubscribe GET shows a confirmation; POST suppresses immediately, including one-click POST. Opaque tokens are not exposed in server access logs.
- Crawling honours robots, limits page count/size, rejects private/reserved network targets and pins checked IPs. Platforms remain signal sources rather than company crawl roots. Default automatic research uses indexed results and single public-page snapshots only where robots permits access. The opt-in VPS browser mode instead uses an operator-owned normal session for visible business fields, with login/challenge/denial holds. Neither mode solves bot checks or exposes unpublished data.
- Playwright research and screenshots load public CDN assets through the same checked fetcher. Resource/render failures, blocked POST requests and unvisited pages are recorded. Partial renders need review before making visual or missing-feature claims.
- IMAP reads a bounded 64 KB prefix per message. Very large/complex mail and replies moved to unmonitored folders can need manual attention; configure the sending mailbox so replies/bounces reach the selected folder. Matching uses thread IDs first, then sender, with DSN handling. It does not automatically answer a prospect.

## PeoplePerHour and free software choices

PeoplePerHour is now included in automatic indexed-signal discovery; robots-permitted public project/profile snapshots are supported. Anonymous projects, multiple website links and unclear company matches stay unresolved. Platform sourcing does not establish a buyer's identity or permission to contact them outside the platform. Logged-in pages and messaging are not automated.

Apify and Apollo are not dependencies. The free self-hosted search backend can be started locally on Windows without Docker:

```powershell
.\.venv\Scripts\python.exe scripts/local_search.py --install
.\.venv\Scripts\python.exe scripts/local_search.py
```

The launcher pins SearXNG source `f4822b3fc46726bb259d14c6332b702c76b98f82`, installs its dependencies into a separate private environment, and binds to loopback port 8888. It is a development server; production uses the Linux/container deployment. Its Windows adapter only supplies the otherwise-unused POSIX diagnostic import with Valkey disabled. Search engines can return CAPTCHA, rate limits, irrelevant results or no data; these are reported, not bypassed. `DISCOVERY_PLATFORMS`, `DISCOVERY_MAX_SIGNALS` and `DISCOVERY_QUERY_DELAY_SECONDS` control source coverage and pacing without reducing website-render quality. The discovery market chooses en-US/en-GB; `SEARCH_LANGUAGE` is the default for standalone provider lookups. A free search backend still depends on accessible search indexes; it cannot expose unpublished emails.

Free repositories used/considered:

- [SearXNG](https://github.com/searxng/searxng): self-hosted metasearch; JSON search API. Search engines may rate-limit or return no results; free software does not guarantee Google access.
- [HTTPX](https://github.com/encode/httpx) and [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/): lightweight public-page fetching and extraction used here.
- [Playwright](https://github.com/microsoft/playwright): JavaScript-rendered crawling, visible DOM/open shadow-root extraction and desktop/mobile screenshots.
- [Reacher](https://github.com/reacherhq/check-if-email-exists/tree/681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67): verification backend at the inspected MIT commit.
- [Crawl4AI](https://github.com/unclecode/crawl4ai): evaluated. The implemented crawler uses Playwright directly to share checked network access, contact provenance and durable job state with this application. This choice is independent of the 4 GB host constraint; its separate server is not a required dependency.

## VPS browser search and business profiles

The opt-in [VPS browser setup](docs/PLATFORM_BROWSER.md) uses a dedicated persistent Chromium session for normal LinkedIn company searches/About pages and X profile searches/bios. It connects directly to existing discovery/research jobs, with no desktop extension, file handoff or LinkedIn/X developer API key. One-time normal sign-in is required where the site requires it. Public business emails remain sourced review candidates; no contact is automatically verified or sent.

Search extraction is limited to rendered result cards. Profile extraction excludes timelines, account navigation and member/private routes. Login/challenge and HTTP access-denial holds stop queued attempts on that platform. Missing fields or unsupported layouts remain unavailable. This implements a server browser transport; actual authenticated VPS access, Linux image startup and sustained lead recall still need deployment acceptance. Restrictions disappearing and Apollo/Apify parity are not established.

Public-source failover is enabled by default: free SearXNG discovery and current independent company pages can continue research when a managed profile is blocked or has no website field. Find prospects shows recorded platform coverage and independently recovered website candidates. Contact recovery prioritizes sourced routes, respects origin/URL cooldowns and reconciles recovered pages with the saved crawl checkpoint. [The implementation and two-business live diagnostic](docs/SOURCE_FAILOVER.md) preserve the original platform failures; they do not claim access was bypassed.

## Browser and optional n8n

If Chromium has not already been installed by the startup script:

```sh
python -m playwright install chromium
```

`BROWSER_ENABLED=true` and Docker `INSTALL_BROWSER=true` are defaults. Browser lanes are configurable; one company cannot be researched and screenshotted concurrently. Mailbox monitoring/sending remains independent of slow research. Setting browser support off is an explicit HTTP-only override and does not count as a complete rendered audit.

The **PageSpeed audit** button queues on-demand mobile/desktop Lighthouse lab measurements from Google's API. Set `PAGESPEED_API_KEY` locally if required by your quota. Inspect the latest report in the company detail or Operations. Partial results and HTTP/quota errors are saved; no score is invented. This does not provide visitor analytics or establish conversion loss. A keyless practice-site check returned HTTP 429 for both strategies; real successful provider measurement is still pending. Automatic screenshots remain independent of this optional service.

See [the requirements re-audit](docs/AUDIT.md) for the full mapping of earlier chats/notes to the current implementation, fixes and deferred work.

See [the live research/draft acceptance notes](docs/BENCHMARK.md) for the ongoing 50-candidate sample, source/copy previews, crawler corrections and remaining operator/deployment checks. Those historical preview messages use offline templates and are not evidence for the current AI writer or model quality. They create no contacts, call no providers and enable no sending.

For n8n: start the `n8n` profile, access its loopback port through a secured HTTPS proxy, set up its owner account, and import `deploy/n8n-discovery.json`. Add a **Header Auth** credential with name `Authorization` and value `Bearer YOUR_API_TOKEN`, select it on the HTTP node, replace the example query, test and then activate. The workflow is inactive on import and contains no secrets. Use either app recurring searches or n8n for the same query, not both. Runtime import was not tested without n8n/Docker.

## Backup and restore

```sh
python scripts/backup.py --output backups
# Docker: creates the backup inside the data volume, then copy it off the host.
docker compose exec app python scripts/backup.py --output /data/backups
```

Copy backups and relevant screenshot files to private off-host storage. Preserve `.env` and `<DATA_DIR>/workspace-settings.json` separately in private encrypted backups. The settings file contains managed login/mailbox/AI-writer overrides and is not inside the SQLite backup or source ZIP. To restore, stop the app, keep a recoverable copy of the old data directory, restore the consistent backup as `outreach.db` into a clean data directory, restore screenshots and configuration, then start **paused**. Do not mix a restored database with unrelated old WAL/SHM files. Reconcile any uncertain sends and inspect provider history before resuming. SQLite backups here do not include screenshot files or n8n's separate volume.

## Tests and readiness

Latest local verification: **795 tests passed**, including 32 professional-source cases, 24 VPS-browser cases and 19 source-failover/recovery/coverage cases; Ruff and Chromium UI checks passed. The browser-mode checks use fictional intercepted pages, not an authenticated VPS deployment. See [the verification record](docs/PLATFORM_BROWSER.md).

```sh
pip install -e '.[test]'
pytest -q
ruff check outreach tests scripts
python scripts/preflight.py
# Optional connectivity only; no emails are sent:
python scripts/preflight.py --network
```

The preflight prints missing configuration, not secrets. With `--network`, Reacher readiness checks invalid-syntax handling and header authentication using only a malformed non-recipient address; root HTTP 200 alone cannot pass. It does not probe a real mailbox. Container URLs are reachable only on the container network; run it there for deployed connectivity checks. `/health` checks HTTP liveness only; `/api/status` reports worker heartbeat/inbox state and sending gaps.

Important API routes are listed by authenticated `GET /api/openapi`. API clients use Bearer or Basic authentication; browser access uses the sign-in form and signed cookie over HTTPS plus same-origin write checks. A single-admin credential model is intentional; this is not a multi-tenant deployment.

## Businesses without a known website

The separate [public professional-contact workflow](docs/PROFESSIONAL_CONTACTS.md) supports LinkedIn `/in/` and X public bios for an existing website prospect. It reuses observed company-page profile links, adds bounded free discovery and requires current employer/role/inbox review before contact import. Captures create no probes or contacts; reviewed imports remain technically unverified. This is not hidden-email discovery or proprietary database enrichment.

Use Find prospects â†’ Add a business without a known website, or let automatic discovery retain unresolved business profiles. Profile evidence, website-search uncertainty and published inbox ownership are reviewed before verification/drafts. Website absence is never inferred solely from missing results. See [the profile prospect workflow](docs/PROFILE_PROSPECTS.md).

## Step-by-step prospect research

The Workflow page opens the Find & research view (17 relevant nodes, seven guided steps). It separates saved candidates/captures, exact source quotes, proposed opportunities and missing business/buyer/country evidence. Overview has 11 grouped stages; Full workflow has 35 nodes. Expand Saved prospects for coverage and Recent search runs for engine failures. See [the live first-workflow audit](docs/FIRST_WORKFLOW_AUDIT.md). No preview changes outreach eligibility.

Public discovery now has bounded search-engine fallback, Common Crawl URL hints, source constraints and current company-profile navigation refresh. See [multi-source coverage and live limitations](docs/MULTISOURCE_DISCOVERY.md); personal-profile email extraction and vendor parity remain unverified.
