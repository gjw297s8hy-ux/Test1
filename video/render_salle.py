"""Reprise de la vidéo « promo-salle » avec l'offre @365daymentality (20 €/mois au lieu de 34 €).
Le décor animé d'origine (tunnel orange + haltère 3D) est conservé ; ses textes sont masqués par un panneau
en verre dépoli, et remplacés par : accroche, offre + pièces, « Comment ça marche », CTA « Commente SALLE ».
Rendu :   python3 render_salle.py          -> promo_salle_365.mp4 (+ _sans_musique.mp4)  1080x1920 60 i/s
Aperçu :  python3 render_salle.py 1 4 9    -> preview_1.png ..."""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 60, 14.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_salle_365.mp4")
SRC = os.path.join(HERE, "assets_salle", "promo-salle.mp4"); CACHE = os.path.join(HERE, "_cache", "salle")
HANDLE = "@365daymentality"
ACC = (255, 116, 18); DEEP = (150, 50, 0); WHITE = (255, 255, 255); GREY = (175, 165, 160); RED = (255, 60, 80)
DARK = (16, 12, 10); GOLD = (255, 196, 40)
FD = "/usr/share/fonts/opentype/inter/"
FW = {"black": FD + "Inter-Black.otf", "xb": FD + "Inter-ExtraBold.otf", "b": FD + "Inter-Bold.otf", "sb": FD + "Inter-SemiBold.otf",
      "bi": FD + "InterDisplay-BlackItalic.otf"}
@lru_cache(None)
def font(w, s): return ImageFont.truetype(FW[w], s)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def out_cubic(x): return 1 - (1 - x) ** 3
def in_cubic(x): return x ** 3
def in_out(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def smooth(x): return x * x * (3 - 2 * x)
def out_back(x, s=1.9): x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, x): return a + (b - a) * x
def mix(c1, c2, x): return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))

def safe_comp(L, im, x, y):
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y); ex, ey = min(im.width, L.width - x), min(im.height, L.height - y)
    if ex > sx and ey > sy: L.alpha_composite(im, (x + sx, y + sy), (sx, sy, ex, ey))

def fade(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a))); return im

def put(L, im, cx, cy, s=1.0, a=1.0, rot=0.0, sx=1.0):
    if s <= 0.01 or a <= 0.01 or abs(sx) < 0.02: return
    w, h = max(1, int(im.width * s * abs(sx))), max(1, int(im.height * s))
    if (w, h) != im.size: im = im.resize((w, h), Image.LANCZOS)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    safe_comp(L, fade(im, a), cx - im.width / 2, cy - im.height / 2)

@lru_cache(None)
def text3d(s, size, face=WHITE, side=None, weight="black", depth=None):
    """Extruded text with soft shadow (same look as the earlier videos)."""
    f = font(weight, size); l, t, r, b = f.getbbox(s)
    depth = depth if depth is not None else max(3, int(size * 0.07)); side = side or mix(face, (0, 0, 0), 0.55)
    pad = 26; mask = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), s, font=f, fill=255)
    im = Image.new("RGBA", (mask.width + depth + 8, mask.height + depth + 8), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 160), (int(depth * 0.8), int(depth * 1.5)), mask)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(3, depth))))
    for k in range(depth, 0, -1): im.paste(mix(side, (0, 0, 0), 0.5 * k / depth) + (255,), (int(k * 0.4), k), mask)
    grad = Image.linear_gradient("L").resize(mask.size)
    faceim = Image.composite(Image.new("RGBA", mask.size, mix(face, (0, 0, 0), 0.18) + (255,)), Image.new("RGBA", mask.size, face + (255,)), grad)
    im.paste(faceim, (0, 0), mask); return im

def reveal(L, img, cx, cy, p, a=1.0):
    if p <= 0 or a <= 0: return
    p = out_cubic(clamp(p)); h = img.height; vis = max(1, int(h * p))
    safe_comp(L, fade(img.crop((0, 0, img.width, vis)), a), cx - img.width / 2, cy - h / 2 + (h - vis))

