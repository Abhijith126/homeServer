# homarr

> Homelab dashboard — runs on the **apps** node · category: `dashboard`

Single landing page for all services, with live widgets (Docker, *arr, Uptime Kuma, etc.).

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://homarr.${DOMAIN}` |
| Local | `http://apps:${HOMARR_PORT}` |
| Node  | `apps`                 |

## Configuration

| Variable                       | Description                                   |
| ------------------------------ | --------------------------------------------- |
| `HOMARR_SECRET_ENCRYPTION_KEY` | 64 hex chars — `openssl rand -hex 32` (**required**) |
| `HOMARR_PORT`                  | Web UI host port                              |

```bash
cp .env.example .env
openssl rand -hex 32   # paste into HOMARR_SECRET_ENCRYPTION_KEY
$EDITOR .env
docker compose up -d
```

The docker socket is mounted **read-only** for container widgets. Losing `SECRET_ENCRYPTION_KEY` means re-entering all saved integration credentials.

## Volumes

| Path                    | Purpose               | Backed up          |
| ----------------------- | --------------------- | ------------------ |
| `${DOCKER_DATA}/homarr` | Config + SQLite DB    | yes → `backup.sh`  |

## Links

- Upstream: https://homarr.dev
