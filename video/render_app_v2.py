"""Motion design style "démo d'appli" v2 (60 i/s, téléphone réaliste, vrai flou de mouvement, profondeur de champ).
Caméra 3D en gros plan sur un téléphone, navigation dans une appli sociale générique :
logo -> fil d'actu -> recherche -> Reel (vidéo v7) -> profil -> commentaire "SALLE" -> notif DM -> logo néon.
Rendu :   python3 render_app_v2.py          -> promo_app_365_v2.mp4 (+ promo_app_365_v2_sans_musique.mp4)
Aperçu :  python3 render_app_v2.py 3 7.5    -> preview_3.png, preview_7.5.png"""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 60, 25.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_app_365_v2.mp4")
CACHE = os.path.join(HERE, "_cache")
V7 = os.path.join(HERE, "promo_abonnement_v7.mp4")
NAME = "365daymentality"

WHITE = (250, 250, 250); GREY = (150, 150, 160); DGREY = (38, 38, 42); BLACK = (0, 0, 0)
ACC = (255, 122, 0); PINK = (255, 50, 130); RED = (255, 48, 64)
FONTS = "/usr/share/fonts/opentype/inter/"
FW = {"black": "Inter-Black.otf", "xb": "Inter-ExtraBold.otf", "b": "Inter-Bold.otf", "sb": "Inter-SemiBold.otf", "m": "Inter-Medium.otf"}

@lru_cache(None)
def font(w, s): return ImageFont.truetype(FONTS + FW[w], s)

