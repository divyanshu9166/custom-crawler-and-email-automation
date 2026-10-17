"""Three explicit free-community profile controls; zero outreach/import/probes.

Third-party profile data is a research hint, never first-party freshness proof.
"""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import professional_target
from outreach.fxembed import parse_profile, BASE, MAX_BYTES
from verify_crawler_recovery_live import fingerprint

async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    folder = Path('data/fxembed-profile-check') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, worker_enabled=False, sending_enabled=False)
    output = {'checked_at': time.time(), 'results': [],
              'scope': 'Three previously observed X profile controls via a user-authorized free third-party API. Mixed target relevance; not fresh discovery, mailbox validity, current-source proof or vendor recall.'}
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False,
            headers={'User-Agent': settings.crawler_user_agent, 'Accept': 'application/json'}) as client:
        for handle in ['ssbmGooms', 'SonriaUK', 'musicplaza_la']:
            target = professional_target('https://x.com/' + handle)[1]
            row = {'profile_url': target, 'transport_url': BASE + handle, 'observed_at': time.time()}
            try:
                async with asyncio.timeout(20), client.stream('GET', BASE + handle) as response:
                    row['http_status'] = response.status_code
                    row['cache_headers'] = {k: v[:200] for k, v in response.headers.items()
                        if k in ('age', 'cache-control', 'date', 'cf-cache-status', 'x-cache')}
                    if response.status_code != 200:
                        row['state'] = 'rate_limited' if response.status_code == 429 else 'http_error'
                    elif 'application/json' not in response.headers.get('content-type', '').lower():
                        row['state'] = 'unexpected_content_type'
                    else:
                        body = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            body.extend(chunk)
                            if len(body) > MAX_BYTES:
                                raise ValueError('Community profile response exceeds byte budget')
                        payload = json.loads(body)
                        row.update(parse_profile(payload, target))
                        row['response_sha256'] = hashlib.sha256(body).hexdigest()
            except Exception as exc:
                row.update(state='unavailable', error_type=type(exc).__name__)
            output['results'].append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ('description', 'published_email_candidates')}
                | {'published_email_candidate_count': len(row.get('published_email_candidates', [])),
                   'bio_chars': len(row.get('description', ''))}), flush=True)
            if row.get('http_status') in (401, 403, 429, 999):
                output['stopped_after_denial'] = True
                break
            await asyncio.sleep(2)
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output.update(main_database_unchanged=True, external_messages_sent=0, email_probes=0,
                  contacts_imported=0, first_party_profile_email_extraction_proven=False)
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/fxembed-profile-check-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
