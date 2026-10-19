import json
import re
import time
from pathlib import Path

from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.workflow_detail import detailed_snapshot


def nodes(db, settings, lead_id=None):
    return {n['id']:n for n in detailed_snapshot(db,settings,lead_id)['nodes']}


def test_detail_matches_all_documented_nodes_and_connections_without_mutation(db,settings):
    text=(Path(__file__).resolve().parents[1]/'docs/WORKFLOW.md').read_text()
    block=text.split('```mermaid',1)[1].split('```',1)[0]
    ids=set(re.findall(r'\b([A-Z][A-Z0-9]*)\[',block))
    with db.connect() as con:
        before=list(con.iterdump())
    result=detailed_snapshot(db,settings)
    assert {n['id'] for n in result['nodes']}==ids and len(ids)==35
    assert all(a in ids and b in ids for a,b in result['edges'])
    assert ('A','C') in result['edges'] and ('N','K') in result['edges']
    bare = re.sub(r'\[[^\]]*\]','',block)
    documented_edges = set(re.findall(r'\b([A-Z][A-Z0-9]*)\s*-->\s*(?:\|[^|]*\|)?\s*([A-Z][A-Z0-9]*)',bare))
    assert set(result['edges']) == documented_edges
    assert result['next_node']=='A'
    mapped={n['id']:n for n in result['nodes']}
    assert mapped['A']['state']=='ready'
    assert all(mapped[k]['state']=='waiting' for k in 'RSTUVWXYZ')
    with db.connect() as con:
        assert list(con.iterdump())==before


def test_detailed_api_auth_scope_and_mode(settings,prepared):
    client=TestClient(create_app(settings))
    assert client.get('/api/workflow?detail=true').status_code==401
    client.headers['Authorization']='Bearer '+settings.api_token
    assert len(client.get('/api/workflow').json()['nodes'])==11
    response=client.get('/api/workflow',params={'detail':True,'lead_id':prepared['lead_id']})
    assert response.status_code==200 and len(response.json()['nodes'])==35
    assert response.json()['scope']=='Bright Demo'
    assert settings.api_token not in response.text
    assert 'alex@bright-demo.com' not in response.text
    assert client.get('/api/workflow?detail=true&lead_id=99999').status_code==400
    assert client.get('/api/workflow?detail=unknown').status_code==422


def test_optional_audit_failure_does_not_falsify_crawler_status(db,settings,prepared):
    lid=prepared['lead_id']
    jid=db.enqueue('performance',{'lead_id':lid})
    db.execute("UPDATE jobs SET state='failed' WHERE id=?",(jid,))
    mapped=nodes(db,settings,lid)
    assert mapped['D']['state']=='complete'
    assert mapped['Q']['state']=='failed'
    assert mapped['CP']['state']=='not_applicable'
    assert mapped['BB']['state']=='not_applicable'
    assert mapped['T']['state']=='waiting'


def test_old_screenshot_cannot_complete_new_research_audit(db,settings,prepared):
    lid=prepared['lead_id']
    db.event('screenshot',{'lead_id':lid,'files':['fictional-old.png']})
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,'{}',time.time()+1))
    mapped=nodes(db,settings,lid)
    assert mapped['Q']['state']!='complete'
    assert mapped['E']['state']!='complete'
    assert mapped['E']['metric']=='0 current source pages'


def test_one_strategy_or_screenshot_is_partial_audit(db,settings,prepared):
    lid=prepared['lead_id']
    db.event('screenshot',{'lead_id':lid,'files':{'mobile':'fictional-mobile.png'}})
    db.event('performance',{'lead_id':lid,'strategies':{'desktop':{'score':50}}})
    assert nodes(db,settings,lid)['Q']['state']=='review'
    db.event('screenshot',{'lead_id':lid,'files':{'mobile':'fictional-mobile.png','desktop':'fictional-desktop.png'}})
    assert nodes(db,settings,lid)['Q']['state']=='complete'


def test_profile_block_and_inactive_branches_are_scoped(db,settings,prepared):
    from outreach.profiles import add_profile_lead
    lid=add_profile_lead(db,'Fictional profile','https://x.com/fictional_profile','B','UK')
    db.execute("UPDATE leads SET status='profile_unavailable',website_status='search_unavailable' WHERE id=?",(lid,))
    mapped=nodes(db,settings,lid)
    assert mapped['CS']['state']=='blocked'
    assert mapped['CR']['state']=='blocked'
    assert mapped['D']['state']=='not_applicable'
    assert mapped['AA']['state']=='not_applicable'
    assert mapped['H']['metric']=='1 businesses held'
    assert mapped['E1']['metric']=='0/0 currently sourced company-domain contacts'
    assert mapped['F']['metric']=='0/0 fresh safe'