# ------------------------------------------------------------------ easing / utils
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
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, L.width - x), min(im.height, L.height - y)
    if ex <= sx or ey <= sy: return
    L.alpha_composite(im, (x + sx, y + sy), (sx, sy, ex, ey))

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
    """Perspective-warp img onto quad pts, only computing the visible part of the canvas."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
    x1, y1 = min(L.width, math.ceil(max(xs))), min(L.height, math.ceil(max(ys)))
    if x1 - x0 < 2 or y1 - y0 < 2: return
    try: co = persp_coeffs([(px - x0, py - y0) for px, py in pts], [(0, 0), (img.width, 0), (img.width, img.height), (0, img.height)])
    except np.linalg.LinAlgError: return
    im = img.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, co, Image.BICUBIC)
    L.alpha_composite(fade(im, a), (x0, y0))

def rotm(rx=0.0, ry=0.0, rz=0.0):
    ax, ay, az = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz

F = 1600.0
def project(P): return [(W / 2 + F * p[0] / p[2], H / 2 + F * p[1] / p[2]) for p in P]
def area(pts): return sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))

# ------------------------------------------------------------------ assets
def prepare_assets():
    if os.path.exists(os.path.join(CACHE, "thumb_5.jpg")): return
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", "4.3", "-i", V7, "-vf", "scale=-2:2200,crop=1040:2200,fps=30",
                    "-q:v", "3", os.path.join(CACHE, "reel_%04d.jpg")], check=True)
    for i, t in enumerate([1.2, 4.6, 8.5, 12.9, 15.6, 17.9]):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", V7, "-frames:v", "1", "-vf",
                        "crop=1080:1440:0:240,scale=346:460", "-q:v", "2", os.path.join(CACHE, f"thumb_{i}.jpg")], check=True)

@lru_cache(None)
def thumb(i): return Image.open(os.path.join(CACHE, f"thumb_{i}.jpg")).convert("RGBA")

@lru_cache(maxsize=8)
def reel_frame(i):
    n = len([f for f in os.listdir(CACHE) if f.startswith("reel_")])
    return Image.open(os.path.join(CACHE, f"reel_{clamp(i, 0, n - 1) + 1:04d}.jpg")).convert("RGBA")

def grad(w, h, c1, c2, diag=True):
    if diag:
        y, x = np.mgrid[0:h, 0:w]; k = ((x / w + y / h) / 2)[..., None]
    else:
        k = np.linspace(0, 1, h)[:, None, None] * np.ones((1, w, 1))
    arr = np.array(c1) * (1 - k) + np.array(c2) * k
    return Image.fromarray(arr.astype(np.uint8)).convert("RGBA")

@lru_cache(None)
def logo(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], int(size * 0.24), fill=255)
    im.paste(grad(size, size, (255, 170, 0), PINK), (0, 0), m); d = ImageDraw.Draw(im)
    d.text((size / 2, size * 0.46), "365", font=font("black", int(size * 0.36)), fill=WHITE, anchor="mm")
    d.text((size / 2, size * 0.74), "DAY MENTALITY", font=font("xb", max(8, int(size * 0.075))), fill=(255, 255, 255, 230), anchor="mm")
    return im

@lru_cache(None)
def avatar(d, ring=True):
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    if ring:
        rg = grad(d, d, (255, 190, 0), PINK); m = Image.new("L", (d, d), 0); ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
        im.paste(rg, (0, 0), m); dr.ellipse([d * 0.06, d * 0.06, d * 0.94, d * 0.94], fill=BLACK)
    inner = int(d * 0.8) if ring else d
    lg = logo(inner); m = Image.new("L", (inner, inner), 0); ImageDraw.Draw(m).ellipse([0, 0, inner - 1, inner - 1], fill=255)
    im.paste(lg, ((d - inner) // 2, (d - inner) // 2), m)
    return im

TIPS = [((80, 40, 200), (20, 90, 255), ["3 ABONNEMENTS", "À RÉSILIER", "AUJOURD'HUI"], "Tu les paies pour rien"),
        ((18, 18, 24), (60, 30, 10), ["TA SALLE", "À 20 €/MOIS"], "au lieu de 34 €  ·  commente SALLE"),
        ((0, 120, 110), (20, 170, 80), ["COURSES :", "5 ASTUCES", "POUR PAYER MOINS"], "Le n°3 va te choquer"),
        ((255, 60, 120), (255, 150, 0), ["GAGNE 1 H", "PAR JOUR"], "avec ces 4 applis gratuites")]

@lru_cache(None)
def tip_card(i, size=1040):
    c1, c2, lines, sub = TIPS[i]; im = grad(size, size, c1, c2); d = ImageDraw.Draw(im)
    if i == 1:
        gl = Image.new("RGBA", (size, size), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse([size * 0.1, size * 0.1, size * 0.9, size * 0.9], fill=ACC + (90,))
        im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(size // 8)))
    k = size / 1040; y = size * 0.5 - len(lines) * 70 * k - 30 * k
    for j, s in enumerate(lines):
        f = font("black", int(100 * k))
        col = ACC if (i == 1 and j == 1) else WHITE
        d.text((size / 2 + 5 * k, y + 6 * k), s, font=f, fill=(0, 0, 0, 90), anchor="mt"); d.text((size / 2, y), s, font=f, fill=col, anchor="mt")
        y += 140 * k
    d.text((size / 2, y + 30 * k), sub, font=font("sb", int(44 * k)), fill=(255, 255, 255, 230), anchor="mt")
    d.text((size / 2, size - 70 * k), "365 DAY MENTALITY", font=font("xb", int(30 * k)), fill=(255, 255, 255, 170), anchor="mm")
    return im

# ------------------------------------------------------------------ icons
def heart_pts(cx, cy, s):
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        x = 16 * math.sin(a) ** 3; y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * s / 32, cy + y * s / 32))
    return pts

def ic_heart(d, cx, cy, s, filled=False, col=WHITE):
    p = heart_pts(cx, cy, s)
    if filled: d.polygon(p, fill=RED)
    else: d.line(p + [p[0]], fill=col, width=max(3, int(s / 12)), joint="curve")

def ic_comment(d, cx, cy, s, col=WHITE):
    r = s / 2; w = max(3, int(s / 12))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)
    d.line([(cx - r * 0.75, cy + r * 0.65), (cx - r * 0.95, cy + r * 1.05), (cx - r * 0.3, cy + r * 0.92)], fill=col, width=w)

def ic_share(d, cx, cy, s, col=WHITE):
    r = s / 2; w = max(3, int(s / 12))
    p = [(cx - r, cy - r * 0.8), (cx + r, cy - r), (cx - r * 0.1, cy + r), (cx - r * 0.25, cy - r * 0.1)]
    d.line(p + [p[0]], fill=col, width=w, joint="curve"); d.line([(cx - r * 0.25, cy - r * 0.1), (cx + r, cy - r)], fill=col, width=w)

def ic_save(d, cx, cy, s, col=WHITE):
    r = s / 2; w = max(3, int(s / 12))
    p = [(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.7, cy + r), (cx, cy + r * 0.45), (cx - r * 0.7, cy + r)]
    d.line(p + [p[0]], fill=col, width=w, joint="curve")

def ic_search(d, cx, cy, s, col=WHITE, w=None):
    r = s * 0.36; w = w or max(3, int(s / 11))
    d.ellipse([cx - r - s * 0.08, cy - r - s * 0.08, cx + r - s * 0.08, cy + r - s * 0.08], outline=col, width=w)
    d.line([(cx + r * 0.55, cy + r * 0.55), (cx + s * 0.48, cy + s * 0.48)], fill=col, width=w)

def ic_home(d, cx, cy, s, col=WHITE, filled=True):
    r = s / 2; p = [(cx - r, cy - r * 0.1), (cx, cy - r), (cx + r, cy - r * 0.1), (cx + r * 0.8, cy - r * 0.1), (cx + r * 0.8, cy + r),
                    (cx - r * 0.8, cy + r), (cx - r * 0.8, cy - r * 0.1)]
    if filled: d.polygon(p, fill=col)
    else: d.line(p + [p[0]], fill=col, width=max(3, int(s / 12)))

def ic_plus(d, cx, cy, s, col=WHITE):
    r = s / 2; w = max(3, int(s / 12))
    d.rounded_rectangle([cx - r, cy - r, cx + r, cy + r], s * 0.25, outline=col, width=w)
    d.line([(cx - r * 0.45, cy), (cx + r * 0.45, cy)], fill=col, width=w); d.line([(cx, cy - r * 0.45), (cx, cy + r * 0.45)], fill=col, width=w)

def ic_reels(d, cx, cy, s, col=WHITE):
    r = s / 2; w = max(3, int(s / 12))
    d.rounded_rectangle([cx - r, cy - r, cx + r, cy + r], s * 0.25, outline=col, width=w)
    d.polygon([(cx - r * 0.25, cy - r * 0.3), (cx + r * 0.4, cy + r * 0.1), (cx - r * 0.25, cy + r * 0.5)], fill=col)
    d.line([(cx - r, cy - r * 0.45), (cx + r, cy - r * 0.45)], fill=col, width=w)

def status_bar(d, col=WHITE):
    d.text((90, 56), "9:41", font=font("sb", 54), fill=col)
    for k in range(4): d.rounded_rectangle([760 + k * 22, 96 - k * 12, 774 + k * 22, 104], 3, fill=col)
    d.arc([860, 54, 920, 114], 225, 315, fill=col, width=9); d.ellipse([884, 92, 896, 104], fill=col)
    d.rounded_rectangle([935, 62, 1010, 102], 12, outline=col, width=4); d.rounded_rectangle([943, 70, 990, 94], 6, fill=col)

def nav_bar(S, active=0):
    d = ImageDraw.Draw(S); d.rectangle([0, 2040, 1040, 2200], fill=BLACK); d.line([(0, 2040), (1040, 2040)], fill=(40, 40, 44), width=2)
    xs = [104, 312, 520, 728, 936]; y = 2105
    ic_home(d, xs[0], y, 62, filled=(active == 0)); ic_search(d, xs[1], y, 66, w=10 if active == 1 else 6); ic_plus(d, xs[2], y, 62)
    ic_reels(d, xs[3], y, 62); S.alpha_composite(avatar(70, False), (xs[4] - 35, y - 35))
    d.rounded_rectangle([370, 2172, 670, 2182], 5, fill=WHITE)

def tap(S, x, y, t, t0, dur=0.35):
    p = prog(t, t0 - 0.08, t0 + dur)
    if 0 < p < 1:
        lay = Image.new("RGBA", S.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        r = lerp(30, 110, out_cubic(p)); a = int(170 * (1 - p))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, a // 2), outline=(255, 255, 255, a), width=5)
        S.alpha_composite(lay)

def heart_pop(S, cx, cy, t, t0):
    p = prog(t, t0, t0 + 0.75)
    if 0 < p < 1:
        lay = Image.new("RGBA", S.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        sc = out_back(prog(t, t0, t0 + 0.28), 2.5) * (1 + 0.15 * smooth(prog(t, t0 + 0.45, t0 + 0.75)))
        a = int(255 * (1 - smooth(prog(t, t0 + 0.45, t0 + 0.75))))
        if sc > 0.02: d.polygon(heart_pts(cx, cy, 360 * sc), fill=(255, 255, 255, a))
        for k in range(10):
            ang = 2 * math.pi * k / 10 + 0.3; rr = 120 + 360 * out_cubic(p)
            d.polygon(heart_pts(cx + math.cos(ang) * rr, cy + math.sin(ang) * rr, 60 * (1 - p)), fill=mix(PINK, RED, k / 10) + (int(255 * (1 - p)),))
        S.alpha_composite(lay)

# ------------------------------------------------------------------ app screens (1040 x 2200)
SW, SH = 1040, 2200

def screen_splash(t):
    S = Image.new("RGBA", (SW, SH), BLACK + (255,))
    S.alpha_composite(logo(300), (370, 950))
    return S

POST_H = 1470
POSTS = [("tip", 0), ("tip", 1), ("tip", 2), ("thumb", 3), ("tip", 3)]
def feed_scroll(t):
    return POST_H * in_out(prog(t, 3.0, 3.45)) + POST_H * 2 * in_out(prog(t, 5.0, 5.55))

def screen_feed(t):
    S = Image.new("RGBA", (SW, SH), BLACK + (255,)); d = ImageDraw.Draw(S)
    y0 = 270 - feed_scroll(t)
    for i, (kind, k) in enumerate(POSTS):
        y = y0 + i * POST_H
        if y > SH or y + POST_H < 0: continue
        S.alpha_composite(avatar(100), (40, int(y + 20)))
        d.text((160, y + 30), NAME, font=font("b", 42), fill=WHITE); d.text((160, y + 80), "Bons plans · Économies", font=font("m", 34), fill=GREY)
        d.text((960, y + 50), "•••", font=font("b", 40), fill=WHITE, anchor="mm")
        img = tip_card(k) if kind == "tip" else thumb(k).resize((1040, 1040), Image.LANCZOS)
        safe_comp(S, img, 0, y + 140)
        liked = (i == 1 and t > 4.42)
        ay = y + 1250; ic_heart(d, 75, ay, 66, liked); ic_comment(d, 185, ay, 58); ic_share(d, 290, ay, 58); ic_save(d, 975, ay, 60)
        d.text((40, y + 1320), NAME, font=font("b", 38), fill=WHITE)
        cap = ["Abonne-toi pour plus d'astuces", "Commente SALLE et je t'envoie tout", "Enregistre pour plus tard", "Nouveau Reel", "Teste et dis-moi"][i]
        d.text((40 + font("b", 38).getlength(NAME) + 16, y + 1320), cap, font=font("m", 38), fill=WHITE)
        d.text((40, y + 1380), "Voir les commentaires", font=font("m", 34), fill=GREY)
        if i == 1: heart_pop(S, 520, y + 140 + 520, t, 4.42)
    d.rectangle([0, 0, SW, 260], fill=BLACK); status_bar(d)
    ic_plus(d, 90, 200, 60); d.text((520, 200), "Pour toi", font=font("xb", 56), fill=WHITE, anchor="mm")
    d.line([(650, 190), (668, 210), (686, 190)], fill=WHITE, width=6); ic_heart(d, 955, 200, 62)
    if y0 > -POST_H: tap(S, 520, y0 + POST_H + 140 + 520, t, 4.3, 0.25); tap(S, 520, y0 + POST_H + 140 + 520, t, 4.42, 0.3)
    nav_bar(S, 0); tap(S, 312, 2105, t, 5.85)
    return S

QUERY = "salle de sport pas chère"
def screen_search(t):
    S = Image.new("RGBA", (SW, SH), BLACK + (255,)); d = ImageDraw.Draw(S); status_bar(d)
    d.rounded_rectangle([40, 160, 1000, 270], 30, fill=DGREY); ic_search(d, 105, 215, 52, GREY, 6)
    n = int(clamp((t - 6.4) * 16, 0, len(QUERY)))
    if n == 0 and t < 6.4: d.text((150, 215), "Rechercher", font=font("m", 46), fill=GREY, anchor="lm")
    txt = QUERY[:n]; d.text((150, 215), txt, font=font("m", 46), fill=WHITE, anchor="lm")
    if (t * 2.5) % 1 < 0.6 and t < 8.6:
        x = 150 + font("m", 46).getlength(txt) + 4; d.line([(x, 185), (x, 245)], fill=ACC, width=5)
    tabs = ["Pour toi", "Comptes", "Audio", "Tags", "Lieux"]; x = 50
    for i, s in enumerate(tabs):
        f = font("b" if i == 0 else "sb", 42); d.text((x, 330), s, font=f, fill=WHITE if i == 0 else GREY)
        if i == 0: d.rectangle([x, 395, x + f.getlength(s), 400], fill=WHITE)
        x += f.getlength(s) + 60
    d.line([(0, 402), (1040, 402)], fill=(40, 40, 44), width=2)
    if t < 8.75:
        if n < 4:
            d.text((50, 450), "Récent", font=font("b", 44), fill=WHITE)
            for i, s in enumerate(["yoga", "recettes rapides", "budget mois"]):
                ic_search(d, 85, 600 + i * 120, 46, GREY, 5); d.text((150, 600 + i * 120), s, font=font("m", 42), fill=WHITE, anchor="lm")
        else:
            sugg = ["salle de sport pas chère", "salle de sport 20 € par mois", "abonnement salle moins cher"]
            for i, s in enumerate(sugg):
                a = int(255 * out_cubic(prog(t, 6.65 + i * 0.12, 6.95 + i * 0.12)))
                if a <= 0: continue
                yy = 500 + i * 130
                if i == 0 and t > 8.55: d.rectangle([0, yy - 65, 1040, yy + 65], fill=(30, 30, 34))
                ic_search(d, 85, yy, 46, GREY + (a,), 5); d.text((150, yy), s, font=font("m", 44), fill=WHITE + (a,), anchor="lm")
            a = out_cubic(prog(t, 7.1, 7.4))
            if a > 0:
                yy = 900; S.alpha_composite(fade(avatar(120), a), (40, yy - 60)); d = ImageDraw.Draw(S)
                d.text((185, yy - 34), NAME, font=font("b", 44), fill=WHITE + (int(255 * a),))
                d.text((185, yy + 22), "365 Day Mentality · Bons plans", font=font("m", 36), fill=GREY + (int(255 * a),))
        tap(S, 400, 500, t, 8.6)
    else:
        imgs = [thumb(0), tip_card(1, 346).crop((0, 0, 346, 346)).resize((346, 460)), thumb(2), tip_card(0, 460).crop((57, 0, 403, 460)),
                thumb(1), thumb(4), tip_card(2, 460).crop((57, 0, 403, 460)), thumb(5), thumb(3)]
        for i, im in enumerate(imgs):
            p = out_cubic(prog(t, 8.75 + 0.04 * i, 9.05 + 0.04 * i))
            if p <= 0: continue
            cx, cy = 2 + (i % 3) * 347, 410 + (i // 3) * 462
            safe_comp(S, fade(im, p), cx, cy + (1 - p) * 60)
            if i in (0, 2, 4, 5, 7, 8): ic_reels(ImageDraw.Draw(S), cx + 300, cy + 45, 40)
        tap(S, 175, 640, t, 9.4)
    nav_bar(S, 1)
    return S

@lru_cache(None)
def reel_shade():
    a = np.zeros((SH, SW), np.uint8); a[1300:] = (np.linspace(0, 200, SH - 1300)[:, None]).astype(np.uint8)
    a[:330] = (np.linspace(120, 0, 330)[:, None]).astype(np.uint8)
    im = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); im.putalpha(Image.fromarray(a)); return im

def screen_reel(t, tr):
    S = reel_frame(int(tr * 30)).copy(); S.alpha_composite(reel_shade()); d = ImageDraw.Draw(S); status_bar(d)
    d.text((60, 185), "Reels", font=font("xb", 58), fill=WHITE, anchor="lm")
    liked = t > 12.2 and t < 17.5
    for y, fn in [(1460, lambda yy: ic_heart(d, 965, yy, 70, liked)), (1640, lambda yy: ic_comment(d, 965, yy, 62)),
                  (1810, lambda yy: ic_share(d, 965, yy, 62)), (1960, lambda yy: d.text((965, yy), "•••", font=font("b", 44), fill=WHITE, anchor="mm"))]:
        fn(y)
    S.alpha_composite(avatar(96), (50, 1752)); d = ImageDraw.Draw(S)
    d.text((165, 1800), NAME, font=font("b", 42), fill=WHITE, anchor="lm")
    x = 175 + font("b", 42).getlength(NAME) + 20
    d.rounded_rectangle([x, 1770, x + 160, 1830], 16, outline=WHITE, width=3); d.text((x + 80, 1800), "Suivre", font=font("b", 34), fill=WHITE, anchor="mm")
    d.text((50, 1880), "Tu paies encore 34 € ta salle ? Commente SALLE", font=font("m", 38), fill=WHITE)
    d.text((50, 1945), "Son original · " + NAME, font=font("m", 34), fill=(230, 230, 230))
    heart_pop(S, 520, 1000, t, 12.2); tap(S, 520, 1000, t, 12.08, 0.2); tap(S, 520, 1000, t, 12.2, 0.3)
    tap(S, 98, 1800, t, 13.45)
    nav_bar(S, 3); return S

BIO = ["Paie moins, vis mieux", "Tips pour gagner du temps & de l'argent", "Salle de sport à 20 €/mois au lieu de 34 €"]
def screen_profile(t):
    S = Image.new("RGBA", (SW, SH), BLACK + (255,)); d = ImageDraw.Draw(S)
    sc = 300 * in_out(prog(t, 16.5, 17.1)); y0 = -sc
    S.alpha_composite(avatar(250), (40, int(330 + y0))); d = ImageDraw.Draw(S)
    d.text((330, 390 + y0), "365 Day Mentality", font=font("xb", 50), fill=WHITE)
    d.text((330, 460 + y0), "Créateur de contenu", font=font("m", 38), fill=GREY)
    for i, s in enumerate(BIO): d.text((50, 630 + i * 58 + y0), s, font=font("m", 40), fill=WHITE)
    d.text((50, 630 + 3 * 58 + y0), "Commente « SALLE » ou écris-moi en DM", font=font("b", 40), fill=ACC)
    fol = t > 15.4; pb = 1 - 0.05 * math.sin(math.pi * prog(t, 15.3, 15.5))
    bw = 465 * pb; cx = 40 + 465 / 2
    d.rounded_rectangle([cx - bw / 2, 900 + y0, cx + bw / 2, 1000 + y0], 22, fill=DGREY if fol else ACC)
    d.text((cx, 950 + y0), "Abonné(e)" if fol else "Suivre", font=font("b", 42), fill=WHITE, anchor="mm")
    d.rounded_rectangle([535, 900 + y0, 1000, 1000 + y0], 22, fill=DGREY); d.text((767, 950 + y0), "Écrire", font=font("b", 42), fill=WHITE, anchor="mm")
    tap(S, cx, 950 + y0, t, 15.35)
    for i, (lab, im) in enumerate([("Salle", tip_card(1, 150)), ("Tips", tip_card(0, 150)), ("Abos", tip_card(3, 150)), ("Courses", tip_card(2, 150))]):
        x = 140 + i * 230; y = 1140 + y0
        d.ellipse([x - 82, y - 82, x + 82, y + 82], outline=(70, 70, 76), width=4)
        m = Image.new("L", (150, 150), 0); ImageDraw.Draw(m).ellipse([0, 0, 149, 149], fill=255)
        c = Image.new("RGBA", (150, 150), (0, 0, 0, 0)); c.paste(im, (0, 0), m); safe_comp(S, c, x - 75, y - 75); d = ImageDraw.Draw(S)
        d.text((x, y + 120), lab, font=font("m", 34), fill=WHITE, anchor="mm")
    y = 1340 + y0; d.line([(0, y), (1040, y)], fill=(40, 40, 44), width=2); d.rectangle([0, y + 100, 346, y + 104], fill=WHITE)
    for k, x in enumerate([173, 520, 866]):
        if k == 0:
            for a in range(3):
                for b in range(3): d.rectangle([x - 30 + a * 22, y + 25 + b * 22, x - 14 + a * 22, y + 41 + b * 22], fill=WHITE)
        elif k == 1: ic_reels(d, x, y + 52, 52, GREY)
        else: d.ellipse([x - 26, y + 26, x + 26, y + 78], outline=GREY, width=5)
    cells = [thumb(0), tip_card(1, 460).crop((57, 0, 403, 460)), thumb(1), tip_card(0, 460).crop((57, 0, 403, 460)), thumb(2), thumb(3),
             tip_card(3, 460).crop((57, 0, 403, 460)), thumb(4), tip_card(2, 460).crop((57, 0, 403, 460)), thumb(5)]
    for i, im in enumerate(cells):
        safe_comp(S, im, 2 + (i % 3) * 347, y + 110 + (i // 3) * 462)
    d.rectangle([0, 0, SW, 290], fill=BLACK); status_bar(d)
    d.text((60, 215), NAME, font=font("xb", 56), fill=WHITE, anchor="lm"); d.line([(560, 205), (578, 225), (596, 205)], fill=WHITE, width=6)
    ic_plus(d, 860, 215, 58)
    for k in range(3): d.rectangle([935, 192 + k * 20, 1000, 198 + k * 20], fill=WHITE)
    nav_bar(S, 4); return S

KEYROWS = ["AZERTYUIOP", "QSDFGHJKLM", "WXCVBN"]
COMMENT = "SALLE"
def key_pos(ch):
    for r, row in enumerate(KEYROWS):
        if ch in row:
            c = row.index(ch); off = [0, 0, 155][r]; return 52 + off + c * 104, 1560 + r * 150
    return 520, 2010

def screen_comments(t):
    S = screen_reel(t, 4.1); S.alpha_composite(Image.new("RGBA", (SW, SH), (0, 0, 0, 130)))
    sy = lerp(SH, 620, out_cubic(prog(t, 17.55, 17.95)))
    d = ImageDraw.Draw(S); d.rounded_rectangle([0, sy, SW, SH + 60], 50, fill=(26, 26, 30))
    d.rounded_rectangle([470, sy + 24, 570, sy + 34], 5, fill=(90, 90, 96))
    d.text((520, sy + 100), "Commentaires", font=font("b", 44), fill=WHITE, anchor="mm"); d.line([(0, sy + 160), (SW, sy + 160)], fill=(48, 48, 54), width=2)
    posted = t > 19.45
    if not posted: d.text((520, sy + 420), "Sois le premier à commenter", font=font("m", 40), fill=GREY, anchor="mm")
    else:
        p = out_back(prog(t, 19.45, 19.8)); cy = sy + 260
        lay = Image.new("RGBA", (SW, 200), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        ld.ellipse([40, 20, 140, 120], fill=(90, 90, 100)); ld.text((90, 70), "T", font=font("b", 50), fill=WHITE, anchor="mm")
        ld.text((170, 26), "toi", font=font("b", 38), fill=WHITE); ld.text((170 + font("b", 38).getlength("toi") + 14, 28), "à l'instant", font=font("m", 34), fill=GREY)
        ld.text((170, 76), COMMENT, font=font("sb", 44), fill=WHITE); ic_heart(ld, 980, 70, 40, False, GREY)
        lay = lay.resize((SW, max(1, int(200 * p)))) if p < 0.999 else lay
        safe_comp(S, fade(lay, clamp(p)), 0, cy); d = ImageDraw.Draw(S)
    ky = lerp(SH, 1450, out_cubic(prog(t, 17.95, 18.25))) + lerp(0, 800, in_cubic(prog(t, 19.45, 19.7)))
    if ky < SH:
        d.rectangle([0, ky, SW, SH], fill=(44, 44, 48))
        n = int(clamp((t - 18.4) / 0.16 + 1, 0, len(COMMENT))) if t > 18.4 else 0
        cur = COMMENT[n - 1] if 0 < n and (t - 18.4) % 0.16 < 0.1 and t < 18.4 + 0.16 * len(COMMENT) else None
        for r, row in enumerate(KEYROWS):
            for c, ch in enumerate(row):
                x, y = key_pos(ch); y = y - 1560 + ky + 110
                hi = ch == cur
                d.rounded_rectangle([x - 46, y - 62, x + 46, y + 62], 14, fill=(120, 120, 128) if hi else (80, 80, 86))
                d.text((x, y), ch, font=font("m", 50), fill=WHITE, anchor="mm")
                if hi:
                    d.rounded_rectangle([x - 60, y - 230, x + 60, y - 70], 20, fill=(120, 120, 128)); d.text((x, y - 150), ch, font=font("sb", 84), fill=WHITE, anchor="mm")
        d.rounded_rectangle([200, ky + 560, 840, ky + 680], 16, fill=(80, 80, 86)); d.text((520, ky + 620), "espace", font=font("m", 40), fill=WHITE, anchor="mm")
        iy = ky - 130
        d.rectangle([0, iy, SW, ky], fill=(26, 26, 30)); S.alpha_composite(avatar(80, False), (40, int(iy + 25))); d = ImageDraw.Draw(S)
        d.rounded_rectangle([140, iy + 20, 1000, iy + 110], 45, outline=(70, 70, 76), width=3)
        typed = COMMENT[:n]
        d.text((180, iy + 65), typed if typed else "Ajouter un commentaire…", font=font("m", 42), fill=WHITE if typed else GREY, anchor="lm")
        if (t * 2.5) % 1 < 0.6 and not posted:
            x = 180 + (font("m", 42).getlength(typed) if typed else 0) + 4; d.line([(x, iy + 38), (x, iy + 92)], fill=ACC, width=5)
        d.text((975, iy + 65), "Publier", font=font("b", 40), fill=ACC if typed else (120, 70, 20), anchor="rm")
        tap(S, 905, iy + 65, t, 19.35)
    ny = lerp(-300, 70, out_back(prog(t, 20.2, 20.55), 1.4)) + lerp(0, -400, in_cubic(prog(t, 21.6, 21.9)))
    if t > 20.2:
        nb = Image.new("RGBA", (980, 230), (0, 0, 0, 0)); nd = ImageDraw.Draw(nb)
        nd.rounded_rectangle([0, 0, 979, 229], 50, fill=(48, 48, 54, 245))
        nb.alpha_composite(logo(120), (36, 55)); nd = ImageDraw.Draw(nb)
        nd.text((185, 50), NAME, font=font("b", 40), fill=WHITE); nd.text((935, 52), "maintenant", font=font("m", 32), fill=GREY, anchor="ra")
        nd.text((185, 105), "Je t'envoie les infos pour la salle", font=font("m", 38), fill=WHITE)
        nd.text((185, 155), "à 20 €/mois en DM", font=font("m", 38), fill=WHITE)
        safe_comp(S, nb, 30, ny)
    return S

def screen_at(t):
    if t < 2.25: return screen_splash(t)
    if t < 5.95: return screen_feed(t)
    if t < 9.55: return screen_search(t)
    if t < 13.55: return screen_reel(t, t - 9.55)
    if t < 17.55: return screen_profile(t)
    return screen_comments(t)

# ------------------------------------------------------------------ phone in 3D
PW, PH, PD = 560, 1140, 54
@lru_cache(None)
def slice_img(k, n, q):
    """One depth slice of the titanium frame. q (0..20) moves the specular highlight with the phone's rotation."""
    u = k / (n - 1); c = q / 20; band = math.exp(-((u - c) / 0.16) ** 2); soft = math.exp(-((u - 0.5) / 0.45) ** 2)
    col = mix(mix((22, 23, 26), (78, 80, 88), soft), (215, 218, 226), band * 0.9)
    im = Image.new("RGBA", (140, 285), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, 139, 284], 20, fill=col); return im

