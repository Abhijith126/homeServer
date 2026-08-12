#!/usr/bin/env bash
#
# Node-level backup: snapshot all app state to the shared restic repo on hdd2.
#
# One encrypted, deduplicated repo is shared by every node (snapshots are tagged
# with the hostname). All app state lives under $BACKUP_PATHS thanks to the
# bind-mount convention, so a single backup covers every stack. Databases that
# cannot be copied while live (Immich Postgres) are dumped first and their live
# data dir excluded.
#
# Usage (run as root so restic can read every stack's data):
#   sudo ./scripts/backup.sh            live backup (default)
#   sudo ./scripts/backup.sh --stop     stop stacks during backup (max consistency)
#   sudo ./scripts/backup.sh --check    run `restic check` after the backup
#
# Config comes from the repo-root .env (RESTIC_REPOSITORY, RESTIC_PASSWORD, ...).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f .env ]]; then
    echo "No root .env found (cp .env.example .env && edit it)." >&2
    exit 1
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a

: "${RESTIC_REPOSITORY:?set RESTIC_REPOSITORY in .env}"
: "${RESTIC_PASSWORD:?set RESTIC_PASSWORD in .env}"
if [[ "$RESTIC_PASSWORD" == "CHANGEME" ]]; then
    echo "RESTIC_PASSWORD is still CHANGEME — set a real password in .env." >&2
    exit 1
fi
export RESTIC_REPOSITORY RESTIC_PASSWORD

data_root="${DOCKER_DATA:-/opt/homelab/data}"
keep_daily="${RESTIC_KEEP_DAILY:-7}"
keep_weekly="${RESTIC_KEEP_WEEKLY:-4}"
keep_monthly="${RESTIC_KEEP_MONTHLY:-6}"
# Media (photos/documents) — a separate, longer-retained snapshot. Set only on
# the node where these trees are local (storage); empty elsewhere.
mkeep_daily="${MEDIA_KEEP_DAILY:-7}"
mkeep_weekly="${MEDIA_KEEP_WEEKLY:-8}"
mkeep_monthly="${MEDIA_KEEP_MONTHLY:-12}"
read -r -a backup_paths <<<"${BACKUP_PATHS:-$data_root}"
host="$(hostname)"

# Transparent compression (repo-format v2). auto = compress what benefits,
# skip already-compressed data like photos/video.
export RESTIC_COMPRESSION="${RESTIC_COMPRESSION:-auto}"

do_stop=false
do_check=false
for arg in "$@"; do
    case "$arg" in
    --stop) do_stop=true ;;
    --check) do_check=true ;;
    *)
        echo "Unknown option: $arg" >&2
        exit 2
        ;;
    esac
done

command -v restic >/dev/null || {
    echo "restic is not installed." >&2
    exit 1
}

# Create the repo on first run.
if ! restic cat config >/dev/null 2>&1; then
    echo "Initializing restic repo at ${RESTIC_REPOSITORY}"
    restic init
fi

# Immich: dump Postgres (safer than copying a live PGDATA dir) into the data
# tree so restic captures it; the live dir is excluded below.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx immich-database; then
    db_user="$(grep -E '^DB_USERNAME=' stacks/storage/immich/.env 2>/dev/null | cut -d= -f2-)"
    db_user="${db_user:-postgres}"
    dump_dir="${data_root}/immich/db-dump"
    mkdir -p "$dump_dir"
    echo "Dumping Immich database -> ${dump_dir}/immich.sql.gz"
    docker exec immich-database pg_dumpall --clean --if-exists -U "$db_user" |
        gzip >"${dump_dir}/immich.sql.gz"
fi

# Optionally stop every stack on this node for a fully consistent snapshot.
stopped=()
if [[ "$do_stop" == true ]]; then
    while IFS= read -r dir; do
        [[ -f "$dir/compose.yaml" && -f "$dir/.env" ]] || continue
        echo "Stopping $(basename "$dir")..."
        (cd "$dir" && docker compose stop) && stopped+=("$dir")
    done < <(find stacks -mindepth 2 -maxdepth 2 -type d | sort)
fi

echo "Backing up ${backup_paths[*]} -> ${RESTIC_REPOSITORY} (host ${host})"
set +e
restic backup "${backup_paths[@]}" \
    --tag homelab \
    --exclude "${data_root}/immich/postgres"
backup_rc=$?
set -e

# Restart whatever we stopped, even if the backup failed.
for dir in "${stopped[@]:-}"; do
    [[ -n "$dir" ]] || continue
    echo "Starting $(basename "$dir")..."
    (cd "$dir" && docker compose start) || true
done

if [[ $backup_rc -ne 0 ]]; then
    echo "restic backup failed (rc=${backup_rc})" >&2
    exit "$backup_rc"
fi

echo "Applying app-data retention (daily=${keep_daily} weekly=${keep_weekly} monthly=${keep_monthly})"
restic forget --host "$host" --tag homelab \
    --keep-daily "$keep_daily" \
    --keep-weekly "$keep_weekly" \
    --keep-monthly "$keep_monthly" \
    --prune

# Media (photos + documents) — separate snapshot, longer retention. Only runs on
# the node where MEDIA_PATHS trees are local (e.g. ryzen for /mnt/nas/*).
if [[ -n "${MEDIA_PATHS:-}" ]]; then
    read -r -a media_req <<<"$MEDIA_PATHS"
    media_paths=()
    for p in "${media_req[@]}"; do
        if [[ -e "$p" ]]; then
            media_paths+=("$p")
        else
            echo "WARN: media path not found, skipping: $p" >&2
        fi
    done
    if [[ ${#media_paths[@]} -gt 0 ]]; then
        echo "Backing up media -> ${RESTIC_REPOSITORY} (tag media): ${media_paths[*]}"
        restic backup "${media_paths[@]}" --tag media
        echo "Applying media retention (daily=${mkeep_daily} weekly=${mkeep_weekly} monthly=${mkeep_monthly})"
        restic forget --host "$host" --tag media \
            --keep-daily "$mkeep_daily" \
            --keep-weekly "$mkeep_weekly" \
            --keep-monthly "$mkeep_monthly" \
            --prune
    fi
fi

if [[ "$do_check" == true ]]; then
    echo "Verifying repository integrity..."
    restic check
fi

echo "Backup complete."
restic snapshots --host "$host"
