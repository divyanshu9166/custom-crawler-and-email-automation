"""Operator-observed business links are research hints, never fetched evidence."""
import hashlib
import json
import math
import time
from urllib.parse import urlsplit, urlunsplit

from .discovery import official_root, platform_of
from .profiles import canonical_profile
from .web import crawl_url, company_crawl_url, domain_of


def save_reference(db, *, company, source_url, website, campaign, country_hint,
                   observed_at, observation, public_business_confirmed,
                   capture_method='operator_browser_reference'):
    now = time.time()
    if public_business_confirmed is not True:
        raise ValueError('Confirm that this is visible public business information')
    if capture_method not in {'operator_browser_reference', 'browser_connector_reference'}:
        raise ValueError('Unsupported browser reference method')
    if (not math.isfinite(observed_at) or not now-30*86400 <= observed_at <= now+60):
        raise ValueError('Use the actual observation time within the last 30 days')
    company, observation = company.strip(), observation.strip()
    if not 2 <= len(company) <= 200 or not 8 <= len(observation) <= 300:
        raise ValueError('Provide a business name and a short factual observation')
    if campaign not in {'A', 'B'} or country_hint not in {'US', 'UK'}:
        raise ValueError('Use Campaign A/B and market US/UK')
    source_url = crawl_url(source_url)
    parts = urlsplit(source_url)
    if parts.query:
        raise ValueError('Use the public profile URL without query parameters')
    # Keep the exact About source in history; validate its company profile root.
    profile_source = source_url
    if platform_of(source_url) == 'linkedin.com' and parts.path.startswith('/in/'):
        # This form saves an unverified company-link hint, without a profile
        # capture. Personal business identities need the profile research path.
        raise ValueError('Use profile research to establish a personal business identity before linking its website')
    if platform_of(source_url) == 'linkedin.com' and parts.path.rstrip('/').endswith('/about'):
        profile_source = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/')[:-6], '', ''))
    canonical_profile(profile_source)
    website = crawl_url(website)
    root = official_root(website)
    seed = company_crawl_url(website, domain_of(root))
    if not seed:
        raise ValueError('Use a public company page, not an account or checkout path')
    detail = {'company': company, 'source_url': source_url, 'website_candidate': seed,
              'campaign': campaign, 'country_hint': country_hint, 'observed_at': observed_at,
              'observation': observation, 'method': capture_method,
              'identity_verified': False, 'server_profile_fetched': False,
              'contact_publication_proof': False, 'review_required': True}
    key = hashlib.sha256(json.dumps(detail, sort_keys=True).encode()).hexdigest()
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('''INSERT OR IGNORE INTO leads(domain,website,company,campaign,source_url,
            research_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
                    (domain_of(root), root, company, campaign, source_url,
                     f'Browser-observed website candidate. Market hint: {country_hint}; identity and country need review.', now, now))
        lead = con.execute('SELECT id,status FROM leads WHERE domain=?', (domain_of(root),)).fetchone()
        lid = lead['id']
        detail['lead_id'] = lid
        con.execute('INSERT OR IGNORE INTO events(kind,detail,external_id,created_at) VALUES(?,?,?,?)',
                    ('browser_business_reference', json.dumps(detail), 'browser-reference:'+key, now))
        job = con.execute("SELECT id FROM jobs WHERE kind='research' AND state IN ('pending','running') AND json_extract(payload,'$.lead_id')=?", (lid,)).fetchone()
        job_id = job['id'] if job else None
        # Preserve existing research/reviews/outreach. Repeated imports cannot
        # invalidate them or silently queue a recrawl.
        if (not job and lead['status'] == 'new'
                and not con.execute('SELECT 1 FROM crawls WHERE lead_id=?', (lid,)).fetchone()
                and not con.execute('SELECT 1 FROM contacts WHERE lead_id=?', (lid,)).fetchone()):
            job_id = con.execute('INSERT INTO jobs(kind,payload,due_at,created_at) VALUES(?,?,?,?)',
                                 ('research', json.dumps({'lead_id': lid, 'seed_urls': [seed]}, sort_keys=True), now, now)).lastrowid
    return {'id': lid, 'job_id': job_id, 'state': 'reference_saved',
            'server_profile_fetched': False, 'review_required': True}
