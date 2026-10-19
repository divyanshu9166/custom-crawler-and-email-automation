"""Evidence-based calling-agent offers; this module never makes a phone call."""
import re


PHONE = r'\b(?:call(?: (?:us|our|the|to|for)|(?=\s+\+?\d))|phone|telephone|tel|helpline|callback|call[ -]back|speak (?:to|with))\b'
EXCLUDED = r'\b(?:emergency|urgent medical|recruitment|vacanc\w*|careers?|apply for|job applicants?)\b'
MODES = {
    'booking': r'\b(?:book\w*|appointments?|schedule|reschedule|reservation\w*|consultation\w*)\b',
    'lead_qualification': r'\b(?:quot(?:e|es|ation)|estimates?|enquir\w*|inquir\w*|discuss your|project requirements?)\b',
    'customer_support': r'\b(?:customer (?:support|service)|helpdesk|support team|support line|questions about|existing customers?)\b',
}
PLANS = {
    'booking': (
        'Collect the requested service, preferred time and location; connect an approved calendar to check availability and book only after caller confirmation, with a human handoff.',
        'Aim to turn a booking conversation into a complete appointment request and reduce manual scheduling steps; validate this in a small pilot.',
        'Would a short example of handling one appointment call be useful?'),
    'lead_qualification': (
        'Ask callers about the service, location and timeline, collect an agreed qualification summary, and route it to the right person with a human handoff.',
        'Aim to give the team useful enquiry details before follow-up, so they can assess fit and prepare the next conversation; validate summary accuracy in a pilot.',
        'Would a short example of qualifying one quote enquiry be useful?'),
    'customer_support': (
        'Answer a narrow set of phone questions from business-approved information and transfer unresolved or sensitive requests to a human; account access needs a separately agreed integration.',
        'Aim to give callers consistent answers to routine questions and pass useful context to the team when human support is needed; measure accuracy and handoff quality in a pilot.',
        'Would a short example of answering one routine support call be useful?'),
}

WRITER_INSTRUCTIONS = """
Pitch ONE AI calling-agent use case from calling_plan, not website optimisation or a
generic chatbot. Briefly mention the published phone process, explain two concrete
steps the proposed agent would handle, then the practical intended benefit and one
small next step (a tailored sample call flow or short walkthrough). Do not dump features.
For qualification: service/location/timeline, a useful summary and routing to the team.
For bookings: capture preferences, connect an approved calendar to check availability,
caller confirmation and human handoff. Do not claim an integration already exists.
For support: answers from approved business knowledge and human transfer for unresolved
requests. Do not promise account actions without agreed access or medical/emergency advice.
Use natural language: show how the agent could help their published process rather than
announcing they need AI. Treat benefits as proposed goals, not an established deficiency.
Do not invent missed calls, lost leads, busy/overwhelmed staff, repetitive-call volume,
after-hours demand, cost savings or guaranteed bookings. A published phone route does not
prove these problems. No unsolicited outbound campaign or customer consent is established.
Scope is inbound calls or callbacks requested by the customer, subject to implementation
review. The local call_flow is a proposed outline, never a working voice demo or deployed
agent. Ignore unrelated lab scores; diagnostic_refs must be []. No fixed email template.
Keep the initial email around 70-100 words, with one relevant low-pressure final question.
"""


def source_signal(text):
    """Require a positive, nearby phone route AND a specific business task."""
    for route in re.finditer(PHONE, text, re.I):
        start = max(0, route.start()-100)
        end = min(len(text), route.end()+160)
        # Do not join separate sentences, or pair footer phone numbers with distant claims.
        left = re.split(r'[.!?\n]', text[start:route.start()])[-1]
        right = re.match(r'[^.!?\n]*[.!?]?', text[route.end():end]).group()
        quote = left + route.group() + right
        if (re.search(EXCLUDED, quote, re.I) or
                re.search(r"\b(?:no|not|never|cannot|can't|don't|do not|does not|without)\b", quote, re.I)):
            continue
        for mode, pattern in MODES.items():
            if re.search(pattern, quote, re.I):
                return {'use_case': mode, 'quote': quote.strip()}
    return None


def pitch_plan(quote):
    signal = source_signal(quote)
    if not signal:
        raise ValueError('AI calling agent needs a current phone/callback route tied to booking, quote enquiries or customer support; a number or Get a Quote button alone is insufficient')
    work, benefit, question = PLANS[signal['use_case']]
    return {**signal, 'scope': 'inbound_or_requested_callback', 'proposed_work': work,
            'intended_benefit': benefit, 'next_step': question,
            'pilot_checks': ['Confirm the business process, approved questions/answers and human handoff.',
                             'Agree phone, calendar/CRM permissions, caller disclosure and applicable callback/recording requirements.',
                             'Test with synthetic calls first; compare summary accuracy, booking correctness and handoff quality before rollout.'],
            'limitations': 'Proposed integration only. Missed calls, lost leads, call volume and customer demand are not established. No calls have been made.'}


def validate_copy(lead, finding, evidence, text, *, initial=True):
    if lead.get('campaign') != 'A' or not any(
            e['id'] == finding.get('evidence_id') and finding.get('quote') and finding['quote'] in e['text'] for e in evidence):
        raise ValueError('Calling-agent copy requires a current Campaign A phone-process source')
    plan = pitch_plan(finding['quote'])
    # Even a tentative rewrite must not smuggle invented pain or existing connections in.
    claims = r'\b(?:miss(?:ed|ing)? calls?|lost leads?|losing (?:leads|bookings)|overwhelmed|understaffed|never miss|guaranteed bookings|already (?:connected|integrated)|your existing (?:AI|voice|calling) agent)\b[^.!?]*'
    for match in re.finditer(claims, text, re.I):
        claim = ' '.join(match.group().casefold().split())
        if not any(claim in ' '.join(e['text'].casefold().split()) for e in evidence):
            raise ValueError('Calling-agent pitch invented operational pain, a promise or an existing integration')
    if initial:
        task = {'booking': r'book|appointment|schedul|availability',
                'lead_qualification': r'qualif|requirements?|service|location|timeline|summary',
                'customer_support': r'approved|knowledge|routine|support|questions?'}[plan['use_case']]
        if not (re.search(r'\b(?:AI|voice|calling|phone)\b', text, re.I) and
                re.search(r'agent|assistant', text, re.I) and re.search(task, text, re.I) and
                re.search(r'collect|ask|capture|answer|qualif|check availability|book|route|transfer', text, re.I) and
                re.search(r'summary|summaries|handoff|hand[ -]off|human|team|staff', text, re.I)):
            raise ValueError('Explain the calling-agent task and concrete collection/answer/booking step with a useful team summary or human handoff')
