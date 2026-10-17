"""Current free profile discovery for one real saved company. No contacts/probes/sends."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import research_professionals,captures
from outreach.research import add_lead,fresh_evidence
from verify_crawler_recovery_live import fingerprint


async def main(lead_id):
    normal=DB(Settings().database)
    assert normal.get('paused')=='true' and not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before=fingerprint(normal)
    lead=normal.one('SELECT * FROM leads WHERE id=?',(lead_id,))
    assert lead and lead['lead_kind']=='website'
    pages=fresh_evidence(normal,lead_id)
    assert pages,'Real saved company evidence is required; no fictional source input'
    folder=Path('data/professional-sources-live')/time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    settings=Settings(_env_file=None,data_dir=folder,worker_enabled=False,sending_enabled=False,
        platform_browser_enabled=False,auto_professional_research=False,auto_contact_research=False,
        search_provider='searxng',serpapi_key='',openai_api_key='',draft_api_key='',professional_max_profiles=2)
    db=DB(settings.database)
    lid=add_lead(db,lead['company'],lead['website'],lead['campaign'],lead['source_url'])
    db.execute('UPDATE leads SET research_notes=?,country=? WHERE id=?',(lead['research_notes'],lead['country'],lid))
    for page in pages:
        db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
            (lid,page['url'],page['title'],page['text'],page['sha256'],page['fetched_at']))
    report=await asyncio.wait_for(research_professionals(db,settings,lid),150)
    output={'checked_at':time.time(),'company':lead['company'],'website':lead['website'],
        'reused_real_company_pages':len(pages),
        'company_pages_recaptured':any(p.get('state')=='captured' for p in report.get('official_link_refresh',[])),
        'company_navigation_recaptures':sum(p.get('state')=='captured' for p in report.get('official_link_refresh',[])),
        'copied_company_evidence_preserved':True,'report':report,
        'published_profile_email_candidates':sum(len(s['published_emails']) for s in captures(db,lid)),
        'main_operational_database_unchanged':fingerprint(normal)==before,'contacts_created':0,
        'email_probes':0,'external_messages_sent':0,'developer_api_keys_used':False,
        'scope':'One real saved business; fresh free index and robots-permitted public profiles, reusing actual earlier company evidence. Not authenticated VPS access or general coverage acceptance.'}
    assert output['main_operational_database_unchanged'] and not db.one('SELECT 1 FROM contacts') and not db.one('SELECT 1 FROM messages')
    path=folder/'report.json'
    path.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    Path('data/professional-sources-live-latest.json').write_text(json.dumps({'report':str(path.resolve())}),encoding='utf-8')
    print(json.dumps(output),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--lead-id',type=int,required=True)
    asyncio.run(main(parser.parse_args().lead_id))
