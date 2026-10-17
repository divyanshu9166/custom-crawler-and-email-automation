# Current verifier recovery

The actual native Windows Reacher backend now runs on loopback 8081 and the development dashboard's verifier check returns HTTP 200 / ready. Startup/auth/syntax passed; a sourced recipient checked in an isolated clone returned catch-all/risky and was never treated as safe. Sending stays disabled; normal records/private configuration remain unchanged. [Native build/startup and real limits](NATIVE_REACHER.md) document the exact optional-worker compatibility guard and reproducible `start.ps1 -NativeVerifier` preview. Earlier Docker-only/404 statements below describe the preceding recovery snapshot.

# Recovery for partial crawls, inaccessible profiles and a wrong verifier endpoint

The system now continues useful public research when individual sources are unavailable. This does not establish complete platform access, guaranteed contact acquisition or safe mailbox verdicts.

## Partial crawls

Every new crawl saves a checkpoint containing queued company URLs, captured/seen URLs and sitemap state. **Continue crawl** runs another batch with the normal 30-page budget, retaining current evidence IDs and avoiding previously captured pages. Renderer/access errors remain visible; additional pages never turn an incomplete audit into a fictional complete result.

Older captures did not record their original frontier. **Find public contacts** can reconstruct a frontier from newly captured official-page links. That is a new, bounded source scope; it cannot reconstruct all unseen URLs from an earlier attempt. Stale captures require a fresh research run. Active/replied/held/closed outreach blocks automatic evidence mutation.

## Public-profile and contact research

The newer [contact-source fallback](CONTACT_SOURCE_FALLBACK.md) also uses current saved official contact/team pages and checkpoint navigation. Empty or failed search can fall back to bounded official-homepage navigation. Saved catalog/blog URLs are not promoted to contact routes because their text contains "about" or "team". The two-site real recovery check found four previously known published inboxes on Skindays and none on SmartRoof; this is recovery proof, not new prospect or buyer acceptance.

The existing indexed LinkedIn/X/business-profile route resolves a company website and preserves access/identity limitations. Automatic contact research now follows website research and searches for contact/team/leadership sources. It runs three queries and captures up to six official-page URLs with the same robots/HTTP/Chromium controls. Settings `AUTO_CONTACT_RESEARCH` and `CONTACT_RESEARCH_MAX_PAGES` control this additional pass; it does not reduce the main crawler budget.

An email in a search snippet or social hint is never enough for contact import or verification. A newly captured official page must publish it. Different-domain inboxes retain ownership review; named-buyer relevance, country/business fit and technical verification remain separate gates. Same-company research, contact recovery and screenshot jobs run serially. Both workflow maps reflect active contact research.

The real SmartRoof and Portland contact-source runs captured official pages but found **no new published emails**. Portland's current official website corroborated a previously saved LinkedIn profile link. A fresh targeted index query did not return that exact profile. This demonstrates website corroboration, not readable LinkedIn profile content or private-email access.

## Verifier 404

The configured local port 8080 serves Apache/httpd, not a running Reacher backend. **Check verifier** uses invalid-syntax input before real-recipient submission. An unrecognized API produces a clear setup hold. Its fallback collects syntax/DNS evidence only: real Skindays MX records were found, but mailbox existence stays unknown and no recipient-server SMTP conversation or email occurred.

A local Compose override exposes the actual backend on loopback port **8081**, leaving other services on 8080 untouched. The helper builds the project's pinned backend and checks startup/auth/syntax before reporting ready:

```powershell
.\.venv\Scripts\python.exe scripts/start_local_reacher.py
```

Docker is unavailable on this workstation, so the helper correctly reports **not ready**, starts nothing and changes no private configuration. After a successful actual startup, configure `REACHER_URL=http://127.0.0.1:8081` in the private local environment and restart the app. Linux/VPS Compose uses the existing internal `http://reacher:8080` endpoint. The user's deployment/mailbox setup remains deferred. Reacher also requires outbound port 25 for its SMTP checks; see the [official self-hosting instructions](https://github.com/reacherhq/check-if-email-exists#1-%EF%B8%8F-http-backend-using-docker-popular-method-).

## Earlier acceptance evidence before the contact-source fallback

**452 tests passed**, including 19 new recovery cases. Actual isolated Chromium dashboard smoke passed. The normal dashboard's new verifier control displayed the real setup problem, and its actual Continue crawl button queued SmartRoof continuation. Desktop/mobile controls were checked without enabling sending. A public practice site rendered two pages followed by two new pages, preserving its original evidence IDs with zero duplicate captures. It is not a business prospect or proof of acquisition performance.

[Earlier machine-readable live results](recovery-live-check.json) records the terminal company/job counts, source hashes from that earlier implementation, actual DNS hold, explicit failed index lookup, counterpart corroboration and practice-site scope. Private settings remained unchanged. No emails, social messages or contact forms were sent/submitted.

The earlier [no-send pilot](NO_SEND_PILOT.md) retains its historical 112-page / five-email-candidate snapshot and source lineage. New recovery captures do not rewrite that acceptance claim.
