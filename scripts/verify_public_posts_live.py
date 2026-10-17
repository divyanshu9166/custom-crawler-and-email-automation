"""Capture known public business posts; no timeline scraping or email activity."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.public_posts import public_post_snapshot, x_post_url
from verify_crawler_recovery_live import fingerprint


async def main(urls):
    assert 1 <= len(urls) <= 3, 'Use up to three known, actually observed public post URLs'
    urls = list(dict.fromkeys(x_post_url(u) for u in urls))
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    settings = Settings(_env_file=None, worker_enabled=False, sending_enabled=False,
                        serpapi_key='', openai_api_key='', draft_api_key='')
    posts = []
    for url in urls:
        if posts:
            await asyncio.sleep(settings.crawl_delay_seconds)
        result = await public_post_snapshot(settings, url)
        posts.append(result)
        if result.get('state') == 'rate_limited':
            break
    root = Path('data/public-posts-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    report = {'checked_at': time.time(), 'posts': posts, 'public_api_requests': len(posts),
              'captured': sum(p.get('state') == 'captured' for p in posts),
              'published_email_candidates': sum(len(p.get('published_emails', [])) for p in posts),
              'direct_profile_requests': 0, 'profile_capture_proven': False,
              'fresh_discovery_proven': False, 'private_email_access_proven': False,
              'messages_sent': 0, 'email_probes_performed': 0,
              'main_database_unchanged': fingerprint(normal) == before}
    assert report['main_database_unchanged']
    destination = root/'report.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    Path('data/public-posts-live-latest.json').write_text(json.dumps({'report': str(destination)}), encoding='utf-8')
    print(json.dumps({**{k: v for k, v in report.items() if k != 'posts'}, 'sources': [
        {'url': p['url'], 'state': p['state'], 'author': p.get('title'), 'posted_label': p.get('posted_label')}
        for p in posts]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('urls', nargs='+')
    asyncio.run(main(parser.parse_args().urls))
