#!/command/with-contenv bash
# shellcheck shell=bash
# Run under the combined image's s6 supervisor, before Unbound starts.
set -uo pipefail

/usr/lib/unbound/package-helper chroot_setup || exit 1
anchor=/var/lib/unbound/root.key
install -d -o unbound -g unbound /var/lib/unbound

# Force IANA's signature-verified recovery path. This handles a fresh volume
# introduced after a rollover, without waiting 30 days for an ADDPEND key.
# The tool returns 1 for an authenticated update and 0 for no update OR error;
# neither status alone proves DNS works. The healthcheck verifies validation.
anchor_status=0
unbound-anchor -a "$anchor" -F -4 -v || anchor_status=$?
if [[ "$anchor_status" -gt 1 ]]; then
    echo "Trust-anchor refresh returned $anchor_status; retaining existing anchors." >&2
fi
if [[ ! -s "$anchor" ]]; then
    echo "No root trust anchor available; refusing to start Unbound." >&2
    exit 1
fi
chown unbound:unbound "$anchor" || exit 1
exec /usr/sbin/unbound -d
