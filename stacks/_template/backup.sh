#!/usr/bin/env bash
# Shared failure-safe backup implementation; use --stop for a consistent archive.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/../../scripts/stack-backup.py" "$script_dir" "$@"
