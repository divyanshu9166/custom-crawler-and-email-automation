"""Model-independent copywriting playbook: plans, scoring and the one-rewrite quality bar."""
import json

import pytest

from outreach import copywriting, email_writer
from outreach.campaigns import CAMPAIGN_SERVICES
from tests.test_pain_led_writing import email_from, packet_for

# Capture the real writer before conftest installs controlled workflow copy.
REAL_GENERATE = email_writer.generate_sequence

OLD_SPOTLESS = ('Spotless Commercial Cleaning Ltd – mobile loading observation and proposed website work',
    'A recent mobile lab test on your site showed the largest visible content appearing at 13.1 seconds, with font '
    'display and render-blocking resources flagged. We can adjust the font-loading behaviour so text appears sooner '
    'while keeping icons working, and defer non-critical CSS/scripts so the service information and the existing Get '
    'a Quote route become visible earlier. We would preserve your current EnquiryBot throughout. As an optional '
    'addition, an AI calling agent could handle a narrow set of approved helpdesk questions and transfer anything '
    'sensitive to your team. Would a short walk-through of the finding and the proposed fixes be useful?')
NEW_SPOTLESS = ('Spotless on mobile: 13.1 seconds',
    "In Google's PageSpeed test on mobile, the main content of the Spotless homepage took 13.1 seconds to appear.\n\n"
    "Google's guideline is 2.5 seconds or less, and it rates anything over 4 seconds as poor. That's a long blank "
    'screen for anyone opening the site on a phone.\n\n'
    'We can change how your fonts load, so your text and services appear straight away. '
    "It's a loading change, not a redesign.\n\nWant me to send over the exact changes?")
WEAK = ("In Google's PageSpeed test on mobile, the main content of the Bright Demo homepage took 13.1 seconds to "
        'appear, and we think we can change how the fonts load so that the text appears sooner, and our team would '
        'handle it and we would check it afterwards with our process and our tools. Would that be useful?')


def test_real_report_style_draft_scores_well_below_the_playbook_version():
    old, new = copywriting.score(*OLD_SPOTLESS, 'website_improvement'), copywriting.score(*NEW_SPOTLESS, 'website_improvement')
    assert new['score'] == 100 and old['score'] <= 70
    assert {'readability', 'paragraphs', 'subject', 'one_offer'} <= {i['check'] for i in old['improve']}


@pytest.mark.parametrize('subject,body,check', [
    ('Spotless on mobile', WEAK, 'hero'),
    ('Spotless on mobile', WEAK, 'readability'),
    ('Spotless on mobile', WEAK, 'paragraphs'),
    ('Spotless on mobile', NEW_SPOTLESS[1].replace('Want me to send', 'Is this useful? Want me to send'), 'single_cta'),
    ('Spotless on mobile', NEW_SPOTLESS[1].replace("It's a loading", 'We could also add a chatbot. It is a loading'), 'one_offer'),
    ('FREE website speed boost for Spotless!', NEW_SPOTLESS[1], 'subject'),
    ('Spotless on mobile', NEW_SPOTLESS[1].replace('straight away.', 'straight away!'), 'personal'),
    ('Spotless on mobile', 'Your homepage is slow.\n\nWe can fix it for you, your team and your customers.\n\nInterested?', 'specific'),
])
def test_each_playbook_check_names_what_to_improve(subject, body, check):
    result = copywriting.score(subject, body, 'website_improvement')
    assert check in {i['check'] for i in result['improve']} and result['score'] < 100


@pytest.mark.parametrize('service', sorted(set().union(*CAMPAIGN_SERVICES.values())))
def test_every_service_has_a_desire_benefit_and_low_risk_cta(service):
    plan = copywriting.copy_plan({'service': service, 'company': 'Bright Demo'}, {}, 'Bright Demo')
    assert plan['their_desire'] and plan['benefit_to_reach'] and plan['awareness_stage'] == 'unaware'
    assert all(cta.endswith('?') and len(cta.split()) <= 14 for cta in plan['cta_options'])
    assert len(plan['principles']) == len(copywriting.PRINCIPLES)
    for text in [plan['benefit_to_reach'], *plan['cta_options']]:
        assert not copywriting.SPAM.search(text) and not copywriting.SECOND_OFFER.search(text)
        assert not email_writer.re.search(r'never miss|losing|lost|guarantee', text, email_writer.re.I)


