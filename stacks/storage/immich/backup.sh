#!/usr/bin/env bash
#
# Immich DATABASE backup (pg_dumpall -> gzip -> NFS_BACKUP).
# The photo library (${IMMICH_LIBRARY}) is large and is NOT included here —
# it is protected by the RAID array + Duplicati. This captures the
# irreplaceable metadata (albums, faces, config) only.
# See https://docs.immich.app/administration/backup-and-restore
# Usage: ./backup.sh
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
archive="${dest_dir}/immich-db-$(date +%Y%m%d-%H%M%S).sql.gz"
keep=7

mkdir -p "$dest_dir"

echo "Dumping immich database -> ${archive}"
docker compose exec -T database \
    pg_dumpall --clean --if-exists --username="$DB_USERNAME" | gzip >"$archive"

# Retain only the newest ${keep} dumps.
find "$dest_dir" -maxdepth 1 -type f -name 'immich-db-*.sql.gz' |
    sort -r | tail -n "+$((keep + 1))" | while IFS= read -r old; do
    rm -f "$old"
done

echo "Backup complete: ${archive}"
echo "NOTE: the photo library (${IMMICH_LIBRARY:-see .env}) is NOT in this archive —"
echo "      ensure Duplicati / RAID covers it."
