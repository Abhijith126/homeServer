# Existing Restic → Backrest migration

**Operator runbook only.** This PR performs no deployment. The two targets must already be `storage` and `docker`; complete any previous Compose path/project migration first. Use the existing absolute checkout and existing root `.env`. Do not run host bootstrap, bulk `make deploy`, old/new schedulers together, `down -v`, repository initialization or cleanup.

Set `REPO` below to the actual checkout path on each host, not a new clone. Commands assume a deployment user who can use Docker; preserve existing data owners.

## 1. Prepare both hosts

```sh
cd /actual/path/homeServer
REPO="$PWD"
git rev-parse HEAD                     # record rollback release
sudo systemctl stop homelab-deploy.timer homelab-health.timer
systemctl is-active homelab-deploy.service homelab-health.service
```

Inspect actual installed unit names with `systemctl list-timers 'homelab*'` if these differ; wait for services to finish. Pause Portainer Git polling if it manages backups. Securely copy root/stack `.env`, tracked/local config, `cloudflare.env`, `.bootstrap` and `.deploy-state` outside the checkout. Never overwrite existing credentials with examples. Keep old Compose definitions in a secure rollback checkout/archive before pulling.

Check **both** hosts' jobs before stopping anything:

```sh
docker ps --format '{{.Names}} {{.Status}}'
for name in restic restic-media restic-check; do
    if docker container inspect "$name" >/dev/null 2>&1; then
        docker top "$name" -eo pid,args
        docker logs --tail 50 "$name"
    fi
done
```

Check for active `restic backup`, `check`, `forget`, `prune`, restore and export processes. Inspect the existing repo's locks using the **currently working** container (`docker exec restic restic list locks`). Review timestamps/owners; never force-unlock. Wait until operations finish and a new schedule window is not imminent. A container PID alone does not prove idle.

Record mounts and named volumes:

```sh
docker inspect restic --format '{{json .Mounts}}'
# Lenovo only:
docker volume inspect caddy_caddy-data caddy_caddy-config pihole-unbound_unbound-state
```

Confirm the two repo paths are the same existing repository via NFS and that the existing password works. Verify a historical staging restore first. Inventory additional/manual persistent mounts too.

## 2. Disable and stop legacy schedulers (manual, both hosts)

Once idle, prevent auto-restart and stop existing backup containers individually. Missing containers are expected on some installations:

```sh
for name in restic restic-media restic-check; do
    if docker container inspect "$name" >/dev/null 2>&1; then
        docker update --restart=no "$name"
        docker stop --time 120 "$name"
    fi
done
```

Inspect `docker ps` and confirm they are stopped. Do not run old Compose `up` afterward. Keep the stopped containers and rollback files intact until verification. If a job begins before the stop, wait for completion rather than killing it.

## 3. Pull and generate root configuration

```sh
git pull --ff-only
nano .env
```

Keep `RESTIC_PASSWORD` and each node's `RESTIC_REPO_PATH` exactly as before. Set on **Ryzen**:

```dotenv
BACKREST_BIND_IP=192.168.1.120
IMMICH_EXPORT_DIR=/mnt/hdd2/immich
BACKREST_IMMICH_SSH_TARGET=pjh10@192.168.1.120
```

Use your actual existing deployment user instead of `pjh10`. Set on **Lenovo**:

```dotenv
BACKREST_BIND_IP=192.168.1.121
```

Remove obsolete root `RESTIC_BACKUP_TIME`, `RESTIC_BACKUP_CRON`, `RESTIC_MEDIA_CRON` and `RESTIC_CHECK_CRON` entries after recording rollback values; keep `RESTIC_PASSWORD` and `RESTIC_REPO_PATH`. If local `.bootstrap/vars.json` skips `restic`, replace that skip with `backrest` before any future provisioning; do not rerun bootstrap for this migration.

Both hosts: `BACKREST_PORT=9898`, `TZ=Europe/Amsterdam`, `BACKREST_ENABLE_SCHEDULES=false`; retain all existing app/HA host settings. Optional native cron values are documented in [backups](backups.md).

