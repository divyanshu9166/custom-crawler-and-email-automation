"""Descriptive, read-only acquisition funnel. SMTP acceptance is not inbox delivery.

Approval context is immutable; legacy sends without a snapshot stay unattributed.
Counts deduplicate business records, never claim independent real-company identity,
audited revenue, causal lift, email opens or automatic experiment winners.
"""
import json
from collections import defaultdict


FIELDS = ('prospect_records', 'qualified_for_outreach', 'approved_records', 'smtp_accepted_records',
          'smtp_accepted_messages', 'human_email_reply_records', 'opt_out_records', 'bounced_records',
          'qualified_sales_records', 'recorded_won_records', 'completed_records')


def decoded(value):
    try:
        item = json.loads(value)
        return item if isinstance(item, dict) else {}
    except (ValueError, TypeError):
        return {}


def summarize(rows):
    totals = {key: sum(row[key] for row in rows) for key in FIELDS}
    accepted = totals['smtp_accepted_records']
    qualified = totals['qualified_sales_records']
    totals['rates'] = {
        'human_email_reply_per_accepted_record': totals['human_email_reply_records'] / accepted if accepted else None,
        'qualified_sales_per_accepted_record': qualified / accepted if accepted else None,
        'recorded_won_per_accepted_record': totals['recorded_won_records'] / accepted if accepted else None,
        'recorded_won_per_qualified_sales_record': totals['recorded_won_records'] / qualified if qualified else None,
    }
    if not accepted:
        action = 'No SMTP-accepted sample yet. Finish provider readiness and reviewed outreach before judging campaign performance.'
    elif accepted < 20:
        action = 'Small sample. Review individual responses and follow-up maturity; these descriptive rates cannot identify a winning offer.'
    elif not totals['human_email_reply_records']:
        action = 'Inspect business fit, contact relevance, provider placement and pitch clarity. Zero recorded replies does not identify the cause.'
    elif not qualified:
        action = 'Review actual reply intent and confirmed client qualification; do not treat every response as interest.'
    elif not totals['recorded_won_records']:
        action = 'Review recorded next actions, objections and proposal scope/terms with qualified prospects.'
    else:
        action = 'Compare client outcome notes with the agreed metric; contract and payment references are operator records, not audited revenue.'
    totals['sample_state'] = 'no_accepted_sample' if not accepted else 'small_sample' if accepted < 20 else 'descriptive_only'
    totals['review_next'] = action
    return totals