def shine(img, p, width=0.18, strength=130):
    if p <= 0 or p >= 1: return img
    w, h = img.size; x = lerp(-0.4 * w, 1.4 * w, p); bw = w * width
    band = Image.new("L", img.size, 0)
    ImageDraw.Draw(band).polygon([(x, 0), (x + bw, 0), (x + bw - h * 0.5, h), (x - h * 0.5, h)], fill=strength)
    a = np.minimum(np.array(band.filter(ImageFilter.GaussianBlur(bw * 0.2)), np.uint16), np.array(img.getchannel("A"), np.uint16))
    light = Image.new("RGBA", img.size, (255, 255, 255, 0)); light.putalpha(Image.fromarray(a.astype(np.uint8)))
    out = img.copy(); out.alpha_composite(light); return out

# ------------------------------------------------------------------ source video (time-remapped)
# (output start, output end, source start, source end): the original 10 s is stretched to 14 s
TMAP = [(0.0, 2.2, 0.0, 2.0), (2.2, 7.2, 2.0, 6.5), (7.2, 10.4, 6.5, 5.0), (10.4, 14.0, 7.2, 10.0)]
def src_time(t):
    for a, b, s0, s1 in TMAP:
        if a <= t < b: return lerp(s0, s1, (t - a) / (b - a))
    return TMAP[-1][3]

@lru_cache(maxsize=8)
def src_frame(i):
    n = len(os.listdir(CACHE)); return Image.open(os.path.join(CACHE, f"f_{int(clamp(i, 0, n - 1)) + 1:04d}.jpg")).convert("RGB")

def background(t):
    s = src_time(t) * 30; i = int(s); f = s - i
    a = src_frame(i)
    return (Image.blend(a, src_frame(i + 1), f) if f > 0.05 else a).convert("RGBA")

# ------------------------------------------------------------------ frosted glass panel (hides the original text)
PANEL_A = (90, 890, 990, 1255)      # covers "PASSE À L'ACTION"
PANEL_B = (36, 336, 1044, 1325)     # covers price / features / CTA of the original
def panel_box(t):
    k = smooth(prog(t, 1.93, 2.13))   # grows just before the original price appears
    return tuple(lerp(a, b, k) for a, b in zip(PANEL_A, PANEL_B))

def glass(L, box, t):
    x0, y0, x1, y1 = [int(v) for v in box]; w, h = x1 - x0, y1 - y0
    reg = L.crop((x0 - 40, y0 - 40, x1 + 40, y1 + 40)).convert("RGB")
    sm = reg.resize((max(1, reg.width // 4), max(1, reg.height // 4)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(11))
    bl = np.asarray(sm.resize(reg.size, Image.BILINEAR), np.float32)[40:40 + h, 40:40 + w]
    bl = bl * 0.30 + np.array([40, 16, 4], np.float32) * 0.35          # darken + warm tint
    pane = Image.fromarray(bl.clip(0, 255).astype(np.uint8)).convert("RGBA")
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 44, fill=255)
    g = Image.new("RGBA", (w + 120, h + 120), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([60, 60, w + 59, h + 59], 44, outline=ACC + (230,), width=10)
    safe_comp(L, g.filter(ImageFilter.GaussianBlur(18)), x0 - 60, y0 - 60)
    L.paste(pane, (x0, y0), m); d = ImageDraw.Draw(L)
    d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], 44, outline=ACC + (255,), width=3)
    d.rounded_rectangle([x0 + 40, y0 + 10, x1 - 40, y0 + 14], 2, fill=(255, 255, 255, 50))

@lru_cache(None)
def tag_img():
    w, h = 700, 96; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = Image.linear_gradient("L").rotate(90).resize((w, h))
    body = Image.composite(Image.new("RGBA", (w, h), (255, 140, 40, 255)), Image.new("RGBA", (w, h), (230, 80, 0, 255)), g)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 18, fill=255); im.paste(body, (0, 0), m)
    d.text((w / 2, h / 2), "BON PLAN  ·  SALLE DE SPORT", font=font("xb", 38), fill=WHITE, anchor="mm"); return im

# ------------------------------------------------------------------ coins & bills (2.5D sprites)
@lru_cache(None)
def coin_img(label="€"):
    S = 220; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=(190, 130, 10)); d.ellipse([8, 8, S - 9, S - 9], fill=GOLD)
    d.ellipse([26, 26, S - 27, S - 27], outline=(205, 140, 0), width=6)
    t = text3d(label, 110, (255, 236, 160), (160, 100, 0), depth=6); im.alpha_composite(t, (int(S / 2 - t.width / 2 + 3), int(S / 2 - t.height / 2 + 3)))
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(hl).ellipse([30, 22, 125, 90], fill=(255, 255, 255, 90))
    im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(14))); return im

