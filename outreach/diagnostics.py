"""Bounded audit inputs, separate from public-page quotes and business pain claims."""
import json
import math
import time

from .web import crawl_url


POLICY = ('Measurements describe this test/capture only. They do not establish lost sales, '
          'visitor behaviour or a confirmed client problem. Partial rendering cannot prove '
          'missing features or broken third-party widgets. Screenshots are not vision analysis.')


def snapshot(db, lead, now=None):
    now = time.time() if now is None else now
    result = {'reports': [], 'observations': [], 'business_pain_confirmed': False, 'policy': POLICY}
    if not lead.get('website') or lead.get('lead_kind') == 'profile':
        return result
    target = crawl_url(lead['website'])
    crawl = db.one('SELECT created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
    for kind in ('performance', 'screenshot'):
        event = db.one("SELECT id,detail,created_at FROM events WHERE kind=? AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (kind, lead['id']))
        if not event:
            result['reports'].append({'kind': kind, 'state': 'not_run'})
            continue
        report = json.loads(event['detail'])
        item = {'kind': kind, 'event_id': event['id'], 'captured_at': event['created_at']}
        if kind == 'performance':
            item['quota_limited'] = any(e.get('reason') == 'HTTP 429' for e in report.get('errors', []))
        current = 0 <= now-event['created_at'] <= 7*86400 and (not crawl or event['created_at'] >= crawl['created_at'])
        try:
            same_target = crawl_url(report.get('url', '')) == target
        except ValueError:
            same_target = False
        if not current or not same_target:
            item['state'] = 'stale' if not current else 'target_unverified'
            result['reports'].append(item)
            continue
        item.update(url=target)
        if kind == 'performance':
            item.update(state=report.get('status', 'failed'), measurements=[])
            for strategy in ('mobile', 'desktop'):
                if report.get('status') not in {'complete', 'partial'}:
                    continue
                value = report.get('strategies', {}).get(strategy, {})
                score = value.get('score')
                if (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100
                        or value.get('final_url') != target):
                    continue
                measurement = {'strategy': strategy, 'score': score, 'metrics': {}}
                for key in ('largest-contentful-paint', 'first-contentful-paint', 'total-blocking-time', 'cumulative-layout-shift'):
                    metric = value.get('metrics', {}).get(key, {})
                    number = metric.get('numericValue')
                    if type(number) in (int, float) and math.isfinite(number) and number >= 0:
                        measurement['metrics'][key] = {'numericValue': number, 'numericUnit': str(metric.get('numericUnit', ''))[:30]}
                item['measurements'].append(measurement)
                if score < 90:
                    result['observations'].append({'ref': f"performance:{event['id']}:{strategy}",
                        'kind': 'lab_measurement', 'fact': f'{strategy} Lighthouse lab performance score: {score}/100.',
                        'anchor': str(score), 'url': target, 'captured_at': event['created_at']})
        else:
            complete = report.get('complete') is True and not report.get('issues')
            item.update(state='complete' if complete else 'partial', render_issue_count=len(report.get('issues', [])))
            visual = report.get('visual', {})
            # No absence/form/drop-off assertions from a DOM count or a failed widget.
            for device, key, width in [('desktop', 'horizontalOverflow', visual.get('viewport', {}).get('width')),
                                       ('mobile', 'mobileHorizontalOverflow', 390)]:
                if complete and visual.get(key) is True and type(width) is int and width > 0:
                    result['observations'].append({'ref': f"screenshot:{event['id']}:{device}",
                        'kind': 'render_observation', 'fact': f'Horizontal page overflow was observed in our {device} capture at {width}px width.',
                        'anchor': str(width), 'url': target, 'captured_at': event['created_at']})
        result['reports'].append(item)
    return result
