#!/usr/bin/env bash
# Użycie (na serwerze, w katalogu z compose.yaml i <env>.env):
#   bash deploy.sh <dev|prod> <image-tag> [--with-app]
# Zawsze pobiera obraz kolektora. --with-app uruchamia też frontend, API i ai-service.
# Po nieudanym wdrożeniu wraca do ostatniego działającego tagu.
set -euo pipefail

ENV_NAME="${1:?podaj środowisko: dev|prod}"
TAG="${2:?podaj tag obrazu}"
WITH_APP="${3:-}"
case "$ENV_NAME" in dev|prod) ;; *) echo "Nieznane środowisko: $ENV_NAME" >&2; exit 2 ;; esac
case "$WITH_APP" in ""|--with-app) ;; *) echo "Nieznana opcja: $WITH_APP" >&2; exit 2 ;; esac

cd "$(dirname "$0")"
ENV_FILE="$ENV_NAME.env"
LAST_GOOD=".last-good-tag"

USE_GPU="$(sed -n 's/^USE_GPU=//p' "$ENV_FILE" | tail -n1)"
FILES=(-f compose.yaml)
if [ "$USE_GPU" = "1" ]; then FILES+=(-f compose.gpu.yaml); fi
compose() { docker compose -p "investwatch-$ENV_NAME" --env-file "$ENV_FILE" "${FILES[@]}" "$@"; }

release() {
  export IMAGE_TAG="$1"
  # Jawne &&: wewnątrz `if release ...` bash wyłącza set -e
  compose --profile jobs pull collector || return 1
  if [ -n "$WITH_APP" ]; then
    compose pull \
      && compose up -d --no-build --remove-orphans --wait --wait-timeout 600
  fi
}

mkdir -p models .secrets
chmod 700 .secrets

if release "$TAG"; then
  echo "$TAG" > "$LAST_GOOD"
  docker image prune -f >/dev/null
  echo "Wdrożono $ENV_NAME: $TAG"
  exit 0
fi

echo "Wdrożenie $TAG nieudane" >&2
if [ -n "$WITH_APP" ]; then
  compose ps >&2 || true
  compose logs --tail=50 >&2 || true
fi
if [ -s "$LAST_GOOD" ]; then
  PREVIOUS="$(cat "$LAST_GOOD")"
  echo "Rollback do $PREVIOUS" >&2
  release "$PREVIOUS" || echo "Rollback nieudany" >&2
fi
exit 1
