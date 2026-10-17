# LinkedIn repo solutions: actual code and live audit

13 October 2026. The user asked for fresh repository research instead of repeated
source-blocker status checks. Repository code was inspected at pinned commits;
descriptions and examples were not counted as working source access.

## Actual implementations

| Repository | Pinned commit | What the inspected implementation requires/proves |
| --- | --- | --- |
| [yatish27/linkedin-scraper](https://github.com/yatish27/linkedin-scraper) | `fb4297f57149507427188f73b89b36c466b6ef0a` | Ruby HTML fetch/parser using legacy public-profile selectors and randomized browser user agents; optional proxy configuration. No demonstrated current native email access. |
| [SuwaidAslam/LinkedIn-profile-scraper](https://github.com/SuwaidAslam/LinkedIn-profile-scraper) | `2a04021d912943ea6c9ce80b15401e5caba8ee3a` | Selenium implementation requires LinkedIn login credentials. Its README's working-date claim is 2021. Not an anonymous current-source solution. |
| [aadisriram/nodejs-linkedin-scraper](https://github.com/aadisriram/nodejs-linkedin-scraper) | `1292f4e10ea70178850e950e8b4f2d82e9232f18` | Maintained HTML parser; optional fetch fails on 429/999/authwall. Live tests run only with `LIVE_LINKEDIN=1`, so normal fixture tests are not live access proof. |
| [Spectre-Scrape/linkedin-profile-scraper-no-cookies](https://github.com/Spectre-Scrape/linkedin-profile-scraper-no-cookies) | `d498691d9d68a08b216fc29f02766ce7357ed9e3` | `src/index.ts` requires `APIFY_API_TOKEN` and dispatches a hosted Actor. The repository is the client wrapper, not the self-hostable upstream extractor. |
| [DWE-CLOUD/Linki-Scrap](https://github.com/DWE-CLOUD/Linki-Scrap) | `73709f37d1fce5a8841c405cbf84948e5b7d38e8` | Despite anonymous/bypass marketing, the source implements username/password login and OTP handling, and setup requires an account. No account state or private contact panel was used in this audit. |
| [ManavvGarg/linkedin-profile-api](https://github.com/ManavvGarg/linkedin-profile-api) | `5775de51aeaa035668d212df8bc4641fa33a31a2` | Primary Voyager extraction requires `li_at`. Its separate public-document header claim was tested independently below, without authenticated/private endpoints. |
| [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) | `7a684934907a8c7feaafe9ff1ccfd9d45cc26faf` | Maintained self-hostable browser/HTTP framework. Its actual 0.4.15 browser fetch was installed in the isolated audit environment and tested below. Not a contact database. |

Private pinned-source review files are in `data/repo-source-review-20261013`.
Repository code was not blindly installed/executed. Scraping-framework dependencies
were installed only into `.venv-audit`, leaving the production environment and
dependency lock unchanged.

## Live transport controls

All controls used the same previously observed UK professional profile,
`https://www.linkedin.com/in/adam-frickleton-15936a13a`. They are known-profile
access controls, not representative new-lead or VPS acceptance tests.

| Actual tested request | Result |
| --- | --- |
| Standard HTTP guest document, sparse browser headers | HTTP 999 |
| Standard HTTP guest document, the reviewed complete header recipe | HTTP 999 |
| `curl_cffi` 0.16.3, Chrome131 TLS and complete headers | HTTP 999 |
| Scrapling 0.4.15/Patchright, installed real Chrome, fresh guest context | HTTP 999, final authwall route |

The Scrapling context started with zero cookies. CAPTCHA solving, synthetic Google
referer, proxies, session copying and private API/contact-panel access were disabled.
Non-GET/private API requests were blocked in that diagnostic. No denial was parsed
as a profile/contact, and no tested failed transport was enabled in production.
The complete-header claim may describe another network environment; these results
do not establish the cause of this host's denial or prove failure on every network.

A first curl diagnostic passed a constructor-only option to the request function
and raised `TypeError`; that setup error was corrected and is not counted as a
LinkedIn response. The corrected result in the table is the actual platform test.

Reproducible diagnostics:

```powershell
.\.venv\Scripts\python.exe scripts/verify_linkedin_guest_headers_live.py
.\.venv-audit\Scripts\python.exe scripts/verify_linkedin_curl_guest_live.py
.\.venv-audit\Scripts\python.exe scripts/verify_scrapling_guest_live.py
```

The optional audit environment requires `scrapling[fetchers]==0.4.15` and an installed
Chrome for the browser check. Run explicitly as diagnostics, not repeated scheduled
retries of a held platform. Saved evidence pointers:

- `data/linkedin-guest-header-check-latest.json`
- `data/linkedin-curl-document-check-20261013.json`
- `data/scrapling-guest-check-latest.json`

## Recommended current system

Keep the custom Python pipeline, free SearXNG discovery, current official company/
staff/contact evidence, approved FxEmbed X research, and source/owner/country review.
An optional VPS-owned LinkedIn browser session can support visible professional
and company research after one-time operator login. It is already implemented in
[the VPS browser mode](PLATFORM_BROWSER.md): the session runs on the VPS and does
not depend on the desktop extension or manual exports per prospect.

Account/session support does not guarantee email availability or unrestricted
automation. Authenticated VPS behavior is unverified until the operator configures
and tests that environment; sessions can expire and source holds require attention.
Protected contact overlays remain excluded. Sending stays disabled during sourcing.

The browser setup instructions previously claimed restart cleared an access hold.
That was stale: holds are durable. The instructions now provide the explicit
per-platform clear command, only after the actual cause has been resolved. Existing
runtime hold behavior and settings have not been weakened or changed.

Apollo documents a [multi-source database and contributor network](https://knowledge.apollo.io/hc/en-us/articles/45824429846669-Apollo-Data-Overview)
and [waterfall enrichment](https://docs.apollo.io/docs/enrich-phone-and-email-using-data-waterfall).
A browser scraping repo supplies a transport/parser, not that data inventory.
Equivalent person-email coverage cannot be inferred from installing one framework.

## Verification and remaining scope

The three new diagnostic scripts passed Ruff; operational data, source holds and
sending-disabled/paused state were unchanged. Zero contacts were imported, recipient
probes performed or messages sent. Production source/dependencies were not changed,
so the preceding 969-test full-suite baseline and later 63 focused source-hint tests
remain separately scoped; no new production full-suite result is claimed here.

This audit completes the requested code-level repo research and live technical
controls. The original acquisition/parity goal remains incomplete: no free guest
LinkedIn profile-email source was established by these controls, and representative
US/UK buyer-email coverage remains unproven. The source-access/account choice is a
real implementation tradeoff, not a verified universal bypass.
