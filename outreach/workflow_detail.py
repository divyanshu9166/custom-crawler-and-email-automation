"""Detailed, read-only business-flow map. No operation is triggered by inspecting it."""
import json
import time

from .profiles import assert_profile_review
from .research import assert_contact_ownership, contact_candidates
from .sales import QUALIFICATION, proposal_context_current
from .deliverables import assert_current_artifact
from .workflow import snapshot


# ID, title, execution mode, action destination. IDs match docs/WORKFLOW.md.
STAGES = [
    ('A', 'US/UK queries or sourced CSV', 'Automatic', 'discovery'),
    ('B', 'Search providers', 'Automatic', 'discovery'),
    ('C', 'Official website & deduplication', 'Automatic + review', 'prospect'),
    ('CP', 'Business profile candidate', 'Automatic', 'prospect'),
    ('CS', 'Profile snapshot & website search', 'Automatic', 'prospect'),
    ('CR', 'Review profile identity & activity', 'Human review', 'prospect'),
    ('CE', 'Published profile email candidate', 'Extraction + review', 'prospect'),
    ('D', 'Robots, sitemaps & Chromium', 'Automatic', 'prospect'),
    ('E', 'Saved evidence & public signals', 'Automatic + review', 'prospect'),
    ('E1', 'Company-domain contacts', 'Automatic', 'prospect'),
    ('E2', 'Other-domain email candidates', 'Extraction + review', 'prospect'),
    ('E3', 'Review source & inbox ownership', 'Human review', 'prospect'),
    ('F', 'Reacher verification', 'Automatic', 'prospect'),
    ('G', 'Country, buyer & opportunity review', 'Human review', 'prospect'),
    ('Q', 'Screenshots & optional lab audit', 'Automatic, optional', 'prospect'),
    ('H', 'Hold & further research', 'Automatic hold + review', 'prospect'),
    ('AA', 'Campaign A: inquiries & bookings', 'Proposals + review', 'prospect'),
    ('BB', 'Campaign B: ecommerce & WhatsApp', 'Proposals + review', 'prospect'),
    ('I', 'Personalized pitch + 3 follow-ups', 'Drafting + review', 'prospect'),
    ('J', 'Review messages & eligibility', 'Human review', 'prospect'),
    ('K', 'Approve, window & quota', 'Approval + scheduling', 'prospect'),
    ('L', 'SMTP submission & Message-ID', 'Automatic', 'settings'),
    ('M', 'Independent IMAP monitoring', 'Automatic', 'operations'),
    ('N', 'Next follow-up; stop at touch 4', 'Automatic', 'prospect'),
    ('O', 'Reply stops cold sequence', 'Automatic + conversation', 'prospect'),
    ('P', 'Global suppression', 'Automatic', 'prospect'),
    ('R', 'Review reply & promised value', 'Operator review', 'prospect'),
    ('S', 'Review value artifact', 'Assisted + review', 'prospect'),
    ('T', 'Confirm client need & buyer', 'Operator-recorded', 'prospect'),
    ('U', 'Agreed call & dated next action', 'Operator-recorded', 'prospect'),
    ('V', 'Prepare & review proposal', 'Assisted + review', 'prospect'),
    ('W', 'Record actual proposal delivery', 'Operator-recorded', 'prospect'),
    ('X', 'Agreement & payment references', 'Operator-recorded', 'prospect'),
    ('Y', 'Delivery & client acceptance', 'Operator-recorded', 'prospect'),
    ('Z', 'Outcomes & campaign learning', 'Recorded + descriptive reporting', 'learning'),
]
EDGES = [('A','B'), ('A','C'), ('B','C'), ('B','CP'), ('CP','CS'), ('CS','C'),
         ('CS','CR'), ('CS','H'), ('CR','CE'), ('CR','G'), ('CE','E3'), ('C','D'),
         ('D','E'), ('E','E1'), ('E1','F'), ('E','E2'), ('E2','E3'), ('E3','F'),
         ('E3','H'), ('E','G'), ('E','Q'), ('Q','G'), ('F','H'), ('F','J'),
         ('G','AA'), ('G','BB'), ('AA','I'), ('BB','I'), ('I','J'), ('J','K'),
         ('K','L'), ('L','M'), ('M','N'), ('N','K'), ('M','O'), ('M','P'),
         ('M','H'), ('O','R'), ('R','S'), ('S','T'), ('T','U'), ('U','V'),
         ('V','W'), ('W','X'), ('X','Y'), ('Y','Z')]
