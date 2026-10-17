# Second workflow: service selection and proof of value

Checked on 11 October 2026 against the user's second diagram. **All 15 diagram nodes have executed behavioral checks.** Campaign A/B and all eight campaign/service combinations pass in isolated fixtures. The final full suite passed **356 tests in 102.24 seconds**, with one existing dependency warning. Chromium submitted actual qualification/artifact forms on desktop and mobile, checked both WhatsApp routes, and reported zero JavaScript errors.

This establishes implemented selection/review behavior. It does not establish a client-confirmed goal, real customer permission, a deployed assistant/store/WhatsApp integration or conversion uplift. The normal database still contains six unqualified candidates, zero selected current offers and zero reviewed current value artifacts. Its records and private configuration were unchanged by the read-only check.

## Node-by-node check

| Node from the diagram | Implemented behavior and executed check | What remains human or live |
|---|---|---|
| Qualified prospect + evidence | `offers.selected_offer` requires one reviewed finding, an allowed campaign service, current/fresh quote and country source. Stale D2C model evidence invalidates selection even if the other finding is fresh. | Actual identity, activity and buyer relevance require operator review. Current real candidates do not pass this entry gate. |
| Primary business goal | Review records the acquisition objective; a goal inconsistent with Campaign A/B is rejected. The UI shows its saved review state. | This target is not a client-confirmed commercial goal; later sales qualification records that conversation. Legacy reviews without an explicit goal remain “needs review” at this node. |
| Campaign A | Only website build/improvement and chatbot offers are accepted. The A fixtures select the inquiry/booking branch. | Choosing a target does not prove a pain point or predicted gain. |
| Campaign B | Current product/business-model quote, D2C fit notes and selling/launch stage are mandatory. Unknown/non-D2C stages and invented/cross-company sources are rejected. | Product ownership and the actual direct selling process must be reviewed. A shopping button alone is insufficient. |
| Website / new service page | New-service fixture selects `website_build`; source-backed concept can be created and reviewed. Existing profile-only tests cover completed no-match searches and website launch selection. | “Website not found” retains search uncertainty; no automatic absence claim or finished website. |
| Existing journey improvement | Inquiry fixture selects `website_improvement` and a sourced audit. Quotes and proposed tests stay separate. | Visible invitation is not proof of friction or lost conversions. Screenshot callouts require a saved company image and human visual inspection. |
| Inquiry / booking chatbot | Campaign A FAQ fixture selects `chatbot`; approved-excerpt FAQ artifact preserves a route to the team. Profile customer-question signals can also propose this offer after a no-match website search. | FAQ artifact is a prototype, not deployed AI, booking integration or helpdesk automation. |
| Starting ecommerce | `store_launch` requires the reviewed `starting_ecommerce` stage, D2C source and fit notes; launch concept fixture passes. | Launch intent and checkout/delivery/support requirements need confirmation. |
| Already selling online | `store_improvement` requires `selling_online`; mismatched launch stage is rejected. Product-journey audit fixture passes. | Actual checkout and private metrics were not exercised on a real store. |
| Shopping / support chatbot | Campaign B support fixture selects `chatbot` with the D2C gate and source-backed FAQ prototype. | Support volume, approved knowledge, handoff and integrations need discovery. |
| WhatsApp fits customers and permission setup? | Separate operator-recorded channel-fit and permission statuses persist. Four combinations of unknown/confirmed statuses select the appropriate branch. `not_suitable` rejects WhatsApp as the primary offer. | A public link never auto-confirms customer permission. Confirmation is an operator record, not a platform or consent-list verification. |
| WhatsApp marketing / automation | Both services are independently tested. Confirmed fit has its own status; unknown fit/permission produces an explicitly qualification-first outline. | These are acquisition offers and planning artifacts. No customer messages, Meta account connection or real recovery/retention journey was executed. |
| Qualify channel and opt-in first | Either unknown status selects `needs_qualification`; both confirmed statuses bypass this unknown branch. UI shows the distinction. | Confirm current messaging requirements, eligible events, customer permissions, timing and economics before implementation. |
| Choose ONE primary offer | Qualification atomically stores one selected service and one finding. Re-selection invalidates unsent drafts and older artifact context. Source suggestions remain alternatives until reviewed. | All five sourced B suggestions can now be compared; the software does not silently mark several offers selected. |
| Prepare relevant proof of value | Eight branch fixtures create/approve the relevant audit, concept, FAQ or WhatsApp outline. Actual browser forms exercise A/B creation, download and review. Source snapshots are checked before draft commit and approval. | Value output requires human review before sharing. Its preparation/review is not a completed client project or actual external delivery. |

## Defects found and corrected

Two negative regressions initially failed: a new artifact could reuse a page from before the latest failed research, and an artifact could be approved after its source changed. Both now pass. Artifact points and FAQ answers require current sources no older than 30 days; a source/offer snapshot is saved with the draft and rechecked transactionally at creation and approval. Sources changed during preparation, expired captures and legacy drafts without proof are held. Historical exports and actual recorded deliveries remain preserved.

The qualification form previously populated only the first suggestion. It now exposes each current sourced offer and fills that offer's service, evidence, quote, observation and suggestion together. All five possible Campaign B offers are retained instead of truncating the last two. D2C evidence and selling stage are explicit fields; WhatsApp channel/permission statuses default to unknown. The selected company's detail panel shows the second diagram's 15 statuses and suitable artifact types.

Older approved artifacts whose source or selected offer changed retain their historical state, but the UI labels them for re-creation before sharing again. They do not count as current reviewed proof of value. Old Campaign B qualifications without the new model review need re-review before new drafts/approval. No database schema migration or credential replacement was required.

## Executed evidence

- `tests/test_second_workflow.py`: **34 new cases**, including all eight service combinations, both WhatsApp branches, invalid model/goal/stage checks, one-offer re-selection, current source preservation and artifact race/freshness holds.
- Existing profile, opportunities, qualification, deliverables and workflow-map cases also pass. Focused intermediate run: 102 passed; final suite: 356 passed. Ruff and JavaScript syntax checks pass.
- `scripts/verify_second_workflow_ui.py`: isolated fictional database and actual Chromium form submissions. It checks secondary A offer selection, five B choices, unknown/confirmed WhatsApp routes, artifact review and invalidation after context changes. No contacts, messages or jobs are created.
- Existing full `scripts/ui_smoke.py` also passes, including source qualification, artifacts, full workflow, sales controls, settings and credential flows in isolated demo data.
- `data/second-workflow-normal-check.json`: actual running dashboard on desktop/mobile. Sourced idea selection matches the evidence; D2C unknowns remain visible; all normal operational rows and private files are preserved. No action was queued or external message sent.

The four new fixture screenshots are labeled by their file names, not as real prospects. Actual normal-state screenshots are [desktop](screenshots/second-workflow-normal-desktop.png) and [mobile](screenshots/second-workflow-normal-mobile.png). [Machine-readable proof](second-workflow-check.json) separates fixture acceptance from normal-state holds.

To inspect: open **Pipeline → select a company → “2 · Match one useful offer”**, then **“02 · Qualify company & select one offer”**. Artifact creation/review is under **“Activity, next actions, calls and proposals → Prepare a promised audit, concept or demo”**.
