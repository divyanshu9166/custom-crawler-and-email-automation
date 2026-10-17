"""Restart safety uses intercepted provider responses, never live X requests."""
import json
import sqlite3
import time

import httpx
import pytest

from outreach import fxembed, source_cache

URL='https://x.com/BrightFounder'
PROFILE={'code':200,'user':{'type':'profile','protected':False,'screen_name':'BrightFounder',
    'url':URL,'name':'Bright Demo','description':'Business enquiries: alex@bright-demo.com','location':'UK'}}


def restart(settings):
    return type(settings)(_env_file=None, **settings.model_dump())


def intercept(monkeypatch, handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(fxembed.httpx,'AsyncClient',lambda **kw:original(
        transport=httpx.MockTransport(handler),**kw))


async def test_persistent_bio_cache_survives_fresh_settings_without_renewing_source_time(settings,monkeypatch):
    settings.fxembed_profiles_enabled=True
    calls=[]
    intercept(monkeypatch,lambda r:(calls.append(r.url.path) or httpx.Response(200,json=PROFILE)))
    first=await fxembed.profile_hint(settings,URL)
    assert not first['cached']
    second=await fxembed.profile_hint(restart(settings),URL.lower())
    assert len(calls)==1 and second['cached']
    assert second['retrieved_at']==first['retrieved_at'] and second['response_sha256']==first['response_sha256']
    assert not second['first_party_publication_verified'] and second['review_required']
    assert second['published_email_candidates']==first['published_email_candidates']


async def test_expired_persisted_bio_fetches_again_and_preserves_original_on_prior_record(settings,monkeypatch):
    settings.fxembed_profiles_enabled=True
    calls=[]
    intercept(monkeypatch,lambda r:(calls.append(r.url.path) or httpx.Response(200,json=PROFILE)))
    first=await fxembed.profile_hint(settings,URL)
    original=first['retrieved_at']
    later=time.time()+901
    monkeypatch.setattr('time.time',lambda:later)
    second=await fxembed.profile_hint(restart(settings),URL)
    assert len(calls)==2 and not second['cached']
    assert second['retrieved_at']>original and first['retrieved_at']==original


@pytest.mark.parametrize('status,body', [(429,None),(200,{'code':429}),(403,None)])
async def test_provider_cooldown_survives_restart_for_another_handle(settings,monkeypatch,status,body):
    settings.fxembed_profiles_enabled=True
    calls=[]
    def response(r):
        calls.append(r.url.path)
        return httpx.Response(status,headers={'retry-after':'7200'},json=body) if body else httpx.Response(status,headers={'retry-after':'7200'})
    intercept(monkeypatch,response)
    await fxembed.profile_hint(settings,URL)
    other=await fxembed.profile_hint(restart(settings),'https://x.com/OtherFounder')
    assert len(calls)==1 and other['state']=='cooldown'
    assert other['retry_at']>time.time()+(7000 if status==429 or body else 3500)


async def test_expired_cooldown_allows_fresh_request_after_restart(settings,monkeypatch):
    settings.fxembed_profiles_enabled=True
    calls=[]
    intercept(monkeypatch,lambda r:(calls.append(r.url.path) or (
        httpx.Response(429,headers={'retry-after':'60'}) if len(calls)==1 else httpx.Response(200,json=PROFILE))))
    await fxembed.profile_hint(settings,URL)
    later=time.time()+61
    monkeypatch.setattr('time.time',lambda:later)
    result=await fxembed.profile_hint(restart(settings),URL)
    assert len(calls)==2 and result['state']=='public_mirror_hint' and not result['cached']


async def test_not_found_negative_cache_expires_without_holding_other_profiles(settings,monkeypatch):
    settings.fxembed_profiles_enabled=True
    calls=[]
    intercept(monkeypatch,lambda r:(calls.append(r.url.path) or httpx.Response(404)))
    first=await fxembed.profile_hint(settings,URL)
    second=await fxembed.profile_hint(restart(settings),URL)
    assert first['state']==second['state']=='not_found' and second['cached'] and len(calls)==1
    later=time.time()+61
    monkeypatch.setattr('time.time',lambda:later)
    third=await fxembed.profile_hint(restart(settings),URL)
    assert len(calls)==2 and not third['cached']
    assert not source_cache.load(settings,'fxembed_profiles','fxprofile:brightfounder')['hold_until']


async def test_corrupt_cache_fails_closed_without_contact_or_provider_request(settings,monkeypatch):
    settings.fxembed_profiles_enabled=True
    (settings.data_dir/'source-cache.sqlite3').write_bytes(b'invalid database')
    def forbidden(*args,**kwargs): pytest.fail('Unreadable cooldown state cannot be ignored')
    monkeypatch.setattr(fxembed.httpx,'AsyncClient',forbidden)
    result=await fxembed.profile_hint(settings,URL)
    assert result['state']=='cache_storage_unavailable' and not result.get('published_email_candidates')


def test_storage_keeps_highest_hold_caps_entries_and_preserves_value_timestamps(settings):
    now=time.time()
    for i in range(260):
        entry={'until':now+900,'value':{'state':'available','retrieved_at':now,'rows':[]}}
        source_cache.save(settings,'fxembed_profiles',str(i),entry,now+7200 if i==0 else 0,0)
    with sqlite3.connect(settings.data_dir/'source-cache.sqlite3') as con:
        assert con.execute('SELECT count(*) FROM source_cache').fetchone()[0]==256
    saved=source_cache.load(settings,'fxembed_profiles','259')
    assert saved['hold_until']==now+7200
    assert saved['entry']['value']['retrieved_at']==now
    assert not any(key in json.dumps(saved).lower() for key in ['authorization','cookie','password'])
