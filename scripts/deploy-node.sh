#!/usr/bin/env bash
# Deploy a node's stacks. --update pulls/builds images and waits for health.
# Usage: deploy-node.sh <apps|storage|infra> [--skip "stack1 stack2"] [--update]
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1
node="${1:-}"
case "$node" in apps | storage | infra) ;; *)
    echo "usage: $0 <apps|storage|infra> [--skip \"stacks\"] [--update]" >&2
    exit 1
    ;;
esac
shift
skip=""
update=false
while [[ $# -gt 0 ]]; do
    case "$1" in
    --skip)
        [[ $# -ge 2 ]] || {
            echo "--skip needs a list" >&2
            exit 1
        }
        skip="$2"
        shift 2
        ;;
    --update)
        update=true
        shift
        ;;
    *)
        echo "unknown option: $1" >&2
        exit 1
        ;;
    esac
done

dirs=()
for dir in "stacks/$node"/*/; do
    [[ -f "${dir}compose.yaml" ]] || continue
    stack="$(basename "$dir")"
    if [[ " $skip " == *" $stack "* ]]; then
        echo "SKIP $stack (--skip)"
        continue
    fi
    if [[ ! -f "${dir}.env" ]]; then
        if [[ "$update" == true ]]; then
            echo "Missing ${dir}.env; run make config" >&2
            exit 1
        fi
        echo "SKIP $stack (no .env)"
        continue
    fi
    # Validate all selected stacks before changing any containers.
    (cd "$dir" && docker compose config -q) || exit 1
    dirs+=("$dir")
done
[[ ${#dirs[@]} -gt 0 ]] || {
    echo "No stacks selected" >&2
    exit 1
}
./scripts/create-networks.sh || exit 1

failed=()
for dir in "${dirs[@]}"; do
    stack="$(basename "$dir")"
    echo "==> $stack"
    if [[ "$update" == true ]]; then
        if [[ "$stack" == immich ]] && ! python3 "$repo_root/scripts/immich-backup.py" "$dir" --pre-update; then
            failed+=("$stack")
            continue
        fi
        if ! (cd "$dir" &&
            docker compose pull --ignore-buildable &&
            docker compose build --pull &&
            docker compose up -d --remove-orphans --wait --wait-timeout 300 &&
            if [[ "$stack" == caddy ]]; then
                docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
            fi); then
            failed+=("$stack")
        fi
    elif ! (cd "$dir" && docker compose up -d); then
        failed+=("$stack")
    fi
done
echo "failed: ${failed[*]:-none}"
[[ ${#failed[@]} -eq 0 ]]
