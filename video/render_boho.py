"""Vidéo événement BOHO Club Rouen : on plonge dans la soirée « La Shattouille » du vendredi 23 octobre.
Programme de la semaine en 3D -> zoom dans la bannière du vendredi -> images d'ambiance -> affiche animée -> infos.
Rendu :   python3 render_boho.py          -> promo_boho_shattouille.mp4 (+ _sans_musique.mp4)  1080x1920 60 i/s
Aperçu :  python3 render_boho.py 2 8      -> preview_2.png ..."""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 60, 15.6
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_boho_shattouille.mp4")
AS = os.path.join(HERE, "assets_boho"); CACHE = os.path.join(HERE, "_cache", "boho")
ORANGE = (255, 120, 20); AMBER = (255, 170, 60); WHITE = (255, 255, 255); GREY = (170, 160, 155)
FD = "/usr/share/fonts/opentype/inter/"
FW = {"bi": FD + "InterDisplay-BlackItalic.otf", "black": FD + "Inter-Black.otf", "xb": FD + "Inter-ExtraBold.otf",
      "b": FD + "Inter-Bold.otf", "sb": FD + "Inter-SemiBold.otf", "m": FD + "Inter-Medium.otf"}
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

def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def warp_clip(L, img, pts, a=1.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
    x1, y1 = min(L.width, math.ceil(max(xs))), min(L.height, math.ceil(max(ys)))
    if x1 - x0 < 2 or y1 - y0 < 2: return
    try: co = persp_coeffs([(px - x0, py - y0) for px, py in pts], [(0, 0), (img.width, 0), (img.width, img.height), (0, img.height)])
    except np.linalg.LinAlgError: return
    L.alpha_composite(fade(img.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, co, Image.BICUBIC), a), (x0, y0))

def rotm(rx=0.0, ry=0.0, rz=0.0):
    ax, ay, az = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz

F = 1600.0
def project(P): return [(W / 2 + F * p[0] / p[2], H / 2 + F * p[1] / p[2]) for p in P]

def premul(D):
    a = np.asarray(D, np.float32); a[..., :3] *= a[..., 3:4] / 255; return a
def unpremul(a):
    al = a[..., 3:4]; rgb = np.where(al > 0, a[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.concatenate([rgb, al], axis=2).clip(0, 255).astype(np.uint8), "RGBA")

def sparkle(d, cx, cy, s, col, a=255):
    if s < 1: return
    pts = [(cx + math.cos(math.pi / 4 * k - math.pi / 2) * (s if k % 2 == 0 else s * 0.2),
            cy + math.sin(math.pi / 4 * k - math.pi / 2) * (s if k % 2 == 0 else s * 0.2)) for k in range(8)]
    d.polygon(pts, fill=col + (int(a),))

def text_img(s, f, col, glow=None, spacing=0, stroke=0):
    l, t, r, b = f.getbbox(s); w = int(r - l + spacing * len(s) + 80); h = int(b - t + 80)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if spacing:
        x = 40
        for ch in s: d.text((x - l, 40 - t), ch, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0)); x += f.getlength(ch) + spacing
    else: d.text((40 - l, 40 - t), s, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0))
    if glow:
        g = Image.new("RGBA", im.size, glow + (0,)); g.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(18)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(g); out.alpha_composite(g); out.alpha_composite(im); return out
    return im

@lru_cache(None)
def T(s, f, col=WHITE, glow=None, spacing=0, stroke=0): return text_img(s, f, col, glow, spacing, stroke)

def put2d(L, im, cx, cy, s=1.0, a=1.0, rot=0.0):
    if s <= 0.01 or a <= 0.01: return
    if s != 1: im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    safe_comp(L, fade(im, a), cx - im.width / 2, cy - im.height / 2)

