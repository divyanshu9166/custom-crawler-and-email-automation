## Nested hidden HTML and deterministic crawl failures — 21 October 2026

Reproduced AttributeError against the current Dazzle homepage and Total Clean
company-values page: decomposing a hidden parent invalidated styled descendants
still in the selector snapshot. Guarded removed elements in staff, professional
profile and public-post extractors. Both live HTTP captures now extract successfully.
Added nested-hidden-content regressions that retain visible content and exclude
hidden identities/contact data. Deterministic parser/programming errors now stop
with a failed job instead of consuming automatic crawl continuation/retry rounds.

158 people/post/discovery/crawl tests and 48 worker/continuation/platform-discovery
tests passed; Ruff passed. The separate queued-to-running email UI checks passed
on desktop and mobile (2 cases). Live preparation for lead 18 finished with a
needs_evidence result and no draft; this is not a provider-success or pitch-quality claim.

## Independent email preparation worker — 21 October 2026

Added one serial preparation lane separate from long browser research. Existing
transactional per-prospect exclusion, research freshness checks, draft preservation,
cancellation, and sending controls are retained. UI distinguishes pending requests
from running preparation and updates the label through polling.

129 focused worker/preparation/journey/UI/runtime tests passed. The new concurrency
regression holds research open and verifies an unrelated preparation starts with
one configured crawl worker. Same-prospect claim exclusion is also tested. Provider
responses in tests are controlled; this does not guarantee live provider latency.

## Prospect research status and screenshot readiness — 21 October 2026

Pipeline now shows actual queued/running source jobs, saved page/contact counts and separate screenshot availability. Selected-prospect polling preserves open forms and draft edits; completed research refreshes a clean workspace. Active journey/email preparation remains visible alongside screenshot jobs. Labels no longer infer active research from a stale lead status. The authenticated read-only activity endpoint exposes safe existing screenshot files, distinguishes partial/stale captures, and does not run providers or change settings. Schema 8 is retained with a compatible lead-job lookup index.

The full regression run recorded 1667 passing cases and two journey-preparation visibility failures. After fixing the conflict, all 77 focused journey, activity, browser and priority cases passed, including both previously failing cases. Full browser smoke passed with zero JavaScript errors. Ruff and JavaScript syntax checks passed. This validates controlled UI/state behavior, not guaranteed completeness of external website research.

# Visible action feedback and background activity — 21 October 2026

Added shared viewport notifications, accessible button loading states, guarded repeated
submissions and an Activity panel for the latest 20 jobs started from the current tab.
Queue acceptance, actual execution, completion, recorded failure and unavailable status
are distinct. Job status survives tab refresh without storing credentials or payloads.
Search progress is attributed to the actual worker job ID. The authenticated read-only
status endpoint uses a compatible event index; schema version remains 8.

The complete suite passed **1,660 tests in 660.52 seconds** with the existing
Starlette/httpx deprecation warning. The 24 final focused checks include desktop/mobile
feedback, repeat-click protection, offline/unknown acceptance, imports, secret-safe
validation and runtime controls. Ruff, JavaScript syntax and all 35 workflow mappings
passed. The full Chromium application smoke passed with zero JavaScript errors.
Its concurrent status mock now drains before cleanup, and its map drag scrolls the
node into the viewport. The runtime-switch test isolates adaptive admission from live
host CPU; resource pressure retains separate controlled coverage. No real messages
or provider jobs were submitted by these tests.

# Google Business Profile intake in Campaign 3 — 21 October 2026

Campaign 3 now has its own Find prospects form, named A-goal campaign, public Maps
search/listing reader, independent website resolution, bounded batch filtering and
recurring-source persistence. Matched websites are excluded. Captured candidates with
incomplete/ambiguous lookups remain held; website absence is never asserted from a
missing button or search result. Public phone/category/address are visible in the
prospect workspace. Phone-only records cannot generate guessed email addresses.

Controlled checks cover current scoped fields and source hashes, review/hidden-email
exclusion, nested hidden HTML, duplicate listing aliases, closed/blocked sources,
known-site exclusion on refresh, positive published-business-email preparation,
Campaign A launch selection without overriding Campaign B, schema 7→8 preservation,
recurring execution and desktop/mobile form/API behavior. The final complete suite
passed **1,642 tests in 615.45 seconds**; Ruff, JavaScript syntax, all 35 workflow-node
mappings and the full Chromium application smoke passed with zero JavaScript errors.
The existing Starlette/httpx deprecation warning remains. The first wider run exposed
an index-based provider assertion after adding Google and a screenshot during initial
page updates; provider-name checks and waiting for completed requests passed the final run.

Native isolated VPS checks captured two public Maps searches and four current listings.
Three listings exposed a website link; another exposed a public phone without an observed
Website field. Its independent lookup was incomplete, so it does not establish website
absence. No published email appeared in these native samples. Controlled tests establish
the hold/preparation behavior; these native checks do not establish email-ready yield,
provider-wide access, delivery or conversion performance. No sample lead was inserted into
the production database and no email, mailbox probe or call was made.

A fresh private schema-7 SQLite backup was taken before rollout. Schema 8 adds only the
recurring discovery-source field. Deployment checks compare existing records and the
Spotless draft digest, database integrity, named Campaign 3 availability and collect-first
flags: research ON, automatic preparation OFF, sending/follow-ups OFF.

# Profile-first bulk preparation — 21 October 2026

The previous mandatory profile-only hold is replaced by current first-party business,
activity, country, completed website-lookup and published-business-inbox checks. Profile-first
search and recurring mode preserve named campaigns. The supported path no longer asks the
operator to copy qualification/ownership notes for every prospect. Final recipient/message
approval remains separate; unsupported source evidence stays held.

Executed focused checks cover automatic Campaign A/B qualification, source/identity hashes,
blocked/ambiguous/stale captures, suppressed/shared contacts, employee exclusion, cancellation,
source/configuration races, one unscheduled draft, history preservation, automatic/bulk
scheduling, recurring worker payloads, schema 6→7 preservation and real writer validation.
Chromium desktop/mobile checks submit a profile-first batch and recurring search using the
actual application/API; the legacy full browser smoke also passed with zero JavaScript errors.
The wider run exposed company-reader/reference/employee-link assumptions affected by allowing
self-selling personal candidates; those company-specific boundaries were restored and their
focused regressions passed. **Final complete suite: 1,601 passed in 597.30 seconds**, with the existing Starlette/httpx
warning. Ruff, JavaScript syntax and diff checks passed. All 35 workflow nodes were mapped
to executed passing checks, including the new automatic profile qualification/contact paths.

Candidate modules were executed in an isolated process on the VPS with synthetic first-party
captures/search reports and the saved live Nemotron configuration. A Campaign A website-launch
sample and Campaign B store-launch sample each reached `drafts_ready`, with one `draft`,
no due/sent timestamp and zero send attempts. The actual leads/contacts/messages digest was
unchanged. The launch writer retains bounded-search uncertainty; no matched website is not
proof of absence. The ordinary profile-based calling proposal also passed a controlled live
writer sample. These are live model/application rehearsals with fictional sources, not evidence
of native LinkedIn/X acquisition yield, real mailbox deliverability or conversion performance.

The VPS has automatic preparation OFF for collect-first use, research ON, sending and follow-ups
OFF. Deployment preserves those choices and the existing Spotless draft. Schema 7 adds only a
recurring-search focus flag; a fresh private SQLite backup was taken before rollout.

# Final audit-reference feedback check — 19 October 2026

A live response cited an unavailable audit observation and was rejected after its bounded
correction; no copy was saved. The correction feedback now supplies the exact allowed audit
reference list and explicitly requires [] when no valid observation exists. The final focused
writer/preparation/diagnostics/Chromium suite passed **134 tests in 41.67 seconds** with the
existing Starlette/httpx warning. Ruff and diff checks passed.

The exact candidate writer module was then executed in an isolated Python process in the VPS
app container against the existing settings and public research. Nemotron returned one valid
email on its first request in **4.61 seconds**. Reading that output found a proposed usability
experiment and sourced public business context; it did not assert a measured website defect,
London trial offer or lost conversions. The existing database copy was asserted unchanged;
no additional draft, approval or recipient message was saved. This is one live sample, not
proof of reliable identification of an actual business pain point.

The source-first VPS retest returned one message in 1.97 seconds without the earlier London
trial assertion. It still used an internal “reviewed finding” phrase; that exploratory copy
was not saved. Automatic output now rejects internal research labels and gives the model its
existing single bounded correction opportunity. The final focused suite passed **133 tests
in 41.06 seconds**, including the label rejection and summary exclusion regressions. The app
and public health endpoint passed; the saved single draft stayed unchanged, with zero scheduled
or sent messages. Sending remained OFF. The fresh capture was partial with 11 render issues;
PageSpeed remained failed/quota limited, so zero technical issues were asserted.

# Source-first writer correction after live audit review — 19 October 2026

The deployed audit-context path returned valid single-email JSON from Nemotron, but manual
review found the output repeated an unsupported London trial claim from an older qualification
summary. That exploratory output was **not saved**. The original edited initial email remained
unchanged. This distinguishes a provider/JSON success from factual-copy acceptance.

The writer packet now excludes free-form observation, business-fit/research notes and trigger
narratives. It supplies actual public-page text, exact selected quotes, the selected service,
a clearly labelled proposed next step and typed audit data. Proposed testing must investigate
whether an issue exists, not presume where an established problem occurs. A regression fixture
injects fabricated trial, loss, chatbot and announcement summaries and asserts none reaches
the packet. The final writer/preparation/diagnostics/Chromium workspace suite passed
**132 tests in 40.37 seconds**, with the existing Starlette/httpx warning; Ruff passed. This reduces the demonstrated summary-laundering path; it is not a guarantee that
a model cannot hallucinate from other inputs. Final factual review remains required.

# Audit inputs and honest problem evidence — 19 October 2026

The live inspection found PageSpeed HTTP 429 with no successful score, partial screenshot
renders, zero saved social posts and an unknown mailbox verifier result. The existing Spotless
email proposes an experiment; these records do not verify an actual client pain point.
See [the research-to-email audit](docs/PAIN_POINT_AUDIT.md) for exact coverage and limits.

The broad local regression run passed **1,323 tests in 472.85 seconds**, with one existing
Starlette/httpx deprecation warning. The latest writer/API/Chromium workspace run passed
**75 tests in 30.61 seconds**, including the subsequent score-unit and stale-audit error
feedback checks. The dedicated audit-context file separately passed **25 tests in 7.17
seconds**. These counts overlap; they are not additive. Ruff, JavaScript syntax and diff
checks passed. Desktop/mobile Chromium screenshots were inspected for the added audit basis.

Coverage includes waiting for audit jobs, configured-key automatic PageSpeed scheduling
and deduplication, partial/unscoped/stale/older-crawl rejection, no borrowing scores from an
older success after a newer failure, real assessment/writer payload contracts with mock
transport, mandatory scoped numeric/reference qualification, incorrect-unit rejection,
audit changes during generation preserving old copy, and changed-audit approval rejection.
Public HTML quotes and lab/render observations remain separate inputs and provenance.

These checks prove code/data-flow behavior. They do not grant provider quota, establish
semantic entailment, perform a complete interactive quote/chatbot journey or prove lost
sales. No real email or recipient verification probe was sent during these checks.

# Focused workspace and one initial email — 18 October 2026

