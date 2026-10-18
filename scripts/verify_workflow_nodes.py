"""Produce a node-by-node source/test evidence report for the documented acquisition flow.

Run pytest with --junitxml=data/audit-each-node-tests.xml first. This maps audited
behavior to executed tests; it is not a proof of provider accuracy or live delivery.
"""
import argparse
import ast
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path


# Each entry was checked against the business-flow requirement and its implementation.
# Automatic = application operation; review/operator = a deliberate human gate.
NODES = [
    ('A', 'automatic', ['app:import_csv', 'discovery:prospect_candidates'], ['test_api_import_detail_and_export', 'test_market_selection_scopes_search_and_locale'], 'Queries include US/UK context; CSV imports sourced website records. Profile-only records use discovery/profile form, not website-only CSV import.', 'Search/import live locally; discovery country is an unconfirmed hint.'),
    ('B', 'automatic', ['providers:discover'], ['test_search_contract', 'test_failed_platform_queries_do_not_discard_successful_official_results'], 'SearXNG JSON and optional SerpApi adapter; failed engines are retained as limitations.', 'Native SearXNG used live; engine blocks/CAPTCHAs observed. Optional paid SerpApi not live validated.'),
    ('C', 'automatic + review', ['research:add_lead', 'discovery:resolve_signal'], ['test_company_and_contact_dedup_preserves_suppression', 'test_multi_platform_discovery_persists_signals_deduplicates_and_queues_research'], 'Domains deduplicate; profile links/name/reciprocal links produce candidate matches, not verified owners.', 'A matched official website was researched; identity and buyer fit still need review.'),
    ('CP', 'automatic', ['profiles:add_profile_lead', 'research:discover_leads'], ['test_profile_discovery_imports_deduplicates_but_never_probes', 'test_profile_api_no_fake_website_and_visual_audits_rejected'], 'Specific business profile retained with empty website and internal identity key; no fake company domain.', 'Live LinkedIn record routed to an existing website; actual website-less acquisition not yet accepted.'),
    ('CS', 'automatic', ['profiles:research_profile', 'discovery:public_snapshot', 'discovery:resolve_signal'], ['test_found_website_routes_to_normal_research_without_merging_contacts', 'test_failed_website_search_is_not_absence', 'test_robots_denial_never_fetches_profile'], 'Robots-permitted profile capture and named-company lookup; matched website creates/reuses a deep-research record.', 'Live lookup matched IMAGE Skincare UK; LinkedIn capture robots-denied. No private-platform scraping.'),
    ('CR', 'review', ['campaigns:review_lead', 'profiles:assert_profile_review'], ['test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate', 'test_ambiguous_or_blocked_profile_cannot_be_qualified'], 'Exact current activity/country quotes, ownership notes and search-limit acknowledgment required. Not-found does not mean confirmed absent.', 'Verified with fictional captured profiles; real profile identity acceptance pending.'),
    ('CE', 'automatic extraction + review', ['profiles:research_profile', 'research:add_contact'], ['test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate', 'test_profile_discovery_imports_deduplicates_but_never_probes'], 'Captured published emails stay candidates; import/probe blocked until profile qualification and inbox ownership review. Candidates can be captured before CR; the later gates still apply.', 'No real profile email acquired/probed in current live record.'),
    ('D', 'automatic', ['web:crawl', 'browser:render'], ['test_sitemap_index_prioritizes_contacts_and_preserves_partial_pages', 'test_real_chromium_executes_spa_and_public_cdn_assets', 'test_robots_denial_prevents_crawl'], 'Robots, sitemap/depth/page budgets, mediated HTTP and sandboxed JS rendering; report partial or failed coverage.', 'Real 30-page Chromium research completed with partial coverage; broader 50-domain audit contains partial/failing sites.'),
    ('E', 'automatic + review', ['research:research_lead', 'web:extract_page', 'providers:research_suggestions', 'opportunities:proposals'], ['test_crawl_report_and_contact_identity_are_persisted', 'test_recrawl_suggestions_exclude_unvisited_historical_pages', 'test_ai_rejects_invented_quote', 'test_no_ai_research_saves_current_signal_proposal_without_qualification_or_drafts', 'test_insufficient_evidence_stays_empty_instead_of_inventing_friction_or_absent_features'], 'Persist URL, text, hashes and contact identity; only current captures support new ideas. Explicit public signals propose relevant services without an AI key; optional AI can suggest more. Weak/negative cues stay needs-review; every exact quote and interpretation requires review.', 'Current real website pages yielded matching store/support proposals in a read-only preview; actual pain points, buyer relevance and recent announcements require interpretation/review.'),
    ('E1', 'automatic', ['research:research_lead', 'research:add_contact'], ['test_research_to_contacts_and_verification', 'test_extract_only_sourced_business_emails'], 'Published same-domain addresses are imported and verification queued; buyer role and eligibility remain separate.', 'Two published website contacts captured; neither established fresh safe.'),
    ('E2', 'automatic candidate capture', ['research:research_lead', 'research:contact_candidates'], ['test_external_published_addresses_are_candidates_not_automatic_contacts', 'test_research_retains_candidates_without_importing_or_verifying_them'], 'Other-domain addresses are held with current source URL/hash; no automatic provider probe.', 'One live website candidate retained; no automatic import.'),
    ('E3', 'review', ['research:add_contact', 'research:assert_contact_ownership'], ['test_alias_contact_requires_source_and_ownership_then_remains_unverified', 'test_recrawl_without_alias_page_invalidates_old_proof_but_preserves_history', 'test_stale_ownership_holds_approved_sequence_before_smtp'], 'Ownership notes plus current official extraction required; re-crawl/source changes invalidate proof; cross-company inbox attachment rejected.', 'Fictional reviewed contacts tested; current real candidate remains held.'),
    ('F', 'automatic / broader provider acceptance pending', ['research:verify_contact', 'providers:verify_email', 'providers:classify_reacher'], ['test_reacher_adapter_contract', 'test_reacher_contradictions', 'test_reviewed_profile_contact_can_verify_and_queue_with_all_existing_gates'], 'Strict response/address checks; unknown/risky/catch-all/disposable/invalid cannot pass. Current source, recipient and suppression checked before dispatch and before committing a result.', 'Native backend/API/auth passed. The earlier isolated recipient was catch-all/risky; a new officially published florist contact received a real safe/non-catch-all verdict. One verdict does not establish universal existence, broader accuracy or inbox delivery; no outreach sent.'),
    ('G', 'AI preparation + exception/final review', ['preparation:prepare', 'preparation:_validate_review', 'campaigns:review_lead', 'priorities:ranked'], ['test_prepare_runs_real_writer_contract_and_leaves_all_messages_unsent', 'test_unsupported_assessments_stay_held_without_drafts', 'test_priority_read_only_explainable_recrawl_and_suppression_reduce_readiness', 'test_active_sequences_are_not_ranked_as_new_outreach_work', 'test_country_evidence_must_match_saved_source', 'test_review_rejects_sources_not_refreshed_in_latest_crawl', 'test_sourced_trigger_and_extra_value_survive_into_drafts'], 'AI preparation validates current source quotes, US/UK country/timezone and one offer; manual editing remains available. Unsupported inputs stay held; buyer/recipient judgment and final messages still require operator review.', 'Actual current businesses not qualified by this audit; quote validity alone does not establish semantic truth.'),
    ('Q', 'automatic optional audit', ['browser:screenshot', 'performance:performance_audit'], ['test_authenticated_crawl_report_and_audit_images', 'test_pagespeed_preserves_lab_evidence_and_partial_results', 'test_pagespeed_failure_never_creates_fake_score'], 'Desktop/mobile screenshots and optional on-demand PageSpeed; no profile-only site audits and no invented scores.', 'Real screenshots exist. Keyless PageSpeed live requests returned HTTP 429; no successful live lab score established.'),
    ('H', 'automatic hold + review', ['mail:send_one', 'mail:record_inbound', 'campaigns:resume_contact', 'profiles:assert_profile_review'], ['test_uncertain_send_is_never_automatically_retried', 'test_resume_requires_fresh_result_and_cannot_override_optout', 'test_unsafe_reverification_holds_instead_of_looping', 'test_ambiguous_or_blocked_profile_cannot_be_qualified'], 'Hold is represented by lead/profile/contact/message states, not a single unified queue. Uncertain sends require reconciliation; blocked sources and unsafe verification cannot send.', 'Current verification/profile failures visible; human resolution or provider availability required.'),
    ('AA', 'automatic proposals + reviewed selection', ['campaigns:review_lead', 'campaigns:draft_sequence', 'opportunities:proposals'], ['test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate', 'test_drafts_do_not_claim_completed_assets', 'test_inquiry_offer_is_grounded_and_reviewed_without_claiming_an_observed_problem', 'test_profile_launch_proposal_requires_completed_not_found_search'], 'Campaign A proposes build/improvement/chatbot from public inquiry/service/support cues; one final offer is reviewed. Profile-only improvement excluded.', 'Fixed cue ranking is not a prediction of client value, sales likelihood or conversion uplift.'),
    ('BB', 'automatic proposals + reviewed selection', ['campaigns:review_lead', 'campaigns:draft_sequence', 'opportunities:proposals'], ['test_campaign_b_rejects_non_d2c_website_offer', 'test_whatsapp_requires_recorded_channel_fit', 'test_whatsapp_flow_requires_qualified_channel_and_artifacts_require_auth', 'test_d2c_signals_prioritize_existing_shopping_journey_and_preserve_campaign_gate', 'test_channel_signal_does_not_infer_customer_permission'], 'Campaign B proposes launch/improvement/chatbot/WhatsApp from source cues; channel-fit, permission/integration and one relevant offer still require review.', 'No live WhatsApp sending or client store integration is performed by this acquisition software.'),
    ('I', 'AI preparation and writing; final message review', ['preparation:prepare', 'campaigns:create_drafts', 'email_writer:generate_sequence', 'email_writer:validate_output'], ['test_sourced_trigger_and_extra_value_survive_into_drafts', 'test_default_followup_adds_new_value', 'test_draft_generation_cannot_overwrite_a_sequence_approved_mid_request'], 'Exactly four editable touches, one relevant offer, source references and distinct follow-up value; activated content cannot be overwritten.', 'Historical templates are offline samples only. The current AI writer requires its own configured endpoint and model-quality acceptance; no live AI/provider or recipient acceptance claimed.'),
    ('J', 'review gate', ['campaigns:approve', 'app:edit_message'], ['test_approval_requires_safe_and_one_contact_per_company', 'test_approve_and_edit_freeze', 'test_old_qualification_cannot_skip_new_country_review'], 'All four draft messages, sender identity, qualification, fresh safe proof, relevance/eligibility notes, opt-out and company conversation gate.', 'No real sequence approved. Current source findings and eligibility require operator judgment.'),
    ('K', 'approval + automatic scheduling', ['campaigns:approve', 'mail:send_one', 'mail:eligible_now'], ['test_two_concurrent_approvals_cannot_activate_twice', 'test_send_windows_weekend_and_dst', 'test_daily_limit', 'test_eligible_timezone_not_starved_by_first_hundred_due_contacts'], 'Atomic approval; one conversation/company; local weekday/hour window, daily quota and minimum send gap.', 'Simulated calendars and isolated transport verified; deployed timezone/quota acceptance pending.'),
    ('L', 'automatic / mailbox setup pending', ['mail:smtp_send', 'mail:build_message', 'mail:send_one'], ['test_real_tls_send_and_imap_optout_stop_sequence', 'test_real_smtp_failure_stages_and_duplicate_protection', 'test_untrusted_tls_fails_before_authentication'], 'TLS authenticated SMTP, durable IDs/threading, explicit acceptance versus uncertain outcome and no automatic uncertain retry.', 'Real socket protocols passed on loopback fixtures; external mailbox delivery/inbox placement unverified.'),
    ('M', 'automatic / mailbox setup pending', ['worker:mail_loop', 'mail:poll_inbox'], ['test_worker_monitors_inbox_during_long_research_and_recovers_shutdown', 'test_imap_bounded_read_and_reply_stop', 'test_imap_login_failure_invalidates_readiness'], 'Independent mailbox lane, bounded read-only IMAP, UID/identity idempotency and freshness; long crawling does not block it.', 'Local protocol fixtures verified; no real mailbox credentials configured.'),
    ('N', 'automatic', ['mail:mark_sent', 'mail:due_candidates'], ['test_four_touch_tls_sequence_respects_actual_acceptance_and_stops', 'test_send_once_and_schedule_from_acceptance'], 'Calendar day 1/4/9/15: gaps 3/5/6 days from actual acceptance, then local-window adjustment. Stop after touch 4; no overdue burst.', 'Loopback TLS test used both ordinary and delayed calendars; no real campaign sent.'),
    ('O', 'automatic stop + human conversation', ['mail:record_inbound', 'sales:record_activity'], ['test_reply_cancels_followups_and_is_idempotent', 'test_html_positive_reply_does_not_inherit_quoted_unsubscribe', 'test_manual_reply_stops_active_sequence_and_cannot_release'], 'Human reply cancels future touches, creates fulfillment task and shared company hold; manual social replies can be recorded.', 'Fixture replies verified; the software does not autonomously negotiate with the prospect.'),
    ('P', 'automatic', ['db:suppress', 'mail:record_inbound', 'app:unsubscribe'], ['test_optout_global_suppression', 'test_permanent_dsn_suppresses', 'test_suppression_overrides_approved_queue', 'test_unsubscribe_get_does_not_mutate'], 'Opt-outs/permanent recipient failures suppress globally; unsubscribe GET is read-only and POST performs the stop.', 'Fixture events/protocol verified; production HTTPS unsubscribe endpoint still requires deployment.'),
    ('R', 'operator review + automatic task', ['mail:record_inbound', 'sales:record_activity', 'sales:create_task'], ['test_inbound_reply_creates_one_fulfillment_task_and_shared_hold', 'test_tasks_are_due_visible_and_close_with_outcome'], 'Transport classifies reply/auto-reply/opt-out/DSN. Commercial intent and promised-value fulfillment are operator notes/tasks/stages, not a trained automatic sales classifier.', 'No actual external reply fulfillment claimed.'),
    ('S', 'assisted creation + review', ['deliverables:create', 'deliverables:action'], ['test_each_value_artifact_is_sourced_reviewable_and_deliverable', 'test_faq_and_concept_labels_do_not_claim_live_ai_or_finished_website', 'test_annotated_artifact_embeds_only_its_saved_company_screenshot'], 'Source-backed audit, annotated screenshot, homepage concept, interactive FAQ and WhatsApp planning outline; review/export and actual-delivery reference.', 'Actual Chromium inspected fictional exports. Concepts/FAQ/WhatsApp outlines are prototypes, not deployed client services.'),
    ('T', 'operator-recorded', ['sales:update_sales'], ['test_unconfirmed_client_need_cannot_advance_or_create_proposal', 'test_complete_operator_confirmed_sales_lifecycle'], 'Confirmed problem, goal, buyer, timeline, budget and success metric required; a real conversation record gates advancement.', 'External buyer confirmation cannot be independently verified by these fixture tests.'),
    ('U', 'operator-recorded', ['sales:update_sales', 'sales:create_task'], ['test_complete_operator_confirmed_sales_lifecycle', 'test_invalid_dates_and_future_activity_are_rejected', 'test_tasks_are_due_visible_and_close_with_outcome'], 'Record agreed call timestamp and dated next action/tasks. This does not book a calendar or send an invitation.', 'No actual booking/calendar integration performed.'),
    ('V', 'assisted creation + review', ['sales:create_proposal', 'sales:proposal_action'], ['test_complete_operator_confirmed_sales_lifecycle', 'test_unconfirmed_client_need_cannot_advance_or_create_proposal'], 'Qualified client need, scope, deliverables, exclusions, acceptance, timeline, terms and USD/GBP fee create reviewed downloadable proposal.', 'Proposal fixtures reviewed; human scope/commercial acceptance required.'),
    ('W', 'operator-recorded', ['sales:proposal_action'], ['test_complete_operator_confirmed_sales_lifecycle', 'test_won_requires_real_references_and_delivered_proposal'], 'Delivery requires reviewed proposal and explicit actual-delivery reference; not automatic SMTP proposal delivery.', 'No real client proposal sent by this audit.'),
    ('X', 'operator-recorded', ['sales:update_sales'], ['test_won_requires_real_references_and_delivered_proposal', 'test_complete_operator_confirmed_sales_lifecycle'], 'Won/delivery/completed require agreement and initial-payment references; no payment processor or signature collection.', 'References are operator assertions, not verified receipts or signed documents.'),
    ('Y', 'operator-recorded task management', ['sales:create_task', 'sales:finish_task', 'sales:update_sales'], ['test_tasks_are_due_visible_and_close_with_outcome', 'test_complete_operator_confirmed_sales_lifecycle'], 'Delivery tasks and closure outcomes; completed stage requires client acceptance reference. No automatic client website/WhatsApp deployment.', 'Actual client delivery and acceptance remain external.'),
    ('Z', 'operator-recorded + automatic descriptive learning', ['sales:update_sales', 'sales:report', 'learning:report', 'learning:summarize', 'finance:record', 'finance:report', 'aftercare:create', 'aftercare:update', 'aftercare:export', 'aftercare:report'], ['test_exact_currency_arithmetic_refunds_and_no_exchange_conversion', 'test_duplicate_receipt_retry_is_idempotent_conflict_and_void_preserve_history', 'test_aftercare_order_permission_idempotency_and_optimistic_version', 'test_case_study_freezes_outcome_escapes_html_and_preserves_inconclusive', 'test_complete_operator_confirmed_sales_lifecycle', 'test_sales_report_includes_companies_without_sales_records', 'test_funnel_counts_records_not_messages_and_excludes_automatic_replies', 'test_approval_snapshot_is_atomic_and_survives_later_business_label_changes', 'test_legacy_approved_context_stays_unknown_instead_of_invented_historical_attribution', 'test_empty_learning_does_not_invent_rates_or_experiment_winners'], 'Outcome notes can be inconclusive. Learning reports frozen campaign/service/country/industry groups, accepted-record-to-human-reply/qualified/recorded-won rates and next-review guidance. No denominator means unknown; repeats and auto-replies cannot inflate conversions. Recorded USD/GBP cost and receipt reports remain separate, with immutable correction history. Completed clients can have dated maintenance/expansion plans and permission-reviewed frozen case studies; external work/publication remains operator-recorded.', 'No automatic analytics attribution, A/B optimization, verified revenue or evidence of conversion uplift. Historical contexts missing an approval snapshot remain unknown.'),
]


