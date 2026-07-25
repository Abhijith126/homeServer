# bazarr

> Subtitle management for your Sonarr/Radarr libraries — runs on the **apps** node · category: `arr`

Point Bazarr at the same `/movies` and `/tv` paths Radarr/Sonarr use so it matches subtitles to your files.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://bazarr.${DOMAIN}` |
| Local | `http://apps:${BAZARR_PORT}` |
| Node  | `apps`                 |

## Configuration

| Variable      | Description                        | Example    |
| ------------- | ---------------------------------- | ---------- |
| `MEDIA_ROOT`  | NFS media root (`/movies`, `/tv`)  | `/mnt/nas` |
| `BAZARR_PORT` | Web UI host port                   | `6767`     |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

## Volumes

| Path                    | Purpose | Backed up          |
| ----------------------- | ------- | ------------------ |
| `${DOCKER_DATA}/bazarr` | Config  | yes → `backup.sh`  |

## Links

- Image (LSIO): https://docs.linuxserver.io/images/docker-bazarr
