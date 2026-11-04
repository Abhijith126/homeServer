# Caddy built with the Cloudflare DNS plugin (for DNS-01 ACME challenges).
# Pin CADDY_VERSION to match the version you'd otherwise pull.
ARG CADDY_VERSION=2.11.7

FROM caddy:${CADDY_VERSION}-builder AS builder
ARG CADDY_VERSION
# renovate: datasource=github-tags depName=caddy-dns/cloudflare
ARG CLOUDFLARE_VERSION=v0.2.4
RUN xcaddy build v${CADDY_VERSION} --with github.com/caddy-dns/cloudflare@${CLOUDFLARE_VERSION}

FROM caddy:${CADDY_VERSION}-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
