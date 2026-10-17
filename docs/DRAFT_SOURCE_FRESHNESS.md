# Current evidence at the draft boundary

**Four stale Campaign A failures reproduced; all five new checks pass. Full suite: 537 tests, 139.16 seconds, one existing Starlette/httpx warning.**

Campaign B already checked the current reviewed offer before draft creation. Campaign A previously accepted a qualified label even after its supporting evidence expired, was future-dated, changed or became superseded by a new crawl. Approval still held those drafts, but the review queue could contain unsupported copy.

Both campaigns now use the same current reviewed-offer/source guard before rendering copy and inside the short draft-write transaction. Invalid source context leaves existing drafts untouched. A current capture explicitly marked partial still permits source-backed review drafts; whole-site completion is not required to quote valid current evidence. No approval or send gate is weakened.

One existing preview test had replaced its valid qualification with a finding missing the quote, service, country quote and review flag. Its comparison now preserves the real reviewed finding while changing only the observation and suggestion being compared. This keeps the production preconditions intact rather than bypassing the new guard.

Reproduce: `python -m pytest -q tests/test_draft_source_freshness.py tests/test_draft_review.py`.

[Machine-readable proof](draft-source-freshness-check.json) records the before/after results and current source hashes. The [new real no-send run](LIVE_ACQUISITION_CURRENT.md) also exercised the updated authenticated API to create four unscheduled drafts from fresh official evidence.
