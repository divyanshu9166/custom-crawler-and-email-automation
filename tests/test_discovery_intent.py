"""Live search noise must not become a company just on a generic query word."""
import pytest

from outreach.discovery import relaxed_profile_query, query_relevant, prospect_candidates, indexed_market_exclusion


@pytest.mark.parametrize('title,snippet,excluded', [
    ("United Kingdom's 13 Most Impressive & Successful Founders in the ...", '', True),
    ('UK cosmetics founders', 'This list showcases the top United Kingdom based Founder operating in the Cosmetics space.', True),
    ('12 Leading Companies in Skincare', '', True),
    ('Founders in cosmetics', 'Our list features skincare brands across the country.', True),
    ('2026 Founder Letter | Bright Skincare', 'Our founder describes current company progress.', False),
    ('13 Most Popular Skincare Products | Bright Skincare', 'Shop our products.', False),
    ('Bright Skincare | Founder and Team', 'Meet our founder and current team.', False),
    ('Bright Skincare | Ingredients', 'Our list of ingredients includes natural oils.', False),
])
def test_structural_founder_listicles_do_not_become_official_company_candidates(title, snippet, excluded):
    from outreach.discovery import indexed_exclusion
    reason = indexed_exclusion({'url': 'https://candidate-demo.com/', 'title': title, 'snippet': snippet})
    assert bool(reason) is excluded


@pytest.mark.parametrize('title,expected', [
    ('Team | IF_DO — Architecture & Design', 'IF_DO'),
    ('Our Team - Studio Architecture', 'Studio Architecture'),
    ('Our Story - ELEMIS', 'ELEMIS'),
    ('News | Bright Demo', 'Bright Demo'),
    ('Sarah Castle - Co-Founding Director | LinkedIn', 'Sarah Castle'),
    ('Home | Business services | Bright Demo', 'Bright Demo'),
])
def test_generic_page_label_is_not_used_as_company_name_hint(title, expected):
    from outreach.discovery import company_title
    assert company_title(title) == expected


