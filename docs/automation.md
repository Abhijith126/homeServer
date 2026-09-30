# Automated image updates

Renovate runs as the free Mend-hosted [GitHub app](https://github.com/apps/renovate). It reads `renovate.json` in this repository and opens dependency PRs. It does not run on a homelab node. Portainer runs on infra and deploys Git stacks to the appropriate Docker environment after changes reach main.

## Enable Renovate

1. Install the Renovate GitHub app for Abhijith126 and select only the homeServer repository.
2. Ensure repository Issues are enabled for the Dependency Dashboard.
3. Check the Dashboard and any onboarding PR. The repository already contains its configuration; review any proposed replacement before merging.
4. Confirm the first update PR passes both CI jobs: `validate` and `renovate-config`.

The app manages its own credentials. No GitHub token or scheduled Renovate Actions workflow is needed. The CI container only validates the configuration; it does not run the update bot.

## Update policy

| Update | Merge policy |
| --- | --- |
| Selected application patch and digest updates | Renovate merges after successful checks |
| Initial image digest pinning | Review |
| Minor and major versions | Review |
| Immich and database dependencies | Review together against upstream release notes |
| Portainer server and agents | Review together; apply agent changes with Ansible |
| Caddy local image | Review and rebuild on infra |
| Backups, qBittorrent, Home Assistant, other images | Review |

The automatic list is Bazarr, Lidarr, Prowlarr, Radarr, Sonarr, Homarr, Uptime Kuma, FileBrowser, Beszel hub/agent, and the portfolio Node runtime. All other dependencies require review. Beszel hub and agent updates are grouped.

Renovate may create update branches and automatically merge from midnight until 05:00 Europe/Amsterdam. The hosted service runs on its own cadence; this is an allowed window, not an exact execution time. Manual merges can happen outside the window. Portainer polling is independent of this window.

Registry images are pinned to digests as well as tags. LinuxServer version and packaging revisions are tracked separately, and qBittorrent keeps its libtorrent compatibility suffix. Custom managers track the Immich version variable, Ansible's Portainer agent version, and every Caddy build/tag version.

CI validates Compose, lint, secrets, and the Renovate configuration. It does not test application startup or data migrations. Keep backups and check service health after deployment. For additional enforcement, make both CI jobs required checks in a GitHub branch rule for main.

## Configure Portainer GitOps

Use Portainer Business Edition for automatic Git polling. Manage all three environments from the infra Portainer server; apps and ryzen use agents.

For each stack:

1. Select its target environment, then **Stacks → Add stack → Repository**.
2. Use `https://github.com/Abhijith126/homeServer` and reference `refs/heads/main`.
3. Set the Compose path from the table below. Keep the existing stack/project name.
4. Run `make config` in your local checkout using your real root `.env`, then import that stack's generated `.env` into Portainer's environment variables. Never commit it.
5. Enable **GitOps updates / Automatic updates**, choose **Polling**, and set an interval such as 5 minutes.
6. Enable **Re-pull image**. Leave **Force redeployment** disabled.
7. Deploy and check container health, ports, and persistent mounts before enabling the next stack.

| Environment | Stack | Compose path |
| --- | --- | --- |
| apps | portfolio | `stacks/apps/portfolio/compose.yaml` |
| apps | sonarr | `stacks/apps/sonarr/compose.yaml` |
| apps | uptime-kuma | `stacks/apps/uptime-kuma/compose.yaml` |
| ryzen | immich | `stacks/storage/immich/compose.yaml` |

Repeat for other stacks using their corresponding paths. If the repository is private, configure read access in Portainer. GitHub needs no inbound connection to the nodes for polling.

When migrating an existing CLI stack, schedule a short outage and stop/remove its containers before deploying the Git stack; preserve all volumes and bind mount paths. Do not delete data volumes or deploy a second copy of the same application.

Portainer stores imported variables separately from Git. Changes to `.env.example` do not update a deployed stack's variables. For Immich version changes, regenerate and re-import its environment before redeploying; check the upstream Compose and database requirements first.

Caddy needs a local Cloudflare-enabled build and its Caddyfile/token files. Keep its documented local deployment procedure until those files/builds are explicitly configured in Portainer. Renovate updates the Dockerfile default, Compose build argument, and local image tag together; on infra rebuild with `docker compose build --pull caddy` before deployment. Portainer server updates also require a deliberate maintenance operation because it manages its own deployment.

## Portfolio releases

The portfolio stack downloads the latest verified standalone release ZIP on container startup. Renovate updates its Node container image; it does not track portfolio release ZIPs.

A new release in the portfolio repository alone does not change homeServer and therefore does not trigger Portainer Git polling. To deploy a new portfolio release, redeploy/recreate the portfolio container in Portainer, or run `docker compose up -d --force-recreate portfolio` from its stack directory. Fully automatic application-release deployment needs an additional release notification or a version update in homeServer.

## Rollback

Revert the image update commit and let Portainer reconcile the previous image. For environment changes, restore the previous imported variables too. Database migrations may require restoring a backup; an image revert alone cannot undo them. See [upgrade.md](upgrade.md).
