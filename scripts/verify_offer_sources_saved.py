"""Replay saved evidence into offline historical templates, not live AI email acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.campaigns import draft_sequence
from outreach.config import Settings
from outreach.db import DB
from outreach.opportunities import proposals
from outreach.research import fresh_evidence


def main():
    root = Path(__file__).resolve().parents[1]
    db = DB(Settings().database)
    tables = ('leads', 'evidence', 'contacts', 'crawls', 'jobs', 'messages', 'events')
    before = {table: db.all('SELECT * FROM '+table+' ORDER BY rowid') for table in tables}
    assert db.get('paused') == 'true' and not before['messages']
    rows, previews = [], ['# Unqualified, unsent draft previews from saved source pages', '',
        'These previews replay already saved public evidence. No new discovery, HTTP capture, buyer/country review, mailbox verification, approval or sending was performed. Each top suggestion is a candidate for review; it is not a final primary offer or a verified pain point. Stored discovery names may need identity review.', '']
    for lead in before['leads']:
        pages = fresh_evidence(db, lead['id'])
        by_id = {p['id']: p for p in pages}
        choices = proposals(lead, pages)
        for choice in choices:
            source = by_id[choice['evidence_id']]
            assert choice['quote'] in source['text'] and choice['review_required'] is True
        preview = []
        if choices:
            first = choices[0]
            preview = draft_sequence(lead['company'], first['service'], first, first['source_url'])
            assert len(preview) == 4
            previews += ['## '+lead['company'], '', 'Unreviewed candidate: '+first['service'], '',
                         'Saved source: '+first['source_url'], '', 'Saved quote: '+first['quote'], '']
            for draft in preview:
                previews += ['### Touch '+str(draft['step']+1)+' - '+draft['subject'], '', draft['body'], '']
        rows.append({'lead_id': lead['id'], 'company': lead['company'], 'domain': lead['domain'],
            'stored_status': lead['status'], 'country_reviewed': lead['country'] in {'US', 'UK'},
            'campaign': lead['campaign'], 'current_pages': len(pages), 'offer_candidates': choices,
            'unqualified_draft_preview': preview,
            'source_snapshots': [{'id': by_id[c['evidence_id']]['id'], 'url': c['source_url'],
                'sha256': by_id[c['evidence_id']]['sha256'], 'fetched_at': by_id[c['evidence_id']]['fetched_at']} for c in choices]})
    assert {table: db.all('SELECT * FROM '+table+' ORDER BY rowid') for table in tables} == before
    assert db.get('paused') == 'true'
    result = {'checked_at': time.time(), 'scope': 'Read-only replay of saved real public pages; not new live acquisition or qualified outreach',
        'results': rows, 'normal_records_unchanged': True, 'network_requests': 0,
        'verification_jobs_executed': 0, 'messages_persisted': 0, 'external_messages_sent': 0,
        'sending_paused': True, 'manual_country_buyer_and_offer_review_required': True,
        'source_hashes': {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
            for name in ('outreach/opportunities.py', 'outreach/campaigns.py', 'scripts/verify_offer_sources_saved.py')}}
    (root/'docs/offer-source-quality-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (root/'docs/OFFER_DRAFT_PREVIEWS.md').write_text('\n'.join(previews)+'\n', encoding='utf-8')
    print(json.dumps({'saved_candidates_replayed': len(rows), 'candidates_with_offer_preview': sum(bool(r['offer_candidates']) for r in rows),
        'draft_preview_touches': sum(len(r['unqualified_draft_preview']) for r in rows), 'records_unchanged': True,
        'messages_persisted': 0, 'network_requests': 0}))


if __name__ == '__main__':
    main()
