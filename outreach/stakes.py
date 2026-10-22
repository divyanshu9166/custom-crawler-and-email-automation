"""Plain-English pitch briefs: the finding, why it matters and the fix.

Deterministic, like conclusions.py. "Why it matters" is limited to published
benchmarks (Google's PageSpeed/Core Web Vitals bands, WCAG contrast minimums)
or the direct mechanical consequence of what was observed (a 404 link is a
dead end). It never asserts that the prospect is losing customers or sales.
"""
import colorsys
import re
from urllib.parse import urlsplit, unquote

LEGAL = re.compile(r'[\s,]+(?:ltd\.?|limited|llc|l\.l\.c\.|inc\.?|incorporated|plc|llp|corp\.?)$', re.I)
HUES = ((15, 'red'), (45, 'orange'), (70, 'yellow'), (155, 'green'), (195, 'teal'),
        (255, 'blue'), (290, 'purple'), (345, 'pink'), (361, 'red'))


def short_name(name):
    """'Spotless Cleaning Ltd' -> 'Spotless Cleaning'; drop SEO tails after a dash or pipe."""
    original = (name or '').strip()
    head = re.split(r'\s+[|–—-]\s+|\s*\|\s*', original)[0].strip()
    value = head if len(head) >= 3 else original
    for _ in range(2):
        value = LEGAL.sub('', value).strip(' ,')
    return value or original


def page_label(url):
    path = unquote(urlsplit(url or '').path).strip('/')
    if not path:
        return 'homepage'
    segment = re.sub(r'\.(?:html?|php|aspx?)$', '', path.split('/')[-1], flags=re.I)
    words = re.sub(r'[-_]+', ' ', segment).strip().lower()
    if not words or not re.search(r'[a-z]{3}', words) or len(words) > 40:
        return 'page'
    return words if words.endswith('page') else words + ' page'


def colour(rgb):
    """Everyday colour name from hue and lightness; greys by lightness alone."""
    h, light, sat = colorsys.rgb_to_hls(*(v/255 for v in rgb))
    if sat < .15 or light > .94 or light < .08:
        return ('white' if light > .9 else 'light grey' if light > .7 else 'grey' if light > .35
                else 'dark grey' if light > .12 else 'black')
    name = next(n for limit, n in HUES if h*360 < limit)
    if name in {'red', 'orange'} and light < .3:
        return 'brown' if name == 'orange' else 'dark red'
    if name in {'orange', 'yellow'} and light > .7 and sat < .5:
        return 'beige'
    return 'light '+name if light > .75 else 'dark '+name if light < .25 else name


def _lab(finding, device, page, name):
    primary = finding.get('primary_measurement')
    fix_text = finding.get('proposed_fix', '')
    if 'font loading' in fix_text:
        plain_fix = 'change how your fonts load, so your text and services appear straight away instead of waiting for them'
        effort = "It's a loading change, not a redesign; the site stays as it is."
    elif 'blocking CSS' in fix_text:
        plain_fix = "load the scripts and styles the first screen doesn't need after it appears, so your services appear first"
        effort = "It's a loading change, not a redesign; the site stays as it is."
    elif 'main-thread' in fix_text:
        plain_fix = 'trim or delay the heavy scripts so taps and scrolling respond straight away'
        effort = ''
    elif 'layout-shift' in fix_text:
        plain_fix = 'reserve space for the parts that jump around so the page stays still while it loads'
        effort = ''
    else:
        plain_fix = "find what's holding back the main content and load it first"
        effort = ''
    if primary:
        seconds = f"{primary['value']:.1f}".rstrip('0').rstrip('.')
        hook = f"In Google's PageSpeed test on {device}, the main content of the {name} {page} took {seconds} seconds to appear."
        why = ("Google's guideline is 2.5 seconds or less, and it rates anything over 4 seconds as poor."
               if primary['value'] > 4 else "Google's guideline is 2.5 seconds or less.")
        risk = ("That's a long blank screen for anyone opening the site on a phone." if device == 'mobile' and primary['value'] > 4
                else "That's a long wait before anyone can see what you offer." if primary['value'] > 4 else '')
        subjects = [f'{{name}} on {device}: {seconds} seconds', f'{seconds} seconds on {device}']
        number = f'{seconds} seconds'
    else:
        score = finding.get('anchor', '')
        hook = f"Google's PageSpeed test scores the {name} {page} {score}/100 on {device}."
        poor = score.isdigit() and int(score) < 50
        why = ('Google treats 90 or above as good and anything under 50 as poor.' if poor
               else 'Google treats 90 or above as good.')
        risk = ''
        subjects = [f'{{name}} scores {score}/100 on {device}', f'your {page} speed score']
        number = f'{score}/100'
    return hook, why, risk, plain_fix, effort, subjects, number


