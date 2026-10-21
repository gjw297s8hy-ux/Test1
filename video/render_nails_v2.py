"""Motion design "démo d'appli" pour @gwn.nails76 (prothésiste ongulaire, Rouen).
Ambiance claire et chic : story avant/après, post, profil, story Information, DM de prise de RDV, carte de fin.
Rendu :   python3 render_nails_v2.py          -> promo_gwn_nails76_v2.mp4 (+ _sans_musique.mp4)  1080x1920 60 i/s
Aperçu :  python3 render_nails_v2.py 3.4 9    -> preview_3.4.png ..."""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 60, 19.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_gwn_nails76_v2.mp4")
AS = os.path.join(HERE, "assets_nails")
NAME = "gwn.nails76"

INK = (24, 22, 22); GREY = (138, 132, 130); LIGHT = (240, 236, 234); WHITE = (255, 255, 255)
ROSE = (222, 128, 146); BLUSH = (246, 206, 210); BROWN = (112, 82, 62); GOLD = (214, 172, 128); RED = (238, 52, 72)
CREAM1, CREAM2 = (250, 244, 238), (232, 216, 202)
FONTS = "/usr/share/fonts/opentype/inter/"; SERIF = "/usr/share/fonts/truetype/freefont/"
FW = {"xb": FONTS + "Inter-ExtraBold.otf", "b": FONTS + "Inter-Bold.otf", "sb": FONTS + "Inter-SemiBold.otf",
      "m": FONTS + "Inter-Medium.otf", "r": FONTS + "Inter-Regular.otf",
      "serif": SERIF + "FreeSerif.ttf", "serif_i": SERIF + "FreeSerifItalic.ttf", "serif_b": SERIF + "FreeSerifBold.ttf"}

@lru_cache(None)
def font(w, s): return ImageFont.truetype(FW[w], s)

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
def area(pts): return sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))

def premul(D):
    a = np.asarray(D, np.float32); a[..., :3] *= a[..., 3:4] / 255; return a

def unpremul(a):
    al = a[..., 3:4]; rgb = np.where(al > 0, a[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.concatenate([rgb, al], axis=2).clip(0, 255).astype(np.uint8), "RGBA")

# ------------------------------------------------------------------ client photos
@lru_cache(None)
def photo(name): return Image.open(os.path.join(AS, name + ".jpg")).convert("RGBA")

def fit_w(im, w):
    return im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)

@lru_cache(None)
def cover(name, w, h):
    im = photo(name); s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2; return im.crop((x, y, x + w, y + h))

@lru_cache(None)
def round_img(name, d, ring=0, ring_col=None):
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    inner = d - 2 * ring
    if ring:
        if ring_col is None:
            g = grad(d, d, (250, 200, 150), ROSE); m = Image.new("L", (d, d), 0); ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
            im.paste(g, (0, 0), m)
        else: dr.ellipse([0, 0, d - 1, d - 1], fill=ring_col)
        dr.ellipse([ring * 0.45, ring * 0.45, d - ring * 0.45, d - ring * 0.45], fill=WHITE)
    p = cover(name, inner, inner); m = Image.new("L", (inner, inner), 0); ImageDraw.Draw(m).ellipse([0, 0, inner - 1, inner - 1], fill=255)
    im.paste(p, (ring, ring), m); return im

def grad(w, h, c1, c2):
    y, x = np.mgrid[0:h, 0:w]; k = ((x / w + y / h) / 2)[..., None]
    return Image.fromarray((np.array(c1) * (1 - k) + np.array(c2) * k).astype(np.uint8)).convert("RGBA")

def rounded(im, r):
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], r, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.paste(im, (0, 0), m); return out

# ------------------------------------------------------------------ icons
def sparkle(d, cx, cy, s, col, a=255):
    """4-point star sparkle."""
    if s < 1: return
    pts = []
    for k in range(8):
        ang = math.pi / 4 * k - math.pi / 2; r = s if k % 2 == 0 else s * 0.22
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    d.polygon(pts, fill=col + (int(a),))

def heart_pts(cx, cy, s):
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        x = 16 * math.sin(a) ** 3; y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * s / 32, cy + y * s / 32))
    return pts

def ic_heart(d, cx, cy, s, filled=False, col=INK):
    p = heart_pts(cx, cy, s)
    if filled: d.polygon(p, fill=RED)
    else: d.line(p + [p[0]], fill=col, width=max(3, int(s / 12)), joint="curve")

def ic_comment(d, cx, cy, s, col=INK):
    r = s / 2; w = max(3, int(s / 12))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)
    d.line([(cx - r * 0.75, cy + r * 0.65), (cx - r * 0.95, cy + r * 1.05), (cx - r * 0.3, cy + r * 0.92)], fill=col, width=w)

def ic_share(d, cx, cy, s, col=INK):
    r = s / 2; w = max(3, int(s / 12))
    p = [(cx - r, cy - r * 0.8), (cx + r, cy - r), (cx - r * 0.1, cy + r), (cx - r * 0.25, cy - r * 0.1)]
    d.line(p + [p[0]], fill=col, width=w, joint="curve"); d.line([(cx - r * 0.25, cy - r * 0.1), (cx + r, cy - r)], fill=col, width=w)

def ic_save(d, cx, cy, s, col=INK):
    r = s / 2; w = max(3, int(s / 12))
    p = [(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.7, cy + r), (cx, cy + r * 0.45), (cx - r * 0.7, cy + r)]
    d.line(p + [p[0]], fill=col, width=w, joint="curve")

def ic_mail(d, cx, cy, s, col=INK):
    r = s / 2; w = max(3, int(s / 14))
    d.rounded_rectangle([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], 6, outline=col, width=w)
    d.line([(cx - r, cy - r * 0.7), (cx, cy + r * 0.1), (cx + r, cy - r * 0.7)], fill=col, width=w)

def ic_pin(d, cx, cy, s, col=INK):
    r = s * 0.34; d.ellipse([cx - r, cy - s * 0.5, cx + r, cy - s * 0.5 + 2 * r], outline=col, width=max(3, int(s / 12)))
    d.polygon([(cx - r * 0.8, cy - s * 0.1), (cx + r * 0.8, cy - s * 0.1), (cx, cy + s * 0.5)], fill=col)
    d.ellipse([cx - r * 0.35, cy - s * 0.5 + r * 0.65, cx + r * 0.35, cy - s * 0.5 + r * 1.35], fill=WHITE)

