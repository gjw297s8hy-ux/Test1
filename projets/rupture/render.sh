#!/usr/bin/env bash
# RUPTURE - rendu complet reproductible.
#   ./render.sh                 rendu final 1080x1920, 540 images, son, titres, MP4
#   SAMPLES=4 RES=270 ./render.sh   previsualisation rapide (meme film, basse resolution)
# Reprise possible : les images deja rendues sont conservees (supprimer renders/frames pour tout refaire).
set -euo pipefail
cd "$(dirname "$0")"
BLENDER="${BLENDER:-blender}"
RES="${RES:-1080}"
SAMPLES="${SAMPLES:-10}"
OUT="${OUT:-renders}"
mkdir -p "$OUT"

# 1. images 3D (Cycles, deterministes : chaque image ne depend que de son numero)
"$BLENDER" -b -P src/build.py -- --res "$RES" --samples "$SAMPLES" --frames 0-539 --out "$OUT/frames" --noblur

# 2. son (synthese originale)
python3 src/audio.py "$OUT/rupture_audio.wav"

# 3. titres en calques (titres.json) + vignettage
python3 src/titles.py composite "$OUT/frames" "$OUT/final"
python3 src/titles.py calques "$OUT/calques"

# 4. encodage : H.264, yuv420p, 30 i/s constantes, 540 images = 18,000 s
ffmpeg -y -framerate 30 -start_number 0 -i "$OUT/final/f%04d.png" -i "$OUT/rupture_audio.wav" \
  -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p -profile:v high -r 30 -fps_mode cfr \
  -c:a aac -b:a 256k -ar 48000 -frames:v 540 -t 18 -movflags +faststart "$OUT/RUPTURE_18s.mp4"

# 5. verification
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_frames,duration \
  -show_entries format=duration -of compact "$OUT/RUPTURE_18s.mp4"
