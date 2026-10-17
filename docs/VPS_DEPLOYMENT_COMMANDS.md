# VPS deployment commands: existing n8n host

Updated 17 October 2026. Target: Ubuntu 24.04, 2 vCPU / 4 GB, with an existing
n8n installation. These commands have not been executed on the target VPS.
Run each section in order and stop if a command fails.

The full implementation/acceptance plan is
[VPS_DEPLOYMENT_CHECKLIST.md](VPS_DEPLOYMENT_CHECKLIST.md). This guide uses the
GitHub repository and stages startup so that resource inspection precedes
automatic research. Installation does not authorize prospect sending.

## 1. Inspect the host before installing

Run in the VPS console or an authenticated SSH session:

```sh
free -h
vmstat 1 5
df -h /
uname -m
sudo docker version
sudo docker compose version
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker stats --no-stream
ps -eo pid,comm,%cpu,%mem,rss --sort=-rss | head -n 16
sudo ss -ltnp
```

Inspect `available` memory and swap activity, container consumption, disk space
and listeners. The provider panel's 79% alone cannot distinguish application
usage from reclaimable cache. Inspect idle and active n8n workflows separately.
Available RAM and resource limits are different measurements.

Use the existing Docker installation. If Docker/Compose is missing, inventory
how n8n runs before installing anything. Follow the
[official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/)
only after checking existing packages; do not blindly remove/reinstall Docker
or containerd on the n8n host. The commands below require Compose v2.

The host port `127.0.0.1:8000` must be unused. If already occupied, arrange a
different loopback binding and matching proxy/tunnel target before startup.
This guide does not stop, rename, restart or reconfigure n8n. It does not start
the repository's optional `n8n` profile.

## 2. Get the project

If `git`, `python3`, `nano` or `curl` is missing, install the missing utilities:

```sh
sudo apt-get update
sudo apt-get install -y git python3 nano curl
```

Clone into a dedicated directory that does not already exist:

```sh
git clone https://github.com/divyanshu9166/custom-crawler-and-email-automation.git "$HOME/custom-crawler-and-email-automation"
cd "$HOME/custom-crawler-and-email-automation"
```

For an existing clone, enter it, inspect `git status`, and use
`git pull --ff-only` instead. Do not overwrite existing files or reset local
changes. Source code does not include the previous machine's database, settings,
evidence, browser sessions or secrets.

## 3. Create private configuration

Only for a new installation without `.env`:

```sh
python3 scripts/init_env.py
chmod 600 .env
nano .env
```

Initialization generates random credentials, prints no secrets, and refuses to
overwrite `.env`. In nano, save with Ctrl+O, Enter, and exit with Ctrl+X.
View/set the dashboard credentials privately in that editor. Do not paste the
configuration or credentials into chat or GitHub.

`ADMIN_PASSWORD` can be any nonempty password, including one character.
`API_TOKEN` is a separate application secret and still requires at least
32 characters. Initialization supplies random values for both. If replacing
the password, use a single-quoted `.env` value when it contains `$` so Compose
does not interpolate it. Keep the generated API token. A missing password or
invalid API token prevents application startup and can appear as a Cloudflare
502; startup logs identify the affected field. After editing `.env`, recreate
app with `docker compose up`;
editing the file or using `docker compose restart` alone does not refresh its
container environment. Never delete the data volume to reset a login.

For an existing installation reporting the old 16-character requirement, update
and rebuild the application image. These commands keep the current tunnel and
do not start the repository's optional n8n service:

```sh
cd "$HOME/custom-crawler-and-email-automation"
git pull --ff-only
nano .env
sudo docker compose --profile search config --quiet
sudo docker compose build app
sudo docker compose --profile search up -d --no-build --force-recreate --wait --wait-timeout 120 app
sudo docker compose ps app
curl -fsS --max-time 5 http://127.0.0.1:8000/health
```

Keep `PUBLIC_URL` equal to the active HTTPS tunnel URL, `SENDING_ENABLED=false`
and `WORKER_ENABLED=false` during this login repair. Refresh the browser with
Ctrl+F5 after the app is healthy. If sign-in details were previously changed in
Settings, the saved username/password override `.env`; use those saved details.

