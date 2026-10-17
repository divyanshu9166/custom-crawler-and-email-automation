"""Discovery must stop at the consumer's retained-record quota, including profiles."""
import json

from outreach.discovery import prospect_candidates
from outreach.research import discover_leads


async def test_website_quota_stops_before_other_rows_or_queries(settings, monkeypatch):
    settings.discovery_platforms = 'linkedin.com,x.com'
    calls, captured = [], []
    async def search(s, query, *args, **kwargs):
        calls.append(query)
        assert len(calls) == 1
        return [{'url': 'https://bright-demo.com', 'title': 'Bright cleaning UK'},
                {'url': 'https://another-demo.com', 'title': 'Another cleaning UK'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    rows, report = await prospect_candidates(settings, 'cleaning UK', 'UK', 1, on_candidate=captured.append)
    assert len(rows) == len(captured) == 1
    assert len(calls) == 1 and report['stop_reason'] == 'requested_limit'
    assert report['executed_queries'] == calls


async def test_pipeline_counts_profile_records_in_limit_and_preserves_last_source(settings, db, monkeypatch):
    settings.platform_browser_enabled = True
    settings.platform_browser_public_fallback = False
    settings.discovery_query_delay_seconds = 0
    searches, resolved = [], []
    async def search(s, platform, query, limit):
        searches.append(platform)
        assert len(searches) == 1
        return [{'url': 'https://www.linkedin.com/company/'+name, 'title': name}
                for name in ('bright-one', 'bright-two', 'bright-three', 'never-read')]
    async def resolve(s, row, country, platforms):
        name = row['title']
        resolved.append(name)
        assert name != 'never-read'
        return {'source_url': row['url'], 'company': name, 'platform': 'linkedin.com',
                'state': 'website_candidate' if name != 'bright-three' else 'no_company_match',
                'website': 'https://'+name+'.com/' if name != 'bright-three' else ''}
    monkeypatch.setattr('outreach.platform_browser.browser_discover', search)
    monkeypatch.setattr('outreach.discovery.resolve_signal', resolve)
    await discover_leads(db, settings, 'cleaning UK', 'A', 'UK', 3)
    assert len(db.all('SELECT id FROM leads')) == 3
    assert len(db.all("SELECT id FROM leads WHERE lead_kind='profile'")) == 1
    assert len(db.all("SELECT id FROM jobs WHERE kind='research'")) == 3
    assert resolved == ['bright-one', 'bright-two', 'bright-three']
    events = db.all("SELECT detail FROM events WHERE kind='prospect_signal'")
    assert len(events) == 3 and all(json.loads(e['detail'])['lead_id'] for e in events)
    report = json.loads(db.one("SELECT detail FROM events WHERE kind='discovery'")['detail'])
    assert len(report['lead_ids']) == 3 and report['report']['stop_reason'] == 'requested_limit'
    assert not db.one("SELECT id FROM events WHERE kind='discovery_interrupted'")


async def test_callback_can_decline_a_candidate_without_consuming_its_quota(settings, monkeypatch):
    settings.discovery_platforms = ''
    async def search(*args, **kwargs):
        return [{'url': 'https://first-demo.com', 'title': 'First cleaning UK'},
                {'url': 'https://first-demo.com/contact', 'title': 'First cleaning UK contact'},
                {'url': 'https://second-demo.com', 'title': 'Second cleaning UK'},
                {'url': 'https://third-demo.com', 'title': 'Third cleaning UK'}]
    seen = []
    def accept(row):
        seen.append(row['url'])
        return len(seen) == 2
    monkeypatch.setattr('outreach.providers.discover', search)
    _, report = await prospect_candidates(settings, 'cleaning UK', 'UK', 1, on_candidate=accept)
    assert seen == ['https://first-demo.com/', 'https://second-demo.com/']
    assert report['stop_reason'] == 'requested_limit'
