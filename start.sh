#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Błąd: nie znaleziono Docker CLI." >&2
  echo "Zainstaluj Docker Engine (Linux) albo Docker Desktop (macOS)." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Błąd: demon Docker nie jest uruchomiony lub użytkownik nie ma do niego dostępu." >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  docker compose config --quiet
  echo "OK: Docker i konfiguracja Compose są gotowe."
  exit 0
fi

docker compose up -d --build

PUBLISHED_ADDRESS="$(docker compose port frontend 8080 | head -n 1)"
APP_PORT="${PUBLISHED_ADDRESS##*:}"
if [[ -z "$APP_PORT" || "$APP_PORT" == "$PUBLISHED_ADDRESS" ]]; then
  APP_PORT="${MOSAIC_PORT:-8090}"
fi
APP_URL="http://localhost:$APP_PORT"
echo "Mozaika TV działa pod adresem: $APP_URL"

if [[ "${NO_BROWSER:-0}" != "1" ]]; then
  case "$(uname -s)" in
    Darwin)
      open "$APP_URL" >/dev/null 2>&1 || true
      ;;
    Linux)
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$APP_URL" >/dev/null 2>&1 || true
      fi
      ;;
  esac
fi
