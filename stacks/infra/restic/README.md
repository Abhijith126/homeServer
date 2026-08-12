# restic (infra node)

Scheduled encrypted backups of this node's app state via [resticker](https://github.com/djmaze/resticker), into the **shared repo on hdd2** (reached over NFS at `/mnt/nfs/backup/restic`). Snapshots are tagged per host.

- Backs up `/opt/homelab/data` (tag `homelab`), Wed + Sun 02:30, retention `--keep-within 1m` (every snapshot from the last month kept).

## Setup

The shared repo is initialized once on the storage node. After that:

```bash
docker compose up -d
docker exec restic backup      # first run now; cron takes over after
```

## Restore

```bash
docker exec restic snapshots
docker exec restic restic restore latest --target /   # stop the app stack first
```

`RESTIC_PASSWORD` (from root `.env`) must match the other nodes. Keep it off-box.
