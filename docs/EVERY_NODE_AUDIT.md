# Every-node acquisition workflow audit

**Email-writing boundary:** tests use controlled AI/provider fixtures; they do not establish live model quality or mailbox delivery. AI preparation is optional and source validated; final recipient/message approval stays manual. No template fallback. See [automatic preparation](AUTO_PREPARATION.md).

Latest recheck: **35 / 35 nodes mapped to actual source and passing executed tests**. Executed checks: **1364 passed**.

The implementation is present for every node, with deliberate human gates. This does **not** mean all nodes are fully automatic or verified against real providers/clients. The dashboard supports eleven overview stages and all thirty-five detailed nodes with source/ownership, branch, hold and operator-recorded statuses.

## What this audit corrected

- Approval status cannot combine drafts, qualification and safe verification from unrelated prospects.
- Manual reply/closed status is not evidence of prior sequence approval; use recorded approval timestamp.
- Terminal research/audit job failures remain visible even with preserved reviewable partial evidence.
- Fresh-safe count excludes suppression and stale profile/other-domain ownership.
- Stale inbox catch-up does not show running monitoring; worker must also be enabled.
- Terminal recorded sales journey with no open tasks is complete instead of permanent needs-review.
- Unqueued new research is ready; partially qualified aggregate is not complete; latest jobs ordered deterministically.

Six new regression cases reproduced six status defects before the fixes (6 failed / 4 passed). The ten workflow-map tests pass afterward. These were visibility/calculation defects; the underlying approval/send gates were independently enforced.

## Latest recheck and diagram differences

Re-ran the complete suite for the user-supplied diagram. A provider-readiness defect was found: the configured local port 8080 serves another service, whose root responds HTTP 200. Preflight now checks Reacher invalid-syntax handling and header authentication instead of accepting root HTTP success. Four regressions cover the wrong service, unknown schema, authenticated syntax rejection and bounded retry. No valid recipient is submitted by this check.

- CSV import goes directly to company website research (A → C); only search queries use B. The diagram should not imply that CSV import requires a search provider.
- CE candidates can be captured during CS, before CR review. They remain held until CR/E3 ownership and qualification gates pass.
- Qualification and technical verification are independent branches; both must pass J. H is distributed across held states, not a separate single work queue.
- R commercial-intent classification and S–Y client actions require an operator. The sales portion is a managed business process, not a mandatory linear automation that books calls, delivers proposals, verifies payments or deploys client services. A call or value artifact is recorded when actually agreed/promised; confirmed need and reviewed proposal delivery guard the later sales stages.
- Full workflow now displays all thirty-five nodes and forty-six connections, while Overview retains eleven grouped stages. Inspect stage and Focus next reveal status, execution mode, conditional routes and action destination. Reading or dragging cannot trigger an operation.

## Every node

