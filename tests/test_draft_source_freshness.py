"""Campaign A drafts require current reviewed evidence, just as Campaign B does."""
import json
import time

import pytest

from outreach.campaigns import create_drafts


@pytest.mark.parametrize('change', ['expired', 'future', 'quote_changed', 'new_attempt'])
def test_campaign_a_stale_review_cannot_generate_or_overwrite_drafts(db, settings, prepared, change):
    cid, lid = prepared['contact_id'], prepared['lead_id']
    before = db.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (cid,))
    if change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    elif change == 'future':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()+120,))
    elif change == 'quote_changed':
        db.execute("UPDATE evidence SET text='Different business details without the reviewed observation'")
    else:
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
                   (lid, json.dumps({'status':'partial'}), time.time()))
    with pytest.raises(ValueError, match='current'):
        create_drafts(db, settings, cid)
    assert db.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (cid,)) == before
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('queued','sent')")


def test_campaign_a_current_partial_capture_can_generate_review_drafts(db, settings, prepared):
    cid, lid = prepared['contact_id'], prepared['lead_id']
    captured_at = time.time()-5
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
               (lid, json.dumps({'status':'partial'}), captured_at))
    create_drafts(db, settings, cid)
    rows = db.all('SELECT body,state FROM messages WHERE contact_id=? ORDER BY step', (cid,))
    assert len(rows) == 4 and all(row['state']=='draft' for row in rows)
    assert 'Your homepage invites visitors to contact you for a consultation.' in rows[0]['body']
