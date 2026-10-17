# VPS deployment and acceptance checklist

Updated 17 October 2026. These are pending server/operator acceptance tasks, not
completed local deployment claims. The domain, VPS and mailbox remain user-owned.
Keep sending disabled throughout installation and source research verification.

For GitHub clone/setup commands on the 4 GB host with an existing n8n installation,
start with [VPS_DEPLOYMENT_COMMANDS.md](VPS_DEPLOYMENT_COMMANDS.md). It stages
startup with workers disabled until available memory and active n8n consumption
are inspected, and does not start a second n8n instance.

## 1. Prepare and upload

- Record OS, CPU/RAM, disk space, Docker/Compose versions and kernel sandbox
  support. Start with one app process and `CRAWL_CONCURRENCY=1` on 4 GB/2 cores;
  actual performance must be measured. n8n is optional, not required for this plan.
- Upload the current `dist/outreach-workbench.zip` source release and verify a
  locally computed SHA-256 against the received archive. The ZIP excludes actual
  configuration, browser state, database and live evidence.
- Extract into a dedicated project directory. Create the server-local `.env`
  with `python3 scripts/init_env.py` only if absent, then edit it privately.
  Do not run initialization over an existing configuration.
- If migrating existing work, transfer a consistent DB plus evidence/screenshots
  and `workspace-settings.json` deliberately into the persistent volume with
  ownership UID 10001. The source release alone does not migrate live data.
  Check managed settings, which override matching `.env` values.
- Set `PUBLIC_URL=https://your-hostname`, dashboard login credentials and provider
  secrets. Keep `SENDING_ENABLED=false`; verify the dashboard reports paused.

## 2. Build, networking and normal startup

From the extracted project directory:

```sh
docker compose --profile verify --profile search config --quiet
docker compose --profile verify --profile search up -d --build app reacher searxng
docker compose ps
docker stats --no-stream
docker compose exec app python scripts/preflight.py
docker compose exec app python scripts/preflight.py --network
```

- Configure hostname DNS and HTTPS reverse proxy using `deploy/Caddyfile.example`.
  Verify authenticated sign-in, Settings updates and public unsubscribe link origin.
- Keep 8000 bound to loopback and Reacher/SearXNG on the internal network. Temporary
  browser setup uses loopback 6080 through SSH, not a public VNC endpoint.
- Confirm app volume permissions, Chromium sandbox startup, installed browser,
  worker heartbeat and error logs. `/health` is liveness, not source/provider proof.
- Verify actual SearXNG JSON search and error/engine coverage. Preflight's Reacher
  contract uses a malformed non-recipient, not a live mailbox. Verify the pinned
  `/v0/check_email` endpoint/header secret and provider-permitted outbound TCP/25.
  Actual safe/risky results require separately selected sourced-contact checks;
  TCP connectivity and HTTP 200 do not prove mailbox existence.
- Inspect SearXNG `/config` for actual enabled general engines and compare with
  `SEARCH_FALLBACK_ENGINES`. Unsupported/private/missing engine names may be
  ignored by the search backend; configured names are not successful coverage.
- Rust image builds may need a larger build host; transfer a verified image when
  the VPS cannot build it. Measure runtime separately from build memory.

## 3. Optional VPS-owned LinkedIn session

This mode is implemented; authenticated VPS access is still unverified. Use a
legitimate own-account session. Login is not a guarantee of allowed automation,
profile access or email availability. Protected contact overlays are excluded.

- Set a unique eight-character `PLATFORM_BROWSER_VIEW_PASSWORD` locally and
  `PLATFORM_BROWSER_SETUP_SITE=linkedin`. Use `x` or `both` only if X browser
  login is wanted; approved FxEmbed sourcing does not require an X browser login.
- Stop app before setup so setup and worker cannot own the same Chrome profile.

```sh
docker compose stop app
docker compose --profile browser-setup run --rm --build --service-ports browser-setup
```

On the operator's computer:

```sh
ssh -L 6080:127.0.0.1:6080 your-user@your-vps
```

- Open `http://127.0.0.1:6080/vnc.html`, enter the local viewer password and sign
  in directly in the VPS browser, including any normal verification. No cookies
  or passwords need to be pasted into chat or copied from the desktop browser.
- An initial navigation timeout leaves the setup browser open for inspection;
  it is not successful source access. Stop setup with Ctrl+C when finished and
  wait for clean shutdown to preserve the persistent profile/release its lock.
- Start runtime with the same profile volume and browser image:

```sh
docker compose -f compose.yaml -f compose.platform-browser.yaml --profile verify --profile search config --quiet
docker compose -f compose.yaml -f compose.platform-browser.yaml --profile verify --profile search up -d --build app reacher searxng
docker compose -f compose.yaml -f compose.platform-browser.yaml exec app python scripts/preflight.py
```

- Check installed Chrome, headed display configuration and profile-directory
  presence. Those are configuration checks, not proof of authentication.
- Inspect any persisted platform hold. Only after resolving its actual cause:

```sh
docker compose -f compose.yaml -f compose.platform-browser.yaml exec app python scripts/manage_platform_browser.py --clear-hold linkedin.com
```

