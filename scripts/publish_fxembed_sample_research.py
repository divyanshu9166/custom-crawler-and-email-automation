"""Publish measured sample evidence/hints for dashboard review, without recipients/jobs."""
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import official_root
from outreach.web import domain_of


def read_pointer(name):
    pointer = json.loads(Path('data', name + '-latest.json').read_text(encoding='utf-8'))
    path = Path(pointer['report'])
    return path, json.loads(path.read_text(encoding='utf-8'))


def main():
    profile_path, profiles = read_pointer('fxembed-business-sample')
    fallback_path, fallback = read_pointer('fxembed-contact-fallback')
    snapshots = {}
    for folder in (profile_path.parent, fallback_path.parent):
        for path in folder.glob('*.json'):
            if path.name != 'report.json':
                page = json.loads(path.read_text(encoding='utf-8'))
                if page.get('state') == 'captured':
                    snapshots[(page['url'], page['sha256'])] = page
    planned = []
    for row in profiles['results']:
        follow = next(item for item in fallback['results'] if item['profile_url'] == row['profile_url'])
        website = official_root(row['website_hint'])
        pages = []
        for item in follow['pages']:
            if item.get('state') != 'captured':
                continue
            assert domain_of(item['url']) == domain_of(website)
            assert time.time()-30*86400 <= item['observed_at'] <= time.time()+60
            page = snapshots[(item['url'], item['sha256'])]
            pages.append((page, item['observed_at']))
        assert pages, 'Only actual current captured company evidence may be published'
        planned.append((row, follow, website, pages))
    db = DB(Settings().database)
    now = time.time()
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        assert con.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == 'true'
        assert not con.execute("SELECT 1 FROM jobs WHERE state IN ('pending','running')").fetchone()
        assert not con.execute('SELECT 1 FROM schedules WHERE enabled=1').fetchone()
        counts = {table: con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in ('contacts', 'jobs', 'messages')}
        ids = []
        for row, follow, website, pages in planned:
            domain = domain_of(website)
            lead = con.execute('SELECT id FROM leads WHERE domain=?', (domain,)).fetchone()
            if lead:
                lid = lead[0]
                assert not con.execute("SELECT 1 FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lid,)).fetchone()
            else:
                lid = con.execute('INSERT INTO leads(domain,website,company,campaign,source_url,research_notes,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (domain, website, row['company'], row['campaign_hint'], row['profile_url'],
                     'Discovery country hint: ' + row['market_hint'] + '; country, business identity and buyer require review. Fixed sample research; no mailbox verification.',
                     'review', now, now)).lastrowid
            for page, observed in pages:
                con.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at',
                    (lid, page['url'], page.get('title', row['company']), page['text'], page['sha256'], observed))
            report = {'lead_id': lid, 'state': 'community_hints_available',
                'community_profile_hints': [row['community_profile']], 'captures': [], 'queries': [],
                'official_link_refresh': [{**item, 'reused_measured_capture': True} for item in follow['pages']],
                'note': 'Actual fixed-sample community response and current official company evidence. Native profiles were not requested in this sample; current buyer, country and mailbox need review.',
                'source_sample_report': str(profile_path), 'finished_at': now}
            key = 'fxsample:' + str(profile_path) + ':' + str(lid)
            con.execute('INSERT OR IGNORE INTO events(kind,external_id,detail,created_at) VALUES(?,?,?,?)',
                        ('professional_research', key, json.dumps(report), now))
            for item in follow['candidate_publications']:
                detail = {'lead_id': lid, 'email': item['email'], 'source_url': item['source_url'],
                    'evidence_sha256': item['source_sha256'], 'method': 'http_visible',
                    'reason': 'Published on the current company page; inbox ownership and buyer relevance require review',
                    'source_observed_at': item['source_observed_at'], 'buyer_verified': False}
                con.execute('INSERT OR IGNORE INTO events(kind,external_id,detail,created_at) VALUES(?,?,?,?)',
                    ('contact_candidate_found', key + ':' + item['email'], json.dumps(detail), now))
            ids.append(lid)
        assert all(con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == n for table, n in counts.items())
    result = {'published_at': now, 'lead_ids': ids, 'research_records': len(ids),
              'contacts_created': 0, 'jobs_created': 0, 'messages_created': 0, 'external_messages_sent': 0}
    Path('data/fxembed-dashboard-publication.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