@lru_cache(None)
def button_img(q):
    im = Image.new("RGBA", (24, 120), (0, 0, 0, 0)); c = q / 20
    g = np.linspace(0, 1, 24)[None, :, None] * np.ones((120, 1, 1)); band = np.exp(-((g - c) / 0.25) ** 2)
    arr = np.array([60, 62, 70]) * (1 - band) + np.array([210, 213, 222]) * band
    body = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    m = Image.new("L", (24, 120), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, 23, 119], 11, fill=255)
    im.paste(body, (0, 0), m); return im

BUTTONS = [(+1, -270, -120), (-1, -350, -300), (-1, -240, -150), (-1, -110, -20)]   # side, y0, y1 (power, action, vol+, vol-)
def draw_buttons(L, C, M, q):
    for side, y0, y1 in BUTTONS:
        x = side * (PW / 2 + 3.5); dz = PD * 0.2
        loc = [[x, y0, -dz], [x, y0, dz], [x, y1, dz], [x, y1, -dz]] if side > 0 else [[x, y0, dz], [x, y0, -dz], [x, y1, -dz], [x, y1, dz]]
        P = np.array(loc, float) @ M.T + C
        if P[:, 2].min() < 150: continue
        pts = project(P)
        if area(pts) > 0: warp_clip(L, button_img(q), pts)

