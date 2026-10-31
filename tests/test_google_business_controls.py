"""Google source controls cover real intake/queue boundaries without live Google calls."""
import json
import asyncio
import time
from urllib.robotparser import RobotFileParser

import pytest
from fastapi.testclient import TestClient

from outreach import google_business as maps
from outreach.app import create_app
from outreach.web import PublicWeb
from outreach.preferences import Preferences
from outreach.config import Settings
from outreach.research import add_lead, discover_leads, research_lead
from outreach.profiles import add_profile_lead

URL = 'https://www.google.com/maps/place/Bright+Plumbing'
HTML = ('<main><h1>Bright Plumbing</h1><button data-item-id="category">Plumber</button>'
        '<button data-item-id="address">10 Fixture Road, Bristol, UK</button>{}</main>')


@pytest.mark.parametrize('href', ['mailto:hello%40bright-demo.com', 'MAILTO:hello@bright-demo.com',
    'mailto:hello%40bright-demo.com?subject=Quote'])
def test_explicit_listing_email_links_decode_and_ignore_query(href):
    result = maps.parse_listing(URL, HTML.format(f'<a data-item-id="email" href="{href}">Email</a>'))
    assert result['published_emails'] == ['hello@bright-demo.com']
    assert 'Business email: hello@bright-demo.com' in result['text']


@pytest.mark.parametrize('failure', ['start', 'render', 'close'])
async def test_browser_failure_preserves_valid_current_public_listing(settings, monkeypatch, failure):
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    async def allowed(*args):
        return robots, 0, URL
    async def get(*args):
        return URL, HTML.format(''), 200
    class BrokenRenderer:
        def __init__(self, web):
            pass
        async def start(self):
            if failure == 'start':
                raise RuntimeError('browser launch failed with private runtime details')
        async def render(self, *args, **kwargs):
            if failure == 'render':
                raise RuntimeError('render failed with private runtime details')
            return {'url': URL, 'html': HTML.format('')}
        async def close(self):
            if failure == 'close':
                raise RuntimeError('cleanup failed with private runtime details')
    monkeypatch.setattr(PublicWeb, 'robots', allowed)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr('outreach.browser.RenderSession', BrokenRenderer)
    result = await maps.snapshot(settings, URL)
    assert result['state'] == 'captured' and result['title'] == 'Bright Plumbing'
    assert result['render_issues'] == [{'reason': 'browser_cleanup_failed' if failure == 'close' else 'browser_unavailable', 'error_type': 'RuntimeError'}]
    assert result['partial'] is True
    assert 'private runtime details' not in json.dumps(result)


def client_for(settings):
    return TestClient(create_app(settings), base_url=settings.public_url,
                      headers={'Authorization': 'Bearer '+settings.api_token})


def test_google_control_is_strict_authenticated_and_persists_across_restart(settings, db):
    original = settings.model_dump()
    client = client_for(settings)
    assert client.get('/api/settings').json()['google_business_enabled'] is True
    anonymous = TestClient(create_app(settings))
    assert anonymous.put('/api/settings/research', json={'google_business_enabled': False}).status_code == 401
    for invalid in ('false', 0, 1):
        assert client.put('/api/settings/research', json={'google_business_enabled': invalid}).status_code == 422
    assert client.put('/api/settings/research', json={'google_business_enabled': False}).json()['google_business_enabled'] is False
    assert client.get('/api/status').json()['google_business_enabled'] is False
    assert next(p for p in client.get('/api/source-status').json()['providers'] if p['provider'] == 'google_maps')['configured'] is False
    restarted = Settings(_env_file=None, **original)
    assert client_for(restarted).get('/api/settings').json()['google_business_enabled'] is False
    assert not maps.enabled(restarted)
    assert db.get('paused') == 'true'


