"""Bounded company-reader diagnostic. Prints structural metadata, never account data."""
import argparse
import asyncio
import json
from pathlib import Path

from outreach import platform_browser
from outreach.config import Settings
from outreach.platform_access import hold, record_hold
from outreach.preferences import Preferences


DOM_STRUCTURE = r"""expected => {
  const u=new URL(location.href);
  const expectedURL=new URL(expected);
  if(u.origin!==expectedURL.origin||u.pathname.replace(/\/$/,'')!==expectedURL.pathname.replace(/\/$/,''))
    return {expected_route:false};
  const visible=e=>!!e&&!e.closest('nav,aside,dialog,[role="dialog"],[aria-hidden="true"],[hidden]')&&e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const all=selector=>[...document.querySelectorAll(selector)];
  const labels=all('main dl dt,main dt').filter(visible).map(e=>e.innerText.replace(/\s+/g,' ').trim().slice(0,80)).slice(0,20);
  const about=all('a[href]').filter(a=>{try{return visible(a)&&a.innerText.trim().toLowerCase()==='about'&&new URL(a.href).pathname.replace(/\/$/,'')===u.pathname.replace(/\/$/,'');}catch{return false;}});
  return {expected_route:true,document_ready:document.readyState,
    first_h1_visible:visible(document.querySelector('h1')),
    visible_main_h1_count:all('main h1').filter(visible).length,
    visible_main_h2_count:all('main h2').filter(visible).length,
    visible_h1_count:all('h1').filter(visible).length,
    visible_definition_list_count:all('dl').filter(visible).length,
    definition_labels:labels,matching_about_link_count:about.length,
    main_present:!!document.querySelector('main'),
    visible_dialog_present:all('dialog,[role="dialog"]').some(e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none')};
}"""


def held_result(value):
    return {'state': 'operator_attention', **{key: value[key] for key in
            ('reason', 'http_status', 'retry_at') if key in value}}


async def check(settings, url, *, attempts=10):
    if settings.worker_enabled or settings.sending_enabled:
        return {'state': 'controls_not_off', 'action': 'Turn Worker and Sending OFF in dashboard Settings first.'}
    if not settings.platform_browser_enabled:
        return {'state': 'browser_mode_disabled'}
    platform, target = platform_browser.profile_target(url)
    if platform != 'linkedin.com':
        raise ValueError('Use a LinkedIn company URL for this diagnostic')
    if blocked := hold(settings, platform):
        return held_result(blocked)
    try:
        async with settings._platform_browser_lock:
            if blocked := hold(settings, platform):
                return held_result(blocked)
            async with platform_browser.BrowserSession(settings) as session:
                await asyncio.sleep(settings.platform_browser_delay_seconds)
                page, denied = await session.navigate(target)
                if denied:
                    if denied in {401, 403, 429, 999}:
                        record_hold(settings, platform, 'http_' + str(denied), session.last_access_issue)
                    return {'state': 'http_error', 'http_status': denied}
                reader = (Path(platform_browser.__file__).parent / 'static/platform-reader.js').read_text(encoding='utf-8')
                for attempt in range(attempts):
                    result = await page.evaluate(reader)
                    if result.get('state') != 'fields_not_ready':
                        break
                    if attempt + 1 < attempts:
                        await asyncio.sleep(1)
                output = {'state': result.get('state'), 'target': target}
                if result.get('state') == 'login_or_challenge':
                    record_hold(settings, platform, 'login_or_challenge')
                    return output
                if result.get('state') in {'captured', 'fields_not_ready'}:
                    output['structure'] = await page.evaluate(DOM_STRUCTURE, target)
                if result.get('state') == 'captured':
                    output.update(title=result.get('title', '')[:200],
                                  text_characters=len(result.get('text', '')),
                                  link_count=len(result.get('links', [])),
                                  mailto_count=len(result.get('mailto', [])))
                return output
    except platform_browser.LoginTransitionError:
        record_hold(settings, platform, 'login_or_challenge')
        return {'state': 'login_or_challenge'}
    except Exception as exc:
        output = {'state': 'browser_unavailable', 'error_type': type(exc).__name__}
        # Classify a known launch failure without printing Chromium's raw logs.
        if 'profile appears to be in use by another' in str(exc).lower():
            output['reason'] = 'profile_in_use'
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://www.linkedin.com/company/linkedin/about/')
    args = parser.parse_args()
    settings = Settings()
    Preferences(settings)
    result = asyncio.run(check(settings, args.url))
    print(json.dumps(result, indent=2))
    return 0 if result.get('state') == 'captured' else 2


if __name__ == '__main__':
    raise SystemExit(main())
