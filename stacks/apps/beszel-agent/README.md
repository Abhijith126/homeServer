# Beszel agent (apps)

This node-local stack is discovered by the scheduled apps deployment.
Renovate updates its pinned image alongside the infra agent and Beszel hub.
See [the shared agent guide](../../infra/beszel-agent/README.md) for configuration.

Set BESZEL_AGENT_KEY in this node's ignored root .env to the public key from
the Beszel hub. If beszel-agent is in HOMELAB_SKIP_STACKS, enable it with
scripts/setup.sh --reconfigure before the next deployment.
