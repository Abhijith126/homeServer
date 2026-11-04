# Homelab

Two physical servers host two Docker deployment targets and a separate Home Assistant VM.

| Target | Host | Address | Services |
| --- | --- | --- | --- |
| storage | Ryzen | 192.168.1.120 | NAS, Jellyfin, Immich, qBittorrent, FileBrowser, Backrest |
| docker | Lenovo Proxmox Docker VM | 192.168.1.121 | Caddy, Pi-hole/Unbound, Homarr, Portainer, Beszel, Uptime Kuma, Sonarr, Radarr, Prowlarr, Lidarr, Bazarr, portfolio, Backrest |
| HA VM (not a Docker target) | Lenovo Proxmox | 192.168.1.122 | Home Assistant :8123 |

Application state lives under `/opt/homelab/data` on each Docker host. Lenovo mounts Ryzen media and the shared encrypted Restic repository over NFS. One Backrest instance per Docker host manages the existing shared Restic repository; Ryzen receives Lenovo operation history. There are no Chromebox dependencies or DIUN/Home Assistant Docker stacks.

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

**Existing installations must follow [the Backrest migration and rollback procedure](docs/migration.md) before enabling backup reconciliation.** Legacy Restic jobs must be stopped manually before Backrest starts; the repository never stops them automatically.

After migration, use `make deploy NODE=storage` or `make deploy NODE=docker`. Each `stacks/<target>/<service>` remains an independent Compose project. Portainer is optional; do not let Portainer and the Git timer both manage the same project.

Fresh hosts can use [bootstrap](docs/bootstrap.md); do not run host bootstrap as a migration shortcut. See [architecture](docs/architecture.md), [backup coverage](docs/backups.md), [automation](docs/automation.md), and [network security](docs/network-security.md).

## Development

`make config` renders private Backrest desired settings too; `sudo make backrest-config NODE=...` imports/reconciles them explicitly while backup services are stopped. Pairing and first-backup verification require UI steps in the migration guide.

`make validate` renders Compose without contacting production. `python3 -m unittest discover -s tests` exercises configuration, deployment orchestration with fake Docker, backup and restore safety. CI also builds Caddy and the portfolio runtime. Secrets and private `.env` files must never be committed.
