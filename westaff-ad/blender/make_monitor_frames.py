"""Écran de l'ordinateur (portrait 9:16) : lecteur « now playing » animé — rose en vidéo au début, pochette à la fin."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, math
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'out/npng_seq/monitor'); os.makedirs(OUT, exist_ok=True)
F = lambda s, w='InterDisplay-Black': ImageFont.truetype(os.path.join(ROOT, 'public/fonts', f'{w}.otf'), s)
W, H, FPS, N = 720, 1280, 30, 450
BEAT, B0 = 0.508, 0.396; E0 = B0 + BEAT * 22
cover = Image.open(os.path.join(ROOT, 'public/npng/cover.jpg')).convert('RGB')
def rose(t):
    n = 33; k = int(t * 15) % (2 * n); k = k if k < n else 2 * n - k
    im = Image.open(os.path.join(ROOT, f'public/npng/rose/f{k + 1:03d}.jpg')).convert('RGB')
    w, h = im.size; s = 560 / min(w, h); im = im.resize((int(w * s), int(h * s)))
    x = (im.width - 560) // 2; return im.crop((x, 0, x + 560, 560))
bg_base = cover.resize((W, W)).filter(ImageFilter.GaussianBlur(40))
for f in range(N):
    t = f / FPS
    im = Image.new('RGB', (W, H), (8, 6, 8))
    bg = bg_base.resize((H, H)).crop(((H - W) // 2, 0, (H - W) // 2 + W, H)).point(lambda v: int(v * 0.35))
    im.paste(bg, (0, 0)); d = ImageDraw.Draw(im)
    art = rose(t) if t < E0 - 0.6 else cover.resize((560, 560))
    im.paste(art, (80, 170)); d.rectangle([80, 170, 640, 730], outline=(255, 255, 255), width=2)
    d.text((80, 800), 'NPNG', font=F(96), fill=(255, 255, 255))
    d.text((80, 915), "O'NEAL", font=F(44, 'Inter-ExtraBold'), fill=(232, 40, 52))
    d.text((80, 980), 'NOUVEAU SON', font=F(26, 'Inter-SemiBold'), fill=(190, 190, 195))
    p = (t % 15) / 15  # barre de lecture
    d.rounded_rectangle([80, 1060, 640, 1068], 4, fill=(70, 70, 76)); d.rounded_rectangle([80, 1060, 80 + 560 * p, 1068], 4, fill=(232, 40, 52))
    d.ellipse([80 + 560 * p - 10, 1054, 80 + 560 * p + 10, 1074], fill=(255, 255, 255))
    for i in range(40):  # mini égaliseur
        a = 10 + 26 * abs(math.sin(t * 6 + i * 0.7)) * (0.6 + 0.4 * math.sin(i * 1.3 + t * 2))
        d.rectangle([80 + i * 14, 1150 - a, 88 + i * 14, 1150], fill=(232, 40, 52) if i % 3 else (255, 255, 255))
    cx = W // 2; d.ellipse([cx - 46, 1190 - 46, cx + 46, 1190 + 46], fill=(255, 255, 255)); d.polygon([(cx - 14, 1168), (cx - 14, 1212), (cx + 22, 1190)], fill=(10, 8, 10))
    im.save(f'{OUT}/f{f + 1:04d}.jpg', quality=90)
print('monitor ok')
