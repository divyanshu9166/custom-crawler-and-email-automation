# Second workflow re-analysis — 19 October 2026

Initial audit scope (f98e936): compare the supplied service-selection/proof-of-value diagram
with code, controlled executions and read-only VPS records. The initial audit did not modify
production records or call the AI provider. The implementation update below records the
subsequent fixes separately. Nothing in this work authorizes or sends outreach.

## Node-by-node mapping

| Diagram node | Current implementation | Verdict / practical limit |
| --- | --- | --- |
| Qualified prospect + evidence | Current quote, country and qualification checks in selected_offer | Record qualification exists; it does not establish a client-confirmed need |
| Primary business goal | Campaign A/B maps to inquiries_bookings/d2c_growth; mismatched review rejected | Goal is selected/reviewed by operator or AI, not confirmed by the prospect |
| Campaign A | website_build, website_improvement, chatbot supported | Routing works in controlled tests |
| Needs website / new service page | Profile-only exceptions and manual website_build review available | Automatic _validate_review rejects website_build on all website prospects, including a valid new-service announcement |
| Visible friction -> website improvement | Current quote and selected service checked; diagnostics now reach writer | Offer selection does not require verified friction; Spotless selects improvement while having zero established technical observations |
| Choosing/booking help -> chatbot + handoff | Question/FAQ signals can propose chatbot; existing chatbot cues stop blanket auto replacement | No automatic demonstration of buyer confusion, complete bot interaction or deployed human handoff |
| Campaign B | Current ecommerce quote, selling stage and D2C fit review required | Controlled route coverage; VPS currently has no Campaign B prospects |
| Starting ecommerce | store_launch requires starting_ecommerce | Stage mismatch rejected; live launch acceptance not demonstrated |
| Already selling online | store_improvement requires selling_online | Stage mismatch rejected; checkout/cart interaction and actual abandonment not measured |
| Product/support questions -> shopping chatbot | Campaign B chatbot route and FAQ prototype | FAQ prototype is exact-quote HTML interaction, not a running shopping AI assistant |
| WhatsApp fit + permission | unknown/confirmed/not_suitable states stored separately | An operator's confirmation is a review record, not automatically verified customer permissions |
| Confirmed-fit WhatsApp offer | Confirmed channel and permission produce confirmed_fit | Planning outline exists; no live customer messaging integration implied |
| Unknown -> qualify first | Snapshot flags qualification_only and qualification-first artifacts | Writer packet currently omits offer_context and channel_fit_notes, so it cannot distinguish unknown from confirmed statuses |
| Choose ONE primary offer | One reviewed finding and matching service/campaign enforced | Works structurally; appropriate business need is not proved merely by one selected service |
| Prepare relevant proof of value | Audit, concept, FAQ and WhatsApp HTML artifacts; source snapshots and review/export actions | Assisted/manual creation; not automatically required before email drafting; zero artifacts on VPS |

## Reproduced mismatches

1. In an isolated temporary database, identical WhatsApp prospect/source/review records were
   qualified first with both statuses unknown and then both confirmed. offer snapshots changed
   qualification_only from true to false. research_packet outputs were exactly identical and
   contained no customer_permission_status. This is a writer-context propagation regression;
   it does not prove an unsafe email was sent or that any real customer permission exists.
2. A current, quoted new-service announcement with valid Campaign A inputs was passed to the
   actual automatic review validator. It returned: “An existing official website needs a supported
   improvement offer, not an absence pitch.” The combined no-website/new-page node therefore
   has a manual/automatic mismatch.
3. Live Spotless snapshot: website_improvement selected, primary_offer complete, value_artifact
   needs_artifact_review, approved artifact IDs empty. Its earlier diagnostic snapshot had zero
   established observations. This is an exploratory opportunity, not verified visible friction.

## Live scope

All three VPS prospects are Campaign A. Only Spotless currently has a selected primary offer;
Blaze and NuServe remain needs_review. deliverables and proposals are both empty. Sending is
OFF and sent-message count is zero. No Campaign B or proof-of-value production acceptance is
established by this dataset.

## Validation and proposed order

58 existing second-workflow, offer-source-quality and deliverable tests passed in 12.54 seconds,
with one existing Starlette/httpx deprecation warning. These tests prove their current checked
contracts; the additional controlled executions above expose requirements not covered by them.

The missing decision before service selection is evidence strength: identify a measured issue,
an exact publicly reported need or an exploratory opportunity. A source-backed generic inquiry
invitation must not be relabelled as visible friction. Keep unknown channel fit/permission on a
qualification-only path. Select one offer, prepare/review one relevant artifact when promised,
then supply the typed context and artifact state to the single-email writer. Preserve the
separate labels for observed fact, hypothesis and unknown client priority.

