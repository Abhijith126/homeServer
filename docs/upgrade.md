# Upgrade guide

## Philosophy

Images are **pinned** to specific tags in git — nothing auto-updates. **Diun** watches every `diun.enable=true` container and emails you when a newer image is published; you then bump the tag deliberately, commit, and redeploy. This keeps deployments reproducible and rollbacks trivial.

## Upgrade a single stack

```bash
cd stacks/<node>/<app>
$EDITOR compose.yaml            # bump the pinned image tag
docker compose pull
docker compose up -d
docker image prune -f          # optional: reclaim space
```

Commit the tag bump so git stays the source of truth. If you use Portainer Git stacks, committing + pushing triggers the update (webhook/polling).

## Finding the new tag

Diun's email names the image. Or check the registry — the same way tags were originally pinned (Docker Hub / GHCR tags API).

## Special cases

### Immich (multi-service)

Immich pins its Postgres and Redis (Valkey) images **by digest**, matched to the server version. When bumping `IMMICH_VERSION`:

1. Read the [release notes](https://github.com/immich-app/immich/releases) for breaking changes.
2. Compare against the upstream compose for that release and update the `redis`/`database` digests if they changed:
   `https://github.com/immich-app/immich/releases/download/<version>/docker-compose.yml`
3. `docker compose pull && docker compose up -d`.

Take a DB backup first: `./backup.sh`.

### Pi-hole (combined image)

`cbcrowe/pihole-unbound` bundles Pi-hole + Unbound. Bump the pinned date tag, `docker compose pull && up -d`. Config/adlists persist in the mounted volumes.

### Home Assistant

Fast release cadence (monthly). Skim release notes for breaking integration changes, then bump the tag. HA's own config lives in `/config` (backed up).

## Host / OS upgrades

Security patches apply automatically (unattended-upgrades). To re-apply configuration or roll out a change to Docker/NFS/firewall settings, re-run Ansible:

```bash
cd ansible
ansible-playbook site.yml --check --diff     # preview
ansible-playbook site.yml
```

## Rollback

Because tags are pinned in git, rollback is a git revert of the tag bump:

```bash
git revert <commit>          # or edit the tag back
docker compose up -d
```

Portainer BE also offers per-stack rollback in the UI. For data-level rollback, restore from a backup (see [disaster-recovery.md](disaster-recovery.md)).
