#!/usr/bin/env bash
#
# Scaffold a new stack from the template.
# Usage: ./scripts/new-app.sh <node> <app> [category]
#   node: storage | apps | infra
#
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
node="${1:-}"
app="${2:-}"
category="${3:-tools}"

if [[ -z "$node" || -z "$app" ]]; then
    echo "Usage: $0 <node> <app> [category]" >&2
    echo "  node: storage | apps | infra" >&2
    exit 1
fi

case "$node" in
storage | apps | infra) ;;
*)
    echo "node must be one of: storage apps infra" >&2
    exit 1
    ;;
esac

dest="${repo_root}/stacks/${node}/${app}"
if [[ -e "$dest" ]]; then
    echo "${dest} already exists" >&2
    exit 1
fi

"${repo_root}/scripts/render-template.sh" "$dest" "$app" "$node" "$category"

echo "Created ${dest}"
echo "Next:"
echo "  1. Edit ${dest}/compose.yaml   (image, ports, volumes, healthcheck)"
echo "  2. Edit ${dest}/.env.example"
echo "  3. cp ${dest}/.env.example ${dest}/.env && \$EDITOR ${dest}/.env"
