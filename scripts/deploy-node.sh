#!/usr/bin/env bash
#
# Deploy every stack for a node in one shot.
#   ./scripts/deploy-node.sh <node> [--skip "stack1 stack2 ..."]
#
# Runs `docker compose up -d` in each stacks/<node>/<app>/ that has a compose
# file and a generated .env. Idempotent — safe to re-run. Stacks without a .env
# are skipped with a hint to run `make config` first.
#
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1

node="${1:-}"
if [[ -z "$node" ]]; then
    echo "usage: $0 <node> [--skip \"stack1 stack2\"]" >&2
    exit 1
fi

node_dir="stacks/${node}"
if [[ ! -d "$node_dir" ]]; then
    echo "no such node directory: ${node_dir}" >&2
    exit 1
fi

skip=""
if [[ "${2:-}" == "--skip" ]]; then
    skip="${3:-}"
fi

# Ensure the shared docker networks exist first (idempotent).
./scripts/create-networks.sh

deployed=()
skipped=()
failed=()

for dir in "$node_dir"/*/; do
    stack="$(basename "$dir")"
    [[ -f "${dir}compose.yaml" ]] || continue

    if [[ " ${skip} " == *" ${stack} "* ]]; then
        echo "SKIP  ${stack} (--skip)"
        skipped+=("$stack")
        continue
    fi
    if [[ ! -f "${dir}.env" ]]; then
        echo "SKIP  ${stack} (no .env — run 'make config')"
        skipped+=("$stack")
        continue
    fi

    echo "==> ${stack}"
    if (cd "$dir" && docker compose up -d); then
        deployed+=("$stack")
    else
        echo "FAIL  ${stack}"
        failed+=("$stack")
    fi
done

echo ""
echo "deployed: ${deployed[*]:-none}"
echo "skipped:  ${skipped[*]:-none}"
echo "failed:   ${failed[*]:-none}"

[[ ${#failed[@]} -eq 0 ]]