The complete local suite passed **1,300 tests in 447.85 seconds**, with one existing
Starlette/httpx deprecation warning. The focused browser and single-email acceptance
suite passed **40 tests in 58.41 seconds**. Ruff and JavaScript syntax checks passed.
Chromium exercised both 1440px desktop and 390px mobile layouts using isolated fictional
records: one editor, collapsed advanced tools, source expansion, draft edits, archived
follow-ups, readable navigation and no horizontal overflow or JavaScript errors. The standalone
legacy advanced-tool browser smoke also passed with zero JavaScript errors,
including source history, settings, sign-in, sales records and workflow-map interactions. These
are local UI checks, not a claim of testing the authenticated VPS browser interactively.

New workspace defaults request exactly one source-supported initial email. Tests cover
the provider contract and final-output budget, approval snapshots, SMTP-stub acceptance
without scheduling a follow-up, disabled legacy follow-up dispatch, expired verifier
status, and transactional archiving that retains the edited initial message and complete
follow-up history. Approved, scheduled, submitted and uncertain history cannot be reset
through the archive action. Historical four-touch fixtures explicitly enable the legacy
flag; the new production default and sending behavior have separate tests.

The interface makes a saved initial draft visible even if an older preparation job failed.
It does not mark that failed job successful, relax source validation or guarantee semantic
accuracy. The operator still reviews the proposed approach and final email. Nothing in
these local checks enabled sending or contacted a real recipient.

## VPS deployment verification

Application commit `83ff746` was pushed and deployed with both production/browser Compose
files. The app returned healthy; authenticated root and new workspace JavaScript returned
HTTP 200. Loaded writer configuration reports one message, Nemotron selected and automatic
follow-ups disabled. Sending remained OFF before and after deployment. n8n and its PostgreSQL
container retained their existing uptime; only the outreach app was recreated.

After confirming the private SQLite backup existed, the normal archive endpoint retained
Spotless's initial message with its exact ID, subject and edited body unchanged. Three unsent
follow-ups were preserved in the archive audit event. AI-origin validation passed for the
retained message. Database checks found one remaining draft, zero scheduled messages and
zero sent messages.

An additional in-memory live Nemotron request using the prospect's current reviewed sources
passed single-email and exact source-support validation in **10.18 seconds** with prompt
`research-email-v4-single`. It did not save a second draft, replace edited copy, approve
outreach or send mail. This proves the deployed single-output provider path; structural
validation does not prove every semantic claim or client requirement.

# Live VPS provider diagnosis and preparation source selection — 18 October 2026

Direct SSH inspection confirmed the managed writer key was present and loaded, with
sending disabled. NVIDIA model-catalog access returned HTTP 200 in about 0.2 seconds;
the selected DeepSeek model was listed, but both bounded synthetic normal and streaming
chat requests timed out after 60 seconds. A synthetic Nemotron comparison returned complete
final text in about 0.5 seconds with the same key. After the operator authorized the switch,
the application writer-settings endpoint saved Nemotron and its connection-test endpoint
passed. This isolates the observed DeepSeek inference failure, not its internal provider cause.

The first real preparation attempt then exposed a separate page-selection problem: current
official evidence contained the incorporated business name outside the twelve-page shortlist.
Selection now retains such a source without increasing the budget or weakening validation.
Unsupported AI quotes and feature-absence claims remain rejected. Assessment gets at most
one correction request before any qualification write; network failures are not retried.

The focused preparation, writer, feedback and Chromium preparation-UI suite passed
**113 tests in 39.20 seconds**, with one existing Starlette/httpx warning, including the
subsequent writer correction, preservation, question and invented-checklist tests. Ruff and diff
checks passed. This is focused validation, not a new full-suite or live delivery verdict.

Live assessment remained variable: a later attempt still failed its exact opportunity quote.
Separately, the writer endpoint generated four saved drafts from the preceding successfully
validated qualification. Reading those drafts exposed unsupported form-checklist claims and
missing questions. Writer prompt v3 now explicitly rejects those assumptions; local checks
require questions in touches 0-2 and reject the observed unsupported checklist assertion.
These checks are deliberately narrow, not a general semantic entailment guarantee.

The deployed v3 writer endpoint subsequently returned HTTP 200 and saved all four drafts.
Assistant review still found residual unsupported compliance/local-offer assumptions and
removed them through the normal message-edit endpoints, with a `draft_copy_review` event.
Final database inspection: four `draft` messages, zero scheduled messages, zero sent messages,
and sending disabled. The revised copy proposes reviewing the existing quote journey without
asserting missing tools, specific form mechanics, lost conversions or completed work.
This proves the deployed writer/storage/edit path for this prospect. It does not establish
unattended qualification reliability: the latest automatic assessment job remained failed
on its exact opportunity quote. Existing valid qualification was used for the separate writer
test; no failed job was marked successful or sending/recipient approval bypassed.

# AI connection-test feedback and diagnostic verdicts — 18 October 2026

The focused writer, preparation, real Chromium desktop/mobile, settings and runtime suite
passed **109 tests in 44.74 seconds**, with one existing Starlette/httpx warning. The final
unsaved-edit guard and deterministic countdown/timeout fixtures passed **17 feedback tests
in 9.55 seconds**. Ruff and JavaScript syntax/diff checks passed. This is focused validation;
the preceding 1251-test full-suite result below predates this diagnostic refinement.

The screenshot showed a disabled test button and a saved-key indicator, not an actual
provider response. Inspection found an unchanged waiting-button label, an off-screen result
area and no browser-wide deadline. Tests cover immediate visible progress, an elapsed
counter, success/error/timeout recovery, no duplicate request, late-response preservation,
saved-key roundtrip without exposure, private verdict persistence/invalidation and stale-test
rejection after writer configuration changes. HTTP 200 truncated/empty-final responses now
report connection acceptance separately from generation readiness. Read timeout, 401, 404
and 429 remain distinct failures. Provider text, reasoning and untrusted finish reasons
cannot echo secrets. A running preparation labels its prior error as Previous attempt.

No live NVIDIA key/request or VPS state was inspected. The selected DeepSeek model is
documented by NVIDIA, but account access, latency and actual drafting remain unverified.
See [the feedback behavior and deployment commands](docs/AUTO_PREPARATION.md).

# Automatic preparation and AI connection diagnostics — 18 October 2026

Full suite: **1251 passed in 377.03 seconds**, with one existing Starlette/httpx
deprecation warning. After the final U.S. country-punctuation correction and bulk-result
panel change, **41 preparation/core/UI cases passed in 25.92 seconds**, including the added
research-completion scheduling regression and two explicit US location/timezone cases.
The broader focused writer/settings/social/runtime UI run passed **97 cases in 46.89 seconds**
before those final adjustments. Ruff, JavaScript syntax checks and diff checks passed.
The standalone Chromium smoke check passed after its expected advanced-editor label and
node execution-mode assertions were updated. It reported zero JavaScript errors and verified
desktop/mobile layout, source/approval holds, settings/auth, workflow map and existing sales
flows. All data/providers were fictional and no real recipient probe or outreach occurred.

Website prospects can now prepare exact country evidence, source-backed business/offer
context and four unsent AI drafts via one action or after source research finishes. Bulk
pages queue up to 100 prospects, expose per-prospect exceptions and advance using a cursor.
Preparation serializes with the same lead's research, preserves existing messages and
concurrent edits, and discards changed source/contact/configuration or cancelled work.
Automatic qualification is labelled `research_ai`; it is not human approval or confirmed
buyer authority. Unknown/profile-only/unsupported cases remain explicit exceptions.

NVIDIA base/root/full chat endpoint forms are normalized without duplicate suffixes. The
dashboard offers a selected-model preset and a synthetic chat connection test. Provider
HTTP 404/401/429 remains a distinct configuration/access/quota issue, with no template or
alternate-model fallback and no provider-body/key echo. No live NVIDIA key or account access
was tested here; current VPS build and successful provider/model writing remain deployment
acceptance checks. Reacher/source restrictions and final recipient/eligibility/message review
are unchanged independent requirements. See [features and deployment steps](docs/AUTO_PREPARATION.md).

# VPS discovery quota and company-link fixes — 18 October 2026

The full suite passed **1213 tests in 365.84 seconds**, with one existing
Starlette/httpx deprecation warning. A final rejected-candidate duplicate scenario was then
reproduced as a failing regression and corrected: duplicate domains cannot satisfy the
default quota after the consumer has declined their original candidate. All **154 affected
discovery, managed-reader, first-workflow and complete-workflow cases passed in 42.72 seconds**
after that adjustment. Ruff, the platform-reader JavaScript syntax check and diff checks passed.
The full suite result precedes that last one-line adjustment; the focused result covers the
final source. The 35-node source/test mapping was refreshed from the full-suite report.

Discovery now stops once the consumer has retained its requested unique website/profile
record count, preserving the last source event and distinguishing executed queries from
planned queries. Visible LinkedIn company Website safety redirects now preserve explicit
HTTP(S) destinations or complete URL labels before query removal. Controlled Chromium tests
exclude hidden/truncated targets, non-HTTP destinations and embedded credentials.

The user's VPS output establishes three retained prospects, partial website captures and
rendered LinkedIn company evidence. It does not establish buyer qualification or safe email
verification. DNS/connectivity failures and an unavailable Reacher backend require deployment
checks; no VPS service, account session or data volume was changed here. No real recipient
probe or outreach was performed. See [findings and limits](docs/LIVE_VPS_DISCOVERY_FIXES.md).

# Python registry override for VPS build recovery — 17 October 2026

Both app Dockerfiles now accept an optional `PYTHON_BASE_IMAGE` build argument, retaining
the previous Python 3.13 slim Bookworm default. An anonymous live check from the development
machine returned HTTP 200 for the ECR Public token and the exact `3.13-slim-bookworm`
manifest, with Linux amd64 support. Fourteen existing deployment/browser-setup checks passed
in 4.04 seconds. This does not establish a Docker build: no local Docker runtime is available.

The override provides a different registry path for the user's failed Docker Hub IPv6
connection. Actual ECR/pip/apt/Playwright reachability and a completed build on that VPS
remain to be checked. See [commands and scope](docs/REGISTRY_BUILD_RECOVERY.md). No host
network, Docker-daemon setting, running VPS service, session or data volume was modified.

# Search submission and background Pipeline refresh — 17 October 2026

The user's VPS initially reported zero leads and no jobs; the subsequent Operations view
also showed no jobs. Enabling Worker does not create a discovery query. Controlled desktop
and mobile tests verify that opening Find prospects creates no job, and submitting Start
research creates a pending discover job visible under Operations.

Pipeline now refreshes counts and the company list on entry and every 15 seconds while
visible. Background reads skip source diagnostics and selected-lead detail rendering, keep
the search filter and unsaved review edits intact, and avoid overlapping background refreshes.
Twelve UI/runtime-control cases passed in 23.05 seconds with one existing Starlette/httpx
warning. Real Chromium fixtures use a controlled clock and an isolated API/database; no live
discovery, recipient probe or outreach was initiated. Live VPS search execution and yield
remain dependent on the first actual submitted query and its job result.

# Pipeline loading and empty-state correction — 17 October 2026

