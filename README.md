# Homelab

Two physical servers host two Docker deployment targets and a separate Home Assistant VM.

| Target | Host | Address | Services |
| --- | --- | --- | --- |
| storage | Ryzen | 192.168.1.120 | NAS, Jellyfin, Immich, qBittorrent, FileBrowser, Restic |
| docker | Lenovo Proxmox Docker VM | 192.168.1.121 | Caddy, Pi-hole/Unbound, Homarr, Portainer, Beszel, Uptime Kuma, Sonarr, Radarr, Prowlarr, Lidarr, Bazarr, portfolio, Restic |
| HA VM (not a Docker target) | Lenovo Proxmox | 192.168.1.122 | Home Assistant :8123 |

Application state lives under `/opt/homelab/data` on each Docker host. Lenovo mounts Ryzen media and the shared encrypted Restic repository over NFS. Exactly one Restic container runs on each Docker host. There are no Chromebox dependencies or DIUN/Home Assistant Docker stacks.

## Central configuration

Keep existing credentials in the ignored root `.env`:

```sh
nano .env
make config
make config-check
make validate
```

For a fresh installation only, copy `.env.example` first. Never replace an existing `.env`, repository password, or application encryption key. `STORAGE_HOST`, `DOCKER_HOST`, and `HA_HOST` select upstreams. The `has.${DOMAIN}` route remains directed to `HA_HOST:8123`. Existing URLs and published ports remain unchanged.

## Deployment

**Existing installations must follow [the incremental migration and rollback procedure](docs/migration.md) before enabling reconciliation.** Moving paths changes bind-mount metadata; a bulk deployment is not a safe first migration step. This PR performs no deployment.

After migration, use `make deploy NODE=storage` or `make deploy NODE=docker`. Each `stacks/<target>/<service>` remains an independent Compose project. Portainer is optional; do not let Portainer and the Git timer both manage the same project.

Fresh hosts can use [bootstrap](docs/bootstrap.md); do not run host bootstrap as a migration shortcut. See [architecture](docs/architecture.md), [backup coverage](docs/backups.md), [automation](docs/automation.md), and [network security](docs/network-security.md).

## Development

`make validate` renders Compose without contacting production. `python3 -m unittest discover -s tests` exercises configuration, deployment orchestration with fake Docker, backup and restore safety. CI also builds Caddy and the portfolio runtime. Secrets and private `.env` files must never be committed.
