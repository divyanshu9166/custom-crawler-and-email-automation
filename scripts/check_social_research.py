"""Bounded deployment checks. No sends, mailbox probes, cookie export or raw contacts."""
import argparse
import asyncio
import json
import time

from outreach.config import Settings
from outreach.preferences import Preferences
from outreach.platform_browser import browser_professional_snapshot
from outreach.social_browser import browser_people_discover, browser_recent_posts


async def check(settings, *, people_query='', person_profile='', linkedin_company='', x_profile=''):
    if settings.worker_enabled or settings.sending_enabled:
        return {'state': 'controls_not_off', 'action': 'Turn Worker and Sending OFF in dashboard Settings first.'}
    if not settings.platform_browser_enabled:
        return {'state': 'browser_mode_disabled'}
    reports = []
    if people_query:
        started = time.monotonic()
        rows = await browser_people_discover(settings, people_query, 2)
        reports.append({'operation': 'linkedin_people_search', 'state': 'captured' if rows else 'unavailable',
                        'candidate_profiles': len(rows), 'engine_issues': rows.engine_issues,
                        'elapsed_seconds': round(time.monotonic()-started, 2)})
    if person_profile:
        started = time.monotonic()
        value = await browser_professional_snapshot(settings, person_profile)
        reports.append({'operation': 'linkedin_person_profile', 'state': value.get('state'),
                        'captured_sections': list(value.get('sections', {})),
                        'section_errors': value.get('section_errors', []),
                        'published_email_count': len(value.get('published_emails', [])),
                        'elapsed_seconds': round(time.monotonic()-started, 2)})
    for profile in (linkedin_company, x_profile):
        if profile:
            started = time.monotonic()
            value = await browser_recent_posts(settings, profile)
            reports.append({'operation': 'author_post_research', 'state': value.get('state'),
                            'http_status': value.get('http_status'), 'post_count': len(value.get('posts', [])),
                            'stop_reason': value.get('stop_reason'),
                            'elapsed_seconds': round(time.monotonic()-started, 2)})
    complete = bool(reports) and all(r['state'] == 'captured' and not r.get('section_errors') for r in reports)
    return {'state': 'captured' if complete else 'incomplete', 'checks': reports,
            'note': 'Bounded capture checks only. Business identity, buyer fit, email ownership and mailbox existence remain unverified. No message was sent.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--people-query', default='')
    parser.add_argument('--person-profile', default='')
    parser.add_argument('--linkedin-company', default='')
    parser.add_argument('--x-profile', default='')
    args = parser.parse_args()
    if not any(vars(args).values()):
        parser.error('Choose at least one company/profile or people query')
    settings = Settings()
    Preferences(settings)
    try:
        report = asyncio.run(check(settings, **vars(args)))
    except ValueError:
        report = {'state': 'invalid_target', 'action': 'Use a supported LinkedIn company/person or X profile URL.'}
    print(json.dumps(report, indent=2))
    return 0 if report['state'] == 'captured' else 2


if __name__ == '__main__':
    raise SystemExit(main())
