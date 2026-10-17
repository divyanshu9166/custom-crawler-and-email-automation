"""Fresh guest-browser/public-company diagnostic. No contacts, probes or outreach."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import resolve_signal, public_snapshot
from verify_crawler_recovery_live import fingerprint


async def main(limit,timeout):
    normal=DB(Settings().database)
    assert normal.get('paused')=='true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before=fingerprint(normal)
    selected={'https://x.com/SonriaUK':'UK',
              'https://www.linkedin.com/company/fonte-coffee-roaster':'US',
              'https://www.linkedin.com/company/mz-skin-ltd.':'UK'}
    rows={}
    for event in normal.all("SELECT detail,created_at FROM events WHERE kind='prospect_signal' ORDER BY id"):
        signal=json.loads(event['detail'])
        if signal.get('source_url') in selected:
            rows[signal['source_url']]={'url':signal['source_url'],'title':signal.get('source_title',''),
                'snippet':signal.get('indexed_snippet',''),'indexed_at':event['created_at']}
    assert set(rows)==set(selected),'Use actually recorded business signals; no fictional lead inputs'
    root=Path('data/source-failover-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True,exist_ok=False)
    settings=Settings(_env_file=None,data_dir=root,worker_enabled=False,sending_enabled=False,
        platform_browser_enabled=True,platform_browser_public_fallback=True,platform_browser_headless=True,
        platform_browser_timeout_seconds=30,search_provider='searxng',serpapi_key='',
        browser_enabled=False,crawl_render_mode='never',openai_api_key='',draft_api_key='',
        auto_contact_research=False,auto_visual_audit=False)
    results=[]
    for url,market in list(selected.items())[:limit]:
        started=time.monotonic()
        result={'source_url':url,'market_hint':market,'indexed_at':rows[url]['indexed_at']}
        signal={}
        try:
            signal=await asyncio.wait_for(resolve_signal(settings,rows[url],market,['linkedin.com','x.com']),timeout)
            result.update(profile_state=signal.get('public_snapshot',{}).get('state','not_run'),
                profile_transport=signal.get('public_snapshot',{}).get('capture_method',''),
                resolution_state=signal.get('state'),website_candidate=signal.get('website',''),
                source_failover=signal.get('source_failover',{}),search=signal.get('website_search',{}))
            if signal.get('website'):
                source=signal.get('official_match_url') or signal['website']
                capture=await asyncio.wait_for(public_snapshot(settings,source),45)
                result['official_source']={'url':capture.get('url',source),'state':capture['state'],
                    'sha256':capture.get('sha256'),'published_email_candidates':len(set(capture.get('published_emails',[]))),
                    'rendered':capture.get('rendered',False)}
        except Exception as exc:
            result['error_type']=type(exc).__name__
        result['seconds']=round(time.monotonic()-started,2)
        results.append(result)
        (root/'report.json').write_text(json.dumps({'results':results,'in_progress':True},indent=2),encoding='utf-8')
        (root/f'signal-{len(results)}.json').write_text(json.dumps(signal,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    assert fingerprint(normal)==before and normal.get('paused')=='true'
    output={'checked_at':time.time(),'results':results,'main_operational_database_unchanged':True,
        'guest_session_only':True,'developer_api_keys_used':False,'paid_sources_used':False,
        'contacts_created':0,'email_probes':0,'external_messages_sent':0,
        'scope':'Known previously indexed companies; current local guest-browser and independent public sources. Not fresh prospect discovery, VPS/account acceptance, complete website audits or unrestricted access.'}
    path=root/'report.json'
    path.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    Path('data/source-failover-live-latest.json').write_text(json.dumps({'report':str(path.resolve())}),encoding='utf-8')
    print('Report: '+str(path.resolve()),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,choices=[1,2,3],default=2)
    parser.add_argument('--timeout',type=float,default=180)
    args=parser.parse_args()
    asyncio.run(main(args.limit,args.timeout))
