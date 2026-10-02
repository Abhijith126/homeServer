# portfolio

> Personal website — runs on the **apps** node · category: `web`

This stack downloads the compiled build from
[Abhijith126/portfolio releases](https://github.com/Abhijith126/portfolio/releases)
and runs it with Node.js 22 Alpine on Linux x86-64. Every push or merge to the
portfolio repo's main branch publishes a build ZIP. The homeServer repo owns
Compose; the portfolio repo owns the application build.

## Access

| Access | Address |
| --- | --- |
| Proxy | `https://portfolio.${DOMAIN}` |
| Local | `http://apps:3000` by default |
| Node | `apps` |

The default host port remains 3000 to match Caddy and the apps-node firewall.
The internal container port is always 3000.

## Configure and deploy

Use the existing root `.env` and `make config` flow. Portfolio no longer needs
`PORTFOLIO_IMAGE` or a container registry account. Its default setting is
`PORTFOLIO_RELEASE=latest`; set an exact release tag in the root `.env` to pin
or roll back to a build.

From the homeServer checkout:

```bash
git pull --ff-only
make config
cd stacks/apps/portfolio
docker compose up -d --wait --wait-timeout 180
docker compose logs --tail=100 portfolio
```

A standalone copy of this stack can use `cp .env.example .env` instead of
`make config`. In Portainer, select `stacks/apps/portfolio/compose.yaml` as
the Git stack Compose path; defaults also work without an `.env` file.

## Deploy a new release

Once the portfolio build workflow has published a new release:

```bash
docker compose up -d --force-recreate --wait --wait-timeout 180
```

On each container start, `latest` resolves to an exact release tag, then the
container downloads that tag's `portfolio-build.zip` and SHA-256 checksum.
It verifies and extracts the ZIP, then runs `node server.js` as the non-root
`node` user. It does not run npm install or build the app on the server.
A running container keeps its current build until restarted or recreated.

The startup installs curl, unzip, and su-exec inside the container, so outbound
access to GitHub, Docker Hub, and Alpine package mirrors is required.
If downloads or checksum verification fail, startup stops and the container
restart policy retries. The health check allows two minutes for startup.

## Pin or roll back

Set `PORTFOLIO_RELEASE` in the root `.env` to an existing release tag from
GitHub Releases, run `make config`, and recreate this stack. Set it back to
`latest` to select the latest release on startup. With `latest`, automatic
container restarts may also pick up a newly published app release.

## Notes

Stateless: no host mounts, data volumes, or backup scripts. The app is restored
from the release ZIP. Image downloads are tracked separately from app releases.
This stack preserves the homelab security, logging, network, and management-label conventions.
