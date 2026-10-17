"""Save attributable social posts locally and expose them for explicit trigger review."""
import hashlib
import json
import time

from . import source_status
from .web import normalize_email, EMAIL_RE, outreach_email_allowed
import re


def eligible_lead(db, lead_id):
    from .contact_recovery import eligible_lead as website_lead
    from .research import fresh_evidence
    from .profiles import source_allowed
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead or lead.get('lead_kind') != 'profile':
        return website_lead(db, lead_id)
    if db.one("SELECT 1 FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)):
        raise ValueError('Existing outreach history: preserve research')
    if not any(source_allowed(lead, p['url']) for p in fresh_evidence(db, lead_id)):
        raise ValueError('Capture current business-profile evidence before post research')
    return lead


async def research_known_posts(db, settings, lead_id):
    from .research import fresh_evidence
    from .profiles import canonical_profile
    lead = eligible_lead(db, lead_id)
    hints = [{'url': lead.get('profile_url') or lead['source_url'], 'origin': 'prospect_source'}]
    pages = {p['url']: p for p in fresh_evidence(db, lead_id)}
    crawl = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead_id,))
    for page in json.loads(crawl['report']).get('pages', []) if crawl else []:
        saved = pages.get(page.get('url'))
        if not saved or saved['sha256'] != page.get('sha256'):
            continue
        for link in page.get('business_profile_links', page.get('links', []))[:500]:
            try:
                hints.append({'url': canonical_profile(link), 'origin': 'captured_official_navigation',
                              'source_url': saved['url'], 'company_sha256': saved['sha256']})
            except ValueError:
                pass
    professional = db.one("SELECT detail FROM events WHERE kind='professional_research' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (lead_id,))
    if professional:
        report = json.loads(professional['detail'])
        if time.time()-30*86400 <= report.get('finished_at', 0) <= time.time()+60:
            hints.extend(report.get('other_public_profile_hints', [])[:20])
    return await research_posts(db, settings, lead_id, hints)


async def research_posts(db, settings, lead_id, hints):
    from .social_browser import browser_recent_posts, post_profile
    if not settings.social_posts_enabled or not settings.platform_browser_enabled:
        return {'state': 'disabled', 'captures': []}
    targets = {}
    for hint in hints:
        try:
            platform, profile, _ = post_profile(hint['url'])
            targets.setdefault(profile, (platform, hint))
        except (ValueError, KeyError):
            pass
    captures = []
    for profile, (platform, hint) in list(targets.items())[:settings.social_posts_max_profiles]:
        eligible_lead(db, lead_id)
        started = time.monotonic()
        value = await browser_recent_posts(settings, profile)
        eligible_lead(db, lead_id)
        value.update(lead_id=lead_id, source_hint=hint)
        if value.get('state') != 'captured':
            value['posts'] = []
        candidates = set()
        for post in value.get('posts', []):
            text = post['text']
            digest = hashlib.sha256(text.encode()).hexdigest()
            post.update(sha256=digest, observed_at=time.time())
            # This is background/trigger evidence, never a business-identity,
            # country, contact ownership or mailbox-verification shortcut.
            db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) '
                       'ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at',
                       (lead_id, post['url'], 'Social post: ' + profile, text, digest, time.time()))
            db.event('social_post_capture', {'lead_id': lead_id, **post, 'source_hint': hint})
            for email in re.findall(EMAIL_RE, text):
                try:
                    address = normalize_email(email)
                    if outreach_email_allowed(address):
                        candidates.add(address)
                except ValueError:
                    pass
        db.event('social_capture', value)
        source_status.record(db, 'managed_browser:' + platform, 'recent_posts', profile, value,
                             lead_id=lead_id, elapsed=time.monotonic()-started, contacts=len(candidates))
        captures.append(value)
    report = {'lead_id': lead_id,
              'state': 'captured' if any(v.get('posts') for v in captures) else 'unavailable' if targets else 'no_known_profiles',
              'captures': captures}
    db.event('social_research', report)
    return report


def is_social_evidence(db, lead_id, page):
    from .web import domain_of
    if domain_of(page['url']) not in {'linkedin.com', 'x.com', 'twitter.com'}:
        return False
    row = db.one("SELECT detail FROM events WHERE kind='social_post_capture' AND json_extract(detail,'$.lead_id')=? "
                 "AND json_extract(detail,'$.url')=? ORDER BY id DESC LIMIT 1", (lead_id, page['url']))
    if not row:
        return False
    value = json.loads(row['detail'])
    return bool(value.get('sha256') == page['sha256'] == hashlib.sha256(page['text'].encode()).hexdigest()
                and time.time()-30*86400 <= value.get('observed_at', 0) <= time.time()+60)


def latest(db, lead_id):
    rows = db.all("SELECT detail FROM events WHERE kind='social_capture' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 20", (lead_id,))
    seen, result = set(), []
    for row in rows:
        value = json.loads(row['detail'])
        if value['profile_url'] in seen:
            continue
        seen.add(value['profile_url'])
        value['fresh'] = time.time()-30*86400 <= value['observed_at'] <= time.time()+60
        result.append(value)
    return result
