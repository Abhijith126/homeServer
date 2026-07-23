# <app>

> <one-line description> — runs on the **<node>** node · category: `<category>`

## Overview

TODO: what this service does and why it is here.

## Access

|         |                                        |
| ------- | -------------------------------------- |
| URL     | `https://<app>.${DOMAIN}` (via Caddy)  |
| Local   | `http://<node-ip>:${<APP>_PORT}`       |
| Node    | `<node>`                               |

## Configuration

| Variable      | Description                | Example           |
| ------------- | -------------------------- | ----------------- |
| `<APP>_PORT`  | Host port for the web UI   | `8080`            |
| `PUID`/`PGID` | Owner of config/data       | `1000`            |
| `TZ`          | Timezone                   | `Europe/Amsterdam`|

```bash
cp .env.example .env
$EDITOR .env
```

## Deploy

```bash
# CLI / Ansible
docker compose up -d

# Portainer: add as a Git stack pointing at stacks/<node>/<app>
```

## Volumes

| Path                     | Purpose             | Backed up          |
| ------------------------ | ------------------- | ------------------ |
| `${DOCKER_DATA}/<app>`   | Config (bind mount) | yes → `backup.sh`  |

## Backup / Restore

```bash
./backup.sh            # tar config → ${NFS_BACKUP}/<app>/
./backup.sh --stop     # stop container during backup (consistent snapshot)
./restore.sh           # restore newest archive
./restore.sh <file>    # restore a specific archive
```

## Upgrade

```bash
docker compose pull && docker compose up -d
```

## Links

- Upstream: TODO