def test_off_cancels_only_queued_google_intake_keeps_history_and_can_be_enabled(settings, db):
    client = client_for(settings)
    request = {'query': 'plumbers Bristol UK', 'campaign': 'A', 'country_hint': 'UK',
               'limit': 3, 'discovery_source': 'google_maps'}
    gid = maps.campaign(db)
    lid = add_profile_lead(db, 'Bright Plumbing', URL, 'A', 'UK', campaign_id=gid)
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lid, URL, 'Bright Plumbing', 'UK plumbing services', 'fixture', time.time()))
    saved = db.all('SELECT * FROM evidence')
    maps_job = client.post('/api/discover', json=request).json()['job_id']
    profile_job = db.enqueue('research', {'lead_id': lid})
    website = add_lead(db, 'Other', 'https://other-demo.com/', 'A', 'https://other-demo.com/')
    other = db.enqueue('research', {'lead_id': website})
    assert client.post('/api/schedules', json={**request, 'interval_hours': 24}).status_code == 200
    assert client.put('/api/settings/research', json={'google_business_enabled': False}).status_code == 200
    for jid in (maps_job, profile_job):
        assert db.one('SELECT state FROM jobs WHERE id=?', (jid,))['state'] == 'cancelled'
    assert db.one('SELECT state FROM jobs WHERE id=?', (other,))['state'] == 'pending'
    assert db.all('SELECT * FROM evidence') == saved
    assert client.get('/api/schedules').json()[0]['source_disabled'] is True
    assert db.one('SELECT enabled FROM schedules')['enabled'] == 1
    for path, body in (('/api/discover', request), ('/api/schedules', {**request, 'interval_hours': 24}),
        ('/api/profile-leads', {'company': 'Bright Plumbing', 'profile_url': URL, 'campaign': 'A', 'country_hint': 'UK'})):
        response = client.post(path, json=body)
        assert response.status_code == 400 and 'OFF' in response.json()['detail']
    assert client.post(f'/api/leads/{lid}/research').status_code == 400
    assert client.put('/api/settings/research', json={'google_business_enabled': True}).status_code == 200
    assert client.get('/api/schedules').json()[0]['source_disabled'] is False
    assert client.post('/api/discover', json=request).status_code == 200
    assert not db.one('SELECT 1 FROM contacts') and not db.one('SELECT 1 FROM send_attempts')


async def test_disabled_source_never_starts_network_or_changes_profile_evidence(settings, db, monkeypatch):
    lid = add_profile_lead(db, 'Bright Plumbing', URL, 'A', 'UK')
    Preferences(settings).update_research(db, {'google_business_enabled': False})
    async def forbidden(*args, **kwargs):
        pytest.fail('Disabled Google source attempted network access')
    monkeypatch.setattr(PublicWeb, 'robots', forbidden)
    monkeypatch.setattr('outreach.providers.discover', forbidden)
    for call in (maps.page(settings, URL), maps.snapshot(settings, URL),
        maps.prospect_candidates(settings, 'UK plumbers', 'UK', 3),
        discover_leads(db, settings, 'UK plumbers', 'A', 'UK', 3, discovery_source='google_maps'),
        research_lead(db, settings, lid)):
        with pytest.raises(maps.GoogleBusinessDisabled):
            await call
    assert not db.one('SELECT 1 FROM crawls')
    assert db.one('SELECT website_status FROM leads')['website_status'] == 'not_checked'


async def test_source_off_during_robots_wait_is_shared_with_settings_copies(settings, db, monkeypatch):
    preferences = Preferences(settings)
    copied = settings.model_copy(update={'search_language': 'en-US'})
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    async def robots_then_off(*args):
        preferences.update_research(db, {'google_business_enabled': False})
        return robots, 0, URL
    async def forbidden(*args):
        pytest.fail('Source switch changed before listing request')
    monkeypatch.setattr(PublicWeb, 'robots', robots_then_off)
    monkeypatch.setattr(PublicWeb, 'get', forbidden)
    with pytest.raises(maps.GoogleBusinessDisabled):
        await maps.page(copied, URL)
    assert not maps.enabled(copied)
    preferences.update_research(db, {'google_business_enabled': True})
    assert maps.enabled(copied)


