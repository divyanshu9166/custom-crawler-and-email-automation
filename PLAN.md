# Outreach automation implementation plan

## Scope
US/UK cold email acquisition for (A) website development/improvement and inquiry/booking chatbots, and (B) new/existing D2C stores, shopping/support chatbots and permission-based WhatsApp workflows. One relevant offer per prospect. Research public evidence; do not invent conversion losses or private metrics.

## Architecture with quality independent of host size
- Python/FastAPI service, authenticated review dashboard, one durable worker controller with independent mailbox/provider/browser lanes.
- SQLite WAL on a persistent local volume: small single-host deployment, no full Supabase stack. Backups through SQLite's backup API. One application process only.
- SearXNG optional free search service; SerpApi optional paid replacement; CSV/manual public URL imports always available.
- HTTPX + Beautiful Soup + Playwright Chromium website extraction; robots and sitemap discovery, configurable deeper crawling, public CDN resources, lazy-loaded content and open shadow roots, contact-source timestamps, structured identities and published obfuscated emails. Desktop/mobile screenshots and explicit partial-coverage reports.
- Reacher self-hosted HTTP integration, conservative result classification and verification expiry. Port 25/IP reputation remain deployment dependencies; no claim that SMTP checks prove mailbox existence.
- Optional AI research suggestions; operational emails require research-based AI writing from current reviewed evidence, with no template fallback. Missing writer configuration or failed validation holds drafting. All initial sequences require review.
- SMTP sending and IMAP reply monitoring through the user's mailbox: no required Smartlead subscription. Durable message IDs, uncertain-send quarantine, opt-outs and global suppression.
- Optional n8n workflow triggers discovery via API; the application alone owns outbound scheduling. Hermes is not required.
- Shared manual outreach ledger and company holds; operator-confirmed client qualification/call/proposal/agreement/payment/delivery stages, dated tasks and campaign reports.
- Source-backed value artifacts: focused audits with optional screenshot callouts, homepage concepts, interactive approved-excerpt FAQ prototypes and qualified WhatsApp-flow outlines; review/export and actual-delivery recording.

## Implementation sequence
1. Settings, schema, auth, migrations, durable jobs and audit log.
2. Search/import, safe website fetch, evidence/contact extraction, Reacher adapter.
3. Service routing, optional AI suggestions, draft/sequence review gates.
4. Send windows, quotas, verification expiry, SMTP and IMAP, suppression and crash recovery.
5. Dashboard, API, Docker Compose, Reacher source pin, optional n8n/SearXNG, setup/backup/preflight tooling.
6. Tests: realistic mocked provider contracts and complete local lifecycle; no unsolicited live mail.
7. Shared channel history, company holds, response-fulfillment tasks and operator-confirmed client lifecycle.
8. Reviewed audit/concept/FAQ/WhatsApp-flow exports, scoped proposals and campaign/task reporting.
9. Representative research benchmark, initial 20 draft reviews and actual deployment/provider acceptance.

## Quality rules
- Discovery country is a hint; country, business fit, identity and contact relevance require evidence/review.
- Country qualification includes a saved official-page location quote. Campaign B rejects Campaign A website offers through the API as well as the dashboard; WhatsApp offers record channel-fit unknowns.
- Optional announcement and extra follow-up sources are preserved in reviewed findings and draft evidence IDs. Each touch adds context; no finished asset or case study is fabricated.
- Unknown/catch-all/invalid/disposable results cannot be approved for sending.
- No contact = research remains useful but lead is held; never generate guessed addresses.
- Evidence text and instructions found on external pages are untrusted data.
- LinkedIn/X/PeoplePerHour and configured business directories participate in automatic indexed-signal research. Single HTTP public snapshots require robots permission; official-site resolution preserves ambiguous matches for review. Optional VPS-owned browser sessions read scoped visible company/professional fields; private contact overlays, platform messaging, challenge bypass and copied desktop sessions remain excluded. Session access does not establish platform permission or outreach eligibility. Authenticated VPS behavior remains unverified.
- Public email and technical validity are distinct from outreach eligibility. Review records the US/UK basis and appropriate business type.
- Sending off by default until real sender, mailbox, address, authenticated domain and reply monitoring are configured.

## Acceptance and deployment boundary
Local automated tests, a seeded demonstration and configuration checks must pass. Live Reacher SMTP accuracy, mailbox integration, Docker resource use and VPS deployment require the user's actual infrastructure. Missing credentials are explicit holds, never simulated successes.

## VPS upload and acceptance tasks — 13 October 2026

All boxes below are **pending on the user's VPS**. Local implementation checks do
not complete them. Detailed commands, evidence and rollback steps are in
[the deployment checklist](docs/VPS_DEPLOYMENT_CHECKLIST.md).