@lru_cache(None)
def face_base():
    im = Image.new("RGBA", (PW * 2, PH * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, PW * 2 - 1, PH * 2 - 1], 160, fill=(5, 5, 7))
    d.rounded_rectangle([2, 2, PW * 2 - 3, PH * 2 - 3], 158, outline=(120, 124, 135), width=3)   # glass edge catching light
    d.rounded_rectangle([7, 7, PW * 2 - 8, PH * 2 - 8], 153, outline=(28, 29, 33), width=4)
    m = Image.new("L", (SW, SH), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, SW - 1, SH - 1], 124, fill=255)
    return im, m

def phone_face(screen, glare):
    base, m = face_base(); im = base.copy(); im.paste(screen, (40, 40), m); d = ImageDraw.Draw(im)
    d.rounded_rectangle([PW - 150, 70, PW + 150, 150], 40, fill=(0, 0, 0))
    d.ellipse([PW + 70, 92, PW + 106, 128], fill=(14, 16, 26)); d.ellipse([PW + 80, 100, PW + 90, 110], fill=(50, 60, 90))
    gx, gy = glare
    g = Image.new("L", (140, 285), 0); gd = ImageDraw.Draw(g); x = lerp(-60, 200, gx)
    gd.ellipse([20 + gx * 60 - 90, -60 + gy * 40, 20 + gx * 60 + 90, 120 + gy * 40], fill=22)       # soft window light
    gd.polygon([(x, 0), (x + 34, 0), (x - 96, 285), (x - 130, 285)], fill=30)                        # sharp streak
    gd.polygon([(x + 52, 0), (x + 60, 0), (x - 70, 285), (x - 78, 285)], fill=24)
    g = g.filter(ImageFilter.GaussianBlur(5)).resize(im.size, Image.BILINEAR)
    gl = Image.new("RGBA", im.size, (255, 255, 255, 0)); gl.putalpha(Image.fromarray(np.minimum(np.array(g), np.array(im.getchannel("A")))))
    im.alpha_composite(gl); return im