GROUPS = {'A':'discovery', 'B':'discovery', 'C':'website', 'D':'website', 'E':'website',
          'Q':'website', 'CP':'profile', 'CS':'profile', 'CR':'profile', 'CE':'contacts',
          'E1':'contacts', 'E2':'contacts', 'E3':'contacts', 'F':'verify', 'G':'qualify',
          'AA':'qualify', 'BB':'qualify', 'H':'contacts', 'I':'drafts', 'J':'approval',
          'K':'approval', 'L':'send', 'M':'replies', 'N':'send', 'O':'replies',
          'P':'replies', **{key:'sales' for key in 'RSTUVWXYZ'}}


class ReadView:
    """Reuse the business guards in one consistent SQLite read transaction."""
    def __init__(self, con):
        self.con = con

    def all(self, sql, params=()):
        return [dict(row) for row in self.con.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def get(self, key, default=''):
        row = self.one('SELECT value FROM settings WHERE key=?', (key,))
        return row['value'] if row else default


def decoded(value):
    try:
        result = json.loads(value)
        return result if isinstance(result,dict) else {}
    except (ValueError, TypeError):
        return {}


def detailed_snapshot(db, settings, lead_id=None):
    with db.connect() as con:
        con.execute('BEGIN')
        return build(ReadView(con), settings, lead_id)


def build(db, settings, lead_id):
    base = snapshot(db, settings, lead_id)
    grouped = {n['id']:n for n in base['nodes']}
    leads = db.all('SELECT * FROM leads' + (' WHERE id=?' if lead_id else ''), (lead_id,) if lead_id else ())
    ids = {lead['id'] for lead in leads}
    contacts = [c for c in db.all('SELECT * FROM contacts') if c['lead_id'] in ids]
    cids = {c['id'] for c in contacts}
    messages = [m for m in db.all('SELECT * FROM messages') if m['contact_id'] in cids]
    sales = {s['lead_id']:s for s in db.all('SELECT * FROM sales') if s['lead_id'] in ids}
    activities = [a for a in db.all('SELECT * FROM activities') if a['lead_id'] in ids]
    tasks = [t for t in db.all('SELECT * FROM tasks') if t['lead_id'] in ids]
    artifacts = [a for a in db.all('SELECT id,lead_id,state FROM deliverables') if a['lead_id'] in ids]
    proposals = [p for p in db.all('SELECT id,lead_id,state,delivery_reference,details FROM proposals') if p['lead_id'] in ids]
    events = []
    for e in db.all("""SELECT kind,contact_id,created_at,CASE
            WHEN kind='discovery' THEN json_object('lead_ids',json_extract(detail,'$.lead_ids'))
            WHEN kind='reply' THEN '{}' ELSE detail END detail FROM events
            WHERE kind IN ('discovery','reply','screenshot','performance') ORDER BY id"""):
        detail = decoded(e['detail'])
        if isinstance(detail, dict) and (e['contact_id'] in cids or detail.get('lead_id') in ids
                or (e['kind'] == 'discovery' and (not lead_id or ids.intersection(detail.get('lead_ids') or [])))):
            events.append({**e, 'detail':detail})
    jobs = []
    for j in db.all('SELECT id,kind,state,payload FROM jobs ORDER BY id'):
        payload = decoded(j['payload'])
        if not lead_id or payload.get('lead_id') in ids or payload.get('contact_id') in cids:
            jobs.append({**j, 'payload':payload})
    websites = [lead for lead in leads if lead['lead_kind'] == 'website']
    profiles = [lead for lead in leads if lead['lead_kind'] == 'profile']
    by_lead = {lead['id']:lead for lead in leads}
    # Counts are enough for the canvas: do not load every company's saved page text.
    evidence_counts = {row['lead_id']:row['n'] for row in db.all("""WITH latest AS (
        SELECT c.lead_id,c.created_at FROM crawls c JOIN
            (SELECT lead_id,MAX(id) id FROM crawls GROUP BY lead_id) x ON x.id=c.id)
        SELECT e.lead_id,COUNT(*) n FROM evidence e LEFT JOIN latest c ON c.lead_id=e.lead_id
        WHERE e.fetched_at>=COALESCE(c.created_at,0) AND e.fetched_at BETWEEN ? AND ?
        GROUP BY e.lead_id""", (time.time()-30*86400, time.time()+60))}
    evidence = {lead['id']:evidence_counts.get(lead['id'],0) for lead in leads}
    crawls = {lead['id']:db.one('SELECT created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],)) for lead in leads}
    candidates = {lead['id']:contact_candidates(db,lead['id']) for lead in leads}
    external = [c for c in contacts if by_lead[c['lead_id']]['lead_kind'] == 'profile'
                or not (c['email'].split('@')[1] == by_lead[c['lead_id']]['domain']
                        or c['email'].split('@')[1].endswith('.'+by_lead[c['lead_id']]['domain']))]
    ownership = set()
    for c in external:
        try:
            assert_contact_ownership(db,c,by_lead[c['lead_id']])
            ownership.add(c['id'])
        except ValueError:
            pass
    suppressed = {c['id'] for c in contacts if c['status'] == 'suppressed' or db.one('SELECT 1 FROM suppression WHERE email=?',(c['email'],))}
    profile_reviewed = set()
    for lead in profiles:
        try:
            assert_profile_review(db,lead)
            profile_reviewed.add(lead['id'])
        except ValueError:
            pass
    nodes = {}
    for key,title,mode,action in STAGES:
        group = grouped[GROUPS[key]]
        nodes[key] = {'id':key,'title':title,'description':'','category':group['category'],
                      'mode':mode,'action':action,'group':GROUPS[key],'state':'waiting',
                      'metric':'No relevant record yet','details':[]}
    def put(key,state,metric,description):
        nodes[key].update(state=state,metric=metric,description=description,details=[description])
    def count(key,done,total,description,ready=False):
        state = 'waiting' if not total else 'complete' if done == total else 'review' if done or ready else 'waiting'
        put(key,state,f'{done}/{total} records',description)
    def phase(kinds, lids=None):
        relevant = [j for j in jobs if j['kind'] in kinds and (lids is None or j['payload'].get('lead_id') in lids)]
        for state,label in [('running','running'),('pending','queued')]:
            if any(j['state'] == state for j in relevant):
                return label
        latest = {}
        for j in relevant:
            latest[(j['kind'],j['payload'].get('lead_id'),j['payload'].get('contact_id'))] = j['state']
        return 'failed' if 'failed' in latest.values() else None

    put('A',grouped['discovery']['state'],f'{len(leads)} prospect records','US/UK discovery hints still need review. Sourced website CSV goes directly to C.')
    searches = [e for e in events if e['kind'] == 'discovery']
    put('B',phase({'discover'}) or ('complete' if searches else 'waiting'),f'{len(searches)} recorded search runs',
        'VPS-owned browser searches LinkedIn companies and X public profiles. Login/challenge holds require operator attention; results remain unqualified.' if settings.platform_browser_enabled else
        'SearXNG or optional SerpApi. A CSV import does not require search; source access and engine limitations remain visible in research.')
    from .offers import selected_offer
    count('C',sum(bool(selected_offer(db, lead)) for lead in websites),len(websites),'Stored domains are deduplicated website candidates. Qualification records identity/buyer review; a search match alone is not verified ownership.',True)
    count('CP',len(profiles),len(profiles),'Profile-only records have no invented website or company domain.')
    finished = sum(bool(crawls[lead['id']]) and lead['status'] not in {'new','researching'} for lead in profiles)
    count('CS',finished,len(profiles),'Read the captured snapshot and named-company website search. Blocked capture, ambiguous matches and search failure are not proof of website absence.')
    profile_phase = phase({'research'},{lead['id'] for lead in profiles})
    if profile_phase or any(lead['status']=='profile_unavailable' for lead in profiles):
        nodes['CS']['state'] = profile_phase or 'blocked'
    if any(lead['status']=='researching' for lead in profiles):
        nodes['CS']['state'] = 'running'
    reviewable_profiles = [lead for lead in profiles if lead['website_status'] != 'website_found']
    count('CR',len(profile_reviewed),len(reviewable_profiles),'Review current profile identity, activity, country and website-search limitations. Website found: open its matched website record.',bool(profile_reviewed) or any(evidence[lead['id']] for lead in reviewable_profiles))
    if any(lead['website_status'] in {'ambiguous','search_unavailable'} or lead['status']=='profile_unavailable' for lead in reviewable_profiles):
        nodes['CR']['state'] = 'blocked'
    profile_candidates = sum(len(candidates[lead['id']]) for lead in profiles)
    put('CE','review' if profile_candidates else 'waiting' if profiles else 'not_applicable',f'{profile_candidates} published candidates','Captured public-profile emails remain candidates until current business/profile/inbox ownership is reviewed. No automatic probe from a candidate.')
    finished_websites = sum(bool(evidence[lead['id']]) and lead['status'] not in {'new','researching'} for lead in websites)
    count('D',finished_websites,len(websites),'Research uses robots, sitemap/page/depth budgets, HTTP and Chromium. Finished research can have partial coverage; inspect its report.',bool(websites))
    website_phase = phase({'research'},{lead['id'] for lead in websites})
    if website_phase:
        nodes['D']['state'] = website_phase
    elif any(lead['status']=='researching' for lead in websites):
        nodes['D']['state'] = 'running'
    elif any(lead['status']=='research_failed' for lead in websites):
        nodes['D']['state'] = 'blocked'
    elif any(lead['status']=='new' for lead in websites):
        nodes['D']['state'] = 'ready'
    count('E',sum(bool(evidence[lead['id']]) for lead in leads),len(leads),'Only fresh pages captured in the latest research attempt support new review. Public signals propose services; pain-point interpretation and recent-announcement meaning require review.')
    contact_phase = phase({'contact_research','professional_research','social_research'}, {lead['id'] for lead in leads})
    if contact_phase:
        nodes['E']['state'] = contact_phase
        nodes['E']['details'].append('Company/contact, professional-profile or social-post research is '+contact_phase+'. Indexed emails stay held until corroborated by captured source evidence and current employer review.')
    nodes['E']['metric'] = f'{sum(evidence.values())} current source pages'
    same_domain = len(contacts)-len(external)
    published_same_domain = 0
    publication_holds = set()
    for contact in contacts:
        if contact in external:
            continue
        try:
            assert_contact_ownership(db,contact,by_lead[contact['lead_id']])
            published_same_domain += 1
        except ValueError:
            if contact['id'] not in suppressed:
                publication_holds.add(contact['lead_id'])
    put('E1','review' if publication_holds else 'complete' if published_same_domain else 'waiting' if websites else 'not_applicable',f'{published_same_domain}/{same_domain} currently sourced company-domain contacts','A company-domain match alone cannot authorize verification. Require current saved publication evidence; buyer relevance and eligibility are separate.')
    other_candidates = sum(len(candidates[lead['id']]) for lead in websites)
    put('E2','review' if other_candidates else 'waiting' if websites else 'not_applicable',f'{other_candidates} published candidates','Other-domain published addresses are held for ownership review; indexed snippets alone are insufficient.')
    pending_candidates = sum(1 for lead in leads for c in candidates[lead['id']] if not any(x['email']==c['email'] and x['lead_id']==lead['id'] for x in contacts))
    ownership_total = len(external)+pending_candidates
    count('E3',len(ownership),ownership_total,'Use current official source and ownership notes. Source changes invalidate proof. Missing or stale proof stays held.',bool(ownership_total))
    nodes['F'].update({k:grouped['verify'][k] for k in ['state','metric','description','details']})
    nodes['G'].update({k:grouped['qualify'][k] for k in ['state','metric','description','details']})
    audits = [e for e in events if e['kind'] in {'screenshot','performance'} and
              e['created_at'] >= (crawls.get(e['detail'].get('lead_id')) or {}).get('created_at',0)]
    audited = {e['detail']['lead_id'] for e in audits if
               (e['kind']=='screenshot' and {'desktop','mobile'}.issubset(e['detail'].get('files') or {})) or
               (e['kind']=='performance' and {'desktop','mobile'}.issubset(e['detail'].get('strategies') or {}))}
    count('Q',len(audited),len(websites),'Desktop/mobile screenshots and optional PageSpeed lab evidence. Optional audit failure is separate from website crawling; no score is invented.',bool(finished_websites))
    audit_phase = phase({'screenshot','performance'},{lead['id'] for lead in websites})
    if audit_phase:
        nodes['Q']['state'] = audit_phase
    held_leads = {lead['id'] for lead in leads if lead['status'] in {'research_failed','profile_unavailable'} or lead['website_status'] in {'ambiguous','search_unavailable'}}
    held_leads.update(publication_holds)
    held_leads.update(c['lead_id'] for c in contacts if c['status']=='hold' or (c['verified_at'] and c['verification'] not in {'safe','unverified'}))
    now = time.time()
    held_leads.update(c['lead_id'] for c in contacts if c['verification']=='safe'
                      and (not c['verified_at'] or not 0 <= now-c['verified_at'] <= settings.verification_max_age_hours*3600))
    held_leads.update(c['lead_id'] for c in external if c['id'] not in ownership)
    held_leads.update(base['context_hold_lead_ids'])
    held_leads.update(next(c['lead_id'] for c in contacts if c['id']==m['contact_id']) for m in messages if m['state']=='uncertain')
    put('H','blocked' if held_leads else 'waiting',f'{len(held_leads)} businesses held','H summarizes current held records. Partial capture and candidate review remain separate. Unknown/risky verification, blocked profiles and uncertain submissions require inspection; uncertain sends never retry automatically.')
    for key,campaign in [('AA','A'),('BB','B')]:
        relevant = [lead for lead in leads if lead['campaign']==campaign]
        count(key,sum(bool(selected_offer(db, lead)) for lead in relevant),len(relevant),'Choose one source-backed offer suited to this business. WhatsApp channel presence does not establish customer permission, integrations or economic fit.',any(evidence[lead['id']] for lead in relevant))
    for key,group in [('I','drafts'),('J','approval'),('K','approval'),('L','send'),('M','replies')]:
        nodes[key].update({k:grouped[group][k] for k in ['state','metric','description','details']})
    nodes['K']['description'] = 'Recorded approval activates one reviewed sequence; submission still obeys quota, minimum spacing, local windows and fresh inbox/verification gates.'
    sent = [m for m in messages if m['state']=='sent']
    followups = [m for m in messages if m['step']>0 and m['state']=='queued' and m['due_at'] is not None]
    finished_sequences = {m['contact_id'] for m in sent if m['step']==3}
    put('N','queued' if followups else 'complete' if finished_sequences else 'waiting',f'{len(followups)} due-dated follow-ups; {len(finished_sequences)} finished sequences','Days 1/4/9/15 use actual accepted submissions and minimum spacing. Touch 4 ends the cold sequence; replies/opt-outs/holds override scheduling.')
    if followups and base['sending_paused']:
        nodes['N']['state'] = 'paused'
    reply_leads = {next(c['lead_id'] for c in contacts if c['id']==e['contact_id']) for e in events if e['kind']=='reply' and e['contact_id'] in cids}
    reply_leads.update(a['lead_id'] for a in activities if a['kind']=='reply')
    put('O','complete' if reply_leads else 'waiting',f'{len(reply_leads)} recorded conversations','A recorded human reply stops future cold touches. Continue the real conversation; do not automatically restart cold email.')
    put('P','complete' if suppressed else 'waiting',f'{len(suppressed)} associated inboxes suppressed','Opt-out/permanent recipient failures suppress the associated address globally. This is scoped visibility, not the entire global suppression count.')
    reviewed_reply = {lid for lid in reply_leads if sales.get(lid,{}).get('stage') in {'interested','qualified','call_booked','proposal','won','delivery','completed','nurture','lost'}}
    reviewed_reply.update(t['lead_id'] for t in tasks if t['lead_id'] in reply_leads and t['kind'] in {'review','followup'} and t['state']=='done')
    reviewed_reply.difference_update(t['lead_id'] for t in tasks if t['lead_id'] in reply_leads
                                    and t['kind'] in {'review','followup','audit','concept','demo'} and t['state']=='open')
    count('R',len(reviewed_reply),len(reply_leads),'Record actual reply intent and fulfill what was promised. Transport classification is automatic; commercial intent requires operator review.',bool(reply_leads))
    approved_artifacts = 0
    for artifact in artifacts:
        if artifact['state'] == 'sent':
            approved_artifacts += 1  # Actual historical delivery remains a ledger fact.
        elif artifact['state'] == 'approved':
            try:
                assert_current_artifact(db, artifact)
                approved_artifacts += 1
            except ValueError:
                pass
    count('S',approved_artifacts,len(artifacts),'Review the promised audit/concept/FAQ/WhatsApp outline before sharing. These are discussion artifacts, not deployed client services.',bool(artifacts))
    details = {lid:decoded(s['details']) for lid,s in sales.items()}
    qualified = {lid for lid,d in details.items() if lid in reply_leads and all(len(str(d.get(k,'')).strip())>=8 for k in QUALIFICATION)}
    count('T',len(qualified),len(reply_leads),'Confirmed problem, goal, success metric, buyer, budget context and timing come from the actual conversation.',bool(reply_leads))
    calls = sum(bool(details[lid].get('call_at')) and bool(details[lid].get('next_action_at'))
                and len(details[lid].get('baseline_notes', '').strip()) >= 12 for lid in qualified)
    count('U',calls,len(qualified),'Record the agreed call and dated next action when applicable. No calendar booking or invitation is sent automatically.',bool(qualified))
    reviewed_proposals = sum(p['state']=='sent' or (p['state']=='approved' and proposal_context_current(sales.get(p['lead_id']), p)) for p in proposals)
    count('V',reviewed_proposals,len(proposals),'Prepare and review scope, deliverables, exclusions, acceptance, timing, fee and commercial terms.',bool(proposals))
    delivered_proposals = [p for p in proposals if p['state']=='sent' and len(p['delivery_reference'].strip())>=12]
    count('W',len(delivered_proposals),len(proposals),'Record actual delivery with a reference after review. A delivery record does not mean this app sent the proposal.',bool(reviewed_proposals))
    won = {lid for lid,d in details.items() if lid in qualified and sales[lid]['stage'] in {'won','delivery','completed'}
           and len(d.get('agreement_reference','').strip())>=8 and len(d.get('payment_reference','').strip())>=8
           and any(p['lead_id']==lid and p['id']==d.get('proposal_id') for p in delivered_proposals)}
    count('X',len(won),len({p['lead_id'] for p in delivered_proposals}),'Agreement and initial-payment references are operator records. The app does not collect payment or independently verify receipts/signatures.',bool(delivered_proposals))
    accepted = {lid for lid in won if sales[lid]['stage']=='completed' and len(details[lid].get('acceptance_reference','').strip())>=12
                and not any(t['lead_id']==lid and t['kind']=='delivery' and t['state']=='open' for t in tasks)}
    count('Y',len(accepted),len(won),'Manage delivery tasks and record actual client acceptance. Recorded acceptance is not automatic client deployment.',bool(won))
    outcomes = sum(len(details[lid].get('outcome_notes','').strip())>=12 for lid in accepted)
    count('Z',outcomes,len(accepted),'Record measured or inconclusive outcomes. Learning reports descriptive campaign results; it does not infer causal uplift or verify revenue.',bool(accepted))
    nodes['Z']['metric'] = f'{outcomes} client outcome records · {len(sent)} SMTP-accepted messages'
    plans = [p for p in db.all('SELECT lead_id,state,kind FROM client_plans') if p['lead_id'] in ids]
    open_plans = sum(p['state'] not in {'completed','declined'} for p in plans)
    finance_entries = db.one('SELECT count(*) n FROM financial_entries WHERE voided_at IS NULL' + (' AND lead_id=?' if lead_id else ''),
                             (lead_id,) if lead_id else ())['n']
    nodes['Z']['details'].append(f'{finance_entries} actual financial entries and {open_plans} open maintenance/expansion/case-study plans. Learning includes separate currency costs/receipts and operator-managed next actions, without causal ROI or automatic publication.')
    if open_plans:
        nodes['Z']['state'] = 'review'
    for n in nodes.values():
        if not n['details']:
            n['details'] = [n['description']]
        n['details'].insert(0,'Execution: '+n['mode'])
    if lead_id:
        for key in (['C','D','E1','E2','Q'] if profiles else ['CP','CS','CR','CE']):
            nodes[key]['state'] = 'not_applicable'
        if profiles and profiles[0]['website_status']=='website_found':
            nodes['C'].update(state='review',metric='Matched website record',
                              description='Website found. Open the matched website prospect for its actual crawl/contact state.')
            nodes['C']['details'] = ['Execution: '+nodes['C']['mode'],nodes['C']['description']]
            nodes['CR']['state'] = 'not_applicable'
            nodes['CE']['state'] = 'not_applicable'
        nodes['BB' if leads[0]['campaign']=='A' else 'AA']['state'] = 'not_applicable'
    order = [key for key,_,_,_ in STAGES if key not in {'H','Z'}]
    next_key = next((key for states in [{'running','queued'},{'ready','review'},{'blocked','failed'},{'paused'}]
                     for key in order if nodes[key]['state'] in states),'A')
    return {**base,'nodes':list(nodes.values()),'edges':EDGES,
            'edge_labels':{'A->B':'Search queries','A->C':'Sourced website CSV','CS->C':'Website matched',
                           'CS->CR':'No website matched','CS->H':'Blocked, failed or ambiguous',
                           'E3->F':'Ownership reviewed','E3->H':'Unknown or stale ownership',
                           'F->J':'Fresh safe result','F->H':'Unknown, risky or invalid',
                           'M->N':'No reply','M->O':'Human reply','M->P':'Opt-out or permanent failure',
                           'M->H':'OOO, temporary failure or uncertain submission','N->K':'Next due follow-up'},
            'next_node':next_key,
            'next_action':'Open matched website prospect' if base['matched_website_lead_id'] else nodes[next_key]['title'],
            'attention_count':sum(n['state'] in {'review','blocked','failed'} for n in nodes.values()),
            'detail':True,'note':'35 business-flow nodes. Saved records and manual gates, not automatic external client actions.'}
