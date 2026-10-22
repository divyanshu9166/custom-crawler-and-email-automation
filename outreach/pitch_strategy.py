"""One coherent prospect solution: a primary service and relevant optional additions."""
import json
import re
import time
from urllib.parse import urlsplit

BOT = re.compile(r'\b(?:(?:powered by|by) (?:enquirybot|intercom|tidio|livechat)|powered by (?:a |our )?chatbot|chat with (?:our|the) (?:assistant|bot))\b', re.I)
PHONE = re.compile(r'(?:\+?\d[\d ()-]{7,}\d)')
QUESTIONS = re.compile(r'frequently asked questions|customer support|questions about (?:booking|services|products)|how (?:do|can) I', re.I)
CALLING_MENTION = re.compile(r'\b(?:AI(?:[ -]powered)?\s+(?:(?:calling|phone|voice|helpdesk|support)\s+)?(?:agent|assistant|receptionist)|(?:calling|voice|phone)\s+(?:agent|assistant))\b', re.I)


def option_mentioned(option, text):
    return bool(CALLING_MENTION.search(text) if option['service'] == 'ai_calling_agent' else
                re.search(r'chatbot|FAQ assistant', text, re.I))


def phone_match(text):
    for match in PHONE.finditer(text):
        digits = re.sub(r'\D', '', match.group())
        context = text[max(0, match.start()-35):match.end()+15]
        if (10 <= len(digits) <= 15 and ('+' in match.group() or
                digits.startswith('0') and len(digits) in {10, 11} or
                re.search(r'\b(?:phone|telephone|tel|call)\b', context, re.I))):
            return match
    return None


