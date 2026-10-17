"""Free, conservative service proposals from explicit current public-page signals.

These propose a reviewable offer, never infer an absent feature, lost revenue,
channel consent or buyer fit. Geography, ownership and final selection stay gated.
"""
import re
from urllib.parse import urlsplit


INQUIRY = r'\b(?:book (?:a |an |your )?(?:consultation|appointment|demo|call)|request (?:a |your )?quote|schedule (?:a |an |your )?(?:appointment|call|demo)|contact us|get in touch|call us)\b'
PRODUCT = r'\b(?:add to (?:cart|basket)|shop now|buy online|product catalogue|product catalog|place (?:an |your )?order)\b'
QUESTIONS = r'\b(?:frequently asked questions|questions about (?:booking|products|shipping|orders)|shipping and returns|customer (?:questions|support))\b'
WHATSAPP = r'\b(?:contact us (?:on|via) whatsapp|chat (?:with us )?(?:on|via) whatsapp|whatsapp)\b'
NEGATION = re.compile(r"\b(?:no|not|never|cannot|can't|don't|do not|does not|without)\b", re.I)
LEGAL_PATH = re.compile(r'(?:^|/)(?:privacy(?:[-_](?:policy|notice))?|terms(?:-of-(?:service|use)|-and-conditions)?|cookies?(?:-policy|-notice)?|data-protection|gdpr)(?:/|$)', re.I)
LEGAL_TITLE = re.compile(r'^(?:privacy (?:policy|notice)|terms(?: of (?:service|use)| and conditions)?|cookie (?:policy|notice)|data protection)\b', re.I)


def excerpt(text, match):
    start, end = max(0, match.start()-45), min(len(text), match.end()+100)
    while start > 0 and text[start-1].isalnum() and text[start].isalnum():
        start -= 1
    while end < len(text) and text[end-1].isalnum() and text[end].isalnum():
        end += 1
    return text[start:end].strip()


def proposals(lead, evidence):
    from .campaigns import CAMPAIGN_SERVICES
    campaign = lead['campaign']
    allowed = CAMPAIGN_SERVICES[campaign]
    profile = lead.get('lead_kind') == 'profile'
    from .discovery import official_root
    from .web import domain_of
    if not profile and lead.get('website'):
        try:
            official_root(lead['website'])
        except ValueError:
            return []
    if profile and lead.get('website_status') != 'website_not_found':
        return []
    if profile:
        rules = [(
            'website_build' if campaign == 'A' else 'store_launch', 95,
            INQUIRY if campaign == 'A' else r'\b(?:products|shop|sell|selling|orders|catalogue|catalog)\b',
            'The captured business profile includes this public service/order signal',
            'Explore a focused services page with an inquiry or suitable booking route.' if campaign == 'A' else
            'Explore a small product catalogue and appropriate checkout/support journey, after confirming the current selling process.'
        ), ('chatbot', 60, QUESTIONS, 'The captured business profile includes customer-question information',
            'Explore approved answers and a clear human handoff after confirming how customers currently ask for help.')]
    elif campaign == 'A':
        rules = [
            ('website_build', 95, r'\b(?:launching|introducing|announcing) (?:a |our |the )?new service\b',
             'The saved page mentions a new service', 'Explore a dedicated service page explaining the offer and one relevant inquiry route.'),
            ('website_improvement', 85, INQUIRY, 'The saved page includes a public inquiry or booking invitation',
             'Review that inquiry journey and test a clearer explanation of the next step; agree on a success metric before making changes.'),
            ('chatbot', 60, QUESTIONS, 'The saved page includes customer-question or support information',
             'Review whether a narrow assistant using approved answers and a clear human handoff would help customers reach the next step.'),
        ]
    else:
        rules = [
            ('store_launch', 95, r'\b(?:online store|online shop|product (?:range|collection)) (?:is )?(?:launching|coming) soon\b',
             'The saved page mentions an upcoming store or product range',
             'Explore a small launch catalogue with suitable checkout, delivery, returns and support information.'),
            ('store_improvement', 85, PRODUCT, 'The saved page includes a public shopping or order invitation',
             'Review one product-to-purchase journey and choose a focused test; confirm actual checkout behavior and measurement first.'),
            ('chatbot', 60, QUESTIONS, 'The saved page includes customer-question or support information',
             'Review a shopping/support assistant with approved answers, clear limitations and a human handoff.'),
            ('whatsapp_marketing', 45, r'\b(?:subscribe|sign up|opt in) (?:to|for) (?:our )?whatsapp (?:updates|offers|messages)\b',
             'The saved page includes a public invitation to request WhatsApp updates',
             'Review a permission-based retention pilot and opt-out handling; confirm valid customer permissions and permitted message requirements first.'),
            ('whatsapp_automation', 40, WHATSAPP, 'The saved page mentions WhatsApp as a public channel',
             'First qualify customer channel fit, permission and eligible events; then explore one useful support or order-update workflow.'),
        ]
    choices = {}
    selected_keys = {}
    for page in evidence:
        path = urlsplit(page['url']).path
        if LEGAL_PATH.search(path) or LEGAL_TITLE.search(page.get('title', '').strip()):
            continue
        if not profile:
            try:
                official_root(page['url'])
            except ValueError:
                continue
            if lead.get('website') and domain_of(page['url']) != domain_of(lead['website']):
                continue
        text = page.get('text', '')
        for service, priority, pattern, observation, suggestion in rules:
            if service not in allowed:
                continue
            for match in re.finditer(pattern, text, re.I):
                # A negative statement is not positive evidence of an available route.
                before = re.split(r'[.!?\n]', text[max(0, match.start()-60):match.start()])[-1]
                if NEGATION.search(before):
                    continue
                generic_contact = match.group().lower() in {'contact us', 'get in touch', 'call us'}
                after = text[match.end():match.end()+80].lstrip(' :,-\n')
                if generic_contact and not re.match(r"(?:for|about|to|at|today|by|with)\b|[\w.+-]+@|\+?\d|\(\d", after, re.I):
                    continue
                if match.group().lower() == 'frequently asked questions':
                    question_context = text[match.end():match.end()+240].strip()
                    if not (re.match(r'about\b', question_context, re.I) or
                            re.search(r'\b(?:how|what|where|when|why|can|do|does|is|are)\b[^?]{0,180}\?', question_context, re.I)):
                        continue
                quote = excerpt(text, match)
                if len(quote) < 8 or quote not in text:
                    continue
                strength = 40 if generic_contact else 60 if match.group().lower() == 'shop now' else 100
                routes = ('contact|book|appointment' if service.startswith('website_') else
                          'products?|collections?|shop|catalogue|catalog' if service.startswith('store_') else
                          'faq|help|support|contact')
                route_bonus = 15 if re.search(r'/(?:'+routes+r')(?:[-/]|$)', path, re.I) else 0
                selection_key = (-(strength+route_bonus), page['url'], quote)
                if service in selected_keys and selected_keys[service] <= selection_key:
                    continue
                selected_keys[service] = selection_key
                choices[service] = {'evidence_id': page['id'], 'quote': quote, 'source_url': page['url'],
                                    'observation': observation + ': ' + quote,
                                    'suggestion': suggestion, 'service': service, 'priority': priority,
                                    'review_required': True, 'kind': 'opportunity',
                                    'proposal_method': 'explicit_public_signal',
                                    'source_selection': 'Contextual contact route' if generic_contact else 'Explicit business action or support signal',
                                    'limitations': 'Proposed relevance only; not a verified pain point, buyer fit, absence claim or predicted conversion gain.'}
    return sorted(choices.values(), key=lambda item: (-item['priority'], item['service']))
