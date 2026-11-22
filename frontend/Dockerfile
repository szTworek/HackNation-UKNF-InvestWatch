# Frontend: build (Vite) -> nginx (nieuprzywilejowany, port 8080)
#
# Targety:
#   dev   – node + zależności, pod `vite --host` / `tsx watch` z kodem montowanym z hosta (compose.dev.yaml)
#   (domyślny) – statyczny build serwowany przez nginx; /api i /socket.io są proxowane do API_UPSTREAM
ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.29-alpine

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts --no-audit

FROM deps AS dev
ENV CHOKIDAR_USEPOLLING=true VITE_USE_POLLING=1
EXPOSE 5173 4000
CMD ["npx", "vite", "--host", "0.0.0.0"]

FROM deps AS build
COPY . .
# Domyślnie same-origin: przeglądarka woła /api i /socket.io na tym samym hoście, nginx proxuje do API.
# Nadal można wkompilować absolutne adresy: --build-arg VITE_API_URL=https://api.example/api
ARG VITE_API_URL=/api
ARG VITE_WS_URL=/
ENV VITE_API_URL=$VITE_API_URL VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
# Poprawki bezpieczeństwa Alpine, których obraz bazowy jeszcze nie ma (skan Grype w CD blokuje high z poprawką).
USER root
RUN apk upgrade --no-cache
USER 101
# Szablon przetwarzany przez envsubst przy starcie kontenera (obraz nginx -> /etc/nginx/conf.d/default.conf)
ENV API_UPSTREAM=http://api:4000 NGINX_RESOLVER=127.0.0.11
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
