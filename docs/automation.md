# Automated deployment on three nodes

Renovate opens image-update PRs. Once a PR is merged to main, a systemd timer on each node pulls the Git change and deploys that node's Compose stacks. No inbound webhooks, GitHub runner on the server, or Portainer license is needed.

| Machine | Deployment node | Directory |
| --- | --- | --- |
| apps | apps | stacks/apps |
| ryzen | storage | stacks/storage |
| infra | infra | stacks/infra |

The same scripts work on every machine and can be reused in another homelab by changing the checkout's Git remote and stack folders.

## One-time setup on each node

Run this command once on each machine (requires curl):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Abhijith126/homeServer/main/scripts/setup.sh) --schedule weekly
```

Choose storage on ryzen, apps on the application node, and infra on the infrastructure node. Provision storage first. The wizard installs prerequisites, configures the host, gathers local configuration and credentials, installs the timer, and starts the first deployment. See [bootstrap.md](bootstrap.md) for supported hosts, optional integrations, and storage/network prerequisites.

For an already provisioned host, install-auto-deploy.sh remains available separately. Bootstrap supplies its mount paths and skipped stacks automatically.

## What happens after a merge

1. Fetch main and fast-forward the local checkout. Tracked local edits or a divergent branch stop deployment.
2. Record managed image IDs before replacing containers; do not delete images before deployment.
3. If the Git revision, root .env, or Caddy token file changed, regenerate node-specific environment files. A failed attempt is retried at the next timer run.
4. Discover all Compose stacks in that node's folder and validate them before changing containers.
5. Back up an existing Immich database; abort that stack if the backup fails. Pull registry images, build local images such as Caddy, and run Compose up with --remove-orphans and --wait. Changed containers are recreated; unchanged containers stay running. Caddy's mounted configuration is explicitly reloaded.
6. After successful deployment, remove previously observed homelab images unused for at least 14 days. Failed deployments preserve all images. Record success only after deployment and cleanup succeed.

Retention is measured from observed disuse, not image creation age. State lives in .deploy-state/<node>/images.json. Unknown/unmanaged images are not collected; images referenced by any running or stopped container are retained. There is no force deletion, volume pruning, or automatic database rollback. Successful unchanged checks can collect expired images too. Losing the retention state can leak old images but cannot accelerate deletion.

A new folder under stacks/<node>/<app> is discovered automatically on the next merge; no new deployment entry is needed. Use the existing new-app scaffolder and provide any new secrets in the node's root .env. Removed services within a Compose project are cleaned up as orphans. Removing a whole stack folder does not delete that project's containers or data; retire whole stacks deliberately with Compose down, without -v.

Beszel agents have a stack in each node folder, so apps, storage, and infra all
receive Renovate's agent updates. Existing nodes must have BESZEL_AGENT_KEY set
in the root .env and must not skip beszel-agent. Reconfigure setup to enable a
previously skipped agent. CI checks that all three agent manifests stay aligned.

All Compose services use restart: unless-stopped. Docker restarts exited
containers and starts them after a daemon/host restart, unless explicitly
stopped. A manual stop persists across reboots. Healthcheck failure alone does
not restart a running container; recurring crashes still require fixing their
cause. These settings apply when Compose reconciles the containers, not merely
when the repository is pulled.

Deployments across nodes are independent and are not atomic. If one stack fails, others may already have updated. The node preserves images, records no successful revision, and retries at the next scheduled run. It does not automatically roll back database migrations.

## Renovate update policy

Install the free hosted [Renovate GitHub app](https://github.com/apps/renovate) with access to homeServer and select Renovate Only / Scan and Alert. It reads renovate.json; no update-bot container or GitHub token is needed on the nodes.

| Update | Merge policy |
| --- | --- |
| Docker minor/patch-only batch | Auto-merge after successful CI |
| Major, digest, or initial pin in the batch | Review the whole batch |
| Immich PostgreSQL or Valkey changes | Review the whole batch against Immich upstream Compose |

All Docker updates share one PR. GitHub Actions updates remain separate. Immich app minor/patch updates are eligible for auto-merge; both app containers use the same committed IMMICH_VERSION.

All existing Compose stacks are tracked, including Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, Homarr, Home Assistant, Jellyfin, FileBrowser, Uptime Kuma, qBittorrent/Gluetun, and portfolio. LinuxServer packaging revisions and qBittorrent's libtorrent compatibility suffix are tracked. Custom managers track Immich's version variable, Ansible's optional Portainer agent version, and Caddy's local build version.

Renovate's update and auto-merge windows are Sunday, 00:00–24:00 Europe/Amsterdam, ahead of the default Monday 03:00 weekly deployments. Existing branches are not updated outside that window (updateNotScheduled=false). The hosted app may still scan on other days; the schedule controls when routine changes and automerges are allowed, not the app's execution cadence. Security alerts or explicit manual requests can bypass routine scheduling. The full Sunday window gives CI and hosted runs time to complete; updates that are not merged before deployment wait for a later deployment. Changing a node's deployment schedule does not automatically change Renovate's repository-wide schedule. Manual merges deploy whenever each node next polls. CI validates configuration, lint, and secrets, but does not test real application startup or data migrations. Make validate and renovate-config required checks in a main branch rule if you want GitHub to enforce them for manual merges too.

## Everyday operations

```bash
# Force a retry/reconcile even when the recorded revision matches:
make auto-deploy NODE=apps

# See the timer and deployed commit:
systemctl list-timers homelab-deploy.timer
cat .deploy-state/apps/revision

# Pause deployments:
sudo systemctl stop homelab-deploy.timer

