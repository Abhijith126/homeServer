#!/usr/bin/env bash
#
# Restore the immich DATABASE from a pg_dumpall archive.
# This recreates the database volume, so ALL current metadata is replaced.
# The photo library on disk is left untouched.
# See https://docs.immich.app/administration/backup-and-restore
# Usage: ./restore.sh [immich-db-YYYYmmdd-HHMMSS.sql.gz]   (defaults to newest)
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

: "${NFS_BACKUP:?NFS_BACKUP not set (create .env from .env.example)}"
: "${DB_USERNAME:?DB_USERNAME not set (create .env from .env.example)}"

dest_dir="${NFS_BACKUP}/immich"
archive="${1:-}"

if [[ -z "$archive" ]]; then
    archive="$(find "$dest_dir" -maxdepth 1 -type f -name 'immich-db-*.sql.gz' | sort -r | head -n1)"
fi

if [[ -z "$archive" || ! -f "$archive" ]]; then
    echo "No archive found (looked in ${dest_dir})" >&2
    exit 1
fi

echo "About to restore immich DB from: ${archive}"
echo "This DROPS and recreates the database volume (all current metadata lost)."
read -r -p "Continue? [y/N] " ans
if [[ "${ans,,}" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

echo "Stopping stack and removing volumes..."
docker compose down -v

echo "Pulling images and creating the database..."
docker compose pull
docker compose create
docker compose start database

echo "Waiting for the database to accept connections..."
until docker compose exec -T database pg_isready --username="$DB_USERNAME" >/dev/null 2>&1; do
    sleep 2
done

echo "Loading dump..."
gunzip <"$archive" | docker compose exec -T database \
    psql --dbname=postgres --username="$DB_USERNAME"

echo "Starting the full stack..."
docker compose up -d

echo "Restore complete."
