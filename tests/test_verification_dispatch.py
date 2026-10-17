"""Real adapter awaits must not disclose or apply results after source revocation."""
import json

import httpx
import pytest

from outreach.research import verify_contact


@pytest.mark.parametrize("boundary", ["readiness", "client_open", "response"])
@pytest.mark.parametrize("change", ["publication", "suppression", "global_suppression", "recipient"])
async def test_verification_rechecks_at_dispatch_and_result_commit(db, settings, prepared, safe_result, monkeypatch, boundary, change):
    cid = prepared['contact_id']
    db.execute("UPDATE contacts SET verification='unverified',verification_raw='{}',verified_at=NULL WHERE id=?", (cid,))
    calls = []
    opens = []

    def revoke():
        if change == 'publication':
            db.execute("UPDATE evidence SET text='Business inquiries now use a form only'")
        elif change == 'recipient':
            db.execute("UPDATE contacts SET email='new-buyer@bright-demo.com' WHERE id=?", (cid,))
            db.execute("UPDATE evidence SET text='Business inquiries new-buyer@bright-demo.com'")
        else:
            db.suppress('alex@bright-demo.com', 'Fictional opt-out during provider await')
            if change == 'global_suppression':
                # Legacy status drift must not erase the authoritative opt-out.
                db.execute("UPDATE contacts SET status='new' WHERE id=?", (cid,))

    def handle(request):
        address = json.loads(request.content)['to_email']
        calls.append(address)
        if address == 'invalid-address-without-at-sign':
            if boundary == 'readiness':
                revoke()
            return httpx.Response(200, json={'input': address, 'is_reachable': 'invalid'})
        if boundary == 'response':
            revoke()
        return httpx.Response(200, json={**safe_result, 'input': address})

    original = httpx.AsyncClient

    class Client(original):
        async def __aenter__(self):
            opened = await super().__aenter__()
            opens.append(True)
            if len(opens) == 2 and boundary == 'client_open':
                revoke()
            return opened

    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(ValueError):
        await verify_contact(db, settings, cid)
    real_calls = [a for a in calls if a != 'invalid-address-without-at-sign']
    assert real_calls == (['alex@bright-demo.com'] if boundary == 'response' else [])
    row = db.one('SELECT * FROM contacts WHERE id=?', (cid,))
    assert row['verification'] != 'safe'
    if change == 'recipient':
        assert row['email'] == 'new-buyer@bright-demo.com'
        assert row['verification'] == 'unverified' and row['verified_at'] is None
    if change == 'suppression':
        assert row['status'] == 'suppressed'
    assert not db.one("SELECT 1 FROM events WHERE kind='verification' AND json_extract(detail,'$.verdict')='safe'")
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")


async def test_verification_unchanged_source_still_uses_real_adapter(db, settings, prepared, safe_result, monkeypatch):
    calls = []

    def handle(request):
        address = json.loads(request.content)['to_email']
        calls.append(address)
        return httpx.Response(200, json={'input': address, 'is_reachable': 'invalid'}
                              if address == 'invalid-address-without-at-sign' else safe_result)

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    await verify_contact(db, settings, prepared['contact_id'])
    assert calls == ['invalid-address-without-at-sign', 'alex@bright-demo.com']
    assert db.one('SELECT verification FROM contacts WHERE id=?', (prepared['contact_id'],))['verification'] == 'safe'
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")
