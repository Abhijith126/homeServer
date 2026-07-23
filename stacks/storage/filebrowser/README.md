# filebrowser

> Web file manager over the storage array — runs on the **storage** node (ryzen) · category: `files`

## Access

|       |                          |
| ----- | ------------------------ |
| URL   | `https://files.${DOMAIN}` |
| Local | `http://ryzen:${FILEBROWSER_PORT}` |
| Node  | `storage` (ryzen)        |

## Configuration

| Variable           | Description                          | Example             |
| ------------------ | ------------------------------------ | ------------------- |
| `FILEBROWSER_ROOT` | Directory tree exposed at `/srv`     | `/mnt`              |
| `FILEBROWSER_PORT` | Web UI host port                     | `8082`              |
| `DOCKER_DATA`      | Holds `filebrowser.db`               | `/opt/homelab/data` |

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Users and settings live in `filebrowser.db` (migrated with your existing data). On a **fresh** database the default login is `admin` / `admin` — change it immediately.

## Volumes

| Path                         | Purpose            | Backed up          |
| ---------------------------- | ------------------ | ------------------ |
| `${DOCKER_DATA}/filebrowser` | Database + settings| yes → `backup.sh`  |
| `${FILEBROWSER_ROOT}` (`/srv`)| Files it manages  | it's the data      |

## Links

- Upstream: https://filebrowser.org
