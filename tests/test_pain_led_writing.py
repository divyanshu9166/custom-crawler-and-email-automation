"""Pain-led initial emails: verified stakes, plain wording and the same truth validators."""
import json

import pytest

from outreach import diagnostics, email_writer, journey
from outreach.stakes import colour, page_label, short_name

# Capture the real writer before conftest installs controlled workflow copy.
REAL_GENERATE = email_writer.generate_sequence
URL = 'https://bright-demo.com/'
KINDS = ['font_timing', 'blocking_timing', 'broken_cta', 'text_contrast', 'form_labels', 'page_overflow']


def image(lid):
    return f'lead-{lid}-1792410725-123abc-mobile.png'


def sample(**patch):
    return {'ready': True, 'styles_ready': True, 'url': URL, 'width': 390, 'scroll_width': 390,
            'controls': [], 'ctas': [], **patch}


def ratio(fg, bg):
    def luminance(color):
        return sum((v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)*w
                   for v, w in zip([c/255 for c in color], (.2126, .7152, .0722)))
    a, b = luminance(fg), luminance(bg)
    return (max(a, b)+.05)/(min(a, b)+.05)


def record(db, lid, kind):
    if kind.endswith('_timing'):
        flag = 'font-display-insight' if kind == 'font_timing' else 'render-blocking-insight'
        db.event('performance', {'lead_id': lid, 'url': URL, 'status': 'complete', 'strategies': {'mobile': {
            'score': 41, 'final_url': URL, 'opportunities': [{'id': flag}],
            'metrics': {'largest-contentful-paint': {'numericValue': 13100, 'numericUnit': 'millisecond'}}}}})
        return
    links = []
    if kind == 'broken_cta':
        capture = journey.capture(sample(), sample(), 'mobile', image(lid))
        links = [{'state': 'confirmed_http_error', 'source_url': URL, 'device': 'mobile', 'screenshot': image(lid),
                  'finding': {'code': 'broken_cta', 'anchor': '404', 'target_url': URL+'quote/', 'selector': '#quote',
                              'label': 'Get a quote', 'http_statuses': [404, 404],
                              'fact': 'The "Get a quote" link returned HTTP 404 in two public GET checks.'}}]
    elif kind == 'form_labels':
        controls = [{'selector': '#email', 'hint': 'Email', 'type': 'email'}, {'selector': '#phone', 'hint': 'Phone', 'type': 'tel'}]
        capture = journey.capture(sample(controls=controls), sample(controls=controls), 'mobile', image(lid))
    elif kind == 'page_overflow':
        capture = journey.capture(sample(scroll_width=620), sample(scroll_width=620), 'mobile', image(lid))
    else:
        fg, bg = [255, 255, 255], [68, 197, 148]
        proof = {'selector': '#service', 'text': 'Commercial cleaning services for offices nationwide.',
                 'foreground': fg, 'background': bg, 'font_size': 16, 'font_weight': 400,
                 'ratio': ratio(fg, bg), 'minimum': 4.5}
        capture = journey.capture(sample(contrast=[proof]), sample(contrast=[proof]), 'mobile', image(lid))
    db.event('screenshot', {'lead_id': lid, 'url': URL, 'complete': False,
                            'journey': {'version': 1, 'state': 'checked', 'captures': [capture], 'links': links}})


def packet_for(db, prepared, kind):
    lid = prepared['lead_id']
    record(db, lid, kind)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    audit = diagnostics.snapshot(db, lead)
    finding = json.loads(lead['findings'])[0]
    evidence = db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    return lead, audit, finding, evidence, email_writer.research_packet(lead, finding, evidence, audit_context=audit)


def email_from(brief, prepared):
    """What a model following the brief literally would write."""
    body = (f"{brief['hook']}\n\n{brief['why_it_matters']} {brief['risk_line']}".rstrip()
            + f"\n\nWe can {brief['plain_fix']}. {brief['effort']}".rstrip()
            + '\n\nWant me to send over the exact changes?')
    return {'messages': [{'step': 0, 'subject': brief['subject_ideas'][0], 'body': body,
                          'diagnostic_refs': [brief['diagnostic_ref']],
                          'support': [{'evidence_id': prepared['evidence_id'], 'quote': 'Contact us for a consultation.'}]}]}