- Restart alone does not clear durable holds. Clearing permits the next source
  check, does not queue jobs or send messages, and renewed denial creates a hold.
  Respect rate-limit retry times and inspect a new login/challenge manually.
- Test a known company About page and a known professional root against fresh
  visible evidence. Check company/person identity, canonical URL, publication
  timestamp, current employer and website matching. Restart and repeat to verify
  session persistence. No email shown means no published email candidate.
- Check expired-session/checkpoint behavior: a timeout after a same-platform
  authentication redirect must create a durable login hold, not be retried as
  ordinary successful zero-result research. Inspect browser-launch/profile-lock
  errors separately; they do not establish an account restriction. Use a second
  paused worker restart to confirm the hold persists until legitimate recovery.
- The direct setup CLI now also defaults to LinkedIn only:
  `python scripts/manage_platform_browser.py --setup --site linkedin`.
  Explicit `--site x|both` is optional. The source release does not carry a login;
  perform the normal sign-in in the server-owned setup browser.
- Run a bounded fresh company search. Report actual query rows, captures, relevant
  US/UK businesses and sourced contacts separately. Known-page access is not
  successful fresh lead discovery or verified person-email coverage.
- Inspect the new search bounds in preflight and verify saved step/scroll/Next/
  unique-result counts and stop reasons in Workflow → Recent search runs. Defaults
  are six snapshot steps, three pages including the initial page, and a 60-second
  capture-loop deadline after initial bounded navigation. Confirm partial results
  remain labelled and an authentication transition stops further UI actions.
- Leave `PLATFORM_BROWSER_PUBLIC_FALLBACK=true` to retain free independent search
  when session research is held. Session expiry requires human recovery; the
  pipeline must not depend solely on the LinkedIn account.

## 4. End-to-end research acceptance, without prospect sending

- Use a fixed sample of US/UK Campaign A/B niches, including businesses with a
  website, website-not-found/profile-first cases and public X profiles. Retain
  input queries/URLs, capture times and source-specific restrictions/errors.
- Inspect deduplicated company records, current country evidence, buyer role,
  official-domain association, email publication/ownership and crawl coverage.
  Company inboxes and personal contacts must be counted separately. No guessed
  addresses; inaccessible/indexed-only contacts remain held.
- Exercise blocked/timeout/partial crawls, durable holds and free-source failover.
  Record attempts, captures, sourced emails and accepted buyers independently;
  zero-result rows must not become fake successes.
- Configure `DRAFT_API_URL`, `DRAFT_API_KEY` and `DRAFT_MODEL` or corresponding
  managed AI-writer settings. Generate from current reviewed evidence and one
  selected offer; review all four touches and actual provider/model quality.
  Missing/failed configuration must hold drafting without a template fallback.
- Confirm source evidence, stage/job progress and extracted data are visible in
  Workflow/Pipeline/Find prospects. Sending remains disabled and paused.

## 5. Mailbox acceptance when configuration is supplied

- Configure sender identity, postal address, SMTP/TLS and IMAP/TLS, SPF/DKIM/DMARC
  and domain authentication using the mailbox provider's instructions. Check
  actual TLS/credentials and independent inbox catch-up/health.
- Only a separately authorized controlled test mailbox should receive test mail.
  Verify durable Message-ID/history, replies, opt-out suppression, permanent and
  temporary failures, OOO/uncertain-send holds, quotas/local windows and four-touch
  termination. Provider acceptance is not inbox placement or a prospect reply.
- Keep prospect sending disabled until explicit pilot authorization and all
  sender/monitoring/evidence/recipient gates pass. Installation does not approve
  any existing sequence or enable the Resume sending control automatically.

## 6. Resources, backup and rollback

- Run a representative crawl/search workload and inspect peak RAM/CPU, browser
  startup/shared memory, disk growth and job durations. Reduce concurrency or
  increase capacity according to measurement; retain crawler functionality.
- Verify app restart, DB migrations, durable job recovery, source holds and Chrome
  profile lock ownership. Confirm failed source startup cannot enable sending.
- Verify FxEmbed's `/data/source-cache.sqlite3` volume ownership and restart behavior:
  a cached bio retains its original retrieval time/hash, and saved provider cooldowns
  are honored across handles. Expired cache data needs a new request; cache hits
  never establish first-party publication. Preserve original cache expiry if the
  private data volume is restored. Other index caches still use memory.
- Create a DB backup: `docker compose exec app python scripts/backup.py --output
  /data/backups`. Also preserve private `.env`, managed settings, evidence and
  screenshots. SQLite backup does not include these or browser session state.
- For a consistent browser-state/access-store backup, stop app/setup and back up
  the persistent volume privately. Browser state is sensitive; encrypt backups
  and store them off-host. Do not include it in source ZIPs or public artifacts.
- Rehearse paused restore in a separate environment. Preserve the old directory;
  never mix a restored DB with unrelated WAL/SHM. Reconcile uncertain sends before
  any future sending resume. Roll back code/image with compatible schema/data
  backup if the new runtime fails; do not reset production data to make it pass.
- Retain an acceptance report containing versions, tested samples, counts,
  provider contracts, resources, restart/restore results and unresolved holds.
  Actual client replies, agreements and measured outcomes remain separate.
