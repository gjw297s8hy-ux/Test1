#!/usr/bin/env bash
# Rendu final : bash scripts/render.sh [sortie.mp4]
# Variables utiles :
#   REMOTION_GL=angle|egl|swangle   (swangle = rendu CPU, par défaut ; angle/egl si GPU disponible)
#   REMOTION_CONCURRENCY=3          (onglets de rendu en parallèle)
#   REMOTION_BROWSER=/chemin/chrome-headless-shell (optionnel)
#   FALLBACK=1                      (force la version 2D sans WebGL)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-out/westaff_ad_1080x1920_60fps.mp4}
mkdir -p "$(dirname "$OUT")"
[ -f public/audio/soundtrack.wav ] || python3 scripts/make_audio.py
if [ -z "${REMOTION_BROWSER:-}" ]; then
  for c in /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell; do [ -x "$c" ] && export REMOTION_BROWSER="$c"; done
fi
FB=$([ "${FALLBACK:-0}" = "1" ] && echo true || echo false)
npx remotion render src/index.ts Ad "$OUT" \
  --codec=h264 --crf=16 --pixel-format=yuv420p --audio-codec=aac --audio-bitrate=256k \
  --props="{\"showSafeZones\":false,\"forceFallback\":$FB,\"withAudio\":true}"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of compact "$OUT"