@lru_cache(None)
def phone_back():
    im = Image.new("RGBA", (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, PW - 1, PH - 1], 80, fill=(52, 55, 64)); d.rounded_rectangle([40, 40, 250, 250], 50, fill=(36, 38, 44))
    for cx, cy in [(95, 95), (195, 95), (95, 195)]: d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(15, 15, 18), outline=(90, 92, 100), width=6)
    return im

def corners(C, M, dz):
    loc = np.array([[-PW / 2, -PH / 2, dz], [PW / 2, -PH / 2, dz], [PW / 2, PH / 2, dz], [-PW / 2, PH / 2, dz]])
    return loc @ M.T + C

def draw_phone(L, C, M, screen, glare):
    fp = corners(C, M, -PD / 2)
    if fp[:, 2].min() < 150: return
    face = project(fp); vis = area(face) > 0; n = 14
    q = int(clamp(10 + glare[0] * 8 - 4, 1, 19))
    SL = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    for k in (range(n) if vis else range(n - 1, -1, -1)):
        pts = project(corners(C, M, lerp(PD / 2, -PD / 2 + 1, k / (n - 1))))
        warp_clip(SL, slice_img(k, n, q), [(x / 2, y / 2) for x, y in pts])
    L.alpha_composite(SL.resize((W, H), Image.BILINEAR))
    draw_buttons(L, C, M, q)
    if vis: warp_clip(L, phone_face(screen, glare), face)
    else:
        b = project(corners(C, M, PD / 2 + 1)); warp_clip(L, phone_back(), [b[1], b[0], b[3], b[2]])

