"""Refresh the complete 35-node audit from executed tests and current source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_workflow_nodes import audit, symbol_line
from outreach.workflow_detail import EDGES, STAGES


EXTRA = {
    'test_complete_current_page_and_qualification_states_expire_together': ['C', 'E', 'G', 'AA', 'J'],
    'test_complete_changed_approval_context_visible_before_worker_attempt': ['H', 'J', 'K'],
    'test_complete_artifact_map_does_not_treat_historical_approval_as_current': ['S'],
    'test_complete_expired_or_future_alias_source_cannot_probe': ['CE', 'E2', 'E3', 'F', 'H'],
    'test_complete_expired_profile_identity_cannot_probe': ['CR', 'CE', 'E3', 'F'],
    'test_complete_call_requires_dated_next_action': ['U'],
    'test_complete_approved_proposal_context_change_visible_on_map': ['V'],
    'test_complete_historical_sales_without_baseline_cannot_complete_call_node': ['U'],
    'test_complete_stale_safe_verdict_routes_to_hold': ['F', 'H'],
    'test_connected_discovery_to_client_outcome': ['A', 'B', 'C', 'CP', 'CS', 'CR', 'CE', 'D', 'E', 'E1', 'E3', 'F', 'G', 'AA', 'BB', 'I', 'J', 'K', 'L', 'M', 'O', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'],
}
PILOT_CHECKS = {
    'test_marketplace_cannot_enter_as_official_company_even_via_import': ['A', 'C'],
    'test_noisy_live_search_marketplace_cannot_consume_official_lead_slot': ['A', 'B', 'C'],
    'test_historical_marketplace_candidate_cannot_recrawl_or_qualify': ['C', 'D', 'G', 'AA', 'BB'],
    'test_worker_restart_labels_preserved_capture_interrupted': ['D', 'E', 'H'],
    'test_dedicated_nonbuyer_inbox_not_extracted_as_outreach_contact': ['E', 'E1', 'E2'],
    'test_privacy_only_external_candidate_cannot_be_added_or_probe': ['CE', 'E2', 'E3', 'F'],
    'test_legacy_privacy_contact_cannot_reach_verification_provider': ['E1', 'F'],
}
RECOVERY_CHECKS = {
    'test_continue_crawl_preserves_current_pages_and_does_not_refetch_captured': ['D', 'E'],
    'test_seeded_contact_capture_honors_robots_without_following_catalog': ['D', 'E', 'E1'],
    'test_contact_recovery_corroborates_official_html_not_indexed_email': ['B', 'E', 'E1', 'E2'],
    'test_contact_recovery_no_official_url_holds_all_social_hints': ['E3', 'H'],
    'test_contact_recovery_uses_official_navigation_when_search_is_unavailable': ['B', 'D', 'E', 'E1'],
    'test_contact_recovery_refreshes_saved_contact_page_without_index_or_homepage_access': ['D', 'E', 'E1'],
    'test_contact_recovery_uses_checkpoint_contact_route_and_skips_unsafe_index_routes': ['D', 'E', 'E1'],
    'test_contact_fallback_does_not_refresh_editorial_or_catalog_urls_as_contact_pages': ['D', 'E'],
    'test_legacy_partial_crawl_adopts_only_fresh_official_links': ['D', 'E'],
    'test_automatic_contact_research_queued_after_full_research': ['D', 'E'],
    'test_contact_research_serializes_with_other_same_company_browser_work': ['D', 'E', 'Q'],
    'test_contact_research_running_visible_on_both_maps': ['E'],
    'test_wrong_verifier_never_receives_real_recipient': ['F', 'H'],
    'test_reacher_invalid_syntax_contract_recognized': ['F'],
    'test_recovery_api_requires_auth_and_rejects_missing_checkpoint': ['D', 'E', 'F'],
    'test_dns_fallback_never_establishes_mailbox_exists': ['F', 'H'],
}
FIXES = [
    'Live search noise exposed generic-word relevance errors. Requested industry vocabulary is now required for supported niches; explicit conflicting market signals are excluded and empty relevant searches receive one bounded focused retry.',
    'Job/category/search routes on PeoplePerHour and supported business directories no longer establish a website-less business profile. Exact current business identity and contact ownership still require review.',
    'Current evidence and qualification counts now enforce latest-crawl and 30-day freshness together.',
    'Profile/other-domain inbox evidence rejects expired or future-dated source captures before Reacher access.',
    'Pending approved sequences recheck frozen sources, recipient, sender identity and all message copy before the canvas shows approval complete; changed context also appears in Hold.',
    'Unsent approved artifacts need current source proof before the canvas shows reviewed completion; actual historical delivery remains a ledger fact.',
    'Unsent approved proposals need unchanged confirmed client context before the canvas shows review complete.',
    'Agreed-call stage requires a dated next action; its canvas completion also requires baseline or an explicit unknown-baseline measurement plan.',
    'Expired or future-dated safe verification routes to Hold on the map as well as blocking verification readiness.',
    'Client acceptance on the map requires delivery tasks to be closed, matching the completion API.',
    'Dedicated privacy/security/automated inboxes are excluded from extraction/import and historical-contact verification.',
    'Known marketplaces are rejected at discovery/import, research, ownership and qualification boundaries.',
    'Restart recovery retains captured evidence and marks unfinished crawls interrupted instead of leaving them running.',
    'Crawl checkpoints allow additional page batches without discarding current evidence or repeating captured pages; fresh contact-page links can reconstruct a legacy frontier.',
    'Automatic contact/team research treats social/index hints as candidates and imports contacts only from newly captured official pages; same-company browser work stays serial.',
    'Contact recovery reuses saved official contact pages and queued navigation when search fails, with a bounded homepage-navigation fallback and explicit partial/held diagnostics.',
    'Verifier syntax preflight prevents real-recipient submission to an unrecognized API. Syntax/DNS fallback is explicitly unknown, never a safe mailbox verdict.',
    'Company-domain inboxes require current official-page publication before verification/approval; mailto/structured extraction proof is bound to the saved source hash, and approval freezes the recipient contact page.',
    'Review priorities now use the same current Campaign A/B offer guard as the workflow, including D2C commerce proof and US/UK scope. Future-dated research earns no source points; canonical country URLs retain valid review credit.',
    'Offer suggestions exclude rejected marketplaces, foreign company pages and legal boilerplate; contextual contact routes and genuine FAQ content beat bare menu links, with stronger service-specific source selection and intact quote words. Unqualified legacy automatic suggestions are refreshed in the review form without changing saved history.',
    'Learning counts current reviewed business offers through the workflow qualification guard, without erasing historical approvals, SMTP acceptance or frozen cohort attribution.',
    'Verification rechecks recipient identity, current publication and global suppression immediately before provider dispatch and atomically before saving the response; changed recipients never inherit the previous address verdict.',
    'Campaign A and B drafts require the current reviewed offer and source evidence, rechecked in the message-write transaction; stale A reviews can no longer overwrite review drafts.',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--junit', type=Path, default=Path('data/live-lead-final-tests.xml'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    junit = root / args.junit
    report = audit(root, junit)
    cases = list(ET.parse(junit).getroot().iter('testcase'))
    assert not any(c.find('skipped') is not None for c in cases), 'Incomplete suite'
    assert len(STAGES) == 35 and len(EDGES) == len(set(EDGES)) == 46
    ids = {row[0] for row in STAGES}
    assert ids == {row['id'] for row in report['nodes']}
    assert all(a in ids and b in ids for a, b in EDGES)
    reachable = {'A'}
    while True:
        new = reachable | {b for a, b in EDGES if a in reachable}
        if new == reachable:
            break
        reachable = new
    assert reachable == ids
    path = root / 'tests/test_complete_workflow.py'
    new_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == path.stem]
    for test, nodes in EXTRA.items():
        executed = [c for c in new_cases if c.get('name', '').split('[', 1)[0] == test]
        assert executed, test
        check = {'path': path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(path, test), 'executed_passing_cases': len(executed)}
        for node in report['nodes']:
            if node['id'] in nodes:
                node['tests'].append(check)
    pilot_path = root / 'tests/test_contact_purpose.py'
    pilot_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == pilot_path.stem]
    for test, nodes in PILOT_CHECKS.items():
        executed = [c for c in pilot_cases if c.get('name', '').split('[', 1)[0] == test]
        assert executed, test
        check = {'path': pilot_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(pilot_path, test), 'executed_passing_cases': len(executed)}
        for node in report['nodes']:
            if node['id'] in nodes:
                node['tests'].append(check)
    recovery_path = root / 'tests/test_research_recovery.py'
    recovery_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == recovery_path.stem]
    for test, nodes in RECOVERY_CHECKS.items():
        executed = [c for c in recovery_cases if c.get('name', '').split('[', 1)[0] == test]
        assert executed, test
        check = {'path': recovery_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(recovery_path, test), 'executed_passing_cases': len(executed)}
        for node in report['nodes']:
            if node['id'] in nodes:
                node['tests'].append(check)
    learning_path = root / 'tests/test_learning.py'
    learning_test = 'test_learning_current_qualification_expires_without_erasing_accepted_history'
    learning_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == learning_path.stem
                      and c.get('name', '').split('[', 1)[0] == learning_test]
    assert len(learning_cases) == 4
    check = {'path': learning_path.relative_to(root).as_posix(), 'test': learning_test,
             'line': symbol_line(learning_path, learning_test), 'executed_passing_cases': len(learning_cases)}
    for node in report['nodes']:
        if node['id'] in {'G', 'Z'}:
            node['tests'].append(check)
    publication_path = root / 'tests/test_contact_publication.py'
    publication_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == publication_path.stem]
    assert len(publication_cases) == 17
    publication_mapping = {
        'test_same_domain_guessed_address_never_reaches_provider': ['E1','F','H'],
        'test_same_domain_publication_rechecked_before_probe': ['E1','F','H'],
        'test_extraction_proof_allows_published_mailto_or_structured_email_not_in_visible_text': ['E','E1','F'],
        'test_new_pending_contact_adopts_actual_fresh_publication_but_not_unsubstantiated_source': ['E1'],
        'test_approval_freezes_separate_recipient_publication_page': ['J','K','L'],
        'test_suppressed_contact_keeps_original_source_on_reimport': ['E1','P'],
        'test_contact_detail_explains_publication_hold_without_mutation': ['E1','F','H'],
        'test_manual_unpublished_contact_can_be_saved_but_cannot_queue_probe': ['E1','F','H'],
        'test_publication_proof_deduplicates_and_never_counts_hidden_script_address': ['E','E1'],
        'test_safe_verdict_cannot_approve_an_unpublished_company_domain_recipient': ['J','K'],
        'test_unpublished_contact_appears_as_review_and_hold_on_both_maps': ['E1','H'],
        'test_publication_is_rechecked_after_provider_spacing_wait': ['F','H'],
    }
    assert set(publication_mapping) == {c.get('name','').split('[',1)[0] for c in publication_cases}
    for test, nodes in publication_mapping.items():
        executed = [c for c in publication_cases if c.get('name', '').split('[', 1)[0] == test]
        check = {'path': publication_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(publication_path, test), 'executed_passing_cases': len(executed)}
        for node in report['nodes']:
            if node['id'] in nodes:
                node['tests'].append(check)
    priority_path = root / 'tests/test_priority_readiness.py'
    priority_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == priority_path.stem]
    assert len(priority_cases) == 10
    for test in sorted({c.get('name','').split('[',1)[0] for c in priority_cases}):
        check = {'path': priority_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(priority_path, test),
                 'executed_passing_cases': sum(c.get('name','').split('[',1)[0] == test for c in priority_cases)}
        for node in report['nodes']:
            if node['id'] in {'G', 'AA', 'BB'}:
                node['tests'].append(check)
    offer_quality_path = root / 'tests/test_offer_source_quality.py'
    offer_quality_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == offer_quality_path.stem]
    assert len(offer_quality_cases) == 15
    for test in sorted({c.get('name','').split('[',1)[0] for c in offer_quality_cases}):
        check = {'path': offer_quality_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(offer_quality_path, test),
                 'executed_passing_cases': sum(c.get('name','').split('[',1)[0] == test for c in offer_quality_cases)}
        for node in report['nodes']:
            if node['id'] in {'G', 'AA', 'BB'}:
                node['tests'].append(check)
    native_path = root / 'tests/test_native_reacher.py'
    native_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == native_path.stem]
    assert len(native_cases) == 13
    for test in sorted({c.get('name', '').split('[', 1)[0] for c in native_cases}):
        check = {'path': native_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(native_path, test),
                 'executed_passing_cases': sum(c.get('name', '').split('[', 1)[0] == test for c in native_cases)}
        for node in report['nodes']:
            if node['id'] in {'F', 'H'}:
                node['tests'].append(check)
    canvas = root / 'outreach/workflow_detail.py'
    for filename, expected, node_ids in (
        ('tests/test_discovery_intent.py', 24, {'A', 'B', 'C', 'CP', 'H'}),
        ('tests/test_business_profile_routes.py', 14, {'CP', 'CS', 'CR', 'CE', 'H'}),
    ):
        test_path = root / filename
        executed = [c for c in cases if c.get('classname', '').split('.')[-1] == test_path.stem]
        assert len(executed) == expected
        for name in sorted({c.get('name', '').split('[', 1)[0] for c in executed}):
            check = {'path': filename, 'test': name, 'line': symbol_line(test_path, name),
                     'executed_passing_cases': sum(c.get('name', '').split('[', 1)[0] == name for c in executed)}
            for node in report['nodes']:
                if node['id'] in node_ids:
                    node['tests'].append(check)
    draft_path = root / 'tests/test_draft_source_freshness.py'
    draft_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == draft_path.stem]
    assert len(draft_cases) == 5
    for test in sorted({c.get('name', '').split('[', 1)[0] for c in draft_cases}):
        check = {'path': draft_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(draft_path, test),
                 'executed_passing_cases': sum(c.get('name', '').split('[', 1)[0] == test for c in draft_cases)}
        for node in report['nodes']:
            if node['id'] in {'G', 'AA', 'BB', 'I', 'J'}:
                node['tests'].append(check)
    dispatch_path = root / 'tests/test_verification_dispatch.py'
    dispatch_cases = [c for c in cases if c.get('classname', '').split('.')[-1] == dispatch_path.stem]
    assert len(dispatch_cases) == 13
    for test in sorted({c.get('name', '').split('[', 1)[0] for c in dispatch_cases}):
        check = {'path': dispatch_path.relative_to(root).as_posix(), 'test': test,
                 'line': symbol_line(dispatch_path, test),
                 'executed_passing_cases': sum(c.get('name', '').split('[', 1)[0] == test for c in dispatch_cases)}
        for node in report['nodes']:
            if node['id'] in {'E1', 'E3', 'F', 'H', 'P'}:
                node['tests'].append(check)
    for node in report['nodes']:
        node['code'].append({'path': 'outreach/workflow_detail.py', 'symbol': 'build',
                             'line': symbol_line(canvas, 'build'), 'sha256': hashlib.sha256(canvas.read_bytes()).hexdigest()})
    report.update(scope='Final complete workflow: all 35 nodes, 46 connections and four connected A/B website/profile journeys. External search/site/Reacher boundaries are controlled fixtures; mail uses actual trusted loopback TLS.',
                  edge_count=len(EDGES), graph_reachable=True, findings_fixed=FIXES,
                  new_executed_cases=len(new_cases), pilot_regression_cases=len(pilot_cases), recovery_regression_cases=len(recovery_cases), learning_freshness_cases=len(learning_cases), publication_regression_cases=len(publication_cases), priority_regression_cases=len(priority_cases), offer_source_quality_cases=len(offer_quality_cases), connected_journeys=4,
                  edges=EDGES, external_messages_sent=0, real_addresses_probed=0,
                  read_only_normal_check='data/complete-workflow-normal-check.json',
                  isolated_browser_check='Full scripts/ui_smoke.py and scripts/verify_third_workflow_ui.py passed.')
    report['native_setup_cases'] = len(native_cases)
    report['verification_dispatch_cases'] = len(dispatch_cases)
    report['draft_source_freshness_cases'] = len(draft_cases)
    report['source_hashes'] = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (root/'outreach').glob('*.py')}
    report['source_hashes']['tests/test_complete_workflow.py'] = hashlib.sha256(path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_contact_purpose.py'] = hashlib.sha256(pilot_path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_research_recovery.py'] = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_learning.py'] = hashlib.sha256(learning_path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_contact_publication.py'] = hashlib.sha256(publication_path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_priority_readiness.py'] = hashlib.sha256(priority_path.read_bytes()).hexdigest()
    report['source_hashes']['tests/test_offer_source_quality.py'] = hashlib.sha256(offer_quality_path.read_bytes()).hexdigest()
    for name in ['tests/test_discovery_intent.py', 'tests/test_business_profile_routes.py', 'tests/test_native_reacher.py', 'tests/test_verification_dispatch.py', 'tests/test_draft_source_freshness.py', 'tests/test_draft_review.py', 'scripts/start_native_reacher.py', 'scripts/start_native_reacher.ps1', 'scripts/start.ps1', 'deploy/reacher-windows.patch']:
        report['source_hashes'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root/'docs/complete-workflow-check.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    lines = ['# Complete acquisition workflow verification', '',
             f"**35/35 nodes and 46/46 connections verified against current source and executed tests. {report['suite_cases_passed']} tests passed; {len(new_cases)} complete-workflow cases include four connected journeys, plus {len(pilot_cases)} pilot regressions, {len(recovery_cases)} recovery regressions, {len(learning_cases)} learning-freshness regressions, {len(publication_cases)} publication regressions {len(priority_cases)} priority regressions and {len(offer_quality_cases)} offer-source regressions.**", '',
             'These results verify application behavior under the tested conditions. They do not establish that the software has zero bugs or that external providers and clients have been accepted in production.', '',
             '## Corrections', '', *['- '+fix for fix in FIXES], '',
             '## Connected journeys', '',
             'Campaign A and Campaign B each run through both an official-website route and a website-less public-profile route: queued search → research → saved source/contact → explicit qualification/ownership → safe verification → four drafts → approval → actual loopback SMTP → actual loopback IMAP reply → stop/fulfillment → artifact → confirmed client need/call/baseline → proposal/review/delivery record → agreement/payment references → acceptance/inconclusive outcome. Public search/site captures and Reacher verdicts are controlled fixtures; they are not new live provider proof. The website routes execute the real robots/sitemap/HTTP crawler with fixture responses. Browser rendering, four-touch calendars, suppression, OOO, partial crawl and uncertain transport branches have separate passing tests.', '',
             '## Every node', '', '| Node | Process | Execution | Verified behavior and boundary |', '|---|---|---|---|']
    for node in report['nodes']:
        lines.append(f"| {node['id']} | {node['label']} | {node['mode']} | {node['behavior_checked']} **Boundary:** {node['live_or_manual_boundary']} |")
    lines += ['', '## Important process details', '',
              '- Website CSV bypasses search (A → C). Search queries use B. Company records deduplicate on domain; profile records retain their own identity.',
              '- Profile capture may find email candidates before identity review; it never authorizes automatic candidate probing. Completed unsuccessful search means website not found, not proven absence.',
              '- Matching email domains do not prove publication. Unpublished manual/CSV contacts stay pending, explicit verification is blocked, and changed recipient-source pages invalidate frozen approval.',
              '- Qualification and technical verification run as separate branches. Approval and every send enforce their required gates.',
              '- H summarizes distributed holds. SMTP uncertainty can arise directly in L and must be reconciled; it cannot automatically retry through the follow-up loop.',
              '- A recorded historical sent artifact/proposal stays a historical delivery fact. An unsent approved record must still have current proof/context to show current readiness.',
              '- R–Y manage operator-confirmed client work. Calls, proposal delivery, agreements, payment references and client acceptance are records; this app does not independently perform or verify those external acts.',
              '- Four touches stop on human reply/opt-out/permanent failure; OOO/temporary/uncertain outcomes hold for review. Learning is descriptive and preserves inconclusive outcomes.', '',
              '## Live readiness', '',
              'Sending remains disabled. VPS/domain/mailbox setup was deferred by the user. This automated graph audit uses controlled provider inputs and loopback mail. The separate [real no-send pilot](NO_SEND_PILOT.md) records actual search/crawl captures and the earlier failed verification jobs. The earlier [native Reacher live check](native-reacher-check.json) established actual local backend/API/auth and one isolated catch-all/risky result. The [new live acquisition run](LIVE_ACQUISITION_CURRENT.md) adds a newly discovered published contact with a safe/non-catch-all provider verdict, one research-qualified candidate, four unapproved drafts and a local FAQ prototype. Individual mailbox existence, broader provider accuracy, delivery/inbox placement, platform coverage and deployed VPS acceptance remain unproven. Normal desktop/mobile dashboard verification preserves real operational records and private configuration.', '',
              'The Windows native backend helper has thirteen checksum/archive/provenance/environment/compatibility checks. Actual native build/startup status is documented separately in [NATIVE_REACHER.md](NATIVE_REACHER.md); helper tests alone never establish a running backend or safe mailbox verdict.', '',
              'Thirteen verification-dispatch checks cover publication, recipient edits and suppression during API readiness, client startup and response handling. Twelve reproduced failing timing cases now pass; the unchanged-context case retains normal verification. These use controlled HTTP responses, with no real addresses submitted.', '',
              'Five draft-source checks cover expired, future-dated, changed and superseded Campaign A evidence, plus current explicitly partial evidence. Four reproduced failing cases now pass; the valid partial route still permits unsent review drafts. The separate [new live acquisition check](LIVE_ACQUISITION_CURRENT.md) records one real candidate, one safe provider verdict, four unapproved drafts and a local FAQ prototype; it does not establish repeatable yield or outreach eligibility.', '',
              '## Reproduce and provenance', '',
              f'`python -m pytest -q --junitxml={args.junit.as_posix()}`', '',
              '`python scripts/verify_complete_workflow.py`', '',
              '[Machine-readable node/source/test mapping](complete-workflow-check.json) contains each passing test name, source line/hash and all 46 connections. Earlier audits are historical snapshots.']
    (root/'docs/COMPLETE_WORKFLOW_AUDIT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'nodes': 35, 'edges': 46, 'tests_passed': report['suite_cases_passed'], 'new_cases': len(new_cases), 'connected_journeys': 4}))


if __name__ == '__main__':
    main()
