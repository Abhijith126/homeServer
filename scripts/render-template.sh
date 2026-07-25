#!/usr/bin/env bash
#
# Render the stack template into a destination directory with substitutions.
# Internal helper used by new-app.sh and validate.sh.
# Usage: render-template.sh <dest-dir> <app> <node> <category>
#
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${1:?dest dir required}"
app="${2:?app name required}"
node="${3:?node required}"
category="${4:?category required}"

# Uppercased, underscore-safe form for env var names (pihole-unbound -> PIHOLE_UNBOUND).
app_upper="$(printf '%s' "$app" | tr '[:lower:]' '[:upper:]' | tr '-' '_')"

mkdir -p "$dest"
cp -R "${repo_root}/stacks/_template/." "$dest/"

for f in compose.yaml .env.example README.md backup.sh restore.sh; do
    [[ -f "${dest}/${f}" ]] || continue
    sed -i.bak \
        -e "s/<APP>/${app_upper}/g" \
        -e "s/<app>/${app}/g" \
        -e "s/<node>/${node}/g" \
        -e "s/<category>/${category}/g" \
        "${dest}/${f}"
    rm -f "${dest}/${f}.bak"
done

chmod +x "${dest}/backup.sh" "${dest}/restore.sh"
