#!/bin/sh
# A host-side forced SSH command creates and verifies a fresh logical DB export.
# No Docker socket or PostgreSQL data write access is granted to Backrest.
set -eu
: "${BACKREST_IMMICH_SSH_TARGET:?Set the restricted export account}"
: "${BACKREST_IMMICH_SSH_PORT:=22}"
exec ssh -T -i /run/immich-ssh/id_ed25519 \
    -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=/run/immich-ssh/known_hosts \
    -o ConnectTimeout=15 -p "$BACKREST_IMMICH_SSH_PORT" \
    "$BACKREST_IMMICH_SSH_TARGET" immich-export
