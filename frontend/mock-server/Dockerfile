# Mock API: bundel esbuild (express + socket.io w jednym pliku) -> czysty node.
# Build z katalogu frontend/:  docker build -f mock-server/Dockerfile -t investwatch-mock .
ARG NODE_IMAGE=node:24-alpine
FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts --no-audit
COPY tsconfig.node.json ./
COPY src/api/types.ts src/api/types.ts
COPY src/api/entityTypes.ts src/api/entityTypes.ts
COPY src/lib/labels.ts src/lib/labels.ts
COPY mock-server mock-server
RUN npm run build:mock

FROM ${NODE_IMAGE}
WORKDIR /app
ENV NODE_ENV=production MOCK_PORT=4000
COPY --from=build /app/dist-mock/server.cjs ./server.cjs
COPY --from=build /app/mock-server/entities.snapshot.json ./mock-server/entities.snapshot.json
# Poprawki Alpine; npm i corepack są zbędne dla bundla i przynoszą własne podatne zależności (undici, brace-expansion).
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
       /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
    && mkdir -p /state && chown node:node /state
USER node
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:4000/api/health || exit 1
CMD ["node", "server.cjs"]
