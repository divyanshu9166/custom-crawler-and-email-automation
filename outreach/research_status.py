"""Read-only first-workflow results. Captures never imply buyer/identity review."""
import json
import time
from .crawl_state import current_errors,timestamp


def source_coverage(con,lead_id,now):
    """Latest observation per source/market; matches and emails are candidates."""
    from .discovery import domain_of, profile_key
    from .web import normalize_email, outreach_email_allowed
    sources,seen={},set()
    for row in con.execute("SELECT detail,created_at FROM events WHERE kind='prospect_signal' ORDER BY id DESC LIMIT 500"):
        signal=json.loads(row['detail'])
        if lead_id and signal.get('lead_id')!=lead_id:
            continue
        url=signal.get('source_url','')
        if not url:
            continue
        key=(*profile_key(url),signal.get('country_hint',''))
        if key in seen:
            continue
        seen.add(key)
        name=signal.get('platform') or domain_of(url) or 'unknown'
        stats=sources.setdefault(name,{'source':name,'signals':0,'captured':0,'unavailable':0,
            'website_candidates':set(),'failover_candidates':set(),'published_email_candidates':set(),'last_observed_at':0})
        stats['signals']+=1
        stats['last_observed_at']=max(stats['last_observed_at'],row['created_at'])
        snap=signal.get('public_snapshot',{})
        captured=snap.get('state')=='captured' and 0<=now-timestamp(snap.get('observed_at',row['created_at']))<=30*86400
        stats['captured' if captured else 'unavailable']+=1
        if signal.get('website'):
            domain=domain_of(signal['website'])
            stats['website_candidates'].add(domain)
            if signal.get('source_failover',{}).get('used'):
                stats['failover_candidates'].add(domain)
        if captured:
            for address in snap.get('published_emails',[]):
                try:
                    email=normalize_email(address)
                    if email in snap.get('text','').lower() and outreach_email_allowed(email):
                        stats['published_email_candidates'].add((key,email))
                except ValueError:
                    pass
    result=[]
    for name,stats in sorted(sources.items()):
        result.append({**stats,**{k:len(stats[k]) for k in ('website_candidates','failover_candidates','published_email_candidates')}})
    return {'rows':result,'scope':'Latest observation per profile/post and market within the latest 500 platform-signal events',
        'note':'Captured means source text was saved within 30 days. Website matches and published emails are unqualified candidates; index snippets are not email publication proof. Independent failover does not mean platform access was restored.'}


