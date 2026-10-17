# Platform access diagnosis and recovery

12 October 2026. This check investigates the observed LinkedIn 999 / X 403 failures without sending messages, probing recipients, transferring credentials or claiming unrestricted access.

## Live diagnosis

`scripts/diagnose_platform_access_live.py` compared an ordinary empty Chromium guest context against the managed browser request allowlist. Each mode requested the same two previously observed public profile URLs once. Both returned LinkedIn **999** and X **403**. Removing the application's request allowlist therefore did not restore access in this sample.

Allowlisted response metadata showed LinkedIn's `cloudflare` server header and a TLS certificate for `www.linkedin.com`; X returned `cloudflare envoy`, a certificate for `*.x.com`, and an empty denial body. No explicit intermediary-policy denial header was observed. These facts do not distinguish IP reputation, account requirements, region policy or bot detection. They establish a target-facing denial in both normal-browser modes, not a parser failure or verified universal bypass. Proxy environment values, cookies, credentials, request headers and raw denial content were not exported.

LinkedIn documents that network request denial can follow unusually high network activity and may recover when activity normalizes: [LinkedIn network guidance](https://www.linkedin.com/help/linkedin/answer/a520504/account-network-blocked). A status code alone does not prove this is the cause of our sample.

## Implemented failure handling

- Platform access holds are now stored independently in `DATA_DIR/platform-browser/access.sqlite3`. Restarting the app cannot silently discard an access denial and hammer that platform again.
- HTTP 429 observes parsed numeric or HTTP-date `Retry-After` values, with a default one-hour cooldown. The next normal queued request may proceed after expiry; expiry does not schedule new requests or establish access.
- HTTP 401/403/999 and visible login/challenge holds require operator resolution and explicit clearing. Missing profiles and temporary 5xx responses remain separate and do not put a whole platform on an authentication hold.
- Corrupt or unavailable access-state storage fails closed; a failed persistence write retains the original denial and a memory hold.
- Only whitelisted response-host/server/status/classification/retry metadata is retained in professional research and authenticated dashboard status. Error documents never become contact evidence.
- Existing free public search and independent company research continue when managed LinkedIn/X sources are held and public failover is enabled. This is a separate source path, not recovered platform access.

After resolving the actual cause, clear only the affected hold with `python scripts/manage_platform_browser.py --clear-hold linkedin.com` or `--clear-hold x.com`, using the same `DATA_DIR` as the app. The running process notices the cleared durable hold on its next status/access check. Clearing does not sign in, schedule work, send mail or prove source access.

## Live recovery result

`scripts/verify_blocked_source_recovery_live.py` reused the observed host-level denials in an isolated data directory and continued an already recorded **SonriaUK** business signal. The public X profile remained on operator hold. Independent public company search found `https://www.sonriadentalclinic.co.uk/`, corroborated the profile through a current reciprocal link, and captured **one published company-email candidate** from the current official homepage.

This is known-company recovery, not fresh prospect discovery, personal-profile email extraction, buyer qualification or mailbox-existence verification. No profile denial was bypassed. The operational database fingerprint was unchanged; zero contacts were imported, zero SMTP probes ran and zero messages were sent.

Private dated reports are referenced by `data/platform-access-diagnosis-latest.json` and `data/blocked-source-recovery-latest.json`; runtime data and session state are excluded from source releases. Tests cover restart persistence, cross-process clear, rate-limit expiry, corrupt storage, metadata redaction and public discovery continuing after both platforms are held. Latest suite results are in the workspace `VALIDATION.md`.

## Remaining acceptance gaps

Actual public personal-profile email capture, reliable representative LinkedIn/X coverage, and actual VPS/network acceptance remain unverified. Neither a saved session nor an accessible public post proves those requirements. These changes improve diagnosis and continuity but do not turn inaccessible or unpublished addresses into usable contacts.

## Follow-up: normally rendered official profile widget

The next public-source check used `scripts/verify_public_profile_embed_live.py` to render the actual HTML returned by X's publishing service in an empty guest browser. The current publication markup references `https://platform.x.com/widgets.js`, which redirected to `platform.twitter.com/widgets.js`; the official timeline JavaScript loaded successfully. This corrected an initial diagnostic precondition that expected only the older script hostname. The rejected first run did not test timeline rendering and is not counted as evidence of a platform error.

In the subsequent actual rendering check, the widget itself requested the public timeline frames for the previously observed `ssbmGooms` and `SonriaUK` profiles. Both returned **HTTP 429** from `syndication.twitter.com`. The page exposed no scoped profile-bio elements and did not establish profile-email extraction. No hidden API request was constructed and no serialized hidden profile data was read. The current publishing endpoint's HTTP 200 therefore cannot be counted as profile-data access.

The diagnostic now stops further profile controls after the first observed 401/403/429/999 and records the parsed retry interval for 429; the completed dated two-control run predates that stop refinement and is preserved unchanged. No production widget adapter was enabled based on the failed result. The private live report is referenced by `data/public-profile-embed-latest.json`; operational rows/settings remained unchanged and zero imports, probes or messages occurred. X documents profile timeline embeds as public-post displays in its [official embed guide](https://help.x.com/en/using-x/embed-x-feed); that scope alone does not promise public profile biographies or email access.
