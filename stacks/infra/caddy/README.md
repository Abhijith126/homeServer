# caddy

> Reverse proxy with automatic HTTPS — runs on the **infra** node · category: `proxy`

Single entry point for every service. Routes live in a static **`Caddyfile`** with explicit per-node upstreams (Docker bridge networks can't span hosts, so cross-node traffic goes to node hostnames on their published ports).

## How routing works

`app.${DOMAIN}` → `reverse_proxy <node>:<port>`. The node hostnames `ryzen` / `apps` / `infra` must resolve — via **Tailscale MagicDNS** or `/etc/hosts` on the infra node.

## Configuration

| Variable     | Description                          | Example            |
| ------------ | ------------------------------------ | ------------------ |
| `DOMAIN`     | Base domain for all subdomains       | `home.example.com` |
| `ACME_EMAIL` | Let's Encrypt contact               | `you@example.com`  |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Edit `Caddyfile` to add/remove routes, then `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`.

## HTTPS options

- **Public domain** (default): automatic Let's Encrypt — needs 80/443 reachable and public DNS for `*.${DOMAIN}`.
- **Tailscale-only / no public exposure**: add `tls internal` per site, or use a **DNS-01 challenge** (Cloudflare example is in the `Caddyfile`) so you get real certs without exposing ports.

## Volumes

| Volume         | Purpose                    | Backed up             |
| -------------- | -------------------------- | --------------------- |
| `caddy-data`   | Certificates + ACME state  | no (auto re-issued)   |
| `caddy-config` | Autosaved config           | no                    |

## Links

- Upstream: https://caddyserver.com