def report(db):
    from .offers import selected_offer
    from .workflow_detail import ReadView
    # One read transaction prevents replies/sends from producing internally inconsistent totals.
    with db.connect() as con:
        con.execute('BEGIN')
        leads = [dict(r) for r in con.execute('SELECT * FROM leads')]
        qualified_current = {lead['id'] for lead in leads if selected_offer(ReadView(con), lead)}
        contacts = [dict(r) for r in con.execute('SELECT id,lead_id,reviewed_at FROM contacts')]
        messages = [dict(r) for r in con.execute("SELECT contact_id,sent_at FROM messages WHERE state='sent' AND sent_at IS NOT NULL")]
        events = [dict(r) for r in con.execute("SELECT kind,contact_id,detail,created_at FROM events WHERE kind IN ('sequence_approved','reply','opt_out','bounce','sales_stage') ORDER BY id")]
        activities = [dict(r) for r in con.execute("SELECT lead_id,channel,kind,happened_at FROM activities WHERE kind IN ('reply','opt_out')")]
        sales = {r['lead_id']: r['stage'] for r in con.execute('SELECT lead_id,stage FROM sales')}
    contact_lead = {c['id']: c['lead_id'] for c in contacts}
    first_approval, approved, sent, first_send = {}, set(), defaultdict(int), {}
    for contact in contacts:
        if contact['reviewed_at']:
            approved.add(contact['lead_id'])
    for event in events:
        lid = contact_lead.get(event['contact_id'])
        if lid is not None and event['kind'] == 'sequence_approved':
            approved.add(lid)
            first_approval.setdefault(lid, decoded(event['detail']).get('context'))
    for message in messages:
        lid = contact_lead.get(message['contact_id'])
        if lid is not None:
            sent[lid] += 1
            first_send[lid] = min(first_send.get(lid, message['sent_at']), message['sent_at'])
    replies, opt_outs, bounces, qualified, won, completed = set(), set(), set(), set(), set(), set()
    qualification_stages = {'qualified', 'call_booked', 'proposal', 'won', 'delivery', 'completed'}
    for event in events:
        detail = decoded(event['detail'])
        lid = detail.get('lead_id') if event['kind'] == 'sales_stage' else contact_lead.get(event['contact_id'])
        if lid not in first_send or event['created_at'] < first_send[lid]:
            continue
        if event['kind'] == 'reply':
            replies.add(lid)
        elif event['kind'] == 'opt_out':
            opt_outs.add(lid)
        elif event['kind'] == 'bounce':
            bounces.add(lid)
        elif event['kind'] == 'sales_stage':
            stage = detail.get('stage')
            if stage in qualification_stages:
                qualified.add(lid)
            if stage in {'won', 'delivery', 'completed'}:
                won.add(lid)
            if stage == 'completed':
                completed.add(lid)
    for activity in activities:
        lid = activity['lead_id']
        if lid not in first_send or activity['happened_at'] < first_send[lid]:
            continue
        if activity['kind'] == 'reply' and activity['channel'] == 'email':
            replies.add(lid)
        elif activity['kind'] == 'opt_out':
            opt_outs.add(lid)
    # Terminal/current records remain useful for imported legacy lifecycle data.
    for lid, stage in sales.items():
        if lid not in first_send:
            continue
        if stage in qualification_stages:
            qualified.add(lid)
        if stage in {'won', 'delivery', 'completed'}:
            won.add(lid)
        if stage == 'completed':
            completed.add(lid)
    grouped = defaultdict(list)
    for lead in leads:
        lid = lead['id']
        context = first_approval.get(lid)
        if isinstance(context, dict) and context.get('lead_id') == lid and context.get('campaign') in {'A', 'B'}:
            cohort = (context['campaign'], context.get('country') or 'unknown', context.get('service') or 'unselected',
                      context.get('industry') or 'unspecified', 'approval_snapshot')
        elif lid in approved or lid in sent:
            cohort = ('unknown', 'unknown', 'legacy_unknown', 'unspecified', 'legacy_without_snapshot')
        else:
            findings = json.loads(lead['findings'])
            industry = findings[0].get('industry', '') if findings and isinstance(findings[0], dict) else ''
            cohort = (lead['campaign'], lead['country'] or 'unconfirmed', lead['service'] or 'unselected',
                      industry or 'unspecified', 'current_unapproved_fields')
        grouped[cohort].append(dict(zip(FIELDS, [1, int(lid in qualified_current), int(lid in approved),
            int(lid in sent), sent[lid], int(lid in replies), int(lid in opt_outs), int(lid in bounces),
            int(lid in qualified), int(lid in won), int(lid in completed)], strict=True)))
    cohorts = [{'campaign': key[0], 'country': key[1], 'service': key[2], 'industry': key[3], 'attribution': key[4],
                **summarize(rows)} for key, rows in sorted(grouped.items())]
    return {'totals': summarize(cohorts), 'cohorts': cohorts, 'demo': db.get('demo') == 'true',
            'definitions': {
                'unit': 'Distinct lead/business records, not independently deduplicated real-world legal entities. Website-found profile records can refer to the same business.',
                'smtp_accepted': 'At least one saved sent message; not proof of inbox delivery.',
                'qualified_for_outreach': 'Current reviewed business offer with fresh latest-attempt country/opportunity evidence; not recipient verification or sending permission. Historical approvals and accepted messages remain separate.',
                'reply': 'Human email reply recorded after first SMTP acceptance; excludes auto-replies, DSNs and non-email manual replies.',
                'qualification': 'Recorded sales qualification after acceptance/current imported sales state; conversations can continue on other channels.',
                'won': 'Operator-recorded won/delivery/completed stage; no independently verified payment or revenue.',
                'rates': 'Lifetime descriptive rates use SMTP-accepted business records, except won/qualified. No denominator = null, never a fictional zero-success result.',
                'attribution': 'Frozen first approval context; earlier approved/sent records without it are unknown. Unapproved records use current labels.',
                'limitations': 'No email opens, inbox placement, positive-intent inference, follow-up maturity correction, cost/ROI measurement, causal attribution or automatic experiment winners.',
            }}
