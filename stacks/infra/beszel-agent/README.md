# beszel-agent

> Metrics agent for the Beszel hub · category: `monitoring`

Reports host + docker metrics to the [`beszel`](../beszel/) hub. **Deploy this on every node** (storage, apps, infra) — conceptually a DaemonSet. Uses `network_mode: host` for accurate host metrics.

## Setup (per node)

```bash
cp .env.example .env
# paste the public key from the hub's "Add System" dialog into BESZEL_AGENT_KEY
$EDITOR .env
docker compose up -d
```

Then in the hub, finish "Add System" pointing at this node's hostname/IP and `BESZEL_AGENT_PORT`.

## Configuration

| Variable            | Description                              | Example   |
| ------------------- | ---------------------------------------- | --------- |
| `BESZEL_AGENT_PORT` | Listen port (match the hub)              | `45876`   |
| `BESZEL_AGENT_KEY`  | Hub public key (**required**)            | —         |

Stateless — no volumes, no backup.

## Links

- Upstream: https://beszel.dev
