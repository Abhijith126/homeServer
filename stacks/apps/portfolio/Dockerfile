# Downloads happen at build time, never when the container restarts.
FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS release
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

FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=release --chown=node:node /app/ ./
USER node
EXPOSE 3000
CMD ["node", "server.js"]