def review_snapshot(db, lead_id):
    row = db.one("SELECT id,detail,created_at FROM events WHERE kind='business_tool_review' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (lead_id,))
    if not row or not time.time()-30*86400 <= row['created_at'] <= time.time()+60:
        return {}
    value = json.loads(row['detail'])
    if value.get('chatbot_status') not in {'present', 'unknown'}:
        return {}
    return {'event_id': row['id'], 'chatbot_status': value['chatbot_status'],
            'source_url': value['source_url'], 'evidence_reference': value['evidence_reference'],
            'reviewed_at': row['created_at']}


def context_pages(lead, finding, pages):
    """Small official-source set with positive tool/phone signals before generic pages."""
    from .profiles import source_allowed
    from .web import domain_of
    lead = {**lead, 'domain': lead.get('domain') or domain_of(lead.get('website', ''))}
    if not lead['domain'] and lead.get('lead_kind') != 'profile':
        return []
    def rank(page):
        path = urlsplit(page['url']).path
        signal = bool(BOT.search(page['text']) or phone_match(page['text']) or QUESTIONS.search(page['text']))
        return (0 if page['id'] == finding.get('evidence_id') else
                1 if path in {'', '/'} else 2 if re.search(r'contact|about|service|faq|book', path, re.I) and signal else
                3 if signal else 4, len(path), page['id'])
    return sorted([p for p in pages if source_allowed(lead, p['url'])], key=rank)[:6]


def writer_excerpt(page, finding):
    """Keep decisive exact evidence and short context rather than duplicate long pages."""
    text = page['text']
    parts = [text[:900]]
    quotes = [finding.get('quote', ''), finding.get('country_quote', ''),
              finding.get('offer_context', {}).get('commerce_quote', '')]
    quotes += [(finding.get(key) or {}).get('quote', '') for key in ('trigger', 'followup')]
    for quote in quotes:
        if quote and quote in text and not any(quote in part for part in parts):
            parts.append(quote)
    matches = [BOT.search(text), phone_match(text), QUESTIONS.search(text)]
    from .calling import source_signal
    call = source_signal(text)
    if call and not any(call['quote'] in part for part in parts):
        parts.append(call['quote'])
    for match in matches:
        if match:
            excerpt = text[max(0, match.start()-80):match.end()+160]
            if not any(excerpt in part for part in parts):
                parts.append(excerpt)
    return '\n[...]\n'.join(parts)[:4000]


def build(lead, finding, pages, audit_context=None, review=None):
    official = context_pages(lead, finding, pages)
    tool = next((p for p in official if BOT.search(p['text'])), None)
    status = 'present' if tool else 'unknown'
    review = review or {}
    if review.get('chatbot_status') == 'present':
        status = 'present'
    service = lead.get('service') or finding.get('service', '')
    plan = {'primary_service': service, 'chatbot_status': status,
            'chatbot_evidence_id': tool['id'] if tool else None,
            'tool_review': review, 'optional_services': [],
            'website_scope': 'existing_website' if lead.get('lead_kind') != 'profile' else 'website_not_found_in_research',
            'ui_design_status': 'not_established_by_speed_test', 'conversion_loss_confirmed': False,
            'source_ids': [p['id'] for p in official]}
    if service == 'website_improvement':
        plan['project_scope'] = 'Propose a clearer mobile service-to-enquiry layout and address the measured loading issue, preserving useful existing tools. Confirm the visual redesign scope in a focused review.'
        from .conclusions import build as conclusion
        points = conclusion(audit_context or {}, service)['findings']
        if points and points[0]['kind'] == 'journey_observation':
            plan['project_scope'] = points[0]['proposed_fix']+' Preserve useful existing tools and confirm any wider redesign scope separately.'
    elif service == 'website_build':
        plan['project_scope'] = ('Build a focused services website with a clear enquiry route, subject to confirming that the business needs a website.' if lead.get('lead_kind') == 'profile' else
                                 'Create the reviewed new service page; do not imply the existing website is missing.')
    if lead.get('campaign') != 'A' or service not in {'website_improvement', 'website_build'}:
        return plan
    question_page = next((p for p in official if QUESTIONS.search(p['text'])), None)
    if status != 'present' and question_page:
        plan['optional_services'].append({'service': 'chatbot', 'status': 'optional_fit_check',
            'evidence_id': question_page['id'], 'quote': QUESTIONS.search(question_page['text']).group(), 'proposal': 'Explore an assistant using approved answers and a human handoff alongside the website work; confirm existing tools and actual question handling first.'})
    from .calling import source_signal, pitch_plan
    route = next(((p, source_signal(p['text'])) for p in official if source_signal(p['text'])), None)
    if route:
        page, signal = route
        plan['optional_services'].append({'service': 'ai_calling_agent', 'status': 'source_backed_option',
            'use_case': signal['use_case'], 'evidence_id': page['id'], 'quote': signal['quote'], 'proposal': pitch_plan(signal['quote'])['proposed_work']})
    else:
        phone = next(((p, phone_match(p['text'])) for p in official if phone_match(p['text'])), None)
        if phone and re.search(r'quot|enquir|inquir|book|appointment|consult|service', finding.get('quote', ''), re.I):
            page, number = phone
            plan['optional_services'].append({'service': 'ai_calling_agent', 'status': 'optional_fit_check',
                'evidence_id': page['id'], 'quote': number.group(),
                'proposal': 'If phone enquiries are relevant, explore collecting service, location and timing details with an AI calling agent and a human handoff. Confirm the phone workflow first; a listed number does not prove missed calls or demand.'})
    return plan


def validate_copy(plan, text, *, initial=False):
    if initial and plan.get('primary_service') in {'website_improvement', 'website_build'} and plan.get('optional_services'):
        project = r'layout|redesign|journey|service.to.(?:enquir|quot)|enquir.{0,20}(?:flow|page)|(?:website|site|mobile).{0,50}(?:load|speed|perform|optim)|(?:service|quote|enquir).{0,45}(?:information|text|content|visible|appear|option|route)|(?:paragraph|introductory|service).{0,35}(?:text|copy|read|contrast)|(?:contrast|colou?r).{0,35}(?:text|panel|paragraph|background)'
        if plan['primary_service'] == 'website_improvement' and not re.search(project, text, re.I):
            raise ValueError('Explain the primary website project and enquiry journey, not just a technical audit fix')
    if plan.get('chatbot_status') == 'present' and re.search(r'(?:add|build|install|introduc\w*|set up|deploy)\s+(?:a\s+|an\s+|new\s+|an? new\s+)?(?:AI\s+)?chatbot|(?:missing|no|without|lack\w*)\s+(?:a\s+|an\s+)?chatbot', text, re.I):
        raise ValueError('The prospect already has a chatbot; preserve it instead of pitching a new or missing chatbot')
    if re.search(r'(?:your|the|current)\s+(?:UI|design|website|site).{0,30}(?:ugly|outdated|poorly designed|not CRO optimised|not CRO optimized|losing conversions|needs (?:a )?redesign)', text, re.I):
        raise ValueError('A speed test does not establish poor UI/CRO or a necessary redesign; offer a proposed change supported by design evidence')
    if CALLING_MENTION.search(text) and plan.get('primary_service') != 'ai_calling_agent':
        option = next((o for o in plan.get('optional_services', []) if o['service'] == 'ai_calling_agent'), None)
        if not option:
            raise ValueError('Calling add-on needs relevant current source context')
        if option['status'] == 'optional_fit_check' and not re.search(r'\bif\b|whether|worth exploring|confirm.{0,30}phone', text, re.I):
            raise ValueError('A listed phone number permits a conditional calling-agent fit check, not an established need')
        if option.get('use_case') == 'customer_support' and re.search(r'(?:qualify|qualifying)\s+(?:your\s+|new\s+|sales\s+)?leads', text, re.I):
            raise ValueError('A helpdesk phone route supports a support proposal, not an assumed sales-qualification workflow')


WRITER_INSTRUCTIONS = """
Use prospect_solution to compose ONE coherent solution, not a menu of everything we sell.
Keep the selected primary service central. optional_services are for a later conversation:
leave them out of an initial email unless one directly fixes the same finding. They are
optional, not additional diagnosed problems, and never a second offer in the first email.
Follow the optional calling use_case: a helpdesk route supports approved support answers
and human handoff, not an assumed sales-qualification or booking workflow.
For a website project, explain the observed page-specific problem and its concrete
fix before any wider project scope. Available optional_services are context, never
a requirement to include an add-on. In the initial email, focus on one current finding
and omit unrelated chatbot/calling-agent offers. A phone route alone does not make
calling automation relevant to a readability, layout or loading finding.
When a current chatbot is present, briefly say it can be retained. A useful website
proposal can refresh the mobile service-to-enquiry layout while fixing the measured
loading issue; this is proposed scope, not proof that a full redesign is necessary.
If chatbot_status=present, acknowledge/preserve that assistant where relevant. Do not offer
to add another chatbot or assert it is absent. Unknown means unknown, not confirmed absence.
If the website was not found in research, retain the supplied uncertainty while offering
website development; do not invent a current website to redesign.
A slow lab result supports loading improvements, not a claim of ugly UI, poor CRO, lost sales
or a necessary full redesign. Propose a clearer mobile/service/quote layout as project scope,
not as proof that the existing layout is bad. Ground claimed design defects in supplied
design observations. Do not manufacture them from the performance score.
Explain the buyer-facing project before implementation detail. Mention one useful measured
fact, then connect the proposed website work to finding services and reaching the next step.
Use at most one numerical measurement. Do not dump LCP/FCP timings or infer when a quote
form becomes usable from page-paint timings. Keep the actual business project central.
Avoid writing an email that sounds like a Lighthouse report or lists font/CSS tasks alone.
The website project can be loading optimisation tied to service information or the
existing enquiry route. Do not force a redesign/layout claim when only loading evidence exists.
For an optional_fit_check calling agent, keep it conditional: if phone enquiries are relevant,
it could collect requirement details and route a summary to the team. Do not infer a phone
bottleneck from a listed number. Keep optional additions to one short sentence, with one
final next-step question for the overall proposal. Stay within the 55-95 word target.
"""