@lru_cache(None)
def bill_img():
    w, h = 360, 164; im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = Image.linear_gradient("L").rotate(90).resize((w, h))
    base = Image.composite(Image.new("RGBA", (w, h), (150, 205, 140, 255)), Image.new("RGBA", (w, h), (105, 165, 100, 255)), g)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 8, fill=255); im.paste(base, (0, 0), m)
    d = ImageDraw.Draw(im); d.rounded_rectangle([8, 8, w - 9, h - 9], 6, outline=(40, 95, 45), width=4)
    d.ellipse([w / 2 - 50, h / 2 - 50, w / 2 + 50, h / 2 + 50], fill=(95, 155, 95), outline=(40, 95, 45), width=4)
    d.text((w / 2, h / 2 + 3), "$", font=font("black", 80), fill=(30, 80, 35), anchor="mm")
    for x, y in [(44, 38), (w - 44, 38), (44, h - 38), (w - 44, h - 38)]: d.text((x, y), "100", font=font("xb", 24), fill=(30, 80, 35), anchor="mm")
    return im

R = np.random.default_rng(4)
BURSTS = [(2.75, (540, 760), 26), (10.5, (540, 700), 30)]
BP = {t0: [(R.uniform(0, 2 * math.pi), R.uniform(700, 1700), R.uniform(0.35, 1.0), R.uniform(4, 14), R.uniform(0, 360), R.uniform(-300, 300),
            "€" if R.random() < 0.7 else "$") for _ in range(n)] for t0, _, n in BURSTS}
RAIN = [(R.uniform(-60, 1140), R.uniform(0, 1), R.uniform(0.35, 0.9), R.uniform(0.6, 1.4), R.uniform(0, 6.3), R.random() < 0.55) for _ in range(22)]

def sprite(L, im, x, y, s, flip, rot, a, blur):
    if s < 0.05: return
    im = im.resize((max(1, int(im.width * s * max(0.04, abs(flip)))), max(1, int(im.height * s))), Image.LANCZOS)
    im = im.rotate(rot, Image.BICUBIC, expand=True)
    if blur > 0.8:
        pad = int(blur * 2.5) + 2; c = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); c.paste(im, (pad, pad)); im = c.filter(ImageFilter.GaussianBlur(blur))
    safe_comp(L, fade(im, a), x - im.width / 2, y - im.height / 2)

def particles(L, t, front):
    for t0, (ox, oy), _ in BURSTS:
        dt = t - t0
        if not 0 < dt < 2.4: continue
        a = 1 - prog(dt, 1.7, 2.4)
        for ang, sp, sc, spin, r0, rs, lab in BP[t0]:
            if (sc > 0.7) != front: continue
            k = 2.0; m = (1 - math.exp(-k * dt)) / k
            x = ox + math.cos(ang) * sp * m; y = oy + (math.sin(ang) * sp * 0.8 - 900) * m + 0.5 * 2200 * dt * dt
            sprite(L, coin_img(lab), x, y, sc * 0.75, math.cos(spin * dt + r0), r0 + rs * dt, a, abs(sc - 0.6) * 10)
    amt = smooth(prog(t, 10.6, 11.2))
    if amt > 0.01:
        for x, ph, sc, sp, wph, is_bill in RAIN:
            if (sc > 0.7) != front: continue
            y = -200 + ((t * 380 * sp + ph * 2400) % 2400)
            xx = x + 70 * math.sin(t * 1.4 + wph)
            if is_bill: sprite(L, bill_img(), xx, y, sc * 0.8, math.cos(t * 2.3 * sp + wph), 25 * math.sin(t * 1.7 + wph), amt, abs(sc - 0.6) * 9)
            else: sprite(L, coin_img("€"), xx, y, sc * 0.55, math.cos(t * 5 * sp + wph), 10, amt, abs(sc - 0.6) * 9)

