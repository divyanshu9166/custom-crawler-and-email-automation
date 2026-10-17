import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.discovery import indexed_exclusion, official_root, prospect_candidates
from outreach.research import add_lead, discover_leads
from outreach.research_status import snapshot


@pytest.mark.parametrize('url,title,reason', [
    ('https://www.independent.co.uk/extras/indybest/skincare', 'Best skincare', 'editorial_or_marketplace_source'),
    ('https://www.flipkart.com/coffee', 'Buy Coffee Online India', 'editorial_or_marketplace_source'),
    ('https://coffeeroaster.com/', 'Find Best Coffee Roasters & Shops US', 'directory_or_listicle_result'),
    ('https://coffeeroaster.com/coffee-roaster', 'US Coffee Roasters | Coffee Roaster Directory', 'directory_or_listicle_result'),
    ('https://yellowpages.com/austin-tx/roofing', 'Best 30 Roofing Contractors in Austin, TX with Reviews', 'directory_or_listicle_result'),
    ('https://en.wikipedia.org/wiki/Coffee', 'Coffee - Wikipedia', 'editorial_or_marketplace_source'),
    ('https://brand.example.com/reviews', 'Customer reviews | Skincare Brand', ''),
    ('https://independent.co.uk.brand.example.com/', 'Independent skincare company', ''),
])
def test_live_search_noise_filters_preserve_official_review_pages(url, title, reason):
    assert indexed_exclusion({'url': url, 'title': title}) == reason


def test_editorial_domain_cannot_be_resolved_as_official_company():
    with pytest.raises(ValueError):
        official_root('https://independent.co.uk/skincare')


async def test_actual_result_classes_exclude_noise_before_domain_import(settings, monkeypatch):
    settings.discovery_platforms = ''
    async def search(*args, **kwargs):
        return [{'url': 'https://flipkart.com/coffee', 'title': 'Coffee shop'},
                {'url': 'https://coffeeroaster.com/', 'title': 'Find Best Coffee Roasters & Shops US'},
                {'url': 'https://brand.example.com/shop', 'title': 'Coffee Roaster Shop'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    rows, report = await prospect_candidates(settings, 'coffee roaster shop', 'US', 3)
    assert len(rows) == 1 and rows[0]['identity_status'] == 'indexed_candidate_needs_review'
    assert len(report['skipped']) == 2


async def test_generic_platform_pages_do_not_consume_profile_resolution_budget(settings, monkeypatch):
    settings.discovery_platforms = ''
    async def search(*args, **kwargs):
        return [{'url': 'https://x.com/', 'title': 'Coffee shop'},
                {'url': 'https://linkedin.com/in/some-person', 'title': 'Coffee shop founder'},
                {'url': 'https://brand.example.com/', 'title': 'Coffee shop'}]
    async def forbidden(*args, **kwargs):
        raise AssertionError('Generic or individual profile must not be resolved as a business')
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.resolve_signal', forbidden)
    rows, report = await prospect_candidates(settings, 'coffee shop', 'US', 3)
    assert len(rows) == 1 and not report['signals'] and len(report['skipped']) == 2


async def test_interrupted_run_context_and_streamed_results_are_preserved(db, settings, monkeypatch):
    settings.discovery_platforms = 'x.com'
    settings.discovery_query_delay_seconds = .1
    async def search(settings, query, *args, **kwargs):
        if query.startswith('site:'):
            raise asyncio.CancelledError()
        return [{'url': 'https://brand.example.com/', 'title': 'Coffee roaster'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    with pytest.raises(asyncio.CancelledError):
        await discover_leads(db, settings, 'coffee roaster', 'B', 'US', 2)
    result = snapshot(db)
    assert result['runs'][0]['state'] == 'interrupted'
    assert result['runs'][0]['campaign'] == 'B' and result['runs'][0]['country_hint'] == 'US'
    assert result['runs'][0]['lead_ids'] == [result['leads'][0]['id']]
    events = db.all("SELECT detail FROM events WHERE kind IN ('discovery_started','discovery_progress','discovery_interrupted')")
    assert len({json.loads(e['detail'])['run_id'] for e in events}) == 1
    assert result['counts']['qualified'] == 0


def test_readout_uses_current_fresh_exact_source_and_country_quotes(db, prepared):
    lid = prepared['lead_id']
    result = snapshot(db, lid)
    assert result['counts']['qualified'] == result['counts']['country_supported'] == 1
    assert result['counts']['supported_opportunities'] == 1
    db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    result = snapshot(db, lid)
    assert result['counts']['current_pages'] == 1
    assert result['counts']['country_supported'] == result['counts']['supported_opportunities'] == 0
    assert result['counts']['qualified'] == 0 and result['leads'][0]['review_required']
    # Historical successful captures do not count after a failed new crawl.
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps({'status': 'failed', 'errors': [{}]}), time.time()))
    result = snapshot(db, lid)
    assert result['counts']['current_pages'] == 0 and result['leads'][0]['crawl_issues'] == 1


def test_search_hint_and_unsupported_suggestions_never_become_reviewed_facts(db):
    lid = add_lead(db, 'Coffee candidate', 'https://brand.example.com/', 'B', 'https://brand.example.com/shop', 'US')
    db.execute('UPDATE leads SET findings=? WHERE id=?', (json.dumps([{'evidence_id': 99, 'quote': 'invented', 'suggestion': 'Double sales'}]), lid))
    result = snapshot(db)
    assert result['counts']['candidates'] == 1
    assert result['counts']['researched'] == result['counts']['qualified'] == result['counts']['country_supported'] == 0
    assert result['counts']['supported_opportunities'] == 0 and result['leads'][0]['review_required']


def test_crawl_diagnostics_show_denial_phase_without_inventing_remaining_coverage(db):
    lid = add_lead(db, 'Blocked candidate', 'https://brand.example.com/', 'A', 'https://brand.example.com/')
    report = {'status': 'failed', 'activity': {'stage': 'robots'},
              'errors': [{'stage': 'crawl', 'last_stage': 'robots', 'http_status': 403, 'reason': 'HTTPStatusError'}]}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(report), time.time()))
    before = db.all('SELECT * FROM leads')
    row = snapshot(db, lid)['leads'][0]
    assert row['crawl_http_status'] == 403 and row['crawl_last_stage'] == 'robots'
    assert row['remaining_urls'] is None and row['first_page_seconds'] is None
    assert row['review_required'] and not row['http_document_reuses']
    assert db.all('SELECT * FROM leads') == before


