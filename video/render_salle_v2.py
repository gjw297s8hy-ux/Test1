"""Promo salle v2 pour @365daymentality : typographie cinétique, coupes rapides sur le beat (140 bpm).
Pas de pièces ni de « Commente SALLE » : accroche -> 34 € barré -> compteur -> 20 €/mois -> -41 % -> 168 €/an
-> paiement au mois -> « Écris-moi en DM ». L'haltère 3D de la vidéo d'origine sert de fond animé.
Rendu :   python3 render_salle_v2.py        -> promo_salle_365_v2.mp4 (+ _sans_musique.mp4)  1080x1920 60 i/s
Aperçu :  python3 render_salle_v2.py 1 4    -> preview_1.png ..."""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H, FPS = 1080, 1920, 60
B = 60 / 140                     # one beat
DUR = 28 * B                     # 12.0 s
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_salle_365_v2.mp4")
SRC = os.path.join(HERE, "assets_salle", "promo-salle.mp4"); CACHE = os.path.join(HERE, "_cache", "salle")
HANDLE = "@365daymentality"
ACC = (255, 110, 16); WHITE = (255, 255, 255); BLACK = (10, 8, 8); RED = (255, 48, 64); PAPER = (244, 240, 234)
FD = "/usr/share/fonts/opentype/inter/"
FW = {"bi": FD + "InterDisplay-BlackItalic.otf", "black": FD + "InterDisplay-Black.otf", "xb": FD + "Inter-ExtraBold.otf", "sb": FD + "Inter-SemiBold.otf"}
@lru_cache(None)
def font(w, s): return ImageFont.truetype(FW[w], s)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def out_cubic(x): return 1 - (1 - x) ** 3
def out_expo(x): return 1 if x >= 1 else 1 - 2 ** (-10 * x)
def in_cubic(x): return x ** 3
def in_out(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def smooth(x): return x * x * (3 - 2 * x)
def lerp(a, b, x): return a + (b - a) * x
def beat(n): return n * B

def comp(L, im, x, y):
    x, y = int(round(x)), int(round(y)); sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, L.width - x), min(im.height, L.height - y)
    if ex > sx and ey > sy: L.alpha_composite(im, (x + sx, y + sy), (sx, sy, ex, ey))

def fade(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a))); return im

def place(L, im, cx, cy, s=1.0, a=1.0, rot=0.0):
    if s <= 0.01 or a <= 0.01: return
    if abs(s - 1) > 0.002: im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR if s > 1.6 else Image.LANCZOS)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    comp(L, fade(im, a), cx - im.width / 2, cy - im.height / 2)

