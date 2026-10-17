# VPS-owned browser session re-audit — 13 October 2026

Requested scope: recheck the implemented LinkedIn login/session transport, correct
bugs and add the remaining server deployment tasks. This is local implementation
verification; no actual account was logged in and no VPS was configured.

## Corrections

1. Initial setup navigation failures previously exited the entire setup context.
   Bounded Playwright timeouts/errors now preserve the human browser window for
   inspection. A failure on one platform no longer discards another platform's
   login. Stop signals prevent opening the next login tab; exceptions print only
   their type, not sensitive URLs/token text.
2. Setup restores previous signal handlers and releases its OS lock on normal
   shutdown and browser-launch failure. The Windows lock branch now closes its
   failed file handle and raises the same clear contention error as Linux.
3. Visible contact dialogs/overlays and aria-hidden descendants are excluded from
   scoped professional/company/search readers. HTTP professional parsing also
   excludes dialogs. Published business bio/normal mailto evidence remains usable;
   protected contact overlays are not a data source.
4. Browser routing aborts malformed ports and uses the exact supported company
   search route rather than allowing arbitrary suffix routes. Existing private
   and off-platform navigation blocks remain in force.
5. The optional browser Docker image now installs the application package, as the
   normal image already did. Path-invoked preflight/backup scripts otherwise lacked
   the package import support in that image. Container execution remains pending.
6. Temporary setup defaults to LinkedIn only; `PLATFORM_BROWSER_SETUP_SITE=x|both`
   is explicit. Setup gets a 120-second stop grace period for orderly browser
   shutdown. Approved FxEmbed research does not require X browser login.
7. Preflight checks Chromium when managed browser mode is enabled even if website
   rendering is disabled. It reports display/profile configuration separately from
   authentication, without exposing secrets or treating directory presence as login.
8. PLAN.md now reflects current research-based AI email writing without template
   fallback and distinguishes optional session support from confirmed access.
   The new VPS checklist includes installation, TLS/provider/source acceptance,
   mailbox/AI setup, resource measurement, off-host backups and paused restore.

## Verification

- Initial browser/access/professional/discovery baseline: 92 tests passed.
- After corrections, browser/setup/access/professional/discovery/deployment checks:
  **113 passed in 33.02 seconds**, with the existing Starlette/httpx warning.
- Real local Chromium checks cover scoped fictional DOM extraction and persistent
  synthetic session restart. Setup shutdown/launch failures use controlled runtime
  doubles; these are not live account sessions or a source-coverage benchmark.
- Ruff, Python compilation, three reader JavaScript syntax checks and Compose
  source/volume checks passed. Read-only preflight confirms installed local
  Chromium and records Docker unavailable on this workstation.

- Complete suite: **986 passed in 246.06 seconds**, with the same existing warning.
- Normal preview refreshed with current code: health/authenticated status HTTP
  200, operational tables unchanged, no active jobs, sending disabled/paused and
  managed mode still disabled pending actual setup. Source release rebuilt with
  ZIP integrity verification. Details are retained in VALIDATION.md.

## Pending deployment evidence

The Linux container build/display/noVNC/sandbox runtime, legitimate account login,
session survival on the user's VPS, account-specific company search/professional
capture and fresh US/UK person-email coverage are not established here. Existing
guest-source HTTP 999 failures have not been claimed fixed by these changes.
See [the actionable VPS checklist](VPS_DEPLOYMENT_CHECKLIST.md) and
[session configuration](PLATFORM_BROWSER.md).

The preview remains sending disabled/paused. No real-recipient probes, external
messages, copied desktop sessions or account actions were performed for this audit.

## Follow-up session and parsing check — 13 October 2026

The upload plan/checklist now includes explicit cold-restart, expired-session and
profile-lock acceptance. Direct CLI setup defaults to LinkedIn, matching the
container setup; X/both must be selected explicitly.

An additional failure path was corrected: if navigation times out after reaching
an actual same-platform checkpoint/login/authwall, it now records a durable login
hold. It cannot be reported as ordinary unavailable/empty research and repeatedly
relaunched by later queued searches. Other navigation/startup/lock failures in
company discovery return an explicit source error, with only the exception type;
they do not expose exception text or falsely establish an account restriction.
Known HTTP denials retain their earlier response-metadata precedence. The helper
rejects lookalike domains, unrelated route prefixes and cross-platform redirects.

The official staff parser also had a heading-variable collision that crashed
segmented-name pages, and role substrings incorrectly identified Arceo as CEO.
The URL/heading variables are now separate and role matching uses word boundaries.
Existing bold-name staff blocks preserve their own profile/publication links and
do not borrow general footer addresses. Replaying the two previously saved real
rendered captures recovered three IF_DO names and four Studio Architecture names,
with zero named email publications in those scopes. This replay made no network
request and proves neither current native LinkedIn access nor fresh email coverage.
The result is retained in `data/session-parser-recheck-20261013.json` locally.

Focused browser/setup/access/professional/discovery/deployment/person checks:
**175 passed in 36.99 seconds** before the additional CLI-default regression.
Ruff and Python compilation passed. The complete current suite is recorded in
VALIDATION.md after completion; earlier test totals in this document remain
historical. Actual VPS/container/account acceptance remains pending as listed
above; no real account was used for these local checks.

## Completed handover check — 14 October 2026

The complete current suite passed **1061 tests in 251.18 seconds**, with the
existing Starlette/httpx deprecation warning. The direct CLI setup regressions
also passed separately (five cases). The normal preview was restarted using
the corrected source. Health and authenticated status both returned HTTP 200;
the operational database fingerprint was unchanged, there were no active jobs,
and sending remained disabled/paused. Managed browser mode remains disabled
until the user's server-owned login setup. No recipient probes or messages
were performed. The source release includes the updated plan/checklist and
this audit; server/account/container acceptance is still pending.
