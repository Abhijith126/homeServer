# 🏠 Homelab

A reproducible, version-controlled **Docker-Compose homelab platform** — Infrastructure as Code for a three-node self-hosted setup. Every service is a self-contained stack that deploys identically from the CLI, from Ansible, or as a Portainer Git stack, and is structured to migrate cleanly to k3s + Helm later.

## Nodes

| Node        | Hostname | Role         | Runs                                                                 |
| ----------- | -------- | ------------ | ------------------------------------------------------------------- |
| **storage** | `ryzen`  | Storage + media | Immich, Jellyfin, Postgres, Redis, qBittorrent, FileBrowser, Portainer agent |
| **apps**    | `apps`   | Applications | Home Assistant, Sonarr/Radarr/Lidarr/Bazarr/Prowlarr, Homarr, Uptime Kuma, portfolio, Portainer agent |
| **infra**   | `infra`  | Infrastructure | Pi-hole + Unbound, Caddy, Tailscale, Beszel monitoring, **Portainer BE server** |

Storage lives on **ryzen** and is consumed by the other nodes over **NFS** — no irreplaceable data lives on the app/infra nodes.

## Repository layout

```
homelab/
├── ansible/            # host provisioning: docker, nfs, tailscale, ufw, ssh, portainer-agent
├── stacks/             # deployable apps, grouped by node
│   ├── storage/        #   → ryzen
│   ├── apps/           #   → apps
│   ├── infra/          #   → infra
│   └── _template/      # canonical stack skeleton (compose + env + readme + backup/restore)
├── lib/compose/        # shared cross-cutting fragments (logging, healthcheck, labels)
├── scripts/            # new-app scaffolder, validate (local CI), create-networks
├── docs/               # architecture, networking, bootstrap, upgrade, disaster-recovery
├── .github/workflows/  # CI: compose config + yamllint + shellcheck + gitleaks
└── Makefile            # make validate | new-app | networks
```

## Quick start

Run once on each Debian 12+ / Ubuntu 24.04+ node as your normal sudo user (requires curl):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Abhijith126/homeServer/main/scripts/setup.sh) --schedule weekly
```

Choose storage, apps, or infra when prompted. Run storage first. The script gathers local settings, installs prerequisites, provisions Docker/NFS/firewall, configures services, and enables deployment from Git. Rerunning it preserves existing secrets.

Someone else can fork this repo and run the same script with their own machine addresses, paths, domain, and credentials. Read [bootstrap.md](docs/bootstrap.md) for prerequisites and optional integrations.

Scaffold a new service:

```bash
make new-app NODE=apps APP=sonarr CAT=arr
```

Validate everything locally (mirrors CI):

```bash
make validate
```

## Automatic deployment

Renovate proposes image updates. After a merge to main, each node's systemd timer deploys every Compose stack in its own folder and prunes unused images after successful startup checks. Install once per node using [docs/automation.md](docs/automation.md). Portainer is optional.

## Conventions

Every stack follows one contract — naming, volumes, secrets, health checks, labels, backups. See **[docs/conventions.md](docs/conventions.md)**.

## Documentation

| Doc | Purpose |
| --- | --- |
| [architecture.md](docs/architecture.md) | System, media-flow & storage diagrams |
| [networking.md](docs/networking.md) | Networks, ports, reverse-proxy routes, DNS, firewall |
| [hardware.md](docs/hardware.md) | Nodes, specs, storage layout |
| [bootstrap.md](docs/bootstrap.md) | Provision a host & deploy stacks |
| [upgrade.md](docs/upgrade.md) | Update workflow & rollback |
| [automation.md](docs/automation.md) | Renovate, automatic deployment on three nodes & image cleanup |
| [disaster-recovery.md](docs/disaster-recovery.md) | Backups & rebuild-from-zero runbook |
| [conventions.md](docs/conventions.md) | The platform contract every stack follows |

## Design principles

- **Portainer-optional** — the repo + plain `docker compose` is the source of truth; Portainer BE is a convenience layer, never a dependency.
- **Self-contained stacks** — one folder = one deployable unit = one future Helm chart.
- **No secrets in git** — `.env` is gitignored; only `.env.example` templates are committed.
- **No hardcoded paths** — everything flows through `.env`.
- **k3s-ready** — stack→chart, `.env`→ConfigMap/Secret, NFS→PVC, labels→k8s labels.
