# Bounded LinkedIn/X search and restart-safe X cache — 14 October 2026

This completes the two agreed pre-VPS changes. Browser pooling/reuse remains
optional future work only if deployed measurements justify it. No native-platform
restriction bypass, new login, recipient probe or message was attempted.

## Search coverage

Managed search now collects multiple rendered result snapshots instead of stopping
at the first loaded list. Native wheel input advances public search results;
LinkedIn can use the normal scoped Next button. Previous X cards remain collected
when a virtualized list replaces them. URLs are canonicalized/deduplicated, with
current rendered card context retained and hidden/dialog/account content excluded.

Defaults:

```dotenv
PLATFORM_BROWSER_SEARCH_STEPS=6
PLATFORM_BROWSER_SEARCH_PAGES=3
PLATFORM_BROWSER_SEARCH_TIMEOUT_SECONDS=60
```

The page limit includes the initial page. Snapshot steps include the initial read.
The capture-loop deadline begins after initial browser startup/navigation, which
retain their separate existing bounded timeouts. Results also stop at the requested
limit or after two rounds without new profiles. Search scope/type/query identity
must remain unchanged; page-number changes are permitted. Each UI action waits
at least 250 ms and otherwise uses the configured platform delay.

Login/challenge and HTTP 401/403/429/999 stop further actions and preserve the
platform hold. Already collected search candidates can be returned as partial
results with explicit issues; denied/error documents never become contacts.
Timeouts keep partial rows and close the browser context. Scope limits are not
represented as exhaustive platform discovery or qualified buyer acceptance.

Provider reports preserve snapshot/scroll/Next counts, unique/rejected/duplicate
rows and the stop reason. Workflow → Recent search runs and limitations displays
these counts even when the query has no HTTP/engine error, with full coverage
details available. Normal discovery records already retain these reports.

## Community X cache and provider cooldown

FxEmbed now uses private `/data/source-cache.sqlite3` in the existing data volume.
Its 15-minute positive cache, short negative cache, provider cooldown and request
pacing survive a fresh Settings instance/app restart. Cached captures preserve
their original retrieval time/hash and remain unverified third-party hints.

HTTP and provider-body rate-limit responses honor an explicit Retry-After header;
otherwise the existing fallback interval applies. A hold applies across handles,
and expired cache/holds permit a new normally paced request. A profile 404 does
not hold unrelated handles. Storage retains at most 256 cache entries per provider;
expired entries are pruned on access/write, not by an independent idle timer.

Transactions preserve the greater saved cooldown, and cache bodies are bounded.
Unreadable/corrupt/unwritable storage returns a source error instead of silently
forgetting a saved cooldown. The operational DB and recipient evidence are not
used as cache storage. Other public-index providers keep their existing memory
cache behavior. This is the application's single-worker deployment model, not a
distributed multi-worker request-lock service.

Treat the cache as private runtime data. Source ZIPs exclude it. A volume backup
retains its original expiry/timestamps; restored data must never receive a fresh
publication timestamp. Native LinkedIn/X access holds remain in their independent
existing access store.

## Verification boundary

The combined focused suite passed **175 tests in 52.00 seconds**. Real local
Chromium executes fictional pagination/virtualized scroll, request-limit and
page/step bounds, stale results, query changes, challenge and HTTP 429 cases.
Controlled timeout checks preserve partial rows and close the session. Real
desktop/mobile dashboard rendering shows the saved coverage without overflow or
JavaScript errors. Mocked FxEmbed responses verify restart, original timestamps,
TTL expiry, cross-handle holds, negative caching, bounded storage and corruption.

One test exposed that a scripted window scroll did not reliably dispatch the load
event in this Chromium environment; normal wheel input fixed that observed path.
No live account or platform recall is inferred from these controlled fixtures.
Ruff, Python compilation and the three changed JavaScript syntax checks passed.
Final complete-suite/preview checks are recorded in VALIDATION.md. Actual VPS
login, accessible selectors, engine/provider availability and qualified US/UK
buyer yield remain deployment acceptance tasks.

Final complete suite: **1096 tests passed in 289.74 seconds**, with the existing
Starlette/httpx deprecation warning. The 23 new cases are included in that total.
The normal preview was restarted and health/authenticated status both returned
HTTP 200. Operational tables were unchanged, there were no active jobs and
sending remained disabled/paused. Managed mode remains disabled until real VPS
setup. The updated source-only ZIP includes these changes and deployment notes;
its integrity and SHA-256 are checked during packaging.