# ------------------------------------------------------------------ assets
BANNERS = [(95, 203, 1078, 440), (97, 467, 1082, 703), (99, 720, 1082, 956), (101, 988, 1085, 1224)]
@lru_cache(None)
def programme():
    im = Image.open(os.path.join(AS, "programme.jpg")).convert("RGBA"); d = ImageDraw.Draw(im)
    for cx, cy, r in [(1112, 80, 62), (80, 1425, 52)]:   # hide screenshot UI (carousel counter, profile icon)
        patch = im.crop((cx - r - 60, cy - r - 60, cx - r - 10, cy + r + 60)).resize((2 * r + 20, 2 * r + 20)).filter(ImageFilter.GaussianBlur(6))
        m = Image.new("L", patch.size, 0); ImageDraw.Draw(m).ellipse([0, 0, patch.width - 1, patch.height - 1], fill=255)
        im.paste(patch, (cx - r - 10, cy - r - 10), m.filter(ImageFilter.GaussianBlur(4)))
    return im

@lru_cache(None)
def banner(i): return programme().crop(BANNERS[i])

@lru_cache(None)
def poster(): return Image.open(os.path.join(AS, "shattouille.jpg")).convert("RGBA")

@lru_cache(None)
def boho_logo():
    im = programme().crop((430, 1245, 800, 1410)).convert("RGB"); a = np.asarray(im, np.float32)
    lum = a.mean(axis=2); alpha = np.clip((lum - 70) * 2.2, 0, 255).astype(np.uint8)
    out = Image.new("RGBA", im.size, (255, 255, 255, 0)); out.putalpha(Image.fromarray(alpha)); return out

@lru_cache(maxsize=6)
def footage(i):
    n = len(os.listdir(CACHE)); return Image.open(os.path.join(CACHE, f"f_{int(clamp(i, 0, n - 1)) + 1:04d}.jpg")).convert("RGBA")

