# sonarr

> TV series management — runs on the **apps** node · category: `arr`

Part of the media-automation suite (Prowlarr → Sonarr/Radarr/Lidarr → qBittorrent → Bazarr → Jellyfin). Media arrives via NFS from ryzen.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://sonarr.${DOMAIN}` |
| Local | `http://apps:${SONARR_PORT}` |
| Node  | `apps`                 |

## Configuration

| Variable      | Description                          | Example             |
| ------------- | ------------------------------------ | ------------------- |
| `MEDIA_ROOT`  | NFS media root (`/downloads`, `/tv`) | `/mnt/nas`          |
| `SONARR_PORT` | Web UI host port                     | `8989`              |
| `PUID`/`PGID` | Media owner                          | `1000`              |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Point Sonarr at Prowlarr for indexers and qBittorrent for the download client. Keep `/downloads` and `/tv` on the same volume (`${MEDIA_ROOT}`) so imports are hardlinks, not copies.

## Volumes

| Path                    | Purpose | Backed up          |
| ----------------------- | ------- | ------------------ |
| `${DOCKER_DATA}/sonarr` | Config  | yes → `backup.sh`  |

## Links

- Image (LSIO): https://docs.linuxserver.io/images/docker-sonarr
