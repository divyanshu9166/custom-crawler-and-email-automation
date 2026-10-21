"""Automatic profile-first qualification and unsent preparation from current proof."""
import hashlib
import json
import re
import time

from .profiles import canonical_profile, source_allowed
from .research import fresh_evidence


ACTIVITY = re.compile(r'\b(?:services?|consult(?:ing|ation|ant)?|cleaning|plumbing|landscaping|book(?:ing)?|appointments?|products?|handmade|sell|selling|orders?|shop|store|business)\b', re.I)


def evidence_context(db, lead):
    """A real current capture and completed lookup, never an indexed/mirror hint."""
    from .discovery import name_matches, company_title
    if lead.get('website_status') != 'website_not_found':
        raise ValueError('Profile-only preparation needs a completed website lookup without a matched website; ambiguous or unavailable searches stay held')
    crawl = db.one('SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
    if not crawl or not time.time()-30*86400 <= crawl['created_at'] <= time.time()+60:
        raise ValueError('Profile-only business research is missing or stale; refresh research')
    report = json.loads(crawl['report'])
    signal = report.get('signal', {})
    search = signal.get('website_search', {})
    snapshot = signal.get('public_snapshot', {})
    if (signal.get('website') or signal.get('state') != 'no_company_match' or search.get('completed') is not True
            or search.get('errors') or search.get('engine_issues')
            or any(q.get('engine_issues') for q in search.get('queries', []))):
        raise ValueError('Profile-only website lookup is incomplete or ambiguous; no website-absence claim or draft will be inferred')
    if snapshot.get('state') != 'captured' or not source_allowed(lead, snapshot.get('url', '')):
        raise ValueError('Current first-party business-profile capture is unavailable; indexed and community hints cannot qualify a business')
    if snapshot.get('capture_method') not in {'public_html', 'managed_browser_public_profile',
                                             'managed_browser_professional_profile', 'public_professional_http'}:
        raise ValueError('Profile-only automation requires a current first-party capture method')
    title = snapshot.get('name') or company_title(snapshot.get('title', ''))
    if not name_matches(lead['company'], title):
        raise ValueError('Captured profile identity does not match the discovered business; no automatic ownership assumption')
    text = snapshot.get('text', '')
    if snapshot.get('published_email_links'):
        text += '\nPublished mailto links: ' + ', '.join(snapshot['published_email_links'])
    digest = hashlib.sha256(text.encode()).hexdigest()
    page = next((p for p in fresh_evidence(db, lead['id'])
                 if source_allowed(lead, p['url']) and p['sha256'] == digest and p['text'] == text), None)
    if not page or not ACTIVITY.search(page['text']):
        raise ValueError('Profile-only automation needs a current captured business activity statement')
    from .profiles import personal_business_snapshot
    if '/in/' in canonical_profile(lead['profile_url']) and not personal_business_snapshot(snapshot):
        raise ValueError('Personal LinkedIn profile does not establish a current self-employed business; employee profiles are not business prospects')
    return {'crawl_id': crawl['id'], 'page': page, 'search': search,
            'ownership_notes': 'Automatic first-party identity match: the captured profile names '+lead['company']+'. Business activity and source hash are checked; buyer authority is not asserted.',
            'search_notes': 'Automatic bounded website lookup completed without a matched site. This is a search limitation, not confirmation that no website exists.'}


def publication_candidates(db, lead, context):
    """Only explicitly labelled business inboxes in current first-party evidence."""
    from .research import contact_candidates
    page = context['page']
    label = re.compile(r'(?:\bbusiness(?:\s+(?:email|contact|enquiries|inquiries))?|\bsales(?:\s+(?:email|contact))?|\b(?:booking|order)s?(?:\s+(?:email|contact|enquiries|inquiries))?|\b(?:enquiries|inquiries))\s*[:=\-]\s*$', re.I)
    choices = []
    for item in contact_candidates(db, lead['id']):
        if item['source_url'] != page['url'] or item['evidence_sha256'] != page['sha256']:
            continue
        email = item['email']
        if db.one('SELECT 1 FROM suppression WHERE email=? COLLATE NOCASE', (email,)):
            continue
        existing = db.one('SELECT lead_id,status FROM contacts WHERE email=? COLLATE NOCASE', (email,))
        if existing and (existing['lead_id'] != lead['id'] or existing['status'] != 'new'):
            continue
        for match in re.finditer(re.escape(email), page['text'], re.I):
            prefix = page['text'][max(0, match.start()-100):match.start()]
            found = label.search(prefix)
            if found:
                quote = page['text'][match.start()-len(prefix)+found.start():match.end()]
                choices.append({**item, 'publication_quote': quote})
                break
    return sorted(choices, key=lambda c: c['email'])


def qualify_fields(lead, review, context):
    """Machine notes describe actual checks, never impersonate operator approval."""
    page = context['page']
    activity = review.get('profile_activity_quote') or review.get('quote', '')
    if not activity or activity not in page['text'] or not ACTIVITY.search(activity):
        raise ValueError('Profile-only offer needs an exact current business activity/service/product quote')
    allowed = {'website_build', 'chatbot', 'ai_calling_agent'} if lead['campaign'] == 'A' else {'store_launch', 'chatbot'}
    if review['service'] not in allowed:
        raise ValueError('Profile-only prospects need a sourced launch or customer-enquiry offer; website performance cannot be audited without a website')
    review.update(profile_activity_quote=activity, profile_ownership_notes=context['ownership_notes'],
                  website_search_notes=context['search_notes'], website_search_reviewed=True)
    if review['service'] == 'website_build':
        review['website_scope'] = 'website_launch'
    return review


def prepare_profile(db, settings, lead_id, *, cancelled=lambda: False):
    from . import preparation, diagnostics
    from .campaigns import review_lead, create_drafts
    from .research import add_contact
    from .sales import assert_outreach_open
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    pages = preparation._pages(db, lead)
    contacts = db.all('SELECT * FROM contacts WHERE lead_id=? ORDER BY id', (lead_id,))
    frozen = (settings.draft_api_url, settings.draft_api_key, settings.draft_model)
    audit = diagnostics.snapshot(db, lead)
    state = {'lead_id': lead_id, 'input_sha256': preparation.fingerprint(lead, fresh_evidence(db, lead_id), audit),
             'method': 'research_ai_profile', 'review_required': True}

    def unchanged():
        if cancelled():
            raise ValueError('Profile preparation cancelled; no new copy will be saved')
        if (db.one('SELECT * FROM leads WHERE id=?', (lead_id,)) != lead
                or preparation._pages(db, lead) != pages or preparation.source_busy(db, lead_id)
                or db.all('SELECT * FROM contacts WHERE lead_id=? ORDER BY id', (lead_id,)) != contacts
                or frozen != (settings.draft_api_url, settings.draft_api_key, settings.draft_model)):
            raise ValueError('Profile research, contact or settings changed during preparation; newer work preserved')
        with db.connect() as con:
            assert_outreach_open(con, lead_id)

    try:
        if db.get('demo') == 'true':
            raise ValueError('Offline demo cannot prepare live emails')
        if preparation.source_busy(db, lead_id) or lead['status'] in {'new', 'researching', 'research_failed'}:
            raise ValueError('Wait for current business-profile research before preparation')
        if any(c['status'] != 'new' for c in contacts):
            raise ValueError('Existing outreach/contact history requires review; automatic preparation stopped')
        if db.one('SELECT 1 FROM messages m JOIN contacts c ON c.id=m.contact_id WHERE c.lead_id=?', (lead_id,)):
            db.event('preparation', {**state, 'state': 'preserved', 'reason': 'Existing drafts/messages preserved; review or regenerate explicitly'})
            return
        unchanged()
        context = evidence_context(db, lead)
        choices = publication_candidates(db, lead, context)
        if not choices:
            raise ValueError('No current explicitly published business inbox on this profile; contact is missing, ambiguous, shared or suppressed. No address will be guessed')
        discovery = db.one("SELECT detail FROM events WHERE (kind='prospect_signal' AND json_extract(detail,'$.lead_id')=?) OR (kind='discovery' AND EXISTS(SELECT 1 FROM json_each(events.detail,'$.lead_ids') WHERE value=?)) ORDER BY id DESC LIMIT 1", (lead_id, lead_id))
        target_query = json.loads(discovery['detail']).get('query', '') if discovery else ''
        assessment = preparation._assessment(settings, lead, pages, unchanged,
                                              target_query=target_query,
                                              audit_context={'profile_context': {'website_lookup': context['search_notes'],
                                                                               'business_identity': context['ownership_notes']}})
        unchanged()
        if not assessment['ready']:
            reason = str(assessment.get('reason') or 'Current profile does not support a relevant country/business/offer assessment')[:500]
            db.event('preparation', {**state, 'state': 'needs_evidence', 'reason': reason})
            return
        review = preparation._validate_review(lead, assessment, pages)
        review = qualify_fields(lead, review, context)
        unchanged()
        review_lead(db, lead_id, review, expected_lead=lead, expected_contacts=contacts, review_method='research_ai_profile')
        # These imports run the same source/hash, unique-inbox, suppression and
        # history gates as manual imports. They never approve or verify a mailbox.
        current = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
        context = evidence_context(db, current)
        choices = publication_candidates(db, current, context)
        if not choices:
            raise ValueError('Published business contact changed during profile preparation; no draft saved')
        candidate = choices[0]
        cid = add_contact(db, lead_id, candidate['email'], candidate['source_url'],
                          ownership_notes='Automatic first-party business publication: '+candidate['publication_quote']+'. Final recipient relevance remains unapproved.',
                          review_method='source_automation')
        create_drafts(db, settings, cid, cancelled=cancelled, preserve_existing=True)
        db.event('preparation', {**state, 'state': 'drafts_ready', 'reason': 'Profile business, country, activity and published inbox checked. One initial email is ready for recipient/message review.',
                                 'contact_id': cid, 'service': review['service'], 'source_ids': [p['id'] for p in pages]})
    except ValueError as exc:
        db.event('preparation', {**state, 'state': 'needs_attention', 'reason': str(exc)[:500]})
        raise
