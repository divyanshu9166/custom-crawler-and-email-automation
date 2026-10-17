"""Summarize actual recovery acceptance; preserve blocked and inconclusive results."""
import hashlib
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import fresh_evidence


def main():
    root = Path(__file__).resolve().parents[1]
    saved = json.loads((root/'data/recovery-live/submitted.json').read_text())
    db = DB(Settings().database)
    jobs = db.all('SELECT id,kind,state,error FROM jobs WHERE id>=? ORDER BY id', (min(saved['jobs']),))
    assert all(j['state'] in {'done', 'failed'} for j in jobs)
    assert db.get('paused') == 'true' and not db.one('SELECT 1 FROM messages')
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in saved['private_hashes'].items())
    cases = list(ET.parse(root/'data/recovery-tests.xml').getroot().iter('testcase'))
    assert cases and not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases)
    events = db.all("SELECT detail FROM events WHERE kind='contact_research' AND created_at>=? ORDER BY id", (saved['started_at'],))
    runs = [json.loads(e['detail']) for e in events]
    current = []
    for lid in [9,11]:
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        report = json.loads(db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))['report'])
        current.append({'id': lid, 'company': lead['company'], 'current_pages': len(fresh_evidence(db, lid)),
                        'status': lead['status'], 'crawl_status': report['status'],
                        'checkpoint_frontier': len(report.get('checkpoint', {}).get('frontier', [])),
                        'resume_history': report.get('resume_history', []),
                        'capture_urls': [p['url'] for p in report['pages']]})
    pointer = json.loads((root/'data/recovery-live/continuation-latest.json').read_text())
    practice = json.loads(Path(pointer['result']).read_text())
    bridge = json.loads((root/'data/recovery-live/social-bridge.json').read_text())
    contact = db.one('SELECT verification,verification_raw FROM contacts WHERE id=6')
    dns_result = json.loads(contact['verification_raw'])
    assert contact['verification']=='unknown' and dns_result['provider_status']['dns_precheck']['safe'] is False
    result = {'checked_at': time.time(), 'tests_passed': len(cases), 'new_recovery_cases': sum(c.get('classname','').endswith('test_research_recovery') for c in cases),
              'real_company_contact_research_runs': len(runs), 'official_contact_page_captures': sum(r['pages_saved'] for r in runs),
              'new_published_contacts': db.one('SELECT COUNT(*) n FROM contacts WHERE created_at>=?', (saved['started_at'],))['n'],
              'companies': current, 'actual_browser_controls': saved['actual_browser_controls'],
              'jobs': jobs, 'social_bridge': bridge, 'dns_only_provider_hold': dns_result,
              'practice_continuation': practice, 'external_messages_sent': 0, 'sending_disabled': True, 'paused': True,
              'private_settings_unchanged': True, 'reacher_started': False,
              'reacher_blocker': 'Configured local port 8080 serves Apache/httpd. Docker/Rust and a usable Linux distribution are unavailable; the real backend has not started.',
              'limits': ['Social/index hints do not expose private profile emails and can be missing/stale.',
                         'No new published contacts found in these real contact-research runs.',
                         'Processed checkpoint frontier is a bounded scope; render/access/depth restrictions keep overall coverage partial.',
                         'DNS MX records do not prove a mailbox exists. Reacher delivery verdicts remain unknown.',
                         'No login/CAPTCHA/robots restrictions bypassed; no paid prospect API used.'],
              'source_hashes': {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'outreach').glob('*.py')}}
    (root/'docs/recovery-live-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['tests_passed','new_recovery_cases','real_company_contact_research_runs','official_contact_page_captures','new_published_contacts','external_messages_sent','reacher_started']}))


if __name__ == '__main__':
    main()
