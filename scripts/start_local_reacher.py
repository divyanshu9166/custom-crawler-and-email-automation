"""Start the real backend on an unused local port, without changing sender/private settings."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from reacher_smoke import check


def main():
    root = Path(__file__).resolve().parents[1]
    if not shutil.which('docker'):
        print(json.dumps({'ready': False, 'reason': 'Docker is unavailable; no backend was started and no settings changed',
                          'port': 8081, 'setup': 'Use this helper after Docker is available, or deploy the existing Linux Compose verify profile.'}))
        return 1
    settings = Settings()
    if not settings.reacher_secret:
        raise SystemExit('Configure REACHER_SECRET in the private .env first; no values changed')
    command = ['docker', 'compose', '--project-directory', str(root), '-f', str(root/'compose.yaml'),
               '-f', str(root/'deploy/reacher-local.compose.yaml'), '--profile', 'verify',
               'up', '-d', '--build', '--no-deps', 'reacher']
    print('Building/starting the pinned Reacher backend; existing services on 8080 stay untouched.', flush=True)
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if result.returncode:
        print(json.dumps({'ready': False, 'reason': 'Docker build/start failed; inspect Docker locally', 'exit_code': result.returncode}))
        return 1
    try:
        verified = check('http://127.0.0.1:8081', settings.reacher_secret)
    except RuntimeError as exc:
        print(json.dumps({'ready': False, 'reason': str(exc)}))
        return 1
    print(json.dumps({'ready': True, 'url': 'http://127.0.0.1:8081', 'check': verified,
                      'next': 'Configure REACHER_URL=http://127.0.0.1:8081 and restart the app. Sender/mailbox configuration and sending remain separate.'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
