"""Bind approved copy and recipient to current evidence in the same transaction."""
import hashlib
import json

from .offers import selected_offer
from .research import fresh_evidence
from .web import crawl_url


class Reader:
    def __init__(self, con):
        self.con = con

    def all(self, sql, args=()):
        return [dict(r) for r in self.con.execute(sql, args)]

    def one(self, sql, args=()):
        row = self.con.execute(sql, args).fetchone()
        return dict(row) if row else None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def capture(con, settings, lead, contact):
    from .email_writer import assert_ai_origin
    assert_ai_origin(Reader(con), contact['id'])
    from .research import assert_contact_ownership
    reader = Reader(con)
    assert_contact_ownership(reader, contact, lead)
    if lead['country'] not in {'US', 'UK'} or not selected_offer(reader, lead):
        raise ValueError('Review the current country, source evidence and selected offer again')
    finding = json.loads(lead['findings'])[0]
    pages = {p['id']: p for p in fresh_evidence(reader, lead['id'])}
    ids = {finding['evidence_id']}
    country_page = next(p for p in pages.values() if crawl_url(p['url']) == crawl_url(lead['country_source']))
    ids.add(country_page['id'])
    recipient_source = next((p for p in pages.values() if crawl_url(p['url']) == crawl_url(contact['source_url'])), None)
    if not recipient_source:
        raise ValueError('Review current saved publication evidence for this recipient')
    ids.add(recipient_source['id'])
    commerce = finding.get('offer_context', {}).get('commerce_evidence_id')
    if commerce:
        ids.add(commerce)
    for key in ('trigger', 'followup'):
        point = finding.get(key)
        if point:
            page = pages.get(point.get('evidence_id'))
            if not page or not point.get('quote') or point['quote'] not in page['text']:
                raise ValueError('Review current optional trigger/follow-up source evidence again')
            ids.add(page['id'])
    messages = reader.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact['id'],))
    if [m['step'] for m in messages] != list(range(4 if settings.followups_enabled else 1)):
        raise ValueError('Review the initial email; legacy follow-ups must be archived in single-email mode')
    return {
        'lead': {k: lead[k] for k in ('id', 'company', 'campaign', 'country', 'country_source', 'timezone',
                                    'business_type', 'service', 'findings', 'fit_notes')},
        'recipient': {k: contact[k] for k in ('id', 'email', 'name', 'role', 'source_url')},
        'sender': {k: getattr(settings, k) for k in ('sender_name', 'sender_company', 'sender_email',
                                                 'sender_website', 'postal_address', 'public_url')},
        'sources': [{'id': eid, 'url': crawl_url(pages[eid]['url']), 'sha256': pages[eid]['sha256'], 'text_digest': digest(pages[eid]['text'])}
                    for eid in sorted(ids)],
        'messages_digest': digest([{k: m[k] for k in ('id', 'step', 'subject', 'body', 'evidence_ids', 'message_id')}
                                   for m in messages]),
    }


def assert_approved(con, settings, lead, contact):
    event = con.execute("SELECT detail FROM events WHERE kind='sequence_approved' AND contact_id=? ORDER BY id DESC LIMIT 1",
                        (contact['id'],)).fetchone()
    saved = json.loads(event[0]).get('review_snapshot') if event else None
    if not saved or saved != capture(con, settings, lead, contact):
        raise ValueError('Approved sequence context or sources changed; review before further outreach')
