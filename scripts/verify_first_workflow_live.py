"""Live acceptance of first workflow, isolated from outreach and provider probes."""
import asyncio
import json
import time
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import discover_leads,research_lead,current_evidence
from outreach.research_status import snapshot
ROOT=Path('data/first-workflow-live')/time.strftime('%Y%m%d-%H%M%S')
ROOT.mkdir(parents=True,exist_ok=False)
s=Settings(_env_file=None,data_dir=ROOT,worker_enabled=False,sending_enabled=False,
           discovery_platforms='linkedin.com,x.com',discovery_max_signals=3,
           discovery_query_delay_seconds=.5,auto_visual_audit=False)
db=DB(s.database)
segments=[('A','UK','"dental clinic" London contact'),('A','US','"roofing company" Austin contact'),
          ('B','UK','"skincare" "shop" UK independent'),('B','US','"coffee roaster" Seattle shop contact')]
checks=[]
async def segment(campaign,market,query):
    started=time.time()
    error=''
    try:
        await asyncio.wait_for(discover_leads(db,s,query,campaign,market,1),120)
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
    checks.append({'campaign':campaign,'market':market,'query':query,'seconds':round(time.time()-started,2),'error':error})
    print('Discovery:',market,campaign,round(time.time()-started,1),'seconds',error,flush=True)
async def research(lid):
    started=time.time()
    error=''
    try:
        await asyncio.wait_for(research_lead(db,s,lid),180)
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
    print('Research:',lid,len(current_evidence(db,lid)),'current pages',round(time.time()-started,1),'seconds',error,flush=True)
    return {'lead_id':lid,'seconds':round(time.time()-started,2),'error':error}
async def main():
    print('Audit directory:',ROOT,flush=True)
    # Independent segments; each actual crawler retains its configured 30-page budget.
    for offset in (0,2):
        await asyncio.gather(*(segment(*v) for v in segments[offset:offset+2]))
    selected=[lead['id'] for lead in db.all("SELECT id FROM leads WHERE lead_kind='website' ORDER BY id")]
    crawls=[]
    for offset in range(0,len(selected),2):
        crawls.extend(await asyncio.gather(*(research(lid) for lid in selected[offset:offset+2])))
    before_domains={lead['domain']:lead['id'] for lead in db.all('SELECT id,domain FROM leads')}
    await asyncio.wait_for(discover_leads(db,s,segments[0][2],segments[0][0],segments[0][1],1),120)
    after_domains={lead['domain']:lead['id'] for lead in db.all('SELECT id,domain FROM leads')}
    assert all(after_domains.get(domain)==lid for domain,lid in before_domains.items()), 'Repeated discovery changed existing company identity'
    from outreach.research import add_lead
    first=db.one("SELECT * FROM leads WHERE lead_kind='website' ORDER BY id LIMIT 1")
    assert add_lead(db,first['company'],first['website'],first['campaign'],first['source_url'])==first['id'], 'Published company domain was not deduplicated'
    status=snapshot(db)
    assert db.one('SELECT count(*) n FROM messages')['n']==0
    assert db.one("SELECT count(*) n FROM events WHERE kind='verification'")['n']==0
    assert db.one('SELECT count(*) n FROM contacts WHERE verified_at IS NOT NULL')['n']==0
    evidence=[]
    for lead in status['leads']:
        evidence.append({'lead_id':lead['id'],'contacts':db.all('SELECT email,source_url,verification FROM contacts WHERE lead_id=?',(lead['id'],)),
                         'pages':[{'id':e['id'],'url':e['url'],'title':e['title'],'sha256':e['sha256'],'fetched_at':e['fetched_at'],'excerpt':e['text'][:800]} for e in current_evidence(db,lead['id'])]})
    output={'live':True,'fixtures':False,'external_mail_sent':0,'email_probes':0,'worker_enabled':False,
            'search':'Own local SearXNG http://localhost:8888','segments':checks,'crawls':crawls,
            'configured_pages_per_site':s.crawl_max_pages,'result':status,'evidence':evidence,
            'deduplication':'Repeated UK dental search reused company domain; inspect run lead IDs',
            'notes':['All discovered businesses remain unqualified. Country, buyer and offer still need exact-source review.',
                     'A contact is a published address, not proof that an inbox exists.',
                     'LinkedIn/X discovery uses indexed/public sources; blocked profiles are held, not bypassed.']}
    path=ROOT/'report.json'
    path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    Path('data/first-workflow-live-latest.json').write_text(json.dumps({'report':str(path.resolve()),'database':str(s.database.resolve())}),encoding='utf-8')
    print(json.dumps({'report':str(path),'counts':status['counts'],'segments':checks},indent=2),flush=True)
asyncio.run(main())
