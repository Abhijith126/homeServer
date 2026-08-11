# Caddy built with the Cloudflare DNS plugin (for DNS-01 ACME challenges).
# Pin CADDY_VERSION to match the version you'd otherwise pull.
ARG CADDY_VERSION=2.11.4

FROM caddy:${CADDY_VERSION}-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION}-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
