# immich

> Self-hosted photo & video backup (a Google Photos alternative) — runs on the **storage** node (ryzen) · category: `media`

Multi-service stack adapted from upstream release **v3.0.3**:

| Service | Image | Role |
| --- | --- | --- |
| `immich-server` | `ghcr.io/immich-app/immich-server` | API + web + microservices |
| `immich-machine-learning` | `ghcr.io/immich-app/immich-machine-learning` | face/object/CLIP inference |
| `redis` | `valkey/valkey` (digest-pinned) | job queue / cache |
| `database` | `ghcr.io/immich-app/postgres` (vectorchord, digest-pinned) | metadata + vector search |

> Service names `redis` and `database` are intentionally kept — immich resolves them by those hostnames.

## Access

|       |                              |
| ----- | ---------------------------- |
| URL   | `https://photos.${DOMAIN}`   |
| Local | `http://ryzen:${IMMICH_PORT}` |
| Node  | `storage` (ryzen)            |

## Configuration

| Variable           | Description                                    | Example                        |
| ------------------ | ---------------------------------------------- | ------------------------------ |
| `IMMICH_VERSION`   | Pinned release tag                             | `v3.0.3`                       |
| `IMMICH_PORT`      | Host port for the web UI                       | `2283`                         |
| `IMMICH_LIBRARY`   | Photo/video library (local RAID path)          | `/mnt/storage/immich/library`  |
| `DOCKER_DATA`      | Base dir for the postgres bind mount (local!)  | `/opt/homelab/data`            |
| `NFS_BACKUP`       | Backup target for the DB dump                  | `/mnt/storage/backup`          |
| `DB_PASSWORD`      | Postgres password (**change it**, `A-Za-z0-9`) | —                              |
| `DB_USERNAME`      | Postgres user                                  | `postgres`                     |
| `DB_DATABASE_NAME` | Database name                                  | `immich`                       |

```bash
cp .env.example .env
$EDITOR .env        # set DB_PASSWORD + confirm IMMICH_LIBRARY
```

## Storage

| Path                              | Purpose                | Notes                              |
| --------------------------------- | ---------------------- | ---------------------------------- |
| `${IMMICH_LIBRARY}`               | Photos & videos        | Large — on the RAID array          |
| `${DOCKER_DATA}/immich/postgres`  | Database (metadata)    | Local disk only — never a network share |
| `model-cache` (named volume)      | ML models              | Re-downloadable                    |

## Deploy

```bash
docker compose up -d
```

## Backup / Restore

`backup.sh` dumps the **database** (the irreplaceable metadata: albums, faces, config) — not the library, which is protected by the RAID array + Duplicati.

```bash
./backup.sh            # pg_dumpall → ${NFS_BACKUP}/immich/immich-db-<ts>.sql.gz
./restore.sh           # restore newest dump (recreates the DB volume)
./restore.sh <file>    # restore a specific dump
```

See the [official backup & restore guide](https://docs.immich.app/administration/backup-and-restore).

## Upgrade

1. Read the [release notes](https://github.com/immich-app/immich/releases) for breaking changes.
2. Bump `IMMICH_VERSION` in `.env` (and refresh the digest-pinned `redis`/`database` images from the matching upstream `docker-compose.yml` if they changed).
3. `docker compose pull && docker compose up -d`

## Links

- Upstream: https://immich.app · https://github.com/immich-app/immich
- Bulk CLI upload: `ghcr.io/immich-app/immich-cli`