def status_bar(d, col=INK):
    d.text((90, 56), "9:41", font=font("sb", 54), fill=col)
    for k in range(4): d.rounded_rectangle([760 + k * 22, 96 - k * 12, 774 + k * 22, 104], 3, fill=col)
    d.arc([860, 54, 920, 114], 225, 315, fill=col, width=9); d.ellipse([884, 92, 896, 104], fill=col)
    d.rounded_rectangle([935, 62, 1010, 102], 12, outline=col, width=4); d.rounded_rectangle([943, 70, 990, 94], 6, fill=col)

def nav_bar(S, active=0):
    d = ImageDraw.Draw(S); d.rectangle([0, 2040, 1040, 2200], fill=WHITE); d.line([(0, 2040), (1040, 2040)], fill=LIGHT, width=2)
    y = 2105
    p = [(70, y), (104, y - 34), (138, y), (130, y), (130, y + 32), (78, y + 32), (78, y)]
    if active == 0: d.polygon(p, fill=INK)
    else: d.line(p + [p[0]], fill=INK, width=5)
    d.ellipse([286, 2077, 334, 2125], outline=INK, width=6); d.line([(328, 2121), (346, 2139)], fill=INK, width=6)
    d.rounded_rectangle([490, 2075, 550, 2135], 16, outline=INK, width=5); d.line([(505, y), (535, y)], fill=INK, width=5); d.line([(520, 2090), (520, 2120)], fill=INK, width=5)
    d.rounded_rectangle([698, 2075, 758, 2135], 16, outline=INK, width=5); d.polygon([(720, 2092), (742, y + 2), (720, 2118)], fill=INK)
    S.alpha_composite(round_img("avatar", 66, 3 if active == 4 else 0, INK if active == 4 else None), (903, 2072))
    d.rounded_rectangle([370, 2172, 670, 2182], 5, fill=INK)

