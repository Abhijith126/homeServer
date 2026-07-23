# jellyfin

> Media server — runs on the **storage** node (ryzen) · category: `media`

Uses `network_mode: host` (DLNA / auto-discovery), matching the current deployment. Runs as `PUID:PGID` so it reads the NAS media as the right owner.

## Access

|       |                          |
| ----- | ------------------------ |
| URL   | `https://jellyfin.${DOMAIN}` |
| Local | `http://ryzen:8096`      |
| Node  | `storage` (ryzen)        |

## Configuration

| Variable      | Description                     | Example             |
| ------------- | ------------------------------- | ------------------- |
| `MEDIA_ROOT`  | NAS/RAID root, mounted `/media` | `/mnt/nas`          |
| `DOCKER_DATA` | Config bind-mount base          | `/opt/homelab/data` |
| `PUID`/`PGID` | Media owner                     | `1000`              |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

## Hardware transcoding

The Ryzen 2200G (Vega 8) supports VAAPI. Uncomment the `devices: /dev/dri` block in `compose.yaml` and enable VAAPI in **Dashboard → Playback**.

## Volumes

| Path                      | Purpose            | Backed up          |
| ------------------------- | ------------------ | ------------------ |
| `${DOCKER_DATA}/jellyfin` | Config + metadata  | yes → `backup.sh`  |
| `jellyfin-cache` (volume) | Transcode cache    | no (regenerated)   |
| `${MEDIA_ROOT}`           | Media library      | it's the source    |

## Backup / Upgrade

```bash
./backup.sh --stop
docker compose pull && docker compose up -d
```

## Links

- Upstream: https://jellyfin.org
