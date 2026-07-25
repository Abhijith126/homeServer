# uptime-kuma

> Self-hosted uptime & status monitoring — runs on the **apps** node · category: `monitoring`

Watches availability of every homelab service (HTTP / TCP / ping / DNS / Docker) and sends alerts. Complements **Beszel** (system metrics) on the infra node — Uptime Kuma answers "is it up?", Beszel answers "how is the box doing?".

## Access

|       |                                   |
| ----- | --------------------------------- |
| URL   | `https://status.${DOMAIN}`        |
| Local | `http://apps:${UPTIME_KUMA_PORT}` |
| Node  | `apps`                            |

## Configuration

| Variable           | Description                        | Example             |
| ------------------ | ---------------------------------- | ------------------- |
| `UPTIME_KUMA_PORT` | Host port for the web UI           | `3001`              |
| `DOCKER_DATA`      | Base dir for the config bind mount | `/opt/homelab/data` |
| `NFS_BACKUP`       | Backup target (NFS from ryzen)     | `/mnt/nfs/backup`   |
| `TZ`               | Timezone                           | `Europe/Amsterdam`  |

```bash
cp .env.example .env
$EDITOR .env
```

## Deploy

```bash
docker compose up -d
```

First run: open the UI and create the admin account.

## Volumes

| Path                         | Purpose                          | Backed up         |
| ---------------------------- | -------------------------------- | ----------------- |
| `${DOCKER_DATA}/uptime-kuma` | SQLite DB + config (`/app/data`) | yes → `backup.sh` |

## Backup / Restore

Uses the standard scripts (config is a self-contained SQLite dir):

```bash
./backup.sh --stop     # stop for a consistent SQLite snapshot
./restore.sh
```

## Upgrade

```bash
docker compose pull && docker compose up -d
```

Bump the pinned tag in `compose.yaml` (tracked by Diun).

## Links

- Upstream: https://github.com/louislam/uptime-kuma
