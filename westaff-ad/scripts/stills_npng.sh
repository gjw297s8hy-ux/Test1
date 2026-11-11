#!/usr/bin/env bash
# Images-clés du teaser NPNG : bash scripts/stills_npng.sh 1.0 3.2 ...
set -e; cd "$(dirname "$0")/.."; OUT=${OUT:-out/npng_stills}; mkdir -p "$OUT"
for s in "$@"; do f=$(python3 -c "print(int(round($s*30)))"); npx remotion still src/index.ts NPNG "$OUT/t_${s}.jpg" --frame=$f --image-format=jpeg --props='{"withAudio":false}' --log=error; done
