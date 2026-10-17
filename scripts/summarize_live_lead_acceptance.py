"""Build a scoped acceptance report from real saved runs, excluding rejected noise."""
import hashlib
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.profiles import canonical_profile
from outreach.research import current_evidence, contact_candidates, add_contact, assert_contact_ownership
from verify_live_lead_acceptance import fingerprint, write

SELECTION = [
    ('UK', 'A', 'Dental', 'bespokedentalclinics.co.uk', 'Manchester M30 7HZ'),
    ('UK', 'A', 'Florist', 'bristolfloraldesign.co.uk', '1 Waterloo Street, Clifton, Bristol, BS8 4BT'),
    ('UK', 'B', 'Beauty retail', 'blommabeauty.com', 'London EC1V 1NQ United Kingdom'),
    ('UK', 'B', 'Coffee', 'origincoffee.co.uk', 'Cornwall England United Kingdom'),
    ('US', 'A', 'Dental', 'atxfamilydental.com', '1700 S. 1st Street Austin, Texas 78704'),
    ('US', 'A', 'Roofing', 'unitedroofingcolorado.com', 'Denver, CO'),
    ('US', 'B', 'Skincare', 'unfilteredskincare.com', 'Bath, Maine'),
    ('US', 'B', 'Coffee', 'usroast.com', 'located in Mount Pleasant, Texas'),
]


