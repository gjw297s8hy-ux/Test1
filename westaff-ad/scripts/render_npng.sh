#!/usr/bin/env bash
# Rendu du teaser NPNG : bash scripts/render_npng.sh [sortie.mp4]
set -euo pipefail; cd "$(dirname "$0")/.."
OUT=${1:-out/npng_teaser_1080x1920.mp4}; mkdir -p "$(dirname "$OUT")"
[ -f public/npng/soundtrack.wav ] || python3 scripts/make_npng_audio.py
if [ -z "${REMOTION_BROWSER:-}" ]; then for c in /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell; do [ -x "$c" ] && export REMOTION_BROWSER="$c"; done; fi
npx remotion render src/index.ts NPNG "$OUT" --codec=h264 --crf=16 --pixel-format=yuv420p --audio-codec=aac --audio-bitrate=256k --props='{"withAudio":true}'
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of compact "$OUT"
