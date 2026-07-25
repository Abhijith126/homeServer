#!/usr/bin/env bash
#
# Validate the platform: compose config, template smoke test, custom lint,
# and (when installed) yamllint, shellcheck, shfmt, gitleaks.
# Mirrors .github/workflows/ci.yml so CI can be run locally.
#
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1

fail=0
note() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# ── 1. Validate every real stack ──
note "docker compose config (stacks)"
found=0
while IFS= read -r compose; do
    found=1
    dir="$(dirname "$compose")"
    if (cd "$dir" && docker compose --env-file .env.example config -q) 2>/tmp/cc.err; then
        echo "  ok   ${compose#./}"
    else
        echo "  FAIL ${compose#./}"
        sed 's/^/       /' /tmp/cc.err
        fail=1
    fi
done < <(find stacks -mindepth 3 -name compose.yaml -not -path '*/_template/*' | sort)
[[ "$found" -eq 0 ]] && echo "  (no stacks yet)"

# ── 2. Template smoke test ──
note "template smoke test (render + config)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
if ./scripts/render-template.sh "$tmp" smoketest apps tools >/dev/null 2>&1; then
    sed -i.bak 's#<image>:<tag>#traefik/whoami:v1.10.0#' "$tmp/compose.yaml"
    rm -f "$tmp/compose.yaml.bak"
    if (cd "$tmp" && docker compose --env-file .env.example config -q) 2>/tmp/cc.err; then
        echo "  ok   template renders and validates"
    else
        echo "  FAIL template"
        sed 's/^/       /' /tmp/cc.err
        fail=1
    fi
else
    echo "  FAIL render-template.sh"
    fail=1
fi

# ── 3. Custom lint ──
note "custom lint"
if grep -rnE '^[[:space:]]*version:[[:space:]]' stacks --include=compose.yaml >/dev/null 2>&1; then
    echo "  FAIL remove obsolete 'version:' key:"
    grep -rnE '^[[:space:]]*version:[[:space:]]' stacks --include=compose.yaml | sed 's/^/       /'
    fail=1
else
    echo "  ok   no obsolete 'version:' keys"
fi
if grep -rnE 'image:[[:space:]]*[^[:space:]]+:latest' stacks --include=compose.yaml >/dev/null 2>&1; then
    echo "  FAIL pin image tags (no :latest):"
    grep -rnE 'image:[[:space:]]*[^[:space:]]+:latest' stacks --include=compose.yaml | sed 's/^/       /'
    fail=1
else
    echo "  ok   no ':latest' tags"
fi
if grep -rn 'restart: always' stacks --include=compose.yaml >/dev/null 2>&1; then
    echo "  FAIL use 'unless-stopped' not 'always':"
    grep -rn 'restart: always' stacks --include=compose.yaml | sed 's/^/       /'
    fail=1
else
    echo "  ok   restart policy"
fi

# ── 4. Optional external linters ──
if have yamllint; then
    note "yamllint"
    if yamllint -c .yamllint.yaml .; then echo "  ok"; else fail=1; fi
else
    printf '\n  (yamllint not installed — skipped)\n'
fi

if have shellcheck; then
    note "shellcheck"
    # shellcheck disable=SC2046
    if shellcheck $(find scripts stacks -name '*.sh'); then echo "  ok"; else fail=1; fi
else
    printf '  (shellcheck not installed — skipped)\n'
fi

if have shfmt; then
    note "shfmt (diff check, -i 4)"
    # shellcheck disable=SC2046
    if shfmt -i 4 -d $(find scripts stacks -name '*.sh'); then echo "  ok"; else fail=1; fi
fi

if have gitleaks; then
    note "gitleaks"
    if gitleaks detect --no-git --config .gitleaks.toml --redact; then echo "  ok"; else fail=1; fi
else
    printf '  (gitleaks not installed — skipped)\n'
fi

note "result"
if [[ "$fail" -eq 0 ]]; then
    echo "  ALL CHECKS PASSED"
else
    echo "  FAILURES ABOVE"
fi
exit "$fail"