def tap(S, x, y, t, t0, dark=True, dur=0.35):
    p = prog(t, t0 - 0.08, t0 + dur)
    if 0 < p < 1:
        lay = Image.new("RGBA", S.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        r = lerp(30, 110, out_cubic(p)); a = int(150 * (1 - p)); c = (60, 40, 40) if dark else (255, 255, 255)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (a // 3,), outline=c + (a,), width=5); S.alpha_composite(lay)

def heart_pop(S, cx, cy, t, t0):
    p = prog(t, t0, t0 + 0.8)
    if 0 < p < 1:
        lay = Image.new("RGBA", S.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        sc = out_back(prog(t, t0, t0 + 0.28), 2.5) * (1 + 0.15 * smooth(prog(t, t0 + 0.5, t0 + 0.8)))
        a = int(255 * (1 - smooth(prog(t, t0 + 0.5, t0 + 0.8))))
        if sc > 0.02: d.polygon(heart_pts(cx, cy, 360 * sc), fill=(255, 255, 255, a))
        for k in range(12):
            ang = 2 * math.pi * k / 12 + 0.2; rr = 130 + 380 * out_cubic(p)
            sparkle(d, cx + math.cos(ang) * rr, cy + math.sin(ang) * rr, 34 * (1 - p), WHITE if k % 2 else BLUSH, 255 * (1 - p))
        S.alpha_composite(lay)

def story_header(S, t, t0, t1, seg, nseg, label, light_text=True):
    d = ImageDraw.Draw(S); col = WHITE if light_text else INK
    sw = (1000 - (nseg - 1) * 10) / nseg
    for k in range(nseg):
        x = 20 + k * (sw + 10); d.rounded_rectangle([x, 150, x + sw, 158], 4, fill=col + (90,))
        f = 1 if k < seg else (prog(t, t0, t1) if k == seg else 0)
        if f > 0: d.rounded_rectangle([x, 150, x + sw * f, 158], 4, fill=col + (255,))
    S.alpha_composite(round_img("avatar", 90), (30, 185)); d = ImageDraw.Draw(S)
    d.text((140, 230), NAME, font=font("b", 40), fill=col, anchor="lm")
    d.text((150 + font("b", 40).getlength(NAME), 230), label, font=font("m", 36), fill=col + (190,), anchor="lm")
    d.line([(950, 205), (995, 250)], fill=col, width=6); d.line([(995, 205), (950, 250)], fill=col, width=6)

def story_footer(S, light=True):
    d = ImageDraw.Draw(S); col = WHITE if light else INK
    d.rounded_rectangle([30, 2040, 800, 2140], 50, outline=col + (200,), width=3)
    d.text((80, 2090), "Envoyer un message", font=font("m", 40), fill=col, anchor="lm")
    ic_heart(d, 870, 2090, 62, col=col); ic_share(d, 975, 2090, 58, col=col)

# ------------------------------------------------------------------ app screens (1040 x 2200)
SW, SH = 1040, 2200

@lru_cache(None)
def story_bg(name):
    return cover(name, SW, SH).filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.8))

BOX = (0, 380, 1040, 1780)      # before/after photo box
def screen_story_ba(t):
    S = story_bg("apres" if t > 3.5 else "avant").copy()
    w, h = BOX[2] - BOX[0], BOX[3] - BOX[1]
    av, ap = cover("avant", w, h), cover("apres", w, h)
    xl = int(lerp(0, w, in_out(prog(t, 3.0, 3.95))))
    S.alpha_composite(av, (BOX[0], BOX[1]))
    if xl > 0: S.alpha_composite(ap.crop((0, 0, xl, h)), (BOX[0], BOX[1]))
    d = ImageDraw.Draw(S)
    if 0 < xl < w:   # glowing wipe line + knob
        gl = Image.new("RGBA", (120, h), (0, 0, 0, 0)); ImageDraw.Draw(gl).rectangle([52, 0, 68, h], fill=(255, 255, 255, 200))
        safe_comp(S, gl.filter(ImageFilter.GaussianBlur(14)), xl - 60, BOX[1]); d = ImageDraw.Draw(S)
        d.rectangle([xl - 3, BOX[1], xl + 3, BOX[3]], fill=WHITE)
        cy = (BOX[1] + BOX[3]) / 2; d.ellipse([xl - 52, cy - 52, xl + 52, cy + 52], fill=WHITE)
        d.polygon([(xl - 14, cy - 18), (xl - 34, cy), (xl - 14, cy + 18)], fill=BROWN); d.polygon([(xl + 14, cy - 18), (xl + 34, cy), (xl + 14, cy + 18)], fill=BROWN)
        for k in range(7):
            yy = BOX[1] + ((k * 211 + t * 900) % h); sparkle(d, xl + 30 * math.sin(k * 2.1 + t * 9), yy, 26, WHITE, 230)
    if t > 3.9:   # sparkles on the result
        for k in range(14):
            ph = (t - 3.9) * 1.6 + k * 0.37; a = max(0, math.sin(ph * 3.1)) * (1 - prog(t, 4.7, 5.0))
            x = BOX[0] + (k * 173) % w; y = BOX[1] + 120 + (k * 331) % (h - 240)
            sparkle(d, x, y, 30 * a + 4, WHITE, 255 * a)
    for txt, x, show in [("AVANT", 760, t < 3.6), ("APRÈS", 60, t > 3.5)]:
        if show:
            f = font("b", 36); tw = f.getlength(txt)
            d.rounded_rectangle([x, BOX[1] + 40, x + tw + 50, BOX[1] + 110], 35, fill=(255, 255, 255, 220))
            d.text((x + 25 + tw / 2, BOX[1] + 75), txt, font=f, fill=BROWN, anchor="mm")
    story_header(S, t, 1.6, 5.0, 0, 2, "Prestations"); story_footer(S)
    return S

POST_TOP = 260
def screen_feed(t):
    S = Image.new("RGBA", (SW, SH), WHITE + (255,)); d = ImageDraw.Draw(S)
    off = lerp(700, 0, out_cubic(prog(t, 5.0, 5.5)))
    y = POST_TOP + off
    S.alpha_composite(round_img("avatar", 100, 6), (30, int(y + 20))); d = ImageDraw.Draw(S)
    d.text((150, y + 30), NAME, font=font("b", 42), fill=INK); d.text((150, y + 80), "Rouen, Normandie", font=font("m", 34), fill=GREY)
    d.text((960, y + 50), "•••", font=font("b", 40), fill=INK, anchor="mm")
    ph = fit_w(photo("cherry"), 1040) if not hasattr(screen_feed, "c") else screen_feed.c
    screen_feed.c = ph
    S.alpha_composite(ph.crop((0, 0, 1040, 1300)), (0, int(y + 140))); d = ImageDraw.Draw(S)
    heart_pop(S, 520, y + 140 + 650, t, 6.6); tap(S, 520, y + 790, t, 6.48, False, 0.2); tap(S, 520, y + 790, t, 6.6, False, 0.3)
    d = ImageDraw.Draw(S); ay = y + 1510
    ic_heart(d, 75, ay, 66, t > 6.6); ic_comment(d, 185, ay, 58); ic_share(d, 290, ay, 58); ic_save(d, 975, ay, 60)
    for k in range(3): d.ellipse([500 + k * 24, ay - 8, 516 + k * 24, ay + 8], fill=ROSE if k == 0 else LIGHT)
    d.text((40, y + 1580), NAME, font=font("b", 38), fill=INK)
    d.text((50 + font("b", 38).getlength(NAME), y + 1580), "Cherry nails, prise de RDV en DM", font=font("m", 38), fill=INK)
    d.text((40, y + 1640), "Voir la traduction", font=font("m", 32), fill=GREY)
    d.rectangle([0, 0, SW, 250], fill=WHITE); status_bar(d)
    d.text((520, 195), "Suggestions pour toi", font=font("serif_b", 60), fill=INK, anchor="mm")
    tap(S, 80, POST_TOP + 70, t, 7.85)
    nav_bar(S, 0); return S

BIO = [("pin", "Rouen / 76"), ("spark", "Prothésiste ongulaire débutante"), ("mail", "Prise de rendez-vous en DM")]
def screen_profile(t):
    S = Image.new("RGBA", (SW, SH), WHITE + (255,)); d = ImageDraw.Draw(S); status_bar(d)
    d.line([(70, 215), (45, 240), (70, 265)], fill=INK, width=7); d.text((115, 240), NAME, font=font("xb", 56), fill=INK, anchor="lm")
    d.text((970, 240), "•••", font=font("b", 44), fill=INK, anchor="mm")
    S.alpha_composite(round_img("avatar", 260, 9), (40, 330)); d = ImageDraw.Draw(S)
    d.text((340, 400), "Prothésiste ongulaire", font=font("b", 46), fill=INK)
    d.text((340, 462), "débutante", font=font("b", 46), fill=INK)
    d.text((340, 530), "Beauté, cosmétique", font=font("m", 36), fill=GREY)
    for i, (ic, s) in enumerate(BIO):
        a = out_cubic(prog(t, 8.3 + i * 0.15, 8.6 + i * 0.15)); y = 680 + i * 70
        if a <= 0: continue
        x = 50 + (1 - a) * 40
        if ic == "pin": ic_pin(d, x + 20, y, 44, BROWN)
        elif ic == "mail": ic_mail(d, x + 20, y, 44, BROWN)
        else: sparkle(d, x + 20, y, 24, GOLD, 255 * a)
        d.text((x + 60, y), s, font=font("m", 42), fill=INK + (int(255 * a),), anchor="lm")
        if ic == "spark": sparkle(d, x + 70 + font("m", 42).getlength(s) + 20, y, 24, GOLD, 255 * a)
    d.rounded_rectangle([40, 900, 515, 1000], 24, fill=ROSE); d.text((277, 950), "Suivre", font=font("b", 42), fill=WHITE, anchor="mm")
    d.rounded_rectangle([535, 900, 1000, 1000], 24, fill=LIGHT); d.text((767, 950), "Envoyer un message", font=font("b", 40), fill=INK, anchor="mm")
    for i, (lab, nm) in enumerate([("Prestations", "apres"), ("Information", "info")]):
        x = 150 + i * 250; y = 1170
        hi = i == 1 and 10.6 < t < 10.95
        d.ellipse([x - 92, y - 92, x + 92, y + 92], outline=ROSE if hi else (214, 210, 208), width=6)
        S.alpha_composite(round_img(nm, 160), (x - 80, y - 80)); d = ImageDraw.Draw(S)
        d.text((x, y + 135), lab, font=font("m", 36), fill=INK, anchor="mm")
    tap(S, 400, 1170, t, 10.75)
    y = 1400; d.line([(0, y), (1040, y)], fill=LIGHT, width=2); d.rectangle([0, y + 100, 346, y + 104], fill=INK)
    for a in range(3):
        for b in range(3): d.rectangle([143 + a * 22, y + 25 + b * 22, 159 + a * 22, y + 41 + b * 22], fill=INK)
    d.rounded_rectangle([494, y + 27, 546, y + 79], 14, outline=GREY, width=5); d.ellipse([840, y + 26, 892, y + 78], outline=GREY, width=5)
    for i, nm in enumerate(["cherry", "apres", "avant"]):
        p = out_cubic(prog(t, 8.5 + i * 0.12, 8.85 + i * 0.12))
        if p > 0: safe_comp(S, fade(cover(nm, 345, 460), p), 1 + i * 347, y + 110 + (1 - p) * 50)
    nav_bar(S, 4); return S

INFO_LINES = [(625, 715), (825, 885), (990, 1110), (1210, 1325), (1435, 1495)]   # y ranges in the original info image
def screen_info(t):
    S = Image.new("RGBA", (SW, SH), (249, 245, 242, 255))
    im = fit_w(photo("info"), 1040) if not hasattr(screen_info, "c") else screen_info.c
    screen_info.c = im; k = 1040 / photo("info").width; oy = (SH - im.height) / 2
    lay = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for i, (y0, y1) in enumerate(INFO_LINES):   # soft rose marker sweeping under each rule
        p = out_cubic(prog(t, 11.35 + i * 0.28, 11.75 + i * 0.28))
        if p > 0:
            ya, yb = oy + y0 * k, oy + y1 * k
            d.rounded_rectangle([80, ya - 8, 80 + 880 * p, yb + 8], 30, fill=BLUSH + (150,))
            sparkle(d, 80 + 880 * p, (ya + yb) / 2, 26 * (1 - prog(t, 11.75 + i * 0.28, 12.0 + i * 0.28)), GOLD, 255)
    safe_comp(S, im, 0, oy); S.alpha_composite(fade(lay, 0.55))
    multiply = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); S2 = S
    story_header(S2, t, 11.0, 13.1, 1, 2, "Information", light_text=False); story_footer(S2, light=False)
    tap(S2, 400, 2090, t, 12.95)
    return S2

