# Official-source profile/contact rendering recovery

13 October 2026. This continuation fixes an actual research-quality gap and a
live regression. It does not claim native LinkedIn access or vendor coverage.

## What changed

Bounded official-page snapshots previously rendered only when extracted HTTP
text was shorter than 300 characters. That could miss JavaScript staff/contact
fields on otherwise substantial pages and ignored the configured `always`/`never`
render policy. Snapshots now honor `crawl_render_mode`: always renders allowed
official pages, auto retains the short-shell heuristic, never does not render.
Browser-disabled behavior is unchanged. Denied platform profiles do not get an
alternate browser; robots, network/domain restrictions and request budgets remain.

Snapshots report `render_attempted`, `rendered`, `render_mode` and render issues.
A failed render retains usable current HTTP evidence without claiming DOM capture.
Person-recovery reports preserve the per-page rendering outcome.

The first live comparison uncovered a real regression: rendering MLA's team page
hid the staff-card content that the current HTTP document published. Its exact
profile/email match disappeared when the HTTP extraction was replaced. The final
implementation preserves the HTTP capture alongside the rendered capture, with
separate text/hash/URL/method and complete scoped staff records. Recovery checks
each record independently. It never joins one version's person/profile link with
the other version's email. An HTTP publication is labelled `public_html`, not a
claim that the element was visible in the rendered viewport. Same-source identity,
current employer, ownership, buyer/country qualification and Reacher gates remain.

## Fixed current query pass

Before the render fix, the existing fixed four-cohort live verifier reran:

| Cohort | Current indexed rows | Selected profiles | Accepted personal emails |
| --- | ---: | ---: | ---: |
| UK dental owner, LinkedIn | 2 | 2 | 0 |
| US skincare founder, LinkedIn | 0 | 0 | 0 |
| UK skincare founder, X | 0 | 0 | 0 |
| US ecommerce founder, X | 0 | 0 | 0 |

These two inputs were already observed profiles, Nik Kotecha and Rakesh Patel,
not new buyers. Free-engine restrictions remained recorded. No replacement
profiles or accepted buyers were substituted. This run does not establish
consistent fresh US/UK recall. Pointer: `data/profile-buyer-coverage-latest.json`.

## Actual paired official-source controls

Three previously observed pages were fixed before the test. Each was captured
in never and always modes, with no native LinkedIn requests:

| Known official source | HTTP exact-profile contact | Final always-mode contact | Limits |
| --- | --- | --- | --- |
| MLA team page / Adam Frickleton | 1 candidate | 1 retained via separate HTTP capture | Rendered card alone lost the match; 2 recorded render issues in final pass |
| NORR staff page / Rachel Rogerson | 1 candidate | 1 distinct candidate | Both source versions link the same person; candidate address is deduplicated; 8 render issues |
| Dental House / Stuart Garton | None | None | A company inbox is not substituted for a personal contact; 3 render issues |

Two candidates are known-control results, not newly qualified buyers or native
profile publication. Resource issues and partial coverage are retained. The
before-fix comparison is also saved; the successful final pass does not erase
that failed regression evidence. Private final pointer:
`data/official-snapshot-rendering-latest.json`.

Reproduce explicitly: `python scripts/verify_official_snapshot_rendering_live.py`.
This is a bounded operator diagnostic, not a scheduled retry of held platforms.

## Verification boundaries

91 focused snapshot/person/profile-resolution checks passed in 39.43 seconds.
Real local Chromium executes a long fictional HTTP page's inline staff/contact
hydration and recovers the published name, role, exact profile and email, with
the initial document reused and no external requests. Tests cover render-policy
selection, failed-render evidence retention, separate capture hashes, raw-only
exact matches, prohibited cross-version joining and invalid raw capture rejection.
The first diagnostic fixture mistakenly referred to a nonexistent fetch method;
it was corrected to the actual `PublicWeb.resource` guard before final acceptance.

Ruff passed. The interim 994-test suite preceded the additional independent-capture
fix; final full-suite/preview/release verification is recorded in VALIDATION.md.
The final complete suite passed **998 tests in 254.34 seconds**, with the existing
Starlette/httpx warning. Changed modules compile successfully.
Live diagnostics preserved operational tables and sending disabled/paused, with
zero contacts imported, real-recipient probes or external messages.

The full acquisition goal remains incomplete. Account-specific VPS acceptance,
native personal-profile availability and representative new US/UK buyer-email
coverage remain unproven. See [the pending VPS checklist](VPS_DEPLOYMENT_CHECKLIST.md).