def test_partial_crawl_exposes_measured_timing_and_reuses_without_qualification(db):
    lid = add_lead(db, 'Partial candidate', 'https://brand.example.com/', 'A', 'https://brand.example.com/')
    report = {'status': 'interrupted', 'first_page_seconds': 10.5, 'activity': {'stage': 'render'},
              'pages': [{'document_reused': True}, {'document_reused': False}], 'retried_requests': [{}]}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(report), time.time()))
    row = snapshot(db, lid)['leads'][0]
    assert row['first_page_seconds'] == 10.5 and row['http_document_reuses'] == row['retried_requests'] == 1
    assert row['crawl_last_stage'] == 'render' and row['crawl_status'] == 'interrupted'
    assert row['crawl_http_status'] is None and row['review_required']


def test_interrupted_pages_offer_read_only_preview_without_faking_completion(db):
    lid = add_lead(db, 'Coffee candidate', 'https://brand.example.com/', 'B', 'https://brand.example.com/', 'US')
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, '{"status":"interrupted"}', time.time()-1))
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lid, 'https://brand.example.com/', 'Coffee', 'Our roasted coffee. Add to cart for delivery.', 'hash', time.time()))
    before = db.all('SELECT * FROM leads')
    result = snapshot(db, lid)
    record = result['leads'][0]
    assert record['preview_generated'] and record['crawl_status'] == 'interrupted'
    assert record['supported_opportunities'] == 1 and not record['observations'][0]['reviewed']
    assert record['opportunities'][0]['review_required'] and record['unknowns']
    assert result['counts']['qualified'] == 0 and db.all('SELECT * FROM leads') == before


def test_endpoint_authenticated_scoped_and_read_only(settings, db, prepared):
    app = create_app(settings)
    before = db.all('SELECT * FROM leads')
    with TestClient(app) as client:
        assert client.get('/api/research-status').status_code == 401
        response = client.get('/api/research-status', headers={'Authorization': 'Bearer '+settings.api_token})
        assert response.status_code == 200 and response.json()['counts']['candidates'] == 1
        assert client.get('/api/research-status?lead_id=999', headers={'Authorization': 'Bearer '+settings.api_token}).status_code == 400
    assert db.all('SELECT * FROM leads') == before


def test_concurrent_same_query_runs_not_merged_by_query(db):
    context = {'query': 'Same query', 'campaign': 'A', 'country_hint': 'UK'}
    db.event('discovery_started', {**context, 'run_id': 'one'})
    db.event('discovery_started', {**context, 'run_id': 'two'})
    db.event('discovery', {**context, 'run_id': 'one', 'lead_ids': [], 'report': {}})
    runs = snapshot(db)['runs']
    assert len(runs) == 2 and runs[0]['state'] == 'finished' and runs[1]['state'] == 'started'