# ------------------------------------------------------------------ background (black glitter + orange smoke)
BG = {}
def background(t, warm=0.0):
    if not BG:
        r = np.random.default_rng(3); arr = np.zeros((H, W, 3), np.float32) + 6
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        wave_ = np.exp(-((yy - H * 0.5 - 260 * np.sin(xx / 260)) / 220) ** 2)   # satin sheen
        arr += wave_[..., None] * np.array([28, 24, 26])
        BG["base"] = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
        BG["glit"] = [(r.uniform(0, W), r.uniform(0, H), r.uniform(1.5, 4), r.uniform(0, 6.3)) for _ in range(260)]
        BG["smoke"] = [Image.fromarray(r.normal(128, 60, (24, 14)).clip(0, 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BICUBIC) for _ in range(2)]
    im = BG["base"].copy(); d = ImageDraw.Draw(im)
    for x, y, s, ph in BG["glit"]:
        a = 110 + 145 * max(0, math.sin(t * 3 + ph * 5))
        c = mix((200, 200, 220), AMBER, (ph % 1) * 0.6 + warm * 0.4)
        if s > 3.3: sparkle(d, x, y, s * 2.2, c, a)
        else: d.ellipse([x - s / 2, y - s / 2, x + s / 2, y + s / 2], fill=c + (int(a),))
    if warm > 0.01:
        sm = BG["smoke"][0]; off = int(t * 12) % (W // 4)
        s2 = Image.new("L", sm.size); s2.paste(sm, (off, 0)); s2.paste(sm, (off - sm.width, 0))
        g = np.asarray(s2, np.float32) / 255; yy = np.linspace(0, 1, sm.height)[:, None]
        g = np.clip((g - 0.45) * 2.2, 0, 1) * (0.3 + 0.7 * yy) * warm
        lay = Image.new("RGBA", sm.size, ORANGE + (0,)); lay.putalpha(Image.fromarray((g * 120).astype(np.uint8)))
        im.alpha_composite(lay.resize((W, H), Image.BILINEAR))
    return im

# ------------------------------------------------------------------ scene A : programme in 3D, dive into Friday
PCX, PCY = 603, 750
KEYS = [(0.0, 603, 750, 3300, 26, -32, -9), (0.95, 603, 760, 2200, 8, -10, -3), (1.75, 603, 760, 2120, 4, 9, 2),
        (2.45, 590, 838, 1550, 7, -11, -3), (2.75, 600, 838, 1450, 5, -7, -2), (3.38, 640, 838, 190, 0, 0, 0)]
def poseA(t):
    k = KEYS[0]
    for a, b in zip(KEYS, KEYS[1:]):
        if a[0] <= t <= b[0]:
            x = (t - a[0]) / (b[0] - a[0]); e = in_cubic(x) if b is KEYS[-1] else in_out(x)
            k = [lerp(p, q, e) for p, q in zip(a, b)]; break
    else:
        if t > KEYS[-1][0]: k = KEYS[-1]
    _, fx, fy, z, rx, ry, rz = k
    rx += 0.4 * math.sin(t * 6.3); ry += 0.4 * math.sin(t * 5.1 + 1)
    M = rotm(rx, ry, rz); C = np.array([0, 0, z]) - M @ np.array([fx - PCX, fy - PCY, 0])
    return C, M

def quad_pts(C, M, box, dz=0.0):
    x0, y0, x1, y1 = box
    loc = np.array([[x0 - PCX, y0 - PCY, dz], [x1 - PCX, y0 - PCY, dz], [x1 - PCX, y1 - PCY, dz], [x0 - PCX, y1 - PCY, dz]], float)
    P = loc @ M.T + C
    return None if P[:, 2].min() < 40 else project(P)

@lru_cache(None)
def shadow_img(w, h):
    im = Image.new("RGBA", (w + 120, h + 120), (0, 0, 0, 0)); ImageDraw.Draw(im).rectangle([60, 60, w + 60, h + 60], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(22))

@lru_cache(None)
def glow_frame(w, h):
    im = Image.new("RGBA", (w + 160, h + 160), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([80, 80, w + 80, h + 80], outline=ORANGE + (255,), width=14); g = im.filter(ImageFilter.GaussianBlur(26))
    g.alpha_composite(g); ImageDraw.Draw(g).rectangle([80, 80, w + 80, h + 80], outline=(255, 210, 150, 255), width=5); return g

@lru_cache(None)
def dark_img(w, h, a): return Image.new("RGBA", (w, h), (0, 0, 0, a))

def lift(t, i):
    up = out_back(prog(t, 0.35 + 0.22 * i, 0.85 + 0.22 * i), 2.2)
    if i == 2: return up + 0.9 * out_back(prog(t, 1.85, 2.3))
    return up * (1 - smooth(prog(t, 1.85, 2.25)))

def draw_programme(L, t):
    C, M = poseA(t)
    pts = quad_pts(C, M, (0, 0, 1206, 1499))
    if pts: warp_clip(L, programme(), pts)
    dim = smooth(prog(t, 1.85, 2.3))
    for i, box in enumerate(BANNERS):
        lv = lift(t, i); x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
        if lv > 0.01:
            sp = quad_pts(C, M, (x0 - 60 + 18 * lv, y0 - 60 + 30 * lv, x1 + 60 + 18 * lv, y1 + 60 + 30 * lv))
            if sp: warp_clip(L, shadow_img(w, h), sp, clamp(lv))
        if i == 2 and dim > 0:
            gp = quad_pts(C, M, (x0 - 80, y0 - 80, x1 + 80, y1 + 80), -70 * lv)
            pulse = 0.75 + 0.25 * math.sin(t * 14)
            if gp: warp_clip(L, glow_frame(w, h), gp, dim * pulse)
        bp = quad_pts(C, M, box, -70 * lv)
        if bp:
            warp_clip(L, banner(i), bp)
            if i != 2 and dim > 0: warp_clip(L, dark_img(w, h, 255), bp, dim * 0.62)

# ------------------------------------------------------------------ scene B : footage cuts with kinetic type
SEGS = [(3.4, 4.2, 1.0), (4.2, 4.9, 2.5), (4.9, 5.5, 3.5), (5.5, 6.62, 5.6)]   # (start, end, source time)
GENRES = [(4.55, "SHATTA"), (4.9, "DANCEHALL"), (5.25, "AFRO"), (5.6, "CARIBBEAN"), (5.95, "URBAN")]
def scene_footage(L, t):
    for a, b, src in SEGS:
        if a <= t < b:
            fr = footage(int((src + (t - a)) * 30)); punch = 1 + 0.09 * math.exp(-(t - a) * 9)
            put2d(L, fr, W / 2, H / 2, punch); break
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); a = np.zeros((H, W), np.uint8)
    a[:500] = np.linspace(150, 0, 500)[:, None].astype(np.uint8); a[1300:] = np.linspace(0, 170, 620)[:, None].astype(np.uint8)
    shade.putalpha(Image.fromarray(a)); L.alpha_composite(shade)
    p = out_cubic(prog(t, 3.5, 3.8))
    if t < 4.5:
        put2d(L, T("VENDREDI", font("xb", 74), WHITE, spacing=26), W / 2, 330 - (1 - p) * 40, 1, p)
        s = out_back(prog(t, 3.68, 3.95), 2.4)
        put2d(L, T("23 OCTOBRE", font("bi", 122), ORANGE, glow=ORANGE, stroke=3), W / 2, 500, s, clamp(s * 2), -4)
    for k, (t0, g) in enumerate(GENRES):
        t1 = GENRES[k + 1][0] if k + 1 < len(GENRES) else 6.6
        if t0 <= t < t1:
            s = lerp(1.35, 1.0, out_cubic(prog(t, t0, t0 + 0.12)))
            put2d(L, T(g, font("bi", 170), WHITE, glow=ORANGE, stroke=4), W / 2, 1500, s, 1, -4)
            put2d(L, T("VENDREDI 23 OCTOBRE", font("xb", 50), AMBER, spacing=8), W / 2, 330, 1, 1)

# ------------------------------------------------------------------ scene C/D : animated poster + infos
FLARES = [(1150, 148), (818, 288), (1033, 214), (445, 238), (690, 358)]
def poster_layout(t):
    """Returns poster centre / scale on screen (in scene C then shrinking for the info card)."""
    s_in = lerp(1.35, 1.0, out_cubic(prog(t, 6.62, 7.1)))
    push = 1 + 0.06 * prog(t, 7.1, 12.6)
    out = in_out(prog(t, 12.5, 13.2))
    s = lerp(s_in * push, 0.58, out); cy = lerp(960, 600, out)
    return W / 2, cy, s

def beat_pulse(t):
    if t < 3.4: return 0
    ph = ((t - 3.4) / 0.6) % 1; return math.exp(-ph * 9)

def scene_poster(L, t):
    cx, cy, s = poster_layout(t); base = 1000 / poster().width
    sc = base * s * (1 + 0.012 * beat_pulse(t)); im = poster()
    pw, ph = im.width * sc, im.height * sc
    ry = 4 * math.sin(t * 0.7); rx = 2.5 * math.sin(t * 0.55)
    # perspective card
    M = rotm(rx, ry, 0); z = 1600; hw, hh = pw / 2, ph / 2
    P = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]], float) @ M.T + np.array([cx - W / 2, cy - H / 2, z])
    pts = project(P)
    g = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0)); ImageDraw.Draw(g).polygon([(x / 4, y / 4) for x, y in pts], fill=ORANGE + (130,))
    L.alpha_composite(g.filter(ImageFilter.GaussianBlur(18)).resize((W, H), Image.BILINEAR))
    warp_clip(L, im, pts)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for k, (fx, fy) in enumerate(FLARES):   # twinkling stage lights
        u, v = fx / im.width, fy / im.height
        x = lerp(lerp(pts[0][0], pts[1][0], u), lerp(pts[3][0], pts[2][0], u), v); y = lerp(lerp(pts[0][1], pts[3][1], v), lerp(pts[1][1], pts[2][1], v), u)
        a = 0.5 + 0.5 * math.sin(t * 5 + k * 1.9); r = (40 + 40 * a) * s
        d.ellipse([x - r, y - r, x + r, y + r], fill=AMBER + (int(70 * a),)); sparkle(d, x, y, (60 + 50 * a) * s, (255, 235, 200), 230 * a)
    for k in range(3):   # sweeping light beams
        ang = math.radians(90 + 32 * math.sin(t * 0.9 + k * 2.1)); ox = W * (0.2 + 0.3 * k)
        ex, ey = ox + math.cos(ang) * 2200, -40 + math.sin(ang) * 2200; nx, ny = -math.sin(ang) * 120, math.cos(ang) * 120
        d.polygon([(ox, -40), (ex + nx, ey + ny), (ex - nx, ey - ny)], fill=(255, 150, 60, 22))
    L.alpha_composite(lay.filter(ImageFilter.GaussianBlur(3)))
    if t < 12.6:
        a = out_cubic(prog(t, 7.0, 7.4)) * (1 - smooth(prog(t, 12.3, 12.6)))
        put2d(L, T("VENDREDI 23 OCTOBRE", font("xb", 58), WHITE, spacing=10), W / 2, 205, 1, a)
        put2d(L, T("BOHO CLUB · ROUEN", font("sb", 40), AMBER, spacing=8), W / 2, 275, 1, a)
        for k, (t0, txt) in enumerate([(8.0, "ENTRÉE GRATUITE POUR LES FILLES AVANT 1H"), (10.0, "UN VERRE OFFERT POUR LES FILLES AVANT 1H")]):
            p = out_back(prog(t, t0, t0 + 0.35)) * (1 - smooth(prog(t, t0 + 1.8, t0 + 2.0) if k == 0 else prog(t, 12.3, 12.6)))
            if p > 0.02:
                tx = T(txt, font("bi", 44), WHITE); pill = Image.new("RGBA", (tx.width + 40, 120), (0, 0, 0, 0))
                ImageDraw.Draw(pill).rounded_rectangle([0, 0, pill.width - 1, 119], 60, fill=ORANGE + (255,))
                pill.alpha_composite(tx, (20, 60 - tx.height // 2)); put2d(L, pill, W / 2, 1700, p * 0.98, clamp(p), -2)

def scene_info(L, t):
    a = lambda t0: out_cubic(prog(t, t0, t0 + 0.4))
    put2d(L, boho_logo(), W / 2, 1100 + (1 - a(13.0)) * 40, 1.3, a(13.0))
    put2d(L, T("INFO / VIP", font("xb", 52), AMBER, spacing=10), W / 2, 1290, 1, a(13.25))
    put2d(L, T("06.67.56.82.54 OU MP", font("black", 84), WHITE, glow=ORANGE), W / 2, 1385, 1, a(13.4))
    put2d(L, T("26 rue Saint-Étienne-des-Tonneliers, 76000 Rouen", font("m", 38), GREY), W / 2, 1500, 1, a(13.6))
    put2d(L, T("Tenue correcte exigée · Interdit aux mineurs", font("m", 34), GREY), W / 2, 1560, 1, a(13.75))
    put2d(L, T("@bohorouen", font("xb", 58), ORANGE, glow=ORANGE), W / 2, 1680, 1, a(13.9))

# ------------------------------------------------------------------ embers (front particles)
R = np.random.default_rng(8)
EMB = [(R.uniform(0, W), R.uniform(0, H), R.uniform(40, 140), R.uniform(2, 6), R.uniform(0, 6.3)) for _ in range(90)]
def embers(L, t, amt):
    if amt <= 0.01: return
    d = ImageDraw.Draw(L)
    for x, y, sp, s, ph in EMB:
        yy = (y - t * sp * 2) % H; xx = x + 30 * math.sin(t * 1.3 + ph)
        a = amt * (0.5 + 0.5 * math.sin(t * 6 + ph * 3)) * 255
        d.ellipse([xx - s, yy - s, xx + s, yy + s], fill=mix(ORANGE, (255, 220, 150), (ph % 1)) + (int(a),))

# ------------------------------------------------------------------ compose / post
def scene_at(t):
    if t < 3.4:
        img = background(t, 0.0)
        v = 0 if t < 2.85 else in_cubic(prog(t, 2.85, 3.38))
        if v > 0.05:   # sub-frame motion blur on the dive
            acc = None; n = 6
            for k in range(n):
                D = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_programme(D, t + (k / (n - 1) - 0.5) * 0.75 / FPS)
                pm = premul(D); acc = pm if acc is None else acc + pm
            img.alpha_composite(unpremul(acc / n))
        else: draw_programme(img, t)
        return img
    if t < 6.62:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255)); scene_footage(img, t); embers(img, t, 0.6); return img
    img = background(t, 1.0); scene_poster(img, t); embers(img, t, 1.0)
    if t >= 12.9: scene_info(img, t)
    return img

