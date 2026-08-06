ARG NODE_IMAGE=node:22-bookworm-slim
FROM ${NODE_IMAGE}

ARG APT_MIRROR=
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG NODE_DIST_MIRROR=https://nodejs.org/download/release
ARG NODE_PRE_GYP_GITHUB_MIRROR=
ARG PREBUILD_INSTALL_BINARY_MIRROR=
ARG CANVAS_BINARY_HOST_MIRROR=

ENV npm_config_disturl=${NODE_DIST_MIRROR}
ENV NODE_PRE_GYP_GITHUB_MIRROR=${NODE_PRE_GYP_GITHUB_MIRROR}
ENV PREBUILD_INSTALL_BINARY_MIRROR=${PREBUILD_INSTALL_BINARY_MIRROR}
ENV npm_config_canvas_binary_host_mirror=${CANVAS_BINARY_HOST_MIRROR}

RUN if [ -n "${APT_MIRROR}" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY echarts-mcp/package.json echarts-mcp/package-lock.json ./
RUN npm config set registry "${NPM_REGISTRY}" \
  && npm config set fetch-retries 5 \
  && npm config set fetch-retry-mintimeout 20000 \
  && npm config set fetch-retry-maxtimeout 120000 \
  && npm ci --omit=dev
COPY echarts-mcp/src ./src

CMD ["npm", "start"]
