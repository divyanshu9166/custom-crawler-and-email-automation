"""Bounded audit inputs, separate from public-page quotes and business pain claims."""
import json
import math
import re
import time
from urllib.parse import urlsplit

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
        current = 0 <= now-event['created_at'] <= 7*86400 and (not crawl or
            min(event['created_at'], report.get('requested_at', event['created_at'])) >= crawl['created_at'])
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
                measurement = {'strategy': strategy, 'score': score, 'metrics': {}, 'opportunities': []}
                titles = {'font-display-insight': 'Font display', 'font-display': 'Font display',
                          'render-blocking-insight': 'Render-blocking requests', 'render-blocking-resources': 'Render-blocking requests'}
                for opportunity in value.get('opportunities', [])[:12]:
                    if isinstance(opportunity, dict) and isinstance(opportunity.get('id'), str) and opportunity['id'] in titles:
                        measurement['opportunities'].append({'id': opportunity['id'], 'title': titles[opportunity['id']]})
                for key in ('largest-contentful-paint', 'first-contentful-paint', 'total-blocking-time', 'cumulative-layout-shift'):
                    metric = value.get('metrics', {}).get(key, {})
                    number = metric.get('numericValue')
                    if type(number) in (int, float) and math.isfinite(number) and number >= 0:
                        measurement['metrics'][key] = {'numericValue': number, 'numericUnit': str(metric.get('numericUnit', ''))[:30]}
                item['measurements'].append(measurement)
                if score < 90:
                    details = ' Lighthouse flagged '+', '.join(dict.fromkeys(o['title'] for o in measurement['opportunities']))+'.' if measurement['opportunities'] else ''
                    lcp = measurement['metrics'].get('largest-contentful-paint', {})
                    primary = ({'metric':'largest-contentful-paint', 'value':lcp['numericValue']/1000,
                        'anchor':f"{lcp['numericValue']/1000:g}", 'unit':'seconds'}
                        if lcp.get('numericUnit') == 'millisecond' and lcp.get('numericValue',0) > 2500 else None)
                    result['observations'].append({'ref': f"performance:{event['id']}:{strategy}",
                        'kind': 'lab_measurement', 'fact': f'{strategy} Lighthouse lab performance score: {score}/100.'+details,
                        'anchor': str(score), 'url': target, 'captured_at': event['created_at'],
                        **({'primary_measurement':primary} if primary else {})})
            public_report = urlsplit(report.get('report_url', ''))
            if (public_report.scheme == 'https' and public_report.netloc == 'pagespeed.web.dev'
                    and public_report.path.startswith('/analysis/')):
                item['report_url'] = public_report.geturl()
        else:
            complete = report.get('complete') is True and not report.get('issues')
            item.update(state='complete' if complete else 'partial', render_issue_count=len(report.get('issues', [])))
            item['screenshots'] = {device: name for device, name in report.get('files', {}).items()
                                   if device in {'desktop', 'mobile'} and isinstance(name, str)
                                   and re.fullmatch(rf"lead-{lead['id']}-\d+-[a-f0-9]{{6}}-(?:mobile|desktop)\.png", name)}
            visual = report.get('visual', {})
            from .journey import observations
            journey = report.get('journey') or {}
            item['journey'] = {'state': journey.get('state', 'not_run'),
                'checked_pages': len({c.get('url') for c in journey.get('captures', []) if c.get('state') == 'checked'}),
                'checked_links': len(journey.get('links', [])), 'limitations': journey.get('limitations', [])}
            result['observations'].extend(observations(journey, lead, event['id'], event['created_at']))
            # No absence/form/drop-off assertions from a DOM count or a failed widget.
            for device, key, width in [('desktop', 'horizontalOverflow', visual.get('viewport', {}).get('width')),
                                       ('mobile', 'mobileHorizontalOverflow', 390)]:
                if complete and visual.get(key) is True and type(width) is int and width > 0:
                    result['observations'].append({'ref': f"screenshot:{event['id']}:{device}",
                        'kind': 'render_observation', 'fact': f'Horizontal page overflow was observed in our {device} capture at {width}px width.',
                        'anchor': str(width), 'url': target, 'captured_at': event['created_at']})
        result['reports'].append(item)
    result['observations'].sort(key=lambda o: o.get('priority', 30), reverse=True)
    from .conclusions import build
    result['conclusion'] = build(result, lead.get('service', ''))
    return result
