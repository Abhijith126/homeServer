# radarr

> Movie management — runs on the **apps** node · category: `arr`

Part of the media-automation suite (Prowlarr → Sonarr/Radarr/Lidarr → qBittorrent → Bazarr → Jellyfin). Media arrives via NFS from ryzen.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://radarr.${DOMAIN}` |
| Local | `http://apps:${RADARR_PORT}` |
| Node  | `apps`                 |

## Configuration

| Variable      | Description                              | Example    |
| ------------- | ---------------------------------------- | ---------- |
| `MEDIA_ROOT`  | NFS media root (`/downloads`, `/movies`) | `/mnt/nas` |
| `RADARR_PORT` | Web UI host port                         | `7878`     |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Keep `/downloads` and `/movies` on the same volume (`${MEDIA_ROOT}`) so imports hardlink.

## Volumes

| Path                    | Purpose | Backed up          |
| ----------------------- | ------- | ------------------ |
| `${DOCKER_DATA}/radarr` | Config  | yes → `backup.sh`  |

## Links

- Image (LSIO): https://docs.linuxserver.io/images/docker-radarr
