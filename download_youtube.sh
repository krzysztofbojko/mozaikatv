#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR/tools"
LOCAL_YT_DLP="$TOOLS_DIR/yt-dlp"

usage() {
  cat <<'EOF'
Użycie:
  ./download_youtube.sh URL [KATALOG_DOCELOWY]
  ./download_youtube.sh --self-test

Pobiera pojedynczy film z YouTube w jakości do 1080p i zapisuje wynik jako MP4.
Domyślny katalog docelowy: ./filmy
EOF
}

detect_release_asset() {
  case "$(uname -s)" in
    Darwin)
      printf '%s\n' "yt-dlp_macos"
      ;;
    Linux)
      case "$(uname -m)" in
        x86_64|amd64)
          printf '%s\n' "yt-dlp_linux"
          ;;
        arm64|aarch64)
          printf '%s\n' "yt-dlp_linux_aarch64"
          ;;
        *)
          echo "Błąd: nieobsługiwana architektura Linux: $(uname -m)" >&2
          return 1
          ;;
      esac
      ;;
    *)
      echo "Błąd: obsługiwane są wyłącznie Linux i macOS." >&2
      return 1
      ;;
  esac
}

require_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    return 0
  fi

  echo "Błąd: wymagane są ffmpeg i ffprobe." >&2
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "Instalacja na macOS: brew install ffmpeg" >&2
  else
    echo "Instalacja na Debian/Ubuntu: sudo apt install ffmpeg" >&2
  fi
  return 1
}

resolve_yt_dlp() {
  if command -v yt-dlp >/dev/null 2>&1; then
    command -v yt-dlp
    return 0
  fi

  if [[ -x "$LOCAL_YT_DLP" ]]; then
    printf '%s\n' "$LOCAL_YT_DLP"
    return 0
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "Błąd: wymagany jest curl do pobrania yt-dlp." >&2
    return 1
  fi

  local asset
  local temporary
  asset="$(detect_release_asset)"
  temporary="$LOCAL_YT_DLP.download"
  mkdir -p "$TOOLS_DIR"

  echo "Pobieranie oficjalnego yt-dlp dla $(uname -s)/$(uname -m)..." >&2
  curl --fail --location --progress-bar \
    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$asset" \
    --output "$temporary"
  chmod 0755 "$temporary"
  mv "$temporary" "$LOCAL_YT_DLP"
  printf '%s\n' "$LOCAL_YT_DLP"
}

self_test() {
  local asset
  asset="$(detect_release_asset)"
  command -v curl >/dev/null 2>&1 || {
    echo "Błąd: brak curl." >&2
    return 1
  }
  require_ffmpeg
  echo "OK: system=$(uname -s), arch=$(uname -m), asset=$asset"
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  --self-test)
    self_test
    exit 0
    ;;
  "")
    usage >&2
    exit 2
    ;;
esac

URL="$1"
OUTPUT_DIR="${2:-$SCRIPT_DIR/filmy}"

if [[ "$URL" != http://* && "$URL" != https://* ]]; then
  echo "Błąd: podaj pełny adres http:// lub https://." >&2
  exit 2
fi

require_ffmpeg
YT_DLP="$(resolve_yt_dlp)"
mkdir -p "$OUTPUT_DIR"

"$YT_DLP" \
  --no-playlist \
  --newline \
  --format "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b[height<=1080]" \
  --merge-output-format mp4 \
  --output "$OUTPUT_DIR/%(title)s [%(id)s].%(ext)s" \
  -- "$URL"

echo "Gotowe. Plik zapisano w: $OUTPUT_DIR"