# ------------------------------------------------------------------ type
@lru_cache(None)
def txt(s, size, fill=WHITE, weight="bi", outline=0, spacing=0):
    f = font(weight, size); l, t, r, b = f.getbbox(s); pad = 30 + outline
    w = int(r - l + spacing * max(0, len(s) - 1)) + 2 * pad; h = b - t + 2 * pad
    def mask(stroke):
        m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m)
        if spacing:
            x = pad
            for ch in s: d.text((x - l, pad - t), ch, font=f, fill=255, stroke_width=stroke, stroke_fill=255); x += f.getlength(ch) + spacing
        else: d.text((pad - l, pad - t), s, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
        return m
    m = ImageChops.subtract(mask(outline), mask(0)) if outline else mask(0)
    im = Image.new("RGBA", (w, h), fill + (0,)); im.putalpha(m); return im

@lru_cache(None)
def fit(s, maxw, weight="bi", spacing=0):
    f = font(weight, 200); wd = f.getlength(s) + spacing * 2 * len(s)
    return max(20, int(200 * maxw / wd))

def slam(L, s, cx, cy, maxw, fill, t, t0, weight="bi", rot=0.0, echo=None):
    """Word punches in from large, with outline echoes trailing behind it."""
    if t < t0: return
    size = fit(s, maxw, weight); e = prog(t, t0, t0 + 0.12); sc = lerp(1.9, 1.0, out_expo(e))
    tr = prog(t, t0, t0 + 0.38)
    if tr < 1:
        o = txt(s, size, echo or fill, weight, outline=max(4, size // 40))
        for k in (3, 2, 1): place(L, o, cx, cy, 1 + 0.16 * k * (1 - out_cubic(tr)) + 0.02 * k, (1 - tr) * 0.55, rot)
    place(L, txt(s, size, fill, weight), cx, cy, sc, clamp(e * 3), rot)

def reveal_up(L, im, cx, cy, p, a=1.0):
    if p <= 0: return
    p = out_expo(clamp(p)); h = im.height; vis = max(1, int(h * p))
    comp(L, fade(im.crop((0, 0, im.width, vis)), a), cx - im.width / 2, cy - h / 2 + (h - vis))

# ------------------------------------------------------------------ backgrounds
def prepare():
    if os.path.exists(os.path.join(CACHE, "f_0001.jpg")): return
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-q:v", "2", os.path.join(CACHE, "f_%04d.jpg")], check=True)

@lru_cache(maxsize=4)
def src_frame(i):
    n = len(os.listdir(CACHE)); return Image.open(os.path.join(CACHE, f"f_{int(clamp(i, 0, n - 1)) + 1:04d}.jpg")).convert("RGB")

def bg_plate(t, dark=0.55, zoom=1.0):
    """The 3D dumbbell of the original video, cropped (no text there) and blown up as a moving backdrop."""
    s = (2.1 + t * 0.62) * 30; fr = src_frame(int(s))
    cw = 360 / zoom; chh = 640 / zoom; cx = 540 + 25 * math.sin(t * 0.9); cy = 1600
    im = fr.crop((int(cx - cw / 2), int(cy - chh / 2), int(cx + cw / 2), int(cy + chh / 2))).resize((W, H), Image.BICUBIC)
    arr = np.asarray(im, np.float32) * dark
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")

def bg_solid(col, t):
    im = Image.new("RGBA", (W, H), col + (255,)); d = ImageDraw.Draw(im)
    shade = tuple(int(c * 0.9) for c in col)
    off = (t * 900) % 240
    for k in range(-12, 12):   # fast diagonal stripes
        x = k * 240 + off; d.polygon([(x, 0), (x + 90, 0), (x + 90 - H * 0.45, H), (x - H * 0.45, H)], fill=shade + (255,))
    return im

R = np.random.default_rng(6)
STREAKS = [(R.uniform(-200, W + 600), R.uniform(0, 1), R.uniform(180, 520), R.uniform(1600, 3400), R.uniform(2, 6)) for _ in range(26)]
def streaks(L, t, col=ACC, a=0.5):
    """Speed lines racing diagonally across the frame."""
    d = ImageDraw.Draw(L)
    for x, ph, ln, sp, wd in STREAKS:
        p = ((t * sp / 2600) + ph) % 1; y = -600 + p * (H + 1200); xx = x - p * 620
        d.line([(xx, y), (xx - ln * 0.42, y + ln)], fill=col + (int(255 * a * math.sin(math.pi * p)),), width=int(wd))

@lru_cache(None)
def marquee_strip(text, fill, band):
    f = font("bi", 64); unit = f.getlength(text) + 60; n = int(2600 / unit) + 2
    im = Image.new("RGBA", (int(unit * n), 108), band + (255,)); d = ImageDraw.Draw(im)
    for k in range(n): d.text((k * unit, 54), text, font=f, fill=fill, anchor="lm")
    return im, unit

def marquee(L, t, text, cy, rot, speed, fill=BLACK, band=ACC, a=1.0):
    strip, unit = marquee_strip(text, fill, band); off = (t * speed) % unit
    seg = strip.crop((int(off if speed > 0 else unit - off), 0, int((off if speed > 0 else unit - off)) + 1500, 108))
    place(L, seg, W / 2, cy, 1, a, rot)

# ------------------------------------------------------------------ scenes
T1, T2, T3, T4, T5, T6, T7, T8 = beat(0), beat(2), beat(6), beat(8), beat(12), beat(14), beat(17), beat(19)

def scene1(t):   # TU PAIES / ENCORE
    L = bg_plate(t, 0.62); streaks(L, t)
    slam(L, "TU PAIES", 540, 760, 900, WHITE, t, 0.02)
    slam(L, "ENCORE", 540, 990, 900, ACC, t, beat(1))
    return L

def scene2(t):   # 34 € TA SALLE ?
    L = bg_plate(t, 0.58, 1.15); streaks(L, t)
    pulse = 1 + 0.03 * math.exp(-((t - T2) % B) * 9)
    slam(L, "34 €", 540, 800, 830, WHITE, t, T2)
    if t > T2 + 0.12: place(L, txt("34 €", fit("34 €", 830), WHITE), 540, 800, pulse)
    bw = 860 * out_expo(prog(t, beat(4), beat(4) + 0.18))
    if bw > 4:
        bar = Image.new("RGBA", (int(bw), 150), ACC + (255,)); place(L, bar, 540 - (860 - bw) / 2, 1190, 1, 1, 3)
        reveal_up(L, txt("TA SALLE ?", 118, BLACK).rotate(3, Image.BICUBIC, expand=True), 540, 1190, prog(t, beat(4) + 0.05, beat(4) + 0.25))
    return L

def scene3(t):   # slash, then the price rolls down
    L = bg_plate(t, 0.5, 1.3); streaks(L, t, RED, 0.6)
    size = fit("34 €", 830); roll = prog(t, beat(7), T4)
    if roll <= 0:
        place(L, txt("34 €", size, WHITE), 540 + 14 * math.sin(t * 90) * (1 - prog(t, T3, T3 + 0.3)), 800)
        sp = out_expo(prog(t, T3, T3 + 0.14))
        d = ImageDraw.Draw(L); d.line([(60, 960), (60 + 960 * sp, 960 - 330 * sp)], fill=RED + (255,), width=46)
    else:
        val = lerp(34, 20, in_out(roll)); n = math.ceil(val - 1e-6); fr = n - val; hgt = 460
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        place(lay, txt(f"{n} €", size, WHITE), 540, 800 - fr * hgt); place(lay, txt(f"{n - 1} €", size, WHITE), 540, 800 + (1 - fr) * hgt)
        sp = math.sin(math.pi * roll)     # vertical motion blur while it spins
        if sp > 0.15:
            a = np.asarray(lay, np.float32); acc = np.zeros_like(a); k = 7
            for j in range(k): acc += np.roll(a, int((j - k // 2) * 26 * sp), axis=0)
            lay = Image.fromarray((acc / k).astype(np.uint8), "RGBA")
        m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).rectangle([0, 540, W, 1060], fill=255)
        L.paste(lay, (0, 0), ImageChops.multiply(lay.getchannel("A"), m))
    return L

def scene4(t):   # 20 € PAR MOIS
    dt = t - T4
    if dt < 0.05: L = bg_solid(ACC, t); col = BLACK
    elif dt < 0.10: L = Image.new("RGBA", (W, H), WHITE + (255,)); col = BLACK
    else: L = bg_plate(t, 0.55, 1.1); streaks(L, t); col = ACC
    size = fit("20 €", 830); sc = lerp(1.7, 1.0, out_expo(prog(t, T4, T4 + 0.16))) * (1 + 0.035 * math.exp(-(dt % B) * 9))
    if dt >= 0.10:
        o = txt("20 €", size, ACC, outline=10); tr = prog(t, T4, T4 + 0.5)
        for k in (3, 2, 1): place(L, o, 540, 790, sc * (1 + 0.14 * k * (1 - out_cubic(tr)) + 0.03 * k), (1 - tr) * 0.5 + 0.12)
        marquee(L, t, "20 € / MOIS  —  ", 330, -5, 520); marquee(L, t, "AU LIEU DE 34 €  —  ", 1420, -5, -420, WHITE, BLACK)
    place(L, txt("20 €", size, col), 540, 790, sc)
    slam(L, "PAR MOIS", 540, 1110, 620, WHITE if dt >= 0.1 else BLACK, t, beat(9))
    return L

def scene5(t):   # -41 %
    L = bg_solid(ACC, t)
    slam(L, "-41%", 540, 800, 840, BLACK, t, T5, echo=WHITE)
    slam(L, "MOINS CHER", 540, 1130, 760, WHITE, t, T5 + B * 0.5, weight="black")
    return L

def scene6(t):   # 168 € / an
    L = bg_plate(t, 0.55, 1.2); streaks(L, t)
    n = int(round(168 * out_expo(prog(t, T6, T6 + 0.55))))
    size = fit("168 €", 840); sc = lerp(1.5, 1, out_expo(prog(t, T6, T6 + 0.14))) * (1 + 0.03 * math.exp(-((t - T6) % B) * 9))
    place(L, txt(f"{n} €", size, WHITE), 540, 760, sc)
    slam(L, "ÉCONOMISÉS", 540, 1040, 880, ACC, t, T6 + B)
    slam(L, "PAR AN", 540, 1210, 520, WHITE, t, T6 + B * 1.5, weight="black")
    return L

def scene7(t):   # paiement au mois
    L = bg_solid(PAPER, t)
    slam(L, "PAIEMENT", 540, 780, 940, BLACK, t, T7, echo=ACC)
    slam(L, "AU MOIS", 540, 1020, 940, ACC, t, T7 + B * 0.5, echo=BLACK)
    return L

def scene8(t):   # call to action : DM
    L = bg_plate(t, 0.52, 1.1); streaks(L, t)
    pulse = 1 + 0.03 * math.exp(-((t - T8) % B) * 9)
    marquee(L, t, "20 € / MOIS AU LIEU DE 34 €  —  ", 300, -4, 420, a=prog(t, beat(22), beat(22) + 0.2))
    slam(L, "INTÉRESSÉ ?", 540, 560, 640, WHITE, t, T8, weight="black")
    slam(L, "ÉCRIS-MOI", 540, 820, 960, WHITE, t, beat(20))
    slam(L, "EN DM", 540, 1070, 760, ACC, t, beat(21))
    p = out_expo(prog(t, beat(22), beat(22) + 0.2))
    if p > 0.02:
        tx = txt(HANDLE, 84, BLACK, "black"); pill = Image.new("RGBA", (tx.width + 60, 150), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle([0, 0, pill.width - 1, 149], 75, fill=ACC + (255,))
        pill.alpha_composite(tx, (30, 75 - tx.height // 2))
        sw = prog((t - beat(23)) % (B * 4), 0, 0.5)   # light sweep
        if 0 < sw < 1 and t > beat(23):
            band = Image.new("L", pill.size, 0); x = lerp(-200, pill.width + 200, sw)
            ImageDraw.Draw(band).polygon([(x, 0), (x + 130, 0), (x + 60, 150), (x - 70, 150)], fill=150)
            lt = Image.new("RGBA", pill.size, (255, 255, 255, 0)); lt.putalpha(ImageChops.darker(band.filter(ImageFilter.GaussianBlur(10)), pill.getchannel("A")))
            pill.alpha_composite(lt)
        g = Image.new("RGBA", (W, 420), (0, 0, 0, 0)); ImageDraw.Draw(g).rounded_rectangle([W / 2 - pill.width / 2, 135, W / 2 + pill.width / 2, 285], 75, fill=ACC + (120,))
        comp(L, fade(g.filter(ImageFilter.GaussianBlur(45)), p), 0, 1330 - 210)
        place(L, pill, 540, 1330, lerp(1.5, 1, p) * pulse, clamp(p * 2))
    return L

SCENES = [(T1, scene1, "cut"), (T2, scene2, "zoom"), (T3, scene3, "glitch"), (T4, scene4, "cut"), (T5, scene5, "push_l"),
          (T6, scene6, "zoom"), (T7, scene7, "push_u"), (T8, scene8, "flash")]

# ------------------------------------------------------------------ transitions / compose / post
def shift_blur(im, dx, dy, blur):
    a = np.asarray(im.convert("RGB"), np.float32); acc = np.zeros_like(a); n = 7 if blur > 3 else 1
    for k in range(n):
        f = (k / max(1, n - 1) - 0.5) if n > 1 else 0
        acc += np.roll(np.roll(a, int(dx + f * blur * (1 if dx or not dy else 0)), axis=1), int(dy + f * blur * (1 if dy else 0)), axis=0)
    return Image.fromarray((acc / n).astype(np.uint8)).convert("RGBA")

def zoom_blur(im, s, amt):
    acc = None
    for k in range(5):
        z = s * (1 + 0.06 * k * amt); w, h = int(W * z), int(H * z); r = im.resize((w, h), Image.BILINEAR)
        if z >= 1: r = r.crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))
        else:
            c = Image.new("RGBA", (W, H), BLACK + (255,)); c.paste(r, ((W - w) // 2, (H - h) // 2)); r = c
        acc = r if acc is None else Image.blend(acc, r, 1 / (k + 1))
    return acc

TIN, TOUT = 0.16, 0.10
def compose(t):
    idx = max(i for i, (t0, _, _) in enumerate(SCENES) if t >= t0)
    t0, fn, kind = SCENES[idx]; img = fn(t)
    nxt = SCENES[idx + 1] if idx + 1 < len(SCENES) else None
    pin = prog(t, t0, t0 + TIN)
    if pin < 1 and idx > 0:
        e = 1 - out_expo(pin)
        if kind == "push_l": img = shift_blur(img, W * e, 0, 260 * e)
        elif kind == "push_u": img = shift_blur(img, 0, H * 0.6 * e, 300 * e)
        elif kind == "zoom": img = zoom_blur(img, 1 + 0.9 * e, e * 2)
    if nxt and t > nxt[0] - TOUT:
        e = in_cubic(prog(t, nxt[0] - TOUT, nxt[0]))
        if nxt[2] == "push_l": img = shift_blur(img, -W * e, 0, 260 * e)
        elif nxt[2] == "push_u": img = shift_blur(img, 0, -H * 0.6 * e, 300 * e)
        elif nxt[2] == "zoom": img = zoom_blur(img, 1 + 1.2 * e, e * 2)
    return img

HITS = [0.02, beat(1), T2, beat(4), T3, T4, beat(9), T5, T6, T6 + B, T7, T7 + B * 0.5, T8, beat(20), beat(21), beat(22)]
GLITCH = [(T3, T3 + 0.22), (T4 - 0.07, T4), (T8, T8 + 0.12)]
VIG = None
def post(img, t, fi):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        VIG = (1 - 0.4 * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None].astype(np.float32)
    hit = sum(math.exp(-(t - h) * 11) for h in HITS if t >= h)
    if hit > 0.05:   # camera shake + punch on every slam
        s = 1 + 0.02 * min(hit, 1.5); w, h = int(W * s), int(H * s); z = img.resize((w, h), Image.BILINEAR)
        ox = (w - W) // 2 + int(10 * hit * math.sin(t * 80)); oy = (h - H) // 2 + int(8 * hit * math.cos(t * 67))
        ox = int(clamp(ox, 0, w - W)); oy = int(clamp(oy, 0, h - H)); img = z.crop((ox, oy, ox + W, oy + H))
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 170, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR), np.float32) * 0.45
    g = 0.0
    for a, b in GLITCH:
        if a <= t <= b: g = 1.0
    ca = int(min(hit, 1.2) * 7 + g * 16)
    if ca > 0: arr[..., 0] = np.roll(arr[..., 0], ca, axis=1); arr[..., 2] = np.roll(arr[..., 2], -ca, axis=1)
    if g > 0:
        r = np.random.default_rng(fi)
        for _ in range(9):
            y0 = int(r.integers(0, H - 60)); hh = int(r.integers(14, 150)); arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], int(r.normal(0, 80)), axis=1)
    fl = 0.6 * math.exp(-max(0, t - T8) * 16) if t >= T8 else 0
    arr = arr + (255 - arr) * fl
    arr = arr * VIG + np.random.default_rng(fi + 7).normal(0, 2.2, (H, W, 1)).astype(np.float32)
    arr *= 1 - smooth(prog(t, DUR - 0.3, DUR))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(compose(t), t, i).tobytes()

# ------------------------------------------------------------------ audio (140 bpm)
def make_audio(path, music=True):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(5)
    def add(sig, t0):
        i = int(t0 * sr)
        if 0 <= i < n: j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    if music:
        tk = T(0.3); kick = np.sin(2 * np.pi * (46 + 130 * np.exp(-tk * 32)) * tk) * np.exp(-tk * 9)
        ts = T(0.18); clap = (Rn.uniform(-1, 1, len(ts)) * 0.8 + np.sin(2 * np.pi * 210 * ts) * 0.3) * np.exp(-ts * 24) * 0.34
        th = T(0.03); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 130) * 0.11
        notes = [55, 55, 65.4, 49, 55, 55, 73.4, 65.4]
        for k in range(28):
            t0 = beat(k); drop = not (beat(6) <= t0 < beat(8))          # drums drop out before the "20 €" hit
            if drop:
                add(kick * 0.95, t0)
                if k % 2 == 1: add(clap, t0)
                for h in range(4): add(hat * (1 if h == 2 else 0.55), t0 + h * B / 4)
            tb = T(B); f = notes[(k // 2) % 8]
            add((np.sign(np.sin(2 * np.pi * f * tb)) * 0.08 + np.sin(2 * np.pi * f * tb) * 0.2) * np.exp(-tb * 5), t0)
            if k % 4 == 0 and k >= 8:
                tp = T(B * 2); stab = sum(np.sign(np.sin(2 * np.pi * f * m * tp)) for m in (4, 5, 6)) * 0.02 * np.exp(-tp * 5)
                add(stab, t0)
        for t1 in (T4, T8):   # risers
            tr = T(B * 2); add((Rn.normal(0, 1, len(tr)) * 0.2 + np.sin(2 * np.pi * np.cumsum(250 + 2600 * (tr / tr[-1]) ** 2) / sr) * 0.12) * (tr / tr[-1]) ** 2, t1 - B * 2)
    tb2 = T(1.0); boom = np.sin(2 * np.pi * (38 + 60 * np.exp(-tb2 * 10)) * tb2) * np.exp(-tb2 * 4)
    for t0, s in [(T2, 0.6), (T4, 1.0), (T5, 0.5), (T6, 0.6), (T7, 0.5), (T8, 0.9)]:
        add((boom + Rn.normal(0, 1, len(tb2)) * np.exp(-tb2 * 16) * 0.35) * 0.5 * s, t0)
    ti = T(0.12)
    for h in HITS: add((np.sin(2 * np.pi * 110 * ti) * np.exp(-ti * 30) + Rn.normal(0, 1, len(ti)) * np.exp(-ti * 60) * 0.5) * 0.22, h)
    tw = T(0.28)
    for t0 in (T2 - 0.1, T5 - 0.1, T6 - 0.1, T7 - 0.1):
        add(np.convolve(Rn.normal(0, 1, len(tw)), np.ones(5) / 5, "same") * np.sin(np.pi * tw / 0.28) ** 2 * 0.28, t0)
    tc = T(0.02)
    for j in range(14): add(np.sin(2 * np.pi * 1500 * tc) * np.exp(-tc * 200) * 0.2, beat(7) + j * B / 14)   # counter ticks
    tz = T(0.2); add(np.sign(np.sin(2 * np.pi * 900 * tz)) * (np.sin(2 * np.pi * 30 * tz) > 0) * 0.1, T3)
    fo = int(0.3 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.35) * 0.88
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

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
    p.stdin.close(); p.wait(); os.remove(wav)
    wav2 = OUT.replace(".mp4", "_sfx.wav"); make_audio(wav2, music=False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", OUT, "-i", wav2, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", OUT.replace(".mp4", "_sans_musique.mp4")], check=True)
    os.remove(wav2); print("OK ->", OUT)