For the initial SSH-tunnel preview, set these existing entries:

```dotenv
PUBLIC_URL=http://localhost:18000
WORKER_ENABLED=false
SENDING_ENABLED=false
CRAWL_CONCURRENCY=1
CRAWL_RENDER_MODE=always
BROWSER_ENABLED=true
PLATFORM_BROWSER_ENABLED=false
FXEMBED_PROFILES_ENABLED=true
```

Keep the generated secret values. The FxEmbed setting enables the previously
approved third-party public X-bio hints; it does not establish native X access
or contact ownership. AI/mailbox settings may remain empty during dashboard
setup. Operational drafting needs a configured AI writer later.

The current default container ceilings are app 2560 MiB / 1.5 CPUs, Reacher
512 MiB / 0.5 CPU and SearXNG 384 MiB / 0.35 CPU. They are ceilings, not measured
requirements or reservations. Their default CPU ceilings exceed this host's two
CPUs when added together, before existing workloads. Do not infer cohosting
capacity from these defaults. Keep workers disabled until resource assessment.

## 4. Start the dashboard and search service

```sh
sudo docker compose --profile search config --quiet
sudo docker compose build app
sudo docker compose --profile search pull searxng
sudo docker compose --profile search up -d --no-build app searxng
sudo docker compose ps
curl -fsS http://127.0.0.1:8000/health
sudo docker compose logs --tail=80 app searxng
sudo docker stats --no-stream
sudo docker compose exec app python scripts/preflight.py
```

Workers and sending remain disabled; Reacher is not running yet. A successful
health request confirms liveness, not crawling, email verification or drafting.
Building images can consume substantially more resources than normal runtime;
schedule builds outside important n8n runs. If the host lacks build headroom,
build on a compatible larger machine/CI and transfer the verified images.

For Cloudflare HTTPS access instead of a desktop SSH tunnel, follow
[CLOUDFLARE_SETUP.md](CLOUDFLARE_SETUP.md). It includes installation, a temporary
domain-free link, keeping the connector alive and changing `PUBLIC_URL`.
Choose one browser origin/access method at a time.

For the SSH option, on your own computer open a separate terminal and replace
both placeholders:

```sh
ssh -N -L 18000:127.0.0.1:8000 YOUR_SSH_USER@YOUR_VPS_IP
```

Keep that terminal open, then visit **http://localhost:18000** and sign in using
the credentials in the server's `.env`. The exact hostname and port must match
`PUBLIC_URL`; `127.0.0.1` and `localhost` are different browser origins. This
tunnel does not require opening port 8000 publicly.

## 5. Add Reacher after checking build/runtime headroom

```sh
sudo docker compose --profile verify --profile search config --quiet
sudo docker compose --profile verify build reacher
sudo docker compose --profile verify --profile search up -d --no-build app reacher searxng
sudo docker compose exec app python scripts/preflight.py --network
sudo docker stats --no-stream
```

Reacher compiles pinned Rust source; its 512 MiB runtime ceiling does not limit
the build. Do not attempt a large compile while the host is already under memory
pressure. A compatible transferred image is an alternative to compiling here.

The network preflight tests SearXNG, Reacher's malformed-address/auth contract
and a single outbound TCP/25 connection. It does not send mail or verify a real
recipient. Review its JSON results; a zero process exit code alone is not a
provider-readiness result. Confirm the hosting provider permits SMTP verification
and outbound TCP/25. A block means email verification remains pending; do not
represent the source or recipient as verified.

## 6. Enable research after resource checks

First check n8n's active-workflow peaks and leave headroom for the OS, all
containers and browser startup. Select measured CPU/memory budgets before
cohosting automatic research; app ceilings are adjustable with `APP_CPU_LIMIT`
and `APP_MEMORY_LIMIT`. Reacher/SearXNG limits live in `compose.yaml`.
Do not blindly add a local LLM or an additional n8n instance.

Edit `.env` privately, change `WORKER_ENABLED=false` to `WORKER_ENABLED=true`,
and keep `SENDING_ENABLED=false`, concurrency 1 and browser rendering enabled:

