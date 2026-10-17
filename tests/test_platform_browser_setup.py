import asyncio
import signal
import sys
from types import SimpleNamespace

import pytest
from playwright.async_api import Error, TimeoutError as BrowserTimeout

from outreach.worker import WorkerLock
from scripts import manage_platform_browser


def test_direct_setup_cli_defaults_to_linkedin_and_allows_explicit_other_site():
    parser=manage_platform_browser.argument_parser()
    assert parser.parse_args(['--setup']).site=='linkedin'
    assert parser.parse_args(['--setup','--site','both']).site=='both'


@pytest.mark.parametrize('stop_after_first', [False, True])
async def test_setup_keeps_manual_browser_after_initial_navigation_failure_and_closes_cleanly(
    settings, monkeypatch, capsys, stop_after_first
):
    stop = asyncio.Event()
    visited = []
    closed = []
    previous = {name: signal.getsignal(name) for name in (signal.SIGINT, signal.SIGTERM)}

    class Page:
        async def goto(self, url, **kwargs):
            visited.append(url)
            assert kwargs['timeout'] == settings.platform_browser_timeout_seconds * 1000
            if len(visited) == 1:
                if stop_after_first:
                    stop.set()
                raise BrowserTimeout('private-token-in-exception-must-not-be-logged')
            stop.set()

    class Context:
        def on(self, *args):
            pass

        async def new_page(self):
            return Page()

        async def close(self):
            closed.append(True)

    class Runtime:
        chromium = None

        async def __aenter__(self):
            self.chromium = self
            return self

        async def __aexit__(self, *args):
            pass

        async def launch_persistent_context(self, profile, **kwargs):
            assert profile == str(settings.data_dir / 'platform-browser/profile')
            assert not kwargs['headless'] and kwargs['chromium_sandbox']
            return Context()

    monkeypatch.setattr(manage_platform_browser, 'Settings', lambda: settings)
    monkeypatch.setattr('playwright.async_api.async_playwright', Runtime)
    await manage_platform_browser.setup('both', stop_event=stop)
    assert len(visited) == (1 if stop_after_first else 2)
    assert closed == [True]
    output = capsys.readouterr().out
    assert 'Browser remains open' in output and 'private-token' not in output
    assert all(signal.getsignal(name) == handler for name, handler in previous.items())
    lock = WorkerLock(settings.data_dir / 'platform-browser/session.lock')
    lock.close()


async def test_setup_launch_failure_releases_lock_and_restores_signal_handlers(settings, monkeypatch):
    previous = {name: signal.getsignal(name) for name in (signal.SIGINT, signal.SIGTERM)}

    class Runtime:
        async def __aenter__(self):
            self.chromium = self
            return self

        async def __aexit__(self, *args):
            pass

        async def launch_persistent_context(self, *args, **kwargs):
            raise Error('synthetic browser launch failure')

    monkeypatch.setattr(manage_platform_browser, 'Settings', lambda: settings)
    monkeypatch.setattr('playwright.async_api.async_playwright', Runtime)
    with pytest.raises(Error):
        await manage_platform_browser.setup('linkedin')
    assert all(signal.getsignal(name) == handler for name, handler in previous.items())
    lock = WorkerLock(settings.data_dir / 'platform-browser/session.lock')
    lock.close()


def test_windows_session_lock_contention_closes_failed_handle_and_returns_clear_error(tmp_path, monkeypatch):
    from outreach import worker
    opened = []
    real_open = open

    def tracked_open(*args, **kwargs):
        file = real_open(*args, **kwargs)
        opened.append(file)
        return file

    def denied(*args):
        raise OSError('synthetic Windows lock contention')

    monkeypatch.setitem(sys.modules, 'fcntl', None)
    monkeypatch.setitem(sys.modules, 'msvcrt', SimpleNamespace(locking=denied, LK_NBLCK=1))
    monkeypatch.setattr(worker, 'open', tracked_open, raising=False)
    with pytest.raises(RuntimeError, match='Another worker'):
        WorkerLock(tmp_path / 'session.lock')
    assert len(opened) == 1 and opened[0].closed