VIG = None
def post(img, t, fi):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
        VIG = (1 - 0.55 * np.clip(r - 0.35, 0, 1) ** 1.4)[..., None].astype(np.float32)
    zb = in_cubic(prog(t, 2.95, 3.38)) if t < 3.4 else 0
    if zb > 0.05:   # zoom blur into the banner
        acc = img
        for k in range(1, 6):
            s = 1 + 0.035 * k * zb; z = img.resize((int(W * s), int(H * s)), Image.BILINEAR)
            z = z.crop(((z.width - W) // 2, (z.height - H) // 2, (z.width - W) // 2 + W, (z.height - H) // 2 + H))
            acc = Image.blend(acc, z, 1 / (k + 1))
        img = acc
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 150, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR), np.float32) * 0.8
    ca = int(8 * math.exp(-max(0, t - 3.4) * 8)) if t >= 3.4 else 0
    for t0, _ in GENRES: ca += int(6 * math.exp(-(t - t0) * 12)) if t >= t0 else 0
    if ca > 0: arr[..., 0] = np.roll(arr[..., 0], ca, axis=1); arr[..., 2] = np.roll(arr[..., 2], -ca, axis=1)
    fl = 0.0
    for t0, s in [(3.36, 1.0), (4.2, 0.35), (4.9, 0.35), (5.5, 0.35), (6.62, 0.8)]:
        if t >= t0 - 0.04: fl += s * math.exp(-max(0, t - t0) * 9)
    arr = arr + (np.array([255, 190, 120], np.float32) - arr) * min(fl, 0.9)
    arr = arr * VIG + np.random.default_rng(fi).normal(0, 3, (H, W, 1)).astype(np.float32)
    arr *= 1 - smooth(prog(t, 15.25, 15.6))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(scene_at(t), t, i).tobytes()

