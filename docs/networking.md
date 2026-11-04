# Networking

## Access model

Two ways in, no services exposed to the public internet by default:

- **Tailscale** — a private mesh across all nodes + your devices. Remote access without port-forwarding.
- **Caddy** (docker node) — single reverse proxy terminating HTTPS and routing `app.${DOMAIN}` to the right node.

```mermaid
flowchart LR
    you["Your device"] -->|Tailscale| ts{{"Tailscale mesh"}}
    ts --> caddy["Caddy :443<br/>(docker)"]
    caddy -->|ryzen:port| storage["storage services"]
    caddy -->|.121:port| docker["Lenovo applications"]
    caddy -->|.122:8123| ha["Home Assistant VM"]
```

Cross-node traffic uses **published ports over the Tailscale/LAN interface** — Docker bridge networks are per-host, so a shared network can't span nodes. Caddy upstreams therefore point at `STORAGE_HOST`, `DOCKER_HOST` and `HA_HOST` addresses from the root `.env`.

## Reverse-proxy routes

| Subdomain | Upstream | Service |
| --- | --- | --- |
| `photos.${DOMAIN}` | `ryzen:2283` | Immich |
| `jellyfin.${DOMAIN}` | `ryzen:8096` | Jellyfin |
| `drive.${DOMAIN}` | `ryzen:8082` | FileBrowser |
| `torrent.${DOMAIN}` | `ryzen:8080` | qBittorrent |
| `sonarr.${DOMAIN}` | `docker:8989` | Sonarr |
| `radarr.${DOMAIN}` | `docker:7878` | Radarr |
| `lidarr.${DOMAIN}` | `docker:8686` | Lidarr |
| `bazarr.${DOMAIN}` | `docker:6767` | Bazarr |
| `prowlarr.${DOMAIN}` | `docker:9696` | Prowlarr |
| `server.${DOMAIN}` | `docker:7575` | Homarr |
| `has.${DOMAIN}` | `${HA_HOST}:8123` | Home Assistant |
| `uptime.${DOMAIN}` | `docker:3001` | Uptime Kuma |
| `${DOMAIN}` | `docker:3000` | Portfolio |
| `pihole.${DOMAIN}` | `docker:8081` | Pi-hole admin |
| `beszel.${DOMAIN}` | `docker:8090` | Beszel |
| `docker.${DOMAIN}` | `docker:9443` | Portainer BE (management) |

Routes live in [`stacks/docker/caddy/Caddyfile`](../stacks/docker/caddy/Caddyfile).

## Ports by node

| Node | TCP | UDP | Notes |
| --- | --- | --- | --- |
| **storage** | 111, 2049 (NFS); 2283, 8096, 8082, 8080; 9001, 45876 | 111, 2049 | Jellyfin uses host networking; qBittorrent 6881 = torrent; 9001 = Portainer agent; 45876 = Beszel agent |
| **docker** | 53, 80, 443, 8081, 8090, 9443, 8989, 7878, 8686, 6767, 9696, 7575, 3001, 3000, 45876 | 53, 443 | Lenovo Docker services; HA :8123 belongs to the separate .122 VM |

The Ansible `common` role opens exactly these on the LAN (plus SSH) and allows everything on `tailscale0`. See [../ansible/group_vars/](../ansible/).

## DNS resolution

Pi-hole is the LAN's DNS server (set it as the DHCP DNS on your router). It filters ads/trackers, then forwards to a local recursive Unbound resolver — no third-party DNS.

```mermaid
flowchart LR
    client["LAN client"] -->|:53| pihole["Pi-hole<br/>(ad/tracker filter)"]
    pihole -->|127.0.0.1#5335| unbound["Unbound<br/>(recursive + DNSSEC)"]
    unbound --> root["Root / authoritative<br/>nameservers"]
    pihole -.->|.local names| router["Router<br/>(conditional forward)"]
```

## Firewall (UFW)

Default **deny incoming**, allow outgoing. Allowed in: SSH, everything on `tailscale0`, and the per-node service ports above (from the LAN CIDR only). Managed by the Ansible `common` role.
