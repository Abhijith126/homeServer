# prowlarr

> Indexer manager for the *arr suite — runs on the **apps** node · category: `arr`

Central place to manage indexers/trackers; syncs them to Sonarr, Radarr, and Lidarr so you configure indexers once.

## Access

|       |                          |
| ----- | ------------------------ |
| URL   | `https://prowlarr.${DOMAIN}` |
| Local | `http://apps:${PROWLARR_PORT}` |
| Node  | `apps`                   |

## Configuration

| Variable        | Description      | Example |
| --------------- | ---------------- | ------- |
| `PROWLARR_PORT` | Web UI host port | `9696`  |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Add your indexers, then under **Settings → Apps** add Sonarr/Radarr/Lidarr (use their `http://apps:<port>` URLs + API keys) so indexers sync automatically.

## Volumes

| Path                      | Purpose | Backed up          |
| ------------------------- | ------- | ------------------ |
| `${DOCKER_DATA}/prowlarr` | Config  | yes → `backup.sh`  |

## Links

- Image (LSIO): https://docs.linuxserver.io/images/docker-prowlarr
