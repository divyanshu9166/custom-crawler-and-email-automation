# Workflow map and workspace settings

## AI email writer — 11 October 2026

Settings now includes API base URL, model, private API key and request timeout. Blank key preserves a saved key; explicit removal clears it. Saving pauses sending and calls no provider. Pipeline labels old template drafts and blocks their approval; the workflow map shows the hold. The actual writer requires current reviewed sources and has no template fallback. Read [the verification and live-model boundary](AI_EMAIL_WRITING.md).

## Previous execution visibility update — 11 October 2026

Full regression suite: **581 passed**, zero failures, one existing Starlette/httpx deprecation warning, 128.33 seconds. Ruff checks passed. Live browser proof is saved locally under `data/workflow-visibility-ui-check.json`; suite results are under `data/workflow-visibility-tests.xml`. These checks do not change the separately documented acquisition/deployment acceptance limits.

The **Running now** panel reports durable running/queued jobs and SMTP submissions separately from **Recommended next step**. Pending work is not described as running. All active jobs contribute to counts even if they are older than the latest 100 completed jobs; the panel shows up to 12 active jobs. Selecting one prospect scopes lead jobs, contact verification and SMTP activity to that business. Global discovery remains under All prospects. Worker heartbeat freshness is displayed separately; a recorded running job with a stale heartbeat needs inspection. Inbox monitoring and recurring search scheduling are separate background functions.

**Saved research data** displays prospect, current page, stored contact and operator-qualified prospect counts in all three map views. Open prospect data goes directly to the selected business in Pipeline, where captured page text, email sources, verification and crawl reports can be inspected. Counts do not establish buyer fit, mailbox safety or crawl completeness. **Review gates and blockers** lists the displayed map's pending review/failed/blocked nodes and opens their inspector. A last-update timestamp accompanies successful refreshes; failed updates explicitly mark displayed data as possibly outdated.

Six activity regression tests cover true execution versus review recommendations, correct prospect/contact scope, old active jobs, count/display limits, independent SMTP activity and stale/disabled worker freshness. Read-only Chromium checks verified all 17/11/35-node maps, selected-data navigation, blocker navigation, desktop/mobile layouts, escaped job labels and simulated activity/refresh failures. No operational records changed or outreach was sent. Screenshots: [desktop](screenshots/workflow-visibility-desktop.png), [mobile](screenshots/workflow-visibility-mobile.png). Older release counts below are historical.

Earlier feature release: **288 tests passed**, zero failures, one existing warning, 93.47 seconds. Explainable prospect priorities, exact separate-currency cost/receipt reporting with correction history, and permission-reviewed post-delivery maintenance/expansion/case-study plans are implemented. Full Chromium checks actual forms and desktop/mobile navigation with zero JavaScript errors; normal-server read-only checks preserve all existing operational records and credentials. Calls, payments, agreement, client delivery and publication remain operator-recorded. See [feature details](PRIORITY_FINANCE_AFTERCARE.md) and [current proof](growth-feature-check.json). Older validation sections below are historical.

Open the local dashboard at http://localhost:8000 and refresh an existing tab after updating the source. Sign in with your existing account. Workflow is the default view; Pipeline, Find prospects, Operations and Settings remain available in the sidebar.

## Connected execution map

The Map selector now offers **Overview (11 stages)** and **Full workflow (35 nodes / 46 connections)**. The detailed view matches every node and connection in WORKFLOW.md, including the direct CSV branch, profile website lookup, held candidates, verification, four touches and R–Z sales process. Each detailed node shows its saved status and execution mode (automatic, review or operator-recorded). Inspect stage and Focus next bring a node into view; its inspector shows possible conditional routes and opens the appropriate prospect, operations, email settings or Learning view.

The detailed API is authenticated and read-only: `/api/workflow?detail=true&lead_id=…`. It uses one consistent database read transaction. Canvas counts do not load every saved page body. Inactive campaign/profile/website branches are identified separately from waiting steps. Optional screenshot/lab failure does not falsely mark the crawler failed, and historical images cannot complete a newer audit. Partial desktop/mobile evidence stays under review. Missing agreement/payment/acceptance references cannot become completed merely because a sales stage says completed. Open promised-value tasks keep reply review pending.

Desktop/mobile Chromium checks cover the new selector, detailed graph, stage inspector, branch state, learning action and return to overview. Mobile details sit below the canvas without obscuring it. The full map is larger than the viewport: use Fit view for the whole graph, or select a stage / Focus next to read it at a useful zoom. Existing overview dragging/zooming and separate browser layout storage remain available.

