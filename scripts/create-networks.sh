#!/usr/bin/env bash
#
# Create the shared external docker networks used by co-located
# reverse-proxy stacks (e.g. Caddy + an app on the same host).
# Idempotent. Run once per host (also invoked by the Ansible docker role).
#
set -euo pipefail

networks=(proxy)

for net in "${networks[@]}"; do
    if docker network inspect "$net" >/dev/null 2>&1; then
        echo "network '${net}' already exists"
    else
        docker network create --driver bridge "$net" >/dev/null
        echo "created network '${net}'"
    fi
done
