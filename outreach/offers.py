"""Review business-model/channel context without inferring customer permission."""
import json
import re


GOALS = {'A': 'inquiries_bookings', 'B': 'd2c_growth'}
ARTIFACTS = {
    'website_build': ['concept', 'audit'], 'website_improvement': ['audit', 'concept'],
    'ai_calling_agent': ['call_flow'],
    'chatbot': ['faq_demo', 'audit'], 'store_launch': ['concept', 'audit'],
    'store_improvement': ['audit', 'concept'],
    'whatsapp_marketing': ['whatsapp_flow', 'audit'], 'whatsapp_automation': ['whatsapp_flow', 'audit'],
}


def new_service_signal(quote):
    """A current announcement supports exploring a page, never claiming it is absent."""
    return bool(re.search(r'\b(?:new|launch\w*|introduc\w*|announc\w*)\b.{0,100}\bservice\w*\b|\bservice\w*\b.{0,100}\b(?:launch\w*|introduc\w*|announc\w*)\b', quote, re.I))


def typed_context(context):
    """Only enums/IDs/exact quotes cross into the writer; free-form notes do not."""
    result = {}
    for key, allowed in {
        'primary_goal': {'inquiries_bookings', 'd2c_growth'},
        'calling_use_case': {'booking', 'lead_qualification', 'customer_support'},
        'calling_scope': {'inbound_or_requested_callback'},
        'selling_stage': {'starting_ecommerce', 'selling_online'},
        'website_scope': {'website_launch', 'new_service_page'},
        'channel_fit_status': {'unknown', 'confirmed', 'not_suitable'},
        'customer_permission_status': {'unknown', 'confirmed', 'not_suitable'},
    }.items():
        if isinstance(context.get(key), str) and context[key] in allowed:
            result[key] = context[key]
    if type(context.get('commerce_evidence_id')) is int:
        result['commerce_evidence_id'] = context['commerce_evidence_id']
        if isinstance(context.get('commerce_quote'), str):
            result['commerce_quote'] = context['commerce_quote'][:700]
    if 'channel_fit_status' in result or 'customer_permission_status' in result:
        result['qualification_only'] = not (result.get('channel_fit_status') == result.get('customer_permission_status') == 'confirmed')
    return result


def evidence_basis(lead, finding, pages, audit_context=None):
    """Deterministic evidence category; technical measurements are not business pain."""
    quote = finding.get('quote', '').strip()
    source = next((p for p in pages if p['id'] == finding.get('evidence_id') and quote and quote in p['text']), None)
    service = finding.get('service', lead.get('service', ''))
    relevant = {
        'website_improvement': r'consult|book|quot(?:e|ation)|enquir|inquir|service|cleaning|appointment',
        'chatbot': r'question|support|help|faq|booking|product|service',
        'store_launch': r'launch|store|shop|product|consumer',
        'store_improvement': r'cart|buy|purchas|shop|product|checkout',
        'whatsapp_marketing': r'whatsapp|product|customer|consumer',
        'whatsapp_automation': r'whatsapp|product|customer|order',
        'website_build': r'service|business|launch|website',
    }.get(service, r'(?!)')
    generic = bool(re.fullmatch(r'[\s.!,:;]*(?:contact\s+us|get\s+in\s+touch|learn\s+more)[\s.!,:;]*', quote, re.I))
    commerce = finding.get('offer_context', {})
    commerce_quote = commerce.get('commerce_quote', '')
    commerce_current = any(p['id'] == commerce.get('commerce_evidence_id') and commerce_quote and commerce_quote in p['text'] for p in pages)
    usable = bool(source and not generic and (re.search(relevant, quote, re.I) or
                  service == 'website_build' and lead.get('lead_kind') == 'profile' or
                  lead.get('campaign') == 'B' and commerce_current and re.search(relevant, commerce_quote, re.I)))
    if service == 'ai_calling_agent':
        from .calling import source_signal
        usable = bool(source and lead.get('campaign') == 'A' and source_signal(quote))
    observations = (audit_context or {}).get('observations', [])
    measured = usable and service in {'website_improvement', 'store_improvement'} and bool(observations)
    return {'classification': 'measured_observation' if measured else 'exploratory_opportunity' if usable else 'insufficient_evidence',
            'business_pain_confirmed': False, 'draft_allowed': usable,
            'diagnostic_refs': [o['ref'] for o in observations] if measured else [],
            'note': 'A measured test/capture supports this proposal; client impact remains unconfirmed.' if measured else
                    'Source-backed experiment to discuss; no defect or client requirement is established.' if usable else
                    'A current, service-relevant business source is required; generic contact wording is insufficient.'}


