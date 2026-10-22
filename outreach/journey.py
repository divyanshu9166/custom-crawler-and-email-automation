"""Bounded, repeatable public enquiry-journey observations; never submit forms."""
import asyncio
import re
from urllib.parse import urlsplit, urljoin

from .web import crawl_url, domain_of


def contrast_valid(proof):
    """Recompute solid-color evidence; transparent/image/gradient cases are not inferred."""
    if not isinstance(proof, dict):
        return False
    colors = [proof.get('foreground'), proof.get('background')]
    if any(not isinstance(c, list) or len(c) != 3 or any(type(v) not in (int, float) or not 0 <= v <= 255 for v in c) for c in colors):
        return False
    size, weight, ratio = (proof.get(k) for k in ('font_size', 'font_weight', 'ratio'))
    if not all(type(v) in (int, float) and 0 < v < 10000 for v in (size, weight, ratio)):
        return False
    minimum = 3 if size >= 24 or size >= 18.66 and weight >= 700 else 4.5
    def luminance(color):
        channels = [v/255 for v in color]
        return sum((v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)*w
                   for v, w in zip(channels, (.2126, .7152, .0722)))
    a, b = map(luminance, colors)
    actual = (max(a, b)+.05)/(min(a, b)+.05)
    return (proof.get('minimum') == minimum and actual < minimum and abs(actual-ratio) < .001
            and isinstance(proof.get('selector'), str) and bool(proof['selector'])
            and isinstance(proof.get('text'), str) and 20 <= len(proof['text']) <= 140)


def capture(first, second, device, screenshot):
    """Only repeatable observations on a loaded, styled page can support copy."""
    valid = (first.get('ready') is True and second.get('ready') is True and
             first.get('styles_ready') is True and second.get('styles_ready') is True and
             first.get('url') == second.get('url') and first.get('width') == second.get('width'))
    result = {'url': second.get('url'), 'device': device, 'screenshot': screenshot,
              'state': 'checked' if valid else 'incomplete', 'findings': [], 'ctas': [],
              'limitations': 'Two DOM samples of this viewport only; no form submission or visitor analytics.'}
    if not valid:
        return result
    width = second.get('width')
    if type(width) is not int or width <= 0:
        result['state'] = 'incomplete'
        return result
    same_controls = [c for c in second.get('controls', []) if c in first.get('controls', [])]
    if same_controls:
        result['findings'].append({'code': 'form_labels', 'anchor': 'label',
            'fact': f'In two {device} DOM samples, {len(same_controls)} visible enquiry-form field(s) had no attached text label, ARIA name or title.',
            'selector': same_controls[0]['selector'], 'controls': same_controls[:3]})
    widths = [v.get('scroll_width') for v in (first, second)]
    if all(type(w) is int and w > width+8 for w in widths):
        result['findings'].append({'code': 'page_overflow', 'anchor': str(width),
            'fact': f'In two {device} captures at {width}px width, the document extended beyond the viewport.',
            'selector': 'html', 'viewport_width': width, 'document_widths': widths})
    for proof in second.get('contrast', [])[:6]:
        if proof in first.get('contrast', []) and contrast_valid(proof):
            result['findings'].append({'code': 'text_contrast', 'anchor': 'contrast',
                'fact': f'In two {device} DOM samples, text "{proof["text"]}" had solid-color contrast {proof["ratio"]:.2f}:1, below the {proof["minimum"]}:1 reference for its sampled font size.',
                'selector': proof['selector'], 'contrast': proof})
            break  # One representative affected text block per viewport, not a repeated issue dump.
    result['contrast_checked'] = min(first.get('contrast_checked', 0), second.get('contrast_checked', 0))
    result['ctas'] = [c for c in second.get('ctas', []) if c in first.get('ctas', [])]
    return result


def targets(origin, captures):
    """Only same-domain, query-free public navigation; exclude action endpoints."""
    seen, result = {crawl_url(origin)}, []
    for sample in captures:
        for cta in sample.get('ctas', []):
            try:
                url = crawl_url(cta['url'])
                parts = urlsplit(cta['url'])
                if (url in seen or parts.query or parts.fragment or domain_of(url) != domain_of(origin) or
                        re.search(r'logout|signout|unsubscribe|delete|remove|add.to.cart|cancel|confirm', parts.path, re.I)):
                    continue
            except (ValueError, KeyError):
                continue
            seen.add(url)
            result.append({**cta, 'url': url, 'source_url': sample['url'],
                           'device': sample['device'], 'screenshot': sample['screenshot']})
    result.sort(key=lambda c: not bool(re.search(r'quote|contact|enquir|inquir|book|appointment', c['label'], re.I)))
    return result[:3]


async def check_link(web, robots, origin, target):
    url = target['url']
    async def checked_get():
        current = url
        for _ in range(4):
            parts = urlsplit(current)
            if (domain_of(current) != domain_of(origin) or parts.query or parts.fragment or
                    re.search(r'logout|signout|unsubscribe|delete|remove|add.to.cart|cancel|confirm', parts.path, re.I)):
                raise ValueError('Redirect outside bounded public navigation')
            if not robots.can_fetch(web.settings.crawler_user_agent, current):
                raise ValueError('Robots denies navigation')
            response = await web.resource(current, domain_of(origin), redirects=False)
            if 300 <= response['status'] < 400:
                current = crawl_url(urljoin(current, response['headers']['location']))
            else:
                return response
        raise ValueError('Redirect budget reached')
    try:
        first = await checked_get()
        result = {'url': url, 'state': 'reachable' if first['status'] == 200 else 'unconfirmed',
                  'http_status': first['status']}
        if first['status'] not in {404, 410}:
            return result
        second = await checked_get()
        if second['status'] != first['status'] or second['url'] != first['url']:
            return result
        status = first['status']
        result.update(state='confirmed_http_error', finding={
            'code': 'broken_cta', 'anchor': str(status), 'target_url': url,
            'selector': target['selector'], 'label': target['label'], 'http_statuses': [status, status],
            'fact': f'The "{target["label"]}" link returned HTTP {status} in two public GET checks.'})
        return result
    except (ValueError, OSError, TimeoutError) as exc:
        return {'state': 'unavailable', 'url': url, 'error_type': type(exc).__name__}
    except Exception as exc:
        # Transport/denial is a limitation, not proof that the prospect's link is broken.
        return {'state': 'unavailable', 'url': url, 'error_type': type(exc).__name__}


