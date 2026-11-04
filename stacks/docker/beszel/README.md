# beszel

> Lightweight monitoring hub — runs on the **docker** node · category: `monitoring`

Tiny Go-based system monitor (CPU / RAM / disk / network / docker stats + history + alerts) — a great fit for the low-power docker node. This is the **hub**; deploy the [`beszel-agent`](../beszel-agent/) stack on every node you want to watch.

## Access

|       |                        |
| ----- | ---------------------- |
| URL   | `https://beszel.${DOMAIN}` |
| Local | `http://docker:${BESZEL_PORT}` |
| Node  | `docker`                |

## Setup

```bash
cp .env.example .env && $EDITOR .env
docker compose up -d
```

1. Open the UI, create the admin account.
2. **Add System** → copy the shown **public key** and the agent port.
3. Put that key into each node's `beszel-agent/.env` as `BESZEL_AGENT_KEY`, then deploy the agent there.

## Volumes

| Path                    | Purpose               | Backed up          |
| ----------------------- | --------------------- | ------------------ |
| `${DOCKER_DATA}/beszel` | Hub DB + config       | yes → `backup.sh`  |

## Links

- Upstream: https://beszel.dev
