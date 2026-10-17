# Cloudflare dashboard access on the VPS

Updated 17 October 2026. These Ubuntu commands are a deployment guide; they
have not been executed on the target VPS. The application still runs on the VPS.
Cloudflare provides its HTTPS access path and does not supply crawler CPU/RAM.

This replaces the desktop SSH-tunnel access step in
[VPS_DEPLOYMENT_COMMANDS.md](VPS_DEPLOYMENT_COMMANDS.md). First start the app
using that guide. Keep workers and prospect sending disabled during setup.

## 1. Check for an existing connector

Run in the VPS console/SSH session:

```sh
command -v cloudflared
systemctl is-active cloudflared
```

`not found`/`inactive` is not an app error; it means no matching host installation
or system service was found. A Docker-based connector will not appear here;
the Docker container list in the main deployment guide covers that case.
If an installed connector already serves n8n, keep it running. Do not reinstall
its system service or replace its tunnel configuration. A managed tunnel can
serve an additional outreach hostname; see section 6.

## 2. Install cloudflared if it is missing

Use Cloudflare's stable repository on Ubuntu 24.04. Skip the cloudflared
installation if it is already installed and in use. Install tmux separately
if needed for the temporary-link steps below.

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl tmux
sudo mkdir -p --mode=0755 /usr/share/keyrings
sudo curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
sudo chmod 0644 /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
cloudflared --version
```

Stop if an installation command fails. Repository instructions verified against
[Cloudflare's package page](https://pkg.cloudflare.com/index.html).

## 3. Start a temporary HTTPS link without a domain

Verify the application is listening first:

```sh
curl -fsS http://127.0.0.1:8000/health
tmux new -s outreach-link
```

In the tmux terminal, run:

```sh
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare prints a generated `https://...trycloudflare.com` URL. Copy that
URL. Keep this process alive. Detach from tmux with **Ctrl+B**, release both
keys, then press **D**. This returns to the VPS shell without stopping the
tunnel, and disconnecting SSH no longer closes that tmux session.

If an `outreach-link` session already exists, attach to it rather than starting
a second connector. If cloudflared reports a configuration conflict, inspect
the existing setup instead of deleting/renaming configuration used by n8n.

Quick Tunnels require no Cloudflare account/domain. They are for testing, have
no uptime guarantee, do not support SSE, and change hostname when a new tunnel
is created. Anyone with the URL can reach the login page; keep the application's
authentication enabled. Current Cloudflare versions also document optional
email authentication, but enabling it does not replace app authentication.
See [the official Quick Tunnel guide](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## 4. Set the exact browser origin

Back at the normal VPS shell:

```sh
cd "$HOME/custom-crawler-and-email-automation"
nano .env
```

Replace `PUBLIC_URL` with the actual generated HTTPS origin, without a trailing
slash/path. Keep these entries:

```dotenv
PUBLIC_URL=https://YOUR-GENERATED-HOST.trycloudflare.com
WORKER_ENABLED=false
SENDING_ENABLED=false
```

Do not literally use the example hostname. Save with Ctrl+O, Enter; exit with
Ctrl+X. Recreate only the app to load its updated environment:

```sh
sudo docker compose --profile search config --quiet
sudo docker compose --profile search up -d --no-build app
sudo docker compose ps
```

If using the optional headed LinkedIn runtime, include
`-f compose.yaml -f compose.platform-browser.yaml` after `docker compose` on
both commands. Do not accidentally switch that installation back to the normal
image/runtime.

Open the generated HTTPS URL on your computer/phone and sign in using the
dashboard credentials stored privately in `.env`. The app validates browser
Origin against `PUBLIC_URL`, so changing the setting is required for login and
settings writes. No public port-8000 binding is needed, and neither the project's
existing n8n nor a separate n8n installation is started by these commands.

## 5. Reconnect, stop or diagnose

```sh
tmux ls
tmux attach -t outreach-link
```

Ctrl+B then D detaches again. Ctrl+C while attached stops this Quick Tunnel.
A VPS reboot ends the tmux session. Create a new tunnel afterward and repeat
section 4 with its new hostname. Automatic durable service startup belongs to
the stable-hostname setup in section 6.

If the browser shows a login/settings 403, check the exact `PUBLIC_URL` and that
app was recreated. For origin connection failures, check `/health` on the VPS
and cloudflared output. The connector must remain running with allowed outbound
connectivity. Do not change firewall rules, drop caches, restart Docker or alter
n8n merely to troubleshoot the dashboard link.

## 6. Stable production address

Use a named/managed Cloudflare Tunnel and an active domain on Cloudflare for a
stable hostname, such as `outreach.your-domain.com`. Follow the
[official managed-tunnel setup](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/).

- If the existing connector already serves n8n, add an additional outreach
  hostname route to it. Do not overwrite the connector token or n8n route.
- A cloudflared process running directly on this host routes outreach HTTP to
  `http://127.0.0.1:8000`. In a connector container, localhost is that container;
  use a deliberately configured reachable app/network upstream instead.
- For a new connector, use the installation/service command Cloudflare generates
  for that tunnel, and keep its token private. Do not paste it into chat or Git.
- Set `PUBLIC_URL` to the stable HTTPS origin and recreate app as in section 4.
  Verify sign-in, settings writes and connector restart behavior.
- Cloudflare Access can protect the private dashboard. If used later, keep the
  public `/unsubscribe/*` routes reachable by
  recipients through appropriately scoped policies and verify the real flow.

Cloudflare setup does not configure mailboxes or email writing, enable research
or sending, establish platform access, or prove resource capacity. Continue the
full deployment/acceptance checklist after dashboard access is working.