MSGS = [(13.55, "photo", None), (13.95, "out", ["Bonjour ! Voici mon inspiration"]), (14.4, "out", ["Dispo samedi après-midi ?"]),
        (15.25, "in", ["Avec plaisir ! Je te confirme", "ton rendez-vous 24 h avant"])]
def bubble(lines, side):
    f = font("m", 40); wd = max(f.getlength(s) for s in lines) + 64; ht = 54 * len(lines) + 46
    im = Image.new("RGBA", (int(wd), int(ht)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if side == "out":
        g = rounded(grad(int(wd), int(ht), (236, 150, 160), (200, 110, 140)), 46); im.alpha_composite(g); col = WHITE
    else: d.rounded_rectangle([0, 0, wd - 1, ht - 1], 46, fill=LIGHT); col = INK
    d = ImageDraw.Draw(im)
    for i, s in enumerate(lines): d.text((32, 22 + i * 54), s, font=f, fill=col)
    return im

def screen_dm(t):
    S = Image.new("RGBA", (SW, SH), WHITE + (255,)); d = ImageDraw.Draw(S); status_bar(d)
    d.line([(70, 215), (45, 240), (70, 265)], fill=INK, width=7)
    S.alpha_composite(round_img("avatar", 100), (100, 190)); d = ImageDraw.Draw(S)
    d.text((225, 215), NAME, font=font("b", 42), fill=INK, anchor="lm"); d.text((225, 265), "Prothésiste ongulaire", font=font("m", 32), fill=GREY, anchor="lm")
    d.line([(0, 320), (1040, 320)], fill=LIGHT, width=2)
    S.alpha_composite(round_img("avatar", 180), (430, 380)); d = ImageDraw.Draw(S)
    d.text((520, 600), NAME, font=font("b", 42), fill=INK, anchor="mm"); d.text((520, 650), "Rouen / 76", font=font("m", 34), fill=GREY, anchor="mm")
    y = 740
    for t0, side, lines in MSGS:
        if side == "in" and t0 - 0.55 < t < t0:
            dots = Image.new("RGBA", (150, 90), (0, 0, 0, 0)); dd = ImageDraw.Draw(dots); dd.rounded_rectangle([0, 0, 149, 89], 45, fill=LIGHT)
            for k in range(3):
                o = 7 * math.sin(t * 14 - k); dd.ellipse([32 + k * 32, 36 + o, 52 + k * 32, 56 + o], fill=GREY)
            S.alpha_composite(dots, (40, y))
        if t < t0: break
        p = out_back(prog(t, t0, t0 + 0.3))
        if side == "photo":
            b = rounded(cover("cherry", 460, 600), 40)
        else: b = bubble(lines, side)
        bs = b.resize((max(1, int(b.width * p)), max(1, int(b.height * p))), Image.LANCZOS)
        x = 40 if side == "in" else 1000 - bs.width
        S.alpha_composite(fade(bs, clamp(p)), (int(x), int(y + b.height - bs.height))); y += b.height + 20
    d = ImageDraw.Draw(S)
    d.rounded_rectangle([30, 2040, 1010, 2150], 55, fill=LIGHT)
    d.ellipse([45, 2055, 125, 2135], fill=ROSE); d.rounded_rectangle([67, 2080, 103, 2110], 6, outline=WHITE, width=4)
    d.text((150, 2095), "Votre message…", font=font("m", 40), fill=GREY, anchor="lm")
    return S

def screen_at(t):
    if t < 5.0: return screen_story_ba(t)
    if t < 8.0: return screen_feed(t)
    if t < 11.0: return screen_profile(t)
    if t < 13.1: return screen_info(t)
    return screen_dm(t)

# ------------------------------------------------------------------ rose-gold phone in 3D
PW, PH, PD = 560, 1140, 54
@lru_cache(None)
def slice_img(k, n, q):
    u = k / (n - 1); c = q / 20; band = math.exp(-((u - c) / 0.16) ** 2); soft = math.exp(-((u - 0.5) / 0.45) ** 2)
    col = mix(mix((120, 86, 72), (196, 150, 128), soft), (255, 232, 215), band * 0.9)
    im = Image.new("RGBA", (140, 285), (0, 0, 0, 0)); ImageDraw.Draw(im).rounded_rectangle([0, 0, 139, 284], 20, fill=col); return im

@lru_cache(None)
def button_img(q):
    c = q / 20; g = np.linspace(0, 1, 24)[None, :, None] * np.ones((120, 1, 1)); band = np.exp(-((g - c) / 0.25) ** 2)
    arr = np.array([150, 108, 90]) * (1 - band) + np.array([255, 228, 210]) * band
    body = Image.fromarray(arr.astype(np.uint8)).convert("RGBA"); m = Image.new("L", (24, 120), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, 23, 119], 11, fill=255); im = Image.new("RGBA", (24, 120), (0, 0, 0, 0)); im.paste(body, (0, 0), m); return im

BUTTONS = [(+1, -270, -120), (-1, -350, -300), (-1, -240, -150), (-1, -110, -20)]
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
    d.rounded_rectangle([0, 0, PW * 2 - 1, PH * 2 - 1], 160, fill=(8, 7, 7))
    d.rounded_rectangle([2, 2, PW * 2 - 3, PH * 2 - 3], 158, outline=(200, 170, 150), width=3)
    d.rounded_rectangle([7, 7, PW * 2 - 8, PH * 2 - 8], 153, outline=(30, 27, 26), width=4)
    m = Image.new("L", (SW, SH), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, SW - 1, SH - 1], 124, fill=255)
    return im, m

