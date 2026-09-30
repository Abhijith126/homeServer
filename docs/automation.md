# Automated deployment on three nodes

Renovate opens image-update PRs. Once a PR is merged to main, a systemd timer on each node pulls the Git change and deploys that node's Compose stacks. No inbound webhooks, GitHub runner on the server, or Portainer license is needed.

| Machine | Deployment node | Directory |
| --- | --- | --- |
| apps | apps | stacks/apps |
| ryzen | storage | stacks/storage |
| infra | infra | stacks/infra |

The same scripts work on every machine and can be reused in another homelab by changing the checkout's Git remote and stack folders.

## One-time setup on each node

First provision Docker, Compose, the shared networks, and storage mounts using [bootstrap.md](bootstrap.md). Use an existing checkout on main owned by your normal Docker-capable user, or clone one:

```bash
git clone https://github.com/Abhijith126/homeServer.git ~/homeServer
cd ~/homeServer
cp .env.example .env
chmod 600 .env
$EDITOR .env
```

Configure that node's real paths and secrets. The deployment service regenerates only that node's stack .env files from the root .env and committed defaults. Do not set image-version overrides in the root .env unless you deliberately want to override Renovate.

On infra, also configure Caddy's cloudflare.env using its example if using DNS-01. Verify the NAS and backup mounts before deploying.

Install once, using the node identifier from the table:

```bash
# On apps:
sudo ./scripts/install-auto-deploy.sh apps

# On ryzen:
sudo ./scripts/install-auto-deploy.sh storage

# On infra:
sudo ./scripts/install-auto-deploy.sh infra
```

Run only the appropriate command on each machine. The installer runs deployments as the user invoking sudo, expects the checkout to belong to that user, and installs homelab-deploy.service plus homelab-deploy.timer. Git, make, util-linux (flock), Docker and Compose must be installed. For a private Git remote, configure read-only SSH access for that user first; scheduled Git fetches never prompt for credentials.

The timer checks about every five minutes, with a small stagger between nodes. Start the first deployment immediately:

```bash
sudo systemctl start homelab-deploy.service
journalctl -u homelab-deploy.service -f
```

The unit requires /mnt/nas and /mnt/nfs/backup on apps/infra, and /mnt/nas plus /mnt/hdd2 on ryzen. If using different mount paths, change RequiresMountsFor in the service before the first run, then run sudo systemctl daemon-reload. Ensure these are real configured mounts: Docker must not silently create an empty directory in place of a missing NAS.

## What happens after a merge

1. Fetch main and fast-forward the local checkout. Tracked local edits or a divergent branch stop deployment.
2. If the Git revision, root .env, or Caddy token file changed, regenerate node-specific environment files. A failed attempt is retried at the next timer run.
3. Discover all Compose stacks in that node's folder and validate them before changing containers.
4. Pull registry images, build local images such as Caddy, and run Compose up with --remove-orphans and --wait. Changed containers are recreated; unchanged containers stay running. Caddy's mounted configuration is explicitly reloaded.
5. After all selected stacks are running or healthy, prune unused Docker images created more than seven days ago and record the successful revision.

The prune is host-wide and uses Docker's image creation timestamp, not time since last use. Images referenced by running or stopped containers are retained. Volumes and data directories are never pruned. Registry images removed by cleanup can be pulled again during rollback.

A new folder under stacks/<node>/<app> is discovered automatically on the next merge; no new deployment entry is needed. Use the existing new-app scaffolder and provide any new secrets in the node's root .env. Removed services within a Compose project are cleaned up as orphans. Removing a whole stack folder does not delete that project's containers or data; retire whole stacks deliberately with Compose down, without -v.

Deployments across nodes are independent and are not an atomic transaction. If one stack fails, other stacks may already have updated. The node records no successful revision and skips image cleanup, then retries. It does not automatically roll back database migrations.

## Renovate update policy

Install the free hosted [Renovate GitHub app](https://github.com/apps/renovate) with access to homeServer and select Renovate Only / Scan and Alert. It reads renovate.json; no update-bot container or GitHub token is needed on the nodes.

| Update | Merge policy |
| --- | --- |
| Application patches and digest updates | Auto-merge after CI, except Immich/backups |
| Beszel hub and agent patches/digests | Auto-merge together after CI |
| Initial digest pins | Review |
| Minor and major upgrades | Review |
| Immich/database, backups, Caddy, Portainer and other infrastructure | Review |

All existing Compose stacks are tracked, including Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, Homarr, Home Assistant, Jellyfin, FileBrowser, Uptime Kuma, qBittorrent/Gluetun, and portfolio. LinuxServer packaging revisions and qBittorrent's libtorrent compatibility suffix are tracked. Custom managers track Immich's version variable, Ansible's optional Portainer agent version, and Caddy's local build version.

Renovate's update/auto-merge window is midnight to 05:00 Europe/Amsterdam. Hosted runs have their own cadence. Manual merges deploy whenever each node next polls. CI validates configuration, lint, and secrets, but does not test real application startup or data migrations. Make validate and renovate-config required checks in a main branch rule if you want GitHub to enforce them for manual merges too.

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

To skip stacks, use sudo systemctl edit homelab-deploy.service:

```ini
[Service]
Environment="HOMELAB_SKIP_STACKS=portainer another-stack"
```

Then sudo systemctl daemon-reload. Portainer is excluded by default and its Ansible agent is opt-in. It can remain installed as an optional UI, but do not let a second system automatically deploy these same projects. To include its stack, set HOMELAB_SKIP_STACKS to an empty value. Re-run the installer when changing service/timer settings; repository script changes arrive through Git automatically.

Revert a version commit in Git to deploy the previous image. For database migrations, consult the application upgrade notes and restore a backup if required.

## Portfolio release ZIPs

Renovate tracks portfolio's Node image. Its existing startup script downloads the standalone ZIP configured by PORTFOLIO_RELEASE. A release published only in the portfolio repository does not change homeServer or restart its container.

To deploy that release through this mechanism, update PORTFOLIO_RELEASE to the exact tag in the committed portfolio .env.example, then merge. Remove the root .env PORTFOLIO_RELEASE=latest override first, so the committed value takes effect. Or manually recreate the portfolio container. Automatic cross-repository release propagation requires a separate release-PR integration.