# camera keys: (t, u, v, z, rx, ry, rz) -> point (u, v) of the phone face is centred on screen at depth z
KEYS = [(1.55, 0, 0, 5200, 30, -60, -25), (2.35, 0, 0, 1500, 6, -16, -4), (2.9, 0, 0, 1500, 4, -12, -2),
        (3.45, 0, -80, 950, 16, -28, -10), (4.7, 0, -40, 900, 13, -22, -7), (5.35, 0, 0, 1450, 4, 12, 3),
        (6.05, 30, -470, 780, 24, 26, 9), (7.7, 130, -440, 760, 20, 18, 6), (8.4, 0, -280, 980, 12, 10, 4),
        (9.3, 0, 0, 1420, 0, -8, -2), (10.0, 0, 30, 1250, -4, 14, 3), (11.6, 0, 120, 1050, -10, 20, 6),
        (12.35, 120, 60, 860, -8, 26, 8), (13.3, -120, -380, 820, 16, -24, -8), (15.0, -60, -150, 900, 12, -14, -4),
        (16.3, 0, 260, 1100, -12, 10, 3), (17.35, 0, 0, 1450, 0, -6, -2), (18.15, 0, 330, 930, -18, -20, -6),
        (19.5, 0, 280, 900, -15, -14, -4), (20.25, 0, -440, 860, 20, 16, 6), (21.3, 0, -420, 820, 17, 10, 4),
        (21.9, 0, 0, 230, 0, 0, 170)]

def pose(t):
    if t <= KEYS[0][0]: k = KEYS[0]
    elif t >= KEYS[-1][0]: k = KEYS[-1]
    else:
        for a, b in zip(KEYS, KEYS[1:]):
            if a[0] <= t <= b[0]:
                x = (t - a[0]) / (b[0] - a[0]); sx = clamp((x - 0.55) / 0.45)
                e = in_out(x) + 0.05 * math.sin(math.pi * sx) * (1 if b[0] - a[0] < 1.2 else 0.4)   # overshoot, then settle
                k = [lerp(p, q, e) for p, q in zip(a, b)]; k[3] = lerp(a[3], b[3], in_out(x)); break
    _, u, v, z, rx, ry, rz = k
    rx += 1.6 * math.sin(t * 1.3); ry += 2.0 * math.sin(t * 0.9 + 1); rz += 0.8 * math.sin(t * 1.1)
    # handheld micro-shake (layered sines ~ smooth noise)
    rx += 0.32 * math.sin(t * 7.3) + 0.18 * math.sin(t * 11.9 + 1.3) + 0.1 * math.sin(t * 17.1 + 2)
    ry += 0.32 * math.sin(t * 6.1 + 2) + 0.18 * math.sin(t * 13.7 + 0.4) + 0.1 * math.sin(t * 19.3)
    rz += 0.22 * math.sin(t * 5.3 + 0.5) + 0.12 * math.sin(t * 9.7 + 3)
    u += 2.2 * math.sin(t * 8.7) + 1.2 * math.sin(t * 14.3 + 1); v += 2.2 * math.sin(t * 9.9 + 1) + 1.2 * math.sin(t * 15.1)
    M = rotm(rx, ry, rz); C = np.array([0, 0, z]) - M @ np.array([u, v, -PD / 2])
    return C, M, (ry, rx), z

