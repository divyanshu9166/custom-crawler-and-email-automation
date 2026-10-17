"""Read-only readiness checks. Network tests are opt-in; no email is sent."""
import argparse
import json
import os
import shutil
import socket
import urllib.request

from outreach.config import Settings
from outreach.preferences import Preferences
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--network", action="store_true")
args = parser.parse_args()
s = Settings()
workspace = Preferences(s)
checks = {"python_configuration": "ok", "docker_available": bool(shutil.which("docker")),
          "managed_workspace_settings_loaded": workspace.path.exists(),
          "worker_enabled": s.worker_enabled,
          "sending_enabled": s.sending_enabled, "sending_gaps": s.sending_gaps(),
          "search_provider": s.search_provider, "reacher_configured": bool(s.reacher_secret),
          "ai_configured": bool(s.openai_api_key and s.openai_model),
          "note": "Provider accuracy, sender authentication and inbox placement require deployment validation."}
checks['platform_browser'] = {
    'enabled': s.platform_browser_enabled,
    'headless': s.platform_browser_headless,
    'public_fallback': s.platform_browser_public_fallback,
    'profile_directory_present': (s.data_dir / 'platform-browser/profile').is_dir(),
    'display_required': s.platform_browser_enabled and not s.platform_browser_headless,
    'display_configured': bool(os.environ.get('DISPLAY')),
    'authenticated_access': 'not established by configuration or profile-directory presence',
    'search_steps': s.platform_browser_search_steps,
    'search_pages': s.platform_browser_search_pages,
    'search_capture_timeout_seconds': s.platform_browser_search_timeout_seconds,
}
if s.browser_enabled or s.platform_browser_enabled:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as browser_runtime:
            checks["chromium_installed"] = Path(browser_runtime.chromium.executable_path).is_file()
    except Exception as exc:
        checks["chromium_installed"] = type(exc).__name__
checks["crawler"] = {"render_mode": s.crawl_render_mode, "pages": s.crawl_max_pages,
                     "depth": s.crawl_max_depth, "concurrency": s.crawl_concurrency,
                     "resource_concurrency": s.browser_resource_concurrency}
checks['social_research'] = {
    'linkedin_people_search': s.linkedin_people_search_enabled,
    'linkedin_experience': s.linkedin_profile_experience_enabled,
    'linkedin_contact_info_opt_in': s.linkedin_contact_info_enabled,
    'author_posts': s.social_posts_enabled,
    'profiles_per_prospect': s.social_posts_max_profiles,
    'posts_per_profile': s.social_posts_max_posts,
    'note': 'Configuration only. Saved provider outcomes are in dashboard Source access and extraction.',
}
if args.network:
    for name, url in [("search", s.searxng_url + "/search?q=example&format=json")]:
        try:
            req = urllib.request.Request(url, headers={"x-reacher-secret": s.reacher_secret} if name == "reacher" else {})
            with urllib.request.urlopen(req, timeout=10) as response:
                checks[name] = f"HTTP {response.status}"
        except Exception as exc:
            checks[name] = type(exc).__name__
    # A different service can answer HTTP 200 on the configured port. Check the
    # actual invalid-syntax/auth contract; never submit a real recipient here.
    from reacher_smoke import check as check_reacher
    if not s.reacher_secret:
        checks["reacher"] = {"ready": False, "reason": "Configure the backend header secret first"}
    else:
        try:
            checks["reacher"] = {"ready": True, **check_reacher(s.reacher_url, s.reacher_secret, attempts=1, path=s.reacher_path)}
        except RuntimeError as exc:
            checks["reacher"] = {"ready": False, "reason": str(exc)}
        except Exception as exc:
            checks["reacher"] = {"ready": False, "reason": type(exc).__name__}
    try:
        with socket.create_connection(("gmail-smtp-in.l.google.com", 25), timeout=10):
            checks["outbound_port_25"] = "connection established; no SMTP commands or email sent"
    except Exception as exc:
        checks["outbound_port_25"] = type(exc).__name__
print(json.dumps(checks, indent=2))
