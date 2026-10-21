# beszel-agent

> Metrics agent for the Beszel hub · category: `monitoring`

Reports host + docker metrics to the [`beszel`](../beszel/) hub. **Deploy this on every node** (storage, apps, infra) — conceptually a DaemonSet. Uses `network_mode: host` for accurate host metrics.

Each node has a `beszel-agent` folder under `stacks/<node>/`, so node-local
environment generation and scheduled deployments discover the agent. Renovate
tracks all three image pins; tests require identical Compose files and environment
templates to keep their versions and configuration aligned.

For existing apps/storage nodes, set `BESZEL_AGENT_KEY` in that node's root `.env`.
If the agent is skipped, run `./scripts/setup.sh --reconfigure` and enable it.
The next merged change is deployed on the node's schedule, or run
`make auto-deploy NODE=apps` (use `storage` on ryzen) to reconcile immediately.
An old agent launched outside this Compose stack may need a one-time migration;
inspect its configuration and project ownership before replacing it.

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