- [ ] Record VPS OS/CPU/RAM/disk, install Docker Engine/Compose and verify Linux user namespaces/sandbox support. Use one app process; reserve measured capacity for Chromium.
- [ ] Upload the reviewed source release and verify its checksum. Create private server-local `.env`; transfer existing operational data/settings only if intentionally continuing them.
- [ ] Set production HTTPS `PUBLIC_URL`, dashboard credentials and API/provider secrets. Inspect managed workspace overrides; retain `SENDING_ENABLED=false` and the global send pause.
- [ ] Configure DNS and reverse-proxy TLS; verify HTTPS sign-in/settings, same-origin writes and correct public links. Keep app/provider/VNC ports off public exposure.
- [ ] Validate Compose, build the normal and optional browser images, and start app + SearXNG + Reacher. Confirm non-root volume permissions, Chromium sandbox/display and one worker heartbeat.
- [ ] Run deployed preflight/provider contracts. Verify SearXNG JSON results and the actual Reacher endpoint/auth; check provider-permitted TCP/25 without treating connectivity as mailbox validity.
- [ ] If LinkedIn session research is selected, stop app, use the SSH-tunnel setup UI for legitimate own-account login, close setup gracefully and restart with the browser overlay. Default setup opens LinkedIn only; X login is optional.
- [ ] After actual access recovery, clear only the relevant durable hold. Verify session persistence across restart, fresh company/professional field captures and blocked/challenge handling. Do not count a profile directory or successful login as a working lead extractor.
- [ ] Verify checkpoint/authwall redirects that time out stop the platform with a durable login hold; verify browser/profile-lock startup errors remain visible as source failures. Test both company search and professional roots after a cold restart, keeping sending paused.
- [ ] Run a bounded, recorded US/UK Campaign A/B sample across website, profile-first and X sources. Inspect identities, current country/role evidence, official links, sourced emails, partial coverage and deduplication; retain unsupported contacts on hold.
- [ ] Configure the AI email writer and review factual personalization, one offer and all four touches against current source evidence. Test failed/missing writer configuration without template fallback.
- [ ] When supplied, configure SMTP/IMAP and sender DNS/authentication. Use the user's controlled test mailbox for separate authorized delivery/reply/opt-out acceptance; no prospect mail during sourcing acceptance.
- [ ] Benchmark resource consumption/restart recovery and durable jobs/holds. Lower concurrency or increase capacity based on measurement; do not remove crawler capabilities solely for 4 GB RAM.
- [ ] Create encrypted off-host backups of consistent DB, evidence/screenshots, managed settings, `.env` and stopped browser state; rehearse paused restore and inspect uncertain sends before any future resume.
- [ ] Sign off source/provider/UI/runtime acceptance with retained evidence and unresolved gaps. Live sending remains disabled until a separately authorized controlled test/pilot and the mailbox gates pass.

Current session-method re-audit corrects setup navigation failure handling,
Windows lock cleanup, scoped reader exclusions, navigation boundaries and browser
image/preflight packaging. It does not establish successful authenticated VPS
discovery or unrestricted LinkedIn email coverage.

The 14 October handover additionally verifies durable login holds on timed-out
authentication redirects, explicit browser-startup errors and consistent
LinkedIn-only setup defaults. Staff parsing crashes/role-substring false positives
were corrected. The complete local suite passes 1061 tests; the server login,
Docker runtime and fresh account-specific lead coverage remain pending. Details
are in [the session re-audit](docs/PLATFORM_SESSION_REAUDIT.md).

The next bounded crawler optimization preserves explicitly published HTTP contact/
team navigation that JavaScript removes, even on an email-free homepage. Existing
fetch/source gates remain in force. Controlled before/after evidence and the scope
are in [the contact-navigation audit](docs/CONTACT_NAVIGATION_RECOVERY.md).

The two agreed pre-VPS platform updates now add bounded multi-snapshot scroll/Next
search with visible coverage reporting, and private restart-safe FxEmbed cache/
cooldown/pacing with original timestamps. Browser reuse is deferred to measured
VPS performance. See [the platform update audit](docs/PRE_VPS_PLATFORM_UPDATES.md).

Official-source snapshot recovery now follows the configured render policy and
preserves independent HTTP/rendered staff evidence, without joining identities
and emails across versions. The live regression and remaining zero-result fresh
buyer sample are recorded in [the rendering recovery audit](docs/OFFICIAL_PROFILE_RENDER_RECOVERY.md).

The subsequent fixed architecture sample and same-row replay remain unqualified
with zero accepted personal emails. Recovery now reserves initial leaf budget
for each identity query and preserves bounded employer headline hints. Actual
engine availability, source ambiguity and the original sample are retained in
[the homonym-recovery audit](docs/HOMONYM_SOURCE_RECOVERY.md).