def phone_face(screen, glare):
    base, m = face_base(); im = base.copy(); im.paste(screen, (40, 40), m); d = ImageDraw.Draw(im)
    d.rounded_rectangle([PW - 150, 70, PW + 150, 150], 40, fill=(0, 0, 0))
    d.ellipse([PW + 70, 92, PW + 106, 128], fill=(14, 16, 26)); d.ellipse([PW + 80, 100, PW + 90, 110], fill=(50, 60, 90))
    gx, gy = glare; g = Image.new("L", (140, 285), 0); gd = ImageDraw.Draw(g); x = lerp(-60, 200, gx)
    gd.ellipse([20 + gx * 60 - 90, -60 + gy * 40, 20 + gx * 60 + 90, 120 + gy * 40], fill=16)
    gd.polygon([(x, 0), (x + 34, 0), (x - 96, 285), (x - 130, 285)], fill=24)
    gd.polygon([(x + 52, 0), (x + 60, 0), (x - 70, 285), (x - 78, 285)], fill=18)
    g = g.filter(ImageFilter.GaussianBlur(5)).resize(im.size, Image.BILINEAR)
    gl = Image.new("RGBA", im.size, (255, 255, 255, 0)); gl.putalpha(Image.fromarray(np.minimum(np.array(g), np.array(im.getchannel("A")))))
    im.alpha_composite(gl); return im

@lru_cache(None)
def phone_back():
    im = Image.new("RGBA", (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, PW - 1, PH - 1], 80, fill=(214, 182, 164)); d.rounded_rectangle([40, 40, 250, 250], 50, fill=(196, 164, 146))
    for cx, cy in [(95, 95), (195, 95), (95, 195)]: d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(15, 15, 18), outline=(150, 120, 104), width=6)
    return im

def corners(C, M, dz):
    loc = np.array([[-PW / 2, -PH / 2, dz], [PW / 2, -PH / 2, dz], [PW / 2, PH / 2, dz], [-PW / 2, PH / 2, dz]])
    return loc @ M.T + C

def draw_phone(L, C, M, screen, glare):
    fp = corners(C, M, -PD / 2)
    if fp[:, 2].min() < 150: return
    face = project(fp); vis = area(face) > 0; n = 14; q = int(clamp(10 + glare[0] * 8 - 4, 1, 19))
    SL = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    for k in (range(n) if vis else range(n - 1, -1, -1)):
        pts = project(corners(C, M, lerp(PD / 2, -PD / 2 + 1, k / (n - 1))))
        warp_clip(SL, slice_img(k, n, q), [(x / 2, y / 2) for x, y in pts])
    L.alpha_composite(SL.resize((W, H), Image.BILINEAR)); draw_buttons(L, C, M, q)
    if vis: warp_clip(L, phone_face(screen, glare), face)
    else:
        b = project(corners(C, M, PD / 2 + 1)); warp_clip(L, phone_back(), [b[1], b[0], b[3], b[2]])

# camera keys (t, u, v, z, rx, ry, rz): phone-face point (u, v) is centred on screen at depth z
KEYS = [(1.5, 0, 0, 5000, 25, -50, -20), (2.3, 0, 0, 1450, 6, -14, -4), (2.9, 0, 0, 1420, 4, -10, -2),
        (3.3, -120, 60, 950, 10, -22, -6), (3.95, 120, 60, 900, 8, 18, 5), (4.7, 0, 0, 1350, 0, 8, 2),
        (5.25, 0, -60, 1300, 6, -12, -3), (6.35, 0, -80, 960, 14, -20, -6), (7.3, 0, -60, 930, 10, -14, -4),
        (7.95, 0, 0, 1420, 0, 10, 3), (8.55, -60, -390, 820, 18, 22, 7), (9.6, -40, -260, 860, 14, 16, 5),
        (10.4, -120, 40, 900, 6, -16, -5), (10.95, 0, 0, 1420, 0, -6, -2), (11.4, 0, -200, 980, 12, 16, 5),
        (12.7, 0, 90, 980, -8, 12, 4), (13.15, 0, 0, 1420, 0, -8, -2), (13.85, 60, -120, 920, 12, -18, -5),
        (15.3, 30, 60, 900, 6, -12, -4), (15.9, 0, 0, 1320, 0, 6, 2), (16.45, 0, 0, 230, 0, 0, 170)]

def pose(t):
    if t <= KEYS[0][0]: k = list(KEYS[0])
    elif t >= KEYS[-1][0]: k = list(KEYS[-1])
    else:
        for a, b in zip(KEYS, KEYS[1:]):
            if a[0] <= t <= b[0]:
                x = (t - a[0]) / (b[0] - a[0]); sx = clamp((x - 0.55) / 0.45)
                e = in_out(x) + 0.05 * math.sin(math.pi * sx) * (1 if b[0] - a[0] < 1.2 else 0.4)
                k = [lerp(p, q, e) for p, q in zip(a, b)]; k[3] = lerp(a[3], b[3], in_out(x)); break
    _, u, v, z, rx, ry, rz = k
    rx += 1.6 * math.sin(t * 1.3); ry += 2.0 * math.sin(t * 0.9 + 1); rz += 0.8 * math.sin(t * 1.1)
    rx += 0.32 * math.sin(t * 7.3) + 0.18 * math.sin(t * 11.9 + 1.3) + 0.1 * math.sin(t * 17.1 + 2)
    ry += 0.32 * math.sin(t * 6.1 + 2) + 0.18 * math.sin(t * 13.7 + 0.4) + 0.1 * math.sin(t * 19.3)
    rz += 0.22 * math.sin(t * 5.3 + 0.5) + 0.12 * math.sin(t * 9.7 + 3)
    u += 2.2 * math.sin(t * 8.7) + 1.2 * math.sin(t * 14.3 + 1); v += 2.2 * math.sin(t * 9.9 + 1) + 1.2 * math.sin(t * 15.1)
    M = rotm(rx, ry, rz); C = np.array([0, 0, z]) - M @ np.array([u, v, -PD / 2])
    return C, M, (ry, rx), z

