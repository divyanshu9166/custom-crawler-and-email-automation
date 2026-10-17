"""Finish the audited US skincare route and resume a real florist checkpoint.

The original diagnostic was stopped after its pre-fix query admitted unrelated
sites. Preserve its captures, explicitly label the operator stop, and use the
separate current-code discovery results for relevance acceptance.
"""
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import research_lead, current_evidence, assert_contact_ownership
from outreach.research_status import snapshot
from verify_live_lead_acceptance import write, fingerprint


async def main():
    root = Path(__file__).resolve().parents[1]
    pointer = json.loads((root/'data/live-lead-acceptance-latest.json').read_text(encoding='utf-8'))
    path = Path(pointer['report'])
    output = path.parent
    report = json.loads(path.read_text(encoding='utf-8'))
    settings = Settings(_env_file=None, data_dir=output, worker_enabled=False, sending_enabled=False,
                        auto_contact_research=False, auto_visual_audit=False)
    db = DB(settings.database)
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    before = fingerprint(normal)
    interrupted = []
    for crawl in db.all('SELECT id,lead_id,report FROM crawls'):
        detail = json.loads(crawl['report'])
        if detail.get('status') == 'running':
            detail['status'] = 'interrupted'
            detail.setdefault('errors', []).append({'stage': 'audit_controller', 'reason': 'Operator stopped superseded pre-fix diagnostic; not an external source failure'})
            db.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(detail), crawl['id']))
            db.execute("UPDATE leads SET status='review',research_notes=? WHERE id=?",
                       ('Pre-fix diagnostic stopped deliberately. Not an accepted target-segment business; retained evidence is not outreach qualification.', crawl['lead_id']))
            interrupted.append({'lead_id': crawl['lead_id'], 'domain': db.one('SELECT domain FROM leads WHERE id=?', (crawl['lead_id'],))['domain'],
                                'pages_preserved': len(current_evidence(db, crawl['lead_id']))})
    report['pre_fix_diagnostic_stopped'] = {'at': time.time(), 'reason': 'Skip irrelevant pre-fix candidates; current-code website discovery and replacement crawls completed separately',
                                            'interrupted': interrupted, 'not_external_source_failures': True}
    report['discovery_superseded_by'] = str(output/'current-sources-final/report.json')
    write(path, report)

    async def capture(domain, continuation):
        lead = db.one('SELECT * FROM leads WHERE domain=?', (domain,))
        lid = lead['id']
        old = {e['id']: e['sha256'] for e in current_evidence(db, lid)}
        started = time.time()
        error = ''
        try:
            await asyncio.wait_for(research_lead(db, settings, lid, continuation=continuation), 360)
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)
        pages = current_evidence(db, lid)
        crawl = json.loads(db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))['report'])
        contacts = []
        for contact in db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,)):
            try:
                assert_contact_ownership(db, contact, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
                guard = True
            except ValueError:
                guard = False
            contacts.append({'id': contact['id'], 'email': contact['email'], 'source_url': contact['source_url'],
                             'publication_guard': guard, 'verification': contact['verification']})
        result = {'lead_id': lid, 'continuation': continuation, 'seconds': round(time.time()-started, 2), 'error': error,
                  'company': db.one('SELECT company,domain,website,campaign FROM leads WHERE id=?', (lid,)),
                  'crawl_report': crawl, 'contacts': contacts, 'pages': pages, 'prior_pages': len(old),
                  'old_evidence_preserved': all(any(e['id'] == eid and e['sha256'] == digest for e in pages) for eid, digest in old.items())}
        report['recovery' if continuation else 'crawls'].append(result)
        write(path, report)
        print(json.dumps({'stage': 'recovery' if continuation else 'skincare', 'domain': domain, 'pages': len(pages),
                          'prior_pages': len(old), 'old_evidence_preserved': result['old_evidence_preserved'],
                          'contacts': len(contacts), 'state': crawl.get('status'), 'error': error}), flush=True)

    await asyncio.gather(capture('unfilteredskincare.com', False), capture('bristolfloraldesign.co.uk', True))
    report['snapshot'] = snapshot(db)
    report['finished_at'] = time.time()
    report['normal_database_unchanged'] = before == fingerprint(normal)
    report['sending_paused'] = normal.get('paused') == 'true'
    report['isolated_messages'] = db.one('SELECT count(*) n FROM messages')['n']
    report['isolated_verified_contacts'] = db.one('SELECT count(*) n FROM contacts WHERE verified_at IS NOT NULL')['n']
    assert report['normal_database_unchanged'] and report['sending_paused']
    assert report['isolated_messages'] == report['isolated_verified_contacts'] == 0
    write(path, report)
    print(json.dumps({'stage': 'finished', 'report': str(path), 'counts': report['snapshot']['counts']}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
