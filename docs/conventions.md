# Platform Conventions

The contract every stack follows. If you follow this, `make validate` (and CI) passes, and any stack behaves predictably across CLI, Ansible, and Portainer.

## 1. Layout & naming

- One app = one folder: `stacks/<node>/<app>/`, where `<node>` ∈ `storage | apps | infra`.
- Folder / stack / `container_name` / compose `name:` are all the same lowercase-kebab string (e.g. `pihole-unbound`).
- Each stack folder is **self-contained**: `compose.yaml`, `.env.example`, `README.md`, `backup.sh`, `restore.sh`. It can be copied, deployed, or turned into a Helm chart on its own.

Scaffold with:

```bash
make new-app NODE=<node> APP=<app> CAT=<category>
```

## 2. Compose standards

- **No `version:` key** (obsolete in the Compose spec).
- Top-level `name: <app>` sets a stable project name regardless of who deploys it.
- **Pin image tags** — never `:latest`. Renovate proposes tag/digest updates; selected patches and digest updates merge after CI. See [automation.md](automation.md).
- `restart: unless-stopped` everywhere (never `always`).
- `security_opt: [no-new-privileges:true]` by default; override only when an image genuinely needs privilege (documented in that stack's README).
- Every service defines a `healthcheck`.

### Cross-cutting fragments (YAML anchors)

The canonical anchors live in [`lib/compose/fragments.yaml`](../lib/compose/fragments.yaml): `x-logging`, `x-healthcheck-defaults`, `x-common`, `x-labels`. Because YAML anchors do not cross files, they are **vendored** into each stack's `compose.yaml` by the scaffolder — keeping stacks self-contained (survives Portainer going away, forkable, k3s-mappable). Edit the canonical file first, then keep stacks in sync.

## 3. Environment & secrets

**One file to configure.** The root [`.env`](../.env.example) (gitignored; copy from `.env.example`) is the single source of truth for shared defaults + every secret. Generate all per-stack `.env` files from it:

```bash
cp .env.example .env
$EDITOR .env         # set the SECRETS section
make config          # renders stacks/<node>/<app>/.env for every stack
```

- `make config` (`scripts/gen-env.sh`) takes each stack's committed `.env.example` defaults and overrides any key you set in the root `.env`. It **refuses to finish** while any secret is still `CHANGEME`, so you can't half-configure. `make config-check` verifies without writing.
- Any key set in the root `.env` overrides that key in **every** stack that uses it (so `PUID`, `TZ`, `MEDIA_ROOT`, `DOMAIN` are set once). Node/stack-specific values (ports, `NFS_BACKUP`, image versions) stay as `.env.example` defaults.
- Stacks remain **self-contained**: each still gets its own `.env`, so `docker compose` and Portainer work per-folder. Generated `.env` files are derived artifacts — don't hand-edit them; change the root `.env` (or the stack's `.env.example`) and re-run `make config`.
- Only `.env.example` files are committed. **No hardcoded paths or credentials** in `compose.yaml` — everything via `${VAR}`.
- `env_file` uses `required: false` so `docker compose config` validates without a real `.env`.
- Upgrade path: dropping in SOPS/age later just means encrypting the root `.env` — no restructuring.

## 4. Volumes & storage

| Kind | Where | Rule |
| --- | --- | --- |
| **Config** (small, precious) | bind mount `${DOCKER_DATA}/<app>` on the local node | backed up by `backup.sh` |
| **Media / bulk** | NFS from ryzen (`${NFS_MEDIA}`, `${NFS_DOWNLOADS}`) | large, centralized |

**No irreplaceable data lives off the ryzen node.** `${DOCKER_DATA}` defaults to `/opt/homelab/data` (system path, created by Ansible — not tied to a user's `$HOME`).

## 5. Networking

- Cross-node traffic uses **published ports on the Tailscale/LAN interface** (Docker bridge networks are per-host, so a shared network can't span nodes).
- Each stack gets its own bridge network (`name: <app>`) for intra-stack communication.
- A shared external `proxy` network (created by `scripts/create-networks.sh`) is used when Caddy and an app are co-located on the same host.
- Reverse proxy is a **static, templated Caddyfile** with explicit per-node upstreams (label-based auto-discovery cannot work across three hosts).

## 6. Logging

- `json-file` driver, `max-size: 10m`, `max-file: 3` per service (via `x-logging`), and set globally in `daemon.json` by the Ansible docker role.

## 7. Labels

| Label | Value |
| --- | --- |
| `homelab.managed` | `"true"` |
| `homelab.node` | `storage` / `apps` / `infra` |
| `homelab.stack` | the app name |
| `homelab.category` | `media`, `arr`, `infra`, `monitoring`, `tools`, … |
| `diun.enable` | `"true"` (update notifications) |

## 8. Backup & restore

- `backup.sh` — tars `${DOCKER_DATA}/<app>` → `${NFS_BACKUP}/<app>/<app>-<timestamp>.tar.gz`, keeps the newest 7. `--stop` for a consistent snapshot.
- `restore.sh` — restores newest (or a named) archive.
- restic backs up `/opt/homelab/data` on every node to the shared repo on `/mnt/hdd2` (the `stacks/<node>/restic` container stack, on a nightly cron). Photos + documents on `/mnt/nas` are backed up from the storage node as a separate `media` snapshot.
- Full rebuild is documented in `docs/disaster-recovery.md` *(Phase 4)*.

## 9. Restart & health

- `restart: unless-stopped`.
- Health checks use tools the image actually ships (`curl`/`wget`/app-native). Tune per stack.

## 10. Validation & CI

`make validate` (and `.github/workflows/ci.yml`) runs:

1. `docker compose config` on every stack (using `.env.example` for substitution)
2. template render + config smoke test
3. custom lint — no `version:`, no `:latest`, no `restart: always`
4. `yamllint`, `shellcheck`, `shfmt -i 4`, `gitleaks` (when installed)

CI also runs `renovate-config-validator --strict renovate.json` in a pinned Renovate container.

## 11. Versioning

- Pinned image tags; Diun/Renovate proposes bumps.
- Conventional commit messages; the platform itself is tagged semver.

## 12. k3s / Helm migration path

| Compose concept | Kubernetes concept |
| --- | --- |
| `stacks/<node>/<app>/` | Helm chart / kustomize dir |
| `.env` / `.env.example` | ConfigMap + Secret |
| NFS bind (`${NFS_*}`) | PersistentVolume + PVC |
| `homelab.*` labels | pod/deployment labels |
| Caddyfile route | Ingress |
| `homelab.node` | nodeSelector / affinity |
