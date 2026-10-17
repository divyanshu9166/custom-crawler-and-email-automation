"""Real browser fixtures and pipeline contracts; no live accounts or recipients."""
import hashlib
import json
import time
import importlib.util
from types import SimpleNamespace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright

from outreach import platform_browser, social_browser, social_research, source_status
from outreach.app import create_app
from outreach.preferences import Preferences
from outreach.config import Settings

ROOT = Path(__file__).resolve().parents[1]
PERSON = 'https://www.linkedin.com/in/alex-demo'
X = 'https://x.com/BrightDemo'
PROFILE = '''<nav>PRIVATE ACCOUNT</nav><main><section><h1>Alex Demo</h1>
<p data-testid="profile-headline">Founder at Bright Demo</p></section>
<section><h2>About</h2><p data-testid="profile-about">We run Bright Demo in London, UK.</p></section></main>'''
EXPERIENCE = '''<nav>PRIVATE INBOX</nav><main><section><h2>Experience</h2>
<p>Founder at Bright Demo since 2022</p><span hidden>PRIVATE HIDDEN</span></section></main>'''
CONTACT = '''<main>PRIVATE PROFILE BACKGROUND</main><div role="dialog"><h2>Contact Info</h2>
<p>Business email <a href="mailto:alex%40bright-demo.com">Email</a></p><span hidden>PRIVATE HIDDEN</span></div>'''


@pytest.fixture
def browser_fixture(settings, monkeypatch):
    settings.platform_browser_enabled = True
    settings.platform_browser_delay_seconds = 0
    settings.platform_browser_search_steps = 1
    settings.social_posts_max_posts = 1
    source = {'routes': {}, 'visited': []}
    class Session:
        def __init__(self, *args):
            self.last_access_issue = {}
        async def __aenter__(self):
            self.runtime = await async_playwright().start()
            self.browser = await self.runtime.chromium.launch()
            self.context = await self.browser.new_context()
            async def route(request):
                value = source['routes'].get(urlsplit(request.request.url).path, '<main>Unsupported fixture</main>')
                status, body = value if isinstance(value, tuple) else (200, value)
                await request.fulfill(status=status, body=body, content_type='text/html')
            await self.context.route('**/*', route)
            return self
        async def navigate(self, url):
            source['visited'].append(url)
            page = await self.context.new_page()
            response = await page.goto(url)
            return page, response.status if response.status >= 400 else None
        async def __aexit__(self, *args):
            await self.browser.close()
            await self.runtime.stop()
    monkeypatch.setattr(platform_browser, 'BrowserSession', Session)
    return settings, source


