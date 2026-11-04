# Recovery testing and disaster recovery

Use [Backrest coverage and consistency limits](backups.md) to choose a usable backup. An online snapshot of a live database is not proof of application recoverability. Keep an independent/off-site repository copy and offline custody of the Restic password.

## Browser-based recovery

1. Log in to the instance that will perform the restore. Ryzen can browse the shared repository's snapshots from either host; operation-history sync is not remote restore execution.
2. Open repo `homelab`, index/list snapshots at **repository level** (clear any plan filter), and inspect date, host and tags. New plans use `created-by:storage`/`created-by:docker` and `plan:storage-data`/`plan:docker-appdata`; historical `apps`/`infra` snapshots keep their original tags.
3. Browse files in the selected snapshot. Download a single config file through the browser, or restore a selected directory to a **new** `/restore/drill-YYYYMMDD/app` path. `/restore` maps to `${DOCKER_DATA}/backrest/restores` on the executing host.
4. Compare checksums/content and file ownership/modes. Inspect a whole application directory including its database export, not just a text file. Restore an `apps` or `infra` snapshot too and compare against known expected bytes.
5. Keep application sources read-only. Do not restore to `/sources/...`, `/repo`, `/config`, `/state`, `/cache`, `/tmp` or `/`; Backrest has admin-level file access to its writable state, so staging requires an explicit operator choice. The UI is not a sandbox against a malicious administrator.
6. To recover production, separately stop the affected application in an approved window, validate a database restore in isolation, and explicitly copy only selected verified data from staging. Web restores do not automatically apply files to Lenovo when run on Ryzen.

For a full application restore, choose the snapshot directory `/sources/appdata/<app>` (older snapshots use `/data/<app>`). Named-volume backups are `/sources/volumes/...` (older `/volumes/...`). Do not invent new Docker volume/project names; restore verified files into the recorded existing volume only during an approved recovery. For Immich, restore its logical PostgreSQL SQL export and matching library; never restore the excluded raw live PostgreSQL directory as the primary recovery method.

## Safe CLI fallback and historical snapshots

The helper retains host/tag validation and restores only into an absolute **non-existing** staging directory:

```sh
# From the checkout root. These preview without writing restored data:
python3 scripts/restic-restore.py docker homelab /mnt/recovery/docker --snapshot SNAPSHOT_ID
python3 scripts/restic-restore.py storage media /mnt/recovery/media --snapshot SNAPSHOT_ID
python3 scripts/restic-restore.py apps homelab /mnt/recovery/old-apps --snapshot SNAPSHOT_ID
# Add --execute after review. Create only /mnt/recovery, not the leaf directory.
```

Historical `apps`/`infra` use the current Lenovo Backrest Compose directory; run those commands there or use Ryzen's repo UI if Lenovo is unavailable. Explicit snapshot IDs are checked against host/tag metadata, since Restic itself can ignore filters for explicit IDs. The helper invokes the pinned image's Restic engine and does not start a second scheduler. `--verify` checks restored content. Keep staging separate from production data and the repository.

## Repository integrity

From Ryzen's `stacks/storage/backrest`, with both writers idle:

```sh
docker compose exec -T backrest restic check
# Optional full data read: substantially more I/O/time.
docker compose exec -T backrest restic check --read-data
```

The Backrest repo UI can schedule equivalent checks on Ryzen only. Never force-unlock an active other-host operation; maintenance is centralized on Ryzen. Record results, and test actual restores even after checks pass.

## Recover Backrest's own configuration and operation database

The backup plans include `backrest/config` but intentionally exclude the live `backrest/data` database, caches, temporary/restored data and private SSH export key. Backrest's UI configuration contains credentials/peer identities and must be protected. Periodically create a **quiesced**, independent copy of both config and data, especially before image upgrades:

```sh
# Operator action on the selected host; wait for operations to finish first.
cd stacks/storage/backrest             # Lenovo: stacks/docker/backrest
docker compose stop backrest
# Substitute configured DOCKER_DATA and an independent secure backup destination.
sudo tar -czf /secure/independent/backrest-state-YYYYMMDD.tar.gz \
  -C /opt/homelab/data/backrest config data
sudo chmod 600 /secure/independent/backrest-state-YYYYMMDD.tar.gz
# Validate archive readability before restarting.
sudo tar -tzf /secure/independent/backrest-state-YYYYMMDD.tar.gz >/dev/null
docker compose up -d --wait
```

Do not store this archive only on the same disk it protects, and never include it in Git. Keep a separately secured copy of the dedicated export SSH key and verified host keys. Restore the archive into **new staging**, inspect it, then stop Backrest and explicitly restore same-version config/data with original owners/modes. Preserve unique `storage`/`docker` identities; do not clone one identity onto two hosts. Database schema rollback requires the prior-version quiesced state, not just an older image.

If the operation database is lost but config/repo/password survive, re-index snapshots in the existing repository. Snapshot contents remain recoverable; historical operation logs may be lost. If config is lost, import the existing repo GUID with the original password, recreate authentication/plans and re-pair peers. Never initialize the repository to rebuild the UI.

## One server offline

- **Lenovo offline:** Ryzen's local repository remains usable. Browse/restore Lenovo and historical snapshots into Ryzen staging, rebuild the VM separately, then explicitly transfer recovered app state/volumes. No remote operation can run on a powered-off client.
- **Ryzen offline:** Lenovo loses both the NFS repository and central dashboard; local UI can show cached history but cannot create/restore backups from an unavailable repository. Recover Ryzen/storage or use an independently verified repository copy. Do not initialize a new repository on the empty/unmounted NFS mount point. Confirm `findmnt` and the repository GUID before retrying.
- **Both lost:** restore storage/repository infrastructure first, supply the original Restic password, import into Backrest, test staged data recovery, then rebuild Lenovo and HA using their separate VM/file backups.

## Proxmox and Home Assistant

Backrest file backups complement, not replace, Proxmox scheduled VM backups. Configure Proxmox `vzdump`/native backup jobs separately for the **complete Lenovo Docker VM** and **Home Assistant VM** to a dedicated Ryzen-backed datastore/share. Schedule them outside heavy NAS/Restic windows, choose VM-consistency options supported by the guests (guest agent/filesystem freeze where applicable), and test VM restore on an isolated network. Home Assistant's own backup/export remains useful for application recovery. Neither Backrest file mounts nor copied live virtual disks constitute a full VM backup.

Back up Proxmox host configuration and keep an independent/off-site copy of VM backups; Ryzen loss must not erase every recovery path. This repository does not install Proxmox Backup Server or create/change Proxmox jobs automatically.
