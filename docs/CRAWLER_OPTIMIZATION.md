# Crawler reliability check — 11 October 2026

The repeat live diagnostic preserved usable pages from three of the same four websites, compared with two before. It saved **36 pages instead of 35**, with **one published, unverified company inbox** in both runs. This proves a modest capture improvement; it does not prove a general speedup, four complete crawls, email existence, business qualification or an operational outreach campaign.

## Changes

- Save the homepage and linked priority pages before expanding optional sitemaps. Afterwards, interleave sitemap expansion and page captures, favoring company/contact/product sitemap indexes before large blog archives.
- Reuse the already fetched, checked HTML only for the matching initial Chromium document. Dynamic scripts and GET data still execute through the guarded public fetcher. Documents from another URL are never substituted.
- Bound DNS lookup and each network/body operation. Retry temporary GET failures once by default; retain temporary failure types for the bounded job retry lane. Respect `Retry-After`, including waits longer than the inline retry allowance. Permanent 401/403/404/410 responses do not receive repeated job retries.
- Let content requests settle without waiting for slow background images during text research. Screenshot capture retains its separate visual load wait. Try to preserve a loaded, same-company DOM after incomplete navigation; record incomplete assets and rendering failures.
- Reject access-challenge and empty pages as evidence and contact sources. A robots denial or HTTP 403 remains a failed/held research result.
- Display the recorded last phase, HTTP error, first-page time and document reuse/retry counts. Interrupted coverage says **“Remaining coverage not finalized”** instead of inventing zero remaining URLs. These diagnostics do not change qualification or sending eligibility.

The default **30-page budget, three-level depth, six-sitemap budget and always-on Chromium rendering** remain in place. Declared robots pacing and source/network checks still apply. The normal worker allows 1,800 seconds per job; the comparative diagnostic intentionally uses the same **180-second deadline** on each site. Cancellation cleanup can take a few seconds beyond that deadline.

## Live comparison

No new search queries were used: both runs researched the same previously discovered websites, two independent sites at a time. The new isolated database had sending and workers disabled. Verification jobs created by ordinary contact import were not executed.

| Website | Pages before | Pages after | First saved page | Result at the diagnostic deadline |
|---|---:|---:|---:|---|
| Dental Clinic London | 16 | 16 | 14.5 s | Interrupted; published inbox remains unverified |
| Austin Roofing / WDR | 0 | 1 | 114.8 s | Interrupted; saved HTTP page after incomplete Chromium rendering |
| Tanuki Coffee Roasters | 19 | 19 | 10.7 s | Interrupted; rendering/resource issues recorded |
| MYSKIN Shop | 0 | 0 | — | Failed at robots fetch, HTTP 403, 0.8 s |

There were **35 confirmed initial-document reuses** among the 36 saved pages. Roofing still takes too long to capture its first page; no new published email was recovered there. The 403 site requires an accessible source or further operator research. These changes do not bypass access controls or establish direct LinkedIn/X capture reliability. Business identity, active trading, country, buyer and one useful offer still need review; all four candidates remain unqualified.

The raw comparison is `data/crawler-optimization-live/20261011-011403/report.json`; its isolated database and before/after pointer remain in `data/`. The raw report is immutable. Final code subsequently added explicit no-page temporary-failure propagation, sitemap-failure completeness handling, worker `Retry-After` coverage, and the dashboard diagnostic fields; those final adjustments are covered by the final suite. They are not retrospectively presented as a second live run.

## Verification and dashboard

**322 tests passed** in 92.60 seconds, with one existing dependency deprecation warning. Focused regressions cover homepage/contact scheduling, permanent and temporary failures, slow streaming bodies, long `Retry-After`, challenge-page exclusion, dynamic GET content with a slow image, wrong-document rejection, and read-only coverage diagnostics. Ruff and dashboard JavaScript syntax checks passed.

Actual Chromium verified the normal dashboard on desktop and mobile, all three 17/11/35 map modes, the visible 403/robots phase and measured first-page times, explicit unknown coverage, no horizontal overflow, and an inspector below the canvas on mobile. Zero JavaScript errors occurred. Only the four unreviewed diagnostic records received updated captures; existing contacts, messages, jobs, suppression, sales, other prospects and private configuration were preserved. No external action was queued by this refresh. The normal dashboard now has six candidates and 66 current pages, including earlier captures; those totals are distinct from the four-site comparison.

See [machine-readable proof](crawler-optimization-check.json). Screenshots: [desktop](screenshots/crawler-diagnostics-desktop.png), [mobile](screenshots/crawler-diagnostics-mobile.png). Re-run the isolated comparison with `python scripts/verify_crawler_optimization_live.py` after generating the preceding first-workflow diagnostic. Tests use `python -m pytest -q`; this check does not require mailbox or VPS setup.