# ------------------------------------------------------------------ cards
@lru_cache(None)
def row_card(text, icon):
    w, h = 820, 110; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 26, fill=(28, 18, 12, 235), outline=(110, 55, 20, 255), width=2)
    d.ellipse([22, 20, 92, 90], fill=ACC)
    if icon == "check": d.line([(40, 56), (52, 69), (75, 42)], fill=DARK, width=8)
    else: d.text((57, 56), icon, font=font("black", 38), fill=DARK, anchor="mm")
    d.text((122, 56), text, font=font("b", 44), fill=WHITE, anchor="lm"); return im

STEPS = [("Commente « SALLE »", "sous cette vidéo"), ("Je t'envoie les infos", "directement en DM"), ("Tu t'entraînes", "pour 20 € par mois")]
@lru_cache(None)
def step_card(i):
    w, h = 860, 190; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 36, fill=(28, 18, 12, 240), outline=(110, 55, 20, 255), width=2)
    d.rounded_rectangle([0, 0, 14, h - 1], 7, fill=ACC)
    d.ellipse([44, 45, 144, 145], fill=ACC); d.text((94, 97), str(i + 1), font=font("black", 60), fill=DARK, anchor="mm")
    d.text((178, 50), STEPS[i][0], font=font("xb", 46), fill=WHITE); d.text((178, 112), STEPS[i][1], font=font("sb", 34), fill=GREY)
    return im

