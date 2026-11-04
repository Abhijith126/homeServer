# Incremental migration and rollback

These commands are an operator runbook, not an automatic deployment. Do not run a bulk deploy or host bootstrap on the existing installation. No service data, containers, volumes or historical snapshots should be deleted. Keep the old release and private files until restore and rollback are tested.

## Prepare before merging or pulling

1. On every old checkout/host, identify all systemd/Git/Portainer deployment owners. Pause the node-local deployment and health timers (inspect `systemctl list-timers 'homelab*'` for actual names) and Portainer Git polling before pulling the migration. Wait for any active deployment/backup to finish. A timer already executing the old script can still use its old arguments. Do not retire a Chromebox that still owns a required service.
2. Record the old Git SHA with `git rev-parse HEAD`, and securely copy the checkout including ignored `.env`, stack `.env`, `cloudflare.env`, `.bootstrap`, `.deploy-state` and tracked Caddy/Pi-hole files outside the checkout. Do not publish these private files. Keep the production checkout's absolute path unchanged. Preserve any local Caddy/Pi-hole edits and compare them with the new files before pulling.
3. Inventory running services and identity/mounts read-only:

   ```sh
   docker compose ls --all
   docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}} {{.Label "com.docker.compose.project.working_dir"}}'
   docker inspect caddy pihole restic --format '{{.Name}} {{json .Mounts}}'
   docker volume inspect caddy_caddy-data caddy_caddy-config pihole-unbound_unbound-state
   ```

   Record every service's project, Compose service name, image ID, bind paths, ports and volumes. Compare with `docker compose config` from the new directory. Nonstandard Portainer project names require explicit overrides and review; stop if identity differs. Both old targets declared project/container `restic` and `beszel-agent`: keep the existing single Lenovo instance of each, never launch a second copy under a new project name. Inventory additional/manual stacks too.
4. Verify current backups and a staging restore; take application-consistent exports or approved quiesced backups (see [backup limits](backups.md)). Preserve existing Restic repository/password, Homarr key, Immich DB password and Caddy CA volumes. Ensure all app data already resides at `/opt/homelab/data` on Lenovo; copying live DB trees from another host is not a safe data migration. If services still run on a Chromebox, migrate those individually in a separate maintenance window and verify them before retiring that host.

## Prepare new paths without starting services

After preserving local changes, pull the reviewed migration into the existing checkout. Old containers continue using their old mount paths; keep those paths available until each is adopted. Recreate compatibility **symlinks**, not new Compose projects, for path-bound containers during the transition:

```sh
# Only when these old directories no longer exist after the pull:
test -e stacks/apps || ln -s docker stacks/apps
test -e stacks/infra || ln -s docker stacks/infra
```

If either old directory still exists (ignored files often keep it present), do not overwrite it. Securely move its private files to the corresponding `stacks/docker/<service>/` paths, comparing any collisions manually, then archive the old directory outside the checkout before creating the symlink. Never discard private files or merge differing Restic passwords silently. Keep `cloudflare.env` next to the moved Caddy stack. These local symlinks are temporary compatibility paths, not deployment targets; do not commit them. Configuration generation follows physical directories and generates only `storage` and `docker`.

Update the root `.env`: set `DOCKER_HOST=192.168.1.121`, `STORAGE_HOST=192.168.1.120`, retain `HA_HOST=192.168.1.122`, remove unused `APPS_HOST`/`INFRA_HOST` and retired HA/DIUN Docker-only variables. Preserve all credentials, path overrides and current URL/port settings. Do not replace the root file with the example.

```sh
nano .env
make config
make config-check
for dir in stacks/docker/* stacks/storage/*; do
    test ! -f "$dir/compose.yaml" || (cd "$dir" && docker compose config -q) || exit 1
done
```

Compare rendered configs to the recorded running mounts. Storage's sources remain selected Gallery/Files/Drive plus app data; ensure an up-to-date Immich export exists. Check the shared repo is mounted, and all three named-volume sources really match live mounts. A missing external volume is a blocker, not a reason to create an empty substitute.

## Adopt one project at a time

A move preserves top-level `name:` and container/service identity, but label and bind-path changes can recreate containers. Schedule each adoption; do not expect zero downtime. After comparing `docker compose config`, use only the existing project's name and only that project's new directory. For example, Caddy already uses project `caddy`:

```sh
cd stacks/docker/caddy
docker compose -p caddy config -q
# At the approved maintenance time, after reviewing the diff:
docker compose -p caddy up -d --no-deps caddy
```

Inspect logs, mounts and health after each adoption. Check DNS on TCP/UDP 53, HTTPS routes, Pi-hole admin :8081, Homarr :7575, monitoring, media automation and Portainer. Test `has.${DOMAIN}` and direct `HA_HOST:8123`; retain Home Assistant's trusted-proxy settings. Caddyfile and Pi-hole helper scripts are preserved in the new directory. Reload Caddy after adoption if needed.

Adopt Lenovo Restic as the existing `restic` project/container, and Storage Restic likewise on Ryzen. Run a manual backup via `/bin/sh /backup-scheduler.sh --once`, inspect snapshots by the expected host and tags, restore into a fresh staging directory, and run a repository check. Only after replacement coverage is verified may an operator disable/stop the old Storage `restic-media` and `restic-check` jobs and any separate retired-host schedulers. This repository never removes them automatically. Do not run old and new schedulers concurrently. Do not run `down`, `--remove-orphans`, `down -v`, volume removal, snapshot deletion or repository initialization.

After all services are verified, create the explicit migration acknowledgement on each Docker host:

```sh
mkdir -p .deploy-state
printf '%s\n' 'Reviewed project identities, mounts, backups and legacy schedulers' > .deploy-state/layout-v2-reviewed
```

Only then enable `sudo make auto-deploy-install NODE=docker` on Lenovo and `NODE=storage` on Ryzen. Keep Portainer under its chosen single owner; the timer skips it by default, so explicitly configure the skip list if it should manage an already adopted Portainer. Review `.bootstrap/vars.json` locally: replace old `bootstrap_node` with `docker`, remove retired group/host entries, and set `bootstrap_docker_ip` to .121 before future provisioning; do not rerun bootstrap for this migration. Keep old timers disabled; inspect installed units and remove obsolete unit definitions only after recording rollback settings. Compatibility symlinks/archived old paths can remain until no container uses them; removal is a separate operator decision.

## Rollback

Pause new deployment/health timers and polling first. Record current snapshots and images. Revert to the recorded old Git SHA while restoring the securely preserved private configuration and original directories (archive compatibility symlinks first). Keep the same Docker project names, external volume identities and data roots. Adopt affected services back one at a time with their old Compose files and recorded image IDs, validating mounts before each action. Moving paths back may recreate containers; do not bring up a second project or remove volumes. Image changes are not part of this migration; never downgrade a database across an application schema migration.

A hostname change does not rewrite snapshots: new `docker` and historical `apps`/`infra`/`storage` remain readable with the original password. Keep backups created after migration. For Storage backup rollback, restore the old schedules only after disabling the replacement scheduler; do not re-enable old broad forget/prune settings. If any application data needs rollback, restore a verified consistent export into staging and perform an explicit application recovery, not an automatic directory overwrite. Resume only the recorded old deployment owners once all checks pass.
