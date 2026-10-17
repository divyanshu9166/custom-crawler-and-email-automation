# VPS browser discovery without developer API keys

This opt-in mode runs the existing discovery/research jobs through a dedicated persistent Chromium profile on the VPS. It navigates normal LinkedIn company search/About pages and X public-profile search/header pages, reads visible business fields, and sends linked official websites directly into the existing crawler. No browser extension, CSV export/import, LinkedIn/X developer API key, paid scraper or publication API is required for this mode.

This is a browser UI transport, not unrestricted access. The websites make their normal frontend requests. There is no spoofed fingerprint, proxy rotation, hidden API-data extraction, cookie cloning, login automation, CAPTCHA solving, private messaging or account action. Login/challenges, access denial and 429 responses hold that platform for operator attention. Normal profile-page access and account/site rules still apply. Unpublished emails are not available through this mechanism.

## Configure on the VPS

Domain, VPS and mailbox credentials remain user-configured. These steps prepare a **new VPS-owned** session; do not copy a desktop Chrome profile or paste cookies/tokens into the app.

1. Deploy the normal source release and create/configure `.env` as usual. Keep `SENDING_ENABLED=false`. Set a unique eight-character `PLATFORM_BROWSER_VIEW_PASSWORD` locally. It protects the temporary VNC viewer inside an SSH tunnel; do not place it in a URL or chat. `PLATFORM_BROWSER_SETUP_SITE=linkedin` now opens LinkedIn only by default; choose `x` or `both` explicitly if needed. Use a legitimate own-account session.
2. Stop the app while signing in, so two Chromium processes cannot use the profile:

   ```sh
   docker compose stop app
   docker compose --profile browser-setup run --rm --build --service-ports browser-setup
   ```

3. From your computer, create an SSH tunnel to the VPS:

   ```sh
   ssh -L 6080:127.0.0.1:6080 your-user@your-vps
   ```

   Open `http://127.0.0.1:6080/vnc.html` locally and enter the viewer password. Sign in to LinkedIn/X directly in the VPS browser if needed, including any normal user verification. The setup program opens only their normal sign-in pages and never reads or submits credentials. When finished, stop the setup container with Ctrl+C; it closes Chromium gracefully to retain the session.

   An initial navigation timeout/transport error now keeps the setup browser open
   for human inspection instead of discarding the session. It does not establish
   access or automatically retry a denied platform. Setup also restores signal
   handlers and releases the OS profile lock on exit or launch failure.

4. Start the server worker with the browser overlay:

   ```sh
   docker compose -f compose.yaml -f compose.platform-browser.yaml up -d --build app
   ```

   The overlay enables `PLATFORM_BROWSER_ENABLED=true` and headed Chromium in a private virtual display. The app and setup use the same Playwright version, UID and `app_data:/data` volume. The GUI setup port is host-loopback only and is not published by the running app. No debug/browser-control port is exposed.

5. Use the existing **Find prospects → Start research** form or recurring search schedule. Managed mode searches LinkedIn companies and X profiles in the background, then resolves visible website links and queues normal website research. By default, `PLATFORM_BROWSER_PUBLIC_FALLBACK=true` also enables free SearXNG discovery and independent company matching when the browser is held or has no website field. Set it false only for browser-only discovery. Existing workflow/job/evidence screens show actual progress; Find prospects shows recorded source coverage and platform holds. See [public-source failover](SOURCE_FAILOVER.md).

6. If a platform is held for login/challenge/denial, inspect the saved reason. Use the same stop/setup/restart process for legitimate sign-in recovery. **Restart does not clear durable access holds.** After resolving the actual cause, clear only that platform's hold using the same app/data volume:

   ```sh
   docker compose -f compose.yaml -f compose.platform-browser.yaml exec app python scripts/manage_platform_browser.py --clear-hold linkedin.com
   ```

   Use `x.com` instead for an X hold. Clearing a hold only permits the next normal source check; it does not establish access, schedule research or enable sending. A renewed denial/login/challenge records a new hold. See [current durable recovery behavior](PLATFORM_ACCESS_RECOVERY.md).

   A timeout after reaching the same platform's login/checkpoint/authwall also
   records a durable login hold without treating its document as contact evidence.
   Browser startup/profile-lock failures are diagnostic source errors. The direct
   setup CLI defaults to LinkedIn only, matching the container setup.

The persistent profile resides under `/data/platform-browser/profile`. It is sensitive local browser state, excluded from release ZIPs. Setup and worker share an OS file lock; browser operations inside the worker are serialized. Browser subprocesses receive only the existing environment allowlist plus display authentication, not mailbox/API credentials from `.env`.

The browser image installs the application package as well as dependencies, so
deployment scripts such as preflight/backup can import it when invoked by path.
Preflight now reports managed mode, display/profile presence and browser installation
even if website rendering is disabled. It never reports authentication from these
configuration checks. See [the complete pending VPS checklist](VPS_DEPLOYMENT_CHECKLIST.md).

## Reader diagnostics

The company reader now supports the h2/Overview and p/div label-value rows
observed on the VPS on 17 October 2026, alongside the existing h1/dl format.
It scopes modern rows between Overview and the next visible peer heading,
requires a preceding company heading and at least two recognised fields with
Website or Industry, and rejects conflicting duplicate fields. Hashed CSS class
names are not selectors. Account/follower context, posts, later Locations/career
sections, hidden elements and contact dialogs are excluded. This compatibility
change needs a fresh real-page check; fixtures alone do not establish live capture.
The focused regression run passed 81 cases; an additional real-Chromium fixture
verified modern-layout website/email extraction through the existing snapshot
source filters. Ruff and reader syntax checks passed. No authenticated VPS
capture or sending is claimed by these local checks.