| Node | Process | Execution | Verified behavior and boundary |
|---|---|---|---|
| A | US/UK search queries or sourced CSV | automatic | Queries include US/UK context; CSV imports sourced website records. Profile-only records use discovery/profile form, not website-only CSV import. **Boundary:** Search/import live locally; discovery country is an unconfirmed hint. |
| B | SearXNG or optional SerpApi | automatic | SearXNG JSON and optional SerpApi adapter; failed engines are retained as limitations. **Boundary:** Native SearXNG used live; engine blocks/CAPTCHAs observed. Optional paid SerpApi not live validated. |
| C | Official company website · domain deduplication | automatic + review | Domains deduplicate; profile links/name/reciprocal links produce candidate matches, not verified owners. **Boundary:** A matched official website was researched; identity and buyer fit still need review. |
| CP | Business profile · no known website | automatic | Specific business profile retained with empty website and internal identity key; no fake company domain. **Boundary:** Live LinkedIn record routed to an existing website; actual website-less acquisition not yet accepted. |
| CS | Public snapshot and named-company website search | automatic | Robots-permitted profile capture and named-company lookup; matched website creates/reuses a deep-research record. **Boundary:** Live lookup matched IMAGE Skincare UK; LinkedIn capture robots-denied. No private-platform scraping. |
| CR | Review profile identity, activity and search limits | review | Exact current activity/country quotes, ownership notes and search-limit acknowledgment required. Not-found does not mean confirmed absent. **Boundary:** Verified with fictional captured profiles; real profile identity acceptance pending. |
| CE | Published profile email candidate · no automatic probe | automatic extraction + review | Captured published emails stay candidates; import/probe blocked until profile qualification and inbox ownership review. Candidates can be captured before CR; the later gates still apply. **Boundary:** No real profile email acquired/probed in current live record. |
| D | Robots + sitemaps + HTTP + Chromium | automatic | Robots, sitemap/depth/page budgets, mediated HTTP and sandboxed JS rendering; report partial or failed coverage. **Boundary:** Real 30-page Chromium research completed with partial coverage; broader 50-domain audit contains partial/failing sites. |
| E | Saved evidence · recent public signals · sourced contacts | automatic + review | Persist URL, text, hashes and contact identity; only current captures support new ideas. Explicit public signals propose relevant services without an AI key; optional AI can suggest more. Weak/negative cues stay needs-review; every exact quote and interpretation requires review. **Boundary:** Current real website pages yielded matching store/support proposals in a read-only preview; actual pain points, buyer relevance and recent announcements require interpretation/review. |
| E1 | Company-domain contacts | automatic | Published same-domain addresses are imported and verification queued; buyer role and eligibility remain separate. **Boundary:** Two published website contacts captured; neither established fresh safe. |
| E2 | Other-domain published candidates | automatic candidate capture | Other-domain addresses are held with current source URL/hash; no automatic provider probe. **Boundary:** One live website candidate retained; no automatic import. |
| E3 | Review current official source and company ownership | review | Ownership notes plus current official extraction required; re-crawl/source changes invalidate proof; cross-company inbox attachment rejected. **Boundary:** Fictional reviewed contacts tested; current real candidate remains held. |
| F | Reacher verification | automatic / broader provider acceptance pending | Strict response/address checks; unknown/risky/catch-all/disposable/invalid cannot pass. Current source, recipient and suppression checked before dispatch and before committing a result. **Boundary:** Native backend/API/auth passed. The earlier isolated recipient was catch-all/risky; a new officially published florist contact received a real safe/non-catch-all verdict. One verdict does not establish universal existence, broader accuracy or inbox delivery; no outreach sent. |
| G | Review saved country quote, buyer and one opportunity | AI preparation + exception/final review | AI preparation validates current source quotes, US/UK country/timezone and one offer; manual editing remains available. Unsupported inputs stay held; buyer/recipient judgment and final messages still require operator review. **Boundary:** Actual current businesses not qualified by this audit; quote validity alone does not establish semantic truth. |
| Q | Desktop/mobile screenshots · optional PageSpeed lab audit | automatic optional audit | Desktop/mobile screenshots and optional on-demand PageSpeed; no profile-only site audits and no invented scores. **Boundary:** Real screenshots exist. Keyless PageSpeed live requests returned HTTP 429; no successful live lab score established. |
| H | Hold · inspect or research further | automatic hold + review | Hold is represented by lead/profile/contact/message states, not a single unified queue. Uncertain sends require reconciliation; blocked sources and unsafe verification cannot send. **Boundary:** Current verification/profile failures visible; human resolution or provider availability required. |
| AA | Campaign A · website or inquiry/booking chatbot | automatic proposals + reviewed selection | Campaign A proposes build/improvement/chatbot from public inquiry/service/support cues; one final offer is reviewed. Profile-only improvement excluded. **Boundary:** Fixed cue ranking is not a prediction of client value, sales likelihood or conversion uplift. |
| BB | Campaign B · ecommerce or suitable WhatsApp workflow | automatic proposals + reviewed selection | Campaign B proposes launch/improvement/chatbot/WhatsApp from source cues; channel-fit, permission/integration and one relevant offer still require review. **Boundary:** No live WhatsApp sending or client store integration is performed by this acquisition software. |
| I | Source-backed personalized draft + 3 follow-ups | AI preparation and writing; final message review | One editable initial email by default, one relevant offer, source references and a current local proof preview. Follow-ups require explicit opt-in; activated content cannot be overwritten. **Boundary:** Historical templates are offline samples only. The current AI writer requires its own configured endpoint and model-quality acceptance; no live AI/provider or recipient acceptance claimed. |
| J | Review all messages and outreach eligibility | review gate | Review the initial email (and all explicitly enabled legacy follow-ups), sender identity, qualification, fresh safe proof, relevance/eligibility notes, opt-out and company conversation gate. **Boundary:** No real sequence approved. Current source findings and eligibility require operator judgment. |
| K | Approve · local send window · mailbox quota | approval + automatic scheduling | Atomic approval; one conversation/company; local weekday/hour window, daily quota and minimum send gap. **Boundary:** Simulated calendars and isolated transport verified; deployed timezone/quota acceptance pending. |
| L | SMTP send · durable Message-ID | automatic / mailbox setup pending | TLS authenticated SMTP, durable IDs/threading, explicit acceptance versus uncertain outcome and no automatic uncertain retry. **Boundary:** Real socket protocols passed on loopback fixtures; external mailbox delivery/inbox placement unverified. |
| M | Independent IMAP monitoring | automatic / mailbox setup pending | Independent mailbox lane, bounded read-only IMAP, UID/identity idempotency and freshness; long crawling does not block it. **Boundary:** Local protocol fixtures verified; no real mailbox credentials configured. |
| N | Next due follow-up · stop after touch 4 | automatic | Follow-ups are disabled by default. The opt-in legacy sequence uses gaps 3/5/6 days from actual acceptance with local-window adjustment and stops after touch 4; no overdue burst. **Boundary:** Loopback TLS test used both ordinary and delayed calendars; no real campaign sent. |
| O | Stop sequence · human conversation | automatic stop + human conversation | Human reply cancels future touches, creates fulfillment task and shared company hold; manual social replies can be recorded. **Boundary:** Fixture replies verified; the software does not autonomously negotiate with the prospect. |
| P | Global suppression | automatic | Opt-outs/permanent recipient failures suppress globally; unsubscribe GET is read-only and POST performs the stop. **Boundary:** Fixture events/protocol verified; production HTTPS unsubscribe endpoint still requires deployment. |
| R | Classify actual reply and fulfill promised value | operator review + automatic task | Transport classifies reply/auto-reply/opt-out/DSN. Commercial intent and promised-value fulfillment are operator notes/tasks/stages, not a trained automatic sales classifier. **Boundary:** No actual external reply fulfillment claimed. |
| S | Review audit / concept / FAQ / WhatsApp-flow artifact | automatic preview + final review | One automatically prepared source-backed discussion preview for the selected offer; optional annotated screenshot and manual artifacts. Review/export and actual-delivery reference stay separate; no automatic delivery. **Boundary:** Actual Chromium inspected fictional exports. Concepts/FAQ/WhatsApp outlines are prototypes, not deployed client services. |
| T | Confirm problem, buyer, budget, timing and success metric | operator-recorded | Confirmed problem, goal, buyer, timeline, budget and success metric required; a real conversation record gates advancement. **Boundary:** External buyer confirmation cannot be independently verified by these fixture tests. |
| U | Record agreed call and dated next action | operator-recorded | Record agreed call timestamp and dated next action/tasks. This does not book a calendar or send an invitation. **Boundary:** No actual booking/calendar integration performed. |
| V | Prepare and review scoped proposal | assisted creation + review | Qualified client need, scope, deliverables, exclusions, acceptance, timeline, terms and USD/GBP fee create reviewed downloadable proposal. **Boundary:** Proposal fixtures reviewed; human scope/commercial acceptance required. |
| W | Record actual proposal delivery | operator-recorded | Delivery requires reviewed proposal and explicit actual-delivery reference; not automatic SMTP proposal delivery. **Boundary:** No real client proposal sent by this audit. |
| X | Record agreement and initial payment references | operator-recorded | Won/delivery/completed require agreement and initial-payment references; no payment processor or signature collection. **Boundary:** References are operator assertions, not verified receipts or signed documents. |
| Y | Manage delivery tasks and record client acceptance | operator-recorded task management | Delivery tasks and closure outcomes; completed stage requires client acceptance reference. No automatic client website/WhatsApp deployment. **Boundary:** Actual client delivery and acceptance remain external. |
| Z | Record measured or inconclusive outcome and campaign learning | operator-recorded + automatic descriptive learning | Outcome notes can be inconclusive. Learning reports frozen campaign/service/country/industry groups, accepted-record-to-human-reply/qualified/recorded-won rates and next-review guidance. No denominator means unknown; repeats and auto-replies cannot inflate conversions. Recorded USD/GBP cost and receipt reports remain separate, with immutable correction history. Completed clients can have dated maintenance/expansion plans and permission-reviewed frozen case studies; external work/publication remains operator-recorded. **Boundary:** No automatic analytics attribution, A/B optimization, verified revenue or evidence of conversion uplift. Historical contexts missing an approval snapshot remain unknown. |

