# From public evidence to a specific proposal

The desktop/mobile audit now checks the public enquiry journey as well as recording screenshots. It uses the existing DNS-pinned, robots-aware browser; forms are never submitted and non-GET browser requests remain blocked.

## What it can establish

- Two stable samples at each viewport identify visible business enquiry fields with no attached text label, ARIA name or title. Hidden, disabled, read-only and newsletter-only controls are excluded. Proposed work: add connected persistent labels and check keyboard/mobile use.
- Repeated document overflow produces a scoped layout finding. Proposed work: inspect the responsible layout, adjust width/wrapping and preserve intentional scrolling components.
- Up to three relevant public same-domain links receive bounded GET checks. HTTP 404/410 is citable only after two matching results. Redirect hops are checked against robots and domain constraints; queries, action endpoints, denials, timeouts and transient errors do not become broken-link claims.
- At most two reachable linked pages receive additional desktop/mobile captures, so a contact form need not be on the homepage. Total supplementary work has a 120-second budget; completed evidence is retained on interruption.

These checks extend, rather than replace, Lighthouse observations. An enquiry-link failure ranks above layout/label observations and generic speed scores. Every accepted finding contains its source URL, exact DOM selector or HTTP proof, saved screenshot, proposed implementation, intended benefit and a repeat test. Evidence is scoped to the capture, not a claim about lost sales or actual visitor behaviour.

A low aggregate score alone no longer enables an improvement pitch. A specific supported insight or underlying paint/blocking/layout-shift measurement is required before proposing a matching fix.

## Automatic workflow

`JOURNEY_AUDIT_ENABLED=true` is the default. Existing automatic visual audits include these checks. For a new website prospect with a published contact, preparation can queue the audit before calling the writer. It resumes after the research job finishes; the dashboard polls through this stage.

There is one automatic attempt per source cycle, preventing failed captures from creating a retry loop. Explicit desktop/mobile audit remains available for an operator retry. Disabled browser/visual-audit settings remain respected. Existing drafts and human edits are preserved.

The writer must use the strongest supplied journey finding, explain a matching concrete repair and ask one small next-step question. A score-only or audit-only response cannot displace that finding. Proof previews can embed the matching local screenshot. Failed, stale, changed-cycle or out-of-domain evidence is not citable.

## Boundaries

This is a bounded public-page diagnostic, not comprehensive visual design judgment, a submitted booking/checkout test or conversion analytics. A JS-only modal or inaccessible third-party widget may remain untested. If no supported issue is found, the system holds an improvement pitch instead of inventing a problem. Calling, chatbot and other opportunities still need their own business evidence.

Tests cover repeated versus unstable captures, labelled/hidden/newsletter controls in Chromium, HTTP confirmation and redirects, scope/freshness, automatic audit scheduling and retry limits, stronger-finding copy validation, and an actual mediated browser capture through an enquiry page into a screenshot-backed proof preview. No live external message or recipient probe is part of these checks.