Priority order for subsequent implementation: restore typed WhatsApp/stage context to the
writer without restoring unverified narrative summaries; separate website build from a new
page on an existing website; distinguish verified observations from exploratory offer selection;
and define/implement the intended automated proof-of-value preparation step.

## Implemented corrections

- Offer snapshots and the focused workspace now distinguish `measured_observation`,
  `exploratory_opportunity` and `insufficient_evidence`. Failed/partial/stale audits cannot
  create a measured finding, and a generic contact link alone cannot select an offer. A
  measurement still does not establish revenue loss, client priority or confirmed pain.
- `website_build` on an existing website now means `new_service_page` and requires a
  current exact service-announcement quote. A website-launch/absence pitch remains invalid
  for an existing official website. Reviewed profile exceptions retain search uncertainty.
  This scope is inferred from evidence, without adding another required user question.
- The writer receives only typed goal, stage, scope and channel-status fields, plus validated
  exact commerce-source quotes. Free-form qualification/observation summaries remain excluded.
  Unknown WhatsApp customer fit or permission requires a qualification-first question;
  implementation pitches without that qualification are rejected. Operator confirmation is
  a review record, not automatically verified permission. Edited copy receives this check at
  approval too.
- Email creation automatically prepares one relevant, unsent value preview: an assessment
  plan, proposed page/store concept, exact-source FAQ prototype or qualification-first
  WhatsApp outline. Its facts come from exact source quotes and current audit observations,
  not historical model summaries. These previews do not claim completed implementations.
- Preview creation is idempotent and preserves edited email copy. Preview hashes, source
  hashes, selected offer and audit snapshots are checked during generation and approval.
  Changed/expired inputs invalidate the preview. The writer receives actual local preview
  metadata; it cannot treat a local draft as delivered or attached.
- The normal workspace shows the evidence category and an expandable sandboxed preview
  next to the single email. Legacy draft backfill has one optional action and never rewrites
  the email. The workflow map counts reviewed proof per prospect rather than requiring every
  historical/automatic draft iteration to be approved.

Regression coverage includes all eight A/B service routes, unknown/confirmed WhatsApp packet
differences, correction of an invalid implementation pitch, new-service-page routing, partial
audit handling, stale/tampered/concurrently changed previews, exact edited-email preservation,
and desktop/mobile rendering. Production deployment acceptance is recorded after verification.

## Verification and deployment checks

The latest executed results cover 1,364 unique tests with no unresolved failures. This is a
consolidated report from the full-suite run and focused post-fix reruns, not a claim that a
single untouched run passed every revision. The full run passed 1,353 cases and exposed one
outdated expectation that no artifact existed after drafting; that assertion was corrected
to check an unsent draft preview, then re-executed successfully. Final writer/source/audit
regressions passed 110 cases. All 35 node mappings were checked against the consolidated
JUnit report at `data/offer-gap-verified-tests.xml`. Ruff and JavaScript syntax checks passed.

Real Chromium desktop/mobile checks and the broader browser smoke passed, including the
sandboxed preview, one email editor, draft save, collapsed advanced tools, no horizontal
overflow, and no JavaScript errors. These checks use isolated fictional records.

App code through `a27a19a` was pushed and deployed on the VPS. Spotless has one current,
unsent audit/test-plan preview (artifact 1), with `exploratory_opportunity` and `preview_ready`
states. No technical defect or client-confirmed pain was established. Its original edited
email remained byte-for-byte unchanged: the message snapshot digest before and after the
preview backfill was `31767e5d0ecbc21879e25f6482585f9c0e0d61f4f8e76978cdcb33e072f01307`.
Sending and follow-ups stayed OFF, the worker stayed ON, and the sent-message count stayed
zero. n8n and PostgreSQL remained running. A private SQLite backup was taken before changes.

Live Nemotron samples on isolated copies exposed additional wording defects. The deployed
writer now rejects unsupported sender experience, buyer-behaviour claims, operational
deductions from company size, and internal capture-failure/data-availability wording. Failed
audit reports remain available in Operations and provenance; only established observations
are supplied to the writer. Local validation is a guardrail, not universal semantic proof;
the final recipient and wording review remains required. No test sample replaced the saved
email or was sent to the prospect.

The final deployed Nemotron check returned a validated single-email sample on an isolated
copy. It cited the published team size and quote invitation, proposed testing with an explicit
target audience, and stated that the aim was to find out whether friction exists before making
changes. It did not invent sender case studies, assert an existing client defect, infer inquiry
volume, or expose capture failures. The saved message digest remained unchanged and sent
count remained zero. This is a successful bounded sample, not a guarantee of every future
model response. The app and public tunnel health checks returned HTTP 200.

External limits remain separate: successful PageSpeed requests need available provider quota;
the existing failed HTTP 429 runs provide no score. Platform access and actual client outcomes
are not made complete by these code changes. A prototype is not a deployed integration.
