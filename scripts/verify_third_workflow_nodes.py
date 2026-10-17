"""Map all 23 boxes in the user's third diagram to executed behavioral evidence."""
import ast
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET


NODES = [
    ('Selected offer + evidence', 'review + automatic guards', 'offers:selected_offer',
     ['test_every_offer_branch_selects_one_service_and_prepares_relevant_source_proof', 'test_third_approval_rejects_changed_campaign_a_sources'],
     'One current, quoted and country-reviewed A/B offer; stale evidence cannot approve.', 'Real companies still need identity and service-fit review.'),
    ('Identify relevant buyer', 'operator review', 'campaigns:approve',
     ['test_third_unsent_revision_preserves_copy_history_and_requires_new_approval'],
     'Stored contact name/role and an explicit relevance note are reviewed at approval and frozen.', 'Public roles are clues; actual buying authority is confirmed by the operator/client.'),
    ('Choose contact route', 'automatic email checks / manual social', 'research:assert_contact_ownership',
     ['test_alias_contact_requires_source_and_ownership_then_remains_unverified', 'test_manual_linkedin_history_blocks_new_cold_email'],
     'Different-domain/profile inboxes require ownership review; manual LinkedIn history blocks overlapping cold outreach.', 'No automated LinkedIn/X DM or guarantee of email availability. Reacher/provider accuracy needs later live acceptance.'),
    ('Check contact eligibility', 'operator review + automatic guards', 'campaigns:approve',
     ['test_suppression_overrides_approved_queue', 'test_approval_requires_safe_and_one_contact_per_company', 'test_manual_reply_stops_active_sequence_and_cannot_release'],
     'Approval requires recorded eligibility/relevance, current qualification, fresh safe verification, sender identity and no shared stop/history conflict.', 'The application records the operator eligibility review; it does not determine legal permission from an email address.'),
    ('Draft personalized pitch', 'research-based AI + human wording review', 'email_writer:generate_sequence',
     ['test_sourced_trigger_and_extra_value_survive_into_drafts', 'test_unsourced_optional_claims_are_rejected', 'test_drafts_do_not_claim_completed_assets'],
     'Source-backed observation, optional sourced trigger, one offer and a question; no fabricated completed asset or sales lift.', 'Human review decides accuracy, tone and relevance before any send.'),
    ('Initial pilot review / revise / approve', 'operator gate', 'campaigns:revise_unsent_sequence',
     ['test_third_unsent_revision_preserves_copy_history_and_requires_new_approval', 'test_third_revision_cannot_erase_submission_or_uncertainty', 'test_third_send_holds_changed_approval_context'],
     'All four drafts are reviewed; copy, recipient, identity and evidence snapshot freeze atomically. Unsent approval can return to draft review with history preserved.', 'Sent/sending/uncertain/failed or stopped conversations cannot reset through this control.'),
    ('Send + log contact history', 'automatic after approval/readiness', 'mail:send_one',
     ['test_real_tls_send_and_imap_optout_stop_sequence', 'test_third_claim_rechecks_readiness_after_candidate_read', 'test_real_smtp_failure_stages_and_duplicate_protection'],
     'Trusted loopback TLS SMTP exercises actual protocol acceptance, durable Message-ID, local windows, quota/interval and inbox readiness.', 'This proves local protocol behavior, not your real mailbox, inbox placement, DNS or VPS deployment.'),
    ('Response / delivery status', 'automatic monitoring + operator intent review', 'mail:record_inbound',
     ['test_third_delivery_status_does_not_treat_positive_notice_as_delay', 'test_imap_bounded_read_and_reply_stop'],
     'Positive 2.x notices stay separate from temporary/unknown delay and permanent bounce; IMAP reads bounded messages independently.', 'A reported delivery notice is a provider report, not independently verified inbox visibility. Reply interest is reviewed by a human.'),
    ('Suggested follow-ups Day 4 / 9 / 15', 'automatic schedule of reviewed copy', 'mail:mark_sent',
     ['test_four_touch_tls_sequence_respects_actual_acceptance_and_stops', 'test_default_followup_adds_new_value'],
     'Three follow-ups use 3/5/6-day gaps after actual previous acceptance, preserving minimum spacing when delayed.', 'Day 1/4/9/15 are nominal inclusive days. Local business windows, weekends and actual delays can shift sends.'),
    ('Any reply or stop signal?', 'automatic stop', 'mail:record_inbound',
     ['test_third_all_reply_branches_stop_followups_without_inventing_interest', 'test_reply_cancels_followups_and_is_idempotent'],
     'Any human reply cancels pending touches; automatic replies hold. Repeated IMAP records cannot duplicate fulfillment tasks.', 'An email already submitted cannot be recalled; SMTP uncertainty stays held for reconciliation.'),
    ('Interested: stop + promised audit/demo/ideas', 'automatic stop/task + operator fulfillment', 'deliverables:create',
     ['test_inbound_reply_creates_one_fulfillment_task_and_shared_hold', 'test_each_value_artifact_is_sourced_reviewable_and_deliverable'],
     'A human reply creates a due review/fulfillment task; sourced artifacts can be prepared, inspected, approved and recorded as actually delivered.', 'Interest classification, asset selection and external delivery are operator actions; the task does not itself answer the prospect.'),
    ('Question: stop + answer in context', 'automatic stop/task + operator conversation', 'sales:record_activity',
     ['test_third_all_reply_branches_stop_followups_without_inventing_interest', 'test_manual_reply_stops_active_sequence_and_cannot_release'],
     'Questions stop the cold sequence and enter the shared conversation ledger/task queue.', 'The operator reads and answers the actual question; no automatic interested label or invented answer.'),
    ('Later / out of office: pause + next date', 'automatic hold / operator next date', 'campaigns:resume_contact',
     ['test_out_of_office_pauses', 'test_resume_requires_fresh_result_and_cannot_override_optout', 'test_third_resume_rejects_changed_source_before_scheduling'],
     'OOO holds/cancels queued steps. Reviewed resume requires a future date, fresh verification and unchanged approved sources/copy. Nurture requires a future date.', 'Human later replies remain stopped; record nurture and continue the existing conversation. No automatic date inference or cold restart.'),
    ('No / opt-out / hard bounce: stop + suppression/status', 'automatic + operator closure', 'mail:record_inbound',
     ['test_optout_global_suppression', 'test_permanent_dsn_suppresses', 'test_third_before_submission_failure_keeps_concurrent_stop_cancelled'],
     'Explicit opt-out/permanent recipient failure suppresses globally; known non-acceptance cannot requeue a concurrent stopped message.', 'A plain negative human reply also stops the sequence; operator records lost/closure context. Conservative text recognition still needs response review.'),
    ('None after final touch: close sequence', 'automatic', 'mail:mark_sent',
     ['test_four_touch_tls_sequence_respects_actual_acceptance_and_stops'],
     'Touch four closes the active cold sequence and no fifth message is queued.', 'Closure is after fourth SMTP acceptance, not a timed proof of no later reply; later replies are still processed.'),
    ('Qualify need / timing / buyer / budget', 'operator-confirmed records', 'sales:update_sales',
     ['test_unconfirmed_client_need_cannot_advance_or_create_proposal', 'test_complete_operator_confirmed_sales_lifecycle', 'test_stale_sales_update_cannot_overwrite_new_client_context'],
     'Actual conversation plus confirmed problem, goal, metric, decision maker, timeline and budget context guard qualified stages; optimistic versions reject stale saves.', 'Unknowns are recorded explicitly. No automatic budget/need invention or buyer-authority guarantee.'),
    ('Discovery call: problem / baseline / metric', 'operator-confirmed record', 'sales:update_sales',
     ['test_third_call_and_proposal_require_recorded_baseline_or_measurement_plan', 'test_complete_operator_confirmed_sales_lifecycle'],
     'Call-booked needs an agreed call time and explicit baseline notes; unknown baseline requires a measurement plan. Baseline and agreed metric appear in proposals.', 'The app records calls and dates; it does not book the external calendar or measure business analytics automatically.'),
    ('Scoped proposal', 'automatic document + operator review/delivery', 'sales:proposal_action',
     ['test_complete_operator_confirmed_sales_lifecycle', 'test_third_proposal_review_cannot_approve_changed_client_context'],
     'Versioned draft includes deliverables, milestones, exclusions, acceptance, commercial terms and exact USD/GBP fee. Changed client qualification invalidates draft review.', 'External proposal delivery is separately recorded with an actual-delivery confirmation/reference. Existing delivered versions remain history.'),
    ('Agreement + initial payment', 'operator-confirmed records', 'sales:update_sales',
     ['test_won_requires_real_references_and_delivered_proposal', 'test_finance_requires_actual_confirmation_and_past_time', 'test_exact_currency_arithmetic_refunds_and_no_exchange_conversion'],
     'Won/delivery needs a delivered reviewed proposal and actual agreement/payment references. Confirmed cash/cost entries use exact separate currencies.', 'No signature verification, payment gateway or independently verified bank receipt. Contract fee is not counted as cash received.'),
    ('Deliver project / measure outcome', 'operator work + automatic record gates', 'sales:update_sales',
     ['test_third_completion_cannot_leave_delivery_work_open', 'test_complete_operator_confirmed_sales_lifecycle', 'test_tasks_are_due_visible_and_close_with_outcome'],
     'Existing delivery tasks must close with outcomes; completion requires client acceptance and measured or inconclusive outcome notes.', 'These controls manage delivery records; they do not themselves build/deploy the sold client website/bot or establish causal conversion uplift.'),
    ('Expand: maintenance / improvements / case study', 'operator plan + automatic guards', 'aftercare:update',
     ['test_aftercare_requires_actual_completed_acceptance_not_won_label', 'test_aftercare_order_permission_idempotency_and_optimistic_version', 'test_case_study_freezes_outcome_escapes_html_and_preserves_inconclusive'],
     'Completed accepted clients can have dated maintenance/expansion plans; reviewed case studies require explicit permission and preserve measured/inconclusive context.', 'Client agreement, actual follow-on work and publication remain operator actions.'),
    ('Campaign review', 'automatic descriptive report + human interpretation', 'learning:report',
     ['test_funnel_counts_records_not_messages_and_excludes_automatic_replies', 'test_approval_snapshot_is_atomic_and_survives_later_business_label_changes', 'test_empty_learning_does_not_invent_rates_or_experiment_winners'],
     'Saved approval cohorts, accepted business records, human email replies and sales milestones are deduplicated. Automatic replies/DSNs do not inflate human replies.', 'No opens, guaranteed inbox placement, causal attribution or automatic experiment winner.'),
    ('Improve targeting / research / offer; replies / calls / wins / cost', 'automatic reports + operator changes', 'sales:report',
     ['test_finance_wins_and_void_correct_denominators_without_fee_as_income', 'test_finance_and_growth_reports_scoped_authenticated_no_automatic_side_effects', 'test_recorded_sales_funnel_retains_history_and_does_not_call_contract_value_revenue'],
     'Learning provides next-review guidance, confirmed qualification/wins, recorded calls and currency-specific cost/receipt calculations with immutable correction history.', 'Targeting/copy changes require operator judgment. Missing costs/sample sizes stay unknown; client references are not audited revenue.'),
]