A controlled Chromium test reproduced a blank Pipeline despite a saved lead when the
source-status endpoint returned HTTP 503. A second test reproduced the misleading
"No companies yet" text when an existing company was merely excluded by the search filter.
The dashboard now renders core status/leads independently of optional source diagnostics,
reports each failed diagnostic in its own panel, and distinguishes an empty database from
zero filter matches. Ten desktop/mobile and runtime-control cases passed in 19.04 seconds,
with one existing Starlette/httpx warning. Ruff and app.js syntax checks passed.

These are local UI reproductions, not a diagnosis of the user's current VPS database.
VPS lead/job counts are requested read-only before concluding that records are missing or
that the same optional-endpoint failure caused the reported blank Pipeline. No data was
migrated, deleted or sent during this correction.

# Selected NVIDIA writer adapter — 17 October 2026

For `nvidia/nemotron-3-ultra-550b-a55b` at the NVIDIA hosted endpoint, requests now explicitly
disable reasoning using the provider-documented `reasoning_effort: "none"`. Other models and
providers retain their previous request fields. Writer contracts, social research and runtime
UI controls passed **79 focused tests in 33.67 seconds**, with one existing Starlette/httpx
warning; Ruff passed. Four new cases cover the selected model, trailing-slash base URL,
another model and another provider. Mock-provider results remain unactivated drafts.

No real NVIDIA key was configured or tested here, and no live prospect data was sent to
the provider. Live account access, quota, output quality and latency remain to be checked
after the user saves the key in dashboard Settings → AI email writer. The preceding full
suite result below covers the crawler bug-review revision before this small adapter change.

# LinkedIn/X follow-up bug review — 17 October 2026

The full current suite passed **1194 tests in 352.09 seconds**, with zero failures and
one existing Starlette/httpx warning. The focused social-research, desktop/mobile dashboard
and runtime-control run passed **41 tests**. Thirteen additional regression cases cover
unrequested dialog links, empty section headings, optional-section deadlines, mismatched
LinkedIn activity links, hidden dates/permalinks, invalid X status routes, interrupted
captures, diagnostic completeness, lead-filtered history, transactional capture rollback
and outreach-status changes during browser access.

