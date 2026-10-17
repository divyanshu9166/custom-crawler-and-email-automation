"""Unattended progress is bounded, source-preserving and independent of sending."""
import asyncio
import json
import time

import httpx
import pytest

from outreach.crawl_resources import AdaptiveConcurrency, container_limits
from outreach.crawl_scheduler import reschedule
from outreach.research import add_lead, research_lead
from outreach.web import PublicWeb
from outreach.worker import execute_job


def setup(settings):
    settings.sending_enabled = False
    settings.browser_enabled = False
    settings.crawl_render_mode = 'never'
    settings.crawl_delay_seconds = .001
    settings.crawl_max_sitemaps = 0
    settings.crawl_max_pages = 2


async def site(self, url, expected_domain=None):
    if url.endswith('/robots.txt'):
        return url, 'User-agent: *\nAllow: /', 200
    text = '<p>London company</p>'
    if url.endswith('/'):
        text += '<a href="/contact">Contact</a><a href="/services">Services</a><a href="/team">Team</a>'
    if url.endswith('/contact'):
        text += '<p>hello@bright-demo.com</p>'
    return url, text, 200


async def drive(db, settings, jid):
    db.execute('UPDATE jobs SET due_at=0 WHERE id=?', (jid,))
    job = db.claim({'research'})
    assert job and job['id'] == jid
    await execute_job(db, settings, job)


async def test_partial_crawl_automatically_continues_same_job_and_source_ids(db, settings, monkeypatch):
    setup(settings)
    monkeypatch.setattr(PublicWeb, 'get', site)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    await drive(db, settings, jid)
    first = db.all('SELECT id,url FROM evidence')
    row = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
    assert row['state'] == 'pending' and json.loads(row['payload'])['auto_pass'] == 1
    assert len(first) == 2
    await drive(db, settings, jid)
    assert db.one('SELECT state FROM jobs WHERE id=?', (jid,))['state'] == 'done'
    assert db.one('SELECT COUNT(*) n FROM evidence')['n'] == 4
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1
    for entry in first:
        assert db.one('SELECT id FROM evidence WHERE url=?', (entry['url'],))['id'] == entry['id']
    report = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert report['status'] == 'complete' and report['automation']['state'] == 'finished'
    assert not db.all('SELECT * FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')


@pytest.mark.parametrize('limit', ['pages', 'passes'])
async def test_auto_cycle_stops_at_total_budget(db, settings, monkeypatch, limit):
    setup(settings)
    settings.crawl_auto_max_pages = 3 if limit == 'pages' else 180
    settings.crawl_auto_max_passes = 2
    async def more(self, url, expected_domain=None):
        final, html, code = await site(self, url, expected_domain)
        if limit == 'passes' and url.endswith('/'):
            html += '<a href="/news/launch">Launch</a>'
        return final, html, code
    monkeypatch.setattr(PublicWeb, 'get', more)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    await drive(db, settings, jid)
    await drive(db, settings, jid)
    row = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
    assert row['state'] == 'done'
    report = json.loads(db.one('SELECT report FROM crawls')['report'])
    if limit == 'pages':
        assert report['attempted'] == 3 and report['status'] == 'partial'
        assert report['automation']['state'] == 'budget_exhausted'
    else:
        assert report['attempted'] == 4 and report['remaining'] > 0
        assert report['automation']['state'] == 'budget_exhausted'


def test_due_job_fairness_prevents_old_continuation_starving_other_prospects(db):
    first = db.enqueue('research', {'lead_id': 1, 'continuation': True})
    second = db.enqueue('research', {'lead_id': 2})
    db.execute('UPDATE jobs SET due_at=? WHERE id=?', (time.time()-10, first))
    db.execute('UPDATE jobs SET due_at=? WHERE id=?', (time.time()-100, second))
    assert db.claim({'research'})['id'] == second


