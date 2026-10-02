#!/usr/bin/env bash
# Clone once, then run this on each Debian/Ubuntu node.
# Usage: ./scripts/bootstrap-node.sh [storage|apps|infra]
set -euo pipefail
umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $EUID -eq 0 ]]; then
    if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
        exec sudo -u "$SUDO_USER" -- "$repo_root/scripts/bootstrap-node.sh" "$@"
    fi
    echo "Run as the user who owns the checkout; the script uses sudo when needed." >&2
    exit 1
fi
[[ -t 0 ]] || {
    echo "Run in an interactive terminal." >&2
    exit 1
}
[[ "$repo_root" =~ ^/[a-zA-Z0-9_./-]+$ ]] || {
    echo "Use a checkout path with letters, numbers, /, _, . and - only." >&2
    exit 1
}
cd "$repo_root"
[[ "$(stat -c %U .)" == "$(id -un)" ]] || {
    echo "The checkout must belong to your user." >&2
    exit 1
}
[[ "$(git branch --show-current)" == main ]] || {
    echo "Switch the checkout to main first." >&2
    exit 1
}
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Commit or stash tracked changes before bootstrap." >&2
    exit 1
fi
# shellcheck source=/dev/null
source /etc/os-release
case "$ID" in debian | ubuntu) ;; *)
    echo "This bootstrap supports Debian and Ubuntu." >&2
    exit 1
    ;;
esac
command -v systemctl >/dev/null || {
    echo "A systemd host is required." >&2
    exit 1
}
if command -v snap >/dev/null && snap list docker >/dev/null 2>&1; then
    echo "Snap Docker detected. Migrate its data to standard Docker before bootstrap; it will not be replaced automatically." >&2
    exit 1
fi

sudo -v
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-apt python3-requests git make curl ca-certificates util-linux
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Use Debian 12+ or Ubuntu 24.04+ (Python 3.11+)."'
if sudo systemctl cat homelab-deploy.timer >/dev/null 2>&1; then
    sudo systemctl stop homelab-deploy.timer
    echo "Waiting for any current deployment to finish..."
    while [[ "$(systemctl show homelab-deploy.service -p ActiveState --value)" =~ ^(active|activating|deactivating|reloading)$ ]]; do
        sleep 2
    done
fi
mkdir -p .bootstrap
trap 'rm -f "$repo_root/.bootstrap/auth.json"' EXIT
python3 scripts/bootstrap-config.py "$@"
python3 -m venv .bootstrap/venv
.bootstrap/venv/bin/python -m pip install --quiet 'ansible>=11,<15'

sudo env ANSIBLE_CONFIG="$repo_root/ansible/ansible.cfg" \
    "$repo_root/.bootstrap/venv/bin/ansible-playbook" \
    -i "$repo_root/.bootstrap/inventory.json" ansible/bootstrap.yml \
    -e "@$repo_root/.bootstrap/vars.json" -e "@$repo_root/.bootstrap/auth.json"

mapfile -t settings < <(python3 scripts/bootstrap-config.py --settings)
node="${settings[0]}"
mounts="${settings[1]}"
skip="${settings[2]}"
sudo ./scripts/install-auto-deploy.sh "$node" --mounts "$mounts" --skip "$skip" \
    --schedule "${settings[3]}" --time "${settings[4]}" --timezone "${settings[5]}"
if ! sudo systemctl start homelab-deploy.service; then
    sudo journalctl -u homelab-deploy.service --no-pager -n 60
    echo "Deployment failed. Fix the reported issue and rerun bootstrap." >&2
    exit 1
fi
echo "Setup complete. Merged main changes deploy on your ${settings[3]} schedule."
echo "Logs: journalctl -u homelab-deploy.service -f"
