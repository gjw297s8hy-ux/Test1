#!/usr/bin/env bash
# Rend des images-clés pour vérification : bash scripts/stills.sh 1.0 3.2 ...  (secondes)
set -e
cd "$(dirname "$0")/.."
OUT=${OUT:-out/stills}; mkdir -p "$OUT"
FPS=60
for s in "$@"; do
  f=$(python3 -c "print(int(round($s*$FPS)))")
  npx remotion still src/index.ts Ad "$OUT/t_${s}.jpg" --frame=$f --image-format=jpeg --props='{"showSafeZones":false,"forceFallback":false,"withAudio":false}' --log=error
done