# ------------------------------------------------------------------ audio : dembow / shatta beat + sound design
def make_audio(path, music=True):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(2)
    def add(sig, t0):
        i = int(t0 * sr)
        if 0 <= i < n: j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def Tm(d): return np.arange(int(d * sr)) / sr
    beat = 0.6
    tk = Tm(0.4); kick = np.sin(2 * np.pi * (48 + 110 * np.exp(-tk * 26)) * tk) * np.exp(-tk * 7)
    ts = Tm(0.16); snare = (Rn.uniform(-1, 1, len(ts)) * 0.7 + np.sin(2 * np.pi * 240 * ts) * 0.5) * np.exp(-ts * 26) * 0.42
    th = Tm(0.03); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 130) * 0.1
    def horn(t0, f0=466.2):
        for k in range(4):
            tt = Tm(0.16 if k < 3 else 0.5); f = f0 * (1 - 0.06 * tt / tt[-1])
            saw = sum(np.sin(2 * np.pi * f * h * tt) / h for h in range(1, 9)) * 0.12
            saw2 = sum(np.sin(2 * np.pi * f * 1.5 * h * tt) / h for h in range(1, 6)) * 0.06
            add((saw + saw2) * np.minimum(1, tt / 0.01) * np.exp(-tt * (2 if k == 3 else 6)), t0 + k * 0.17)
    if music:
        tp = Tm(3.4); pad = sum(np.sin(2 * np.pi * f * tp) for f in (138.6, 207.7, 277.2)) * 0.035 * np.minimum(1, tp / 0.8)
        add(pad, 0.0)
        for k in range(8): add(hat * (0.4 + k * 0.08), 0.3 * k + 0.9)
        tr = Tm(1.0); add((Rn.normal(0, 1, len(tr)) * 0.25 + np.sin(2 * np.pi * np.cumsum(200 + 1800 * tr ** 2) / sr) * 0.12) * tr ** 2, 2.38)
        bass_notes = [69.3, 69.3, 82.4, 61.7]
        k = 0
        while 3.4 + k * beat < 15.2:
            t0 = 3.4 + k * beat; bar = (k // 4) % 4
            add(kick * 0.9, t0)
            for off in (0.75, 1.5):
                if (k % 2 == 0 and off == 0.75) or (k % 2 == 1 and off == 1.5 - 1): add(snare, t0 + off * beat)
            if k % 2 == 1: add(snare, t0 + 0.5 * beat)
            for h in range(4): add(hat * (1 if h % 2 else 0.6), t0 + h * beat / 4)
            tb = Tm(beat); add(np.sin(2 * np.pi * bass_notes[bar] * tb) * np.exp(-tb * 3) * 0.32, t0)
            if k % 8 == 0:
                tch = Tm(beat * 4); env = np.exp(-tch * 1.3)
                add(sum(np.sign(np.sin(2 * np.pi * f * tch)) for f in (277.2, 329.6, 415.3)) * 0.018 * env, t0)
            k += 1
        horn(3.36); horn(6.6, 554.4); horn(12.9)
    tb2 = Tm(1.4); boom = np.sin(2 * np.pi * (36 + 60 * np.exp(-tb2 * 9)) * tb2) * np.exp(-tb2 * 3)
    for t0, s in [(3.38, 1.0), (6.62, 0.8), (13.0, 0.5)]: add((boom + Rn.normal(0, 1, len(tb2)) * np.exp(-tb2 * 14) * 0.3) * 0.55 * s, t0)
    tw = Tm(0.3)
    for i in range(4): add(np.convolve(Rn.normal(0, 1, len(tw)), np.ones(6) / 6, "same") * np.sin(np.pi * tw / 0.3) ** 2 * 0.2, 0.3 + 0.22 * i)
    for t0 in (1.85, 12.5): add(np.convolve(Rn.normal(0, 1, len(tw)), np.ones(6) / 6, "same") * np.sin(np.pi * tw / 0.3) ** 2 * 0.25, t0)
    ti = Tm(0.25)
    for t0, _ in GENRES: add((np.sin(2 * np.pi * 90 * ti) * np.exp(-ti * 14) + Rn.normal(0, 1, len(ti)) * np.exp(-ti * 30) * 0.4) * 0.35, t0)
    for t0 in (8.0, 10.0): add(np.sin(2 * np.pi * np.cumsum(600 + 1200 * ti / 0.25) / sr) * np.exp(-ti * 12) * 0.2, t0)
    fo = int(0.5 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.3) * 0.88
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

def prepare():
    if os.path.exists(os.path.join(CACHE, "f_0001.jpg")): return
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(AS, "ambiance.mov"), "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.12:saturation=1.15,"
                    "colorbalance=rs=0.14:gs=-0.02:bs=-0.16:rm=0.08:bm=-0.08", "-q:v", "3", os.path.join(CACHE, "f_%04d.jpg")], check=True)

if __name__ == "__main__":
    prepare()
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            t = float(s); post(scene_at(t), t, int(t * FPS)).save(f"preview_{s}.png")
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
