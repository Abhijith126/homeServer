# Backup coverage and restore

There are exactly two Restic configurations and scheduled containers: `stacks/storage/restic` (host `storage`) and `stacks/docker/restic` (host `docker`). Both reuse the existing encrypted repository and password. The pinned image supplies Restic; `scripts/restic-scheduler.sh` replaces its entrypoint so startup never initializes repositories or forgets snapshots. No Docker socket is available to the backup containers.

The root `.env` overrides stack defaults through `make config`. Keep each host's existing `RESTIC_REPO_PATH` (normally `/mnt/hdd2/restic` on Ryzen, `/mnt/nfs/backup/restic` on Lenovo). `RESTIC_BACKUP_TIME` is HH:MM in `TZ`; defaults are 02:00 on storage and 04:00 on Docker. A root override applies to both, so avoid overlapping schedules. Failed backups are logged and the next attempt is the next daily window; health audit checks freshness. Missed windows are not caught up automatically. Manual retry in the selected Restic directory: `docker compose exec -T restic /bin/sh /backup-scheduler.sh --once`.

## Mount audit

| Persistent source | Coverage |
| --- | --- |
| Both hosts' `${DOCKER_DATA}` | `/data`, all service subdirectories, including Homarr, Portainer, Beszel, Kuma and *arr configs |
| `caddy_caddy-data` | Existing external volume mounted read-only at `/volumes/caddy-data`; certificates, keys and CA state |
| `caddy_caddy-config` | Existing external volume at `/volumes/caddy-config` |
| `pihole-unbound_unbound-state` | Existing external volume at `/volumes/unbound-state`; DNSSEC trust anchor |
| Pi-hole config and dnsmasq | Under `${DOCKER_DATA}/pihole-unbound`; tracked helper scripts retained |
| Checkout (Lenovo) | `/checkout`, includes Caddyfile, Compose/helper files and ignored local configuration; contains secrets, protect restores accordingly |
| `${MEDIA_ROOT}/{Gallery,Files,Drive}` | Storage `/nas/...`; same snapshot now carries both `homelab` and `media` tags |
| Immich PostgreSQL directory | Excluded; use `python3 scripts/immich-backup.py stacks/storage/immich` for a consistent logical export under Docker data **before** the backup window; validate export freshness separately |
| Jellyfin `jellyfin-cache`, Immich `model-cache` | Rebuildable cache volumes, deliberately excluded |
| Immich Valkey/Redis | No persistent mount declared; cache only |
| Movies, Shows, Music, Downloads | Not selected NAS backup sources; media/download mounts in *arr, Jellyfin and qBittorrent do not imply backup coverage |
| FileBrowser `${FILEBROWSER_ROOT}`, Immich `${IMMICH_LIBRARY}` overrides | Covered only if located inside selected NAS directories; explicitly add sources/mounts if using other paths |
| Docker socket, `/etc/localtime` | Runtime resources, not application backup data |
| Portfolio | Release image, no persistent application mount |
| Home Assistant VM | Outside Docker backup scope; maintain HA/Proxmox backups separately |

External volumes must already exist; Compose fails rather than silently backing up empty newly created volumes. Inventory production mounts read-only before adoption, including any manually added stacks and custom root `.env` paths. This table audits repository declarations, not the running hosts.

## Consistency

Read-only mounts prevent backup writes but do not freeze applications. Live Caddy files and raw database/config trees are best-effort file copies, not a transactionally consistent backup. Caddy certificate/config state can change during a backup; take a quiesced supplemental copy during a planned maintenance window for CA disaster recovery. For SQLite applications (Kuma, Beszel, *arr, Pi-hole, Jellyfin, FileBrowser) use their supported online export/SQLite backup API, or take a planned stop-and-backup with existing stack helpers' `--stop` option. Homarr and Portainer need application-supported exports or a quiesced copy as well. Never assume raw live database files are sufficient. No scheduled process here stops services. Test restoration of exports in isolation before relying on them.

Immich's existing helper produces a verified logical database export, but daily Restic does not automatically create one or prove its freshness. Operators must schedule/export and check it before the Storage window. The media files and database are not a single atomic snapshot. Large media runs can overlap Lenovo's window: repository locking is preserved, failures require a retry; never force-unlock an active job.

## Shared repository retention

Automatic `forget`, `prune`, initialization and cleanup are absent. Existing `apps`, `infra`, and `storage` snapshots are untouched; new Lenovo snapshots use `docker`. Disk usage can grow until an operator reviews retention.

Inspect `restic snapshots --group-by host,tags,paths` and restore representative snapshots first. A manual proposal must specify `--host docker` (or `storage`), `--tag homelab`, `--group-by host,tags,paths` and `--dry-run`; review selected IDs before removing `--dry-run`. Do not run unscoped retention in this shared repository. Do not include historical `apps` or `infra` in automatic retention. Combined storage snapshots have different paths/tags, so old groups require a separate explicit review. Any prune is a repository-wide maintenance operation; coordinate both writers, ensure a repository copy and verify capacity/locks first. This migration provides no destructive cleanup commands.

Run `docker compose exec -T restic restic check` manually in a non-overlapping maintenance window; the separate check/media containers are retired only by an operator after a verified replacement backup. Run `python3 scripts/health-audit.py storage` and `... docker` to check service and snapshot freshness. Restore helpers retain historical host selection; see [disaster recovery](disaster-recovery.md).
