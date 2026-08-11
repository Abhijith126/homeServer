# portainer

> Portainer BE management server — runs on the **infra** node · category: `management`

Web UI + API for managing Docker across the homelab. It manages the infra host
directly over the local Docker socket, and the **apps** and **ryzen** nodes
through the `portainer/agent` deployed there (Ansible `portainer_agent` role,
port `9001`).

Portainer is a **convenience layer only** — the repo + plain `docker compose` is
the source of truth. If the licence lapses or the server is down, every stack
still deploys from the CLI unchanged.

> **Why infra and not ryzen?** The management plane lives on the always-on,
> low-load edge node so it stays up while the storage node is rebuilt or busy.

## Access

|       |                                   |
| ----- | --------------------------------- |
| URL   | `https://portainer.${DOMAIN}` (via Caddy) |
| Local | `https://infra:${PORTAINER_PORT}` (self-signed) |
| Node  | `infra`                           |

## Setup

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

1. Open the UI within a few minutes of first start and create the admin account
   (Portainer locks initial setup after a timeout — `docker compose restart` if you miss it).
2. Add the free **Business Edition** licence key (3 nodes free) under *Settings → Licenses*.
3. Add each remote node as an **Agent** environment:
   *Environments → Add environment → Docker Standalone → Agent*,
   URL `apps:9001` and `ryzen:9001` (deploy the agent there first via Ansible).

## Volumes

| Path                       | Purpose                         | Backed up          |
| -------------------------- | ------------------------------- | ------------------ |
| `${DOCKER_DATA}/portainer` | Portainer DB, settings, licence | yes → `backup.sh`  |
| `/var/run/docker.sock`     | Manage the local (infra) Docker | n/a                |

## Backup / Restore

```bash
./backup.sh            # tar config → ${NFS_BACKUP}/portainer/
./backup.sh --stop     # stop container during backup (consistent snapshot)
./restore.sh           # restore newest archive
```

## Upgrade

Keep the server version in step with the agents (`portainer_agent_version` in
`ansible/group_vars/all.yml`), then:

```bash
docker compose pull && docker compose up -d
```

## Links

- Upstream: https://www.portainer.io