def snapshot(db, lead_id=None):
    now = time.time()
    with db.connect() as con:
        con.execute('BEGIN')
        where = ' WHERE id=?' if lead_id else ''
        args = (lead_id,) if lead_id else ()
        leads = [dict(r) for r in con.execute(
            'SELECT id,company,campaign,country,country_source,status,service,lead_kind,website_status,website,profile_url,source_url,findings '
            ',domain FROM leads' + where + ' ORDER BY id DESC LIMIT 500', args)]
        if lead_id and not leads:
            raise ValueError('Prospect not found')
        result = []
        for lead in leads:
            lid = lead['id']
            crawl = con.execute('SELECT report,created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,)).fetchone()
            cutoff = crawl['created_at'] if crawl else 0
            evidence = [dict(r) for r in con.execute('SELECT id,url,sha256,text,fetched_at FROM evidence WHERE lead_id=? AND fetched_at>=?', (lid, cutoff))]
            fresh = [e for e in evidence if 0 <= now-e['fetched_at'] <= 30*86400]
            from .profiles import source_allowed
            business_fresh=[e for e in fresh if source_allowed(lead,e['url'])]
            by_id = {e['id']: e for e in fresh}
            findings = json.loads(lead.pop('findings'))
            preview_generated = not findings and lead['status'] != 'qualified'
            if preview_generated:
                from .opportunities import proposals
                # Interrupted crawls can preserve useful pages. A read-only
                # preview makes those pages reviewable without claiming the
                # crawl finished, persisting a selection or changing eligibility.
                findings = proposals(lead, business_fresh)
            supported = [f for f in findings if f.get('evidence_id') in by_id and f.get('quote', '').strip()
                         and f['quote'] in by_id[f['evidence_id']]['text'] and f.get('suggestion', '').strip()]
            report = json.loads(crawl['report']) if crawl else {}
            errors = current_errors(report)
            last_error = errors[-1] if errors else {}
            phase = last_error.get('last_stage', report.get('activity', {}).get('stage', ''))
            http_status = next((e['http_status'] for e in reversed(errors) if e.get('http_status')), None)
            contacts = con.execute('SELECT count(*) FROM contacts WHERE lead_id=?', (lid,)).fetchone()[0]
            # No guessed geography: a saved quote on a fresh current page is required.
            country_supported = bool(lead['country'] in {'US', 'UK'} and lead['country_source'].strip()
                                     and any(e['url'] == lead['country_source'] and
                                             any(f.get('country_quote', '').strip() and f['country_quote'] in e['text'] for f in findings)
                                             for e in fresh))
            review_required = lead['status'] != 'qualified' or not country_supported or not supported or not lead['service']
            unknowns = []
            if not country_supported:
                unknowns.append('US/UK location needs an exact current source quote')
            if review_required:
                unknowns.append('Official ownership, active business and relevant buyer need review')
                unknowns.append('Choose one useful offer; conversion uplift is unmeasured')
                if lead['campaign'] == 'B':
                    unknowns.append('Confirm D2C/product ownership and the actual selling or launch process')
            if not supported:
                unknowns.append('No current source-backed opportunity is ready for review')
            if lead['lead_kind'] == 'profile':
                unknowns.append('Website lookup coverage is limited; not found does not mean no website exists')
            result.append({**lead, 'current_pages': len(evidence), 'fresh_pages': len(fresh),
                           'contacts': contacts, 'supported_opportunities': len(supported),
                           'country_supported': country_supported, 'crawl_status': report.get('status', 'not_run'),
                           'crawl_issues': len(errors), 'remaining_urls': report.get('remaining'),
                           'resolved_crawl_issues': len(report.get('errors', []))-len(errors),
                           'retry_pending': len(report.get('checkpoint', {}).get('retry_urls', [])),
                           'sitemap_retry_pending': len(report.get('checkpoint', {}).get('retry_sitemaps', [])),
                           'domain_not_before': report.get('checkpoint', {}).get('domain_not_before', 0),
                           'automation': report.get('automation', {}),
                           'adaptive_delay_seconds': report.get('throttle', {}).get(lead.get('domain', ''), {}).get('delay_seconds'),
                           'crawl_last_stage': phase, 'crawl_http_status': http_status,
                           'first_page_seconds': report.get('first_page_seconds'),
                           'http_document_reuses': sum(bool(p.get('document_reused')) for p in report.get('pages', [])),
                           'retried_requests': len(report.get('retried_requests', [])),
                           'review_required': bool(review_required),
                           'preview_generated': preview_generated,
                           'observations': [{'quote': f['quote'], 'url': by_id[f['evidence_id']]['url'],
                                             'reviewed': not review_required and not f.get('review_required', True)} for f in supported[:3]],
                           'opportunities': [{'suggestion': f['suggestion'], 'service': f.get('service', ''),
                                              'review_required': f.get('review_required', True)} for f in supported[:3]],
                           'unknowns': unknowns,
                           'evidence_links': [{'url': e['url'], 'captured_at': e['fetched_at'], 'sha256': e['sha256']} for e in fresh[:3]]})
        runs = []
        for row in con.execute("SELECT id,kind,detail,created_at FROM events WHERE kind IN ('discovery_started','discovery','discovery_interrupted') ORDER BY id DESC LIMIT 60"):
            detail = json.loads(row['detail'])
            if lead_id and lead_id not in detail.get('lead_ids', []):
                continue
            key = detail.get('run_id')
            # Legacy events cannot reliably be joined; show terminal ones only.
            if not key and row['kind'] == 'discovery_started':
                continue
            if key and any(r['run_id'] == key for r in runs):
                continue
            report = detail.get('report', {})
            runs.append({'run_id': key, 'state': 'interrupted' if row['kind'] == 'discovery_interrupted' else
                         'finished' if row['kind'] == 'discovery' else 'started',
                         'at': row['created_at'], 'query': detail.get('base_query', detail.get('query', '')),
                         'campaign': detail.get('campaign', ''), 'country_hint': detail.get('country_hint', ''),
                         'lead_ids': detail.get('lead_ids', []), 'candidate_domains': detail.get('candidates', 0),
                         'signals': len(report.get('signals', [])), 'skipped': len(report.get('skipped', [])),
                         'errors': report.get('errors', []), 'engine_reports': report.get('engine_reports', []),
                         'error_type': detail.get('error_type', '')})
            if len(runs) == 5:
                break
        coverage=source_coverage(con,lead_id,now)
    qualified = sum(not r['review_required'] for r in result)
    return {'leads': result, 'runs': runs,'source_coverage':coverage, 'scope': 'Selected prospect' if lead_id else 'Latest 500 company records',
            'counts': {'candidates': len(result), 'websites': sum(r['lead_kind'] == 'website' for r in result),
                       'profiles': sum(r['lead_kind'] == 'profile' for r in result),
                       'researched': sum(r['current_pages'] > 0 for r in result),
                       'current_pages': sum(r['current_pages'] for r in result),
                       'stored_contacts': sum(r['contacts'] for r in result),
                       'country_supported': sum(r['country_supported'] for r in result),
                       'supported_opportunities': sum(r['supported_opportunities'] for r in result),
                       'qualified': qualified},
            'note': 'Candidates and saved pages are research outputs. Identity, activity, buyer relevance, geography and one offer require review; email existence is a later verification step.'}
