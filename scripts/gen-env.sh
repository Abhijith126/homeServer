#!/usr/bin/env bash
#
# Generate every stack's .env from the single root .env.
#
# For each stack, values default from its committed .env.example; any key that
# is ALSO set in the root .env overrides it. Then verify no CHANGEME
# placeholders remain, so you configure secrets in ONE place.
#
# Usage:
#   ./scripts/gen-env.sh           generate all stack .env files, then verify
#   ./scripts/gen-env.sh --check   verify only (no writes)
#   ./scripts/gen-env.sh --node apps   generate/verify only one node
#
set -euo pipefail
umask 077

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

check_only=false
node_root=stacks
while [[ $# -gt 0 ]]; do
    case "$1" in
    --check)
        check_only=true
        shift
        ;;
    --node)
        case "${2:-}" in apps | storage | infra) node_root="stacks/$2" ;; *)
            echo "--node requires apps, storage, or infra" >&2
            exit 1
            ;;
        esac
        shift 2
        ;;
    *)
        echo "usage: $0 [--check] [--node apps|storage|infra]" >&2
        exit 1
        ;;
    esac
done

root_env="${repo_root}/.env"
if [[ ! -f "$root_env" ]]; then
    echo "No root .env found. Run:  cp .env.example .env && \$EDITOR .env" >&2
    exit 1
fi

# Load the root .env into an associative array (first '=' splits key/value).
declare -A root_vars
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    key="${key// /}"
    root_vars["$key"]="${line#*=}"
done <"$root_env"

# Render one stack: copy its .env.example, overriding any root-defined key.
render_stack() {
    local example="$1" out="$2" line key
    : >"${out}.tmp"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            if [[ -n "${root_vars[$key]+x}" ]]; then
                printf '%s=%s\n' "$key" "${root_vars[$key]}" >>"${out}.tmp"
                continue
            fi
        fi
        printf '%s\n' "$line" >>"${out}.tmp"
    done <"$example"
    mv "${out}.tmp" "$out"
}

generated=0
if [[ "$check_only" == false ]]; then
    while IFS= read -r example; do
        out="$(dirname "$example")/.env"
        render_stack "$example" "$out"
        generated=$((generated + 1))
        echo "  wrote ${out#./}"
    done < <(find "$node_root" -name '.env.example' -not -path '*/_template/*' | sort)
    echo ""
fi

# Verify: every stack has a .env with no unset (CHANGEME) values.
missing=0
while IFS= read -r example; do
    envf="$(dirname "$example")/.env"
    if [[ ! -f "$envf" ]]; then
        echo "  MISSING  ${envf#./}  (run 'make config' to generate)"
        missing=$((missing + 1))
        continue
    fi
    while IFS= read -r hit; do
        echo "  UNSET    ${envf#./}: ${hit}"
        missing=$((missing + 1))
    done < <(grep -nE '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGEME' "$envf" || true)
done < <(find "$node_root" -name '.env.example' -not -path '*/_template/*' | sort)

if [[ "$missing" -gt 0 ]]; then
    echo ""
    echo "✗ ${missing} value(s) still need configuring — set them in ./.env and re-run 'make config'."
    exit 1
fi

if [[ "$check_only" == true ]]; then
    echo "✓ all stack .env files present and fully configured"
else
    echo "✓ generated ${generated} stack .env files — all secrets configured"
fi
