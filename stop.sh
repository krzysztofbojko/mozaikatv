#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Błąd: nie znaleziono Docker CLI." >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  docker compose config --quiet
  echo "OK: konfiguracja Compose jest poprawna."
  exit 0
fi

docker compose down
echo "Mozaika TV została zatrzymana."