## Source and executed test evidence

### A — US/UK search queries or sourced CSV

Source: [outreach/app.py:660 — import_csv](../outreach/app.py), [outreach/discovery.py:494 — prospect_candidates](../outreach/discovery.py)

- [test_api_import_detail_and_export](../tests/test_api.py) — 1 executed passing case(s), function line 23.
- [test_market_selection_scopes_search_and_locale](../tests/test_platform_discovery.py) — 2 executed passing case(s), function line 152.

### B — SearXNG or optional SerpApi

Source: [outreach/providers.py:131 — discover](../outreach/providers.py)

- [test_search_contract](../tests/test_research.py) — 1 executed passing case(s), function line 146.
- [test_failed_platform_queries_do_not_discard_successful_official_results](../tests/test_platform_discovery.py) — 1 executed passing case(s), function line 70.

### C — Official company website · domain deduplication

Source: [outreach/research.py:13 — add_lead](../outreach/research.py), [outreach/discovery.py:294 — resolve_signal](../outreach/discovery.py)

- [test_company_and_contact_dedup_preserves_suppression](../tests/test_research.py) — 1 executed passing case(s), function line 53.
- [test_multi_platform_discovery_persists_signals_deduplicates_and_queues_research](../tests/test_platform_discovery.py) — 1 executed passing case(s), function line 36.

