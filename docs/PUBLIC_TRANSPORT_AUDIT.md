# Live publishing and anonymous-browser audit

12 October 2026. This audit tests the next existing public-source paths after direct HTTP professional-profile attempts stopped at the robots gate. It preserves the original goal: live personal-profile email acquisition and representative vendor-comparable coverage are still required; a public post control cannot stand in for those requirements.

## Changes

The public X post reader now retains explicitly published mailto links whose display label does not contain the address, and visible `[at]`/`[dot]` address spelling. Hidden descendants, scripts, forms, frames and HTML outside the single validated post body cannot contribute an email candidate. Security/privacy/system inboxes remain excluded from outreach candidates. Addresses are normalized from actual published strings; no mailbox guesses or contact imports were added.

The managed browser now records every HTTP error response before attempting to parse page fields. Chromium can raise during navigation for LinkedIn's custom status **999**; its observed main-document response is retained rather than flattened to `browser_unavailable / Error`. Authentication/denial/rate-limit statuses 401/403/429/999 put the platform on operator hold. A missing profile or temporary 5xx response is reported separately and does not falsely become a persistent authentication hold. Error documents never become contact evidence.

Professional captures and research reports now retain the bounded access-issue fields (`http_status`, `error_type`, `reason`) returned by the adapter. Existing authenticated prospect details expose the report, so the actual failure cause is available for inspection.

## Real observations

[Dated live report](public-transports-live-check.json); reproducible with `scripts/verify_public_transports_live.py` while the operational database is paused and idle.

| Public-source path | Result | What this proves |
|---|---|---|
| X's fixed `publish.x.com/oembed` service, explicit US Interior public post | HTTP 200, validated single-post capture, zero emails | Live transport/schema compatibility only; government post is not a client lead |
| Normal headless Chromium, empty task-owned profile, explicit LinkedIn professional URL | HTTP 999, no profile text/email | Anonymous source denial on this host; no authenticated VPS acceptance |
| Same ordinary guest-browser path, explicit X professional URL | HTTP 403, no profile text/email | Anonymous source denial on this host |
| X's publishing service, two explicit profile URLs | HTTP 200, timeline-anchor markup only, no biography field, no returned author field, zero email strings in returned markup | A successful profile embed request does not provide profile biography or email extraction |

The diagnostic used no user browser cookies, account sign-in, developer keys, CAPTCHA/challenge solving, identity impersonation or proxy rotation. Browser session files live in a new private task-owned runtime folder and are excluded from source archives. No contacts, real recipient probes or messages were created. The operational database fingerprint stayed unchanged; sending remained disabled/paused. The profile controls have mixed relevance and do not count as qualified potential clients.

The live post contained no email. Published mailto/obfuscation handling is therefore fixture-verified, not a demonstrated live personal-email acquisition. The guest-browser run was local Windows; it does not establish Linux-container deployment, allowed account automation or success on a future VPS/IP.

## Completion audit

| Original requirement | Evidence | Status |
|---|---|---|
| Actual LinkedIn professional email extraction | HTTP/native-browser controls stop at robots/999; no live captured address | Incomplete |
| Actual X professional profile email extraction | Native browser HTTP 403; profile publishing returns only an embed link | Incomplete |
| Current employer, buyer and published-email corroboration | Review gates exist and fixture tests pass; no live profile recipient proof | Incomplete |
| Apollo/Apify-like representative coverage | Prior public-source sample and current transport controls are not a matched vendor benchmark | Unproven |
| Unattended VPS operation | Portable code/deployment sources exist; actual VPS/account/runtime acceptance deferred by the user | Deferred and unverified |
| No sending or recipient probes during development verification | Isolated workers disabled, fingerprint assertions and explicit zero-message/probe checks | Verified for this diagnostic |

The goal remains active and incomplete. Current public-only access does not supply the protected/missing profile content. Further code changes alone cannot prove access or manufacture unpublished addresses. An authorized, working source/access path and representative live data are necessary before the missing requirements can pass. No paid access or account setup was initiated.

## Checks

**854 tests passed** after these changes; fifteen new cases cover publication mailto/obfuscation and hidden-data filtering, real Chromium HTTP 999/403/429/404/500/503 behavior, and preservation of source denial metadata. The focused publication/browser/professional set passed 100 tests. Ruff and Python compilation passed. Synthetic intercepted browser/mailto fixtures are not live prospect-email evidence. The one warning is the existing Starlette/httpx deprecation.
