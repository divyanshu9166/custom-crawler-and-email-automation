# Core website-to-person publication recovery

13 October 2026. Earlier goal work fixed snapshot-only HTTP/DOM retention and
homonym research. This continuation inspected the normal application path and
found that its crawler still replaced the original HTTP extraction after rendering.
The snapshot diagnostic's success did not prove the production research pipeline.

## Real pipeline comparison

The known official MLA team page was processed by actual `research_lead`, with
rendering enabled, a one-page/no-sitemap budget and an isolated database. No worker
or verification job was started:

| Current known-source run | Isolated contact records | Named contact records | Saved current publication checks |
| --- | ---: | ---: | ---: |
| Before core retention | 1 generic inbox | 0 | Not counted as person recovery |
| After core retention | 72 published address records | 5 | 72 passed |

These are one company's publicly published address records, not 72 clients,
qualified buyers, confirmed current employees or safe mailboxes. Both runs were
partial one-page crawls. The additional addresses came from the currently fetched
public HTTP document, not address-pattern generation or protected profile panels.
Rendered resource issues remain in the saved reports.

Automatic `research_professionals` then consumed the actual saved crawl/evidence
hashes, with no manually supplied profile, and found five distinct official named
email candidates. It made zero index queries because an observed profile filled
the one-profile diagnostic budget. The native profile capture was still **held**;
no native LinkedIn publication or unrestricted access is inferred.

The isolated run queued 72 technical verification jobs. **None executed.** The
operational database was unchanged: zero operational recipient imports, real
mailbox probes, messages, account actions or approvals. Country, buyer relevance,
ownership, outreach eligibility and mailbox validity remain unreviewed.

## Core corrections

- Allowed same-URL HTTP and rendered contact/person evidence is retained when
  the HTTP capture adds information. Different routes or identical/no-additional
  publications are not combined. Robots, URL/network budgets, challenge handling
  and read-only browser requests remain unchanged.
- Complete person records preserve their own capture method/document hash.
  A name/profile from one version cannot receive another version's scoped email.
  Shared addresses across different named people clear individual identity;
  newly discovered ambiguity also clears an earlier inferred name/role on a
  still-new contact. Existing outreach history remains protected from recrawling.
- Evidence text labels additional public HTTP content explicitly, without
  claiming rendered visibility. The evidence digest commits both original
  document hashes. Removing an HTTP-only address changes its proof even when
  rendered content stays unchanged, preventing reuse of withdrawn publication.
- Main and contact-recovery crawl reports retain capture methods/hashes and the
  scoped staff records, so automatic professional research can consume them.
  Other-domain addresses stay ownership-review candidates; suppression and
  recipient/message review gates are not relaxed.

The normal evidence table still uses one current record per URL. The composite
digest binds its labelled captures rather than silently overwriting one source
or treating a raw HTTP quote as a rendered observation. Non-contact pages retain
their original single-document digest when no extra contact evidence is present.

## Verification

143 focused crawler/person/publication/professional/failover checks passed in
61.63 seconds with the existing Starlette/httpx warning. Real local Chromium tests
exercise the full `research_lead` pipeline, saved publication proofs, automatic
professional lookup, conflicting names on a shared address, and withdrawal of
an HTTP-only contact. Pure scope tests cover redirects, unchanged data, independent
profile/email associations and other-domain review. Ruff passed.

The full suite passed **1016 tests in 267.15 seconds**, with the same existing
warning. Final preview/release verification is retained in VALIDATION.md.

Private measured evidence:

- `data/core-staff-publication-before-latest.json`
- `data/core-staff-publication-after-latest.json`
- The after-run folder's `professional-report.json`

For an explicit repeat of the current implementation, run
`python scripts/verify_core_staff_publication_live.py`; it creates another isolated
database and never starts its worker. A repeat is a known-source control, not new
prospect discovery. Source-only releases exclude these live databases/reports.

## Remaining full-goal scope

This fixes a verified extraction loss in the actual pipeline. Representative
fresh US/UK buyer discovery, native personal-profile availability, authenticated
VPS behavior and Apollo/Apify-equivalent recall remain unproven. The original goal
is not marked complete or narrowed to this single successful company control.