The normal website/contact-recovery pipelines now retain additional current
HTTP publication alongside rendered evidence, with independent person scopes
and a digest covering both documents. Actual known-page research recovered
published address records and automatic named-profile research; this is not
fresh buyer or native-platform coverage. See [the core pipeline audit](docs/CORE_PUBLICATION_RECOVERY.md).

The initial five-page HTTP-only default was superseded by the user's quality-first instruction. Browser rendering is enabled by default, with 30 pages per company (configurable up to 500). A 4 GB host lowers concurrency, not functionality. Increase infrastructure capacity when representative benchmarks require it.

The 10 October re-audit is documented in `docs/AUDIT.md`. On-demand PageSpeed API jobs cover the earlier performance-audit step; successful live measurements remain dependent on provider quota/key. Mail scheduling scans due contacts in bounded pages so older out-of-window records do not hide eligible timezones. Transactional review/approval/generation guards and terminal reply/opt-out precedence cover concurrent requests and recovery.

The goal continuation implements the earlier shared-history and post-reply workflows as a reviewed workflow manager. External actions remain human-confirmed. Batch research benchmarking supports isolated parallel companies, preserved partial evidence and an independent review sheet. The original 50-candidate attempt run finished with 29 partial and 21 failed reports; the 21-company retry was interrupted at the user's requested pause after 13 completed attempts (9 partial / 4 failed). The resumed nine-attempt run finished with 212 captured/rendered pages and partial reports. Yafa Queen recovered in a subsequent 30-page rendering attempt after DNS became available. Goldstein rendered 25/25 captures before its 1800-second deadline; the separate extended attempt finished with 30 unique/rendered captures in 2098.21 seconds and no job error, using a 3600-second deadline without overriding robots pacing. Its resource coverage remains partial. Twenty distinct real company draft sequences / 80 messages have source/copy review, with five companies in each campaign/country group; independent operator/buyer/recipient approval and the live 20-prospect pilot remain unfinished. `docs/BENCHMARK.md` records sample limits, corrections and the original run's implementation boundary.

After the temporary pause, confirmed browser-context closure gates cleanup-error recovery. Historical source rows are preserved, but new suggestions and qualification require pages refreshed in the latest research attempt; review commits recheck those sources. Research start is atomic against approval. Other-domain recipient verification rechecks ownership and suppression after its pacing wait. These controls are included in the 181-test local suite and current Chromium dashboard check; they do not replace deployment/provider acceptance.

Latest completed reports for the original 50 candidate domains are 46 partial / 4 failed, retaining earlier/current code lineage. Source notes cover 46 companies with 43 geographic source supports and 3 holds; buyer, eligibility, ownership and recipient approvals remain independent. Successful full-depth rendering does not imply complete resource coverage, current-version acceptance of all earlier reports, or live deployment/provider acceptance.

## Profile-first development prospects

The latest README/original-workflow comparison is in `docs/README_WORKFLOW_CHECK.md`: 249 tests passed in 83.26 seconds and full Chromium checks passed. Free current-source service proposals now cover explicit inquiry/shopping/support/launch/WhatsApp cues, with review rather than invented pain. Learning now reports approval-frozen campaign/service/country/industry groups, accepted/human-reply/qualification/recorded-win rates and review guidance. Preflight loads managed Settings; source setup and deployment acceptance remain distinct.

Businesses without a known website now have a distinct research/contact-review branch. Automatic discovery and direct profile imports record website-search scope, current public profile evidence and held published-email candidates. A website match routes to the normal crawler. Otherwise current business identity/activity, country, inquiry/order observation and search limits must be reviewed before a website/store-launch pitch. Indexed-only and inaccessible evidence cannot create a verified recipient. See `docs/PROFILE_PROSPECTS.md` and its dated check.

## Agent Reach comparison improvements — 17 October 2026

Implemented in the existing VPS browser/pipeline: company/buyer keyword people search,
visible personal Experience, optional account-visible Contact Info, author-matched LinkedIn
company and X posts, X latest-post author-search fallback, semantic search-card alternatives,
saved source/operation timing and contact diagnostics, dashboard research controls and
post evidence in the reviewed announcement-to-AI-writing path. Existing source, country,
ownership, verifier, approval and sending gates remain separate. Settings and captures use
the existing local VPS volume. See `docs/SOCIAL_RESEARCH_UPGRADE.md` for controls, data scope
and exact two-file Compose deployment commands.

The previously supplied VPS output proved the installed company About reader on one page.
The additional paths in this upgrade require fresh VPS/session acceptance after deployment;
local browser fixtures do not establish platform-wide availability or greater real email yield.
