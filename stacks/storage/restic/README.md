# restic (storage node)

Scheduled, encrypted, deduplicated backups via the [resticker](https://github.com/djmaze/resticker) image. Two jobs write to **one shared repo** on hdd2:

| Service | Backs up | Tag | Schedule |
| --- | --- | --- | --- |
| `restic` | `/opt/homelab/data` (all app state; excludes live Immich Postgres) | `homelab` | Wed + Sun 02:00 |
| `restic-media` | `/mnt/nas/{Gallery,Files,Drive}` (photos + documents) | `media` | Wed + Sun 04:00 |

`CHECK_CRON` runs `restic check` weekly (Sun 06:00). **Retention: `--keep-within 1m`** — every snapshot from the last month is kept (prunes older), so you can restore to any of the ~8 twice-weekly backups in the past month.

> **Immich database:** enable Immich's built-in database backup (Admin → Settings → Backup). It dumps to `Gallery/backups/`, which the `media` job captures — no separate `pg_dumpall` needed. The live `immich/postgres` dir is excluded from the app-data job on purpose.

## First-time setup

```bash
# 1. init the shared repo once (before starting the containers)
docker run --rm -e RESTIC_PASSWORD="$RESTIC_PASSWORD" \
  -v /mnt/hdd2/restic:/repo restic/restic -r /repo init

# 2. start the stack
docker compose up -d

# 3. kick off the first backups manually (media is the big ~200 GB one)
docker exec restic       backup
docker exec restic-media backup
```

After that the crons run automatically.

## Restore

```bash
docker exec restic snapshots                          # list all snapshots
docker exec restic restic restore latest --target /   # in place (stop the app first)
docker exec restic restic restore <id> --target /tmp/r --tag media   # inspect first
```

For media, the snapshot restores `/mnt/nas/{Gallery,Files,Drive}` back under `--target`.

## Config

| Var | Meaning |
| --- | --- |
| `RESTIC_REPO_PATH` | Host path of the repo (`/mnt/hdd2/restic` on ryzen) |
| `RESTIC_PASSWORD`  | Repo encryption password (shared across nodes; from root `.env`) |
| `RESTIC_BACKUP_CRON` / `RESTIC_MEDIA_CRON` / `RESTIC_CHECK_CRON` | Schedules (6-field cron) |

> Keep `RESTIC_PASSWORD` off-box (password manager). Without it the backups are unrecoverable.