Ruff, syntax checks for every JavaScript reader/dashboard file and all **35 workflow-node
mappings** passed. Evidence, attribution and capture events now commit atomically with an
eligibility check inside the same transaction. The source dashboard distinguishes partial
capture from a bounded sample, and the deployment diagnostic refuses a partial pass.
See [the fixes](docs/SOCIAL_RESEARCH_UPGRADE.md#follow-up-bug-review).

These checks use isolated APIs, SQLite databases and controlled Chromium pages; they do
not access live LinkedIn/X accounts, verify real recipients or send outreach. Docker/VPS
acceptance and live yield of the new paths remain pending. Earlier results below retain
their original scope.

# LinkedIn/X research upgrade verification — 17 October 2026

The corrected full regression suite passed **1180 tests in 325.96 seconds**, with zero
failures and one existing Starlette/httpx warning. A separately added protected-X-account
rejection regression also passed. The focused desktop/mobile and privacy run passed 28
cases. All 35 workflow-node mappings were verified against the passing full-suite report.
Ruff and syntax checks for every dashboard/reader JavaScript file passed.

Real Chromium fixtures exercised managed people cards, semantic search layouts, Experience,
opt-in account-visible Contact Info, exact profile identity, hidden/dialog exclusion, durable
denial holds, author/permalink matching, quote-only/repost/protected-account rejection,
X latest-post author hints, timeout capture preservation and saved-source hash changes.
Pipeline tests verified local post storage without automatic contact/probe creation, reviewed
announcement evidence reaching AI-writing provenance, authenticated settings/queue APIs,
preflight control guards, and same-prospect job serialization.

Full dashboard JavaScript was checked against an isolated real API on desktop and mobile:
saved provider outcomes and posts rendered, post sources appeared in announcement review
but not the primary business finding selector, settings persisted and sending stayed OFF.
Screenshots are local at `data/social-upgrade-ui/desktop.png` and `mobile.png`. No live social
account, provider email probe or outreach was used by these checks. Test data is fictional.

The user's earlier VPS output proved the installed company About reader on one LinkedIn
page. It does not validate these new account-specific people/section/post paths. Docker/VPS
runtime acceptance, representative live yield and mailbox delivery remain separate. No
unrestricted access, invisible email recovery or Agent Reach performance superiority is
claimed. See [features and deployment](docs/SOCIAL_RESEARCH_UPGRADE.md).

Earlier dated verification snapshots follow with their original scopes.

# Live US/UK acquisition recheck - 11 October 2026

**575 tests passed in 130.31 seconds**, with one existing Starlette/httpx warning. Thirty-eight new intent/market/profile-route regressions cover bugs exposed by actual searches. Two current-code discovery waves reused 16 candidate companies across eight segment cells. Eight researched business representatives retain 205 current official pages, nine published company-domain inboxes and one separately reviewed owner Gmail; no qualification, recipient probe or outreach occurred in this check. Partial capture/continuation and restricted platforms were tested live. A genuine website-less email remains unaccepted. See [the scoped live proof](docs/LIVE_LEAD_ACCEPTANCE.md). Previous sections below retain their historical scopes.

# Current draft freshness and live acquisition verification - 11 October 2026

**537 tests passed in 139.16 seconds**, with one existing Starlette/httpx warning. Four stale Campaign A draft failures were reproduced and fixed; all five new checks pass, including a current partial-capture positive case. Current reviewed offer/source checks now run for both campaigns and again in the draft-write transaction. See [draft-source proof](docs/DRAFT_SOURCE_FRESHNESS.md).

A new actual SearXNG/worker run produced one florist prospect, 21 official pages and a published business-domain contact with a real Reacher safe/non-catch-all verdict. Source review produced four unscheduled, unapproved drafts and a local three-question FAQ prototype. No outreach was sent. Legal entity, buying authority, need, budget, interest and outreach eligibility remain unconfirmed. All 35 dashboard nodes and 46 connections passed read-only desktop/mobile inspection, preserving records after the intentional live run. See [actual live proof and limits](docs/LIVE_ACQUISITION_CURRENT.md). Earlier checks below retain their historical scope.

# Earlier verifier-dispatch/native setup verification - 11 October 2026

**532 tests passed in 126.67 seconds**, with one existing Starlette/httpx warning. Twelve verification timing failures were reproduced; thirteen regression cases now pass. Current publication, unchanged recipient and contact/global suppression are rechecked before dispatch and atomically before result storage. The updated normal dashboard passed all 35 node inspections on desktop/mobile, preserving operational records and private configuration. Sending remains disabled and paused. See [verification-dispatch proof](docs/VERIFICATION_DISPATCH.md). Earlier native-helper and source-quality results below remain historical; the actual native API and isolated catch-all result are documented separately in [NATIVE_REACHER.md](docs/NATIVE_REACHER.md).

# Current offer-source verification - 11 October 2026

**506 tests passed in 139.41 seconds**, with one existing Starlette/httpx dependency warning. Fifteen new cases verify legal/foreign/marketplace exclusions, contextual inquiry/FAQ signals, stronger service-specific source selection and exact word boundaries. Legacy automatic prefill is rechecked without changing records. Full Chromium smoke, second- and third-workflow forms and normal read-only desktop/mobile checks passed.

Saved-source replay of eleven real candidates produced eight reviewable offer sets and 32 unsent preview messages. It used existing evidence, made no network/verifier requests and saved no messages. Country/buyer/final-offer and mailbox review remain pending; no new live discovery or qualified lead acceptance is claimed. See [verification](docs/OFFER_SOURCE_QUALITY.md) and [preview material](docs/OFFER_DRAFT_PREVIEWS.md). Earlier sections below retain their snapshots.

# Current priority-readiness verification - 11 October 2026

**491 tests passed in 136.08 seconds**, with one existing Starlette/httpx dependency warning. Ten new regression cases failed before the fix and pass afterward. Readiness now uses the same current Campaign A/B offer and US/UK scope guard as the workflow and Learning; separate D2C commerce proof and canonical country-source matching are included. Future captures earn no research credit. Full isolated Chromium smoke and the third-workflow form check passed.

An isolated local benchmark measured 500 unreviewed records in 0.0273 seconds and 500 reviewed D2C records with 1,500 source pages and 500 published-contact fixtures in 0.1319 seconds. Jobs/messages/events stayed unchanged; no normal database, network, worker, verifier or sender was used. This is review-queue latency only. See [details](docs/PRIORITY_READINESS.md) and [the current complete audit](docs/COMPLETE_WORKFLOW_AUDIT.md).

Earlier sections below retain their source snapshots.

# Current contact-publication verification - 11 October 2026

**481 tests passed in 134.07 seconds**, with one existing Starlette/httpx dependency warning. Seventeen new publication regression cases cover guessed addresses, stale/future/superseded sources, public mailto and structured contacts, source adoption, suppression preservation, API/UI holds and frozen recipient-page approval. The send claim records both source and sequence holds when publication changes, using the same transaction.

Full isolated Chromium smoke and the third-workflow form check passed. The reloaded normal dashboard passed read-only inspection of all 35 nodes and 46 connections, eleven overview stages, eleven prospect maps and all nine contact verification buttons on desktop/mobile, with zero JavaScript errors or overflow. Real operational data and private configuration were unchanged; sending stays hard-disabled and globally paused with zero messages.

Live isolated contact recovery refreshed two pages each on Skindays and SmartRoof. Skindays returned four previously known published inbox candidates, all passing the new publication gate; SmartRoof returned none. Both remained partial. No verifier or sender ran. Public-source proof does not establish buyer relevance, mailbox existence or unrestricted platform access. See [the source gate](docs/CONTACT_PUBLICATION.md), [current live results](docs/contact-fallback-live-check.json) and [node/test mappings](docs/COMPLETE_WORKFLOW_AUDIT.md).

Earlier sections below retain their historical snapshots.

# Latest README/workflow and Learning recheck — 11 October 2026

**464 tests passed in 137.84 seconds**, with one existing Starlette/httpx warning. All four new source-freshness regressions failed before the fix and pass afterward. Learning current qualification now shares the workflow’s reviewed-offer guard; historical approvals/SMTP acceptance stay preserved. Full isolated Chromium smoke, installed dependency check, JavaScript syntax and PowerShell startup syntax passed. The current full graph maps all 35 nodes and 46 connections to executed checks. README’s obsolete leading audit count and database schema claim were corrected; WORKFLOW.md and its three-part comparison point to current proof while retaining historical snapshots.

Actual external deployment/provider/acquisition/client acceptance remains incomplete. See [the current comparison](docs/README_WORKFLOW_CHECK.md). No email or social message was sent; real operational data and private configuration remain unchanged. Sending stays hard-disabled and globally paused.

# Earlier contact-source fallback — 11 October 2026

**460 tests passed in 114.05 seconds**, with one existing Starlette/httpx dependency warning; Ruff passed. Twenty-seven recovery cases now include eight additional cases covering empty/failed index fallback, current saved-contact refresh, checkpoint-origin route recovery, unsafe index-route exclusion and four editorial/catalog false-positive variants.

Real HTTP/Chromium captures used an intentionally empty search index in an isolated copy of existing candidate evidence. Skindays yielded four previously known published inbox candidates from two official pages. SmartRoof yielded none from two pages. Both runs remain partial. No new discovery, country/buyer qualification or mailbox verification was performed. The normal database counters and private settings were unchanged; sending remains hard-disabled and globally paused with zero messages.

The current normal dashboard's 35 nodes, 46 connections, eleven-stage overview and eleven prospect maps passed read-only desktop/mobile inspection with zero JavaScript errors or overflow. The full node/test mapping includes the new recovery cases. See [scope and reproduction](docs/CONTACT_SOURCE_FALLBACK.md), [raw current-source live proof](docs/contact-fallback-live-check.json) and [current complete workflow audit](docs/COMPLETE_WORKFLOW_AUDIT.md).

Earlier checks below describe their historical snapshots.

# Earlier research recovery — 11 October 2026

**452 tests passed in 113.01 seconds**, with one existing Starlette/httpx dependency warning; full isolated Chromium dashboard smoke passed. Nineteen new recovery cases cover checkpoint preservation, legacy frontier reconstruction, seeded robots controls, index-to-official contact corroboration, automatic queueing, same-company serialization, workflow status, unavailable-verifier recipient protection, syntax-contract variants and DNS limits. The updated 35-node source/test mapping includes these cases separately from earlier complete-workflow/pilot regressions.

Actual normal-dashboard controls displayed the real verifier setup problem and queued SmartRoof continuation. Its saved current pages grew from 30 to **41**, without discarding the existing page records; coverage remains partial. Three actual contact-source passes across SmartRoof and Portland captured **18 official pages including refreshes**, with **zero new published contacts**. A fresh targeted LinkedIn index query did not find the exact stored profile; Portland's current official site did corroborate the earlier stored LinkedIn link. This is counterpart corroboration, not successful direct platform/email access. Actual free DNS fallback found Skindays mail exchangers; the contact remains unknown, and the wrong API receives syntax-only input. No recipient-server SMTP conversation or email occurred. The actual backend has not started: local 8080 serves Apache/httpd, and Docker/Rust/usable Linux are unavailable. The local backend helper honestly reports not ready; its Compose override uses loopback 8081 when Docker becomes available.

The current-code public practice-site check rendered 2 pages followed by 2 new pages, preserving original IDs with zero duplicate captures. This is checkpoint/Chromium proof, not prospect or performance acceptance. Sending stays hard-disabled and globally paused, private configuration is unchanged, and no email/social message/contact form was submitted. See [behavior and runtime limits](docs/RECOVERY_PATHS.md) and [live results/current source hashes](docs/recovery-live-check.json).

Earlier workflow checks below describe their historical snapshots.

# Live no-send pilot before recovery — 11 October 2026

**433 tests passed in 110.79 seconds**, with one existing Starlette/httpx dependency warning; Ruff passed. Twenty-two new regressions cover nonbuyer inboxes, noisy marketplace discovery/import guards and interrupted-crawl recovery. Full isolated Chromium UI smoke passed. The updated 35-node source/test map includes these checks separately from the eighteen complete-workflow cases and four loopback client journeys.

The user-requested actual discovery/crawl run used the normal dashboard database and native SearXNG: four searches across Campaign A/B and US/UK, 36 search queries, four website candidates, **112 current official-site captures (all rendered)**, desktop/mobile screenshots, and **five published email candidates after exclusions**. One privacy-only inbox was excluded without recording a fictional recipient opt-out; a wrong marketplace record remains rejected history. All four crawls are partial, all companies remain unqualified and all retained new contacts have unknown mailbox verification. The configured local Reacher endpoint returns HTTP 404; no successful recipient-server probe or safe verdict is established. LinkedIn/X/platform snapshots often remain robots-denied or unavailable. There are **zero messages, zero approved sequences and zero emails sent**. See [the live report](docs/NO_SEND_PILOT.md) and [saved counts/source hashes](docs/no-send-pilot-check.json).

Normal desktop/mobile Chromium inspection passed for all 35 nodes, 46 connections, eleven prospect maps and the eleven-stage overview, with zero JavaScript errors or overflow. The fifteen operational tables and private settings remained unchanged during this read-only inspection. The dashboard now contains eleven historical/current candidate records (including rejected history), nine contact records (including excluded history), zero qualified companies and zero messages. Sending remains hard-disabled and globally paused. Runtime search depth is restored to its default 40-signal ceiling after the pilot; the crawl stayed at its usual 30-page budget.

Earlier workflow checks below describe their historical snapshots.

# Complete-workflow verification before the live pilot — 11 October 2026

**411 tests passed in 114.03 seconds**, with one existing Starlette/httpx dependency warning; Ruff and dashboard JavaScript syntax checks passed. All 35 nodes and 46 unique reachable connections map to current implementation and executed passing tests. Eighteen new cases cover cross-node freshness, frozen approval changes, artifact/proposal readiness, call requirements and stale verification Hold status. Four connected journeys exercise Campaign A/B with official websites and website-less profiles from queued discovery through client outcome records. Search/site/Reacher inputs are controlled fixtures; the actual crawler and trusted loopback TLS SMTP/IMAP clients execute. Existing separate tests cover Chromium crawling, screenshots, four-touch scheduling, opt-out/bounce/OOO/uncertain outcomes, quotas, concurrency and client task/finance/aftercare conditions.

Full isolated Chromium smoke and approval/revision/reapproval controls passed. Updated normal server inspection opened all 35 nodes, checked all six prospect maps and the eleven-stage overview on desktop/mobile, with zero JavaScript errors or page overflow. All fifteen operational tables and private configuration stayed unchanged: six candidates, three unverified contacts, zero messages and zero qualified candidates. No real address was probed and no external email was sent. VPS/domain/mailbox remain user-owned setup; external provider and real-client acceptance has not been established. See [every node](docs/COMPLETE_WORKFLOW_AUDIT.md) and [machine-readable proof](docs/complete-workflow-check.json).

Earlier workflow checks below describe their historical snapshots.

# Third-workflow verification — 11 October 2026

**393 tests passed in 115.18 seconds**, with one existing dependency warning; Ruff and JavaScript syntax checks passed. All 23 boxes in the supplied third diagram map to executed behavioral checks, including 37 new cases. Trusted localhost SMTP/IMAP tests exercise actual TLS protocols, four touches and failure/stop branches. Actual isolated Chromium forms verify approval/revision/reapproval and the new baseline field; the full dashboard smoke also passed. Normal desktop/mobile checks show zero JavaScript errors/overflow and preserve all real operational records/private configuration. Six real candidates remain unqualified, with three unverified contacts and zero messages. No real recipient was probed or emailed; domain/VPS/mailbox setup remains user-owned. See [each node and its boundary](docs/THIRD_WORKFLOW_AUDIT.md) and [machine-readable evidence](docs/third-workflow-check.json).

Earlier workflow checks below describe their respective snapshots.

# Second-workflow verification — 11 October 2026

**356 tests passed in 102.24 seconds**, with one existing dependency warning; Ruff and JavaScript syntax checks passed. All 15 nodes of the service-selection diagram have behavioral evidence, including eight campaign/service combinations. Chromium submitted actual A/B qualification and artifact-review forms in fictional isolated data, checked unknown/confirmed WhatsApp routing, and passed the existing full UI smoke. Normal-server desktop/mobile checks showed zero JavaScript errors and preserved real records/configuration. Six real candidates remain unqualified, with zero current selected offers or reviewed value artifacts. No email probe or external message occurred. See [the second-workflow audit](docs/SECOND_WORKFLOW_AUDIT.md) and [machine-readable proof](docs/second-workflow-check.json).

# Crawler optimization verification — 11 October 2026

**322 tests passed in 92.60 seconds**, with one existing dependency warning. Ruff, dashboard JavaScript syntax, and actual normal-server desktop/mobile Chromium checks passed. The same four-site, 180-second live diagnostic preserved 36 pages instead of 35, with three sites yielding captures instead of two; the published unverified inbox count stayed at one. Three crawls were interrupted at the diagnostic deadline; one failed at robots fetch with HTTP 403. All candidates remain unqualified. No email probe or outgoing mail occurred. See [the crawler comparison](docs/CRAWLER_OPTIMIZATION.md) and [machine-readable proof](docs/crawler-optimization-check.json).

Historical first-workflow check follows; its raw captures and reports remain unchanged.

# First-workflow verification — 11 October 2026

305 tests passed, followed by 17 focused cases after the final freshness/readiness adjustment; full Chromium smoke and normal desktop/mobile UI checks passed with zero JavaScript errors. Own live search produced four new website candidates; two crawls preserved 35 current source pages and one published business inbox. Two sites did not yield usable pages within the diagnostic; all candidates remain unqualified. The read-only view exposes three current quoted opportunity previews. No external mail or email probe occurred. See [the first-workflow audit](docs/FIRST_WORKFLOW_AUDIT.md) and [machine-readable proof](docs/first-workflow-check.json).

The new default research view has 17 nodes and seven guided steps. The 11-stage overview and 35-node complete map remain available. Earlier results below describe their respective historical check; they are not current live acceptance claims.

# Validation and deployment readiness

Latest feature release: **288 tests passed**, zero failures, one existing warning, 93.47 seconds. Explainable prospect priorities, exact separate-currency cost/receipt reporting with correction history, and permission-reviewed post-delivery maintenance/expansion/case-study plans are implemented. Full Chromium checks actual forms and desktop/mobile navigation with zero JavaScript errors; normal-server read-only checks preserve all existing operational records and credentials. Calls, payments, agreement, client delivery and publication remain operator-recorded. See [feature details](docs/PRIORITY_FINANCE_AFTERCARE.md) and [current proof](docs/growth-feature-check.json). Older validation sections below are historical.

Latest full-workflow map: **264 passed, zero failures, one existing deprecation warning, 81.92 seconds** (`data/audit-detailed-map-tests-release.log`, JUnit `data/audit-detailed-map-tests-release.xml`). Overview retains eleven stages; Full workflow now renders every one of the 35 documented nodes and 46 connections. Eleven new API/state tests cover branch and review accuracy, partial/historical audits, reply tasks and sales-reference gates. Actual desktop/mobile Chromium verifies mode switching, stage inspection, scope, routes/actions, learning navigation and an inspector that does not obscure the canvas, with zero JavaScript errors. Domain/VPS/mailbox setup remains user-owned, independently of local development.

Latest user-requested node recheck, 10 October 2026: **253 passed, zero failures, one existing deprecation warning, 82.47 seconds** (`data/audit-user-node-tests.log`, JUnit `data/audit-user-node-tests.xml`). All 35 detailed nodes were remapped against these executed tests in [the audit](docs/EVERY_NODE_AUDIT.md). App API read-only checks confirm eleven grouped stages, two prospects/two contacts, zero approvals/messages/safe contacts, and sending disabled. Reacher root HTTP 200 was a different local service; the invalid-syntax API returns HTTP 404. Preflight now checks the syntax/auth contract and has four new passing regressions. TCP/25 connectivity alone does not establish recipient verification or deployment readiness. No UI source changed in this recheck; the prior successful Chromium results below are retained as prior evidence, not newly executed UI acceptance.

Checked on 10 October 2026 in the user's Windows workspace. The development app and free native search backend run locally; the user has deferred VPS and mailbox configuration. Production sending infrastructure is not configured or validated.

## Completed checks

| Check | Result |
|---|---|
| Automated suite | 249 passed, zero failures in 83.26 seconds; all 35 nodes mapped to source and executed tests in `docs/every-node-audit.json` and `docs/EVERY_NODE_AUDIT.md`. Latest README/workflow comparison is `docs/README_WORKFLOW_CHECK.md`. Earlier UI/settings evidence (224 tests) is retained in `docs/ui-workspace-check.json`, profile-first evidence in `docs/profile-prospects-check.json`, platform/login evidence in `docs/platform-discovery-check.json`, and the crawler/source audit passed 181 tests in 71.60 seconds. |
| Free service proposals | Eleven new tests cover campaign/quote/offer priority, profile website-status holds, negative/insufficient cues, channel-consent limits and an integrated no-AI crawl-to-idea path without qualification/drafts. A read-only preview on thirty current real website pages produced matching store/support proposals; the blocked profile produced none. No live recipient was probed. See `docs/SERVICE_PROPOSALS.md`. |
| Learning and effective readiness | Seven learning tests cover empty rates, deduplication, automatic-response exclusion, channel/timing boundaries, immutable approval context, unknown legacy attribution, sales history, auth/redaction and read-only reporting. An actual subprocess preflight test checks managed overrides without secret disclosure. Chromium verifies empty/nonzero/XSS-labelled fictional learning and desktop/mobile layouts. Real-server learning still has zero accepted/approved and null rates. See `docs/LEARNING.md`. |
| Every detailed node | Source/functions, passing test cases, actual behavior, human gates and live limits recorded separately for A–Z plus branch nodes: 35 total. Six map-status defects first reproduced (6 failed / 4 passed), then all ten map tests passed. Current browser smoke passed with zero JavaScript errors. Node implementation is not a claim of deployed provider/client acceptance. |
| Workflow map and settings | Actual Chromium checked eleven connected stages, node selection/drag/zoom, per-prospect filtering, desktop/mobile layout, persisted fictional SMTP/IMAP settings, password change, session termination and fresh login; zero JavaScript errors. Settings security tests cover secret redaction, origin protection, password hashing, session invalidation, restart persistence, save validation and concurrent mailbox protection. Normal-server UI was inspected without changing actual credentials or sending mail. See `docs/UI_WORKSPACE.md`. |
| Python lint | Ruff passed |
| Dashboard JavaScript | `node --check` passed for `app.js`, `sales.js` and the new `login.js` |
| Actual Chromium dashboard smoke | Passed committed-action/refresh-failure feedback (one persisted note, no false save-failure message), then authenticated source qualification/drafts, demo controls, shared manual reply, client qualification, dated task, artifact creation/review/export, proposal creation/review, mobile layout and unsafe approval rejection; zero JavaScript errors |
| Actual Chromium crawler fixture | Executed external CDN JavaScript/CSS and GET data request, extracted dynamically inserted emails and open shadow-root content, excluded hidden text, blocked private-network/POST requests, and captured desktop/mobile images |
| Browser resource and shutdown behavior | Real Chromium verified bounded asset concurrency, eligible cache reuse, late-request cancellation and retention of rendered evidence after an injected cleanup failure. Shared declared robots pacing applies across HTTP pages, assets and www aliases; browser-close failure still stops the driver |
| Sitemap/deep research | Tested nested indexes, contact priority, tracking URL deduplication, catalog/news budget sharing, hash routes and partial-page preservation |
| Durable research | Tested saved contact identity/coverage reports, late-failure evidence preservation, blocked review during active research, atomic research-start/approval exclusion, current-only suggestions, stale country/observation/trigger/follow-up rejection, transactional source recheck and per-lead job isolation |
| Independent mailbox lane | Tested that monitoring/sending continues during long research and shutdown returns an interrupted job to pending |
| Conservative verification and outreach lifecycle | Tested Reacher contract/contradictions, freshness/unknown holds, reviewed drafts, quota/window behavior, uncertain SMTP outcomes, replies/bounces, opt-out and recovery |
| Full four-touch calendar | Two additional real TLS SMTP tests passed in 1.82 seconds. They exercised all four touches with nominal and delayed simulated calendars across the UK DST transition, checked minimum spacing from actual acceptance, durable/thread message IDs, no overdue burst and terminal closure after four accepted messages. Fresh verification/inbox state is an isolated fixture, not a real provider result. Both tests are included in the current 215-test full suite |
| Actual loopback mail protocols | Python SMTP STARTTLS/implicit TLS and IMAP TLS connected to isolated protocol fixtures with temporary trusted certificates; captured RFC messages, read-only inbox polling, HTML-only opt-out, UID idempotency and sequence cancellation passed. No external delivery occurred. |
| SMTP stages and certificate verification | Real socket tests covered authentication failure, temporary recipient refusal, DATA rejection, lost acceptance response and post-acceptance QUIT disconnect. Untrusted certificates were rejected before authentication; uncertain outcomes were not retried. |
| Offline demo isolation | API rejects resume; sender skips demo data even with live settings; worker skips provider/mail lanes. Chromium checked the demo label and disabled resume button. |
| Browser process isolation | Sandbox-enabled Chromium fixture passed on Windows; application/provider secrets are excluded from the browser subprocess environment |
| Artifact access | Authenticated report and new desktop/mobile screenshot filenames tested; unauthenticated access blocked |
| Deployment files and backup | Compose/TOML/JSON parsed in tests; provider ports internal; database backup integrity passed |
| Local readiness | Chromium installed; sending disabled; sender/mailbox/HTTPS/domain-auth configuration missing |
| Requirements re-audit | Regression checks for Campaign B offer restrictions, exact saved country quotes, sourced announcements/follow-up ideas, WhatsApp channel-fit notes, legacy qualification gate, platform filtering, concurrent approvals/draft generation, stop-status preservation and timezone queue fairness |
| PageSpeed adapter | Mobile/desktop response parsing, partial success, quota failure, cross-business redirect rejection, API job/report access and key redaction tested using controlled provider responses |
| Shared outreach history | Manual outreach blocks overlapping cold email; manual/inbox replies stop sequences and create review/fulfillment tasks; opt-outs persist; cross-company contacts and unsafe hold release rejected |
| Published other-domain inboxes | Thirteen tests cover sourced candidate retention without automatic import/probing, ownership/source requirements, stale source invalidation after partial/failed recrawls, atomic source-import checks, verification-wait opt-outs/source changes, shared-inbox conflicts, API review, provider-probe blocking and pre-SMTP holds. Actual Chromium verified candidate visibility, rejected missing ownership notes, accepted reviewed fictional contact, mobile layout and zero JavaScript errors. Fresh live official-page research retained one candidate / zero automatic contacts in 25.54 seconds, without observed callback warnings; no real recipient was probed |
| Sales lifecycle and migration | Actual v1-layout fixture upgrades to schema 2 without losing messages; stale updates, unconfirmed qualification, unreviewed/undelivered proposals and missing agreement/payment/acceptance references rejected; operator-recorded lifecycle and currency-separated reporting passed |
| Value artifacts | Exact same-company quotes, escaped content, same-company screenshots/callouts, review and delivery gates tested for audit, concept, FAQ prototype and WhatsApp outline. Real Chromium opened fictional audit/FAQ exports with no remote asset requests; FAQ disclosure interaction and mobile layout passed |
| Research benchmark tooling | Deduplication/platform filtering, streamed partial evidence, review-sheet output, isolated parallel workers and unknown quality/memory metrics tested. The original 50 attempts finished: 29 partial / 21 failed, 774 rendered captures / 769 unique final URLs. The 21-company retry stopped at the user's temporary pause after 13 completed attempts (9 partial / 4 failed); the resumed nine-attempt run finished with 212 captured/rendered pages and explicit partial coverage. A further DNS-recovery check rendered 30 Yafa Queen pages. Latest-per-domain results are 46 partial / 4 failed across the original 50 candidates; mixed code lineage and independent acceptance remain explicit |
| Evidence-based draft previews | Eight tests verify production-copy parity, sourced company/country/observation evidence, supported offers, completed/distinct reports and escaped exports; no database, provider calls or operational contacts are created. Twenty distinct companies / 80 messages have source/copy review, with five companies in each campaign/country group. Actual Chromium opened all follow-ups at mobile width with no overflow, remote requests or JavaScript errors. Source/copy review is complete; independent operator/buyer/recipient approval and live pilot acceptance remain pending |
| Browser context recovery | Actual Chromium reproduced an unowned-abort cleanup exception on Playwright 1.58.0. Version 1.63.0 and app recovery rendered the next mediated page through a fresh context without orphan callbacks. Page-creation failure is reported with empty rendered HTML, allowing static evidence and later pages to remain usable. A further cleanup-task failure was reproduced and fixed; recovery requires a confirmed context close, with both recovery and unconfirmed-close refusal covered by real Chromium. The extended live run finished with 30 unique/rendered Goldstein pages, no job error and partial resource coverage |
| Terminal browser route failures | Actual Chromium fixtures exercise failed fulfill and unowned abort operations without orphan callbacks or direct-network fallback. A fresh affected-page live check retained one rendered page in 29.1 seconds, with explicit partial coverage and no observed callback warning |
| Reacher startup-smoke tooling | Real loopback HTTP fixture checked invalid-syntax-only requests, header rejection, error response handling and rejection of an unprotected/wrong-contract service. This is not a Reacher binary/container startup result |

The current full suite includes the final copy edits, browser recovery, current-source review and verification-wait fixes. Actual Chromium passed the complete dashboard workflow, an injected post-save refresh failure (one persisted fictional note and explicit committed-action feedback), and historical-source display with current-only qualification selectors. [The dated draft-preview check](docs/draft-review-check.json) preserves the 20-company/80-message scope and its approval limits.

One dependency warning remains: Starlette's test client deprecates its HTTPX adapter in favor of HTTPX2. It did not cause a test failure. This is a test dependency migration task, not evidence of live provider validation.

## Live crawler smoke check

The public JavaScript practice website `https://quotes.toscrape.com/js/` was researched using the implemented fetcher and real Chromium. Two pages rendered successfully in 30.59 seconds on this Windows workstation. There were no fetch/render errors. The report is **partial** because the explicit two-page test budget left more URLs to research.

See [the concise machine-readable result](docs/crawler-live-check.json). It preserves URLs, hashes, text counts and coverage metadata, without copied page text. This practice site is not a prospect. No contacts were imported/verified and no email was sent. The timing is not a benchmark of a 4 GB VPS or of typical Shopify/service-business sites.

Four genuine service/ecommerce candidate websites across US/UK were also researched after the live-crawler fixes, with a two-page budget per company: **8 pages captured and rendered, no unhandled callback errors observed** in that fresh run. Individual two-page runs took 34.85–44.04 seconds on this workstation. All four reports are **partial**: the page budget and reported blocked POST/external-document requests, resource limits/pending resources and site script errors prevent a complete-audit claim. Rendered HTML does not mean every resource or feature worked. See [the business-site smoke result](docs/crawler-business-check.json); full page evidence and the independent review sheet stay in the private data directory. No prospect import, recipient verification or email send occurred. This four-site sample does not fulfill the 50-company or 20-draft acceptance plan.

## Not yet validated

- The on-demand PageSpeed integration was attempted against the public practice site without a key; Google returned HTTP 429 for both strategies. No score was saved. See [the provider-check result](docs/pagespeed-live-check.json). Successful live mobile/desktop measurement requires available provider quota/key; tests cover the response contract, not live measurement accuracy.

- Docker is unavailable on this workstation. App/Reacher image builds, the seccomp/kernel user-namespace combination, container startup and memory/CPU behavior have not been run here. CI includes dashboard/browser checks, app build/config checks and a separate Reacher source build/startup/auth/syntax check. It has not been dispatched to an external repository; a workflow file is not evidence that these builds passed.
- The pinned Reacher source recipe and adapter exist. Actual self-hosted startup, outbound TCP/25, EHLO/reverse DNS, recipient-server probing and result accuracy require the real deployment. A technical safe result is still not proof of mailbox ownership or guaranteed inbox delivery.
- The pinned native SearXNG development backend now runs locally and completed actual indexed-platform discovery. Its Linux/container deployment, n8n runtime and optional paid provider remain unvalidated. Some engines returned CAPTCHA/access denial/rate limits; these are recorded, not bypassed. See `docs/PLATFORM_DISCOVERY.md` and the dated feature check.
- Real SMTP/IMAP login, sender SPF/DKIM/DMARC, public HTTPS/unsubscribe reachability, controlled-recipient send/reply/bounce tests and actual provider quotas require the user's mailbox/domain/VPS.
- Optional AI suggestions have a mocked structured-output/quote-validation test. No real model API call has been made; an API key/model is not configured.
- No real prospect campaign is active. Nothing in the test results establishes acquisition performance, replies, conversions or clients.
- The original 50-company attempt run finished, with 29 partial reports and 21 failed attempts. The 21-company retry was interrupted at the user's requested pause after 13 completed attempts. Its Goldstein Heather result saved 30 pages but rendered only 14; this is not a passing recovery result. The resumed nine-attempt run finished with 212/212 rendered captures and all reports partial. A further DNS-recovery attempt rendered 30/30 Yafa Queen captures. Goldstein rendered 25/25 captures but hit its 1800-second deadline; the extended check finished with 30 unique/rendered captures in 2098.21 seconds and no job error, preserving declared robots pacing within its explicit 3600-second deadline. Completed other-company attempts were preserved. Source/copy review covers twenty distinct real company previews / 80 messages, balanced across both campaigns and countries; none is a send-ready or operator-approved contact. The live 20-prospect pilot and independent buyer/recipient acceptance remain pending. The original run predates the redirect/route/contact corrections and produced callback warnings, so its observational evidence does not establish clean acceptance of the corrected code. See [the benchmark scope and findings](docs/BENCHMARK.md) and its dated progress snapshot. Fixture/example output is not representative acceptance.

See [the chat/notes requirements audit](docs/AUDIT.md) for which early alternatives were superseded, what is implemented and which business-process steps remain manual.

## Deployment acceptance

Before treating the system as live, configure the actual sender/domain/mailbox and VPS, build/start the providers, run read-only preflight connectivity checks, benchmark representative sites, inspect crawl coverage/screenshots, validate a controlled-recipient mail lifecycle and test public opt-out reachability. Then review real sourced prospects and enable/resume sending. Credentials belong in the private deployment `.env`, never in chat or the source release.

## Reproduce

Latest 12 October verification: **854 tests passed**, including 15 subsequent publication/browser-status cases, 19 named-person/profile-parser cases and 25 multi-source/quality cases, 32 professional-source cases, 24 opt-in VPS-browser tests and 19 source-failover/recovery/coverage cases. Ruff, Python compilation, reader JavaScript syntax and Chromium UI smoke passed. The normal preview remains sending-disabled/paused with operational data/settings unchanged in its read-only UI check. Browser-mode tests use intercepted fictional DOM and synthetic persistent session state; they do not establish authenticated VPS access or vendor parity. See [the browser-mode verification boundaries](docs/PLATFORM_BROWSER.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check outreach tests scripts
node --check outreach/static/app.js
node --check outreach/static/sales.js
.\.venv\Scripts\python.exe scripts/ui_smoke.py
.\.venv\Scripts\python.exe scripts/preflight.py
.\.venv\Scripts\python.exe scripts/package_release.py
```

## Latest recovery evidence

The completed nine-attempt run contains 212 captures, all rendered, with coverage/resource limitations still reported. Actual cleanup-task failures were followed by successful context recreation and capture on Austin Studio Architects and Yafa Queen. [The recovery report](docs/crawler-recovery-check.json) records the affected source URLs/hashes and the earlier failure. Goldstein's earlier 25/25 rendered attempt ended at the 1800-second deadline. The [terminal extended-run result](docs/benchmark-extended-progress.json) captured/rendered 30 unique pages in 2098.21 seconds without a job error; four context recreations preserved rendering and no orphan callback warning was observed in its log. Pending resources keep coverage partial; this is not complete website or actual VPS acceptance. The benchmark CLI now accepts `--timeout` and records its effective company deadline; both explicit override and environment fallback preserve the full browser/page scope in tests.

[The latest-per-domain inventory](docs/benchmark-latest-attempts.json) preserves 46 partial / 4 failed outcomes across 50 original candidates, with mixed implementation lineage. Source/fit review covers the 46 available companies: 43 geographic source supports / 3 holds. These are not independent buyer, business, ownership or recipient approvals. Nothing was imported into an operational prospect campaign, probed or emailed.

## Profile-first prospects

The website-less prospect branch is implemented. Actual Chromium exercised the profile form, identity/activity/search review, sourced Gmail ownership import, four drafts and mobile layout using fictional evidence. The updated normal development dashboard and CSV profile fields were also checked. A real LinkedIn-company-profile job found/reused the already researched website; the profile snapshot was robots-denied and no profile contact or verification job was created. It does not establish real website-less recipient acquisition. See `docs/PROFILE_PROSPECTS.md` and `docs/profile-prospects-check.json`.

## Multi-source discovery and contact check

Bounded alternate engine selection, Common Crawl URL hints, current official navigation, profile-company relevance checks, cache/pacing/cooldown, directory exclusions and source-summary UI are implemented. A real four-query discovery pass yielded 13 indexed company candidates after filtering/deduplication. Two known companies yielded 2/2 current contact-recovery pages: Bouquets 1 current sourced company email, Portland 0. Bouquets had one observed official Instagram link but no matching LinkedIn/X professional capture; separate indexed social hints remain unverified. No recipient probes or sends occurred, and the operational database was unchanged. See [multi-source implementation and limits](docs/MULTISOURCE_DISCOVERY.md) and the dated [live report](docs/multisource-live-check.json). This is not representative buyer qualification, personal-email extraction, vendor parity or VPS acceptance.

## Subsequent personal-profile goal audit

Sourced names without an email now guide profile queries, and scoped X name/handle/mailto parsing was corrected. Eleven real official pages across six companies exposed three person hints. Three isolated professional runs produced zero live personal-profile emails; two Portland indexed professional targets and six direct access controls stopped at the robots gate. No contacts, probes, sends or operational-data changes occurred. The goal remains incomplete. See [sourced-person implementation and exact live boundaries](docs/NAMED_PEOPLE_RESEARCH.md).

## Public publishing and guest-browser audit

The first-party X single-post endpoint works live on a non-client control with zero emails. Two anonymous browser profile controls returned LinkedIn HTTP 999 and X HTTP 403. Profile publishing returned timeline-anchor markup without biography/email content. Explicit post mailto/obfuscation and hidden-data filtering were corrected; browser errors and professional reports retain actual source statuses. The acquisition/parity goal remains incomplete. See [the current requirement-by-requirement audit](docs/PUBLIC_TRANSPORT_AUDIT.md) and [live evidence](docs/public-transports-live-check.json). No contacts, probes, sends or operational-data mutations occurred.

## Access-origin diagnosis and durable recovery — 12 October 2026

**867 tests passed in 193.70 seconds**, with the existing Starlette/httpx warning. Thirteen new checks cover durable per-platform denial holds, cross-process clearing, rate-limit expiry and HTTP-date parsing, corrupt-state handling, secret-free diagnostic metadata, prevention of browser relaunch after restart, and continued free discovery when both platforms are held. Ruff and Python compilation passed.

A four-navigation live comparison returned the same LinkedIn 999 and X 403 in ordinary guest Chromium and the managed allowlist mode. Removing the application's routing did not restore access. An isolated recovery test then held both platforms using those observed host-level denials, resolved the recorded SonriaUK business via current independent public research, and captured one published business-email candidate from its official homepage. This was known-company recovery, not fresh discovery, recipient verification or personal-profile email extraction. The main database remained unchanged, with zero imports, probes and sends. See [diagnosis, recovery and remaining gaps](docs/PLATFORM_ACCESS_RECOVERY.md).

The local preview was restarted on updated source, with sending disabled and paused, managed browsing disabled, no active jobs and no enabled schedules. A read-only desktop/mobile UI check passed with zero JavaScript errors, zero provider calls/messages and unchanged operational data/settings. Runtime session/access state is excluded from the release ZIP. Direct LinkedIn/X profile-email acquisition and representative vendor-level coverage remain incomplete.

The follow-up official X profile-widget rendering diagnostic loaded current first-party widget/timeline JavaScript, but both public timeline frames returned 429. No profile bio was captured and no personal-email success was established. This is new live access-path evidence, not a passing production adapter. The diagnostic now stops further controls after the first denial and records a bounded retry interval. Ruff/Python compilation and source ZIP integrity passed; the production implementation did not change after the 867-test suite. See the follow-up section in [the recovery audit](docs/PLATFORM_ACCESS_RECOVERY.md).

## User-authorized free community X profile test and optional adapter — 12 October 2026

The explicitly authorized three-profile FxEmbed API test returned three matching public bios and **two actual bio email candidates**, including one personal-profile control. Native X/LinkedIn access was not restored. Source freshness, mailbox existence, buyer relevance and representative client recall remain unverified. The operational database remained unchanged, with zero contacts imported, probes or sends. See [the exact live sample, provenance and limits](docs/FXEMBED_PROFILE_CHECK.md).

The optional fixed-host adapter remains **disabled by default and in the normal preview**. Company-professional research can collect separate community hints after a native X capture fails when the setting is enabled. The original denial remains authoritative for the native capture; community data cannot become first-party evidence or automatically create recipients/verification/send jobs. The dashboard displays mirror hints separately with source, cache and retrieval information.

**885 tests passed in 185.31 seconds**, with one existing warning; the 55-test focused adapter/professional set also passed. Chromium smoke passed mirror-source display and script-text escaping, plus the existing desktop/mobile flows, with zero JavaScript errors. Ruff, Python compilation and JavaScript syntax passed. The updated normal preview's read-only desktop/mobile check preserved operational data/settings, made zero provider calls/messages and confirmed sending disabled/paused. Source ZIP integrity passed with runtime/session data excluded. The full LinkedIn/X and vendor-coverage objective is not complete.

### Follow-up: current publication and contact-route accuracy

The two saved bio candidates are explicitly labelled customer-support/order-inquiry routes; neither establishes a decision-maker inbox. The adapter/dashboard now preserve exact label context and this distinction, without assigning buyer authority. **61 focused adapter/professional checks passed** after six new purpose-label cases; Chromium smoke passed the new labels and escaping with zero JavaScript errors. Ruff and JavaScript syntax passed. The preceding 885 full-suite result is the baseline before this additive follow-up.

A current normal-crawler capture independently matched Music Plaza's bio address on its official help page. Gooms' linked store could not be recaptured over HTTP/HTTPS. A further public HTML mirror stopped on a robots-resource 403, so it was not integrated. No additional FxEmbed API calls, contacts, probes or sends occurred. Operational data stayed unchanged. See the [current corroboration and exact remaining limits](docs/FXEMBED_PROFILE_CHECK.md).

## Enabled automatic X source and eight-business validation — 12 October 2026

The user delegated the best implementation after the three-profile pilot. The workspace now enables free community X research in initial discovery and company-professional research, while retaining native source state and buyer/publication gates. The fixed eight-business sample returned six bios and zero bio emails; current official homepage/contact research yielded five published email candidates across four businesses. No replacement profiles inflated the sample. Full details and limitations are in [the enabled-source audit](docs/FXEMBED_AUTOMATIC_RESEARCH.md).

**893 tests passed in 184.50 seconds**, with one existing warning; 57 focused adapter/discovery/failover checks also passed. Chromium smoke verified initial-discovery community display and the source-enabled banner with zero JavaScript errors. Ruff, Python compilation and JavaScript syntax passed.

The isolated diagnostics preserved the operational database. A separate deliberate, idempotent publication then added/reused eight unqualified company research records and five sourced email-candidate observations for dashboard review, without creating recipients, jobs or messages. The updated normal preview was restarted with FxEmbed enabled and sending disabled/paused. Read-only Chromium inspection verified all eight real research reports, enabled-source status and desktop/mobile layout while preserving the published records; zero provider calls/messages occurred. LinkedIn access, verified buyer contacts and representative/vendor-equivalent coverage remain incomplete.

## Ordinary Firefox LinkedIn control and repo review

A task-owned normal Firefox guest session returned **HTTP 999** for the same previously observed LinkedIn profile denied in Chromium. A local Windows `mozglue` assembly-manifest launch issue was repaired before this actual platform request; the failed first launch is not a native-source result. The reviewed public crawler repositories supplied parsing/session/crawl machinery but no demonstrated working access to this profile. No production engine, native source hold, account state, recipient probe or message changed. The operational database remained unchanged. Diagnostic Ruff/Python compilation passed; the prior production full-suite result remains 893 tests. See [the exact control, primary sources and remaining access gate](docs/LINKEDIN_ACCESS_RECHECK.md).

## LinkedIn-linked current staff contact recovery — 12 October 2026

Implemented a bounded personal-result discovery branch and scoped official staff-email associations. Two known UK architectural-business controls matched exact LinkedIn profile links, named roles and two current published emails; homepage-only variants also recovered the same people through observed navigation. Native LinkedIn snapshots remained robots-denied. Unseeded exact-profile and less restrictive name queries still yielded zero accepted source results with free-engine restrictions. No native access recovery, fresh-discovery acceptance, qualified buyer, mailbox existence or vendor-equivalent coverage is claimed. Operational data stayed unchanged, with zero imports, probes or sends.

The full regression run passed **907 tests in 209.12 seconds**; the final bounded-navigation refinement passed **67 focused checks in 29.27 seconds**. Chromium smoke passed official-person email/source display, preserved native state and script-text escaping with zero JavaScript errors. Ruff/Python compilation/JavaScript syntax and source ZIP integrity passed. The normal preview was restarted with FxEmbed enabled and sending disabled/paused; read-only status/health/assets checks preserved operational data. See [the complete implementation, live provenance and limits](docs/LINKEDIN_PERSON_RECOVERY.md).

## LinkedIn company-URL-free recovery correction — 13 October 2026

The previous zero-result claim for both known controls was partly an implementation problem: negative `-site:` filters were parsed as positive restrictions, and over-constrained queries hid useful company sources. Fixed negative/positive site semantics, minimal-name-first resolution, named-index hint normalization, bounded official people/studio/practice routes, and contact-broker/client-project source exclusions. With company URLs omitted, two known UK professional controls independently resolved company staff pages and two published emails. Native LinkedIn access remains restricted. Four separately discovered profile controls produced no accepted email candidates; two UK rechecks also held. No universal mirror/bypass, qualified buyer, mailbox existence or representative recall is claimed.

**932 tests passed in 219.39 seconds**, with one existing warning. Focused checks, Ruff and compilation passed. A timing-sensitive retry fixture was corrected without relaxing production freshness or cooldown checks. The final preview was restarted and read-only status/health checks confirmed sending disabled/paused, FxEmbed enabled, and operational data unchanged. No contacts were imported, real mailbox probes or messages sent. Source ZIP integrity passed. See [the actual fixes, public-repo research, known-control successes and fresh-sample limits](docs/LINKEDIN_UNSEEDED_RECOVERY.md).

## Fresh founder hints to independent company contacts — 13 October 2026

Implemented unverified employer-guided queries, segmented staff headings, identity-held observations and an independent company-only discovery branch. Four genuinely fresh public-index founder hints were tested across UK coffee and US skincare; none passed exact person/profile acceptance. The follow-up resolved Renoir Coffee and Sonage independently, then current company crawls found two published business-email candidates. Renoir required normal Chromium rendering; its HTTP-only shell capture was not normal-renderer coverage. Both three-page contact runs remained partial. No founder-inbox, native LinkedIn access, mailbox existence or vendor-equivalent coverage claim is made. A public-post URL check produced zero accepted results and a robots-respecting Jina Reader control returned HTTP 409; neither was integrated as a native-source recovery.

**943 tests passed in 221.90 seconds**, with one existing warning; focused checks, Ruff and JavaScript syntax passed. Chromium smoke passed separate company/person source states and escaping with zero JavaScript errors. Operational data remained unchanged with zero recipient imports, probes or messages. See [current source coverage, precise limits and original goal status](docs/FOUNDER_SOURCE_COVERAGE.md).

## Personal X extraction and current LinkedIn recheck — 13 October 2026

Four fresh free-index professional X profiles yielded four literal business-bio
email candidates through the approved community adapter. A separate six-profile
control yielded five bios and seven addresses after fixing explicitly published
at/dot notation; booking-agent and shared contacts are not owner-inbox claims.
Explicit provider website references now remain unverified and visible for
independent research. No qualified buyer or native-profile access is inferred.
See [the measured sample and extraction fix](docs/PERSONAL_X_EMAIL_ACCEPTANCE.md).

The company-URL-free LinkedIn path was rerun with two known names/profile URLs
and empty snippets: both exact official staff/profile matches and two published
emails were recovered again. Native access remains denied; fresh representative
coverage is not established. Two additional no-cookie repository claims proved
to be a PDL wrapper and an Apify service README, not a verified free mirror.
See [the current recheck](docs/LINKEDIN_UNSEEDED_RECOVERY.md).

**87 focused tests passed in 35.86 seconds**; Chromium smoke passed with zero
JavaScript errors. Ruff and JavaScript syntax passed. The earlier full-suite
baseline remains 943 tests; no new full-suite count is claimed without retained
completion output. Preview health/assets and read-only state were checked after
restart; operational data stayed unchanged and sending remains disabled/paused.
Zero contacts imported, recipient probes or messages sent.

## Fresh buyer-role coverage and source-hint corrections — 13 October 2026

Four fixed fresh LinkedIn/X sector-role queries provided two indexed profile rows
and initially one eligible name/profile input, rather than eight planned slots.
No accepted emails or qualified buyers resulted. Free-engine restrictions remain
recorded; country words in education/client descriptions did not approve business
location or buying fit. Normal official-site rendering was retained in the final
run. Corrected a real truncated-employer hint (`Dental Care of Corona`) and
boundary direction marks dropping a named profile hint. The full employer now
finds the observed staff route, but that capture is unavailable. A saved-row live
replay restored the second name hint without establishing person/email acceptance.

91 combined recovery/discovery/community checks passed after the employer fix;
61 person/recovery checks passed after the subsequent boundary-name correction.
These sets overlap. Ruff passed. Operational data stayed unchanged, with zero
imports, probes and messages. See [the actual fixed sample, source limits and
implementation corrections](docs/BUYER_PROFILE_COVERAGE.md).

## Bounded zero-result platform query recovery — 13 October 2026

Generated empty LinkedIn/X profile queries now get at most one paced less
restrictive retry, retaining platform/path, sector and roles. Only trailing
market text and phrase quoting are relaxed; arbitrary operators, successful
queries and recursive retries are excluded. Metadata preserves the original
query. Existing foreign-market exclusions, identity/publication review and
budgets remain in force.

A separate four-query live pass yielded 25 indexed rows and eight selected
profile hints, three available X bios and zero accepted personal emails. The
sample includes company accounts and foreign/unknown market hints, so it is not
eight US/UK buyer leads. One extra official staff-page check had a company inbox
but no exact LinkedIn link; it was not counted as personal acceptance. No contacts,
probes or messages resulted, and operational data stayed unchanged.

**969 full-suite tests passed in 218.48 seconds**, with the existing warning;
109 focused checks and Ruff also passed. The current preview was restarted and
read-only health/status checks confirmed sending disabled/paused and unchanged
operational data. See [the measured discovery improvement and precise coverage
limits](docs/PROFILE_QUERY_RECOVERY.md). The original full goal remains incomplete.

### Resumed founder-source check

A current free founder query returned six rows and two usable named inputs were
processed. Fixed actual first-person contractions being appended to a declared
employer (`Skincare Scientists I’m`). A same-row live replay correctly resolved
the independent Skincare Scientists company domain; person identity and email
acceptance remained held. Fatma's company pages were captured without an exact
staff/profile match. No contacts, probes or messages resulted. 63 focused checks
passed after the fix, with the existing warning; Ruff passed. The earlier 969-test
full suite remains the baseline before this additive follow-up. See the resumed
check in [the query recovery audit](docs/PROFILE_QUERY_RECOVERY.md).

## LinkedIn repository and transport audit — 13 October 2026

Reviewed seven pinned public repositories at source level. Some advertised
anonymous extraction but required a login session or an Apify service token;
HTML parser fixtures did not establish current native access. Independently
tested sparse/complete public document headers, Chrome TLS through curl_cffi,
and Scrapling 0.4.15 with installed Chrome and a fresh guest context. All four
controls returned HTTP 999 for the same known UK profile. These are bounded
local access controls, not representative VPS or new-buyer acceptance tests.

Three diagnostic scripts passed Ruff and compilation. Audit dependencies remain
isolated in `.venv-audit`; production dependencies/settings were not changed.
Operational data and durable holds stayed unchanged; zero imports, recipient
probes or messages occurred, and sending stayed disabled/paused. Corrected the
VPS browser guide: restarting does not clear durable source holds. The previous
969-test full suite and subsequent 63 focused checks remain separately scoped.
See [the pinned repository review, actual controls and recommended multi-source
setup](docs/LINKEDIN_REPO_SOLUTIONS_AUDIT.md). Own-account VPS browser support is
already implemented but authenticated VPS access remains unverified.

## VPS session-method re-verification — 13 October 2026

Added the pending upload/runtime/provider/source/mailbox/AI/backup acceptance
checklist to PLAN.md and docs/VPS_DEPLOYMENT_CHECKLIST.md. Corrected stale plan
claims about template fallback and the implemented optional session transport.

Fixed setup exit on initial browser navigation failure, signal/lock cleanup and
Windows contention handle leakage; excluded dialogs/aria-hidden data from scoped
readers; tightened exact search navigation and malformed-port handling. Browser
setup defaults to LinkedIn only and has a 120-second shutdown grace period. The
optional image now installs the app package for path-invoked deployment scripts.
Preflight also checks managed Chromium/display/profile configuration without
claiming authenticated access. See [the code-level re-audit](docs/PLATFORM_SESSION_REAUDIT.md).

**986 full-suite tests passed in 246.06 seconds**, with one existing Starlette/httpx
deprecation warning. 113 focused session/access/professional/discovery/deployment
checks passed in 33.02 seconds. Ruff, Python compilation, three reader JavaScript
syntax checks and Compose source/volume checks passed. Local preflight confirms
Chromium installation and Docker unavailable; container build/runtime and actual
authenticated VPS LinkedIn search/capture remain pending.

Restarted the normal preview with current code: health and authenticated status
both HTTP 200. Operational tables stayed unchanged; sending disabled, globally
paused, managed browser disabled pending setup, no active jobs. Zero contact
imports, real-recipient probes or external messages occurred. Real Chromium DOM
and synthetic session tests are controlled implementation checks, not live
account/email coverage proof. Rebuilt the source-only verified release.

## Official profile/contact snapshot recovery — 13 October 2026

The previous human turn made concrete progress through setup/lock/image/reader
fixes and passing runtime/source checks. This continuation reran the fixed
four-cohort buyer queries before changing code: two already observed LinkedIn
inputs, zero accepted personal emails and zero qualified buyers; other cohorts
returned no profiles. This is not eight new leads or established buyer coverage.

Found a real extraction gap: substantial official HTML skipped Chromium even
when `crawl_render_mode=always`. Corrected snapshots to honor always/auto/never,
record render attempts/issues and retain HTTP evidence on render failure.
The paired live test then exposed a regression: MLA's rendered staff cards lost
an exact profile/email match present in its current HTTP publication. Fixed this
by preserving independent HTTP/rendered captures and verifying complete scoped
staff records within each version, never combining names/links/emails across
versions. Person records retain their own capture method/hash. Recovery preserves
both versions' observed navigation without guessing routes.

Final paired known-source controls retained one distinct person-email candidate
each for MLA/Adam Frickleton and NORR/Rachel Rogerson, and zero for Dental House/
Stuart Garton. Render issues remained recorded; these are existing controls, not
new buyers or native LinkedIn publication. Diagnostic records and the first
regression result are preserved. See [the evidence and precise scope](docs/OFFICIAL_PROFILE_RENDER_RECOVERY.md).

**998 full-suite tests passed in 254.34 seconds**, with the existing Starlette/httpx
warning; 91 focused snapshot/person/profile-resolution checks passed in 39.43
seconds. Ruff and Python compilation passed. The earlier interim 994-test result
predated the separate-capture fix and is not its final acceptance. A diagnostic
fixture's incorrect fetch-method name was corrected before the final checks.

Normal preview refreshed with current code: health and authenticated status both
HTTP 200, operational tables unchanged and no active jobs. Live sourcing made zero
contact imports, real-recipient probes or external messages. Sending stays
disabled/paused. Native access, authenticated VPS behavior and consistent fresh
US/UK buyer-email coverage remain unproven; the full goal is not marked complete.

## Fresh architecture sample and recovery query budget — 13 October 2026

Two fixed free UK/US architecture-role queries returned seven rows each and four
selected person hints, frozen before contact resolution. All four stayed personally
unconfirmed with zero accepted personal emails/qualified buyers. Legacy Twitter
queries also returned zero accepted roots. No replacement profiles, fabricated
addresses or company inbox substitutions were counted as personal coverage.

Corrected an actual homonym-research inefficiency: an unrelated staff frontier
could use all four leaf requests before a second identity query. Each query now
gets a two-page initial batch, with the same total four-page cap and a final
pending-navigation pass. Added bounded unverified role/department/employer
headline hints; the live Mark McIntosh row now retains AECOM. Exact current
staff/profile/name/role/company checks remain unchanged.

The four original rows were replayed, preserving the original reports. David's
second identity query now executed while the four-leaf cap held; all accepted
personal-email counts remained zero. Read-only search configuration showed
configured Mojeek absent; recorded that actual engine availability must be
verified during deployment. Rotated only the local search session-signing key
and restarted the verified original local launcher without exposing its replacement.
See [the frozen sample, correction and verification limits](docs/HOMONYM_SOURCE_RECOVERY.md).

**1008 full-suite tests passed in 266.01 seconds**, with the existing warning.
129 focused person/recovery/index/profile-resolution checks passed in 47.13
seconds; Ruff and Python compilation passed. Live diagnostics retained unchanged
operational tables, zero recipient probes/imports/messages and sending disabled/
paused. Authenticated VPS behavior, native personal-profile availability and
representative new-buyer coverage remain unproven; the full goal remains active.

The current normal preview was refreshed: health and authenticated status both
HTTP 200, operational tables unchanged, no active jobs and sending disabled/
paused. The verified local search backend's `/config` also returned HTTP 200
with six enabled general engines. The source-only release and SHA-256 checksum
were rebuilt after final documentation.

## Core website/professional publication integration — 13 October 2026

The previous goal turn improved identity-query budgeting and yielded fixed-sample
evidence. This continuation found that snapshot-only HTTP preservation had not
reached the main website crawler: rendering still replaced the original extraction.
Actual one-page `research_lead` on the known MLA team page saved one generic inbox
and zero named contacts before the correction.

The main and contact-recovery crawlers now retain additional same-URL public HTTP
contact/person evidence alongside rendered capture. Complete scoped person records
stay independent; conflicting people on a shared address clear individual identity,
including an earlier inferred name on a still-new contact. The saved evidence
digest commits both original hashes, so withdrawing an HTTP-only email cannot
reuse old proof against an unchanged DOM. HTTP text is explicitly labelled as
publication, not rendered visibility. Other-domain ownership and outreach gates
remain unchanged.

After the correction, the real known-source pipeline saved **72 isolated published
address records, five named**, with 72 current saved-publication checks passing.
Automatic professional research consumed the saved crawl/hash, made zero index
queries with its one-profile diagnostic budget, and exposed five distinct official
named email candidates while the native capture stayed held. One company/control
is not 72 clients, confirmed employees, safe mailboxes or representative fresh
US/UK coverage. Both website runs remained partial. The 72 isolated verification
jobs were queued but never executed; operational imports, real probes and external
messages stayed zero. See [the actual integration audit](docs/CORE_PUBLICATION_RECOVERY.md).

**1016 full-suite tests passed in 267.15 seconds**, with the existing Starlette/httpx
warning. 143 focused crawler/person/publication/professional/failover checks passed
in 61.63 seconds. Real Chromium tests cover saved publication proof, automatic
professional lookup, shared-address identity clearing and source withdrawal. Ruff
and Python compilation passed. Native access, broader fresh buyer recall and
authenticated VPS acceptance remain unproven; the full goal is not marked complete.

The normal preview was refreshed with current core extraction code: health and
authenticated status both HTTP 200, operational tables unchanged, no active jobs
and sending disabled/paused. The source-only release/checksum was rebuilt.

## VPS upload plan and session re-verification — 14 October 2026

The VPS checklist and PLAN now retain pending installation/upload/checksum,
server-local configuration, TLS/internal networking, SearXNG/Reacher contracts,
server-owned browser login, session restart/expiry, AI/mailbox acceptance,
resource measurement, private backups and paused restore tasks.

Timed-out navigation to a same-platform login/checkpoint/authwall now creates a
durable login hold; subsequent search calls stop without launching another
browser. Search startup/profile-lock failures return explicit source errors
without printing exception text. Direct setup CLI defaults to LinkedIn only.
Tests reject lookalike/cross-platform redirects and unrelated route prefixes.

The staff parser's segmented-heading variable collision and false CEO match
inside Arceo were fixed. Saved real capture replay found three IF_DO names and
four Studio Architecture names, with zero named email publications in those
scopes and zero network calls. This is saved-evidence parser verification, not
current native-platform access or a fresh lead-coverage claim.

**1061 complete-suite tests passed in 251.18 seconds**, with the existing
Starlette/httpx warning. The focused browser/setup/access/professional/discovery/
deployment/person run passed 175 tests in 36.99 seconds before the final CLI
regression; all five setup tests also passed separately. Ruff and Python
compilation passed. Local Chromium fixture/synthetic-session checks are distinct
from authenticated account acceptance; Docker runtime remains unverified here.

The normal preview was restarted and checked read-only: health/status HTTP 200,
operational database unchanged, no active jobs, sending disabled/paused and
managed mode disabled pending actual server setup. No account login, recipient
probe or message was performed. See [the session audit](docs/PLATFORM_SESSION_REAUDIT.md)
and [the pending deployment checklist](docs/VPS_DEPLOYMENT_CHECKLIST.md).

## Bounded contact-navigation recovery — 14 October 2026

One reproduced extraction-path gap was corrected: HTTP-only contact/team/about/
staff navigation survived rendering only if the source also added email/person
data. An email-free homepage could therefore lose its actual contact routes.
The shared source-preservation helper now retains explicitly published same-company
contact routes, records them in crawler reports and commits both document hashes.
Routing/robots, depth/page budgets, retries and source/recipient gates remain active.

Before the fix, the capture regression and real Chromium pipeline test both failed.
Afterward, the same controlled three-page/no-sitemap run saved three pages and two
published unverified contacts, compared with one homepage and zero contacts before.
A robots-denied contact route was not fetched; only the permitted staff-page contact
was saved. These are intercepted fictional documents in isolated databases, not a
live client sample. Link discovery alone creates no email contact.

**1073 tests passed in 333.65 seconds**, with the existing Starlette/httpx warning.
The focused navigation/publication/resume/optimization set passed 52 tests in
38.65 seconds; twelve new cases cover loss, withdrawal, scope, excluded routes,
actual page publication and robots behavior. Ruff and Python compilation passed.

The updated preview passed health/authenticated status HTTP 200. Operational data
was unchanged, no active jobs remained and sending stayed disabled/paused. No real
recipient probe, message or account login occurred. The bounded change and its
limits are documented in [the navigation audit](docs/CONTACT_NAVIGATION_RECOVERY.md).

## Agreed pre-VPS LinkedIn/X improvements — 14 October 2026

Managed search now uses bounded snapshots, normal wheel input and scoped Next
buttons, deduplicates URL identities and preserves already seen virtualized cards.
Query/platform/type identity stays fixed while page numbers may change. Requested
limits, six default steps, three pages and the capture-loop deadline stop work;
two no-new-result rounds stop stalled search. Denials/authentication transitions
retain partial candidate rows with explicit issues and stop further actions.
Coverage counters/stop reasons are saved and shown in Recent search runs.

FxEmbed caches and provider cooldown/pacing now persist in the private runtime
source cache. Restart never renews retrieval timestamps or turns mirror hints
into first-party evidence. TTL expiry, negative cache, cross-handle HTTP/body 429
holds, Retry-After, bounded entries and corrupt storage are tested. Unreadable
storage fails with a source error rather than forgetting a saved cooldown.

**1096 tests passed in 289.74 seconds**, with the existing Starlette/httpx warning.
The focused browser/search/cache/provider/deployment run passed 175 cases in
52.00 seconds. Twenty-three new cases include actual Chromium controlled search
UI and desktop/mobile coverage rendering. A controlled deadline double tests
partial-row cleanup; provider responses are mocked. No live account or additional
platform acquisition was used. Ruff, Python compilation and all three changed
JavaScript syntax checks passed.

The corrected normal preview passed health/authenticated status HTTP 200 after
restart. Operational data was unchanged, no active jobs remained and sending
was disabled/paused. Managed mode is still disabled pending the user's server
login. The source release includes the implementation and updated VPS acceptance
checklist. See [the scoped platform audit](docs/PRE_VPS_PLATFORM_UPDATES.md).
