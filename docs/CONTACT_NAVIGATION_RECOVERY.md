# Bounded contact-navigation optimization — 14 October 2026

This implements one confirmed crawler gap, rather than another open-ended
platform-access project. It does not claim a LinkedIn bypass or vendor parity.

## Reproduced problem

`retain_http_publications` previously kept the original HTTP capture only when
it added contacts, named staff or professional-profile links. An email-free
homepage could publish contact/team navigation in HTTP, then remove it during
JavaScript rendering. The crawler discarded those routes before ever visiting
the pages where the emails were published. Sitemap/search fallback could mask
the loss but did not fix it.

Two before-fix regressions failed: a direct capture comparison lost both routes,
and actual `research_lead` with real Chromium fetched only the homepage in a
controlled three-page/no-sitemap run. The fictional homepage had no email.

## Implemented behavior

- Preserve additional explicitly published same-company contact/team/about/staff
  routes even when the homepage itself has no contact publication.
- Validate routes through the existing company/contact-route rules. External,
  private/account, editorial/catalog and download routes cannot trigger this
  navigation-only recovery. No URL or email pattern is generated.
- Keep the original HTTP and DOM hashes, labelled source text and a composite
  digest. Withdrawal of a route changes the proof; captures from different URLs
  are never joined. Name/email scope rules remain unchanged.
- Record recovered HTTP navigation in normal and contact-recovery crawl reports.
  Queue deduplication uses sets; robots, depth/page budgets, cooldowns and durable
  checkpoints still govern actual target-page fetching.
- A link alone creates no email contact. Recipient publication must come from
  the fetched contact/staff page, with the existing ownership/verification gates.

## Verification and practical boundary

In the same controlled Chromium pipeline, the outcome changes from **one saved
page / zero contacts** to **three saved pages / two published unverified contacts**.
When robots denies the contact page, it is never fetched and only the permitted
staff-page contact is saved. These are fictional intercepted documents and
isolated databases, not newly acquired clients or proof of live-platform recall.

The focused navigation/publication/resume/optimization suite passed **52 tests in
38.65 seconds**. Twelve new regression cases cover loss/withdrawal, scope, excluded
routes, publication and robots behavior. Ruff and compilation passed. Final
complete-suite, preview and source-release checks are recorded in VALIDATION.md.

No operational lead import, real recipient probe, account login or message was
performed. Native LinkedIn restrictions, actual VPS throughput and consistent
qualified-buyer discovery remain separate acceptance work. This change stops at
the reproduced navigation gap; further changes need measured failures or yield.

The final complete suite passed **1073 tests in 333.65 seconds**, with the existing
Starlette/httpx warning. The corrected normal preview passed health/authenticated
status HTTP 200 after restart, with an unchanged operational database, no active
jobs and sending disabled/paused. The source-only release includes this audit and
the corrected crawler; ZIP integrity and SHA-256 are checked during packaging.