def needs_audit(db, settings, lead):
    if not settings.journey_audit_enabled or not settings.auto_visual_audit or not settings.browser_enabled:
        return False
    if lead.get('lead_kind') == 'profile':
        return False
    import json
    import time
    started = db.one("SELECT detail,created_at FROM events WHERE kind='journey_audit_started' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (lead['id'],))
    event = db.one("SELECT detail,created_at FROM events WHERE kind='screenshot' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (lead['id'],))
    crawl = db.one('SELECT created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
    if started and 0 <= time.time()-started['created_at'] <= 7*86400 and (not crawl or started['created_at'] >= crawl['created_at']) and json.loads(started['detail']).get('url') == crawl_url(lead['website']):
        return False  # One automatic attempt per source cycle; manual audit can retry.
    if not event or not 0 <= time.time()-event['created_at'] <= 7*86400 or (crawl and event['created_at'] < crawl['created_at']):
        return True
    report = json.loads(event['detail'])
    return report.get('url') != crawl_url(lead['website']) or report.get('journey', {}).get('version') != 1


async def extend(web, robots, origin, root_visual, render_target):
    report = {'version': 1, 'captures': list(root_visual.get('journey_checks', [])),
              'links': [], 'limitations': [], 'form_submission_tested': False}
    try:
        async with asyncio.timeout(120):
            selected = targets(origin, report['captures'])
            for target in selected:
                link = await check_link(web, robots, origin, target)
                report['links'].append({**link, 'source_url': target['source_url'],
                    'device': target['device'], 'screenshot': target['screenshot']})
                if link['state'] == 'reachable' and len(report['captures']) < 6:
                    try:
                        report['captures'].extend(await render_target(target['url']))
                    except Exception as exc:
                        report['limitations'].append('Linked page capture unavailable: '+type(exc).__name__)
    except TimeoutError:
        report['limitations'].append('Targeted journey deadline reached; completed observations preserved.')
    report['state'] = 'checked' if report['captures'] and all(c['state'] == 'checked' for c in report['captures']) and not report['limitations'] and all(link['state'] in {'reachable','confirmed_http_error'} for link in report['links']) else 'partial'
    return report


def observations(report, lead, event_id, captured_at):
    """Validate scope/proof again at consumption; old or partial samples stay non-citable."""
    if not isinstance(report, dict) or report.get('version') != 1:
        return []
    result = []
    samples = [dict(c) for c in report.get('captures', []) if isinstance(c, dict) and c.get('state') == 'checked']
    samples.extend({**link, 'state': 'checked', 'url': link.get('source_url'),
                    'findings': [link['finding']]} for link in report.get('links', [])
                   if isinstance(link, dict) and link.get('state') == 'confirmed_http_error' and isinstance(link.get('finding'), dict))
    for sample in samples:
        try:
            url = crawl_url(sample['url'])
            if domain_of(url) != domain_of(lead['website']) or sample.get('device') not in {'desktop','mobile'}:
                continue
        except (ValueError, KeyError, TypeError):
            continue
        image = sample.get('screenshot', '')
        if not isinstance(image, str) or not re.fullmatch(rf"lead-{lead['id']}-\d+-[a-f0-9]{{6}}-{sample['device']}\.png", image):
            continue
        for finding in sample.get('findings', [])[:3]:
            if not isinstance(finding, dict):
                continue
            code = finding.get('code')
            if not all(isinstance(finding.get(k), str) and 0 < len(finding[k]) <= 1200 for k in ('fact','selector','anchor')):
                continue
            if code == 'broken_cta':
                try:
                    if domain_of(crawl_url(finding['target_url'])) != domain_of(lead['website']):
                        continue
                except (ValueError, KeyError):
                    continue
            if code == 'broken_cta' and (finding.get('http_statuses') not in ([404,404],[410,410]) or
                    finding.get('anchor') != str(finding['http_statuses'][0])):
                continue
            if code == 'form_labels' and not finding.get('controls'):
                continue
            if code == 'text_contrast' and not contrast_valid(finding.get('contrast')):
                continue
            if code == 'page_overflow' and not (type(finding.get('viewport_width')) is int and
                    len(finding.get('document_widths', [])) == 2 and
                    all(type(w) is int and w > finding['viewport_width']+8 for w in finding['document_widths'])):
                continue
            if code not in {'broken_cta','form_labels','page_overflow','text_contrast'}:
                continue
            priority = {'broken_cta':100,'text_contrast':90,'page_overflow':85,'form_labels':75}[code]+(sample['device']=='mobile')
            result.append({'ref':f'screenshot:{event_id}:journey{len(result)}', 'kind':'journey_observation',
                'code':code, 'fact':finding['fact'], 'anchor':finding['anchor'], 'url':url,
                'device':sample['device'], 'selector':finding['selector'], 'screenshot':image,
                'captured_at':captured_at, 'priority':priority, 'proof':finding,
                'scope':'Repeated public-page checks only; no submission, conversion measurement or confirmed business loss.'})
    return result