The map shows eleven stages from discovery through website/profile research, published contacts, qualification, verification, four drafts, approval, sending, replies and the recorded client journey. Select all prospects or one business. Click a node for its counts, explanations and available action. The next-action card recommends the pending stage, prioritizing running/queued jobs and required review. Active views refresh every ten seconds.

Status labels reflect saved application data: complete, running/queued, needs review, blocked/failed, waiting or paused. Research complete means its job finished; coverage can still be partial. Read the node details and research report before treating it as sufficient evidence. A completed discovery stage does not establish buyer fit. Verification safe is counted only when fresh and eligible; SMTP acceptance is not an inbox delivery claim.

Drag nodes or the background, use zoom and Fit view, or reset the layout. Arrow keys also move a selected node. Layout changes persist locally in that browser. This is a live execution map with layout controls; it does not support adding arbitrary executable nodes or rewriting the pipeline by connecting edges. Existing research, source review and approval rules still determine execution.

## Email settings

Settings contains business/sender identity, SMTP with STARTTLS or implicit TLS, IMAP TLS, sending limits and the prospect-local send window. The domain-authentication checkbox records your confirmation; the application does not provision or independently check DNS authentication here.

Saving persists changes and pauses sending. It does not validate the provider connection or turn on `SENDING_ENABLED`. Configuration readiness is not deliverability evidence. A live mailbox operation or in-flight send prevents a conflicting save until it finishes. Inbox catch-up must happen again after settings change. The worker can use saved mailbox settings for subsequent normal polling; saving is not an outbound mail test.

Password fields stay blank after loading/saving. Blank means keep the saved password; the explicit removal checkbox clears it. Responses and validation failures do not return mailbox passwords. Do not enter production credentials into the fictional offline demo.

## Sign-in settings

Under Change sign-in details, enter the username, current password and a matching new password of at least sixteen characters. Saving requires the current password, stores a salted PBKDF2 hash and invalidates existing browser sessions. Sign in again with the new credentials. API Bearer tokens are independent and are not rotated by this form.

Initial credentials come from `.env`. Saved values override their matching `.env` fields on subsequent application startups. Changing the old `.env` password does not override a managed password hash.

## Persistence and backup

The private file `<DATA_DIR>/workspace-settings.json` contains saved field overrides, the sign-in password hash, session version and any configured mailbox passwords. Mailbox passwords are private stored configuration, **not encrypted storage**. Keep this file, `.env` and the database under appropriate host access controls; Windows requires folder ACLs. Back up the private settings file alongside `.env` and the database separately. The SQLite backup script backs up the database only. The source release intentionally excludes all runtime settings, databases and credentials.

## Latest full-map verification

**264 tests passed, one existing deprecation warning, 81.92 seconds.** Eleven new detailed-map tests cover every documented node/edge, authenticated/scoped read-only access, no database mutation, partial/current audit evidence, inactive branches, cross-company approval, suppression/stale monitoring/uncertain submission, missing sales references, genuine recorded outcomes and open promised-value tasks. Actual Chromium verified full/overview switching, desktop/mobile stage inspection, conditional actions, learning navigation and a mobile inspector below the canvas, with zero JavaScript errors. See `detailed-workflow-check.json` and the current node audit. Real credentials and operational message/approval counts were unchanged.

## Earlier verification on 10 October 2026

Subsequent [every-node audit](EVERY_NODE_AUDIT.md): 230 tests passed in 78.06 seconds. Six reproduced map-status defects were corrected: cross-prospect approval readiness, approval inferred from a manual reply, hidden terminal research failure, suppression counted as fresh safe, stale inbox shown as running, and completed sales shown as unfinished. New research without a queued job is ready; partially qualified aggregates are not complete. The eleven UI nodes remain grouped summaries of the detailed thirty-five-node diagram.

The full suite passed 224 tests in 99.72 seconds, with one existing Starlette/httpx deprecation warning. Actual Chromium checked node selection, drag/zoom, per-prospect state, desktop/mobile layouts, persisted fictional mailbox settings, credential change, session termination and fresh login with zero JavaScript errors. Normal-server inspection also confirmed eleven nodes, visible settings, blank secrets and no mobile overflow without changing the user's credentials or mailbox. See `ui-workspace-check.json` and the fictional screenshots in `screenshots/`.

VPS deployment, real provider verification, mailbox connections and live delivery acceptance remain pending; this UI verification does not establish those results.
