# duplicati

> Encrypted, versioned backups — runs on the **storage** node (ryzen) · category: `backup`

Backs up the NAS (`/source`, **read-only**) to the backup disk (`/backups`). This is the off-array copy that protects everything the per-stack `backup.sh` scripts drop into `${NFS_BACKUP}`.

## Access

|       |                          |
| ----- | ------------------------ |
| URL   | `https://backup.${DOMAIN}` |
| Local | `http://ryzen:${DUPLICATI_PORT}` |
| Node  | `storage` (ryzen)        |

## Configuration

| Variable                            | Description                       |
| ----------------------------------- | --------------------------------- |
| `MEDIA_ROOT`                        | Source data (read-only)           |
| `BACKUP_ROOT`                       | Destination disk (`/mnt/hdd2`)    |
| `DUPLICATI_WEBSERVICE_PASSWORD`     | Web UI password (**change it**)   |
| `DUPLICATI_SETTINGS_ENCRYPTION_KEY` | Encrypts Duplicati's own settings |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

> Keep `DUPLICATI_SETTINGS_ENCRYPTION_KEY` and your backup passphrase safe and off-box — without them, backups can't be restored.

## Volumes

| Path                       | Purpose               | Backed up         |
| -------------------------- | --------------------- | ----------------- |
| `${DOCKER_DATA}/duplicati` | Config + job database | yes → `backup.sh` |
| `${BACKUP_ROOT}`           | Backup destination    | it's the target   |
| `${MEDIA_ROOT}` (ro)       | Backup source         | —                 |

## Links

- Upstream: https://duplicati.com · Image (LSIO): https://docs.linuxserver.io/images/docker-duplicati