def phone_motion(t):
    """Screen-space motion (px/frame) of the phone, used for motion blur."""
    C0, M0, _, _ = pose(t); C1, M1, _, _ = pose(t + 1 / FPS)
    p0 = np.array(project(corners(C0, M0, 0))); p1 = np.array(project(corners(C1, M1, 0)))
    return (p1 - p0).mean(axis=0)

def motion_blur(D, v):
    L = float(np.hypot(*v)) * 0.9
    if L < 4: return D
    L = min(L, 140); n = int(min(12, 3 + L / 10)); ux, uy = v / np.hypot(*v)
    a = np.asarray(D, np.float32); pm = a.copy(); pm[..., :3] *= a[..., 3:4] / 255
    acc = np.zeros_like(pm)
    for k in range(n):
        o = (k / (n - 1) - 0.5) * L; dx, dy = int(round(ux * o)), int(round(uy * o))
        acc += np.roll(np.roll(pm, dy, axis=0), dx, axis=1)
    acc /= n; al = acc[..., 3:4]; rgb = np.where(al > 0, acc[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.concatenate([rgb, al], axis=2).clip(0, 255).astype(np.uint8), "RGBA")

SHUTTER = 0.75   # 270-degree shutter
SCROLLS = [(2.95, 3.5), (4.95, 5.6)]

def device_at(t, screen=None):
    C, M, (ry, rx), _ = pose(t); D = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_phone(D, C, M, screen if screen is not None else screen_at(t), (0.5 + ry / 120, 0.5 + rx / 60))
    return D

def premul(D):
    a = np.asarray(D, np.float32); a[..., :3] *= a[..., 3:4] / 255; return a

def unpremul(a):
    al = a[..., 3:4]; rgb = np.where(al > 0, a[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.concatenate([rgb, al], axis=2).clip(0, 255).astype(np.uint8), "RGBA")

def render_device(t):
    """Real motion blur: average several sub-frames across the shutter, then lens depth of field."""
    v = phone_motion(t); L = float(np.hypot(*v)) * SHUTTER
    n = 1 if L < 2.5 else min(6, 1 + int(L / 5))
    if n == 1: D = device_at(t)
    else:
        scrolling = any(a <= t <= b for a, b in SCROLLS); scr = None if scrolling else screen_at(t); acc = None
        for k in range(n):
            ts = t + (k / (n - 1) - 0.5) * SHUTTER / FPS
            pm = premul(device_at(ts, scr)); acc = pm if acc is None else acc + pm
        D = unpremul(acc / n)
        if L / (n - 1) > 5: D = motion_blur(D, v * (L / (n - 1)) / max(1e-3, float(np.hypot(*v))) / 0.9)
    return depth_of_field(D, t)

def depth_of_field(D, t):
    C, M, _, _ = pose(t); zf = pose(t - 0.12)[3]          # focus lags slightly behind the camera (focus pull)
    nrm = M @ np.array([0, 0, -1.0]); P0 = C + M @ np.array([0, 0, -PD / 2]); d = float(nrm @ P0)
    gy, gx = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32) * 8
    den = nrm[0] * (gx - W / 2) + nrm[1] * (gy - H / 2) + nrm[2] * F
    z = np.where(np.abs(den) > 1e-3, F * d / np.where(np.abs(den) > 1e-3, den, 1), 1e9)
    m = np.clip((np.abs(1 - zf / np.maximum(z, 1)) - 0.045) * 4.5, 0, 1).astype(np.float32)
    if m.max() < 0.05: return D
    mk = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255
    sharp = premul(D)
    small = Image.fromarray(sharp.clip(0, 255).astype(np.uint8), "RGBA").resize((W // 3, H // 3), Image.BILINEAR)
    blur = np.asarray(small.filter(ImageFilter.GaussianBlur(3.5)).resize((W, H), Image.BILINEAR), np.float32)
    return unpremul(sharp * (1 - mk) + blur * mk)

# ------------------------------------------------------------------ background, intro, outro
BG = None
def background(t):
    global BG
    if BG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2), 0, 1)[..., None]
        arr = np.array([30, 70, 245], np.float32) * (1 - r) + np.array([8, 20, 110], np.float32) * r
        dark = np.array([6, 7, 14], np.float32) * np.ones_like(arr)
        BG = (Image.fromarray(arr.astype(np.uint8)).convert("RGBA"), Image.fromarray(dark.astype(np.uint8)).convert("RGBA"))
    k = smooth(prog(t, 21.5, 21.95))
    im = BG[0].copy() if k <= 0 else (BG[1].copy() if k >= 1 else Image.blend(BG[0], BG[1], k))
    sm = Image.new("RGBA", (W // 8, H // 8), (0, 0, 0, 0)); d = ImageDraw.Draw(sm)
    cx, cy = W / 16 + 30 * math.sin(t * 0.5), H / 20 + 20 * math.cos(t * 0.4)
    d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=(120, 170, 255, int(50 * (1 - k))))
    im.alpha_composite(sm.filter(ImageFilter.GaussianBlur(18)).resize((W, H), Image.BILINEAR))
    return im

def intro(L, t):
    if t >= 1.75: return
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for k in range(8):   # concentric ripples
        p = (t - k * 0.18) / 1.3
        if 0 < p < 1:
            r = 40 + 1100 * out_cubic(p); a = int(70 * (1 - p))
            d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=(140, 180, 255, a))
    L.alpha_composite(lay)
    s = out_back(prog(t, 0.3, 0.7), 2.2) * (1 + 9 * in_cubic(prog(t, 1.25, 1.65)))
    if s > 0.02:
        size = int(300 * s)
        if size < 3200:
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([W / 2 - size * 0.8, H / 2 - size * 0.8, W / 2 + size * 0.8, H / 2 + size * 0.8], fill=ACC + (90,))
            L.alpha_composite(g.filter(ImageFilter.GaussianBlur(60)))
            lg = logo(300).resize((size, size), Image.LANCZOS)
            safe_comp(L, fade(lg, 1 - smooth(prog(t, 1.5, 1.7))), W / 2 - size / 2, H / 2 - size / 2)

def lemniscate(n=240, a=400, cx=W / 2, cy=800):
    pts = []
    for k in range(n + 1):
        s = 2 * math.pi * k / n - math.pi / 2; den = 1 + math.sin(s) ** 2
        pts.append((cx + a * math.cos(s) / den, cy + a * math.sin(s) * math.cos(s) / den * 1.25))
    return pts
LEM = lemniscate()

def outro(L, t):
    if t < 21.9: return
    p = in_out(prog(t, 21.95, 23.2)); n = max(2, int(len(LEM) * p))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for i in range(n - 1):
        c = mix(ACC, PINK, abs(math.sin(i / len(LEM) * math.pi)))
        d.line([LEM[i], LEM[i + 1]], fill=c + (255,), width=20)
    hx, hy = LEM[n - 1]
    if p < 1: d.ellipse([hx - 22, hy - 22, hx + 22, hy + 22], fill=WHITE)
    glow = lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BILINEAR)
    L.alpha_composite(glow); L.alpha_composite(glow); L.alpha_composite(lay)
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0)); cd = ImageDraw.Draw(core)
    for i in range(n - 1): cd.line([LEM[i], LEM[i + 1]], fill=(255, 240, 220, 220), width=6)
    L.alpha_composite(core)
    for txt, f, col, y, t0 in [("365 DAY MENTALITY", font("black", 88), WHITE, 1200, 22.9), ("@" + NAME, font("xb", 64), ACC, 1320, 23.15),
                               ("Abonne-toi pour plus de bons plans", font("sb", 46), (200, 205, 220), 1420, 23.4)]:
        a = out_cubic(prog(t, t0, t0 + 0.4))
        if a > 0:
            im = Image.new("RGBA", (W, 160), (0, 0, 0, 0)); ImageDraw.Draw(im).text((W / 2, 80), txt, font=f, fill=col, anchor="mm")
            safe_comp(L, fade(im, a), 0, y - 80 + (1 - a) * 40)