@pytest.mark.parametrize('kind', KINDS)
def test_brief_gives_plain_hook_verified_stakes_and_passes_every_truth_check(db, prepared, kind):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, kind)
    brief = packet['pitch_brief']
    assert brief['diagnostic_ref'] == audit['conclusion']['findings'][0]['ref']
    assert 'Bright Demo' in brief['hook'] and brief['why_it_matters'] and brief['plain_fix']
    expected = {'font_timing': ('13.1 seconds', '2.5 seconds', 'font'), 'blocking_timing': ('13.1 seconds', '4 seconds', 'scripts'),
                'broken_cta': ('404', 'dead end', 'repair'), 'text_contrast': ('2.', '4.5:1', 'darken'),
                'form_labels': ('2 fields', 'WCAG', 'labels'), 'page_overflow': ('390', 'off-screen', 'fits')}[kind]
    text = ' '.join([brief['hook'], brief['why_it_matters'], brief['plain_fix']])
    assert all(fragment in text for fragment in expected)
    for word in ('render-blocking', 'contentful', 'DOM', 'viewport', 'selector', 'losing', 'lost'):
        assert word not in text
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    messages = email_writer.validate_output(email_from(brief, prepared), lead, contact, evidence,
                                            audit_context=audit, finding=finding)
    assert messages[0]['body'].startswith('Hi Alex,\n\nIn Google' if kind.endswith('_timing') else 'Hi Alex,\n\nWhen I checked')
    assert len(messages[0]['body'].split()) < 130


def test_brief_is_only_for_measured_improvement_pitches(db, prepared):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'broken_cta')
    assert packet['pitch_brief']
    chatbot = {**lead, 'service': 'chatbot'}
    assert email_writer.research_packet(chatbot, {**finding, 'service': 'chatbot'}, evidence, audit_context=audit)['pitch_brief'] == {}
    assert email_writer.research_packet(lead, finding, evidence, audit_context={})['pitch_brief'] == {}


@pytest.mark.parametrize('subject,body,message', [
    ('Bright Demo - mobile loading observation and proposed website work', None, 'subject'),
    (None, "I came across Bright Demo's website. ", 'open with'),
    (None, 'Bright Demo has render-blocking resources. ', 'jargon'),
    (None, 'Treat this as a test rather than a confirmed need. ', 'hedging'),
    (None, 'Sites like Bright Demo lose 53% of mobile visitors. ', 'percentages'),
])
def test_report_style_jargon_hedges_and_invented_statistics_are_rejected(db, prepared, subject, body, message):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'font_timing')
    output = email_from(packet['pitch_brief'], prepared)
    if subject:
        output['messages'][0]['subject'] = subject
    if body:
        output['messages'][0]['body'] = body + output['messages'][0]['body']
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    with pytest.raises(ValueError, match='Writing quality') as error:
        email_writer.validate_output(output, lead, contact, evidence, audit_context=audit, finding=finding)
    assert message in str(error.value)


def test_supplied_percentage_from_the_source_is_allowed(db, prepared):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'font_timing')
    db.execute('UPDATE evidence SET text=text||? WHERE id=?', (' Rated 98% by our clients.', prepared['evidence_id']))
    evidence = db.all('SELECT * FROM evidence WHERE lead_id=?', (lead['id'],))
    output = email_from(packet['pitch_brief'], prepared)
    output['messages'][0]['body'] = 'Your clients rate you 98%. ' + output['messages'][0]['body']
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    assert email_writer.validate_output(output, lead, contact, evidence, audit_context=audit, finding=finding)


def test_prompt_orders_hook_stakes_fix_question_and_keeps_truth_rules():
    prompt = ' '.join((email_writer.SINGLE_INSTRUCTIONS + email_writer.WEBSITE_INSTRUCTIONS).split())
    order = [prompt.index(part) for part in ('1. Hook', '2. Why it matters', '3. The fix', '4. ONE easy yes/no question')]
    assert order == sorted(order)
    for rule in ('Never claim they ARE losing', 'never use statistics or percentages that were not supplied',
                 'bounded profile/search check', 'diagnostic_refs MUST be []', 'ONLY WhatsApp offer'):
        assert rule in prompt


