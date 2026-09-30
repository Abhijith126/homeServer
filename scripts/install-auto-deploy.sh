#!/usr/bin/env bash
# Install on an existing, configured node: sudo ./scripts/install-auto-deploy.sh apps
set -euo pipefail

[[ $EUID -eq 0 ]] || {
    echo "Run this installer with sudo" >&2
    exit 1
}
node="${1:-}"
case "$node" in apps | storage | infra) ;; *)
    echo "usage: sudo $0 <apps|storage|infra>" >&2
    exit 1
    ;;
esac
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_user="${SUDO_USER:-root}"
[[ "$repo_root" != *[[:space:]]* ]] || {
    echo "Use a checkout path without spaces" >&2
    exit 1
}
for command in git docker flock make; do
    command -v "$command" >/dev/null || {
        echo "Install $command first" >&2
        exit 1
    }
done
[[ -f "$repo_root/.env" ]] || {
    echo "Configure $repo_root/.env first" >&2
    exit 1
}
[[ "$(stat -c %U "$repo_root")" == "$run_user" ]] || {
    echo "Checkout must belong to $run_user" >&2
    exit 1
}
mounts="/mnt/nas /mnt/nfs/backup"
[[ "$node" != storage ]] || mounts="/mnt/nas /mnt/hdd2"

cat >/etc/systemd/system/homelab-deploy.service <<EOF
[Unit]
Description=Deploy homelab Compose stacks from Git
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service
RequiresMountsFor=$mounts

[Service]
Type=oneshot
User=$run_user
WorkingDirectory=$repo_root
Environment=HOMELAB_SKIP_STACKS=portainer
Environment=GIT_TERMINAL_PROMPT=0
Environment="GIT_SSH_COMMAND=/usr/bin/ssh -oBatchMode=yes"
ExecStart=$repo_root/scripts/auto-deploy.sh $node
TimeoutStartSec=45min
UMask=0077
EOF
cat >/etc/systemd/system/homelab-deploy.timer <<'EOF'
[Unit]
Description=Check homelab Git updates every five minutes

[Timer]
OnActiveSec=2min
OnUnitInactiveSec=5min
RandomizedDelaySec=30s
Unit=homelab-deploy.service

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now homelab-deploy.timer
echo "Installed for $node. First check in about two minutes."
echo "Run now: sudo systemctl start homelab-deploy.service"
echo "Logs: journalctl -u homelab-deploy.service -f"