```sh
nano .env
sudo docker compose --profile verify --profile search config --quiet
sudo docker compose --profile verify --profile search up -d --no-build app reacher searxng
sudo docker compose exec app python scripts/preflight.py
sudo docker stats --no-stream
```

Use Find prospects for one bounded initial query/company and inspect the source
URLs, saved pages, contact publication, crawl coverage and actual worker progress.
Do not import a large batch first. Compare n8n responsiveness, CPU, available RAM,
swap and container restarts during research. Schedule heavy jobs separately or
change capacity if cohosting degrades either workload. No production throughput
or platform-coverage acceptance is claimed by successful installation.

## 7. Domain, AI writer and mailbox

1. Point an outreach subdomain at the VPS. Add it to the existing reverse proxy;
   do not start a second proxy competing with n8n for ports 80/443.
2. Use `deploy/Caddyfile.example` only if the host uses Caddy. Otherwise add the
   equivalent route to the installed Nginx/Traefik/proxy configuration. Proxy to
   `127.0.0.1:8000` only when the proxy runs on the host; a containerized proxy
   needs an explicitly reachable upstream. Keep n8n's route intact.
3. Change `.env` `PUBLIC_URL` to the exact HTTPS outreach origin and recreate
   app using the section 6 command. Sign in at that origin. A temporary tunnel
   remains a useful transport, but it does not change the configured browser origin.
4. In Settings configure business identity and AI writer URL, key and model.
   Review real generated drafts; there is no operational template fallback.
5. Add SMTP/IMAP, postal address and sender identity when available. Verify
   SPF/DKIM/DMARC and independent inbox monitoring. Leave sending disabled and
   paused until the separately authorized controlled mailbox/pilot checks in
   [the full checklist](VPS_DEPLOYMENT_CHECKLIST.md#5-mailbox-acceptance-when-configuration-is-supplied).

Managed settings override matching `.env` values. Recreating a container does
not reset saved settings. The default source `.env` does not contain your local
workspace's prior mailbox, AI credentials or browser session.

## 8. Optional LinkedIn browser setup

Follow [section 3 of the full checklist](VPS_DEPLOYMENT_CHECKLIST.md#3-optional-vps-owned-linkedin-session):
stop only the outreach app, use its temporary loopback viewer through SSH,
sign in normally in the VPS-owned browser, close setup cleanly, and start with
both `compose.yaml` and `compose.platform-browser.yaml`. Keep the same two-file
command on subsequent updates. Do not copy desktop cookies or run setup/runtime
against the same Chrome profile simultaneously. Browser setup also consumes RAM.

Login/session presence does not prove platform access, permitted automation,
fresh discovery or email coverage. Challenges/expired sessions still need human
recovery. Free independent sources remain available when this source is held.

## 9. Back up, update and pause

For the normal, non-platform-browser compose mode shown above:

```sh
sudo docker compose exec app python scripts/backup.py --output /data/backups
```

Copy the DB backups and evidence/screenshots to private off-host storage. Also
back up `.env`, managed settings, source-cache/access-store and any browser state
privately; a database-only backup is incomplete. See section 6 of the full
checklist for consistent browser-state backup and restore requirements.

Before an update, finish the current crawl, back up, set `WORKER_ENABLED=false`
in `.env`, recreate app, and check that n8n is outside its busy window. Then:

```sh
git status --short
git pull --ff-only
sudo docker compose --profile verify --profile search config --quiet
sudo docker compose build app
sudo docker compose --profile verify --profile search up -d --no-build app reacher searxng
sudo docker compose exec app python scripts/preflight.py
```

If Dockerfiles or pinned dependency/service images changed, rebuild/pull the
affected services deliberately before `up --no-build`. Re-enable research only
after acceptance. Keep prospect sending disabled. Include the platform-browser
compose file when that mode is in use, as described in section 8.

To stop only this project's services while retaining its persistent volume:

```sh
sudo docker compose --profile verify --profile search stop app reacher searxng
```

Do not use volume deletion, system-wide prune, firewall changes or a Docker daemon
restart as routine installation steps on this shared host.