### CP — Business profile · no known website

Source: [outreach/profiles.py:72 — add_profile_lead](../outreach/profiles.py), [outreach/research.py:363 — discover_leads](../outreach/research.py)

- [test_profile_discovery_imports_deduplicates_but_never_probes](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 69.
- [test_profile_api_no_fake_website_and_visual_audits_rejected](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 139.

### CS — Public snapshot and named-company website search

Source: [outreach/profiles.py:102 — research_profile](../outreach/profiles.py), [outreach/discovery.py:74 — public_snapshot](../outreach/discovery.py), [outreach/discovery.py:294 — resolve_signal](../outreach/discovery.py)

- [test_found_website_routes_to_normal_research_without_merging_contacts](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 110.
- [test_failed_website_search_is_not_absence](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 99.
- [test_robots_denial_never_fetches_profile](../tests/test_platform_discovery.py) — 1 executed passing case(s), function line 58.

### CR — Review profile identity, activity and search limits

Source: [outreach/campaigns.py:46 — review_lead](../outreach/campaigns.py), [outreach/profiles.py:90 — assert_profile_review](../outreach/profiles.py)

- [test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate](../tests/test_profile_prospects.py) — 2 executed passing case(s), function line 46.
- [test_ambiguous_or_blocked_profile_cannot_be_qualified](../tests/test_profile_prospects.py) — 2 executed passing case(s), function line 85.

### CE — Published profile email candidate · no automatic probe

Source: [outreach/profiles.py:102 — research_profile](../outreach/profiles.py), [outreach/research.py:140 — add_contact](../outreach/research.py)

- [test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate](../tests/test_profile_prospects.py) — 2 executed passing case(s), function line 46.
- [test_profile_discovery_imports_deduplicates_but_never_probes](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 69.

### D — Robots + sitemaps + HTTP + Chromium

Source: [outreach/web.py:277 — crawl](../outreach/web.py), [outreach/browser.py:90 — render](../outreach/browser.py)

- [test_sitemap_index_prioritizes_contacts_and_preserves_partial_pages](../tests/test_crawler_quality.py) — 1 executed passing case(s), function line 378.
- [test_real_chromium_executes_spa_and_public_cdn_assets](../tests/test_crawler_quality.py) — 1 executed passing case(s), function line 409.
- [test_robots_denial_prevents_crawl](../tests/test_research.py) — 1 executed passing case(s), function line 80.

### E — Saved evidence · recent public signals · sourced contacts

Source: [outreach/research.py:213 — research_lead](../outreach/research.py), [outreach/web.py:681 — extract_page](../outreach/web.py), [outreach/providers.py:219 — research_suggestions](../outreach/providers.py), [outreach/opportunities.py:28 — proposals](../outreach/opportunities.py)

- [test_crawl_report_and_contact_identity_are_persisted](../tests/test_crawler_quality.py) — 1 executed passing case(s), function line 457.
- [test_recrawl_suggestions_exclude_unvisited_historical_pages](../tests/test_research.py) — 1 executed passing case(s), function line 126.
- [test_ai_rejects_invented_quote](../tests/test_research.py) — 1 executed passing case(s), function line 155.
- [test_no_ai_research_saves_current_signal_proposal_without_qualification_or_drafts](../tests/test_opportunities.py) — 1 executed passing case(s), function line 71.
- [test_insufficient_evidence_stays_empty_instead_of_inventing_friction_or_absent_features](../tests/test_opportunities.py) — 1 executed passing case(s), function line 60.

### E1 — Company-domain contacts

Source: [outreach/research.py:213 — research_lead](../outreach/research.py), [outreach/research.py:140 — add_contact](../outreach/research.py)

- [test_research_to_contacts_and_verification](../tests/test_research.py) — 1 executed passing case(s), function line 105.
- [test_extract_only_sourced_business_emails](../tests/test_research.py) — 1 executed passing case(s), function line 36.

### E2 — Other-domain published candidates

Source: [outreach/research.py:213 — research_lead](../outreach/research.py), [outreach/research.py:121 — contact_candidates](../outreach/research.py)

- [test_external_published_addresses_are_candidates_not_automatic_contacts](../tests/test_contact_candidates.py) — 1 executed passing case(s), function line 21.
- [test_research_retains_candidates_without_importing_or_verifying_them](../tests/test_contact_candidates.py) — 1 executed passing case(s), function line 28.

### E3 — Review current official source and company ownership

Source: [outreach/research.py:140 — add_contact](../outreach/research.py), [outreach/research.py:97 — assert_contact_ownership](../outreach/research.py)

- [test_alias_contact_requires_source_and_ownership_then_remains_unverified](../tests/test_contact_candidates.py) — 1 executed passing case(s), function line 45.
- [test_recrawl_without_alias_page_invalidates_old_proof_but_preserves_history](../tests/test_contact_candidates.py) — 2 executed passing case(s), function line 153.
- [test_stale_ownership_holds_approved_sequence_before_smtp](../tests/test_contact_candidates.py) — 1 executed passing case(s), function line 211.

### F — Reacher verification

Source: [outreach/research.py:421 — verify_contact](../outreach/research.py), [outreach/providers.py:190 — verify_email](../outreach/providers.py), [outreach/providers.py:166 — classify_reacher](../outreach/providers.py)

- [test_reacher_adapter_contract](../tests/test_research.py) — 1 executed passing case(s), function line 91.
- [test_reacher_contradictions](../tests/test_research.py) — 4 executed passing case(s), function line 19.
- [test_reviewed_profile_contact_can_verify_and_queue_with_all_existing_gates](../tests/test_profile_prospects.py) — 1 executed passing case(s), function line 154.

### G — Review saved country quote, buyer and one opportunity

Source: [outreach/preparation.py:229 — prepare](../outreach/preparation.py), [outreach/preparation.py:158 — _validate_review](../outreach/preparation.py), [outreach/campaigns.py:46 — review_lead](../outreach/campaigns.py), [outreach/priorities.py:9 — ranked](../outreach/priorities.py)

- [test_prepare_runs_real_writer_contract_and_leaves_all_messages_unsent](../tests/test_preparation.py) — 1 executed passing case(s), function line 119.
- [test_unsupported_assessments_stay_held_without_drafts](../tests/test_preparation.py) — 12 executed passing case(s), function line 152.
- [test_priority_read_only_explainable_recrawl_and_suppression_reduce_readiness](../tests/test_growth_finance_priority.py) — 1 executed passing case(s), function line 97.
- [test_active_sequences_are_not_ranked_as_new_outreach_work](../tests/test_growth_finance_priority.py) — 1 executed passing case(s), function line 141.
- [test_country_evidence_must_match_saved_source](../tests/test_requirements_audit.py) — 2 executed passing case(s), function line 24.
- [test_review_rejects_sources_not_refreshed_in_latest_crawl](../tests/test_requirements_audit.py) — 4 executed passing case(s), function line 85.
- [test_sourced_trigger_and_extra_value_survive_into_drafts](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 49.

### Q — Desktop/mobile screenshots · optional PageSpeed lab audit

Source: [outreach/browser.py:349 — screenshot](../outreach/browser.py), [outreach/performance.py:9 — performance_audit](../outreach/performance.py)

- [test_authenticated_crawl_report_and_audit_images](../tests/test_api.py) — 1 executed passing case(s), function line 37.
- [test_pagespeed_preserves_lab_evidence_and_partial_results](../tests/test_performance.py) — 3 executed passing case(s), function line 23.
- [test_pagespeed_failure_never_creates_fake_score](../tests/test_performance.py) — 1 executed passing case(s), function line 47.

### H — Hold · inspect or research further

Source: [outreach/mail.py:95 — send_one](../outreach/mail.py), [outreach/mail.py:251 — record_inbound](../outreach/mail.py), [outreach/campaigns.py:369 — resume_contact](../outreach/campaigns.py), [outreach/profiles.py:90 — assert_profile_review](../outreach/profiles.py)

- [test_uncertain_send_is_never_automatically_retried](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 54.
- [test_resume_requires_fresh_result_and_cannot_override_optout](../tests/test_mail_providers.py) — 1 executed passing case(s), function line 85.
- [test_unsafe_reverification_holds_instead_of_looping](../tests/test_mail_providers.py) — 1 executed passing case(s), function line 75.
- [test_ambiguous_or_blocked_profile_cannot_be_qualified](../tests/test_profile_prospects.py) — 2 executed passing case(s), function line 85.

### AA — Campaign A · website or inquiry/booking chatbot

Source: [outreach/campaigns.py:46 — review_lead](../outreach/campaigns.py), [outreach/campaigns.py:176 — draft_sequence](../outreach/campaigns.py), [outreach/opportunities.py:28 — proposals](../outreach/opportunities.py)

- [test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate](../tests/test_profile_prospects.py) — 2 executed passing case(s), function line 46.
- [test_drafts_do_not_claim_completed_assets](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 147.
- [test_inquiry_offer_is_grounded_and_reviewed_without_claiming_an_observed_problem](../tests/test_opportunities.py) — 1 executed passing case(s), function line 14.
- [test_profile_launch_proposal_requires_completed_not_found_search](../tests/test_opportunities.py) — 2 executed passing case(s), function line 44.

### BB — Campaign B · ecommerce or suitable WhatsApp workflow

Source: [outreach/campaigns.py:46 — review_lead](../outreach/campaigns.py), [outreach/campaigns.py:176 — draft_sequence](../outreach/campaigns.py), [outreach/opportunities.py:28 — proposals](../outreach/opportunities.py)

- [test_campaign_b_rejects_non_d2c_website_offer](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 29.
- [test_whatsapp_requires_recorded_channel_fit](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 35.
- [test_whatsapp_flow_requires_qualified_channel_and_artifacts_require_auth](../tests/test_deliverables.py) — 1 executed passing case(s), function line 93.
- [test_d2c_signals_prioritize_existing_shopping_journey_and_preserve_campaign_gate](../tests/test_opportunities.py) — 1 executed passing case(s), function line 24.
- [test_channel_signal_does_not_infer_customer_permission](../tests/test_opportunities.py) — 1 executed passing case(s), function line 33.

### I — Source-backed personalized draft + 3 follow-ups

Source: [outreach/preparation.py:229 — prepare](../outreach/preparation.py), [outreach/campaigns.py:201 — create_drafts](../outreach/campaigns.py), [outreach/email_writer.py:300 — generate_sequence](../outreach/email_writer.py), [outreach/email_writer.py:214 — validate_output](../outreach/email_writer.py)

- [test_sourced_trigger_and_extra_value_survive_into_drafts](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 49.
- [test_default_followup_adds_new_value](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 78.
- [test_draft_generation_cannot_overwrite_a_sequence_approved_mid_request](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 226.

### J — Review all messages and outreach eligibility

Source: [outreach/campaigns.py:299 — approve](../outreach/campaigns.py), [outreach/app.py:989 — edit_message](../outreach/app.py)

- [test_approval_requires_safe_and_one_contact_per_company](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 20.
- [test_approve_and_edit_freeze](../tests/test_api.py) — 1 executed passing case(s), function line 64.
- [test_old_qualification_cannot_skip_new_country_review](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 169.

### K — Approve · local send window · mailbox quota

Source: [outreach/campaigns.py:299 — approve](../outreach/campaigns.py), [outreach/mail.py:95 — send_one](../outreach/mail.py), [outreach/mail.py:24 — eligible_now](../outreach/mail.py)

- [test_two_concurrent_approvals_cannot_activate_twice](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 189.
- [test_send_windows_weekend_and_dst](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 128.
- [test_daily_limit](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 140.
- [test_eligible_timezone_not_starved_by_first_hundred_due_contacts](../tests/test_requirements_audit.py) — 1 executed passing case(s), function line 210.

### L — SMTP send · durable Message-ID

Source: [outreach/mail.py:50 — smtp_send](../outreach/mail.py), [outreach/mail.py:29 — build_message](../outreach/mail.py), [outreach/mail.py:95 — send_one](../outreach/mail.py)

- [test_real_tls_send_and_imap_optout_stop_sequence](../tests/test_mail_wire.py) — 2 executed passing case(s), function line 29.
- [test_real_smtp_failure_stages_and_duplicate_protection](../tests/test_mail_wire.py) — 5 executed passing case(s), function line 104.
- [test_untrusted_tls_fails_before_authentication](../tests/test_mail_wire.py) — 2 executed passing case(s), function line 129.

### M — Independent IMAP monitoring

Source: [outreach/worker.py:149 — mail_loop](../outreach/worker.py), [outreach/mail.py:314 — poll_inbox](../outreach/mail.py)

- [test_worker_monitors_inbox_during_long_research_and_recovers_shutdown](../tests/test_crawler_quality.py) — 1 executed passing case(s), function line 536.
- [test_imap_bounded_read_and_reply_stop](../tests/test_mail_providers.py) — 1 executed passing case(s), function line 34.
- [test_imap_login_failure_invalidates_readiness](../tests/test_mail_providers.py) — 1 executed passing case(s), function line 65.

### N — Next due follow-up · stop after touch 4

Source: [outreach/mail.py:220 — mark_sent](../outreach/mail.py), [outreach/mail.py:84 — due_candidates](../outreach/mail.py)

- [test_four_touch_tls_sequence_respects_actual_acceptance_and_stops](../tests/test_mail_wire.py) — 2 executed passing case(s), function line 58.
- [test_send_once_and_schedule_from_acceptance](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 27.

### O — Stop sequence · human conversation

Source: [outreach/mail.py:251 — record_inbound](../outreach/mail.py), [outreach/sales.py:39 — record_activity](../outreach/sales.py)

- [test_reply_cancels_followups_and_is_idempotent](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 83.
- [test_html_positive_reply_does_not_inherit_quoted_unsubscribe](../tests/test_mail_wire.py) — 1 executed passing case(s), function line 119.
- [test_manual_reply_stops_active_sequence_and_cannot_release](../tests/test_sales.py) — 1 executed passing case(s), function line 47.

### P — Global suppression

Source: [outreach/db.py:212 — suppress](../outreach/db.py), [outreach/mail.py:251 — record_inbound](../outreach/mail.py), [outreach/app.py:1068 — unsubscribe](../outreach/app.py)

- [test_optout_global_suppression](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 93.
- [test_permanent_dsn_suppresses](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 104.
- [test_suppression_overrides_approved_queue](../tests/test_campaigns_mail.py) — 1 executed passing case(s), function line 134.
- [test_unsubscribe_get_does_not_mutate](../tests/test_api.py) — 1 executed passing case(s), function line 55.

### R — Classify actual reply and fulfill promised value

Source: [outreach/mail.py:251 — record_inbound](../outreach/mail.py), [outreach/sales.py:39 — record_activity](../outreach/sales.py), [outreach/sales.py:137 — create_task](../outreach/sales.py)

- [test_inbound_reply_creates_one_fulfillment_task_and_shared_hold](../tests/test_sales.py) — 1 executed passing case(s), function line 79.
- [test_tasks_are_due_visible_and_close_with_outcome](../tests/test_sales.py) — 1 executed passing case(s), function line 134.

### S — Review audit / concept / FAQ / WhatsApp-flow artifact

Source: [outreach/deliverables.py:185 — prepare_automatic](../outreach/deliverables.py), [outreach/deliverables.py:68 — create](../outreach/deliverables.py), [outreach/deliverables.py:247 — action](../outreach/deliverables.py)

- [test_each_value_artifact_is_sourced_reviewable_and_deliverable](../tests/test_deliverables.py) — 4 executed passing case(s), function line 25.
- [test_faq_and_concept_labels_do_not_claim_live_ai_or_finished_website](../tests/test_deliverables.py) — 1 executed passing case(s), function line 58.
- [test_annotated_artifact_embeds_only_its_saved_company_screenshot](../tests/test_deliverables.py) — 1 executed passing case(s), function line 76.

### T — Confirm problem, buyer, budget, timing and success metric

Source: [outreach/sales.py:91 — update_sales](../outreach/sales.py)

- [test_unconfirmed_client_need_cannot_advance_or_create_proposal](../tests/test_sales.py) — 1 executed passing case(s), function line 88.
- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.

### U — Record agreed call and dated next action

Source: [outreach/sales.py:91 — update_sales](../outreach/sales.py), [outreach/sales.py:137 — create_task](../outreach/sales.py)

- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.
- [test_invalid_dates_and_future_activity_are_rejected](../tests/test_sales.py) — 1 executed passing case(s), function line 151.
- [test_tasks_are_due_visible_and_close_with_outcome](../tests/test_sales.py) — 1 executed passing case(s), function line 134.

### V — Prepare and review scoped proposal

Source: [outreach/sales.py:160 — create_proposal](../outreach/sales.py), [outreach/sales.py:198 — proposal_action](../outreach/sales.py)

- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.
- [test_unconfirmed_client_need_cannot_advance_or_create_proposal](../tests/test_sales.py) — 1 executed passing case(s), function line 88.

### W — Record actual proposal delivery

Source: [outreach/sales.py:198 — proposal_action](../outreach/sales.py)

- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.
- [test_won_requires_real_references_and_delivered_proposal](../tests/test_sales.py) — 1 executed passing case(s), function line 118.

### X — Record agreement and initial payment references

Source: [outreach/sales.py:91 — update_sales](../outreach/sales.py)

- [test_won_requires_real_references_and_delivered_proposal](../tests/test_sales.py) — 1 executed passing case(s), function line 118.
- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.

### Y — Manage delivery tasks and record client acceptance

Source: [outreach/sales.py:137 — create_task](../outreach/sales.py), [outreach/sales.py:148 — finish_task](../outreach/sales.py), [outreach/sales.py:91 — update_sales](../outreach/sales.py)

- [test_tasks_are_due_visible_and_close_with_outcome](../tests/test_sales.py) — 1 executed passing case(s), function line 134.
- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.

### Z — Record measured or inconclusive outcome and campaign learning

Source: [outreach/sales.py:91 — update_sales](../outreach/sales.py), [outreach/sales.py:217 — report](../outreach/sales.py), [outreach/learning.py:51 — report](../outreach/learning.py), [outreach/learning.py:24 — summarize](../outreach/learning.py), [outreach/finance.py:19 — record](../outreach/finance.py), [outreach/finance.py:65 — report](../outreach/finance.py), [outreach/aftercare.py:24 — create](../outreach/aftercare.py), [outreach/aftercare.py:44 — update](../outreach/aftercare.py), [outreach/aftercare.py:76 — export](../outreach/aftercare.py), [outreach/aftercare.py:90 — report](../outreach/aftercare.py)

- [test_exact_currency_arithmetic_refunds_and_no_exchange_conversion](../tests/test_growth_finance_priority.py) — 1 executed passing case(s), function line 47.
- [test_duplicate_receipt_retry_is_idempotent_conflict_and_void_preserve_history](../tests/test_growth_finance_priority.py) — 1 executed passing case(s), function line 71.
- [test_aftercare_order_permission_idempotency_and_optimistic_version](../tests/test_growth_finance_priority.py) — 3 executed passing case(s), function line 156.
- [test_case_study_freezes_outcome_escapes_html_and_preserves_inconclusive](../tests/test_growth_finance_priority.py) — 1 executed passing case(s), function line 176.
- [test_complete_operator_confirmed_sales_lifecycle](../tests/test_sales.py) — 1 executed passing case(s), function line 94.
- [test_sales_report_includes_companies_without_sales_records](../tests/test_sales.py) — 1 executed passing case(s), function line 65.
- [test_funnel_counts_records_not_messages_and_excludes_automatic_replies](../tests/test_learning.py) — 1 executed passing case(s), function line 28.
- [test_approval_snapshot_is_atomic_and_survives_later_business_label_changes](../tests/test_learning.py) — 1 executed passing case(s), function line 47.
- [test_legacy_approved_context_stays_unknown_instead_of_invented_historical_attribution](../tests/test_learning.py) — 1 executed passing case(s), function line 60.
- [test_empty_learning_does_not_invent_rates_or_experiment_winners](../tests/test_learning.py) — 1 executed passing case(s), function line 20.

## Latest VPS evidence — 18 October 2026

The user reports saved official-site and rendered LinkedIn company evidence, partial website crawls and a writer HTTP 404. Automatic preparation, endpoint normalization and a synthetic connection-test UI are now covered by controlled tests; this does not establish a successful deployed NVIDIA request. See AUTO_PREPARATION.md and VALIDATION.md. Earlier local checks below are historical and are not a diagnosis of the VPS.

## Earlier local acceptance baseline

Local discovery and rendered website research ran. The current records contain published website contacts without established fresh-safe verification. A LinkedIn profile lookup reused the found website but its snapshot was robots-denied. Sending stays disabled and paused; this audit did not approve recipients, probe real addresses or send external mail.

The configured local Reacher API fails the invalid-syntax endpoint check (HTTP 404); another service occupies port 8080. The separate outbound TCP/25 connection check succeeded without any SMTP commands, which does not establish Reacher accuracy or deployability. Real Reacher backend/provider accuracy, mailbox/domain/HTTPS, VPS/Linux Docker, real website-less email coverage, independent buyer/eligibility review and controlled delivery acceptance remain pending. VPS/mailbox setup was explicitly deferred by the user.

Reply intent review, actual call booking, external artifact/proposal delivery, agreement/payment, client deployment/acceptance and measured business outcomes require operator records. Automatic descriptive campaign learning is available under Learning, with frozen approval groups and honest null/unknown rates. No automatic payment collection, signature verification, sales negotiation, causal campaign optimization or conversion guarantee is claimed.

Re-run: `python -m pytest -q --junitxml=data/audit-each-node-tests.xml`, then `python scripts/verify_workflow_nodes.py`. Full machine-readable provenance is in `every-node-audit.json`.
