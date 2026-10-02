#!/usr/bin/env bash
# Run from a checkout, or: bash <(curl -fsSL <repo>/main/scripts/setup.sh)
set -euo pipefail

main() {
    [[ $EUID -ne 0 ]] || { echo "Run as your normal sudo user, without sudo." >&2; return 1; }
    local checkout="${HOMELAB_DIRECTORY:-$HOME/homeServer}"
    local repository="${HOMELAB_REPOSITORY:-https://github.com/Abhijith126/homeServer.git}"
    local source_dir reconfigure=false
    source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    if [[ -d "$source_dir/.git" && -f "$source_dir/scripts/bootstrap-node.sh" ]]; then
        checkout="$source_dir"
    fi
    local args=()
    for argument in "$@"; do
        if [[ "$argument" == --reconfigure ]]; then reconfigure=true; else args+=("$argument"); fi
    done
    if ! command -v git >/dev/null; then
        sudo apt-get update
        sudo apt-get install -y git ca-certificates
    fi
    if [[ ! -d "$checkout/.git" ]]; then
        [[ ! -e "$checkout" ]] || { echo "$checkout exists but is not a Git checkout." >&2; return 1; }
        git clone --branch main --single-branch "$repository" "$checkout"
    fi
    cd "$checkout"
    [[ "$(git branch --show-current)" == main ]] || { echo "Checkout must be on main." >&2; return 1; }
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Tracked local edits found; commit or stash them before setup." >&2
        return 1
    fi
    if sudo systemctl cat homelab-deploy.timer >/dev/null 2>&1; then
        sudo systemctl stop homelab-deploy.timer
        while [[ "$(systemctl show homelab-deploy.service -p ActiveState --value)" =~ ^(active|activating|deactivating|reloading)$ ]]; do
            sleep 2
        done
    fi
    git fetch origin main
    git merge --ff-only origin/main
    if [[ -f .bootstrap/vars.json && "$reconfigure" == false ]]; then
        python3 scripts/bootstrap-config.py --updates-only "${args[@]}"
        local settings_text
        settings_text="$(python3 scripts/bootstrap-config.py --settings)"
        local settings=()
        mapfile -t settings <<<"$settings_text"
        sudo ./scripts/install-auto-deploy.sh "${settings[0]}" \
            --mounts "${settings[1]}" --skip "${settings[2]}" \
            --schedule "${settings[3]}" --time "${settings[4]}" --timezone "${settings[5]}"
        echo "Update schedule saved. Use --reconfigure to repeat host provisioning."
    else
        exec ./scripts/bootstrap-node.sh "${args[@]}"
    fi
}
main "$@"
