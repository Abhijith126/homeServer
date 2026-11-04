#!/usr/bin/env bash
#
# Restore this stack's config directory from a backup archive.
# Usage: ./restore.sh [archive.tar.gz]   (defaults to the newest archive)
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

dest_dir="${NFS_BACKUP}/${stack}"
archive="${1:-}"

if [[ -z "$archive" ]]; then
    archive="$(find "$dest_dir" -maxdepth 1 -type f -name "${stack}-*.tar.gz" | sort -r | head -n1)"
fi

if [[ -z "$archive" || ! -f "$archive" ]]; then
    echo "No archive found (looked in ${dest_dir})" >&2
    exit 1
fi

echo "About to restore: ${archive}"
echo "This will OVERWRITE ${DOCKER_DATA}/${stack}"
read -r -p "Continue? [y/N] " ans
if [[ "${ans,,}" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

echo "Stopping ${stack}..."
docker compose down

mkdir -p "$DOCKER_DATA"
echo "Extracting ${archive} -> ${DOCKER_DATA}"
tar -xzf "$archive" -C "$DOCKER_DATA"

echo "Starting ${stack}..."
docker compose up -d

echo "Restore complete."
