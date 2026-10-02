#!/usr/bin/env bash
# Database only; photo files require a separate backup. Keep seven successful dumps.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/../../../scripts/immich-backup.py" "$script_dir"