def phone_motion(t):
    C0, M0, _, _ = pose(t); C1, M1, _, _ = pose(t + 1 / FPS)
    return (np.array(project(corners(C1, M1, 0))) - np.array(project(corners(C0, M0, 0)))).mean(axis=0)

def motion_blur(D, v):
    L = float(np.hypot(*v)) * 0.9
    if L < 4: return D
    L = min(L, 140); n = int(min(12, 3 + L / 10)); ux, uy = v / np.hypot(*v)
    pm = premul(D); acc = np.zeros_like(pm)
    for k in range(n):
        o = (k / (n - 1) - 0.5) * L; acc += np.roll(np.roll(pm, int(round(uy * o)), axis=0), int(round(ux * o)), axis=1)
    return unpremul(acc / n)

SHUTTER = 0.75
SCROLLS = [(5.0, 5.5), (2.95, 4.0)]
def device_at(t, screen=None):
    C, M, (ry, rx), _ = pose(t); D = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_phone(D, C, M, screen if screen is not None else screen_at(t), (0.5 + ry / 120, 0.5 + rx / 60)); return D

def render_device(t):
    v = phone_motion(t); L = float(np.hypot(*v)) * SHUTTER
    n = 1 if L < 2.0 else min(9, 1 + int(L / 2.5))
    if n == 1: D = device_at(t)
    else:
        scr = None if any(a <= t <= b for a, b in SCROLLS) else screen_at(t); acc = None
        for k in range(n):
            pm = premul(device_at(t + (k / (n - 1) - 0.5) * SHUTTER / FPS, scr)); acc = pm if acc is None else acc + pm
        D = unpremul(acc / n)
        if L / (n - 1) > 2.5: D = motion_blur(D, v * (L / (n - 1)) / max(1e-3, float(np.hypot(*v))) / 0.9)
    return depth_of_field(D, t)

def depth_of_field(D, t):
    C, M, _, _ = pose(t); zf = pose(t - 0.12)[3]
    nrm = M @ np.array([0, 0, -1.0]); d = float(nrm @ (C + M @ np.array([0, 0, -PD / 2])))
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
# ------------------------------------------------------------------ aesthetic studio decor
DECOR = {}
def leaf(d, x0, y0, ang, scale):
    """Palm frond silhouette (stem + leaflets) used as a sunlight shadow."""
    a = math.radians(ang); pts = []
    for i in range(16):
        u = i / 15; sx = x0 + math.cos(a) * 260 * scale * u + math.sin(u * 3) * 10 * scale
        sy = y0 + math.sin(a) * 260 * scale * u
        pts.append((sx, sy))
    d.line(pts, fill=255, width=max(2, int(4 * scale)))
    for i, (sx, sy) in enumerate(pts[2:], 2):
        ln = 95 * scale * math.sin(math.pi * (i / 16)) + 15 * scale
        for sgn in (-1, 1):
            b = a + sgn * 1.05 + 0.25 * math.sin(i)
            ex, ey = sx + math.cos(b) * ln, sy + math.sin(b) * ln
            nx, ny = -math.sin(b) * 7 * scale, math.cos(b) * 7 * scale
            d.polygon([(sx, sy), ((sx + ex) / 2 + nx, (sy + ey) / 2 + ny), (ex, ey), ((sx + ex) / 2 - nx, (sy + ey) / 2 - ny)], fill=255)

def marquee_strip(text_parts, f, col, alpha):
    unit_w = sum(f.getlength(s) for s in text_parts) + 140 * len(text_parts)
    strip = Image.new("RGBA", (int(unit_w * 3), 240), (0, 0, 0, 0)); d = ImageDraw.Draw(strip); x = 0
    for _ in range(3):
        for s in text_parts:
            d.text((x, 120), s, font=f, fill=col + (alpha,), anchor="lm"); x += f.getlength(s) + 70
            sparkle(d, x, 120, 26, GOLD, alpha + 40); x += 70
    return strip, unit_w