def _journey(finding, device, page, name):
    code, proof = finding.get('code'), finding.get('proof') or {}
    if code == 'broken_cta':
        status = finding.get('anchor', '404')
        label = str(proof.get('label', 'enquiry')).strip()[:60] or 'enquiry'
        error = '"page not found"' if status == '404' else '"gone"'
        hook = f'When I checked the {name} {page}, the "{label}" link returned a {status} {error} error, both times.'
        why = f'So anyone who clicks "{label}" hits a dead end instead of reaching you.'
        return (hook, why, '', 'repair the link so it goes to the right page again and check the other buttons that use it, restoring that step of the journey',
                "It's a quick fix.", [f'your "{label.lower()}" link', f'broken link on your {page}'], status)
    if code == 'text_contrast':
        contrast = proof.get('contrast') or proof
        ratio = f"{contrast.get('ratio', 0):.1f}".rstrip('0').rstrip('.')
        words = str(contrast.get('text', '')).split()
        snippet = ' '.join(words[:8]) + ('...' if len(words) > 8 else '')
        fg, bg = colour(contrast.get('foreground', [0, 0, 0])), colour(contrast.get('background', [255, 255, 255]))
        hook = (f'When I checked the {name} {page} on {device}, the text "{snippet}" was {fg} on a {bg} background, '
                f'a contrast of {ratio}:1.')
        why = (f"Accessibility guidelines (WCAG) ask for at least {contrast.get('minimum', 4.5):g}:1 contrast for text that size, "
               "so it is harder to read, especially on a phone in daylight.")
        return (hook, why, '', 'darken the text or adjust the background colour so it passes, keeping your brand colours',
                "It's a small colour change.", [f'hard-to-read text on your {page}', 'a readability fix'], 'contrast')
    if code == 'form_labels':
        count = re.search(r'(\d+) visible enquiry-form field', finding.get('fact', ''))
        count = int(count[1]) if count else len(proof.get('controls', [])) or 1
        hook = (f'When I checked the enquiry form on the {name} {page}, one field had no label attached.' if count == 1 else
                f'When I checked the enquiry form on the {name} {page}, {count} fields had no label attached.')
        why = ('Screen readers announce unlabelled fields as blank boxes, and accessibility guidelines (WCAG) '
               'expect every form field to have a label.')
        return (hook, why, '', 'add proper labels to those fields so every step of the enquiry journey is clear, keeping the form working exactly as it does now',
                "It's a small change.", [f'your {page} enquiry form', 'unlabelled form fields'], 'label')
    width = finding.get('anchor', '')
    hook = (f'When I checked the {name} {page} on a {device}-sized screen ({width} pixels wide), '
            'it was wider than the screen and scrolled sideways.')
    why = 'Part of the page sits off-screen, so people have to pan side to side to read it.'
    return (hook, why, '', "adjust the element that's too wide so the page fits the screen",
            "It's a layout fix, not a redesign.", [f'your {page} on {device}', f'{{name}} on a {device} screen'], width)


def brief(conclusion, lead):
    """One pitch brief for the strongest current finding; empty when nothing was measured."""
    findings = (conclusion or {}).get('findings') or []
    if not findings:
        return {}
    finding = findings[0]
    device = finding.get('device') or finding.get('ref', '').split(':')[-1]
    device = device if device in {'mobile', 'desktop'} else 'mobile'
    page = page_label(finding.get('url', ''))
    name = short_name(lead.get('company', ''))
    if finding.get('kind') == 'lab_measurement':
        hook, why, risk, fix, effort, subjects, number = _lab(finding, device, page, name)
    elif finding.get('kind') in {'journey_observation', 'render_observation'}:
        if finding.get('kind') == 'render_observation':
            finding = {**finding, 'code': 'page_overflow'}
        hook, why, risk, fix, effort, subjects, number = _journey(finding, device, page, name)
    else:
        return {}
    return {'diagnostic_ref': finding['ref'], 'page': page, 'device': device,
            'hook': hook, 'why_it_matters': why, 'risk_line': risk,
            'plain_fix': fix, 'effort': effort, 'key_number': number,
            'subject_ideas': [s.replace('{name}', name) for s in subjects]}
