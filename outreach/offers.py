"""Review business-model/channel context without inferring customer permission."""
import json


GOALS = {'A': 'inquiries_bookings', 'B': 'd2c_growth'}
ARTIFACTS = {
    'website_build': ['concept', 'audit'], 'website_improvement': ['audit', 'concept'],
    'chatbot': ['faq_demo', 'audit'], 'store_launch': ['concept', 'audit'],
    'store_improvement': ['audit', 'concept'],
    'whatsapp_marketing': ['whatsapp_flow', 'audit'], 'whatsapp_automation': ['whatsapp_flow', 'audit'],
}


def review_context(lead, review, by_id):
    goal = review.get('primary_goal') or GOALS[lead['campaign']]
    if goal != GOALS[lead['campaign']]:
        raise ValueError('Primary goal must match the selected Campaign A/B target')
    context = {'primary_goal': goal, 'goal_reviewed': bool(review.get('primary_goal'))}
    sources = {}
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
    if lead['campaign'] == 'B':
        try:
            review_context(lead, {**finding.get('offer_context', {}), 'service': lead['service']}, pages)
        except ValueError:
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
    nodes = [
        ('input', 'Qualified prospect + current evidence', 'complete' if current else 'needs_review'),
        ('goal', 'Primary business goal', 'complete' if current and context.get('goal_reviewed') else 'needs_review'),
        ('campaign_a', 'Campaign A · inquiries and bookings', 'selected' if lead['campaign'] == 'A' else 'other_branch'),
        ('campaign_b', 'Campaign B · D2C growth', 'selected' if lead['campaign'] == 'B' else 'other_branch'),
        ('website_build', 'Website / new service page', 'selected' if selected == 'website_build' else 'not_selected'),
        ('website_improvement', 'Website improvement / redesign', 'selected' if selected == 'website_improvement' else 'not_selected'),
        ('inquiry_chatbot', 'Inquiry / booking chatbot + human handoff', 'selected' if selected == 'chatbot' and lead['campaign'] == 'A' else 'not_selected'),
        ('store_launch', 'Starting ecommerce · store launch', 'selected' if selected == 'store_launch' and commerce_ready else 'not_selected'),
        ('store_improvement', 'Selling online · shopping journey', 'selected' if selected == 'store_improvement' and commerce_ready else 'not_selected'),
        ('shopping_chatbot', 'Shopping / support chatbot', 'selected' if selected == 'chatbot' and lead['campaign'] == 'B' and commerce_ready else 'not_selected'),
        ('whatsapp_fit', 'WhatsApp customer fit and permission', 'confirmed' if channel_ready else 'needs_qualification' if whatsapp else 'not_selected'),
        ('whatsapp_offer', 'WhatsApp marketing / automation', 'confirmed_fit' if channel_ready else 'qualification_only' if whatsapp else 'not_selected'),
        ('whatsapp_qualify', 'Qualify channel and opt-in first', 'needs_qualification' if whatsapp and not channel_ready else 'not_selected'),
        ('primary_offer', 'Choose ONE primary offer', 'complete' if selected and commerce_ready else 'needs_review'),
    ]
    approved = []
    for artifact in db.all("SELECT * FROM deliverables WHERE lead_id=? AND state IN ('approved','sent')", (lead_id,)):
        try:
            from .deliverables import assert_current_artifact
            assert_current_artifact(db, artifact)
        except ValueError:
            continue
        if artifact['kind'] in ARTIFACTS.get(selected, []):
            approved.append(artifact['id'])
    nodes.append(('value_artifact', 'Prepare and review relevant proof of value', 'reviewed' if approved else 'needs_artifact_review' if selected else 'waiting'))
    return {'lead_id': lead_id, 'campaign': lead['campaign'], 'selected_service': selected, 'context': context,
            'nodes': [{'id': key, 'label': label, 'state': state} for key, label, state in nodes],
            'recommended_artifacts': ARTIFACTS.get(selected, []), 'reviewed_current_artifact_ids': approved,
            'note': 'Selected offers and reviewed artifacts do not establish a live client result. Unknown WhatsApp fit or permission permits qualification planning only.'}
