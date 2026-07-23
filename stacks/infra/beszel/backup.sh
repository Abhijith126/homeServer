#!/usr/bin/env bash
#
# Back up this stack's config directory to the NFS backup target.
# Usage: ./backup.sh [--stop]
#   --stop   stop the container during backup for a consistent snapshot
#
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

stack="$(basename "$script_dir")"
: "${DOCKER_DATA:?DOCKER_DATA not set (create .env from .env.example)}"
: "${NFS_BACKUP:?NFS_BACKUP not set (create .env from .env.example)}"

src="${DOCKER_DATA}/${stack}"
dest_dir="${NFS_BACKUP}/${stack}"
archive="${dest_dir}/${stack}-$(date +%Y%m%d-%H%M%S).tar.gz"
keep=7

stop=false
[[ "${1:-}" == "--stop" ]] && stop=true

if [[ ! -d "$src" ]]; then
    echo "Nothing to back up: ${src} does not exist" >&2
    exit 1
fi
mkdir -p "$dest_dir"

if [[ "$stop" == true ]]; then
    echo "Stopping ${stack}..."
    docker compose stop
fi

echo "Backing up ${src} -> ${archive}"
tar -czf "$archive" -C "$(dirname "$src")" "$(basename "$src")"

if [[ "$stop" == true ]]; then
    echo "Starting ${stack}..."
    docker compose start
fi

# Retain only the newest ${keep} archives.
find "$dest_dir" -maxdepth 1 -type f -name "${stack}-*.tar.gz" |
    sort -r | tail -n "+$((keep + 1))" | while IFS= read -r old; do
    rm -f "$old"
done

echo "Backup complete: ${archive}"