### Diagnosing an empty company reader

`fields_not_ready` means the reader did not find a supported, unambiguous visible
company layout. The legacy path requires its heading/About link/definition list;
the modern path requires its heading/Overview and label-value rows. It is neither a
successful capture nor a proven LinkedIn denial. Keep Worker and Sending OFF
and inspect only structural metadata with the bounded diagnostic:

```sh
git pull --ff-only
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml exec -T app xvfb-run -a python - < scripts/check_platform_browser.py
```

The host supplies the script on stdin, so this diagnostic also works before
rebuilding an older app image. It uses the installed reader and browser module,
the persistent profile and a temporary private virtual display. Output includes
visible heading/definition-list counts, bounded main-content heading labels,
company navigation paths without queries, field-marker tag/classes and failed
request counts by host. These explain missing selectors or incomplete loading
without interpreting an arbitrary heading as a company identity. It does not print
account navigation, page bodies, cookie values or hidden framework data. A
non-captured result exits with status 2 and remains unverified. Authentication
challenges and HTTP denials stop inspection and preserve normal platform holds.

To test the trusted repository's updated reader with the existing container,
without changing the running app or rebuilding first:

```sh
git pull --ff-only
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml exec -T app xvfb-run -a python - --reader-base64 "$(base64 -w0 outreach/static/platform-reader.js)" < scripts/check_platform_browser.py
```

The report identifies `reader_source: supplied` and, on capture, the reader
layout. Only use the repository reader you reviewed for this option: it executes
the supplied DOM reader in your browser session. A successful preview does not
update the app image; build and start app with both Compose files to deploy it.

If Chromium instead reports a profile in use on a former setup-container host,
stop the app and verify that no container using its profile volume is running.
Only then recover the three Chromium SingletonLock/SingletonCookie/SingletonSocket
entries while holding the application's session lock. Preserve the profile,
cookies and `session.lock` file. Never automatically delete these entries while
a live browser may own the profile. A recovered launch is a separate check from
successful page-field extraction or authenticated access.

## Data and qualification

LinkedIn `/in/` professional roots are supported through the separate [professional-source workflow](PROFESSIONAL_CONTACTS.md), associated with an existing company. They remain rejected by the business/company-profile importer. Its scoped reader excludes protected contact-info overlays and requires independent current-company/person review before recipient import.

LinkedIn reads company heading, current About navigation and public Overview/definition fields such as website, industry, headquarters, phone and published business email. It ignores account navigation, member-profile routes, employee lists and private messages. X reads its scoped public profile header/bio; timeline content and private routes are not read. An opaque short-link label remains a website candidate until current company research corroborates it.

Source records use `managed_browser_public_profile` and `visible_business_fields` with capture time and text hash. Business identity, geography, buyer relevance and mailbox existence remain unverified. Public profile emails are candidate evidence; the adapter does not create verified contacts or send/probe email. Existing source/ownership/country/offer review and Reacher gates remain required. With failover disabled, a missing website field is `website_link_not_observed`; with failover enabled, independent search reports its actual match/coverage outcome. Neither observation confirms website absence; a profile-only prospect cannot pass website-absence review from a missing field alone.

Search results are read only from rendered LinkedIn company-result cards or X UserCell cards, with bounded readiness waits and deduplication. Account shortcuts and timeline/post links are excluded. Results remain unqualified candidates, including possible non-business X accounts. Their current source evidence and independent website research must establish target fit. Search country hints are not verified geography. Public-profile capture only occurs on explicitly supported routes; redirects into private/account/employee routes and off-platform documents are blocked.

## Verification boundaries

Local tests exercise real Chromium DOM parsing with fully intercepted fictional business pages, persistent synthetic session restart, normal queue integration without search/publication APIs, About-source identity, challenge/denial holds, private/off-platform route rejection and loopback setup configuration. The previously observed live Fonte/Sonria layouts informed the reader. This is not a successful deployment or authenticated LinkedIn/X acceptance test on the user's VPS. Docker is unavailable in the current environment; the GUI container, Linux display and account-specific behavior require deployment verification. Source/code tests cannot prove stable prospect recall, platform restrictions disappearing or private-email availability.

On 12 October 2026, the complete suite passed **744 tests**, including **24 browser-mode cases**. Ruff, Python compilation, both JavaScript reader syntax checks and the Chromium dashboard smoke test passed. The smoke test also exercised a simulated enabled-mode/login-hold banner; it did not create a real platform session. The normal development preview was restarted and checked read-only: sending disabled and paused, managed mode disabled until session setup, no active jobs or enabled recurring schedules. The separate normal-preview UI check preserved operational rows/settings and made zero provider calls or external sends. One existing Starlette/httpx deprecation warning remains. Container build/runtime and actual authenticated VPS discovery are pending.

Subsequent [ordinary anonymous-browser audit](PUBLIC_TRANSPORT_AUDIT.md): LinkedIn returned HTTP 999 and X HTTP 403. These statuses now survive navigation errors and are retained in professional captures/reports. This is failure-path verification on the local host, not live profile-email acquisition or authenticated VPS acceptance. Latest full-suite results are in VALIDATION.md; earlier counts above remain historical.

The [access diagnosis and recovery audit](PLATFORM_ACCESS_RECOVERY.md) compares ordinary networking against the managed allowlist, persists platform holds across restarts, honors 429 retry intervals, and verifies known-company public-source recovery while platform access remains denied. See that audit for the explicit per-platform clear command; restarting alone no longer clears a denial.