@lru_cache(None)
def badge():
    S = 230; im = Image.new("RGBA", (S + 20, S + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for k in range(14, 0, -1): d.ellipse([k * 0.4, k, S + k * 0.4, S + k], fill=mix(RED, (0, 0, 0), 0.4 + 0.3 * k / 14))
    d.ellipse([0, 0, S, S], fill=RED); d.ellipse([12, 12, S - 12, S - 12], outline=(255, 255, 255, 110), width=4)
    t = text3d("-41%", 64, WHITE, (120, 10, 25), depth=4); im.alpha_composite(t, (int(S / 2 - t.width / 2 + 4), int(S / 2 - t.height / 2 + 4))); return im

# ------------------------------------------------------------------ overlay per section
def overlay(L, t):
    if t < 2.15:   # A : hook (inside the small panel)
        a = 1 - smooth(prog(t, 1.9, 2.1))
        reveal(L, text3d("TU PAIES ENCORE", 74), 540, 975, prog(t, 0.1, 0.45), a)
        bw = 820 * out_cubic(prog(t, 0.4, 0.7))
        if bw > 4:
            bar = Image.new("RGBA", (int(bw), 128), (0, 0, 0, 0)); ImageDraw.Draw(bar).rounded_rectangle([0, 0, bw - 1, 127], 20, fill=ACC)
            safe_comp(L, fade(bar.rotate(2, Image.BICUBIC, expand=True), a), 540 - 410, 1060)
        reveal(L, text3d("34 € TA SALLE ?", 92, DARK, DEEP), 540, 1122, prog(t, 0.5, 0.85), a)
    elif t < 7.2:   # B : the offer
        a = 1 - smooth(prog(t, 6.95, 7.2))
        reveal(L, text3d("AVEC MOI", 76), 540, 440, prog(t, 2.25, 2.55), a)
        reveal(L, text3d("34 €", 92, GREY), 540, 565, prog(t, 2.35, 2.6), a)
        if t > 2.55:
            sp = out_cubic(prog(t, 2.55, 2.75)); d = ImageDraw.Draw(L)
            d.line([(440, 590), (440 + 200 * sp, 545)], fill=RED + (int(255 * a),), width=12)
        s = out_back(prog(t, 2.7, 3.0), 2.2) * (1 + 0.025 * math.sin((t - 3.0) * 8) if t > 3.0 else 1)
        put(L, text3d("20 €", 250, ACC, DEEP), 540, 760, s, clamp(s * 2) * a)
        reveal(L, text3d("PAR MOIS", 70, WHITE, weight="xb"), 540, 920, prog(t, 3.0, 3.3), a)
        bp = prog(t, 3.2, 4.0)
        if bp > 0:
            ang = (720 * (1 - out_cubic(bp)) + 15 * math.sin(t * 3)) % 360
            put(L, badge(), 865, 640, out_back(clamp(bp * 3)) * 0.92, a, rot=14, sx=math.cos(math.radians(ang)))
        for i, (txt, ic) in enumerate([("Tu économises 168 € / an", "€"), ("Paiement au mois", "check")]):
            p = prog(t, 4.2 + 0.3 * i, 4.6 + 0.3 * i)
            if p > 0:
                img = shine(row_card(txt, ic), prog(t, 5.4 + 0.2 * i, 5.9 + 0.2 * i))
                put(L, img, 540 + (1 - out_cubic(p)) * -400, 1070 + i * 130, 1, clamp(p * 1.5) * a)
    elif t < 10.4:   # C : how it works
        a = 1 - smooth(prog(t, 10.15, 10.4))
        reveal(L, text3d("COMMENT ÇA MARCHE ?", 66), 540, 445, prog(t, 7.3, 7.65), a)
        for i in range(3):
            p = prog(t, 7.6 + 0.4 * i, 8.0 + 0.4 * i)
            if p > 0:
                img = shine(step_card(i), prog(t, 9.0 + 0.15 * i, 9.5 + 0.15 * i))
                put(L, img, 540, 640 + i * 225, lerp(0.8, 1, out_back(p)), clamp(p * 2) * a)
    else:   # D : call to action
        reveal(L, text3d("20 € / MOIS", 110, ACC, DEEP), 540, 470, prog(t, 10.45, 10.8))
        reveal(L, text3d("au lieu de 34 €", 54, WHITE, weight="xb"), 540, 580, prog(t, 10.6, 10.9))
        pb = out_back(prog(t, 10.8, 11.2))
        if pb > 0.02:
            btn = Image.new("RGBA", (860, 170), (0, 0, 0, 0)); bd = ImageDraw.Draw(btn); bd.rounded_rectangle([0, 0, 859, 169], 85, fill=ACC)
            tx = text3d("COMMENTE « SALLE »", 64, DARK, DEEP, depth=4); btn.alpha_composite(tx, (int(430 - tx.width / 2), int(85 - tx.height / 2)))
            for k in range(3): btn = shine(btn, prog(t, 11.5 + k * 0.7, 11.95 + k * 0.7), 0.16, 120)
            pulse = 1 + 0.04 * math.sin((t - 11.2) * 7) if t > 11.2 else 1
            g = Image.new("RGBA", (W, 400), (0, 0, 0, 0)); ImageDraw.Draw(g).rounded_rectangle([110, 120, 970, 280], 80, fill=ACC + (110,))
            safe_comp(L, fade(g.filter(ImageFilter.GaussianBlur(40)), clamp(pb)), 0, 790 - 200)
            put(L, btn, 540, 790, pb * pulse)
        reveal(L, text3d("ou écris-moi en DM", 50, WHITE, weight="xb"), 540, 960, prog(t, 11.2, 11.5))
        reveal(L, text3d(HANDLE, 74, ACC, DEEP), 540, 1065, prog(t, 11.4, 11.7))
        reveal(L, text3d("Abonne-toi pour plus de bons plans", 38, GREY, weight="sb", depth=2), 540, 1190, prog(t, 11.7, 12.0))

# ------------------------------------------------------------------ compose / post
IMPACTS = [(0.55, 0.5), (2.75, 1.0), (7.25, 0.4), (10.5, 0.9)]
def impact(t, rate=8.0): return sum(s * math.exp(-(t - t0) * rate) for t0, s in IMPACTS if t >= t0)

def compose(t):
    img = background(t)
    glass(img, panel_box(t), t)
    put(img, tag_img(), 540, 288, 1 + 0.03 * impact(t))
    particles(img, t, False); overlay(img, t); particles(img, t, True)
    sx = sum(s * math.exp(-(t - t0) * 10) * 14 * math.sin((t - t0) * 70) for t0, s in IMPACTS if t >= t0)
    if abs(sx) > 0.5:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 255)); safe_comp(sh, img, sx, sx * 0.6); img = sh
    return img

VIG = None
def post(img, t, fi):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        VIG = (1 - 0.4 * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None].astype(np.float32)
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 150, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR), np.float32) * 0.55
    ca = int(impact(t, 10) * 7)
    if ca > 0: arr[..., 0] = np.roll(arr[..., 0], ca, axis=1); arr[..., 2] = np.roll(arr[..., 2], -ca, axis=1)
    fl = sum(s * math.exp(-(t - t0) * 14) * 0.3 for t0, s in IMPACTS if t >= t0)
    arr = arr + (np.array([255, 200, 140], np.float32) - arr) * min(fl, 0.5)
    arr = arr * VIG + np.random.default_rng(fi).normal(0, 2, (H, W, 1)).astype(np.float32)
    arr *= 1 - smooth(prog(t, 13.6, 14.0))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(compose(t), t, i).tobytes()

