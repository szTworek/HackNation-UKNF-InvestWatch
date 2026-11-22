#!/usr/bin/env bash
# Wdrożenie weryfikacyjne: buduje stack ze źródeł, stawia go z ustawieniami środowiska,
# sprawdza działanie i sprząta po sobie. Użycie: bash deploy/verify.sh <dev|prod>
set -euo pipefail

ENV_NAME="${1:?podaj środowisko: dev|prod}"
case "$ENV_NAME" in dev|prod) ;; *) echo "Nieznane środowisko: $ENV_NAME" >&2; exit 2 ;; esac

cd "$(dirname "$0")/.."
ENV_FILE="deploy/$ENV_NAME.env"

value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n1 | tr -d '\r'; }
compose() { docker compose -p "investwatch-verify-$ENV_NAME" --env-file "$ENV_FILE" -f compose.yaml "$@"; }

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    compose ps >&2 || true
    compose logs --tail=50 >&2 || true
  fi
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

FRONTEND="http://127.0.0.1:$(value FRONTEND_PORT)"
AI="http://127.0.0.1:$(value AI_PORT)"

check() {
  curl -fsS --retry 5 --retry-delay 2 --retry-all-errors -o /dev/null "$2"
  echo "ok: $1"
}

compose up -d --build --wait --wait-timeout 900

for svc in postgres minio; do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$(compose ps -q "$svc")")" = healthy ]
  echo "ok: $svc healthy"
done
[ "$(docker inspect -f '{{.State.ExitCode}}' "$(compose ps -aq loader)")" = 0 ]
echo "ok: loader zakończony"

check "frontend" "$FRONTEND/"
check "nginx health" "$FRONTEND/healthz"
check "API przez nginx" "$FRONTEND/api/health"
check "lista wyników" "$FRONTEND/api/findings?pageSize=1"
curl -fsS "$FRONTEND/api/health" | grep -Eq '"findings":[1-9][0-9]*,"dataMode":"real"'
echo "ok: rekordy z Postgresa"
curl -fsS "$FRONTEND/api/entities/xtb" | grep -q '"hasData":true'
echo "ok: podmiot z Postgresa"
MEDIA_KEY="$(curl -fsS "$FRONTEND/api/entities/xtb/items?limit=200" | grep -o '"key":"[^"]*\.webp"' | head -n1 | cut -d'"' -f4)"
[ -n "$MEDIA_KEY" ]
check "grafika z MinIO" "$FRONTEND/api/media/$MEDIA_KEY"
check "socket.io przez nginx" "$FRONTEND/socket.io/?EIO=4&transport=polling"
check "ai-service" "$AI/health"

curl -fsS -X POST "$AI/analyze" -H 'content-type: application/json' \
  -d '{"items":[{"id":"verify-1","text":"Gwarantowany zysk 300% w tydzien, wplac 250 USD"}]}' \
  | grep -q '"itemId":"verify-1"'
echo "ok: analiza AI"

echo "Wdrożenie $ENV_NAME zweryfikowane"
