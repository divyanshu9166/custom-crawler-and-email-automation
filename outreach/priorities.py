"""Explainable work-queue ranking, never a prediction or a permission to send."""
import time

from .research import assert_contact_ownership
from .offers import selected_offer
from .workflow_detail import ReadView
from .mailboxes import sendable


def ranked(db, settings, lead_id=None):
    now = time.time()
    with db.connect() as con:
        con.execute('BEGIN')
        view = ReadView(con)
        leads = view.all("""SELECT l.*,
            (SELECT json_extract(e.detail,'$.state') FROM events e WHERE e.kind='preparation' AND json_extract(e.detail,'$.lead_id')=l.id ORDER BY e.id DESC LIMIT 1) preparation_state,
            (SELECT j.state FROM jobs j WHERE j.kind='prepare' AND json_extract(j.payload,'$.lead_id')=l.id ORDER BY j.id DESC LIMIT 1) preparation_job,
            (SELECT count(*) FROM contacts c WHERE c.lead_id=l.id) contact_count,
            (SELECT m.state FROM messages m JOIN contacts c ON c.id=m.contact_id WHERE c.lead_id=l.id AND m.step=0 ORDER BY m.id DESC LIMIT 1) initial_email_state,
            EXISTS(SELECT 1 FROM evidence e WHERE e.lead_id=l.id AND e.fetched_at BETWEEN ? AND ?
              AND e.fetched_at>=COALESCE((SELECT created_at FROM crawls WHERE lead_id=l.id ORDER BY id DESC LIMIT 1),0)) current_evidence
            FROM leads l""" + (' WHERE l.id=?' if lead_id else ' WHERE l.deleted_at IS NULL') + ' ORDER BY l.id DESC' + ('' if lead_id else ' LIMIT 500'),
            (now - 30*86400, now + 60, lead_id) if lead_id else (now - 30*86400, now + 60))
        contacts = view.all('SELECT c.id,c.lead_id,c.email,c.source_url,c.status,c.verification,c.verified_at FROM contacts c WHERE c.lead_id IN (' +
                            ('SELECT id FROM leads WHERE id=?' if lead_id else 'SELECT id FROM leads ORDER BY id DESC LIMIT 500') + ')',
                            (lead_id,) if lead_id else ())
        suppressed = {r['email'] for r in view.all('SELECT email FROM suppression')}
        sales = {r['lead_id']:r for r in view.all('SELECT lead_id,stage,cold_email_hold FROM sales')}
        grouped = {}
        from .activity import source_jobs, source_job
        jobs = source_jobs(view, [lead['id'] for lead in leads])
        for contact in contacts:
            grouped.setdefault(contact['lead_id'], []).append(contact)
        for lead in leads:
            lead['source_job'] = source_job(jobs.get(lead['id'], []))
            reasons, blockers = [], []
            def add(points, reason):
                reasons.append({'points': points, 'reason': reason})
            if lead['current_evidence']:
                add(20, 'Evidence refreshed in the latest attempt within 30 days')
            else:
                blockers.append('Current research evidence needed')
            reviewed = bool(selected_offer(view, lead))
            if reviewed:
                add(25, 'Business fit reviewed with a still-current source quote')
                if lead['country'] in {'US', 'UK'}:
                    add(10, 'US/UK country recorded in business review')
                if lead['service']:
                    add(15, 'One primary service selected during review')
            else:
                blockers.append('Current business, buyer and offer review needed')
            usable, safe = [], []
            for contact in grouped.get(lead['id'], []):
                if contact['email'] in suppressed or contact['status'] not in {'new', 'active'}:
                    continue
                try:
                    assert_contact_ownership(view, contact, lead)
                except ValueError:
                    continue
                usable.append(contact)
                if (sendable(settings, contact['verification']) and contact['verified_at']
                        and 0 <= now-contact['verified_at'] <= settings.verification_max_age_hours*3600):
                    safe.append(contact)
            if usable:
                add(15, 'Published contact with current ownership eligibility')
            else:
                blockers.append('Published contact ownership or contact status needs attention')
            if safe:
                add(15, 'At least one unsuppressed contact has fresh safe verification')
            else:
                blockers.append('Fresh safe technical verification needed')
            sales_record = sales.get(lead['id'], {})
            ongoing = sales_record.get('cold_email_hold') or sales_record.get('stage') not in {None, 'new', 'contacted'}
            if lead['lead_kind'] == 'profile' and lead['website_status'] != 'website_not_found':
                blockers.append('Profile lookup is blocked, ambiguous or routed to a website')
            if lead['status'] in {'researching', 'research_failed', 'profile_unavailable'}:
                blockers.append('Research is running or needs recovery')
            active_sequence = any(c['status'] == 'active' for c in grouped.get(lead['id'], []))
            lane = 'existing_conversation' if ongoing else 'active_sequence' if active_sequence else 'outreach_review' if reviewed and safe and len(blockers) == 0 else 'research_review'
            lead['priority'] = {'score': sum(r['points'] for r in reasons), 'reasons': reasons, 'blockers': blockers,
                'lane': lane, 'requires_approval': True, 'method': 'Evidence/readiness rubric v2; current workflow offer guard, not sales probability or send authorization'}
        lanes = {'outreach_review': 0, 'research_review': 1, 'active_sequence': 2, 'existing_conversation': 3}
        return sorted(leads, key=lambda lead: (lanes[lead['priority']['lane']], -lead['priority']['score'], lead['created_at'], lead['id']))
