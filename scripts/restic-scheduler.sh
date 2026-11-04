#!/bin/sh
# Use the pinned image's Restic binary, without resticker's init/forget hooks.
set -eu
: "${RESTIC_BACKUP_TIME:?HH:MM backup time required}"
: "${BACKUP_HOST:?snapshot host required}"
case "$RESTIC_BACKUP_TIME" in [01][0-9]:[0-5][0-9] | 2[0-3]:[0-5][0-9]) ;; *) echo "Invalid HH:MM" >&2; exit 1 ;; esac
case "$BACKUP_HOST" in storage | docker) ;; *) exit 1 ;; esac
backup() {
    # Fail closed if repository is unavailable; never initialize a repository.
    restic snapshots --json >/dev/null
    if [ "$BACKUP_HOST" = storage ]; then
        restic backup --host storage --tag homelab --tag media \
            --exclude /data/immich/postgres /data /nas/Gallery /nas/Files /nas/Drive
    else
        restic backup --host docker --tag homelab /data /volumes /checkout
    fi
}
if [ "${1:-}" = --once ]; then
    backup
    exit
fi
last=""
while :; do
    day=$(date +%F)
    if [ "$(date +%H:%M)" = "$RESTIC_BACKUP_TIME" ] && [ "$day" != "$last" ]; then
        last=$day
        if ! backup; then
            echo "Backup failed; inspect logs and repository access" >&2
        fi
    fi
    sleep 20 &
    wait $!
done