async def test_people_search_uses_bounded_rendered_cards_and_keeps_identity_unverified(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/search/results/people/'] = '''<nav><a href="/in/private-owner">PRIVATE ACCOUNT</a></nav>
    <main><div class="search-results-container"><div class="entity-result">
    <a href="/in/alex-demo?tracking=private">Alex Demo</a><a href="/in/alex-demo">Alex Demo</a>
    Founder at Bright Demo · London<span hidden>PRIVATE HIDDEN</span></div>
    <div class="entity-result"><a href="https://attacker.test/in/other">Wrong origin</a></div></div></main>'''
    rows = await social_browser.browser_people_discover(settings, 'Bright Demo founder UK', 1)
    assert len(rows) == 1 and rows[0]['url'] == PERSON
    assert not rows[0]['buyer_verified'] and not rows[0]['identity_verified']
    assert 'PRIVATE' not in json.dumps(rows) and 'tracking' not in rows[0]['url']
    assert rows.provider_reports[0]['operation'] == 'people_search'
    assert rows.provider_reports[0]['next_page_actions'] == 0


async def test_people_search_honors_durable_access_hold_without_opening_browser(browser_fixture):
    settings, source = browser_fixture
    platform_browser.record_hold(settings, 'linkedin.com', 'http_999')
    rows = await social_browser.browser_people_discover(settings, 'Bright Demo founder UK')
    assert not rows and rows.engine_issues == [['linkedin.com', 'operator_attention']]
    assert not source['visited']


async def test_experience_and_explicit_contact_info_reuse_root_session_and_keep_provenance(browser_fixture):
    settings, source = browser_fixture
    settings.linkedin_contact_info_enabled = True
    source['routes'].update({'/in/alex-demo': PROFILE, '/in/alex-demo/details/experience/': EXPERIENCE,
                             '/in/alex-demo/overlay/contact-info/': CONTACT})
    result = await platform_browser.browser_professional_snapshot(settings, PERSON)
    assert result['state'] == 'captured' and result['url'] == PERSON
    assert result['published_emails'] == ['alex@bright-demo.com']
    assert 'Founder at Bright Demo since 2022' in result['text']
    assert 'PRIVATE' not in json.dumps(result)
    assert result['sections']['experience']['source_url'].endswith('/details/experience/')
    assert result['sections']['contact_info']['visibility'] == 'account_visible'
    assert result['scope'] == 'account_visible_professional_fields'
    assert not result['identity_verified']
    assert len(source['visited']) == 3


async def test_contact_panel_is_not_requested_by_default_and_inline_experience_avoids_extra_navigation(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/in/alex-demo'] = PROFILE.replace('</main>', '<section><h2>Experience</h2><p>Founder at Bright Demo</p></section></main>')
    result = await platform_browser.browser_professional_snapshot(settings, PERSON)
    assert 'experience' in result['sections'] and 'contact_info' not in result['sections']
    assert source['visited'] == [PERSON]


async def test_experience_switch_excludes_inline_experience_and_avoids_detail_navigation(browser_fixture):
    settings, source = browser_fixture
    settings.linkedin_profile_experience_enabled = False
    source['routes']['/in/alex-demo'] = PROFILE.replace('</main>', '<section><h2>Experience</h2><p>OFF EXPERIENCE DATA</p></section></main>')
    result = await platform_browser.browser_professional_snapshot(settings, PERSON)
    assert 'experience' not in result['sections'] and 'OFF EXPERIENCE' not in result['text']
    assert source['visited'] == [PERSON]


async def test_semantic_people_cards_do_not_require_legacy_css_classes(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/search/results/people/'] = '<main><div role="list"><div role="listitem"><a href="/in/alex-demo">Alex Demo</a>Founder at Bright Demo</div></div></main>'
    rows = await social_browser.browser_people_discover(settings, 'Bright Demo founder UK', 1)
    assert len(rows) == 1 and rows[0]['url'] == PERSON


async def test_modern_person_h2_and_hidden_first_h1_are_supported_without_account_chrome(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/in/alex-demo'] = PROFILE.replace('<h1>Alex Demo</h1>', '<h1 hidden>PRIVATE HIDDEN</h1><header><h2>Alex Demo</h2></header>')
    settings.linkedin_profile_experience_enabled = False
    # Headline belongs to the top-card section, not the inner header.
    result = await platform_browser.browser_professional_snapshot(settings, PERSON)
    assert result['state'] == 'captured' and result['title'] == 'Alex Demo'
    assert 'PRIVATE' not in result['text']


async def test_optional_section_denial_keeps_root_evidence_but_records_hold(browser_fixture):
    settings, source = browser_fixture
    source['routes'].update({'/in/alex-demo': PROFILE, '/in/alex-demo/details/experience/': (403, 'Denied')})
    result = await platform_browser.browser_professional_snapshot(settings, PERSON)
    assert result['state'] == 'captured'
    assert result['section_errors'] == [{'section': 'experience', 'state': 'http_error', 'http_status': 403}]
    assert platform_browser.hold(settings, 'linkedin.com')['reason'] == 'http_403'


def tweet(author='BrightDemo', text='We launched a new UK store. Business email: hello@bright-demo.com', post_author=None):
    return f'''<article data-testid="tweet"><div data-testid="User-Name"><a href="/{author}">{author}</a></div>
    <div data-testid="tweetText">{text}<span hidden>PRIVATE HIDDEN</span><div data-testid="quoteTweet">PRIVATE QUOTED</div></div>
    <a href="/{post_author or author}/status/123456"><time datetime="2026-10-16T12:00:00Z">Yesterday</time></a></article>'''


async def test_x_posts_require_matching_author_and_permalink_and_exclude_quotes(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/BrightDemo'] = '<nav>PRIVATE ACCOUNT</nav><main>' + tweet('OtherDemo') + tweet(post_author='OtherDemo') + tweet() + '</main>'
    result = await social_browser.browser_recent_posts(settings, X)
    assert result['state'] == 'captured' and len(result['posts']) == 1
    assert result['posts'][0]['author_url'] == X and result['posts'][0]['url'] == X+'/status/123456'
    assert 'PRIVATE' not in json.dumps(result)
    assert result['posts'][0]['published_at'] == '2026-10-16T12:00:00Z'
    assert not result['posts'][0]['identity_verified']


async def test_quote_only_post_cannot_be_misattributed_to_the_outer_author(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/BrightDemo'] = '''<main><article data-testid="tweet">
      <div data-testid="User-Name"><a href="/BrightDemo">Bright Demo</a></div>
      <div data-testid="quoteTweet"><div data-testid="tweetText">OTHER AUTHOR EMAIL: wrong@other-demo.com</div></div>
      <a href="/BrightDemo/status/123456"><time datetime="2026-10-16T12:00:00Z">Yesterday</time></a></article></main>'''
    result = await social_browser.browser_recent_posts(settings, X)
    assert not result['posts'] and result['state'] == 'no_author_matched_posts'


async def test_protected_x_account_posts_are_not_accepted_as_public_research(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/BrightDemo'] = '<main><div data-testid="UserName"><span aria-label="Protected account">Locked</span></div>'+tweet()+'</main>'
    result = await social_browser.browser_recent_posts(settings, X)
    assert result['state'] == 'protected_profile' and not result['posts']


async def test_linkedin_company_posts_are_separate_from_personal_and_inbox_routes(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/company/bright/posts/'] = '''<main><div data-urn="urn:li:activity:123456">
      <div class="update-components-actor"><a href="/company/bright/">Bright</a></div>
      <div class="update-components-text">Our new ecommerce store is live.</div></div></main>'''
    result = await social_browser.browser_recent_posts(settings, 'https://www.linkedin.com/company/bright/about/')
    assert result['state'] == 'captured' and len(result['posts']) == 1
    assert result['posts'][0]['url'] == 'https://www.linkedin.com/feed/update/urn:li:activity:123456/'
    assert result['posts'][0]['published_at'] is None
    with pytest.raises(ValueError):
        await social_browser.browser_recent_posts(settings, PERSON)


async def test_x_search_can_fall_back_to_public_post_author_hints_without_api_or_cookies_export(browser_fixture):
    settings, source = browser_fixture
    source['routes']['/search'] = '<main>' + tweet() + '</main>'
    # User search cannot read a post card; latest-post search supplies author hints.
    # Avoid the legacy 10-second empty-layout readiness wait in this focused path.
    target = 'https://x.com/search?q=UK+store&f=live'
    rows = await platform_browser._discover_locked(settings, 'x.com', target, 1, post_search=True)
    assert len(rows) == 1 and rows[0]['url'] == X
    assert rows[0]['source_post_url'] == X+'/status/123456'
    assert rows[0]['indexed_signal_only']
    assert platform_browser.search_identity_matches(target, target+'&page=2')
    assert not platform_browser.search_identity_matches(target, target.replace('f=live','f=user'))


def test_research_controls_persist_and_do_not_enable_worker_or_sending(settings):
    settings.sending_enabled = False
    original = settings.model_dump()
    app = create_app(settings)
    client = TestClient(app, base_url=settings.public_url)
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    body = {'linkedin_contact_info_enabled': True, 'social_posts_max_posts': 2, 'social_posts_max_profiles': 1}
    assert client.put('/api/settings/research', json=body).status_code == 200
    restarted = Settings(_env_file=None, **original)
    Preferences(restarted)
    assert restarted.linkedin_contact_info_enabled and restarted.social_posts_max_posts == 2
    assert not restarted.worker_enabled and not restarted.sending_enabled
    assert app.state.db.get('paused') == 'true'
    assert client.put('/api/settings/research', json={'linkedin_contact_info_enabled': 'yes'}).status_code == 422
    assert client.put('/api/settings/research', json={'social_posts_max_posts': 100}).status_code == 422
    assert client.put('/api/settings/research', json={'sending_enabled': True}).status_code == 422
    client.headers.clear()
    assert client.get('/api/source-status').status_code == 401


def test_source_status_does_not_infer_access_from_configuration_and_deduplicates_latest(settings, db):
    settings.platform_browser_enabled = True
    assert source_status.snapshot(db, settings)['providers'][0]['last_state'] == 'not_tested'
    source_status.record(db, 'managed_browser:linkedin.com', 'profile', PERSON, {'state': 'captured'}, contacts=1)
    source_status.record(db, 'managed_browser:linkedin.com', 'profile', PERSON, {'state': 'operator_attention'})
    summary = source_status.snapshot(db, settings)
    row = summary['providers'][0]
    assert row['configured'] and row['captured_sources'] == 0 and row['contact_sources'] == 0
    assert row['last_state'] == 'operator_attention' and len(summary['observations']) == 1


async def test_post_capture_is_saved_locally_without_contact_import_and_can_support_reviewed_ai_trigger(settings, db, prepared, monkeypatch):
    from outreach.campaigns import review_lead, create_drafts
    settings.platform_browser_enabled = True
    text = 'Bright Demo launched a new online store for UK customers.'
    async def captured(s, url):
        return {'state': 'captured', 'profile_url': X, 'observed_at': time.time(),
                'posts': [{'url': X+'/status/123456', 'author_url': X, 'text': text, 'published_at': None}]}
    monkeypatch.setattr(social_browser, 'browser_recent_posts', captured)
    lid = prepared['lead_id']
    result = await social_research.research_posts(db, settings, lid, [{'url': X, 'origin': 'captured_official_navigation'}])
    page = db.one('SELECT * FROM evidence WHERE lead_id=? AND url=?', (lid, X+'/status/123456'))
    assert result['state'] == 'captured' and social_research.is_social_evidence(db, lid, page)
    assert len(db.all('SELECT * FROM contacts')) == 1
    assert not db.one("SELECT id FROM jobs WHERE kind='verify'")
    value = {'company': 'Bright Demo', 'country': 'UK', 'country_source': 'https://bright-demo.com/',
             'country_quote': 'UK consulting services', 'timezone': 'Europe/London', 'business_type': 'corporate',
             'service': 'website_improvement', 'primary_goal': 'inquiries_bookings',
             'fit_notes': 'Relevant consulting company serving UK business clients.', 'evidence_id': prepared['evidence_id'],
             'quote': 'Contact us for a consultation.', 'observation': 'Your homepage invites visitors to contact you.',
             'suggestion': 'Test a clearer explanation of the first consultation.', 'recent_trigger': 'You announced a new online store.',
             'trigger_evidence_id': page['id'], 'trigger_quote': text}
    review_lead(db, lid, value)
    create_drafts(db, settings, prepared['contact_id'])
    event = db.one("SELECT detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")
    # The controlled writer records all reviewed sources in its provenance.
    assert page['id'] in json.loads(event['detail'])['source_ids']
    assert social_research.is_social_evidence(db, lid, page)
    page['text'] = 'Changed unverified content'
    page['sha256'] = hashlib.sha256(page['text'].encode()).hexdigest()
    assert not social_research.is_social_evidence(db, lid, page)
    with pytest.raises(ValueError):
        review_lead(db, lid, {**value, 'evidence_id': db.one('SELECT id FROM evidence WHERE url=?', (X+'/status/123456',))['id'], 'quote': text})


def test_social_job_is_authenticated_deduplicated_and_serialized_with_same_prospect_research(settings, db, prepared):
    settings.platform_browser_enabled = True
    client = TestClient(create_app(settings), base_url=settings.public_url)
    url = f"/api/leads/{prepared['lead_id']}/social-research"
    assert client.post(url).status_code == 401
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    first = client.post(url)
    assert first.status_code == 200
    assert first.json() == client.post(url).json()
    jid = first.json()['job_id']
    app_db = client.app.state.db
    app_db.execute("UPDATE jobs SET state='running' WHERE id=?", (jid,))
    other = app_db.enqueue('research', {'lead_id': prepared['lead_id']})
    assert app_db.claim({'research'}) is None
    app_db.execute("UPDATE jobs SET state='done' WHERE id=?", (jid,))
    assert app_db.claim({'research'})['id'] == other
    assert client.get('/api/source-status').status_code == 200


async def test_deployment_diagnostic_refuses_enabled_controls_before_any_provider_call(settings, monkeypatch):
    spec = importlib.util.spec_from_file_location('check_social_research', ROOT/'scripts/check_social_research.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async def forbidden(*args, **kwargs):
        pytest.fail('Controls must be checked before browser access')
    monkeypatch.setattr(module, 'browser_people_discover', forbidden)
    result = await module.check(settings, people_query='Bright Demo founder UK')
    assert result['state'] == 'controls_not_off'


async def test_automatic_professional_research_uses_managed_buyer_search_and_saves_capture(settings, db, prepared, monkeypatch):
    from outreach.professionals import research_professionals
    from outreach.providers import SearchRows
    settings.platform_browser_enabled = True
    settings.platform_browser_public_fallback = False
    settings.professional_max_profiles = 1
    settings.social_posts_enabled = False
    seen = []
    async def people(s, query, limit):
        seen.append(query)
        return SearchRows([{'url': PERSON, 'title': 'Alex Demo', 'snippet': 'Founder at Bright Demo'}])
    async def profile(s, target):
        assert target == PERSON
        return {'state': 'captured', 'url': PERSON, 'title': 'Alex Demo', 'headline': 'Founder at Bright Demo',
                'text': 'Alex Demo Founder at Bright Demo. Business email: alex@bright-demo.com'}
    monkeypatch.setattr(social_browser, 'browser_people_discover', people)
    monkeypatch.setattr('outreach.professionals.profile_snapshot', profile)
    result = await research_professionals(db, settings, prepared['lead_id'])
    assert len(seen) == 1 and 'Bright Demo' in seen[0] and 'founder' in seen[0]
    assert result['state'] == 'captured'
    capture = json.loads(db.one("SELECT detail FROM events WHERE kind='professional_capture' ORDER BY id DESC LIMIT 1")['detail'])
    assert capture['source_hint']['origin'] == 'managed_people_search' and not capture['identity_verified']
    assert len(db.all('SELECT * FROM contacts')) == 1


async def test_post_scroll_timeout_preserves_already_captured_posts(settings, monkeypatch):
    settings.platform_browser_enabled = True
    settings.platform_browser_delay_seconds = 0
    settings.platform_browser_search_steps = 2
    settings.social_posts_max_posts = 2
    async def evaluate(*args):
        return {'state': 'captured', 'posts': [{'url': X+'/status/123456', 'text': 'A current business announcement.'}]}
    async def timeout(*args):
        raise TimeoutError()
    page = SimpleNamespace(evaluate=evaluate, mouse=SimpleNamespace(wheel=timeout))
    class Session:
        def __init__(self, *args): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def navigate(self, url): return page, None
    monkeypatch.setattr(platform_browser, 'BrowserSession', Session)
    result = await social_browser.browser_recent_posts(settings, X)
    assert result['state'] == 'captured' and result['stop_reason'] == 'deadline'
    assert len(result['posts']) == 1 and result['partial']


async def test_standalone_post_job_reads_only_current_saved_business_profile_links(settings, db, prepared, monkeypatch):
    settings.platform_browser_enabled = True
    lid = prepared['lead_id']
    page = db.one('SELECT * FROM evidence WHERE id=?', (prepared['evidence_id'],))
    report = {'pages': [{'url': page['url'], 'sha256': page['sha256'], 'business_profile_links': [X]}]}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(report), time.time()-20))
    seen = []
    async def captured(s, profile):
        seen.append(profile)
        return {'state': 'captured', 'profile_url': profile, 'observed_at': time.time(),
                'posts': [{'url': X+'/status/123456', 'text': 'Bright Demo announcement'}]}
    monkeypatch.setattr(social_browser, 'browser_recent_posts', captured)
    await social_research.research_known_posts(db, settings, lid)
    assert seen == [X]
    db.execute("UPDATE evidence SET sha256='changed' WHERE id=?", (page['id'],))
    seen.clear()
    report = await social_research.research_known_posts(db, settings, lid)
    assert not seen and report['state'] == 'no_known_profiles'


def test_business_profile_links_are_bounded_deduplicated_and_reject_private_routes():
    from outreach.profiles import business_profile_links
    links = [X, X+'?tracking=discarded', 'https://www.linkedin.com/company/bright',
             PERSON, 'https://x.com/messages', 'https://bright-demo.com/contact']
    assert business_profile_links(links) == [X, 'https://www.linkedin.com/company/bright']
