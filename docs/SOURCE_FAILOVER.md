# Public-source failover and crawler recovery

Platform restrictions remain unresolved. This change continues independent public company research when a profile is unavailable; it does not recover access to the blocked platform or expose unpublished emails.

## Behavior

- `PLATFORM_BROWSER_PUBLIC_FALLBACK=true` is the default. With managed mode enabled, the existing free SearXNG market/platform searches supplement normal browser search. A held or unavailable browser search no longer prevents accessible website candidates from being found. Index-result relevance, marketplace exclusion, market-conflict checks and domain deduplication remain active.
- A blocked managed profile or a captured profile without a website link can use bounded named-company/backlink/contact searches and current official-page matching. The original profile capture state and `source_failover` provenance remain saved. The fallback forces the free search provider; it does not call paid SerpApi or LinkedIn/X developer APIs. A current website match is still an unqualified candidate.
- No website is inferred from an email domain. Failed/partial search coverage cannot establish website absence. Multiple direct company links remain ambiguous. Setting the fallback flag false retains browser-only discovery and holds.
- Contact crawling prioritizes actual contact/team/about/enquiry/media-relations routes rather than arbitrary substrings. Contact recovery can reuse sourced failed/interrupted routes. It checks site cooldowns before network work and preserves per-URL retry times even if search rediscovers that URL.
- Newly recovered contact pages remove their resolved retry/in-flight entries from the original crawl and mark transient errors resolved. Other frontier/retry work, previously saved pages and cooldowns are preserved. The existing automatic continuation still retries only outstanding work within bounded budgets; permanent denials are not converted into transient retries.

## Dashboard

**Find prospects → Recorded platform coverage** reports saved source signals, current captures, unavailable/stale observations, distinct website candidates, independently recovered website candidates and published email candidates. It uses the latest observation for each profile/post and market within the latest 500 platform-signal events, not an unrestricted historical total or a vendor-recall benchmark.

Only addresses present in a current saved capture count as published candidates; index-only addresses, duplicate addresses and dedicated privacy/security inboxes do not. These counts do not prove business ownership, a relevant buyer, mailbox existence or outreach eligibility. Search-run failures remain separately visible in Workflow → Recent search runs. The authenticated read-only `/api/source-coverage` endpoint avoids reloading all prospect evidence just to populate this table.

## Live no-send diagnostic, 12 October 2026

`scripts/verify_source_failover_live.py --limit 2` rechecked two actual previously indexed businesses using a new isolated local guest browser profile, free SearXNG search and HTTP company-page captures. It did not reuse the user's browser login or fabricate index inputs.

| Known business signal | Current profile attempt | Independent website result | Email result on the checked company page |
| --- | --- | --- | --- |
| X: Sonria Dental Clinic, UK hint | HTTP 403; platform held | Current public company page backlink supported `www.sonriadentalclinic.co.uk` | One published email candidate; ownership and mailbox existence unverified |
| LinkedIn: Fonte Coffee Roaster, US hint | Browser unavailable | Current name/content match supported `www.fontecoffee.com`; checked page redirected to `/coffee/` | Zero published email candidates on that page |

Both website captures succeeded as **single-page HTTP checks**, with rendering disabled. They are not full crawls or authenticated VPS acceptance. SearXNG still reported Brave rate limiting, Google denial and Qwant CAPTCHA; those limitations were preserved and not bypassed. Neither geographic hint is an independently reviewed country qualification.

The diagnostic created zero contacts, performed zero mailbox probes and sent zero messages. Main operational tables remained unchanged. Runtime reports and the guest profile are private/excluded from source releases; `data/source-failover-live-latest.json` points to the report. [The small release-safe result](source-failover-live-check.json) records counts/states/hashes without copied contact addresses.

The live result proves useful independent research can continue for these two known signals despite profile failure. It does not establish fresh discovery recall across segments, unrestricted platform access, private email availability or Apollo/Apify parity. Local tests separately cover fake DOM/held-browser paths and current-source verification, so those fixtures are not represented as live platform captures.

## Local verification

The complete suite passed **763 tests**, including **19 new failover, route-priority, cooldown/reconciliation and source-coverage cases**. Ruff, Python compilation and the JavaScript syntax check passed. Chromium exercised the coverage table, held-mode banner and existing workflow on desktop/mobile using fictional isolated data, with zero JavaScript errors and no mobile overflow. The normal preview was restarted with sending disabled/paused; its new coverage endpoint responded and no operational job was active. The separate read-only normal-preview UI check preserved operational data/settings and made zero provider calls or external sends. One existing Starlette/httpx deprecation warning remains. Actual Linux container/VPS acceptance is still pending.
