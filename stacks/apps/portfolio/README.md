# Portfolio

Runs on apps at the portfolio subdomain or port 3000. The Dockerfile pins the
GitHub release and Node image; Renovate tracks both. Downloads, checksum checking
and extraction happen at build time. The runtime starts as the non-root node user
and needs no GitHub/Alpine downloads on restart. App integrations may still need
external access.

## Deploy

Run make config, then from this stack run docker compose build --pull followed by
docker compose up -d --wait. The normal updater already performs those steps.
Failed downloads/builds prevent replacement of the existing container. CI builds
the same Dockerfile and tests HTTP startup without external networking.

## Migration and release selection

The release is now committed as PORTFOLIO_RELEASE in Dockerfile. Remove old
PORTFOLIO_RELEASE overrides from root/per-stack .env files: they are no longer
used. The initial pin is build-3-04ada73651fe, verified from upstream metadata when
this change was prepared. Check the running version before rollout if you used
another release deliberately. Change the Dockerfile pin to select another release;
Renovate tracks the build counter and requires review.

PORTFOLIO_REPOSITORY remains a build-time override; its release tag must match the
pin. The default Renovate rule tracks Abhijith126/portfolio only. This repo builds
locally: it does not publish images or modify the portfolio repo. Reverting a pin
and rebuilding supports stateless rollback; verify external data/API compatibility
separately.
