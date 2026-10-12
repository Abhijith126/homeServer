#!/usr/bin/env bash
# Check both authenticated recursion and Pi-hole forwarding, not only pi.hole.
set -euo pipefail
root_answer="$(dig @127.0.0.1 -p 5335 . DNSKEY +dnssec +time=3 +tries=1)"
[[ "$root_answer" == *"status: NOERROR"* ]] || exit 1
printf '%s\n' "$root_answer" | grep -Eq '^;; flags:.*[[:space:]]ad([[:space:];])' || exit 1
pihole_answer="$(dig @127.0.0.1 . NS +time=3 +tries=1)"
[[ "$pihole_answer" == *"status: NOERROR"* ]] || exit 1
