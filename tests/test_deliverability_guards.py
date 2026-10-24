"""Domain DNS readiness, our own quoted text in replies, and the automatic-approval injection guard."""
import dns.resolver
import pytest
from fastapi.testclient import TestClient

from outreach import deliverability, guard
from outreach.app import create_app
from outreach.campaign_manager import bulk
from outreach.mail import FOOTER_NOTICE, record_inbound, without_our_text
from test_campaigns_mail import inbound

DKIM = 'v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA'


class Answer:
    def __init__(self, text):
        self.text = text

    def to_text(self):
        return self.text


class FakeResolver:
    """Public DNS stand-in: {(name, type): [record text] | exception class}."""
    def __init__(self, records):
        self.records, self.lifetime = records, None

    def resolve(self, name, kind):
        value = self.records.get((name, kind))
        if value is None:
            raise dns.resolver.NXDOMAIN()
        if isinstance(value, type):
            raise value()
        return [Answer(v) for v in value]


def healthy(**changes):
    records = {('acme.com', 'TXT'): ['"v=spf1 include:_spf.google.com ~all"'],
               ('google._domainkey.acme.com', 'TXT'): [f'"{DKIM[:40]}" "{DKIM[40:]}"'],
               ('_dmarc.acme.com', 'TXT'): ['"v=DMARC1; p=quarantine; rua=mailto:d@acme.com"'],
               ('acme.com', 'MX'): ['1 smtp.google.com.']}
    records.update(changes)
    return FakeResolver({k: v for k, v in records.items() if v != 'drop'})


def test_ready_domain_passes_every_check():
    result = deliverability.check('acme.com', resolver=healthy())
    assert result['ready'] and not result['issues']
    assert result['dkim']['selectors'] == ['google'] and result['dmarc']['policy'] == 'quarantine'
    assert result['mx']['hosts'] == ['smtp.google.com'] and {b['state'] for b in result['blocklists']} == {'clean'}


@pytest.mark.parametrize('changes,issue', [
    ({('acme.com', 'TXT'): 'drop'}, 'No SPF record'),
    ({('acme.com', 'TXT'): ['"v=spf1 include:a.com ~all"', '"v=spf1 mx -all"']}, 'More than one SPF'),
    ({('acme.com', 'TXT'): ['"v=spf1 +all"']}, 'lets anyone send'),
    ({('acme.com', 'TXT'): ['"v=spf1 -all"']}, 'authorises no sending servers'),
    ({('google._domainkey.acme.com', 'TXT'): ['"v=DKIM1; k=rsa; p="']}, 'No DKIM key'),
    ({('_dmarc.acme.com', 'TXT'): 'drop'}, 'No DMARC record'),
    ({('acme.com', 'MX'): ['0 .']}, 'No MX record'),
    ({('acme.com.dbl.spamhaus.org', 'A'): ['127.0.1.2']}, 'listed on Spamhaus DBL'),
    ({('acme.com', 'MX'): dns.resolver.LifetimeTimeout}, 'MX lookup failed'),
])
def test_each_dns_problem_is_named_and_blocks_ready(changes, issue):
    result = deliverability.check('acme.com', resolver=healthy_with(changes))
    assert not result['ready'] and any(issue in i for i in result['issues'])


def healthy_with(changes):
    resolver = healthy()
    for key, value in changes.items():
        if value == 'drop':
            resolver.records.pop(key, None)
        else:
            resolver.records[key] = value
    return resolver


def test_refused_blocklist_query_is_unknown_not_listed_and_custom_selector_is_tried():
    resolver = healthy_with({('acme.com.dbl.spamhaus.org', 'A'): ['127.255.255.254'], ('google._domainkey.acme.com', 'TXT'): 'drop',
                             ('s2024._domainkey.acme.com', 'TXT'): [f'"{DKIM}"']})
    result = deliverability.check('acme.com', ['s2024'], resolver=resolver)
    assert result['ready'] and result['dkim']['selectors'] == ['s2024']
    assert next(b for b in result['blocklists'] if b['list'] == 'Spamhaus DBL')['state'] == 'unknown'
    with pytest.raises(ValueError, match='valid sending domain'):
        deliverability.check('not a domain', resolver=resolver)