def review_context(lead, review, by_id):
    goal = review.get('primary_goal') or GOALS[lead['campaign']]
    if goal != GOALS[lead['campaign']]:
        raise ValueError('Primary goal must match the selected Campaign A/B target')
    context = {'primary_goal': goal, 'goal_reviewed': bool(review.get('primary_goal'))}
    sources = {}
    if review['service'] == 'ai_calling_agent':
        from .calling import pitch_plan
        page = by_id.get(review.get('evidence_id'))
        quote = review.get('quote', '')
        if lead['campaign'] != 'A' or not page or not quote or quote not in page['text']:
            raise ValueError('Calling-agent offer needs Campaign A and a current exact business source quote')
        plan = pitch_plan(quote)
        context.update(calling_use_case=plan['use_case'], calling_scope=plan['scope'])
    if review['service'] == 'website_build':
        scope = review.get('website_scope', 'auto')
        if scope == 'auto':
            scope = 'website_launch' if lead.get('lead_kind') == 'profile' else 'new_service_page'
        if scope == 'new_service_page':
            page = by_id.get(review.get('evidence_id'))
            quote = review.get('quote', '')
            if not page or quote not in page['text'] or not new_service_signal(quote):
                raise ValueError('New service-page routing needs a current exact service announcement quote')
        elif scope != 'website_launch' or lead.get('lead_kind') != 'profile':
            raise ValueError('An existing website needs a sourced new service-page scope, not a missing-website pitch')
        context['website_scope'] = scope
    if lead['campaign'] == 'B':
        stage = review.get('selling_stage', 'unknown')
        if stage not in {'starting_ecommerce', 'selling_online'}:
            raise ValueError('Confirm the D2C selling stage before qualifying Campaign B')
        if (review['service'] == 'store_launch' and stage != 'starting_ecommerce' or
                review['service'] == 'store_improvement' and stage != 'selling_online'):
            raise ValueError('Selected store offer does not match the reviewed selling stage')
        page = by_id.get(review.get('commerce_evidence_id'))
        quote = review.get('commerce_quote', '').strip()
        notes = review.get('d2c_fit_notes', '').strip()
        if not page or len(quote) < 8 or quote not in page['text'] or len(notes) < 20:
            raise ValueError('Record a current D2C source quote and review product ownership and selling/launch process')
        context.update(selling_stage=stage, commerce_evidence_id=page['id'], commerce_quote=quote, d2c_fit_notes=notes)
        sources[page['id']] = page['sha256']
    if review['service'].startswith('whatsapp_'):
        fit = review.get('channel_fit_status', 'unknown')
        permission = review.get('customer_permission_status', 'unknown')
        if fit not in {'unknown', 'confirmed', 'not_suitable'} or permission not in {'unknown', 'confirmed', 'not_suitable'}:
            raise ValueError('Choose a valid WhatsApp fit and customer-permission review status')
        if 'not_suitable' in {fit, permission}:
            raise ValueError('WhatsApp is not suitable for this review; choose another primary offer')
        context.update(channel_fit_status=fit, customer_permission_status=permission,
                       qualification_only=fit != 'confirmed' or permission != 'confirmed')
    return context, sources


def selected_offer(db, lead):
    from .campaigns import CAMPAIGN_SERVICES
    from .research import fresh_evidence
    from .web import crawl_url
    if lead.get('lead_kind') != 'profile':
        from .discovery import official_root
        try:
            official_root(lead['website'])
        except ValueError:
            return ''
    findings = json.loads(lead['findings'])
    if (lead['status'] != 'qualified' or lead['country'] not in {'US', 'UK'}
            or len(findings) != 1 or lead['service'] not in CAMPAIGN_SERVICES[lead['campaign']]):
        return ''
    finding = findings[0]
    pages = {e['id']: e for e in fresh_evidence(db, lead['id'])}
    page = pages.get(finding.get('evidence_id'))
    if (not page or finding.get('review_required') is not False or finding.get('service') != lead['service'] or
            not finding.get('quote', '').strip() or finding['quote'] not in page['text'] or
            not any(crawl_url(e['url']) == crawl_url(lead['country_source']) and finding.get('country_quote', '').strip()
                    and finding['country_quote'] in e['text'] for e in pages.values())):
        return ''
    if lead['campaign'] == 'B' or lead['service'] in {'website_build', 'ai_calling_agent'}:
        try:
            review_context(lead, {**finding, **finding.get('offer_context', {}), 'service': lead['service']}, pages)
        except ValueError:
            return ''
    if not evidence_basis(lead, finding, list(pages.values()))['draft_allowed']:
        return ''
    return lead['service']


