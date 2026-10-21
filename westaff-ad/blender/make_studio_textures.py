"""Textures procédurales du studio (écrans DAW, contrôleurs, racks, TV) — générées, sans visuel tiers."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random, math, os
OUT = os.path.join(os.path.dirname(__file__), 'tex'); os.makedirs(OUT, exist_ok=True)
F = lambda s, w='InterDisplay-Black': ImageFont.truetype(os.path.join(os.path.dirname(__file__), '..', 'public', 'fonts', f'{w}.otf'), s)
R = random.Random(4)
PAL = [(255, 64, 64), (255, 170, 40), (250, 230, 70), (90, 220, 120), (60, 200, 255), (120, 120, 255), (230, 90, 255)]

def daw(w=1920, h=1080):
    im = Image.new('RGB', (w, h), (22, 23, 28)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 40], fill=(40, 42, 50))
    for x in range(0, w // 2, 24):  # tranches de console
        c = PAL[(x // 24) % len(PAL)]
        d.rectangle([x + 2, 50, x + 21, h - 10], fill=(32, 34, 40))
        d.rectangle([x + 4, 60, x + 19, 90], fill=c)
        lvl = R.randint(250, 900); d.rectangle([x + 8, h - lvl, x + 15, h - 20], fill=(80, 230, 110))
        d.rectangle([x + 8, h - lvl - 40, x + 15, h - lvl], fill=(250, 210, 60))
        fy = 500 + R.randint(-80, 80); d.rectangle([x + 5, fy, x + 18, fy + 20], fill=(200, 200, 205))
    for row in range(14):  # pistes / régions
        y = 60 + row * 70; c = PAL[row % len(PAL)]
        d.rectangle([w // 2 + 10, y, w - 10, y + 62], fill=(30, 31, 37))
        x = w // 2 + 20
        while x < w - 40:
            L = R.randint(80, 320)
            d.rectangle([x, y + 6, min(w - 20, x + L), y + 56], fill=tuple(int(v * 0.75) for v in c))
            for k in range(0, L, 6):
                a = R.randint(4, 22); d.line([x + k, y + 31 - a, x + k, y + 31 + a], fill=tuple(min(255, v + 60) for v in c))
            x += L + R.randint(10, 60)
    d.line([w * 0.72, 40, w * 0.72, h], fill=(255, 255, 255), width=2)
    return im

def touch(w=800, h=500):
    im = Image.new('RGB', (w, h), (15, 16, 20)); d = ImageDraw.Draw(im)
    for i in range(8):
        x = 20 + i * 97; c = PAL[i % len(PAL)]
        d.rectangle([x, 20, x + 85, 60], fill=c)
        lvl = R.randint(120, 380); d.rectangle([x + 30, h - lvl, x + 55, h - 20], fill=tuple(int(v * 0.8) for v in c))
    return im

def rack(w=1024, h=256, seed=0):
    r = random.Random(seed); base = r.choice([(28, 28, 32), (190, 186, 175), (40, 70, 60), (20, 30, 55)])
    im = Image.new('RGB', (w, h), base); d = ImageDraw.Draw(im)
    for sx in (18, w - 34): d.ellipse([sx, 20, sx + 16, 36], fill=(120, 120, 120)); d.ellipse([sx, h - 36, sx + 16, h - 20], fill=(120, 120, 120))
    x = 70
    while x < w - 120:
        k = r.random()
        if k < 0.35:  # VU-mètre rétroéclairé
            d.rectangle([x, 50, x + 130, 170], fill=(255, 196, 90)); d.line([x + 20, 160, x + 20 + r.randint(30, 100), 70], fill=(30, 20, 10), width=4); x += 160
        elif k < 0.7:  # boutons
            for j in range(3):
                cx, cy = x + 25, 60 + j * 60; d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(70, 70, 75)); d.ellipse([cx - 6, cy - 18, cx + 6, cy - 6], fill=(230, 230, 230))
            x += 70
        else:  # LEDs
            for j in range(8):
                col = r.choice([(60, 160, 255), (90, 255, 140), (255, 60, 60)]); d.ellipse([x, 60 + j * 18, x + 10, 70 + j * 18], fill=col)
            x += 40
    return im

def tv(w=1600, h=900):
    im = Image.new('RGB', (w, h), (10, 3, 6)); d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / h; d.line([0, y, w, y], fill=(int(30 + 60 * k), int(4 + 4 * k), int(10 + 12 * k)))
    d.pieslice([w * 0.45, -h * 0.6, w * 1.6, h * 1.4], 160, 250, fill=(120, 10, 25))
    d.text((w / 2, h / 2 - 40), 'NPNG', font=F(300), fill=(255, 255, 255), anchor='mm')
    d.text((w / 2, h / 2 + 160), "O'NEAL", font=F(110, 'Inter-ExtraBold'), fill=(235, 40, 50), anchor='mm')
    return im

daw().save(f'{OUT}/daw.png'); touch().save(f'{OUT}/touch.png'); tv().save(f'{OUT}/tv.png')
for i in range(6): rack(seed=i).save(f'{OUT}/rack{i}.png')
print('textures ok')
