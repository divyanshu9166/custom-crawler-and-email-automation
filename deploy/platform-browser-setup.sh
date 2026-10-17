#!/bin/sh
set -eu
# noVNC is published on host loopback only. Use an SSH tunnel, never a public proxy.
if [ "${#PLATFORM_BROWSER_VIEW_PASSWORD}" -ne 8 ]; then
  echo 'Set a unique 8-character PLATFORM_BROWSER_VIEW_PASSWORD locally in .env.' >&2
  exit 1
fi
umask 077
setup_site=${PLATFORM_BROWSER_SETUP_SITE:-linkedin}
case "$setup_site" in
  linkedin|x|both) ;;
  *) echo 'PLATFORM_BROWSER_SETUP_SITE must be linkedin, x or both.' >&2; exit 1 ;;
esac
Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp &
xvfb_pid=$!
cleanup() {
  trap - EXIT INT TERM
  if [ -n "${setup_pid:-}" ]; then kill -TERM "$setup_pid" 2>/dev/null || true; wait "$setup_pid" 2>/dev/null || true; fi
  kill "$xvfb_pid" ${vnc_pid:-} ${web_pid:-} 2>/dev/null || true
}
trap cleanup EXIT INT TERM
attempt=0
until [ -S /tmp/.X11-unix/X99 ]; do
  attempt=$((attempt+1))
  if [ "$attempt" -ge 25 ]; then echo 'Virtual display failed to start' >&2; exit 1; fi
  sleep 0.2
done
x11vnc -storepasswd "$PLATFORM_BROWSER_VIEW_PASSWORD" /tmp/platform-view.auth >/dev/null 2>&1
x11vnc -display :99 -localhost -rfbauth /tmp/platform-view.auth -forever -shared -quiet &
vnc_pid=$!
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 &
web_pid=$!
python scripts/manage_platform_browser.py --setup --site "$setup_site" &
setup_pid=$!
wait "$setup_pid"
