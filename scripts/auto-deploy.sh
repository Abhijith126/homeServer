#!/usr/bin/env bash
# Called by the systemd timer, or manually to retry/reconcile a node.
set -euo pipefail
umask 077

# The function is parsed before Git updates this script in the checkout.
main() {
    local node="${1:-}" repo_root state_dir revision fingerprint previous=""
    case "$node" in apps | storage | infra) ;; *)
        echo "usage: $0 <apps|storage|infra> [--force]" >&2
        return 1
        ;;
    esac
    [[ "${2:-}" == "" || "${2:-}" == --force ]] || {
        echo "unknown option: $2" >&2
        return 1
    }
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$repo_root"
    state_dir="$repo_root/.deploy-state/$node"
    mkdir -p "$state_dir"
    exec 9>"$state_dir/lock"
    flock -n 9 || {
        echo "Another deployment is running"
        return 0
    }

    [[ "$(git branch --show-current)" == main ]] || {
        echo "Checkout must be on main" >&2
        return 1
    }
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Tracked local edits; refusing to overwrite them" >&2
        return 1
    fi
    git fetch --quiet origin main
    git merge --ff-only origin/main
    revision="$(git rev-parse HEAD)"
    [[ -f .env ]] || {
        echo "Configure the root .env first" >&2
        return 1
    }

    # Portainer is optional and excluded by default. Override in the service.
    local skip="${HOMELAB_SKIP_STACKS-portainer}"
    fingerprint="$({
        printf '%s\n' "$revision" "$node" "$skip"
        sha256sum .env
        if [[ -f stacks/infra/caddy/cloudflare.env ]]; then
            sha256sum stacks/infra/caddy/cloudflare.env
        fi
    } | sha256sum | cut -d ' ' -f 1)"
    [[ ! -f "$state_dir/success" ]] || previous="$(cat "$state_dir/success")"
    if [[ "$fingerprint" == "$previous" && "${2:-}" != --force ]]; then
        echo "Already deployed $revision"
        return 0
    fi

    echo "Deploying $node at $revision"
    ./scripts/gen-env.sh --node "$node"
    ./scripts/deploy-node.sh "$node" --update --skip "$skip"

    # No volumes or running/stopped-container images are removed. This is
    # host-wide: prune unused images whose creation time is over seven days old.
    docker image prune --all --force --filter "until=168h"
    printf '%s\n' "$fingerprint" >"$state_dir/success.tmp"
    mv "$state_dir/success.tmp" "$state_dir/success"
    printf '%s\n' "$revision" >"$state_dir/revision"
    echo "Successfully deployed $node at $revision"
}
main "$@"
