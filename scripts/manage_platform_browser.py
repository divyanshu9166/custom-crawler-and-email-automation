"""Create a dedicated local VPS browser session; sign in normally through its UI."""
import argparse
import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.browser import browser_environment
from outreach.worker import WorkerLock


async def setup(site, stop_event=None):
    from playwright.async_api import async_playwright, Error as PlaywrightError
    settings=Settings()
    profile=settings.data_dir/'platform-browser'
    profile.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=WorkerLock(profile/'session.lock')
    stop=stop_event if stop_event is not None else asyncio.Event()
    loop=asyncio.get_running_loop()
    handlers=[]
    try:
        for name in (signal.SIGINT,signal.SIGTERM):
            previous=signal.getsignal(name)
            try:
                loop.add_signal_handler(name,stop.set)
                handlers.append((name,previous,True))
            except NotImplementedError:
                signal.signal(name,lambda *_:loop.call_soon_threadsafe(stop.set))
                handlers.append((name,previous,False))
        async with async_playwright() as p:
            context=await p.chromium.launch_persistent_context(str(profile/'profile'),headless=False,
                chromium_sandbox=True,env=browser_environment(),viewport={'width':1440,'height':900},
                accept_downloads=False)
            try:
                context.on('close',lambda *_:stop.set())
                print('Sign in directly in the VPS browser. No credentials are printed or copied. Stop this setup process after finishing; then restart app with PLATFORM_BROWSER_ENABLED=true.')
                for url in (['https://www.linkedin.com/login','https://x.com/i/flow/login'] if site=='both'
                            else ['https://www.linkedin.com/login' if site=='linkedin' else 'https://x.com/i/flow/login']):
                    if stop.is_set():
                        break
                    page=await context.new_page()
                    try:
                        await page.goto(url,wait_until='domcontentloaded',
                                        timeout=settings.platform_browser_timeout_seconds*1000)
                    except PlaywrightError as exc:
                        # Keep the UI/session available for human recovery. A failed
                        # initial tab must not discard a successful login on the other
                        # platform. Never print exception text, cookies or URLs.
                        print('Initial '+('LinkedIn' if 'linkedin.com' in url else 'X')+
                              ' page unavailable ('+type(exc).__name__+'). Browser remains open for manual inspection; source access is not verified.')
                await stop.wait()
            finally:
                await context.close()
    finally:
        try:
            for name,previous,via_loop in reversed(handlers):
                if via_loop:
                    loop.remove_signal_handler(name)
                signal.signal(name,previous)
        finally:
            lock.close()


def argument_parser():
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--setup',action='store_true')
    action.add_argument('--clear-hold',choices=['linkedin.com','x.com'],
                        help='Clear only this access hold after resolving its cause; does not sign in or send')
    parser.add_argument('--site',choices=['linkedin','x','both'],default='linkedin')
    return parser


if __name__=='__main__':
    args=argument_parser().parse_args()
    if args.clear_hold:
        from outreach.platform_access import clear_hold
        clear_hold(Settings(),args.clear_hold)
        print('Cleared access hold for '+args.clear_hold+'. This does not establish source access.')
    else:
        asyncio.run(setup(args.site))
