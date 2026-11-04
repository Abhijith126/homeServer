# lidarr

> Music management — runs on the **docker** node · category: `arr`

Part of the media-automation suite. Media arrives via NFS from ryzen.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://lidarr.${DOMAIN}` |
| Local | `http://docker:${LIDARR_PORT}` |
| Node  | `docker`                 |

## Configuration

| Variable      | Description                             | Example    |
| ------------- | --------------------------------------- | ---------- |
| `MEDIA_ROOT`  | NFS media root (`/downloads`, `/music`) | `/mnt/nas` |
| `LIDARR_PORT` | Web UI host port                        | `8686`     |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

## Volumes

| Path                    | Purpose | Backed up          |
| ----------------------- | ------- | ------------------ |
| `${DOCKER_DATA}/lidarr` | Config  | yes → `backup.sh`  |

## Links

- Image (LSIO): https://docs.linuxserver.io/images/docker-lidarr
