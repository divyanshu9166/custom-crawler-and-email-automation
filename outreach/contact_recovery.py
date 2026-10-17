"""Recover public contact sources without treating indexed/social hints as ownership proof."""
import asyncio
import hashlib
import json
import re
import time
from urllib.parse import unquote, urlsplit

from . import providers
from .discovery import company_title, official_root
from .research import add_contact, fresh_evidence, record_contact_publications
from .web import PublicWeb, company_crawl_url, crawl_url, priority
from .crawl_state import timestamp


def eligible_lead(db, lead_id):
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead or lead['lead_kind'] == 'profile':
        raise ValueError('Resolve and research the official website before contact recovery')
    official_root(lead['website'])
    if db.one("SELECT 1 FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)):
        raise ValueError('Existing outreach history: preserve evidence and review manually')
    if not fresh_evidence(db, lead_id):
        raise ValueError('Contact recovery requires current official-site research first')
    crawl=db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1',(lead_id,))
    checkpoint=json.loads(crawl['report']).get('checkpoint',{}) if crawl else {}
    if timestamp(checkpoint.get('domain_not_before'))>time.time():
        raise ValueError('Site cooldown is active; contact recovery must wait until the saved retry time')
    return lead


def contact_route(url, domain):
    url = company_crawl_url(url, domain)
    if not url:
        return ''
    parts = urlsplit(url)
    segments = unquote(parts.path + '/' + parts.fragment).lower().split('/')
    editorial_or_catalog = {'blog', 'blogs', 'news', 'articles', 'products', 'collections',
        'projects', 'case-studies', 'portfolio', 'testimonials', 'reviews', 'clients', 'customers', 'insights'}
    route = any(re.match(r'^(?:contact|about|team|people|our-people|studio|practice|leadership|founders?|staff|management|our-team|meet-the-team|business-enquiries|business-inquiries|enquiries|inquiries|media-relations)(?:[-_]|$)', s)
                or s in {'contactus', 'aboutus'} for s in segments)
    return url if route and not editorial_or_catalog.intersection(segments) else ''


def official_contact_seeds(db, lead):
    """Reuse sourced contact/navigation routes even when the index is unavailable."""
    sources = {}
    def add(url, origin):
        try:
            url = contact_route(url, lead['domain'])
        except ValueError:
            return
        if url:
            sources.setdefault(url, set()).add(origin)
    for page in fresh_evidence(db, lead['id']):
        add(page['url'], 'saved_official_page')
    row = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
    if row:
        checkpoint = json.loads(row['report']).get('checkpoint', {})
        if checkpoint.get('website') == crawl_url(lead['website']):
            for entry in checkpoint.get('frontier', []):
                add(entry['url'], 'saved_official_navigation')
            for entry in checkpoint.get('retry_urls',[]):
                add(entry['url'],'saved_retry_route')
            if checkpoint.get('inflight'):
                add(checkpoint['inflight']['url'],'interrupted_official_route')
    return sources


async def research_contacts(db, settings, lead_id):
    lead = eligible_lead(db, lead_id)
    domain = lead['domain']
    name = company_title(lead['company']).replace('"', '')
    queries = [f'site:{domain} (contact OR email)',
               f'site:{domain} (founder OR owner OR leadership OR team)',
               f'"{name}" "{domain}" contact email']
    report = {'lead_id': lead_id, 'started_at': time.time(), 'queries': [], 'indexed_hints': [],
              'pages_saved': 0, 'contact_ids': [], 'state': 'researching',
              'note': 'Index/social snippets are discovery hints only. Contacts require a newly captured official page; buyer relevance and mailbox verification remain separate.'}
    sources = official_contact_seeds(db, lead)
    for query in queries:
        try:
            rows = await providers.discover(settings, query, 10, include_platforms=True)
            report['queries'].append({'query': query, 'engine_issues': getattr(rows, 'engine_issues', []),
                'providers': getattr(rows, 'provider_reports', []), 'result_count': len(rows)})
            for row in rows:
                try:
                    url = crawl_url(row['url'])
                except ValueError:
                    continue
                report['indexed_hints'].append({'url': url, 'title': row.get('title', '')[:200],
                    'snippet': row.get('snippet', '')[:1500], 'review_required': True,
                    'sha256': hashlib.sha256((row.get('title', '')+'\n'+row.get('snippet', '')).encode()).hexdigest()})
                official = company_crawl_url(url, domain)
                if official:
                    sources.setdefault(official, set()).add('search_index')
        except Exception as exc:
            report['queries'].append({'query': query, 'error_type': type(exc).__name__})
        await asyncio.sleep(settings.discovery_query_delay_seconds)
    from .public_index import commoncrawl_routes
    archive = await commoncrawl_routes(settings, lead['website'])
    report['url_index'] = archive
    for hint in archive['rows']:
        sources.setdefault(hint['url'], set()).add('commoncrawl_url_hint')
    # Indexed routes can expose contact/team pages missed by navigational links.
    # Published emails in those snippets are never imported or probed directly.
    main_row=db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1',(lead_id,))
    cp=json.loads(main_row['report']).get('checkpoint',{}) if main_row else {}
    deferred={entry['url'] for entry in cp.get('retry_urls',[]) if timestamp(entry.get('not_before'))>time.time()}
    report['deferred_retry_urls']=sorted(set(sources)&deferred)
    seeds = sorted(set(sources)-deferred, key=lambda u: (priority(u), 'saved_official_page' in sources[u], u))[:settings.contact_research_max_pages]
    if not seeds and report['deferred_retry_urls']:
        report.update(state='held',reason='Known contact routes are awaiting their saved retry time',finished_at=time.time())
        db.event('contact_research',report)
        return report
    navigation_fallback = not seeds
    if navigation_fallback:
        # Follow only newly observed official links; do not guess contact paths.
        seeds = [crawl_url(lead['website'])]
        sources[seeds[0]] = {'official_homepage_navigation'}
    report['seed_sources'] = [{'url': u, 'origins': sorted(sources[u])} for u in seeds]
    report['navigation_fallback'] = navigation_fallback
    eligible_lead(db, lead_id)  # Search can take minutes; recheck before mutation.
    crawl_row = db.one('SELECT id FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead_id,))
    async def save(page, _):
        eligible_lead(db, lead_id)
        with db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute("SELECT 1 FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)).fetchone():
                raise ValueError('Outreach started during recovery; preserve approved evidence')
            latest = con.execute('SELECT id FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead_id,)).fetchone()
            if (latest['id'] if latest else None) != (crawl_row or {}).get('id'):
                raise ValueError('Research changed during contact recovery; reload')
            con.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at',
                        (lead_id, page['url'], page['title'], page['text'], page['sha256'], time.time()))
            if latest:
                main = json.loads(con.execute('SELECT report FROM crawls WHERE id=?', (latest['id'],)).fetchone()['report'])
                captured = {r['url'] for r in con.execute('SELECT url FROM evidence WHERE lead_id=? AND fetched_at>=(SELECT created_at FROM crawls WHERE id=?)', (lead_id, latest['id']))}
                checkpoint = main.setdefault('checkpoint', {'website': crawl_url(lead['website']), 'frontier': [],
                    'seen': sorted(captured), 'sitemap_queue': [], 'sitemap_seen': [], 'depth_limited': [],
                    'origin': 'Newly captured official contact-search pages; reconstructed frontier, not the original cursor'})
                frontier = {e['url']: e for e in checkpoint['frontier'] if e['url'] not in captured}
                for link in page['links']:
                    try:
                        url = company_crawl_url(link, domain)
                    except ValueError:
                        continue
                    if url and url not in captured and len(frontier) < 10000:
                        frontier.setdefault(url, {'url': url, 'depth': 1})
                checkpoint['frontier'] = list(frontier.values())
                checkpoint['seen'] = sorted(set(checkpoint.get('seen', [])) | captured)
                # A recovered page must not remain queued as a failed URL in
                # the original crawl. Keep unrelated work and cooldowns intact.
                checkpoint['retry_urls']=[e for e in checkpoint.get('retry_urls',[]) if e['url'] not in captured]
                if (checkpoint.get('inflight') or {}).get('url') in captured:
                    checkpoint['inflight']=None
                for error in main.get('errors',[]):
                    if error.get('url')==page['url'] and error.get('retryable'):
                        error['resolved_at']=time.time()
                entry = {'url': page['url'], 'rendered': page.get('rendered', False), 'emails': len(page['emails']),
                         'text_chars': len(page['text']), 'contact_research': True}
                from .professionals import sourced_profile_links
                entry.update(sha256=page['sha256'],professional_links=sourced_profile_links(page),
                             named_people=page.get('named_people', []),
                             http_publication_retained=page.get('http_publication_retained', False),
                             http_navigation_retained=page.get('http_navigation_retained', False),
                             http_navigation_links=page.get('http_navigation_links', []),
                             capture_sources=page.get('capture_sources', []))
                main['pages'] = [p for p in main.get('pages', []) if p['url'] != page['url']] + [entry]
                main.update(status='partial', remaining=len(set(frontier)|{e['url'] for e in checkpoint['retry_urls']}),
                            retry_pending=len(checkpoint['retry_urls']))
                main.setdefault('contact_recovery', []).append({'at': time.time(), 'url': page['url']})
                con.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(main), latest['id']))
        record_contact_publications(db, lead_id, page)
        for entry in page.get('review_candidates', []):
            detail = {**entry, 'lead_id': lead_id, 'source_url': page['url'], 'evidence_sha256': page['sha256']}
            key = hashlib.sha256(json.dumps([lead_id, page['url'], entry['email'], page['sha256']]).encode()).hexdigest()
            db.event('contact_candidate_found', detail, external_id='candidate:'+key)
        identities = {c['email']: c for c in page.get('contacts', [])}
        for email in page['emails']:
            contact = identities.get(email, {})
            cid = add_contact(db, lead_id, email, page['url'], contact.get('name', ''), contact.get('role', ''))
            if contact.get('identity_ambiguous'):
                db.execute("UPDATE contacts SET name='',role='' WHERE id=? AND status='new'", (cid,))
            report['contact_ids'].append(cid)
            row = db.one('SELECT status,verification FROM contacts WHERE id=?', (cid,))
            if row['status'] != 'suppressed' and row['verification'] == 'unverified':
                db.enqueue('verify', {'contact_id': cid})
        report['pages_saved'] += 1
    bounded = settings.model_copy(update={'crawl_max_pages': settings.contact_research_max_pages,
                                          'crawl_max_sitemaps': 0})
    crawler = PublicWeb(bounded, on_page=save)
    try:
        await crawler.crawl(lead['website'], seed_urls=seeds, follow_links=navigation_fallback)
        report['state'] = ('held' if not report['pages_saved'] else
                           'partial' if crawler.report['status'] != 'complete' else 'captured')
        if not report['pages_saved']:
            report['reason'] = 'No accessible official pages captured; inspect crawl diagnostics'
    except Exception as exc:
        report.update(state='partial' if report['pages_saved'] else 'held', error_type=type(exc).__name__)
    finally:
        report.update(crawl=crawler.report, seed_urls=seeds,
                      contact_ids=sorted(set(report['contact_ids'])), finished_at=time.time())
        db.event('contact_research', report)
    return report
