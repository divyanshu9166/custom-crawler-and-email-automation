import pytest

from outreach import discovery, providers


TARGET = 'https://www.linkedin.com/in/alex-doe'
ROW = {'url': TARGET, 'title': 'Alex Doe - Director | LinkedIn', 'snippet': 'Team https://bright-demo.com/team'}


@pytest.mark.parametrize('snippet,expected', [
    ('Regional Director, Architecture UK&I, AECOM · Passionate about architecture.', 'AECOM'),
    ('Director, Architecture UK&I, Bright Demo | Profile details', 'Bright Demo'),
    ('Director, Architecture, UK · Profile details', ''),
    ('Director, Architecture, United Kingdom · Profile details', ''),
    ('Director, Architecture, Company · Profile details', ''),
    ('Director, Architecture, I’m developing my career.', ''),
    ('Director, Architecture', ''),
    ('Director at Bright Demo · Regional Director, Architecture, Other Demo', 'Bright Demo'),
])
def test_terminal_role_department_employer_headline_is_only_a_bounded_query_hint(snippet, expected):
    from outreach.linkedin_recovery import indexed_employer_hint
    result = indexed_employer_hint({'title': 'Alex Doe | LinkedIn', 'snippet': snippet})
    assert result.get('company', '') == expected
    if result:
        assert result['verified'] is False and result['quote'] in snippet


@pytest.mark.parametrize('second_query_fails', [False, True])
async def test_second_identity_query_runs_before_unmatched_navigation_exhausts_leaf_budget(
    settings, monkeypatch, second_query_fails
):
    searches, pages = [], []
    wrong = 'https://wrong-demo.com/team/alex-doe'
    real = 'https://bright-demo.com/team/alex-doe'

    async def search(s, q, *_args, **_kwargs):
        searches.append(q)
        if len(searches) == 1:
            return [{'url': wrong, 'title': 'Alex Doe'}]
        assert len(pages) == 2  # Coworker frontier must not starve this query.
        if second_query_fails:
            raise TimeoutError('synthetic index failure')
        return [{'url': real, 'title': 'Alex Doe Director'}]

    async def snapshot(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        if url == 'https://bright-demo.com/':
            return staff_snapshot(url)
        pages.append(url)
        if url == real:
            return staff_snapshot(url)
        return {**staff_snapshot(url, TARGET+'-other'),
            'public_links': [f'https://wrong-demo.com/team/person-{i}' for i in range(8)]}

    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snapshot)
    result = await discovery.resolve_signal(settings, {**ROW, 'snippet': ''}, 'UK', ['linkedin.com'])
    assert len(searches) == 2
    assert result['person_recovery']['leaf_page_budget'] == 4
    assert len(result['person_recovery']['pages']) <= 4
    if second_query_fails:
        assert result['state'] == 'person_company_unconfirmed'
        assert len(pages) == 4  # Remaining observed routes are still inspected.
    else:
        assert result['state'] == 'official_staff_profile_candidate'
        assert result['person_recovery']['matched_people'][0]['source_url'] == real