Generate a bcrypt authentication hash **locally**, without putting the password in command arguments/history (requires `htpasswd`, commonly `apache2-utils`):

```sh
# Prompts for a new BACKREST ADMIN password, not the existing Restic password.
htpasswd -nB admin | cut -d: -f2 | tr -d '\n' | base64 -w0
```

Copy the base64 result into ignored root `.env` as `BACKREST_AUTH_BCRYPT=...`. Protect the file with `chmod 600 .env`; never commit the hash/token/password. Initial username is `admin`. Existing Backrest auth, if any, is preserved by reconciliation; change it through the authenticated UI.

```sh
make config
make config-check
make validate
(cd stacks/storage/backrest && docker compose config -q)  # Ryzen
# Lenovo uses: (cd stacks/docker/backrest && docker compose config -q)
```

Missing external named volumes or unexpected paths are blockers; do not create empty substitute volumes. A root override applies to all generated stacks on that host; deploy only its actual target.

## 4. Ryzen: install the restricted Immich export hook

Use a dedicated key for **only** this export command. Keep an independent secure recovery copy; the key is excluded from file backups.

```sh
# Substitute your DOCKER_DATA if different.
install -d -m 700 /opt/homelab/data/backrest/ssh
ssh-keygen -t ed25519 -N '' -f /opt/homelab/data/backrest/ssh/id_ed25519
```

Do not overwrite an existing key. Add its `.pub` line to the existing deployment user's `~/.ssh/authorized_keys`, prefixed with the forced command and restrictions (replace `/actual/path/homeServer`):

```text
restrict,command="/usr/bin/python3 /actual/path/homeServer/scripts/immich-export-command.py" ssh-ed25519 AAAA... dedicated-backrest-immich
```

This account needs existing Docker access, read access to the checkout/root configuration, and write access to `IMMICH_EXPORT_DIR`. Do not grant an unrestricted key or interactive login. The forced helper ignores `SSH_ORIGINAL_COMMAND`, accepts no arguments, and can only produce an Immich logical export.

Verify Ryzen's SSH host-key fingerprint directly against `/etc/ssh/ssh_host_ed25519_key.pub` on Ryzen. Collect the public key with `ssh-keyscan -t ed25519 192.168.1.120`, compare the fingerprint out of band, then store the **verified** entry in `/opt/homelab/data/backrest/ssh/known_hosts` (mode 600). Do not disable host-key checking. Adapt keyscan/known_hosts for a nonstandard SSH port.

Test the forced command before Backrest starts:

```sh
ssh -T -i /opt/homelab/data/backrest/ssh/id_ed25519 \
  -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/opt/homelab/data/backrest/ssh/known_hosts \
  pjh10@192.168.1.120 immich-export
```

Confirm a **new**, nonempty `immich-db-*.sql.gz` in `IMMICH_EXPORT_DIR`; run `gzip -t` on that archive. The helper already validates the whole compressed stream and SQL header, but periodically test a full database restore separately. Verify SSH/firewall access from Docker bridge traffic too; allow the actual configured Docker source subnet if required, without opening public SSH. If this hook cannot succeed, do not enable the Storage plan.

## 5. Import and start Backrest (each host separately)

```sh
# Ryzen, root of existing checkout:
sudo make backrest-config NODE=storage
cd stacks/storage/backrest
docker compose up -d --wait --wait-timeout 180
```

On Lenovo:

```sh
sudo make backrest-config NODE=docker
cd stacks/docker/backrest
docker compose up -d --wait --wait-timeout 180
```

The helper refuses to import while any named legacy scheduler/Backrest is running. It reads `restic cat config` to obtain the existing GUID, writes schema-6 app configuration under `${DOCKER_DATA}/backrest/config`, requires authentication, and does **not** initialize a repo or start services. If credentials/mounts/GUID validation fail, resolve the issue; do not choose a new repo.