async def test_listicle_is_skipped_before_any_contact_research_and_real_brand_remains_candidate(settings, monkeypatch):
    settings.discovery_platforms = ''
    async def search(*args, **kwargs):
        return [{'url': 'https://listing-demo.com/founders', 'title': '13 Most Successful Founders',
                 'snippet': 'This list showcases skincare brands in UK.'},
                {'url': 'https://brand-demo.com/', 'title': 'Bright Skincare UK', 'snippet': 'Our skincare brand.'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    rows, report = await prospect_candidates(settings, 'skincare UK', 'UK', 2)
    assert [r['url'] for r in rows] == ['https://brand-demo.com/']
    assert report['skipped'][0]['reason'] == 'directory_or_listicle_result'


@pytest.mark.parametrize('query,market,expected', [
    ('site:x.com "skincare" "founder" "UK"', 'UK', 'site:x.com skincare founder'),
    ('site:linkedin.com/in/ skincare United States (founder OR owner OR director OR marketing)',
     'US', 'site:linkedin.com/in/ skincare (founder OR owner OR director OR marketing)'),
    ('site:linkedin.com/company/ dental United Kingdom', 'UK', 'site:linkedin.com/company/ dental'),
    ('site:x.com US Foods founder United States', 'US', 'site:x.com US Foods founder'),
    ('site:x.com United Kingdom', 'UK', ''),
    ('site:x.com skincare -site:example.com UK', 'UK', ''),
    ('site:example.com skincare UK', 'UK', ''),
    ('site:x.com skincare', 'UK', ''),
])
def test_bounded_profile_retry_preserves_subject_and_profile_path(query, market, expected):
    assert relaxed_profile_query(query, market) == expected


async def test_empty_platform_query_retries_once_and_foreign_results_still_excluded(settings, monkeypatch):
    settings.discovery_platforms = 'x.com'
    settings.discovery_query_delay_seconds = .001
    calls = []
    async def search(s, q, *args, **kwargs):
        calls.append(q)
        return [{'url': 'https://x.com/skin_demo', 'title': 'Skincare Founder India'}] if q == 'site:x.com skincare' else []
    monkeypatch.setattr('outreach.providers.discover', search)
    rows, report = await prospect_candidates(settings, 'skincare United Kingdom', 'UK', 2)
    assert calls == ['skincare United Kingdom', 'site:x.com skincare United Kingdom', 'site:x.com skincare']
    assert not rows and not report['signals']
    assert report['skipped'][0]['reason'] == 'indexed_market_conflict'
    assert report['relaxed_queries'] == {'site:x.com skincare': 'site:x.com skincare United Kingdom'}
    assert report['engine_reports'][-1]['search_market_constraint_relaxed'] is True


async def test_no_recursive_platform_retry_or_retry_after_success(settings, monkeypatch):
    settings.discovery_platforms = 'x.com'
    settings.discovery_query_delay_seconds = .001
    calls = []
    async def search(s, q, *args, **kwargs):
        calls.append(q)
        return []
    monkeypatch.setattr('outreach.providers.discover', search)
    await prospect_candidates(settings, 'skincare United Kingdom', 'UK', 2)
    assert calls.count('site:x.com skincare') == 1 and len(calls) == 3
    calls.clear()
    async def successful(s, q, *args, **kwargs):
        calls.append(q)
        return [{'url': 'https://x.com/skin_demo', 'title': 'Skincare UK'}] if q.startswith('site:') else []
    async def unresolved(*args, **kwargs):
        return {'state': 'held', 'website': '', 'source_url': 'https://x.com/skin_demo'}
    monkeypatch.setattr('outreach.providers.discover', successful)
    monkeypatch.setattr('outreach.discovery.resolve_signal', unresolved)
    await prospect_candidates(settings, 'skincare United Kingdom', 'UK', 2)
    assert 'site:x.com skincare' not in calls and len(calls) == 2



@pytest.mark.parametrize(('query', 'title', 'snippet', 'expected'), [
    ('local roofing company Denver Colorado US contact', 'Current Local Time in New Delhi, Delhi, India', '', False),
    ('local roofing company Denver Colorado US contact', 'Local, Connaught Place, New Delhi | Zomato', '', False),
    ('specialty coffee roaster US online shop contact', 'Specialty vs. Speciality - Writing Explained', '', False),
    ('independent skincare brand UK online shop contact', 'The Online Shop | UK clothing', '', False),
    ('local roofing company Denver Colorado US contact', 'Denver roofers | Request a quote', '', True),
    ('specialty coffee roaster US online shop contact', 'US Roast', 'Freshly roasted coffee beans delivered', True),
    ('independent dental clinic Manchester UK contact', 'City Centre Dentist', 'Private dentistry in Manchester', True),
    ('independent wedding florist Bristol UK contact', 'Bouquets For Days', 'Wedding flowers in Bristol', True),
    ('independent skincare brand UK online shop contact', 'Organic beauty products', 'Shop natural skin care', True),
    ('site:linkedin.com/company/ florist Bristol UK', 'Bristol Local Companies', 'Business directory', False),
    ('site:linkedin.com/company/ florist Bristol UK', 'Bristol Floral Design | LinkedIn', '', True),
    ('"Tanuki" UK contact', 'Tanuki Coffee', '', True),
])
def test_search_requires_the_requested_subject(query, title, snippet, expected):
    assert query_relevant(query, {'title': title, 'snippet': snippet}) is expected


@pytest.mark.parametrize(('market', 'url', 'title', 'expected'), [
    ('US', 'https://roofings.in/', "India's Largest Roofing Brand", 'indexed_market_conflict'),
    ('UK', 'https://example.com/', 'Roofing services in India', 'indexed_market_conflict'),
    ('US', 'https://example.com/', 'London UK florist', 'indexed_market_conflict'),
    ('US', 'https://example.com/', 'Denver Colorado roofers', ''),
    ('UK', 'https://example.com/', 'Florist in Bristol UK', ''),
    ('US', 'https://example.co.uk/', 'Our United States office', ''),
    ('UK', 'https://example.co.uk/', 'Contact Us | Bespoke Dental Clinics', ''),
    ('US', 'https://example.in/', 'Contact us for skincare in India', 'indexed_market_conflict'),
    ('UK', 'https://example.co.uk/', 'CONTACT US | Bristol Florist', ''),
    ('US', 'https://example.in/', 'CONTACT US | Indian skin care', 'indexed_market_conflict'),
    ('UK', 'https://example.com/', 'US-based coffee company', 'indexed_market_conflict'),
])
def test_indexed_explicit_market_conflicts_are_held(market, url, title, expected):
    assert indexed_market_exclusion({'url': url, 'title': title}, market) == expected


async def test_no_subject_results_trigger_one_focused_retry_without_importing_noise(settings, monkeypatch):
    settings.discovery_platforms = ''
    settings.discovery_query_delay_seconds = .1
    queries = []
    async def search(settings, query, *args, **kwargs):
        queries.append(query)
        if len(queries) == 1:
            return [{'url': 'https://example.com/time', 'title': 'Current local time'}]
        return [{'url': 'https://example.org/', 'title': 'Denver Roofing Contractor', 'snippet': 'Colorado roof repair'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    rows, report = await prospect_candidates(settings, 'local roofing company Denver Colorado US contact', 'US', 2)
    assert len(queries) == 2
    assert queries[1] == 'roofing denver colorado United States'
    assert rows[0]['url'] == 'https://example.org/' and len(rows) == 1
    assert report['queries'] == queries and len(report['skipped']) == 1
