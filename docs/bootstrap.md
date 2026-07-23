# Bootstrap guide

Provision a node from bare OS to running services. Works for a brand-new machine or a fresh reinstall.

## 0. Prerequisites

- Debian/Ubuntu installed, SSH enabled, a sudo user (default `pjh10`), and a static LAN IP.
- Your SSH public key on the host (`ssh-copy-id`).
- On your workstation: Ansible (`pipx install ansible` or `uv tool install ansible`) and this repo cloned.
- A Tailscale auth key from the admin console.

## 1. Provision the host (Ansible)

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml

# edit inventory.ini → set the node's LAN IP
ansible-playbook site.yml --limit <node> --check --diff          # dry run
ansible-playbook site.yml --limit <node> -e tailscale_authkey=tskey-auth-XXXX
```

This installs Docker (+ log rotation), Tailscale, NFS, UFW, creates `/opt/homelab/data`, and (on apps/infra) mounts the NAS and installs the Portainer agent. See [../ansible/README.md](../ansible/README.md).

> **First-node ordering:** provision **ryzen** first (it's the NFS server), then apps/infra (which mount from it). `ansible-playbook site.yml` with no `--limit` does all nodes in the right play order.

## 2. Configure secrets (once, centrally)

Edit the single root config, then generate every stack's `.env`:

```bash
cp .env.example .env
$EDITOR .env            # fill in the SECRETS section (+ DOMAIN, MEDIA_ROOT, etc.)
make config             # writes stacks/<node>/<app>/.env for every stack
```

`make config` refuses to finish until every secret is set (`make config-check` verifies). Re-run it whenever you change the root `.env`. Generate keys where needed, e.g. Homarr: `openssl rand -hex 32`.

> Prefer configuring a single stack by hand (or deploying it only through Portainer)? Each stack's `.env.example` still works standalone: `cd stacks/<node>/<app> && cp .env.example .env`.

## 3. Deploy stacks

**Option A — CLI / Ansible-managed host:**

```bash
cd stacks/<node>/<app>
docker compose up -d
```

**Option B — Portainer BE (Git stack):** in the UI, *Stacks → Add stack → Git repository*, point at this repo, set the compose path to `stacks/<node>/<app>/compose.yaml`, add the env vars, and enable auto-update (polling or webhook).

Validate anything locally first:

```bash
make validate
```

## 4. Wire up the network

1. **DNS:** set your router's DHCP DNS to the infra node's IP (`PIHOLE_HOST_IP`). Add adlists in the Pi-hole UI.
2. **Reverse proxy:** point a wildcard `*.${DOMAIN}` (or per-app records) at the infra node; set `DOMAIN` + `ACME_EMAIL` in `stacks/infra/caddy/.env`. For a Tailscale-only setup use `tls internal` or a DNS-01 challenge (see the Caddyfile).
3. **Hostnames:** ensure `ryzen` / `apps` / `infra` resolve on each node (Tailscale MagicDNS, or `/etc/hosts`).
4. **Agents:** deploy `beszel-agent` and `diun` on **every** node.

## New-host quickstart (TL;DR)

```bash
ssh-copy-id pjh10@<ip>
cd ansible && ansible-playbook site.yml --limit <node> -e tailscale_authkey=tskey-...
cd ../stacks/<node>/<app> && cp .env.example .env && $EDITOR .env && docker compose up -d
```

## Scaffold a new service

```bash
make new-app NODE=apps APP=myapp CAT=tools
# edit stacks/apps/myapp/{compose.yaml,.env.example}, then deploy
```
