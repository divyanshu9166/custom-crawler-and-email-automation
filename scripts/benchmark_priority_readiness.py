"""Measure the 500-record review queue with isolated, explicitly fictional sources."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.priorities import ranked


def measure(folder, reviewed):
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False)
    db = DB(settings.database)
    now = time.time()
    with db.connect() as con:
        for index in range(500):
            host = f'business-{index}.example'
            website = f'https://{host}/'
            lid = con.execute('INSERT INTO leads(domain,website,company,campaign,source_url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                              (host, website, 'Fictional benchmark '+str(index), 'B', website, now, now)).lastrowid
            if not reviewed:
                continue
            quote, commerce = 'Contact our team with product questions.', 'We sell our own consumer products online.'
            eid = con.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                              (lid, website, 'Fictional source', 'Based in London UK. '+quote, 'fixture-home', now)).lastrowid
            commerce_id = con.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                                      (lid, website+'shop', 'Fictional commerce', commerce, 'fixture-commerce', now)).lastrowid
            address = 'hello@'+host
            con.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                        (lid, website+'contact', 'Fictional contact', address, 'fixture-contact', now))
            finding = {'evidence_id': eid, 'quote': quote, 'country_quote': 'Based in London UK.',
                'service': 'store_improvement', 'review_required': False,
                'offer_context': {'primary_goal': 'd2c_growth', 'goal_reviewed': True,
                    'selling_stage': 'selling_online', 'commerce_evidence_id': commerce_id,
                    'commerce_quote': commerce, 'd2c_fit_notes': 'Fictional reviewed product ownership and online sale process.'}}
            con.execute("UPDATE leads SET country='UK',country_source=?,timezone='Europe/London',business_type='corporate',status='qualified',service='store_improvement',findings=? WHERE id=?",
                        (website, json.dumps([finding]), lid))
            con.execute("INSERT INTO contacts(lead_id,email,source_url,unsubscribe_token,created_at,verification,verified_at) VALUES(?,?,?,?,?,'safe',?)",
                        (lid, address, website+'contact', 'fictional-token-'+str(index), now, now))
    before = {name: db.all('SELECT * FROM '+name) for name in ('jobs', 'messages', 'events')}
    started = time.perf_counter()
    result = ranked(db, settings)
    elapsed = time.perf_counter()-started
    assert len(result) == 500
    assert {name: db.all('SELECT * FROM '+name) for name in before} == before
    expected_score, expected_lane = (100, 'outreach_review') if reviewed else (0, 'research_review')
    assert all(r['priority']['score'] == expected_score and r['priority']['lane'] == expected_lane for r in result)
    return {'fixture_businesses': 500, 'reviewed': reviewed,
            'source_pages': 1500 if reviewed else 0, 'contact_records': 500 if reviewed else 0,
            'elapsed_seconds': round(elapsed, 4), 'read_only_records_preserved': True}


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='priority-readiness-') as temporary:
        result = {'checked_at': time.time(), 'scope': 'Local synthetic queue latency; not crawler, whole-VPS or real mailbox verification proof',
            'scenarios': [measure(Path(temporary)/'sparse', False), measure(Path(temporary)/'reviewed', True)],
            'sending_enabled': False, 'worker_enabled': False, 'network_requests': 0,
            'external_messages_sent': 0, 'normal_database_used': False}
    (root/'data/priority-readiness-benchmark.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