def symbol_line(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    matches = [node.lineno for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(matches) != 1:
        raise ValueError(f'Expected one audited symbol {path.name}:{name}; found {len(matches)}')
    return matches[0]


def audit(root, junit):
    diagram = (root / 'docs/WORKFLOW.md').read_text(encoding='utf-8')
    block = diagram.split('```mermaid', 1)[1].split('```', 1)[0]
    labels = dict(re.findall(r'\b([A-Z][A-Z0-9]*)\[([^\]]+)\]', block))
    assert set(labels) == {n[0] for n in NODES}, 'Unmapped or removed workflow nodes'
    cases = list(ET.parse(junit).getroot().iter('testcase'))
    assert cases and not any(c.find('failure') is not None or c.find('error') is not None for c in cases), 'Failed tests'
    tests = {}
    for path in (root / 'tests').glob('test_*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                assert node.name not in tests, 'Ambiguous test name'
                tests[node.name] = (path, node.lineno)
    result = []
    for key, mode, code, checks, behavior, boundary in NODES:
        owners = []
        for reference in code:
            module, symbol = reference.split(':')
            path = root / f'outreach/{module}.py'
            owners.append({'path': path.relative_to(root).as_posix(), 'symbol': symbol,
                           'line': symbol_line(path, symbol), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        evidence = []
        for name in checks:
            path, line = tests[name]
            executed = [c for c in cases if c.get('name', '').split('[', 1)[0] == name
                        and c.get('classname', '').split('.')[-1] == path.stem and c.find('skipped') is None]
            assert executed, f'No executed passing evidence for {name}'
            evidence.append({'path': path.relative_to(root).as_posix(), 'test': name,
                             'line': line, 'executed_passing_cases': len(executed)})
        result.append({'id': key, 'label': labels[key], 'implementation': 'present; mapped tests passed',
                       'mode': mode, 'behavior_checked': behavior, 'live_or_manual_boundary': boundary,
                       'code': owners, 'tests': evidence})
    return {'checked_at': time.time(), 'diagram_node_count': len(result),
            'diagram_sha256': hashlib.sha256(block.encode()).hexdigest(),
            'scope': 'Each documented node: source inspection and mapped tests; fixture success is not deployed/provider/client acceptance.',
            'junit_private_path': junit.relative_to(root).as_posix(),
            'junit_sha256': hashlib.sha256(junit.read_bytes()).hexdigest(),
            'suite_cases_passed': sum(c.find('skipped') is None for c in cases),
            'suite_cases_skipped': sum(c.find('skipped') is not None for c in cases),
            'all_nodes_live_verified': False, 'broader_goal_complete': False,
            'ui': 'Overview has eleven summary stages; Full workflow renders all 35 nodes and 46 connections with saved statuses and execution modes. Layout editing does not change execution rules.',
            'findings_fixed': [
                'Approval status cannot combine drafts, qualification and safe verification from unrelated prospects.',
                'Manual reply/closed status is not evidence of prior sequence approval; use recorded approval timestamp.',
                'Terminal research/audit job failures remain visible even with preserved reviewable partial evidence.',
                'Fresh-safe count excludes suppression and stale profile/other-domain ownership.',
                'Stale inbox catch-up does not show running monitoring; worker must also be enabled.',
                'Terminal recorded sales journey with no open tasks is complete instead of permanent needs-review.',
                'Unqueued new research is ready; partially qualified aggregate is not complete; latest jobs ordered deterministically.'
            ], 'nodes': result}


def markdown(report):
    lines = ['# Every-node acquisition workflow audit', '',
             '**Email-writing boundary:** tests use controlled AI/provider fixtures; they do not establish live model quality or mailbox delivery. AI preparation is optional and source validated; final recipient/message approval stays manual. No template fallback. See [automatic preparation](AUTO_PREPARATION.md).', '',
             f"Latest recheck: **{report['diagram_node_count']} / {report['diagram_node_count']} nodes mapped to actual source and passing executed tests**. Full suite: **{report['suite_cases_passed']} passed**.", '',
             'The implementation is present for every node, with deliberate human gates. This does **not** mean all nodes are fully automatic or verified against real providers/clients. The dashboard supports eleven overview stages and all thirty-five detailed nodes with source/ownership, branch, hold and operator-recorded statuses.', '',
             '## What this audit corrected', '', *['- ' + item for item in report['findings_fixed']], '',
             'Six new regression cases reproduced six status defects before the fixes (6 failed / 4 passed). The ten workflow-map tests pass afterward. These were visibility/calculation defects; the underlying approval/send gates were independently enforced.', '',
             '## Latest recheck and diagram differences', '',
             'Re-ran the complete suite for the user-supplied diagram. A provider-readiness defect was found: the configured local port 8080 serves another service, whose root responds HTTP 200. Preflight now checks Reacher invalid-syntax handling and header authentication instead of accepting root HTTP success. Four regressions cover the wrong service, unknown schema, authenticated syntax rejection and bounded retry. No valid recipient is submitted by this check.', '',
             '- CSV import goes directly to company website research (A → C); only search queries use B. The diagram should not imply that CSV import requires a search provider.',
             '- CE candidates can be captured during CS, before CR review. They remain held until CR/E3 ownership and qualification gates pass.',
             '- Qualification and technical verification are independent branches; both must pass J. H is distributed across held states, not a separate single work queue.',
             '- R commercial-intent classification and S–Y client actions require an operator. The sales portion is a managed business process, not a mandatory linear automation that books calls, delivers proposals, verifies payments or deploys client services. A call or value artifact is recorded when actually agreed/promised; confirmed need and reviewed proposal delivery guard the later sales stages.',
             '- Full workflow now displays all thirty-five nodes and forty-six connections, while Overview retains eleven grouped stages. Inspect stage and Focus next reveal status, execution mode, conditional routes and action destination. Reading or dragging cannot trigger an operation.', '',
             '## Every node', '', '| Node | Process | Execution | Verified behavior and boundary |', '|---|---|---|---|']
    for row in report['nodes']:
        lines.append(f"| {row['id']} | {row['label']} | {row['mode']} | {row['behavior_checked']} **Boundary:** {row['live_or_manual_boundary']} |")
    lines.extend(['', '## Source and executed test evidence', ''])
    for row in report['nodes']:
        lines.extend([f"### {row['id']} — {row['label']}", '', 'Source: ' + ', '.join(
            f"[{o['path']}:{o['line']} — {o['symbol']}](../{o['path']})" for o in row['code']), '',
            *[f"- [{c['test']}](../{c['path']}) — {c['executed_passing_cases']} executed passing case(s), function line {c['line']}." for c in row['tests']], ''])
    lines.extend(['## Latest VPS evidence — 18 October 2026', '',
                  'The user reports saved official-site and rendered LinkedIn company evidence, partial website crawls and a writer HTTP 404. Automatic preparation, endpoint normalization and a synthetic connection-test UI are now covered by controlled tests; this does not establish a successful deployed NVIDIA request. See AUTO_PREPARATION.md and VALIDATION.md. Earlier local checks below are historical and are not a diagnosis of the VPS.', '',
                  '## Earlier local acceptance baseline', '',
                  'Local discovery and rendered website research ran. The current records contain published website contacts without established fresh-safe verification. A LinkedIn profile lookup reused the found website but its snapshot was robots-denied. Sending stays disabled and paused; this audit did not approve recipients, probe real addresses or send external mail.', '',
                  'The configured local Reacher API fails the invalid-syntax endpoint check (HTTP 404); another service occupies port 8080. The separate outbound TCP/25 connection check succeeded without any SMTP commands, which does not establish Reacher accuracy or deployability. Real Reacher backend/provider accuracy, mailbox/domain/HTTPS, VPS/Linux Docker, real website-less email coverage, independent buyer/eligibility review and controlled delivery acceptance remain pending. VPS/mailbox setup was explicitly deferred by the user.', '',
                  'Reply intent review, actual call booking, external artifact/proposal delivery, agreement/payment, client deployment/acceptance and measured business outcomes require operator records. Automatic descriptive campaign learning is available under Learning, with frozen approval groups and honest null/unknown rates. No automatic payment collection, signature verification, sales negotiation, causal campaign optimization or conversion guarantee is claimed.', '',
                  'Re-run: `python -m pytest -q --junitxml=data/audit-each-node-tests.xml`, then `python scripts/verify_workflow_nodes.py`. Full machine-readable provenance is in `every-node-audit.json`.'])
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--junit', type=Path, default=Path('data/audit-each-node-tests.xml'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = audit(root, (root / args.junit).resolve())
    (root / 'docs/every-node-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (root / 'docs/EVERY_NODE_AUDIT.md').write_text(markdown(report), encoding='utf-8')
    print(f"Verified {report['diagram_node_count']} node mappings against {report['suite_cases_passed']} passing tests; production acceptance remains pending.")
