#!/usr/bin/env bash
# Called by the systemd timer, or manually to retry/reconcile a node.
set -euo pipefail
umask 077

finish_report() {
    local status=$?
    trap - EXIT
    python3 "$report_root/scripts/deploy-report.py" finish "$report_node" --status "$status" || true
    exit "$status"
}

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

    report_root="$repo_root"
    report_node="$node"
    export HOMELAB_REPORT_STEP_FILE="$state_dir/step"
    export HOMELAB_REPORT_FAILURE_FILE="$state_dir/failures"
    python3 scripts/deploy-report.py begin "$node" || true
    trap finish_report EXIT
    printf '%s\n' 'Git sync / checkout validation' >"$HOMELAB_REPORT_STEP_FILE"

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
    # Record old image IDs before recreation. Image creation age is NOT a
    # rollback retention window; track when each observed image became unused.
    printf '%s\n' 'Record image retention inventory' >"$HOMELAB_REPORT_STEP_FILE"
    python3 scripts/image-retention.py "$node"

    if [[ "$fingerprint" == "$previous" && "${2:-}" != --force ]]; then
        echo "Already deployed $revision"
        python3 scripts/image-retention.py "$node" --cleanup
        return 0
    fi

    echo "Deploying $node at $revision"
    printf '%s\n' 'Generate environment' >"$HOMELAB_REPORT_STEP_FILE"
    ./scripts/gen-env.sh --node "$node" --skip "$skip"
    local deploy_status=0 cleanup_status=0
    ./scripts/deploy-node.sh "$node" --update --skip "$skip" || deploy_status=$?

    if [[ "$deploy_status" -ne 0 ]]; then
        # Preserve all rollback candidates after any failed deployment.
        return "$deploy_status"
    fi
    echo "Removing managed images unused for at least 14 days"
    python3 scripts/image-retention.py "$node" --cleanup | tee "$state_dir/prune-after" || cleanup_status=$?
    if [[ "$cleanup_status" -ne 0 ]]; then
        printf '%s\n' 'Post-deployment cleanup' >>"$HOMELAB_REPORT_FAILURE_FILE"
    fi
    if [[ "$cleanup_status" -ne 0 ]]; then
        return "$cleanup_status"
    fi
    printf '%s\n' "$fingerprint" >"$state_dir/success.tmp"
    mv "$state_dir/success.tmp" "$state_dir/success"
    printf '%s\n' "$revision" >"$state_dir/revision"
    echo "Successfully deployed $node at $revision"
}
main "$@"