Log in at the configured LAN address/port, or use an SSH tunnel for browser administration. Verify instance IDs and repo `homelab`, password source, URI `/repo`, Auto Initialize/Auto Unlock off, Keep All and maintenance disabled. Index the repository and confirm historical `apps`, `infra`, `storage`, and `docker` snapshots at repository level. Do not accidentally create a second repo record with the same GUID. Follow [first-time multihost pairing](backups.md#first-time-pairing-ui); keep Shared Repos off in this monitoring-only design.

## 6. Verify before enabling schedules

1. In **Ryzen's UI**, run `storage-data` manually. Confirm its hook creates a new export **during this run**, then the backup succeeds with NAS, appdata and export paths. Check export age/content.
2. In **Lenovo's UI**, run `docker-appdata`. Verify Caddy certificate/config volume files, Unbound state, appdata and checkout coverage; no NFS media path is included.
3. Verify Restic hostname `storage`/`docker` and Backrest `created-by:`/`plan:` tags. Confirm Lenovo operation history arrives at Ryzen. Do not assume central sync can launch Lenovo operations.
4. From the shared repository, restore an individual file, a complete app directory and a historical Chromebox snapshot **into a new staging directory**, compare bytes, and confirm live source mounts were not written. See [recovery](disaster-recovery.md).
5. Run a structural repository check on Ryzen; schedule/read a data subset or full data check as capacity permits. No check may overlap an active prune or conflicting writer. Verify denied unauthenticated admin API access and allowed/denied network paths.

Now edit root `.env` on each host: `BACKREST_ENABLE_SCHEDULES=true`, then apply one host at a time:

```sh
# Use storage on Ryzen; substitute docker on Lenovo.
cd /actual/path/homeServer
(cd stacks/storage/backrest && docker compose stop backrest)
make config
make config-check
sudo make backrest-config NODE=storage
(cd stacks/storage/backrest && docker compose up -d --wait --wait-timeout 180)
```

Backup times default to 02:00 and 04:00; Storage check is Sunday noon. Automatic deletion remains disabled. Review upcoming runs in both UIs. Verify a scheduled run on each and inspect logs/freshness before retiring rollback containers.

## 7. Resume deployment ownership and retire old containers

After all checks, acknowledge adoption on each host (choose its node):

```sh
NODE=storage    # docker on Lenovo
mkdir -p ".deploy-state/$NODE"
printf '%s\n' 'Legacy jobs stopped; import, hook, pairing and staging restores verified' > ".deploy-state/$NODE/backrest-reviewed"
```

Keep the existing `.deploy-state/layout-v2-reviewed` from the earlier layout migration. Automatic deployment refuses the new backup stack until this additional marker exists. If Portainer manages Backrest, keep it out of Git timer ownership. Resume the existing deployment and health timers only after verifying their node/skip settings; generation does not rewrite running Backrest config.

Only **after successful manual and scheduled backups, restores and integrity checks**, optionally remove the old **stopped** containers explicitly:

```sh
for name in restic restic-media restic-check; do
    if docker container inspect "$name" >/dev/null 2>&1; then
        test "$(docker inspect -f '{{.State.Running}}' "$name")" = false || exit 1
        docker rm "$name"   # no -f and no -v; keep repositories, data and volumes
    fi
done
```

Never run `docker compose down --remove-orphans`, volume pruning or snapshot cleanup as part of this migration.

## Rollback

Pause deployment/health timers. Wait for Backrest operations to finish, disable its restart policy and stop it manually (`docker update --restart=no backrest`; `docker stop --time 120 backrest`). Preserve its entire state and newly created snapshots. Never start legacy backup jobs while Backrest is still running.

Restore the recorded pre-migration checkout/configuration from the secure archive, preserving credentials, repo GUID, data and named volumes. If old containers remain, restore their recorded restart policies and start only the backup jobs you deliberately need. If they were removed, review the old Compose configuration and recreate only the intended backup project. Do **not** re-enable old broad forget/prune or automatic repository initialization; preserve all snapshots. Re-enable old scheduling only after verifying mounts, password and a staging restore. Image rollback cannot reverse app-state/schema changes; Backrest config/operation DB formats may require the saved same-version state copy.