async def test_source_off_while_waiting_for_browser_lock_never_opens_browser(settings, db, monkeypatch):
    preferences = Preferences(settings)
    ready = asyncio.Event()
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    async def allowed(*args):
        return robots, 0, URL
    async def get(*args):
        ready.set()
        return URL, HTML.format(''), 200
    monkeypatch.setattr(PublicWeb, 'robots', allowed)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr('outreach.browser.RenderSession', lambda *args: pytest.fail('Disabled source launched a browser'))
    async with settings._platform_browser_lock:
        task = asyncio.create_task(maps.page(settings.model_copy(), URL))
        await asyncio.wait_for(ready.wait(), 2)
        preferences.update_research(db, {'google_business_enabled': False})
    with pytest.raises(maps.GoogleBusinessDisabled):
        await task


async def test_rendered_access_denial_is_never_replaced_with_static_success(settings, monkeypatch):
    import httpx
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    async def allowed(*args):
        return robots, 0, URL
    async def get(*args):
        return URL, HTML.format(''), 200
    class Denied:
        def __init__(self, web):
            pass
        async def start(self):
            pass
        async def render(self, *args, **kwargs):
            raise httpx.HTTPStatusError('denied', request=httpx.Request('GET', URL), response=httpx.Response(403))
        async def close(self):
            pass
    monkeypatch.setattr(PublicWeb, 'robots', allowed)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr('outreach.browser.RenderSession', Denied)
    result = await maps.snapshot(settings, URL)
    assert result['state'] == 'http_403' and 'text' not in result


async def test_disabled_mixed_discovery_skips_google_queries_and_rows(settings, db, monkeypatch):
    from outreach.discovery import prospect_candidates
    settings.discovery_platforms = 'google.com'
    settings.discovery_query_delay_seconds = .1
    Preferences(settings).update_research(db, {'google_business_enabled': False})
    searches = []
    async def search(s, query, *args, **kwargs):
        searches.append(query)
        return [{'url': URL, 'title': 'UK plumbing services'},
                {'url': 'https://bright-demo.com/', 'title': 'UK plumbing services'}]
    async def forbidden(*args, **kwargs):
        pytest.fail('Disabled Google result was resolved')
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.resolve_signal', forbidden)
    rows, report = await prospect_candidates(settings, 'UK plumbing services', 'UK', 3)
    assert [row['url'] for row in rows] == ['https://bright-demo.com/']
    assert len(searches) == 1 and 'site:google.com' not in searches[0]
    assert report['skipped'][0]['reason'] == 'google_business_disabled'


async def test_worker_cancels_google_job_when_source_disabled_after_enqueue(settings, db):
    from outreach.worker import execute_job
    settings.google_business_enabled = False
    jid = db.enqueue('discover', {'query': 'UK plumbers', 'campaign': 'A', 'country_hint': 'UK',
                                 'limit': 3, 'discovery_source': 'google_maps'})
    await execute_job(db, settings, db.claim({'discover'}))
    assert db.one('SELECT state FROM jobs WHERE id=?', (jid,))['state'] == 'cancelled'
    assert not db.one("SELECT 1 FROM events WHERE kind='job_failed'")


async def test_scheduler_waits_for_google_switch_without_disabling_other_sources(settings, db, monkeypatch):
    from outreach import worker
    settings.worker_enabled = True
    settings.google_business_enabled = False
    stop = asyncio.Event()
    due = time.time() - 10
    for source in ('google_maps', 'mixed'):
        db.execute('INSERT INTO schedules(query,campaign,country_hint,result_limit,interval_hours,next_run,discovery_source) VALUES(?,?,?,?,?,?,?)',
                   ('UK plumbers', 'A', 'UK', 3, 24, due, source))
    called = []
    async def discover(*args, **kwargs):
        called.append(kwargs)
        stop.set()
    monkeypatch.setattr(worker, 'discover_leads', discover)
    await asyncio.wait_for(worker.job_loop(db, settings, stop, {'discover'}, schedules=True), 3)
    assert len(called) == 1 and 'discovery_source' not in called[0]
    assert len(db.all('SELECT * FROM jobs')) == 1
    assert db.one("SELECT enabled,next_run FROM schedules WHERE discovery_source='google_maps'") == {'enabled': 1, 'next_run': due}
