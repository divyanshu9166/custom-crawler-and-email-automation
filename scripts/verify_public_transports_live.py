"""Bounded public transport checks, isolated guest browser and zero outreach/probes."""
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import profile_snapshot,public_addresses
from outreach.public_posts import public_post_snapshot,ENDPOINT,MAX_RESPONSE
from verify_crawler_recovery_live import fingerprint


async def main():
    normal=DB(Settings().database)
    assert normal.get('paused')=='true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before=fingerprint(normal)
    folder=Path('data/public-transports-live')/time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    settings=Settings(_env_file=None,data_dir=folder,worker_enabled=False,sending_enabled=False,
        platform_browser_enabled=True,platform_browser_headless=True,
        platform_browser_timeout_seconds=20,platform_browser_delay_seconds=2,crawl_request_timeout_seconds=15)
    output={'checked_at':time.time(),'guest_profiles':[],'profile_publishing':[],
        'scope':'Public-transport diagnostics on explicit observed URLs; government post and mixed-relevance guest controls are not qualified client leads. No login, credential/session transfer or challenge handling.'}
    # A first-party published post is a transport/response-contract control,
    # not a client lead or demonstration of actual email acquisition.
    post=await public_post_snapshot(settings,'https://x.com/Interior/status/507185938620219395')
    output['publication_post_control']={k:post[k] for k in ['url','state','capture_method','scope','profile_snapshot','response_sha256'] if k in post}
    output['publication_post_control'].update(published_email_candidates=len(post.get('published_emails',[])))
    for url in ['https://www.linkedin.com/in/kara-webs-403722422','https://x.com/ssbmGooms']:
        result=await profile_snapshot(settings,url)
        row={k:result[k] for k in ['url','state','capture_method','scope','http_status','error_type','observed_at'] if k in result}
        row.update(text_chars=len(result.get('text','')),published_email_candidates=len(public_addresses(result.get('text',''))))
        output['guest_profiles'].append(row)
        print(json.dumps(row),flush=True)
    for url in ['https://x.com/ssbmGooms','https://x.com/musicplaza_la']:
        await asyncio.sleep(2)
        async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
            async with client.stream('GET',ENDPOINT,params={'url':url,'omit_script':'true','dnt':'true'}) as response:
                row={'url':url,'http_status':response.status_code,'observed_at':time.time()}
                body=bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body)>MAX_RESPONSE:
                        raise ValueError('Publishing response exceeds byte budget')
                if response.status_code==200:
                    payload=json.loads(body)
                    row.update(fields=list(payload),has_bio_field='description' in payload,
                        markup_scope='timeline_anchor' if 'twitter-timeline' in payload.get('html','') else 'other',
                        returned_author=payload.get('author_name'),
                        email_strings_in_returned_markup=len(public_addresses(payload.get('html',''))),
                        biography_extraction_proven=False)
                output['profile_publishing'].append(row)
    assert normal.get('paused')=='true' and fingerprint(normal)==before
    output.update(main_operational_database_unchanged=True,contacts_imported=0,email_probes=0,
        external_messages_sent=0,paid_keys_used=False,completion_proven=False)
    path=folder/'report.json'
    path.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    Path('data/public-transports-live-latest.json').write_text(json.dumps({'report':str(path.resolve())}),encoding='utf-8')
    print('Report: '+str(path.resolve()),flush=True)


if __name__=='__main__':
    asyncio.run(main())