@pytest.mark.parametrize('mode', ['raw_exact', 'split_scopes', 'foreign_raw', 'unhashed_raw'])
async def test_http_and_rendered_staff_records_keep_independent_profile_email_scope(settings, monkeypatch, mode):
    async def snapshot(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        result = staff_snapshot(url)
        result.update(rendered=True, sha256='rendered-hash')
        raw = staff_snapshot(url)
        raw.update(capture_method='public_html', sha256='http-hash')
        if mode == 'raw_exact':
            result['named_people'] = []
        else:
            result['named_people'][0]['email_publications'] = []
            if mode == 'split_scopes':
                raw['named_people'][0]['professional_links'] = [TARGET+'-other']
            elif mode == 'foreign_raw':
                raw['url'] = 'https://other-demo.com/team'
            else:
                raw.pop('sha256')
        result['http_snapshot'] = raw
        return result

    async def search(*args, **kwargs):
        pytest.fail('Explicit current staff URL should suffice')

    monkeypatch.setattr(discovery, 'public_snapshot', snapshot)
    monkeypatch.setattr(providers, 'discover', search)
    result = await discovery.resolve_signal(settings, ROW, 'UK', ['linkedin.com'])
    assert result['state'] == 'official_staff_profile_candidate'
    matched = result['person_recovery']['matched_people']
    assert len(matched) == 1
    if mode == 'raw_exact':
        assert matched[0]['official_snapshot_sha256'] == 'http-hash'
        assert matched[0]['source_capture_method'] == 'public_html'
        assert matched[0]['email_publications'][0]['email'] == 'alex@bright-demo.com'
    else:
        assert matched[0]['official_snapshot_sha256'] == 'rendered-hash'
        assert not matched[0]['email_publications']


@pytest.mark.parametrize('value,expected', [
    ('\u200fNik Kotecha\u200f', 'Nik Kotecha'),
    ('\u200e Alex Doe \u200e', 'Alex Doe'),
    ('Al\u200fex Doe', ''),
])
def test_index_name_boundary_direction_marks_do_not_drop_public_person_hint(value, expected):
    from outreach.people import indexed_person_name
    assert indexed_person_name(value) == expected


def staff_snapshot(url, profile=TARGET):
    return {'state': 'captured', 'url': url, 'title': 'Bright Demo', 'text': 'Bright Demo team', 'sha256': 'source-hash',
        'organization_names': ['Bright Demo'], 'named_people': [{'name': 'Alex Doe', 'role': 'Director',
        'quote': 'Alex Doe Director', 'professional_links': [profile], 'source_url': url,
        'email_publications': [{'email': 'alex@bright-demo.com', 'method': 'scoped_mailto'}]}]}


async def test_denied_linkedin_is_resolved_from_exact_current_staff_card(settings, monkeypatch):
    calls = []
    async def snap(s, url, platform=False):
        calls.append(url)
        if platform:
            return {'state': 'source_denied', 'http_status': 999}
        return staff_snapshot(url)
    async def search(*a, **kw):
        pytest.fail('Explicit official staff hint is sufficient; no engine request needed')
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    monkeypatch.setattr(providers, 'discover', search)
    signal = await discovery.resolve_signal(settings, ROW, 'UK', ['linkedin.com'])
    assert signal['website'] == 'https://bright-demo.com/' and signal['company'] == 'Bright Demo'
    assert signal['state'] == 'official_staff_profile_candidate'
    assert signal['public_snapshot']['http_status'] == 999
    assert signal['source_failover']['platform_access_recovered'] is False and calls.count(TARGET) == 1
    assert signal['person_recovery']['matched_people'][0]['email_publications'][0]['email'] == 'alex@bright-demo.com'


@pytest.mark.parametrize('issue', ['different_profile', 'name_mismatch', 'no_role', 'unavailable_home', 'article'])
async def test_person_name_or_indexed_email_alone_cannot_resolve_company(settings, monkeypatch, issue):
    async def snap(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        result = staff_snapshot(url, TARGET+'-other' if issue == 'different_profile' else TARGET)
        if issue == 'name_mismatch':
            result['named_people'][0]['name'] = 'Sam Roe'
        if issue == 'no_role':
            result['named_people'][0]['role'] = ''
        if issue == 'unavailable_home' and url == 'https://bright-demo.com/':
            result['state'] = 'unavailable'
        return result
    async def search(s, *a, **kw):
        assert s.search_provider == 'searxng' and not s.serpapi_key
        return []
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    monkeypatch.setattr(providers, 'discover', search)
    row = {**ROW, 'snippet': 'https://bright-demo.com/blog/alex alex@bright-demo.com' if issue == 'article' else ROW['snippet']}
    signal = await discovery.resolve_signal(settings, row, 'UK', ['linkedin.com'])
    assert not signal['website'] and signal['state'] == 'person_company_unconfirmed'


async def test_two_current_company_cards_for_same_profile_require_employer_review(settings, monkeypatch):
    async def snap(s, url, platform=False):
        return {'state': 'robots_denied'} if platform else staff_snapshot(url)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    signal = await discovery.resolve_signal(settings, {**ROW, 'snippet': ROW['snippet']+' https://other-demo.com/team'}, 'UK', ['linkedin.com'])
    assert signal['state'] == 'ambiguous_person_company_matches' and not signal['website']


async def test_initial_discovery_accepts_person_signal_without_creating_profile_business(db, settings, monkeypatch):
    from outreach.research import discover_leads
    settings.discovery_platforms = 'linkedin.com'
    async def search(s, q, *a, **kw):
        return [ROW] if 'site:linkedin.com/in/' in q else []
    async def snap(s, url, platform=False):
        return {'state': 'robots_denied'} if platform else staff_snapshot(url)
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    await discover_leads(db, settings, 'Director', 'A', 'UK', 2)
    lead = db.one('SELECT * FROM leads')
    assert lead['company'] == 'Bright Demo' and lead['lead_kind'] != 'profile'
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='research'")['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM contacts')['n'] == 0
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='verify'")['n'] == 0


async def test_homepage_hint_follows_only_observed_team_route_and_reuses_home(settings, monkeypatch):
    calls = []
    async def snap(s, url, platform=False):
        calls.append(url)
        if platform:
            return {'state': 'robots_denied'}
        if url == 'https://bright-demo.com/':
            return {**staff_snapshot(url), 'named_people': [], 'public_links': ['https://bright-demo.com/team',
                'https://other-company.com/team', 'https://bright-demo.com/account/team']}
        assert url == 'https://bright-demo.com/team'
        return {**staff_snapshot(url), 'public_links': ['https://bright-demo.com/contact',
            'https://bright-demo.com/team/unrelated-person']}
    async def search(*a, **kw):
        pytest.fail('Observed official navigation should not require an engine')
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    monkeypatch.setattr(providers, 'discover', search)
    signal = await discovery.resolve_signal(settings, {**ROW, 'snippet': 'https://bright-demo.com/'}, 'UK', ['linkedin.com'])
    assert signal['state'] == 'official_staff_profile_candidate'
    assert calls == [TARGET, 'https://bright-demo.com/', 'https://bright-demo.com/team']


async def test_navigation_budget_is_bounded_when_no_exact_staff_profile_matches(settings, monkeypatch):
    calls = []
    async def snap(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        calls.append(url)
        return {**staff_snapshot(url, TARGET+'-other'), 'public_links': [f'https://bright-demo.com/team/member-{i}' for i in range(100)]}
    async def search(*a, **kw):
        pytest.fail('Official page budget was exhausted')
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    monkeypatch.setattr(providers, 'discover', search)
    signal = await discovery.resolve_signal(settings, ROW, 'UK', ['linkedin.com'])
    assert len(calls) == 4 and not signal['website']


async def test_no_company_hint_resolves_through_minimal_name_index_query(settings, monkeypatch):
    queries = []
    async def search(s, q, *a, **kw):
        queries.append(q)
        assert q == '"Alex Doe"' and s.search_provider == 'searxng' and not s.serpapi_key
        return [{'url': 'https://bright-demo.com/team', 'title': 'Alex Doe | Bright Demo'}]
    async def snap(s, url, platform=False):
        return {'state': 'robots_denied'} if platform else staff_snapshot(url)
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    signal = await discovery.resolve_signal(settings, {**ROW, 'snippet': ''}, 'UK', ['linkedin.com'])
    assert signal['website'] == 'https://bright-demo.com/' and len(queries) == 1


async def test_contact_broker_copy_cannot_be_a_current_employer_source(settings, monkeypatch):
    async def search(s, *a, **kw):
        return [{'url': 'https://revonect.com/contact/Alex%20Doe', 'title': 'Alex Doe, Director'}]
    async def snap(s, url, platform=False):
        if not platform:
            pytest.fail('Contact broker must not be crawled as an employer publication')
        return {'state': 'robots_denied'}
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    signal = await discovery.resolve_signal(settings, {**ROW, 'snippet': ''}, 'UK', ['linkedin.com'])
    assert not signal['website'] and not signal['person_recovery']['pages']


@pytest.mark.parametrize('snippet,expected', [
    ('Architect Director within BDP with a focus on workplace projects.', 'BDP'),
    ('Founder and CEO at Bright Demo, London.', 'Bright Demo'),
    ('Director at Michael Laird Architects | UK', 'Michael Laird Architects'),
    ('Dentist and Owner at Dental Care of Corona ...', 'Dental Care of Corona'),
    ('Director at University of the Arts London', 'University of the Arts London'),
    ('Founder at Smith & Jones with a focus on services', 'Smith & Jones'),
    ('Founder at Bright Demo and interested in ecommerce', 'Bright Demo'),
    ('founder of Skincare Scientists I’m passionate about skincare', 'Skincare Scientists'),
    ("Founder at Bright Demo I've built a team", 'Bright Demo'),
    ('CEO at Bright Demo We’re growing', 'Bright Demo'),
    ("Director at O'Neill & Sons", "O'Neill & Sons"),
    ('Founder at a marketing agency', ''),
    ('CEO at self-employed', ''),
])
def test_only_declared_employer_hint_guides_research(snippet, expected):
    from outreach.linkedin_recovery import indexed_employer_hint
    hint = indexed_employer_hint({'snippet': snippet})
    assert hint.get('company', '') == expected
    if hint:
        assert hint['quote'] in snippet and hint['verified'] is False


async def test_employer_hint_targets_source_but_missing_profile_link_still_holds(settings, monkeypatch):
    calls = []
    async def search(s, q, *a, **kw):
        calls.append(q)
        return [{'url': 'https://bright-demo.com/people/alex-doe', 'title': 'Alex Doe Bright Demo'}]
    async def snap(s, url, platform=False):
        return {'state': 'robots_denied'} if platform else staff_snapshot(url, TARGET+'-other')
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    signal = await discovery.resolve_signal(settings, {**ROW, 'snippet': 'Director within Bright Demo with a focus on services'}, 'UK', ['linkedin.com'])
    assert calls[0] == '"Alex Doe" "Bright Demo"'
    assert signal['website'] == 'https://bright-demo.com/' and signal['resolved_company_only'] is True
    assert signal['person_identity_verified'] is False and signal['person_recovery']['person_identity_state'] == 'held'
    observations = signal['person_recovery']['official_person_observations']
    assert observations and all(p['matches_requested_profile'] is False for p in observations)
    assert not signal['person_recovery']['matched_people']


async def test_employer_company_match_cannot_use_name_mentioned_only_in_customer_text(settings, monkeypatch):
    from outreach.linkedin_recovery import employer_company_candidate
    async def search(*a, **kw):
        return [{'url': 'https://publisher-demo.com/people/alex', 'title': 'Bright Demo'}]
    async def snap(s, url, **kw):
        return {'state': 'captured', 'url': url, 'title': 'Publisher Demo', 'organization_names': ['Publisher Demo'],
                'text': 'We write about Bright Demo and its founders.', 'sha256': 'hash'}
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    report = await employer_company_candidate(settings, {'company': 'Bright Demo'}, 'UK')
    assert report['state'] == 'unconfirmed' and not report.get('company_candidate')


async def test_ambiguous_current_employer_company_domains_remain_unconfirmed(settings, monkeypatch):
    from outreach.linkedin_recovery import employer_company_candidate
    async def search(*a, **kw):
        return [{'url': 'https://one-demo.com/', 'title': 'Bright Demo'}, {'url': 'https://two-demo.com/', 'title': 'Bright Demo'}]
    async def snap(s, url, **kw):
        return staff_snapshot(url)
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    report = await employer_company_candidate(settings, {'company': 'Bright Demo'}, 'UK')
    assert report['state'] == 'ambiguous_company_candidates' and not report.get('company_candidate')


async def test_directory_roots_do_not_consume_the_independent_company_budget(settings, monkeypatch):
    from outreach.linkedin_recovery import employer_company_candidate
    async def search(*a, **kw):
        return [{'url': f'https://{host}/people/alex', 'title': 'Bright Demo'} for host in
            ['findglocal.com', 'endole.co.uk', 'ipaddress.com', 'shop.app']] + [
            {'url': 'https://bright-demo.com/', 'title': 'Bright Demo'}]
    async def snap(s, url, **kw):
        assert url == 'https://bright-demo.com/'
        return staff_snapshot(url)
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(discovery, 'public_snapshot', snap)
    report = await employer_company_candidate(settings, {'company': 'Bright Demo'}, 'UK')
    assert report['state'] == 'company_only_candidate' and len(report['candidates']) == 1