@pytest.mark.parametrize('name,expected', [
    ('Spotless Commercial Cleaning Ltd', 'Spotless Commercial Cleaning'),
    ('Office Cleaning London – Expert Commercial Cleaners', 'Office Cleaning London'),
    ('Bright Studio | Design Agency', 'Bright Studio'),
    ('Acme Plumbing, LLC', 'Acme Plumbing'),
    ('B&Q', 'B&Q'),
])
def test_short_name_drops_legal_suffixes_and_seo_taglines(name, expected):
    assert short_name(name) == expected


def test_page_labels_and_colour_names_stay_plain():
    assert page_label('https://x.co.uk/') == 'homepage'
    assert page_label('https://x.co.uk/services/office-cleaning/') == 'office cleaning page'
    assert page_label('https://x.co.uk/contact-page') == 'contact page'
    assert page_label('https://x.co.uk/p/12345') == 'page'
    assert colour([47, 163, 151]) == 'teal' and colour([255, 255, 255]) == 'white'
    assert colour([68, 197, 148]) == 'teal' and colour([225, 210, 180]) == 'beige' and colour([20, 30, 90]) == 'dark blue'
    assert colour([150, 60, 200]) == 'purple' and colour([240, 240, 240]) == 'white'


@pytest.mark.parametrize('quote,saved', [
    ('Contact us for a consultation.', 'Contact us for a consultation.'),
    ('“contact us for a  consultation”', 'Contact us for a consultation'),
    ('We offer UK consulting services...', 'We offer UK consulting services'),
    ('We lose customers because the booking process fails.', None),
])
def test_support_quotes_match_page_text_despite_quote_marks_spacing_and_ellipses(db, prepared, quote, saved):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'broken_cta')
    output = email_from(packet['pitch_brief'], prepared)
    output['messages'][0]['support'] = [{'evidence_id': prepared['evidence_id'], 'quote': quote}]
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    if saved is None:
        with pytest.raises(ValueError, match='invented or unavailable source quote'):
            email_writer.validate_output(output, lead, contact, evidence, audit_context=audit, finding=finding)
        return
    message = email_writer.validate_output(output, lead, contact, evidence, audit_context=audit, finding=finding)[0]
    assert message['support'][0]['quote'] == saved
    assert saved in next(e['text'] for e in evidence if e['id'] == prepared['evidence_id'])


def test_one_invented_quote_is_dropped_when_a_genuine_quote_remains(db, prepared):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'broken_cta')
    output = email_from(packet['pitch_brief'], prepared)
    output['messages'][0]['support'] = [{'evidence_id': prepared['evidence_id'], 'quote': 'An invented customer complaint here.'},
                                        {'evidence_id': prepared['evidence_id'], 'quote': 'Contact us for a consultation.'}]
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    message = email_writer.validate_output(output, lead, contact, evidence, audit_context=audit, finding=finding)[0]
    assert [s['quote'] for s in message['support']] == ['Contact us for a consultation.']


def test_retry_after_a_bad_quote_offers_the_verified_finding_quote(db, prepared, settings, monkeypatch):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'broken_cta')
    good = email_from(packet['pitch_brief'], prepared)
    bad = json.loads(json.dumps(good))
    bad['messages'][0]['support'] = [{'evidence_id': prepared['evidence_id'], 'quote': 'Nothing like this is on the page.'}]
    settings.followups_enabled, settings.draft_api_key, settings.draft_model = False, 'fixture-key', 'fixture-model'
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    sent = []
    def chat(_settings, instructions, encoded, **kwargs):
        sent.append((instructions, json.loads(encoded)))
        return json.dumps([bad, good][len(sent)-1])
    monkeypatch.setattr(email_writer, 'chat', chat)
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    email_writer.generate_sequence(settings, lead, contact, finding, evidence, audit_context=audit)
    assert 'character for character' in sent[0][0]
    assert sent[1][1]['validation_feedback']['verified_support_quotes'] == [
        {'evidence_id': prepared['evidence_id'], 'quote': 'Contact us for a consultation.'}]