def test_detailed_approval_cannot_combine_different_company_records(db,settings,prepared):
    from outreach.research import add_lead,add_contact
    db.execute("UPDATE contacts SET verification='unknown' WHERE id=?",(prepared['contact_id'],))
    lid=add_lead(db,'Other fictional company','https://other-demo.com','A','https://other-demo.com')
    cid=add_contact(db,lid,'owner@other-demo.com','https://other-demo.com/contact')
    db.execute("UPDATE contacts SET verification='safe',verified_at=? WHERE id=?",(time.time(),cid))
    assert nodes(db,settings)['J']['state']=='blocked'


def test_suppression_stale_monitor_and_uncertain_send_remain_visible(db,settings,active):
    lid=active['lead_id']
    cid=active['contact_id']
    db.execute("UPDATE messages SET state='sent',sent_at=? WHERE contact_id=? AND step=0",(time.time(),cid))
    db.execute("UPDATE messages SET state='uncertain' WHERE contact_id=? AND step=1",(cid,))
    db.set('imap_caught_up','true')
    db.set('imap_last_success',time.time()-600)
    db.suppress('alex@bright-demo.com','Fictional opt-out')
    mapped=nodes(db,settings,lid)
    assert mapped['F']['state']=='blocked'
    assert mapped['M']['state']=='blocked'
    assert mapped['H']['state']=='blocked'
    assert mapped['P']['metric']=='1 associated inboxes suppressed'
    assert mapped['O']['state']=='waiting'


def test_future_sales_status_without_real_references_does_not_complete_payment_or_delivery(db,settings,prepared):
    lid=prepared['lead_id']
    db.execute('INSERT INTO sales(lead_id,stage,details,updated_at) VALUES(?,?,?,?)',(lid,'completed','{}',time.time()))
    mapped=nodes(db,settings,lid)
    assert all(mapped[k]['state']!='complete' for k in 'RSTUVWXYZ')


def test_recorded_sales_references_and_inconclusive_outcome_are_separate_from_delivery_claim(db,settings,prepared):
    from outreach.sales import QUALIFICATION
    lid=prepared['lead_id']
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid,'phone','reply','Fictional buyer conversation fixture',time.time(),time.time()))
    pid=db.execute('INSERT INTO proposals(lead_id,details,body,state,delivery_reference,created_at) VALUES(?,?,?,?,?,?)',
                   (lid,'{}','Fictional proposal fixture','sent','Fictional delivery reference',time.time()))
    detail={**{key:'Fictional confirmed '+key for key in QUALIFICATION},'proposal_id':pid,
            'agreement_reference':'Fictional agreement','payment_reference':'Fictional payment',
            'acceptance_reference':'Fictional client acceptance','outcome_notes':'Inconclusive fictional pilot; no measured uplift',
            'baseline_notes':'Unknown fictional baseline; measure agreed pilot metric.',
            'call_at':time.time(),'next_action_at':time.time()+3600}
    db.execute('INSERT INTO sales(lead_id,stage,details,updated_at) VALUES(?,?,?,?)',(lid,'completed',json.dumps(detail),time.time()))
    mapped=nodes(db,settings,lid)
    assert all(mapped[k]['state']=='complete' for k in ['O','R','T','U','V','W','X','Y','Z'])
    # Draft creation now prepares an unsent discussion preview; recorded sales
    # references do not approve or deliver that artifact.
    assert mapped['S']['state']=='review'
    assert db.one('SELECT state FROM deliverables WHERE lead_id=?', (lid,))['state'] == 'draft'
    assert mapped['Z']['metric']=='1 client outcome records · 0 SMTP-accepted messages'
    assert 'does not collect payment' in mapped['X']['description']


def test_open_promised_value_task_keeps_reply_review_pending(db,settings,prepared):
    lid=prepared['lead_id']
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid,'email','reply','Fictional prospect requested an audit',time.time(),time.time()))
    db.execute('INSERT INTO sales(lead_id,stage,updated_at) VALUES(?,?,?)',(lid,'interested',time.time()))
    db.execute('INSERT INTO tasks(lead_id,kind,title,due_at,created_at) VALUES(?,?,?,?,?)',
               (lid,'audit','Fictional promised audit',time.time()+3600,time.time()))
    assert nodes(db,settings,lid)['R']['state']=='review'