def test_dns_check_endpoint_saves_and_shows_the_result(settings, monkeypatch):
    real = deliverability.check
    monkeypatch.setattr(deliverability, 'check', lambda domain, selectors=(): {**real('acme.com', resolver=healthy()), 'domain': domain})
    client = TestClient(create_app(settings))
    headers = {'Authorization': 'Bearer ' + settings.api_token}
    assert client.post('/api/deliverability/check', json={'domain': 'acme.com'}).status_code == 401
    assert client.post('/api/deliverability/check', json={'domain': 'acme.com'}, headers=headers).json()['ready']
    client.post('/api/deliverability/check', json={'domain': 'sender.example.com'}, headers=headers)
    domains = client.get('/api/delivery', headers=headers).json()['domains']
    assert next(d for d in domains if d['domain'] == 'sender.example.com')['dns_check']['ready']


def test_quoted_footer_without_markers_is_not_an_opt_out(db, active):
    cut = FOOTER_NOTICE.rindex(' ', 0, 60)  # Mail clients wrap at spaces, without quote markers.
    reply = ('Thanks, this is interesting. Can you send the fix?\n\n' + FOOTER_NOTICE[:cut] + '\n' + FOOTER_NOTICE[cut + 1:]
             + ' https://outreach.example.com/unsubscribe/x')
    raw = inbound(db, reply)
    record_inbound(db, raw, 'quoted-footer')
    contact = db.one('SELECT status,delivery_state FROM contacts WHERE id=?', (active['contact_id'],))
    assert contact == {'status': 'replied', 'delivery_state': 'REPLIED'}
    assert not db.one('SELECT 1 FROM suppression')


def test_own_short_opt_out_still_counts_beside_our_quoted_email(db, active):
    body = db.one('SELECT body FROM messages WHERE step=0')['body']
    record_inbound(db, inbound(db, 'unsubscribe\n\n' + body), 'real-opt-out')
    assert db.one('SELECT 1 FROM suppression')


def test_without_our_text_keeps_their_words():
    ours = ['In our test the main content of your homepage took 13.1 seconds to appear on a phone.', FOOTER_NOTICE]
    assert without_our_text('Please remove me.\nIn our test the main content of your homepage took 13.1 seconds', ours) == 'Please remove me.'
    assert without_our_text('remove me', ours) == 'remove me'


@pytest.mark.parametrize('text,held', [
    ('Your bright-demo.com homepage works with Node.js; contrast 4.5:1, e.g. on mobile.', False),
    ('Read the guide at helpful-tools.net/fix first.', True),
    ('Email the details to agent@outside.io', True),
    ('Book through quickcal dot io today', True),
])
def test_guard_flags_outside_domains_only(settings, text, held):
    reasons = guard.review(settings, {'website': 'https://bright-demo.com', 'domain': 'bright-demo.com'},
                           {'email': 'alex@bright-demo.com'}, [{'subject': 'Idea', 'body': text}])
    assert bool(reasons) is held


def test_bulk_approval_holds_injected_drafts_for_manual_review(db, settings, prepared):
    from outreach.email_writer import COPY_INSTRUCTIONS
    db.execute("UPDATE messages SET body=body||? WHERE contact_id=? AND step=0", (' Visit promo-deals.com now.', prepared['contact_id']))
    result = bulk(db, settings, [prepared['lead_id']], 'approve')
    assert result['succeeded'] == 0 and 'Held for manual review' in result['results'][0]['reason']
    assert db.one("SELECT 1 FROM events WHERE kind='approval_held'")
    assert db.one('SELECT status FROM contacts')['status'] == 'new'
    leak = ' '.join(COPY_INSTRUCTIONS.split()[20:36])
    assert guard.copies_instructions('As requested: ' + leak)
