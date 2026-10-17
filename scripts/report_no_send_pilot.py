"""Publish honest results from the real normal-dashboard pilot, with no sending."""
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import official_root
from outreach.research import fresh_evidence, contact_candidates
from outreach.web import outreach_email_allowed


def main():
    root = Path(__file__).resolve().parents[1]
    latest = json.loads((root/'data/no-send-pilot-latest.json').read_text())
    directory = Path(latest['directory'])
    baseline = json.loads((directory/'baseline.json').read_text())
    db = DB(Settings().database)
    rows = []
    for lead in db.all('SELECT * FROM leads ORDER BY id'):
        if lead['id'] in baseline['lead_ids']:
            continue
        eligible = True
        if lead['lead_kind'] == 'website':
            try:
                official_root(lead['website'])
            except ValueError:
                eligible = False
        pages = fresh_evidence(db, lead['id'])
        contacts = db.all('SELECT id,email,status,verification,name,role,source_url FROM contacts WHERE lead_id=?', (lead['id'],))
        usable = [c for c in contacts if c['status'] != 'suppressed' and outreach_email_allowed(c['email'])]
        crawl = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
        crawl = json.loads(crawl['report']) if crawl else {}
        captures = crawl.get('pages', [])
        signals = db.all("SELECT detail FROM events WHERE kind IN ('screenshot','performance') AND json_extract(detail,'$.lead_id')=?", (lead['id'],))
        screenshots = any({'desktop', 'mobile'}.issubset(json.loads(e['detail']).get('files', {})) for e in signals)
        errors, render_issues = {}, {}
        for error in crawl.get('errors', []):
            reason = error.get('reason') or error.get('stage', 'unknown')
            errors[reason] = errors.get(reason, 0)+1
            for issue in error.get('issues', []):
                reason = issue.get('reason', 'unknown')
                render_issues[reason] = render_issues.get(reason, 0)+1
        rows.append({'id': lead['id'], 'company': lead['company'], 'website': lead['website'],
                     'campaign': lead['campaign'], 'state': lead['status'], 'source_eligible': eligible,
                     'crawl_state': crawl.get('status', 'not_started'), 'current_pages': len(pages),
                     'rendered_pages': sum(bool(p.get('rendered')) for p in captures), 'errors': errors,
                     'render_issues': render_issues,
                     'screenshots_desktop_mobile': screenshots, 'contacts': contacts,
                     'usable_published_contacts': len(usable), 'excluded_contacts': len(contacts)-len(usable),
                     'review_candidates': len(contact_candidates(db, lead['id'])),
                     'source_url': lead['source_url'], 'research_notes': lead['research_notes'],
                     'finding_previews': len(json.loads(lead['findings'])),
                     'pages': [{'url': p['url'], 'sha256': p['sha256']} for p in pages]})
    eligible = [row for row in rows if row['source_eligible']]
    jobs = db.all('SELECT id,kind,state,attempts,error,created_at FROM jobs WHERE id>? ORDER BY id', (baseline['last_job'],))
    assert jobs and all(job['state'] in {'done', 'failed'} for job in jobs), 'Pilot still has queued/running work'
    searches = []
    for event in db.all("SELECT detail FROM events WHERE kind='discovery' AND created_at>=? ORDER BY id", (min(j['created_at'] for j in jobs),)):
        detail = json.loads(event['detail'])
        report = detail['report']
        snapshot_states = {}
        for signal in report.get('signals', []):
            state = signal.get('public_snapshot', {}).get('state', 'unknown')
            snapshot_states[state] = snapshot_states.get(state, 0)+1
        searches.append({'query': detail['base_query'], 'campaign': detail['campaign'],
                         'country_hint': detail['country_hint'], 'lead_ids': detail['lead_ids'],
                         'queries': report.get('queries', []), 'signal_count': len(report.get('signals', [])),
                         'public_snapshot_states': snapshot_states,
                         'engine_reports': report.get('engine_reports', []),
                         'errors': report.get('errors', [])})
    assert db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('sent','sending','uncertain')")
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha for path, sha in baseline['private_hashes'].items())
    result = {'checked_at': time.time(), 'live': True, 'fixtures': False, 'normal_dashboard': True,
              'duration_seconds': round(time.time()-min(j['created_at'] for j in jobs)),
              'source_eligible_prospects': len(eligible), 'rejected_source_records': len(rows)-len(eligible),
              'current_official_pages': sum(row['current_pages'] for row in eligible),
              'rendered_official_pages': sum(row['rendered_pages'] for row in eligible),
              'usable_published_contacts': sum(row['usable_published_contacts'] for row in eligible),
              'excluded_contacts': sum(row['excluded_contacts'] for row in rows),
              'qualified_companies': sum(row['state']=='qualified' for row in eligible),
              'external_mail_sent': 0, 'approved_contacts': db.one('SELECT COUNT(*) n FROM contacts WHERE reviewed_at IS NOT NULL')['n'],
              'message_states': db.all('SELECT state,COUNT(*) n FROM messages GROUP BY state'),
              'private_configuration_unchanged': True, 'sending_disabled': True, 'paused': True,
              'final_pilot_search_signal_budget': 10, 'initial_search_signal_budget': 40, 'crawl_page_budget': 30,
              'rows': rows, 'jobs': jobs, 'searches': searches,
              'limits': ['Crawl completion remains partial when page/depth/render/robots limits apply.',
                         'A published inbox is not a verified mailbox or a confirmed relevant buyer.',
                         'The local Reacher syntax endpoint returned HTTP 404; no safe mailbox verdict established.',
                         'LinkedIn/X and other public platforms can return inaccessible/stale/ambiguous signals.',
                         'No qualified country/buyer/offer review, sequence approval or sending is fabricated.'],
              'fixes': ['Privacy/security/automated inbox filtering and historical-contact probe guard.',
                        'Marketplace exclusion in discovery, CSV/imports, research, ownership and qualification.',
                        'Worker recovery marks interrupted captures honestly while retaining their evidence.']}
    result['source_hashes'] = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (root/'outreach').glob('*.py')}
    (root/'docs/no-send-pilot-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    lines = ['# Real no-send acquisition pilot', '',
             f"Live search and normal-dashboard worker run: **{len(eligible)} website candidates, {result['current_official_pages']} current official pages, {result['usable_published_contacts']} published email candidates after purpose exclusions**. One collected marketplace record is retained as rejected history. **Zero emails sent, zero sequences approved.**", '',
             'These are research candidates. Published patient-support, press or partnerships inboxes still need buyer/contact-route review; their extraction is not approval for sales outreach.', '',
             '| Prospect | Campaign | Current pages | Published email candidates after exclusions | Result |', '|---|---|---:|---:|---|']
    for row in rows:
        company = row['company'].replace('|', '&#124;')
        lines.append(f"| [{company}]({row['website']}) | {row['campaign']} | {row['current_pages']} | {row['usable_published_contacts']} | {'Rejected marketplace/source' if not row['source_eligible'] else row['state']+'; crawl '+row['crawl_state']} |")
    lines += ['', '## Actual discovery runs', '', '| Query | Campaign / country hint | Queries issued | Public signals | Snapshot states |', '|---|---|---:|---:|---|']
    for search in searches:
        lines.append(f"| {search['query']} | {search['campaign']} / {search['country_hint']} | {len(search['queries'])} | {search['signal_count']} | {search['public_snapshot_states']} |")
    lines += ['', 'Search engine CAPTCHA, access-denial and rate-limit reports are saved. Indexed profile results can help resolve a company website; they do not establish readable profile content or an accessible profile email.', '',
              '## Findings and fixes', '', *['- '+fix for fix in result['fixes']], '',
              'The first UK dental candidate published a data-protection inbox. That record remains auditable and is excluded/suppressed specifically for nonbuyer purpose; it is not recorded as a recipient opt-out. Its patient-support address is still only a sourced contact, with buyer relevance unconfirmed. A noisy US roofing search initially selected IndiaMART; the corrected filters reject it and the real search selects SmartRoof instead. Updates were loaded through server restarts; queued work recovered and partial capture history is retained. Crawl limits stayed at 30 pages with real Chromium rendering. The initial UK search used the default 40-signal ceiling; subsequent runs cap deeper platform resolutions at 10 signals while still issuing all configured platform queries.', '',
              '## Where the real workflow stops', '', *['- '+limit for limit in result['limits']], '',
              'Source-backed finding previews and screenshots are research material. They are not confirmed pain points, improved conversions, buyer consent or client results. No phone/contact form was submitted and no LinkedIn/X/WhatsApp message was sent. VPS/domain/mailbox setup remains deferred by the user.', '',
              '[Full saved results and current source hashes](no-send-pilot-check.json). Detailed URLs, captures, reports and held contacts are visible in the normal dashboard at http://localhost:8000/. Raw run files stay under private data/no-send-pilot/.']
    (root/'docs/NO_SEND_PILOT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['source_eligible_prospects', 'rejected_source_records', 'current_official_pages', 'usable_published_contacts', 'excluded_contacts', 'external_mail_sent']}))


if __name__ == '__main__':
    main()
