# Downloads happen at build time, never when the container restarts.
FROM node:26-alpine@sha256:8996bb5821d62a8fd9bb27c1cb07462f3fdce6e47d640c6a881ead0b064ce216 AS release
ARG PORTFOLIO_REPOSITORY=Abhijith126/portfolio
# renovate: datasource=github-tags depName=Abhijith126/portfolio
ARG PORTFOLIO_RELEASE=build-3-04ada73651fe
RUN apk add --no-cache curl unzip \
    && test "$PORTFOLIO_RELEASE" != latest \
    && mkdir /download /app \
    && cd /download \
    && curl -fL --retry 3 -o portfolio-build.zip "https://github.com/${PORTFOLIO_REPOSITORY}/releases/download/${PORTFOLIO_RELEASE}/portfolio-build.zip" \
    && curl -fL --retry 3 -o portfolio-build.zip.sha256 "https://github.com/${PORTFOLIO_REPOSITORY}/releases/download/${PORTFOLIO_RELEASE}/portfolio-build.zip.sha256" \
    && sha256sum -c portfolio-build.zip.sha256 \
    && unzip -q portfolio-build.zip -d /app

FROM node:26-alpine@sha256:8996bb5821d62a8fd9bb27c1cb07462f3fdce6e47d640c6a881ead0b064ce216
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=release --chown=node:node /app/ ./
USER node
EXPOSE 3000
CMD ["node", "server.js"]