# ------------------------------------------------------------------ compose & post
def compose(t):
    img = background(t); intro(img, t)
    if 1.55 <= t < 21.92:
        D = render_device(t)
        sh = D.getchannel("A").resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
        shadow = Image.new("RGBA", (W, H), (0, 0, 20, 0)); shadow.putalpha(sh.point(lambda v: int(v * 0.5)))
        z = pose(t)[3]; o = 1500 / z
        safe_comp(img, shadow, 45 * o, 85 * o)
        tight = D.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        sh2 = Image.new("RGBA", (W, H), (0, 0, 10, 0)); sh2.putalpha(tight.point(lambda v: int(v * 0.35)))
        safe_comp(img, sh2, 12 * o, 22 * o)
        img.alpha_composite(D)
    outro(img, t)
    return img

VIG = None
def post(img, t, fi):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        VIG = (1 - 0.45 * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None].astype(np.float32)
    sw = math.sin(math.pi * prog(t, 21.45, 22.15))   # swirl transition
    if sw > 0.02:
        acc = None
        for k in range(7):
            r = img.rotate(-(k - 3) * 6 * sw, Image.BILINEAR, center=(W / 2, H / 2), fillcolor=(6, 7, 14, 255))
            acc = r if acc is None else Image.blend(acc, r, 1 / (k + 1))
        img = acc
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 140, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR), np.float32) * 0.6
    fl = math.exp(-max(0, t - 21.92) * 10) * 0.6 if t >= 21.92 else 0
    fl += 0.5 * math.sin(math.pi * prog(t, 1.45, 1.75))
    arr = arr + (255 - arr) * min(fl, 0.8)
    arr = arr * VIG + np.random.default_rng(fi).normal(0, 2, (H, W, 1)).astype(np.float32)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(compose(t), t, i).tobytes()

# ------------------------------------------------------------------ audio
WHOOSH = [1.5, 2.95, 3.4, 4.95, 5.3, 6.0, 9.25, 9.95, 12.3, 13.25, 16.25, 17.3, 18.1, 20.2, 21.4]
TAPS = [4.3, 4.42, 5.85, 8.6, 9.4, 12.08, 12.2, 13.45, 15.35, 19.35]
def make_audio(path, music=True):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(4)
    def add(sig, t0):
        i = int(t0 * sr)
        if i >= n or i < 0: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    beat = 0.5
    if music:
        tk = T(0.35); kick = np.sin(2 * np.pi * (46 + 120 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 8)
        th = T(0.04); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 110) * 0.11
        ts = T(0.22); snare = (Rn.uniform(-1, 1, len(ts)) * 0.6 + np.sin(2 * np.pi * 200 * ts) * 0.4) * np.exp(-ts * 20) * 0.3
        chords = [(220, 277.2, 329.6), (196, 246.9, 293.7), (174.6, 220, 261.6), (196, 246.9, 311.1)]
        k = 0
        while k * beat < 21.4:
            t0 = k * beat; bar = (k // 4) % 4
            if t0 >= 1.7:
                add(kick * 0.85, t0); add(hat, t0 + beat / 2)
                if k % 2 == 1: add(snare, t0)
                tb = T(beat); root = chords[bar][0] / 4
                add(np.sin(2 * np.pi * root * tb) * np.exp(-tb * 3) * 0.22, t0)
            for j in range(2):   # pluck arpeggio
                f = chords[bar][(k * 2 + j) % 3] * 2; tp = T(0.25)
                add((np.sin(2 * np.pi * f * tp) + 0.3 * np.sin(4 * np.pi * f * tp)) * np.exp(-tp * 14) * 0.07, t0 + j * beat / 2)
            k += 1
        tr = T(1.5); add(np.sin(2 * np.pi * np.cumsum(200 + 1200 * (tr / 1.5) ** 2) / sr) * (tr / 1.5) ** 2 * 0.08, 0.1)
        tp = T(3.0)
        pad = sum(np.sin(2 * np.pi * f * tp) for f in (220, 277.2, 329.6, 440)) * np.exp(-tp * 0.9) * 0.05
        add(pad, 21.95)
    tw = T(0.35)
    for t0 in WHOOSH:
        nz = Rn.normal(0, 1, len(tw)); nz = np.convolve(nz, np.ones(6) / 6, "same")
        add(nz * np.sin(np.pi * tw / 0.35) ** 2 * 0.28, t0)
    tc = T(0.03)
    for t0 in TAPS: add(np.sin(2 * np.pi * 1800 * tc) * np.exp(-tc * 160) * 0.35, t0)
    for i in range(len(QUERY)): add(Rn.uniform(-1, 1, len(tc)) * np.exp(-tc * 220) * 0.25, 6.4 + i / 16)
    for i in range(len(COMMENT)): add(Rn.uniform(-1, 1, len(tc)) * np.exp(-tc * 220) * 0.3, 18.4 + i * 0.16)
    tpop = T(0.18)
    for t0 in (4.42, 12.2, 19.45): add(np.sin(2 * np.pi * np.cumsum(400 + 1400 * tpop / 0.18) / sr) * np.exp(-tpop * 18) * 0.3, t0)
    td = T(0.6)
    for f, dt in ((1318.5, 0), (1760, 0.12)): add(np.sin(2 * np.pi * f * td) * np.exp(-td * 7) * 0.22, 20.25 + dt)
    tb2 = T(1.4); add((np.sin(2 * np.pi * (40 + 50 * np.exp(-tb2 * 8)) * tb2) * np.exp(-tb2 * 3)) * 0.6, 21.93)
    add(np.sin(2 * np.pi * np.cumsum(500 + 300 * T(0.3) / 0.3) / sr) * np.exp(-T(0.3) * 10) * 0.2, 0.32)
    fo = int(0.5 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.3) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    prepare_assets()
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