# ------------------------------------------------------------------ audio
def make_audio(path, music=True):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(1)
    def add(sig, t0):
        i = int(t0 * sr)
        if 0 <= i < n: j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    beat = 60 / 124
    if music:
        tk = T(0.35); kick = np.sin(2 * np.pi * (48 + 120 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 8)
        th = T(0.04); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 110) * 0.12
        ts = T(0.2); clap = Rn.uniform(-1, 1, len(ts)) * np.exp(-ts * 22) * 0.3
        tb = T(beat); chords = [(55, 110, 164.8), (49, 98, 146.8), (65.4, 130.8, 196), (58.3, 116.5, 174.6)]
        k = 0
        while k * beat < DUR - 0.5:
            t0 = k * beat; root, a2, a3 = chords[(k // 4) % 4]
            add(kick * 0.9, t0); add(hat, t0 + beat / 2); add(hat * 0.6, t0 + beat * 0.75)
            if k % 2 == 1: add(clap, t0)
            add((np.sign(np.sin(2 * np.pi * root * tb)) * 0.09 + np.sin(2 * np.pi * a2 * tb) * 0.05) * np.exp(-tb * 4), t0)
            if k % 4 == 0:
                tp = T(beat * 4); pad = sum(np.sin(2 * np.pi * f * tp) for f in (a2 * 2, a3 * 2, a2 * 3)) * 0.022
                add(pad * np.minimum(1, tp / 0.3) * np.minimum(1, (beat * 4 - tp) / 0.3), t0)
            k += 1
    for t0, s in IMPACTS:
        tt = T(1.0); boom = np.sin(2 * np.pi * (40 + 55 * np.exp(-tt * 10)) * tt) * np.exp(-tt * 4)
        add((boom + Rn.normal(0, 1, len(tt)) * np.exp(-tt * 16) * 0.35) * 0.5 * s, t0)
    tw = T(0.35)
    for t0 in (2.0, 7.05, 10.25):
        add(np.convolve(Rn.normal(0, 1, len(tw)), np.ones(6) / 6, "same") * np.sin(np.pi * tw / 0.35) ** 2 * 0.25, t0)
    tc = T(0.12)
    for t0, _, _ in BURSTS:
        for j in range(14): add(np.sin(2 * np.pi * Rn.uniform(2500, 4200) * tc) * np.exp(-tc * 30) * 0.11, t0 + Rn.uniform(0, 0.9))
        tch = T(0.9); add((np.sin(2 * np.pi * 1568 * tch) + 0.6 * np.sin(2 * np.pi * 2349 * tch)) * np.exp(-tch * 5) * 0.22, t0 + 0.05)
    for t0 in (4.2, 4.5, 7.6, 8.0, 8.4, 10.8):
        tp = T(0.15); add(np.sin(2 * np.pi * 660 * tp) * np.exp(-tp * 20) * 0.2, t0)
    fo = int(0.4 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.3) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

def prepare():
    if os.path.exists(os.path.join(CACHE, "f_0001.jpg")): return
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-q:v", "2", os.path.join(CACHE, "f_%04d.jpg")], check=True)

if __name__ == "__main__":
    prepare()
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            t = float(s); post(compose(t), t, int(t * FPS)).save(f"preview_{s}.png")
        sys.exit()
    wav = OUT.replace(".mp4", ".wav"); make_audio(wav)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "16M", "-bufsize", "32M",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(frame_rgb, range(int(DUR * FPS)), chunksize=4)):
            p.stdin.write(buf)
            if i % 180 == 0: print(f"frame {i}", flush=True)
    p.stdin.close(); p.wait(); os.remove(wav)
    wav2 = OUT.replace(".mp4", "_sfx.wav"); make_audio(wav2, music=False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", OUT, "-i", wav2, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", OUT.replace(".mp4", "_sans_musique.mp4")], check=True)
    os.remove(wav2); print("OK ->", OUT)