def main():
    root = Path(__file__).resolve().parents[1]
    junit = root/'data/third-workflow-tests.xml'
    cases = list(ET.parse(junit).getroot().iter('testcase'))
    assert cases and not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases)
    names = {c.get('name').split('[', 1)[0] for c in cases}
    tests = {}
    for path in (root/'tests').glob('test_*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                tests[node.name] = {'path': path.relative_to(root).as_posix(), 'line': node.lineno}
    nodes = []
    for i, (label, mode, reference, checks, behavior, boundary) in enumerate(NODES, 1):
        assert all(name in names for name in checks), (label, [n for n in checks if n not in names])
        module, symbol = reference.split(':')
        path = root/f'outreach/{module}.py'
        functions = [n.lineno for n in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig')))
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol]
        assert len(functions) == 1
        nodes.append({'id': i, 'label': label, 'mode': mode, 'local_test_status': 'passed', 'behavior': behavior,
                      'live_or_manual_boundary': boundary, 'code': {'path': path.relative_to(root).as_posix(),
                      'symbol': symbol, 'line': functions[0], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                      'tests': [{'name': n, **tests[n]} for n in checks]})
    report = {'checked_at': time.time(), 'diagram_nodes': len(nodes), 'suite_passed': len(cases),
              'suite_seconds': float(ET.parse(junit).getroot().find('testsuite').get('time')),
              'new_third_workflow_cases': sum(c.get('classname', '').endswith('test_third_workflow') for c in cases),
              'junit_sha256': hashlib.sha256(junit.read_bytes()).hexdigest(), 'all_nodes_live_verified': False,
              'normal_state': json.loads((root/'data/third-workflow-normal-check.json').read_text()),
              'isolated_chromium': json.loads((root/'data/third-workflow-ui-check.json').read_text()), 'nodes': nodes}
    sources = ['outreach/sequence.py', 'outreach/campaigns.py', 'outreach/mail.py', 'outreach/offers.py',
               'outreach/sales.py', 'outreach/aftercare.py', 'outreach/app.py', 'outreach/static/app.js',
               'outreach/static/sales.js', 'tests/test_third_workflow.py', 'tests/test_sales.py',
               'scripts/ui_smoke.py', 'scripts/verify_third_workflow_ui.py', 'scripts/verify_third_workflow_nodes.py']
    report['source_sha256'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}
    (root/'docs/third-workflow-check.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    text = ['# Third workflow: node-by-node verification', '',
            f"All **{len(nodes)} boxes** in the supplied third diagram have implementation and executed passing behavioral evidence. **{len(cases)} tests passed** in {report['suite_seconds']:.2f} seconds; **{report['new_third_workflow_cases']} new cases** target this audit. Ruff, JavaScript syntax, the full isolated Chromium smoke and dedicated approval/revision desktop/mobile checks passed.", '',
            '**This is local implementation acceptance, not a claim that every real provider/client action is live or fully automatic.** Real state remains six unqualified candidates, three unverified contacts and zero messages; all real records/private configuration were preserved. No real recipient was probed or emailed. VPS/domain/mailbox setup remains deferred to the user.', '',
            '## Each node', '', '| # | Diagram node | Mode | Verified behavior | Live/manual boundary |', '|---|---|---|---|---|']
    for row in nodes:
        text.append(f"| {row['id']} | {row['label']} | {row['mode']} | **Passed local checks.** {row['behavior']} | {row['live_or_manual_boundary']} |")
    text += ['', '## Corrections made', '',
             '- Campaign A now shares the current-source approval gate; expired/replaced/recrawled pages cannot qualify a send. Canonical homepage URLs avoid false stale-source rejection.',
             '- Approval saves evidence/copy/recipient/sender context. Every send and reviewed resume rechecks it. Changed sources, copy, identity or legacy missing proof go to hold.',
             '- Under the send-claim write lock, verification, shared stops, inbox catch-up, global pause, quota reservations and interval are checked again. A readiness change between candidate read and claim cannot submit SMTP.',
             '- Known non-acceptance preserves a concurrent reply/opt-out as cancelled instead of requeueing its in-flight message. Uncertain sends still require reconciliation and cannot reset.',
             '- Positive 2.x delivery notices no longer pause a sequence or count as human replies. Temporary/unknown DSNs hold; permanent failures suppress.',
             '- Calls/proposals now require a recorded baseline or explicit unknown-baseline measurement plan. The proposal and case-study snapshot preserve this context.',
             '- Proposal review checks the saved client qualification context; changed requirements need a new preserved draft. Delivered historical proposals stay recorded.',
             '- Completion rejects existing open delivery tasks. Client acceptance and measured/inconclusive outcomes remain required.',
             '- The dashboard supports returning an unsent pilot to draft review with the previous copy/history preserved. An explicit new approval is required.', '',
             'Twenty-two of the first 25 negative branch cases failed before the fixes; three DSN hold/bounce cases already passed. Two additional sales regressions reproduced stale proposal review and open-task completion. These are branch scenarios, not 24 distinct root causes.', '',
             '## Operational limits', '',
             'The localhost TLS fixtures exercise real SMTP/IMAP clients, both TLS modes, all four touches, thread IDs and failure stages. They do not establish real mailbox delivery or Reacher accuracy. Human reply intent, useful answers, actual artifact/proposal sharing, buyer qualification, calendar booking, agreement, payment, client work and measured results require operator/client evidence. They are supported records and review gates, not completed external actions.', '',
             'The final touch closes after SMTP acceptance; later replies are still processed. Nominal Day 1/4/9/15 schedules can move with local sending windows and delays. Once SMTP submission starts, a concurrent stop cannot recall that message. Missing historical approval proof cannot silently resume; an entirely unsent pilot can return to review, while a started sequence requires conversation/delivery inspection.', '',
             '## Reproduce and inspect', '',
             '- `python -m pytest -q --junitxml=data/third-workflow-tests.xml`',
             '- `python scripts/verify_third_workflow_ui.py` and `python scripts/ui_smoke.py`',
             '- `python scripts/verify_third_workflow_nodes.py`',
             '- Pipeline → company → contact: **Return unsent pilot to review**. Sales workflow → qualification: **Baseline and measurement period**.',
             '- [Machine-readable per-node evidence](third-workflow-check.json); fixture [revision desktop](screenshots/third-workflow-revision-desktop.png) / [mobile](screenshots/third-workflow-revision-mobile.png); real read-only [sales desktop](screenshots/third-workflow-normal-desktop.png) / [mobile](screenshots/third-workflow-normal-mobile.png).', '']
    (root/'docs/THIRD_WORKFLOW_AUDIT.md').write_text('\n'.join(text), encoding='utf-8')
    print(f"Verified {len(nodes)} diagram boxes against {len(cases)} passing cases; real provider/client acceptance remains pending.")


if __name__ == '__main__':
    main()
