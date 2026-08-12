#!/usr/bin/env bash
#
# Restore app state from the shared restic repo. Run as root.
#
# Usage:
#   sudo ./scripts/restore.sh                       list this host's snapshots
#   sudo ./scripts/restore.sh latest                restore latest in place (to /)
#   sudo ./scripts/restore.sh <snapshot-id>         restore a specific snapshot
#   sudo ./scripts/restore.sh latest --target /tmp/r   restore elsewhere to inspect
#
# For an in-place restore, stop the affected stacks first. Immich Postgres is not
# in the snapshot (only the SQL dump under immich/db-dump) — after restoring,
# bring Immich up and load the dump via stacks/storage/immich/restore.sh.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f .env ]]; then
    echo "No root .env found." >&2
    exit 1
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a

: "${RESTIC_REPOSITORY:?set RESTIC_REPOSITORY in .env}"
: "${RESTIC_PASSWORD:?set RESTIC_PASSWORD in .env}"
export RESTIC_REPOSITORY RESTIC_PASSWORD

command -v restic >/dev/null || {
    echo "restic is not installed." >&2
    exit 1
}

host="$(hostname)"
snap="${1:-snapshots}"
shift || true

target="/"
while [[ $# -gt 0 ]]; do
    case "$1" in
    --target)
        target="$2"
        shift 2
        ;;
    *)
        echo "Unknown option: $1" >&2
        exit 2
        ;;
    esac
done

if [[ "$snap" == "snapshots" || "$snap" == "list" ]]; then
    restic snapshots --host "$host"
    exit 0
fi

echo "Restoring snapshot '${snap}' (host ${host}) -> ${target}"
restic restore "$snap" --host "$host" --target "$target"
echo "Restore complete."