# Resume:
sudo systemctl start homelab-deploy.timer
```

To change skipped stacks, run ./scripts/setup.sh --reconfigure. For a manual override, use sudo systemctl edit homelab-deploy.service:

```ini
[Service]
Environment="HOMELAB_SKIP_STACKS=portainer another-stack"
```

Then sudo systemctl daemon-reload. Portainer is excluded by default and its Ansible agent is opt-in. It can remain installed as an optional UI, but do not let a second system automatically deploy these same projects. To include its stack, set HOMELAB_SKIP_STACKS to an empty value. Bootstrap reinstalls the service/timer when configuration changes; repository script changes arrive through Git automatically.

Revert a version commit in Git to deploy the previous image. For database migrations, consult the application upgrade notes and restore a backup if required.

## Portfolio release ZIPs

Portfolio's pinned release ZIP is baked into a local image during deployment; startup has no downloads. Renovate tracks its Dockerfile release pin and Node base image. Release changes require review.

Release selection now lives in Dockerfile. Remove old PORTFOLIO_RELEASE overrides from .env; they are no longer used. See the stack README for migration and rollback.

## Update schedule

### Independent health checks

Re-run the timer installer with existing schedule, mounts and skip list (or setup
reconfiguration) to install homelab-health.timer. Git pull alone does not create
this new unit. It runs every 15 minutes independently of updates, skipping while
a deployment holds the shared lock. It checks expected Compose services for
missing/stopped/unhealthy replicas and restic snapshots by node/tag. Services
without healthchecks are checked for running state only.

The default backup freshness window is 120 hours, allowing the Wed/Sun schedule
plus grace. Override HOMELAB_BACKUP_MAX_HOURS in the health service for different
schedules. Skipped restic stacks are not checked. Freshness does not prove data
consistency or restorability.

Alerts use existing root .env SMTP settings. Unchanged health stays quiet;
changed failures/recovery notify. Failed delivery retries for ongoing failures.
Local results live in .deploy-state/<node>/health.json. No automatic restarts or
database rollbacks occur. Use external monitoring for dead nodes or broken SMTP.
View journalctl -u homelab-health.service. Keep HOMELAB_SKIP_STACKS aligned in
both units when editing manually; reconfiguration installs the same list in both.

### Deployment cadence

On an already bootstrapped node, the same setup command changes only the schedule and preserves credentials. From its checkout:

```bash
./scripts/setup.sh --schedule daily --time 03:00
./scripts/setup.sh --schedule weekly --time 03:00
./scripts/setup.sh --schedule monthly --time 03:00
```

Weekly means Monday; monthly means the first of the month. Times use the node's configured timezone (Europe/Amsterdam by default), with up to 30 seconds of jitter. Hourly and 5min are also supported; --time applies only to daily/weekly/monthly. Calendar timers catch up after downtime. Initial bootstrap deploys immediately. Failed updates retry at the next scheduled check; manually retry with sudo systemctl start homelab-deploy.service. Setup saves the schedule per node in .bootstrap/vars.json. A failed setup can leave the timer paused; rerun setup after fixing the error.

## Immich updates

The committed stacks/storage/immich/.env.example supplies IMMICH_VERSION to both server and machine-learning. Remove an IMMICH_VERSION override from the node's root .env if you want Renovate's committed version to take effect. Do not replace it with latest or release.

Before any scheduled reconciliation of an existing Immich stack, a database dump is written to NFS_BACKUP/immich. Only successful dumps become .sql.gz archives; seven are retained. A failed dump or stopped existing database blocks that stack's update. A fresh installation with an empty database directory needs no dump. Photos are not included: back up IMMICH_LIBRARY separately; RAID is not a backup.

PostgreSQL/vector extensions and Valkey must match Immich's upstream requirements. Their updates require review even when nominally minor or patch. Read release notes for app upgrades too. Database migrations are not automatically reversible: do not downgrade an Immich image to recover a failed upgrade. Restore a compatible database backup using the instructions for that release, along with photo files if needed.

## Deployment emails and history

The updater reads SMTP_HOST, SMTP_PORT, SMTP_SECURITY, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, and SMTP_TO from the ignored root .env on each node. See the root .env.example for Brevo defaults. Use starttls on port 587 or ssl on port 465; certificate verification is required. SMTP_PASSWORD is the Brevo SMTP key. No additional container is needed. Uptime Kuma's notification settings remain separate in its persistent application data; its stack environment does not configure SMTP notifications.

One report is sent after container changes or a failed run. It includes node/hostname, UTC timestamps, Git revision, old/new image references and image IDs, recreated/added/removed containers, failed steps, and available space on Docker's filesystem. Image-retention decisions are in the deployment journal; the legacy prune-total fields may be unavailable because host-wide pruning no longer runs. A successful check without container changes stays quiet. Configuration-only changes that do not recreate containers (such as a Caddy reload) do not generate a success email. An unavailable container inventory is reported explicitly.

The last 50 run reports are retained as private JSON files under .deploy-state/<node>/history, including unchanged checks. Raw command output and secrets are not included in reports. Email delivery failures are recorded locally and do not fail or repeat a successful deployment; emails are not queued for retry. A powered-off node, hard-killed process, or unreachable SMTP server cannot send an alert; use Uptime Kuma for availability monitoring.

Existing timers pick up the code through Git. Because the running updater is parsed before fetching, its new reporting hooks start on the following scheduled run. No timer reinstall is required. Diun has been removed from the repository; an already running Diun container must be retired separately (the updater does not delete whole removed stacks).