def decor_static():
    if DECOR: return DECOR
    rng = np.random.default_rng(12)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.clip(np.sqrt(((xx - W * 0.45) / W) ** 2 + ((yy - H * 0.4) / (H * 0.8)) ** 2), 0, 1)[..., None]
    base = np.array([246, 238, 229], np.float32) * (1 - r) + np.array([226, 210, 195], np.float32) * r
    mott = np.asarray(Image.fromarray(rng.normal(128, 40, (H // 40, W // 40)).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    base += ((mott - 128) / 128 * 5)[..., None] + rng.normal(0, 2.2, (H, W, 1))     # plaster texture
    wall = Image.fromarray(base.clip(0, 255).astype(np.uint8)).convert("RGBA")
    arch = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(arch)
    d.rounded_rectangle([600, 120, 1000, 1000], 200, fill=(232, 214, 198, 255))     # arch "mirror" panel
    d.rounded_rectangle([630, 150, 970, 970], 170, outline=(214, 186, 160, 255), width=6)
    cx, cy = 60, H + 40   # boho rainbow arches
    for rr, col in [(620, (205, 140, 112)), (520, (238, 196, 184)), (420, (226, 200, 168)), (320, (244, 226, 214)), (220, (212, 160, 132))]:
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col + (255,))
    d.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=(246, 238, 229, 255))
    sh = arch.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((W, H))
    shadow = Image.new("RGBA", (W, H), (120, 90, 70, 0)); shadow.putalpha(sh.point(lambda v: int(v * 0.25)))
    wall.alpha_composite(shadow, (14, 22)); wall.alpha_composite(arch)
    panes = Image.new("L", (W // 4, H // 4), 0); pd = ImageDraw.Draw(panes)
    for i in range(2):
        for j in range(3):
            x0, y0 = 20 + i * 70, 60 + j * 110
            pd.polygon([(x0, y0), (x0 + 60, y0 - 30), (x0 + 60, y0 + 70), (x0, y0 + 100)], fill=255)
    DECOR.update(wall=wall, panes=panes.filter(ImageFilter.GaussianBlur(4)),
                 m1=marquee_strip(["gwn.nails76", "Nail art", "Rouen"], font("serif_i", 150), BROWN, 46),
                 m2=marquee_strip(["Prothésiste ongulaire", "Prise de RDV en DM"], font("serif", 96), BROWN, 26))
    return DECOR

def background(t):
    dc = decor_static(); im = dc["wall"].copy()
    for key, y, speed in (("m1", 70, 60), ("m2", 1745, -45)):   # slow scrolling banners
        strip, uw = dc[key]; off = (t * speed) % uw
        safe_comp(im, strip, -uw - off if speed > 0 else -uw + off, y)
    lm = Image.new("L", (W // 4, H // 4), 0); lm.paste(dc["panes"], (int(6 * math.sin(t * 0.2)), 0))
    lf = Image.new("L", (W // 4, H // 4), 0); ld = ImageDraw.Draw(lf)
    sway = 4 * math.sin(t * 0.9) + 1.5 * math.sin(t * 2.3)
    leaf(ld, 250, 40, 145 + sway, 0.62); leaf(ld, 262, 120, 168 + sway * 1.3, 0.5)
    lf = lf.filter(ImageFilter.GaussianBlur(2.5))
    lmap = np.asarray(lm, np.float32) / 255 * (1 - np.asarray(lf, np.float32) / 255 * 0.75)
    lfull = np.asarray(Image.fromarray((lmap * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255
    shade = np.asarray(lf.resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255
    arr = np.asarray(im.convert("RGB"), np.float32)
    arr = arr * (0.93 + 0.13 * lfull - 0.13 * shade) + np.array([255, 214, 170], np.float32) * 0.09 * lfull
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    for k in range(9):
        x = (k * 263 + 40 * math.sin(t * 0.6 + k)) % W; y = (k * 487 - t * 30 * (1 + k % 3)) % H
        sparkle(d, x, y, 10 + (k % 4) * 5, WHITE, 150 * (0.5 + 0.5 * math.sin(t * 2.2 + k * 1.7)))
    return im

def intro(L, t):
    if t >= 1.65: return
    d = ImageDraw.Draw(L)
    for k in range(18):   # sparkles bursting in
        p = prog(t, 0.05 + k * 0.03, 0.9 + k * 0.03); ang = k * 2.39
        rr = 200 + 420 * out_cubic(p); a = 255 * math.sin(math.pi * p)
        sparkle(d, W / 2 + math.cos(ang) * rr, 820 + math.sin(ang) * rr, 30 * math.sin(math.pi * p) + 2, GOLD if k % 2 else WHITE, a)
    s = out_back(prog(t, 0.15, 0.6), 2.0) * (1 + 7 * in_cubic(prog(t, 1.2, 1.62)))
    if s > 0.02 and s < 9:
        dd = int(380 * s); av = round_img("avatar", 380, 0).resize((dd, dd), Image.LANCZOS)
        ring = Image.new("RGBA", (dd + 60, dd + 60), (0, 0, 0, 0)); rd = ImageDraw.Draw(ring)
        sweep = 360 * out_cubic(prog(t, 0.35, 1.0))
        for k in range(0, int(sweep), 3):
            c = mix((250, 200, 150), ROSE, k / 360); a0 = -90 + k
            rd.arc([6, 6, dd + 54, dd + 54], a0, a0 + 4, fill=c, width=max(4, int(14 * s)))
        ring.alpha_composite(av, (30, 30)); al = 1 - smooth(prog(t, 1.48, 1.64))
        safe_comp(L, fade(ring, al), W / 2 - ring.width / 2, 820 - ring.height / 2)
        a = out_cubic(prog(t, 0.55, 0.85)) * (1 - smooth(prog(t, 1.15, 1.3)))
        if a > 0:
            tx = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); td = ImageDraw.Draw(tx)
            td.text((W / 2, 70), NAME, font=font("serif_i", 104), fill=BROWN, anchor="mm")
            td.text((W / 2, 160), "Prothésiste ongulaire · Rouen", font=font("m", 42), fill=GREY, anchor="mm")
            safe_comp(L, fade(tx, a), 0, 1080 + (1 - a) * 30)

def outro(L, t):
    if t < 16.45: return
    d = ImageDraw.Draw(L)
    for k in range(26):
        p = prog(t, 16.5 + (k % 9) * 0.05, 17.6 + (k % 9) * 0.05); ang = k * 2.39; rr = 160 + 600 * out_cubic(p)
        sparkle(d, W / 2 + math.cos(ang) * rr, 640 + math.sin(ang) * rr * 0.9, 34 * math.sin(math.pi * p) + 1, GOLD if k % 3 else WHITE, 255 * math.sin(math.pi * p))
    s = out_back(prog(t, 16.5, 16.95), 1.8)
    if s > 0.02:
        dd = int(330 * s); ring = round_img("avatar", 330, 12).resize((dd, dd), Image.LANCZOS)
        g = Image.new("RGBA", (W, 700), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([W / 2 - 230, 120, W / 2 + 230, 580], fill=(255, 255, 255, 160))
        safe_comp(L, g.filter(ImageFilter.GaussianBlur(60)), 0, 640 - 350); safe_comp(L, ring, W / 2 - dd / 2, 640 - dd / 2)
    items = [(NAME, font("serif_i", 120), BROWN, 930, 16.85), ("Prothésiste ongulaire · Rouen / 76", font("m", 44), GREY, 1050, 17.05)]
    for txt, f, col, y, t0 in items:
        a = out_cubic(prog(t, t0, t0 + 0.45))
        if a > 0:
            tx = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); ImageDraw.Draw(tx).text((W / 2, 100), txt, font=f, fill=col, anchor="mm")
            safe_comp(L, fade(tx, a), 0, y - 100 + (1 - a) * 36)
    lp = out_cubic(prog(t, 17.2, 17.7))
    if lp > 0: d.line([(W / 2 - 220 * lp, 1135), (W / 2 + 220 * lp, 1135)], fill=GOLD, width=3); sparkle(d, W / 2, 1135, 18 * lp, GOLD)
    pb = out_back(prog(t, 17.45, 17.85))
    if pb > 0.02:
        btn = Image.new("RGBA", (820, 150), (0, 0, 0, 0)); bd = ImageDraw.Draw(btn)
        btn.alpha_composite(rounded(grad(820, 150, (236, 150, 160), (200, 110, 140)), 75)); bd = ImageDraw.Draw(btn)
        ic_mail(bd, 130, 75, 54, WHITE); bd.text((440, 75), "Prise de RDV en DM", font=font("b", 50), fill=WHITE, anchor="mm")
        sp = prog(t, 18.0, 18.6)
        if 0 < sp < 1:
            band = Image.new("L", btn.size, 0); x = lerp(-200, 1020, sp)
            ImageDraw.Draw(band).polygon([(x, 0), (x + 120, 0), (x + 50, 150), (x - 70, 150)], fill=120)
            lt = Image.new("RGBA", btn.size, (255, 255, 255, 0)); lt.putalpha(Image.fromarray(np.minimum(np.array(band.filter(ImageFilter.GaussianBlur(10))), np.array(btn.getchannel("A")))))
            btn.alpha_composite(lt)
        pulse = pb * (1 + 0.035 * math.sin((t - 17.85) * 6) if t > 17.85 else 1)
        btn = btn.resize((int(820 * pulse), int(150 * pulse)), Image.LANCZOS); safe_comp(L, btn, W / 2 - btn.width / 2, 1290 - btn.height / 2)
    a = out_cubic(prog(t, 17.8, 18.2))
    if a > 0:
        tx = Image.new("RGBA", (W, 120), (0, 0, 0, 0)); ImageDraw.Draw(tx).text((W / 2, 60), "@" + NAME, font=font("b", 50), fill=BROWN, anchor="mm")
        safe_comp(L, fade(tx, a), 0, 1430 - 60)

# ------------------------------------------------------------------ compose & post
def compose(t):
    img = background(t); intro(img, t)
    if 1.5 <= t < 16.47:
        D = render_device(t); z = pose(t)[3]; o = 1500 / z
        sh = D.getchannel("A").resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
        shadow = Image.new("RGBA", (W, H), (90, 60, 45, 0)); shadow.putalpha(sh.point(lambda v: int(v * 0.42)))
        safe_comp(img, shadow, 45 * o, 85 * o)
        tight = D.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        sh2 = Image.new("RGBA", (W, H), (70, 45, 35, 0)); sh2.putalpha(tight.point(lambda v: int(v * 0.3)))
        safe_comp(img, sh2, 12 * o, 22 * o); img.alpha_composite(D)
    outro(img, t); return img

VIG = None
def post(img, t, fi):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        VIG = (1 - 0.22 * np.clip(r - 0.45, 0, 1) ** 1.5)[..., None].astype(np.float32)
    sw = math.sin(math.pi * prog(t, 16.0, 16.7))
    if sw > 0.02:
        acc = None
        for k in range(7):
            r = img.rotate(-(k - 3) * 6 * sw, Image.BILINEAR, center=(W / 2, H / 2), fillcolor=CREAM2 + (255,))
            acc = r if acc is None else Image.blend(acc, r, 1 / (k + 1))
        img = acc
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 215, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR), np.float32) * 0.5
    fl = (math.exp(-max(0, t - 16.47) * 9) * 0.55 if t >= 16.47 else 0) + 0.45 * math.sin(math.pi * prog(t, 1.4, 1.7))
    arr = arr + (255 - arr) * min(fl, 0.8)
    arr = arr * VIG + np.random.default_rng(fi).normal(0, 1.8, (H, W, 1)).astype(np.float32)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(compose(t), t, i).tobytes()

# ------------------------------------------------------------------ audio (chic lo-fi + sound design)
WHOOSH = [1.45, 3.2, 3.9, 4.65, 5.0, 6.25, 7.9, 8.5, 10.35, 10.9, 11.45, 13.1, 13.8, 15.85, 16.0]
TAPS = [6.48, 6.6, 7.85, 10.75, 12.95]
def make_audio(path, music=True):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(9)
    def add(sig, t0):
        i = int(t0 * sr)
        if i >= n or i < 0: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    if music:
        beat = 0.6   # 100 bpm
        chords = [(261.6, 329.6, 392, 493.9), (220, 261.6, 329.6, 392), (174.6, 220, 261.6, 329.6), (196, 246.9, 293.7, 349.2)]
        tk = T(0.4); kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-tk * 25)) * tk) * np.exp(-tk * 7) * 0.7
        ts = T(0.12); snap = Rn.uniform(-1, 1, len(ts)) * np.exp(-ts * 45) * 0.28
        th = T(0.03); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 120) * 0.07
        k = 0
        while k * beat < 16.4:
            t0 = k * beat; bar = (k // 4) % 4
            if t0 > 1.4:
                if k % 4 in (0, 2): add(kick, t0)
                if k % 4 in (1, 3): add(snap, t0)
                add(hat, t0 + beat / 2); add(hat * 0.6, t0 + beat * 0.75)
            if k % 4 == 0:
                tp = T(beat * 4); env = np.minimum(1, tp / 0.05) * np.exp(-tp * 0.7)
                keys = sum(np.sin(2 * np.pi * f * tp) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * tp)) for f in chords[bar]) * 0.045 * env
                add(keys, t0); add(np.sin(2 * np.pi * chords[bar][0] / 2 * tp) * env * 0.12, t0)
            tb = T(0.3); f = chords[bar][(k * 3) % 4] * 2
            add(np.sin(2 * np.pi * f * tb) * np.exp(-tb * 12) * 0.035, t0 + beat * 0.5)
            k += 1
        tp = T(2.6); add(sum(np.sin(2 * np.pi * f * tp) for f in (523.3, 659.3, 784, 987.8)) * np.exp(-tp * 1.2) * 0.06, 16.5)
    tw = T(0.35)
    for t0 in WHOOSH:
        nz = np.convolve(Rn.normal(0, 1, len(tw)), np.ones(8) / 8, "same"); add(nz * np.sin(np.pi * tw / 0.35) ** 2 * 0.22, t0)
    tc = T(0.03)
    for t0 in TAPS: add(np.sin(2 * np.pi * 1600 * tc) * np.exp(-tc * 160) * 0.3, t0)
    tg = T(0.25)
    for j in range(30):   # sparkle shimmer
        for base in (0.1, 3.05, 16.5):
            if j < 12: add(np.sin(2 * np.pi * Rn.uniform(3000, 6500) * tg) * np.exp(-tg * 22) * 0.05, base + Rn.uniform(0, 0.9))
    tpop = T(0.18); add(np.sin(2 * np.pi * np.cumsum(500 + 1400 * tpop / 0.18) / sr) * np.exp(-tpop * 18) * 0.28, 6.6)
    for t0, side, _ in MSGS:
        if side == "in":
            td = T(0.5); add((np.sin(2 * np.pi * 1318.5 * td) + 0.5 * np.sin(2 * np.pi * 1975 * td)) * np.exp(-td * 8) * 0.16, t0)
        else:
            ts2 = T(0.2); add(np.sin(2 * np.pi * np.cumsum(700 + 900 * ts2 / 0.2) / sr) * np.exp(-ts2 * 16) * 0.14, t0)
    fo = int(0.6 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.3) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
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