async def test_retry_job_waits_and_recovers_contact_without_restart(db, settings, monkeypatch):
    setup(settings)
    settings.crawl_max_pages = 10
    broken = True
    async def flaky(self, url, expected_domain=None):
        if url.endswith('/contact') and broken:
            raise httpx.HTTPStatusError('busy', request=httpx.Request('GET', url),
                response=httpx.Response(429, headers={'Retry-After': '120'}))
        return await site(self, url, expected_domain)
    monkeypatch.setattr(PublicWeb, 'get', flaky)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    started = time.time()
    await drive(db, settings, jid)
    row = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
    assert row['state'] == 'pending' and row['due_at'] >= started+120
    assert db.claim({'research'}) is None
    report = json.loads(db.one('SELECT report FROM crawls')['report'])
    report['checkpoint']['domain_not_before'] = 0
    for retry in report['checkpoint']['retry_urls']:
        retry['not_before'] = 0
    db.execute('UPDATE crawls SET report=?', (json.dumps(report),))
    broken = False
    await drive(db, settings, jid)
    assert db.one('SELECT COUNT(*) n FROM contacts')['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1
    assert not db.one('SELECT 1 FROM messages')


async def test_review_after_scheduling_stops_auto_job_before_network(db, settings, monkeypatch):
    setup(settings)
    monkeypatch.setattr(PublicWeb, 'get', site)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    await drive(db, settings, jid)
    db.execute("UPDATE leads SET status='qualified' WHERE id=?", (lid,))
    before = db.all('SELECT * FROM evidence')
    async def forbidden(*_, **__):
        pytest.fail('A reviewed prospect must not be researched automatically')
    monkeypatch.setattr(PublicWeb, 'get', forbidden)
    await drive(db, settings, jid)
    assert db.all('SELECT * FROM evidence') == before
    assert db.one('SELECT status FROM leads')['status'] == 'qualified'
    assert json.loads(db.one('SELECT report FROM crawls')['report'])['automation']['state'] == 'stopped_after_review'


async def test_superseded_checkpoint_job_does_not_recrawl(db, settings, monkeypatch):
    setup(settings)
    monkeypatch.setattr(PublicWeb, 'get', site)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    await drive(db, settings, jid)
    await research_lead(db, settings, lid)  # Operator fresh research supersedes queued cycle.
    before = db.all('SELECT * FROM evidence')
    async def forbidden(*_, **__):
        pytest.fail('Old queued cycle must not affect a newer crawl')
    monkeypatch.setattr(PublicWeb, 'get', forbidden)
    await drive(db, settings, jid)
    assert db.all('SELECT * FROM evidence') == before
    assert 'Superseded' in db.one('SELECT error FROM jobs WHERE id=?', (jid,))['error']


async def test_review_race_is_rechecked_inside_research_transaction(db, settings, monkeypatch):
    from outreach import research
    setup(settings)
    monkeypatch.setattr(PublicWeb, 'get', site)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    await research_lead(db, settings, lid)
    original = research.research_checkpoint
    before = db.all('SELECT * FROM evidence')
    def raced(database, lead_id):
        row = original(database, lead_id)
        database.execute("UPDATE leads SET status='qualified' WHERE id=?", (lead_id,))
        return row
    monkeypatch.setattr(research, 'research_checkpoint', raced)
    with pytest.raises(ValueError, match='business review'):
        await research_lead(db, settings, lid, continuation=True, protect_review=True)
    assert db.one('SELECT status FROM leads')['status'] == 'qualified'
    assert db.all('SELECT * FROM evidence') == before


async def test_interrupted_worker_restart_resumes_saved_checkpoint(db, settings, monkeypatch):
    setup(settings)
    interrupted = True
    async def cancel(self, url, expected_domain=None):
        if url.endswith('/contact') and interrupted:
            raise asyncio.CancelledError()
        return await site(self, url, expected_domain)
    monkeypatch.setattr(PublicWeb, 'get', cancel)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    with pytest.raises(asyncio.CancelledError):
        await drive(db, settings, jid)
    first = db.one('SELECT * FROM evidence')
    db.recover()
    interrupted = False
    await drive(db, settings, jid)
    assert db.one('SELECT id FROM evidence WHERE url=?', (first['url'],))['id'] == first['id']
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1


async def test_auto_off_and_competing_manual_request_prevent_rescheduling(db, settings, monkeypatch):
    setup(settings)
    monkeypatch.setattr(PublicWeb, 'get', site)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    db.enqueue('research', {'lead_id': lid})
    job = db.claim({'research'})
    await research_lead(db, settings, lid)
    settings.crawl_auto_continue = False
    assert not reschedule(db, settings, job)
    settings.crawl_auto_continue = True
    db.enqueue('research', {'lead_id': lid, 'continuation': True})
    assert not reschedule(db, settings, job)


async def test_contact_search_is_deferred_until_cycle_end_and_not_repeated(db, settings, monkeypatch):
    setup(settings)
    settings.auto_contact_research = True
    async def no_email(self, url, expected_domain=None):
        final, html, code = await site(self, url, expected_domain)
        return final, html.replace('hello@bright-demo.com', 'Phone inquiries'), code
    monkeypatch.setattr(PublicWeb, 'get', no_email)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    jid = db.enqueue('research', {'lead_id': lid})
    await drive(db, settings, jid)
    assert not db.one("SELECT 1 FROM jobs WHERE kind='contact_research'")
    await drive(db, settings, jid)
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='contact_research'")['n'] == 1


async def test_sitemap_retry_recovers_links_without_refetching_home(settings, monkeypatch):
    setup(settings)
    settings.crawl_max_sitemaps = 2
    broken = True
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if url.endswith('/sitemap.xml'):
            if broken:
                raise httpx.ReadTimeout('slow map')
            return url, '<urlset><url><loc>https://bright-demo.com/contact</loc></url></urlset>', 200
        return url, '<p>Company hello@bright-demo.com</p>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings)
    await crawler.crawl('https://bright-demo.com/')
    report = json.loads(json.dumps(crawler.report))
    assert report['checkpoint']['retry_sitemaps']
    report['checkpoint']['retry_sitemaps'][0]['not_before'] = 0
    calls.clear()
    broken = False
    resumed = PublicWeb(settings)
    await resumed.crawl('https://bright-demo.com/', continuation=report)
    assert 'https://bright-demo.com/' not in calls
    assert resumed.report['status'] == 'complete'
    assert resumed.report['skipped'][0]['resolved_at']


def test_adaptive_admission_scales_then_pauses_without_killing_active_jobs(db, settings, monkeypatch):
    settings.crawl_concurrency = 3
    clock = [0.0]
    metrics = {'cpu_percent': 20, 'memory_percent': 40, 'available_mb': 4000}
    monkeypatch.setattr('outreach.crawl_resources.time.monotonic', lambda: clock[0])
    gate = AdaptiveConcurrency(settings, db, probe=lambda _: metrics.copy())
    assert gate.acquire() and not gate.acquire()
    clock[0] = 6
    assert gate.acquire() and gate.desired == 2
    metrics.update(cpu_percent=99)
    clock[0] = 12
    assert not gate.acquire() and gate.active == 2 and gate.paused
    gate.release()
    gate.release()
    metrics.update(cpu_percent=20)
    clock[0] = 18
    assert gate.acquire()
    status = json.loads(db.get('crawler_runtime'))
    assert status['active'] == 1 and status['maximum'] == 3


@pytest.mark.parametrize('metrics', [{}, {'cpu_percent': float('nan'), 'memory_percent': 30, 'available_mb': 2000}])
def test_missing_or_invalid_metrics_fall_back_to_serial(db, settings, metrics):
    settings.crawl_concurrency = 3
    gate = AdaptiveConcurrency(settings, db, probe=lambda _: metrics)
    assert gate.acquire() and not gate.acquire()
    assert gate.reason == 'metrics_unavailable_serial'
    assert json.loads(db.get('crawler_runtime'))['desired'] == 1


def test_cgroup_v2_limits_and_unlimited_values(tmp_path):
    (tmp_path/'memory.max').write_text('4294967296')
    (tmp_path/'memory.current').write_text('2147483648')
    (tmp_path/'cpu.max').write_text('150000 100000')
    (tmp_path/'cpu.stat').write_text('usage_usec 2500000\n')
    assert container_limits(tmp_path) == {'memory_limit': 4294967296, 'memory_used': 2147483648,
                                         'cpu_cores': 1.5, 'cpu_used_seconds': 2.5}
    (tmp_path/'memory.max').write_text('max')
    (tmp_path/'cpu.max').write_text('max 100000')
    result = container_limits(tmp_path)
    assert 'memory_limit' not in result and 'cpu_cores' not in result


async def test_resource_monitor_keeps_sampling_during_active_job(db, settings, monkeypatch):
    from outreach.worker import monitor_resources
    clock = [0.0]
    metrics = {'cpu_percent': 20, 'memory_percent': 40, 'available_mb': 4000}
    gate = AdaptiveConcurrency(settings, db, probe=lambda _: metrics.copy(), clock=lambda: clock[0])
    assert gate.acquire()
    stop = asyncio.Event()
    task = asyncio.create_task(monitor_resources(gate, stop, interval=.01))
    try:
        await asyncio.sleep(.02)
        clock[0] = 6
        metrics['cpu_percent'] = 99
        await asyncio.sleep(.03)
        assert gate.paused and gate.active == 1
        assert json.loads(db.get('crawler_runtime'))['paused_admission']
    finally:
        stop.set()
        await task


async def test_adaptive_pacing_never_accelerates_on_error_and_respects_floor(settings, monkeypatch):
    settings.crawl_http_retries = 0
    settings.crawl_delay_seconds = 2
    settings.crawl_adaptive_max_delay_seconds = 10
    code, latency = 200, 8
    async def resource(self, url, expected_domain=None):
        return {'url': url, 'status': code, 'body': b'<p>Company</p>', 'headers': {'content-type': 'text/html'},
                'encoding': 'utf-8', 'latency_seconds': latency}
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    crawler = PublicWeb(settings)
    await crawler.get('https://bright-demo.com/')
    assert crawler.adaptive_delays['bright-demo.com'] == 5
    code, latency = 503, .1
    with pytest.raises(httpx.HTTPStatusError):
        await crawler.get('https://bright-demo.com/contact')
    assert crawler.adaptive_delays['bright-demo.com'] == 5
    code, latency = 200, .1
    await crawler.get('https://bright-demo.com/contact')
    assert crawler.adaptive_delays['bright-demo.com'] == 3.5
    settings.crawl_adaptive_pacing = False
    await PublicWeb(settings).get('https://bright-demo.com/')
