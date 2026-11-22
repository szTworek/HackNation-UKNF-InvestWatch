# API (express + socket.io): bundel esbuild -> czysty node. Typy kontraktu współdzielone z frontend/src.
# Build z katalogu głównego repo:  docker build -f api/Dockerfile -t investwatch-api .
ARG NODE_IMAGE=node:24-alpine
FROM ${NODE_IMAGE} AS deps
WORKDIR /app/api
COPY api/package.json api/package-lock.json api/.npmrc ./
RUN npm ci --ignore-scripts --no-audit

# compose.dev.yaml: kod montowany z hosta, tsx watch
FROM deps AS dev
EXPOSE 4000
CMD ["npx", "tsx", "watch", "server.ts"]

FROM deps AS build
COPY frontend/src/api/types.ts /app/frontend/src/api/types.ts
COPY frontend/src/api/entityTypes.ts /app/frontend/src/api/entityTypes.ts
COPY frontend/src/lib/labels.ts /app/frontend/src/lib/labels.ts
COPY api ./
RUN npm run build

FROM ${NODE_IMAGE}
WORKDIR /app
ENV NODE_ENV=production API_PORT=4000
COPY --from=build /app/api/dist/server.cjs ./server.cjs
COPY eval_decisions.json ./eval_decisions.json
# Poprawki Alpine; npm i corepack są zbędne dla bundla i przynoszą własne podatne zależności (undici, brace-expansion).
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
       /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack
USER node
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:4000/api/health || exit 1
CMD ["node", "server.cjs"]
