"""Saved provider observations. Configuration is never proof of live access."""
import json
import time

from .platform_access import access_status


def record(db, provider, operation, target, result, *, lead_id=None, elapsed=None, contacts=0):
    state = result.get('state', 'unavailable')
    db.event('source_observation', {
        'provider': provider, 'operation': operation, 'target': target, 'lead_id': lead_id,
        'state': state, 'captured': state == 'captured', 'published_contact_candidates': max(0, int(contacts)),
        'elapsed_seconds': round(elapsed, 3) if elapsed is not None else None,
        'observed_at': time.time(), 'http_status': result.get('http_status'),
        'reason': result.get('reason') or result.get('stop_reason') or result.get('error_type', ''),
        'partial': bool(result.get('section_errors')) or result.get('coverage') == 'bounded_visible_posts',
        'review_required': True,
    })


def snapshot(db, settings, lead_id=None):
    configured = {'managed_browser:linkedin.com': settings.platform_browser_enabled,
                  'managed_browser:x.com': settings.platform_browser_enabled,
                  'website': True, 'fxembed_profiles': settings.fxembed_profiles_enabled}
    seen, latest = set(), []
    for row in db.all("SELECT detail FROM events WHERE kind='source_observation' ORDER BY id DESC LIMIT 1000"):
        value = json.loads(row['detail'])
        if lead_id and value.get('lead_id') != lead_id:
            continue
        key = (value['provider'], value['operation'], value['target'], value.get('lead_id'))
        if key in seen:
            continue
        seen.add(key)
        value['fresh'] = time.time() - 30 * 86400 <= value['observed_at'] <= time.time() + 60
        latest.append(value)
    rows = []
    for provider, enabled in configured.items():
        observations = [v for v in latest if v['provider'] == provider]
        fresh = [v for v in observations if v['fresh']]
        captured = [v for v in fresh if v['captured']]
        rows.append({'provider': provider, 'configured': enabled,
                     'last_state': observations[0]['state'] if observations else 'not_tested',
                     'observed_at': observations[0]['observed_at'] if observations else None,
                     'captured_sources': len(captured),
                     'contact_sources': sum(v['published_contact_candidates'] > 0 for v in captured),
                     'published_contact_candidates': sum(v['published_contact_candidates'] for v in captured),
                     'failed_or_stale': len(observations) - len(captured)})
    return {'providers': rows, 'observations': latest[:100], 'platform_holds': access_status(settings),
            'note': 'Saved observations only; configured does not mean accessible. Captures and published contacts remain unqualified. No network probe or message was sent.'}