def main():
    root = Path(__file__).resolve().parents[1]
    pointer = json.loads((root/'data/live-lead-acceptance-latest.json').read_text(encoding='utf-8'))
    output = Path(pointer['report']).parent
    baseline = json.loads(Path(pointer['report']).read_text(encoding='utf-8'))
    matrix_path = output/'current-sources-final/report.json'
    matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
    platform_path = output/'current-sources/report.json'
    platforms = json.loads(platform_path.read_text(encoding='utf-8'))
    replacement_path = output/'current-sources-final/replacement-crawls.json'
    replacements = json.loads(replacement_path.read_text(encoding='utf-8'))
    assert all(r.get('finished_at') for r in (baseline, matrix, platforms, replacements)), 'Wait for all live runs'
    db = DB(Path(pointer['database']))
    corrected = DB(Path(matrix['database']))
    normal = DB(Settings().database)
    before = fingerprint(normal)
    assert normal.get('paused') == 'true'
    # Actual official source explicitly identifies an owner and their Gmail.
    # This is inbox publication/ownership review, not consent, mailbox existence
    # or confirmation that this person will purchase our services.
    lead = db.one("SELECT * FROM leads WHERE domain='unfilteredskincare.com'")
    page = next(e for e in current_evidence(db, lead['id']) if e['url'].endswith('/contact'))
    owner_quote = 'Brionne Beck | Owner & Creator unfilteredbodyproducts@gmail.com Bath, Maine'
    assert owner_quote in page['text']
    cid = add_contact(db, lead['id'], 'unfilteredbodyproducts@gmail.com', page['url'], 'Brionne Beck', 'Owner & Creator',
                      'Current official Contact page explicitly publishes Brionne Beck as Owner & Creator immediately beside this Gmail and Bath, Maine. The exact saved source supports business contact publication; mailbox control, interest, buying authority for this project and outreach eligibility remain unconfirmed.')
    assert_contact_ownership(db, db.one('SELECT * FROM contacts WHERE id=?', (cid,)), lead)

    rows = []
    for market, campaign, segment, domain, country_quote in SELECTION:
        source_db = corrected if domain in {'unitedroofingcolorado.com', 'usroast.com'} else db
        lead = source_db.one('SELECT * FROM leads WHERE domain=?', (domain,))
        pages = current_evidence(source_db, lead['id'])
        geo = next((e for e in pages if country_quote in e['text']), None)
        assert geo, f'Current geographic quote missing: {domain}'
        contacts = []
        for c in source_db.all('SELECT * FROM contacts WHERE lead_id=?', (lead['id'],)):
            assert_contact_ownership(source_db, c, lead)
            contacts.append({'email': c['email'], 'source_url': c['source_url'], 'name': c['name'], 'role': c['role'],
                             'verification': c['verification'], 'status': c['status'], 'publication_guard': True,
                             'same_company_domain': c['email'].split('@')[1] == domain})
        crawl = json.loads(source_db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))['report'])
        rows.append({'market': market, 'campaign': campaign, 'segment': segment, 'domain': domain,
                     'company': lead['company'], 'lead_id': lead['id'], 'isolated_database': str(source_db.path) if hasattr(source_db, 'path') else str(source_db),
                     'current_pages': len(pages), 'crawl_status': crawl['status'], 'crawl_issues': len(crawl.get('errors', [])),
                     'remaining_urls': crawl.get('remaining'), 'contacts': contacts, 'review_candidates': contact_candidates(source_db, lead['id']),
                     'country_review': {'quote': country_quote, 'url': geo['url'], 'evidence_id': geo['id'], 'sha256': geo['sha256'],
                                        'interpretation': 'Researcher geographic interpretation of current official publication; not registered legal-entity or buyer validation'},
                     'evidence': [{'id': e['id'], 'url': e['url'], 'sha256': e['sha256'], 'fetched_at': e['fetched_at']} for e in pages],
                     'outreach_qualified': False})
    repeated = []
    for cell in matrix['waves']:
        if cell['wave'] != 1:
            continue
        second = next(c for c in matrix['waves'] if c['wave'] == 2 and c['market'] == cell['market'] and c['campaign'] == cell['campaign'] and c['segment'] == cell['segment'])
        first_domains = {c['domain'] for c in cell['companies']}
        second_domains = {c['domain'] for c in second['companies']}
        repeated.append({'market': cell['market'], 'campaign': cell['campaign'], 'segment': cell['segment'],
                         'wave_1_candidates': len(first_domains), 'wave_2_candidates': len(second_domains),
                         'domains_reused': first_domains == second_domains,
                         'ids_reused': set(cell['lead_ids']) == set(second['lead_ids'])})
    valid_profiles, rejected_profiles = [], []
    for search in platforms['profiles']:
        for checked in search['checked']:
            try:
                canonical_profile(checked['source_url'])
            except ValueError:
                rejected_profiles.append({'url': checked['source_url'], 'reason': 'Job/category route is not a specific business profile; the earlier diagnostic result is superseded'})
                continue
            signal = checked.get('signal', {})
            valid_profiles.append({'url': checked['source_url'], 'public_snapshot_state': signal.get('public_snapshot', {}).get('state'),
                                   'website_status': checked.get('profile', {}).get('website_status'),
                                   'first_resolution_state': signal.get('state'), 'first_resolution_website': signal.get('website'),
                                   'published_candidates': len(checked.get('published_candidates', [])),
                                   'current_saved_pages': len(checked.get('pages', [])), 'outreach_ready': False})
    recovery = baseline['recovery'][-1]
    result = {'checked_at': time.time(), 'live': True, 'fixtures': False, 'sending_enabled': False, 'messages_sent': 0,
              'email_verification_jobs_executed_this_check': 0, 'normal_database_unchanged': before == fingerprint(normal),
              'tests_passed': 575, 'junit_path': 'data/live-lead-final-tests.xml',
              'matrix': repeated, 'researched_representatives': rows,
              'counts': {'market_campaign_segment_cells': len(repeated), 'discovery_waves': 2,
                         'unique_indexed_company_candidates': len({c['domain'] for cell in matrix['waves'] for c in cell['companies']}),
                         'official_business_representatives': len(rows), 'current_official_pages': sum(r['current_pages'] for r in rows),
                         'company_domain_published_contacts': sum(c['same_company_domain'] for r in rows for c in r['contacts']),
                         'reviewed_other_domain_contact': 1, 'representatives_with_published_contact': sum(bool(r['contacts']) for r in rows),
                         'outreach_qualified_by_this_check': 0},
              'platform_profiles': valid_profiles, 'rejected_non_business_routes': rejected_profiles,
              'website_less_contact_path': {'accepted_current_public_email': 0,
                  'real_website_not_found_examples': [p for p in valid_profiles if p['website_status'] == 'website_not_found'],
                  'state': 'not_accepted', 'reason': 'No tested website-less business had a readable current published contact source plus reviewed identity/activity. Blocked or indexed-only emails remain held.'},
              'real_business_continuation': {'domain': recovery['company']['domain'], 'before_pages': recovery['prior_pages'],
                    'after_pages': len(recovery['pages']), 'old_evidence_preserved': recovery['old_evidence_preserved'],
                    'status': recovery['crawl_report']['status'], 'error': recovery['error']},
              'reviewed_owner_contact': {'email': 'unfilteredbodyproducts@gmail.com', 'owner_quote': owner_quote,
                                       'source_url': page['url'], 'evidence_sha256': page['sha256'], 'mailbox_verified': False,
                                       'website_less': False, 'outreach_approved': False},
              'limits': ['Two same-session search waves are a repeatability sample, not a long-term yield/SLA measurement.',
                         'Sixteen indexed candidates are not sixteen qualified buyers; eight representatives have reviewed current location/industry evidence.',
                         'Crawls preserve the 30-page, depth-3, always-Chromium production budgets; 360-second diagnostic limits caused reported interruptions. No whole-site completeness claim.',
                         'Nine valid platform profiles were inaccessible; five profile research passes found website candidates, with varying named-search resolution between passes. Private platform email access was not established.',
                         'PPH jobs can be useful manually, but a job/listing cannot establish a company with no website.',
                         'All retained inboxes need separate buyer/relevance/eligibility and fresh technical verification before outreach.',
                         'The florist continuation preserved evidence and added pages; remaining errors/frontier are still partial.',
                         'A real website-less contact path remains unaccepted. A search not finding a website never proves that none exists.'],
              'private_run_paths': [str(Path(pointer['report'])), str(matrix_path), str(platform_path), str(replacement_path)],
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'outreach').glob('*.py'))}}
    suites = ET.parse(root/result['junit_path']).getroot()
    cases = list(suites.iter('testcase'))
    assert len(cases) == result['tests_passed'] and not list(suites.iter('failure')) and not list(suites.iter('error'))
    assert all(c['domains_reused'] and c['ids_reused'] and c['wave_1_candidates'] == c['wave_2_candidates'] == 2 for c in repeated)
    assert result['normal_database_unchanged'] and normal.get('paused') == 'true'
    write(root/'docs/live-lead-acceptance-check.json', result)
    lines = ['# Live US/UK lead and source acceptance — 11 October 2026', '',
             '**575 tests passed. Real searches/crawls ran in isolated databases; no worker, sender or recipient verifier ran. The normal database stayed unchanged and sending remains disabled/paused.**', '',
             'This check establishes a bounded research sample. It does not establish bug-free software, universal platform access or a steady supply of qualified buyers.', '',
             '## Eight market/campaign/segment cells', '',
             'Two actual website-discovery waves returned two indexed company candidates per cell: 16 unique company domains, with identical domains and record IDs reused. The production crawler retained its 30-page/depth-3/always-Chromium settings. Restricted platforms were tested separately; this is not a full default eight-platform expansion for every matrix cell.', '',
             '| Market | Campaign | Segment | Researched official site | Current pages | Published contacts | Capture |',
             '| --- | --- | --- | --- | ---: | ---: | --- |']
    for row in rows:
        lines.append(f"| {row['market']} | {row['campaign']} | {row['segment']} | [{row['domain']}](https://{row['domain']}/) | {row['current_pages']} | {len(row['contacts'])} | {row['crawl_status']} |")
    lines += ['', f"These eight representatives preserve **{result['counts']['current_official_pages']} current official pages**, **{result['counts']['company_domain_published_contacts']} published company-domain addresses** and one separately reviewed public Gmail. Seven of eight had a published email; the dental clinic without one has a current contact/booking route. No recipient was marked outreach-qualified by this check. Buyer relevance and mailbox existence are separate.", '',
              'Blomma is a beauty retailer, not proven to manufacture its own product line. Damigrow remains an unresearched indexed candidate; the US skincare representative was Unfiltered, whose current source names Bath, Maine and its owner. Technical/order inboxes are publication findings, not confirmed purchasing contacts.', '',
              '## Fixes exposed by real queries', '',
              '- Generic adjectives admitted a local-time site and a dictionary article as roofing/coffee leads. Industry vocabulary now controls relevance for supported niches; explicit conflicting market signals are excluded, and an empty relevant search gets one bounded focused retry.',
              '- “Contact us” and all-caps “CONTACT US” cannot establish or contradict United States geography.',
              '- PeoplePerHour job/category pages and non-profile directory routes are rejected as business profiles. They cannot become false website-less companies.', '',
              '## Partial captures and restricted sources', '',
              f"The actual Bristol florist checkpoint continued from **{recovery['prior_pages']} to {len(recovery['pages'])} pages**, preserving every prior evidence ID/hash. Its report remains **{recovery['crawl_report']['status']}**: the diagnostic deadline ended the pass, so remaining coverage is not accepted as complete.", '',
              'All eight representative captures remain partial/interrupted. Some pass limits and render/resource issues persist. The initial pre-fix diagnostic was deliberately stopped while researching irrelevant sites; that controller stop is recorded separately from external site failures. Those sites and their contacts are excluded from the target-market results above.', '',
              '| Source | Actual result |', '| --- | --- |',
              '| LinkedIn | Two company profiles: robots denied; official named-search result unconfirmed/ambiguous. |',
              '| X | Two profiles: robots denied; official website candidates resolved. |',
              '| Facebook | Two profiles: robots denied; one current lookup found a website candidate, one ambiguous. |',
              '| Instagram | One profile: robots denied; website not found in the tested named search. No current identity/email proof. |',
              '| BBB | Two business profiles unavailable; independent named lookups found website candidates. |',
              '| PeoplePerHour | Two readable job/category pages rejected as business identities after the classification fix. |',
              '| Additional Yell hunt | Three real listings unavailable; no published email accepted. |', '',
              'SearXNG continued returning results while individual engines reported access denial, CAPTCHAs, rate limits or parsing errors. This demonstrates graceful degradation in this sample, not guaranteed future search availability. Platform resolution changed between some independent lookups; ambiguity stays reviewable.', '',
              '## Website-less contact path', '',
              '**Not accepted live.** The tested Instagram business signal had a completed no-match website search, but its profile was unreadable and had no current saved public contact evidence. No website-less email was imported, probed or approved. Synthetic regression tests cover the reviewed profile-to-contact route; they do not substitute for a real accessible business/email.', '',
              'The Unfiltered Gmail review is genuine current official-website evidence and names its owner. It proves an other-domain publication path; this business has a website, so it is not website-less acceptance.', '',
              '## Evidence and repeatable checks', '',
              'Sources, exact location quotes, hashes, contacts, per-platform states and the bounded acceptance limits are in [the machine-readable report](live-lead-acceptance-check.json). Full captured page text and raw run history stay in the private `data/live-lead-acceptance` directories, excluded from the source release.', '',
              'Run `python scripts/verify_live_lead_acceptance.py` for an isolated live diagnostic; `python scripts/verify_live_lead_sources.py --discovery-only` repeats the current website-search matrix. Large sites can exceed the explicitly reported audit deadlines. The full local application suite is `python -m pytest -q --junitxml=data/live-lead-final-tests.xml`.', '']
    (root/'docs/LIVE_LEAD_ACCEPTANCE.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'report': 'docs/LIVE_LEAD_ACCEPTANCE.md', 'counts': result['counts'],
                      'platform_profiles': len(valid_profiles), 'website_less_accepted': False, 'messages_sent': 0}))


if __name__ == '__main__':
    main()