def test_measured_finding_sets_problem_unaware_entry_and_packet_carries_the_plan(db, prepared):
    *_, packet = packet_for(db, prepared, 'broken_cta')
    plan = packet['copy_plan']
    assert plan['awareness_stage'] == 'problem_unaware' and 'pitch_brief.hook' in plan['entry_point']
    assert 'Bright Demo' in plan['reader']


def writer(monkeypatch, settings, replies):
    """Run the real writer against scripted model replies; return the packets it sent."""
    settings.followups_enabled = False
    settings.draft_api_key, settings.draft_model = 'fixture-key', 'fixture-model'
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    sent = []
    def chat(_settings, instructions, encoded, **kwargs):
        if kwargs.get('before_request'):
            kwargs['before_request']()  # As the real chat() does before every request.
        sent.append((instructions, json.loads(encoded)))
        reply = replies[len(sent)-1]
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply)
    monkeypatch.setattr(email_writer, 'chat', chat)
    return sent


def drafts(db, prepared):
    lead, audit, finding, evidence, packet = packet_for(db, prepared, 'font_timing')
    good = email_from(packet['pitch_brief'], prepared)
    weak = json.loads(json.dumps(good))
    weak['messages'][0].update(subject='Bright Demo homepage loading on mobile devices and next steps', body=WEAK)
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    return lead, contact, finding, evidence, audit, good, weak


@pytest.mark.parametrize('second', ['better', 'invalid', 'provider_error'])
def test_low_scoring_valid_draft_gets_one_rewrite_and_never_ends_worse(db, prepared, settings, monkeypatch, second):
    lead, contact, finding, evidence, audit, good, weak = drafts(db, prepared)
    settings.copy_min_score = 75
    replies = [weak, good if second == 'better' else {'messages': []} if second == 'invalid' else ValueError('AI writing endpoint unavailable')]
    sent = writer(monkeypatch, settings, replies)
    result = email_writer.generate_sequence(settings, lead, contact, finding, evidence, audit_context=audit)
    assert len(sent) == 2
    feedback = sent[1][1]['validation_feedback']
    assert 'Copy score' in feedback['error'] and {'hero', 'readability'} <= {i['check'] for i in feedback['improve']}
    assert 'COPYWRITING PLAYBOOK' in sent[0][0] and sent[0][1]['copy_plan']['cta_options']
    review = result['provenance']['copy_review']
    if second == 'better':
        assert review['score'] == 100 and result['messages'][0]['subject'] == good['messages'][0]['subject']
    else:
        assert review['score'] < 75 and result['messages'][0]['body'].endswith(WEAK)


def test_good_first_draft_or_disabled_bar_uses_a_single_call(db, prepared, settings, monkeypatch):
    lead, contact, finding, evidence, audit, good, weak = drafts(db, prepared)
    settings.copy_min_score = 75
    sent = writer(monkeypatch, settings, [good])
    assert email_writer.generate_sequence(settings, lead, contact, finding, evidence, audit_context=audit)['provenance']['copy_review']['score'] == 100
    assert len(sent) == 1
    settings.copy_min_score = 0
    sent = writer(monkeypatch, settings, [weak])
    email_writer.generate_sequence(settings, lead, contact, finding, evidence, audit_context=audit)
    assert len(sent) == 1


def test_context_change_during_the_rewrite_still_discards_the_result(db, prepared, settings, monkeypatch):
    lead, contact, finding, evidence, audit, good, weak = drafts(db, prepared)
    settings.copy_min_score = 75
    writer(monkeypatch, settings, [weak, ValueError('AI writing endpoint unavailable')])
    calls = []
    def before_request():
        calls.append(1)
        if len(calls) > 1:
            raise ValueError('Contact, research or drafts changed during AI writing; result discarded')
    with pytest.raises(ValueError, match='changed during AI writing'):
        email_writer.generate_sequence(settings, lead, contact, finding, evidence, audit_context=audit, before_request=before_request)