def snapshot(db, lead_id):
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead:
        raise ValueError('Prospect not found')
    finding = (json.loads(lead['findings']) or [{}])[0]
    context = finding.get('offer_context', {})
    selected = selected_offer(db, lead)
    current = bool(selected)
    whatsapp = selected.startswith('whatsapp_')
    fit = context.get('channel_fit_status', 'unknown')
    permission = context.get('customer_permission_status', 'unknown')
    channel_ready = whatsapp and fit == permission == 'confirmed'
    commerce_ready = lead['campaign'] != 'B' or context.get('selling_stage') in {'starting_ecommerce', 'selling_online'}
    from .research import fresh_evidence
    from .diagnostics import snapshot as audit_snapshot
    basis = evidence_basis(lead, finding, fresh_evidence(db, lead_id), audit_snapshot(db, lead))
    nodes = [
        ('input', 'Qualified prospect + current evidence', 'complete' if current else 'needs_review'),
        ('goal', 'Primary business goal', 'complete' if current and context.get('goal_reviewed') else 'needs_review'),
        ('campaign_a', 'Campaign A · inquiries and bookings', 'selected' if lead['campaign'] == 'A' else 'other_branch'),
        ('campaign_b', 'Campaign B · D2C growth', 'selected' if lead['campaign'] == 'B' else 'other_branch'),
        ('website_build', 'Website / new service page', 'selected' if selected == 'website_build' else 'not_selected'),
        ('website_improvement', 'Website improvement / redesign', 'selected' if selected == 'website_improvement' else 'not_selected'),
        ('inquiry_chatbot', 'Inquiry / booking chatbot + human handoff', 'selected' if selected == 'chatbot' and lead['campaign'] == 'A' else 'not_selected'),
        ('calling_agent', 'AI calling agent · qualification, bookings & support', 'selected' if selected == 'ai_calling_agent' else 'not_selected'),
        ('store_launch', 'Starting ecommerce · store launch', 'selected' if selected == 'store_launch' and commerce_ready else 'not_selected'),
        ('store_improvement', 'Selling online · shopping journey', 'selected' if selected == 'store_improvement' and commerce_ready else 'not_selected'),
        ('shopping_chatbot', 'Shopping / support chatbot', 'selected' if selected == 'chatbot' and lead['campaign'] == 'B' and commerce_ready else 'not_selected'),
        ('whatsapp_fit', 'WhatsApp customer fit and permission', 'confirmed' if channel_ready else 'needs_qualification' if whatsapp else 'not_selected'),
        ('whatsapp_offer', 'WhatsApp marketing / automation', 'confirmed_fit' if channel_ready else 'qualification_only' if whatsapp else 'not_selected'),
        ('whatsapp_qualify', 'Qualify channel and opt-in first', 'needs_qualification' if whatsapp and not channel_ready else 'not_selected'),
        ('primary_offer', 'One primary project + relevant optional additions', 'qualification_only' if whatsapp and not channel_ready else basis['classification'] if selected and commerce_ready else 'needs_review'),
    ]
    approved, prepared = [], []
    for artifact in db.all("SELECT * FROM deliverables WHERE lead_id=?", (lead_id,)):
        try:
            from .deliverables import assert_current_artifact
            assert_current_artifact(db, artifact)
        except ValueError:
            continue
        if artifact['kind'] in ARTIFACTS.get(selected, []):
            prepared.append(artifact['id'])
            if artifact['state'] in {'approved', 'sent'}:
                approved.append(artifact['id'])
    nodes.append(('value_artifact', 'Prepare and review relevant proof of value', 'reviewed' if approved else 'preview_ready' if prepared else 'needs_artifact_review' if selected else 'waiting'))
    calling_plan = {}
    if selected == 'ai_calling_agent':
        from .calling import pitch_plan
        calling_plan = pitch_plan(finding['quote'])
    from .pitch_strategy import build as solution, review_snapshot
    strategy = solution(lead, finding, fresh_evidence(db, lead_id), review=review_snapshot(db, lead_id))
    return {'prospect_solution': strategy, 'calling_plan': calling_plan, 'lead_id': lead_id, 'campaign': lead['campaign'], 'selected_service': selected, 'context': context,
            'nodes': [{'id': key, 'label': label, 'state': state} for key, label, state in nodes],
            'evidence_basis': basis, 'prepared_current_artifact_ids': prepared,
            'recommended_artifacts': ARTIFACTS.get(selected, []), 'reviewed_current_artifact_ids': approved,
            'note': 'Selected offers and reviewed artifacts do not establish a live client result. Unknown WhatsApp fit or permission permits qualification planning only.'}
