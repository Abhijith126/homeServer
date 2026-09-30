# Ansible — host bootstrap

One command turns a fresh Debian/Ubuntu box into a ready homelab node: base packages + hardening, Docker (with log rotation), Tailscale, NFS, firewall, and an optional Portainer agent.

## Local one-command setup

For a fresh clone on each node, run `./scripts/bootstrap-node.sh` from the repository root. It installs Ansible, generates a local inventory and settings, and runs `ansible/bootstrap.yml`. See [bootstrap.md](../docs/bootstrap.md). The instructions below describe advanced provisioning from a separate workstation.

## Prerequisites

- SSH access to each host as a sudo user (`ansible_user`, default `pjh10`).
- Ansible on your workstation (`pipx install ansible` or `uv tool install ansible`).
- Collections:

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

## Configure

1. Edit `inventory.ini` — set each node's **LAN IP**.
2. Review `group_vars/` — `all.yml` (identity, NFS, firewall defaults) and the per-node files (`storage_nodes.yml`, `app_nodes.yml`, `infra_nodes.yml`).
3. Get a Tailscale **auth key** from the admin console (pass it at run time — never commit it).

## Run

```bash
ansible-playbook site.yml --check --diff                       # dry run first
ansible-playbook site.yml -e tailscale_authkey=tskey-auth-XXXX # all nodes
ansible-playbook site.yml --limit infra -e tailscale_authkey=… # one node
```

## What each role does

| Role | Applies to | Does |
| --- | --- | --- |
| `common` | all | timezone, base packages, `/opt/homelab/data`, unattended security upgrades, SSH hardening, UFW (deny-in, allow SSH + `tailscale0` + per-node LAN ports), optional `systemd-resolved` port-53 fix |
| `docker` | all | Docker CE + compose plugin from the official repo, `daemon.json` log rotation + live-restore, `docker` group, shared `proxy` network |
| `tailscale` | all | install + `tailscale up --ssh` |
| `nfs_server` | storage | export `/mnt/nas` + `/mnt/hdd2` to the LAN |
| `nfs_client` | apps, infra | mount them at `/mnt/nas` + `/mnt/nfs/backup` (systemd automount) |
| `portainer_agent` | apps, storage (opt-in) | Optional Portainer agent on `:9001` |

## Notes / gotchas

- **OS repositories:** local bootstrap uses the installed OS codename for Docker. On Debian 13 it uses the configured bookworm fallback for Tailscale.
- **SSH lockout:** `ssh_disable_password_auth` defaults to `false`. Only flip it to `true` after confirming key login works.
- **ryzen uses snap Docker today.** This role installs apt Docker (the standard) and is aimed at the fresh apps/infra nodes; migrating ryzen off snap is a manual step (reinstall Docker, re-point stacks at `/opt/homelab/data`).
- **NFS performance:** set `nfs_server_host` (in `group_vars/all.yml`) to ryzen's LAN IP rather than a Tailscale name.
- After provisioning, install the [automatic deployment timer](../docs/automation.md) on each node. Portainer agents are disabled by default; enable them only if you want the optional UI.
