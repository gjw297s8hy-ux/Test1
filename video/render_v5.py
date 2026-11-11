"""Motion design v5 (orange) : mockups 3D (téléphone + ordinateur portable), pièces et billets.
Offre : abonnement salle de sport 20 €/mois au lieu de 34 €.
Rendu :   python3 render_v5.py           -> promo_abonnement_v5.mp4 (1080x1920, 30 fps, 16 s)
Aperçu :  python3 render_v5.py 2 7.5     -> preview_2.png, preview_7.5.png"""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 16.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_abonnement_v5.mp4")
HANDLE = "@toncompte"   # <- remplace par ton pseudo / numéro

WHITE = (248, 248, 250); GREY = (150, 154, 168); ACC = (255, 122, 0); RED = (255, 70, 90)
DARK = (14, 15, 20); GOLD = (255, 196, 40); OLIVE = (125, 50, 0)
FONTS = "/usr/share/fonts/opentype/inter/"
FW = {"black": "Inter-Black.otf", "xb": "Inter-ExtraBold.otf", "b": "Inter-Bold.otf", "sb": "Inter-SemiBold.otf"}

@lru_cache(None)
def font(w, s): return ImageFont.truetype(FONTS + FW[w], s)

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def out_cubic(x): return 1 - (1 - x) ** 3
def in_cubic(x): return x ** 3
def in_out(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def smooth(x): return x * x * (3 - 2 * x)
def out_back(x, s=1.9): x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, x): return a + (b - a) * x
def mix(c1, c2, x): return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))

# ------------------------------------------------------------------ 2D compositing
def safe_comp(L, im, x, y):
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, L.width - x), min(im.height, L.height - y)
    if ex <= sx or ey <= sy: return
    L.alpha_composite(im, (x + sx, y + sy), (sx, sy, ex, ey))

def fade(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a))); return im

def blurred(im, r):
    if r < 0.6: return im, 0
    pad = int(r * 2.5) + 2
    c = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); c.paste(im, (pad, pad))
    return c.filter(ImageFilter.GaussianBlur(r)), pad

def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def warp(L, img, pts, a=1.0, blur=0.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys))
    if x1 - x0 < 2 or y1 - y0 < 2 or x1 - x0 > 3 * W or y1 - y0 > 3 * H: return
    if x1 < 0 or y1 < 0 or x0 > L.width or y0 > L.height: return
    try: co = persp_coeffs([(px - x0, py - y0) for px, py in pts], [(0, 0), (img.width, 0), (img.width, img.height), (0, img.height)])
    except np.linalg.LinAlgError: return
    im = img.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, co, Image.BICUBIC)
    im, pad = blurred(im, blur)
    safe_comp(L, fade(im, a), x0 - pad, y0 - pad)

# ------------------------------------------------------------------ tiny 3D engine
def rotm(rx=0.0, ry=0.0, rz=0.0):
    ax, ay, az = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz

CAM = {"R": np.eye(3), "piv": np.array([0.0, 100.0, 1700.0]), "f": 1600.0, "sh": (0.0, 0.0)}
FOCUS = 1650.0

def view(P): return (np.asarray(P, float) - CAM["piv"]) @ CAM["R"].T + CAM["piv"]

def project(Q):
    f = CAM["f"]; sx, sy = CAM["sh"]
    return [(W / 2 + f * q[0] / q[2] + sx, H / 2 + f * q[1] / q[2] + sy) for q in Q]

def quad(L, img, P, a=1.0, cull=True, dof=False):
    """Draw an image on a 3D quad (world corners TL, TR, BR, BL). Returns True if front-facing."""
    Q = view(P)
    if Q[:, 2].min() < 160: return False
    pts = project(Q)
    area = sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))
    if cull and area <= 0: return False
    blur = float(min(18.0, abs(FOCUS / Q[:, 2].mean() - 1) * 16)) if dof else 0.0
    warp(L, img, pts, a, blur); return area > 0

def plane(C, M, w, h, dz=0.0):
    loc = np.array([[-w / 2, -h / 2, dz], [w / 2, -h / 2, dz], [w / 2, h / 2, dz], [-w / 2, h / 2, dz]])
    return loc @ M.T + C

def front_visible(P):
    pts = project(view(P))
    return sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4)) > 0

# ------------------------------------------------------------------ assets
@lru_cache(None)
def text3d(s, size, face=WHITE, side=None, weight="black", depth=None):
    f = font(weight, size); l, t, r, b = f.getbbox(s)
    depth = depth if depth is not None else max(3, int(size * 0.07))
    side = side or mix(face, (0, 0, 0), 0.55)
    pad = 26; mask = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), s, font=f, fill=255)
    im = Image.new("RGBA", (mask.width + depth + 8, mask.height + depth + 8), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 150), (int(depth * 0.8), int(depth * 1.5)), mask)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(3, depth))))
    for k in range(depth, 0, -1):
        im.paste(mix(side, (0, 0, 0), 0.5 * k / depth) + (255,), (int(k * 0.4), k), mask)
    grad = Image.linear_gradient("L").resize(mask.size)
    faceim = Image.composite(Image.new("RGBA", mask.size, mix(face, (0, 0, 0), 0.18) + (255,)), Image.new("RGBA", mask.size, face + (255,)), grad)
    im.paste(faceim, (0, 0), mask); return im

def reveal(L, img, cx, cy, p, a=1.0, s=1.0):
    """Mask reveal: text slides up from an invisible baseline."""
    if p <= 0 or a <= 0: return
    if s != 1: img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    p = out_cubic(clamp(p)); h = img.height; vis = max(1, int(h * p))
    safe_comp(L, fade(img.crop((0, 0, img.width, vis)), a), cx - img.width / 2, cy - h / 2 + (h - vis))

def shine(img, p, width=0.2, strength=170):
    if p <= 0 or p >= 1: return img
    w, h = img.size; x = lerp(-0.4 * w, 1.4 * w, p); bw = w * width
    band = Image.new("L", img.size, 0)
    ImageDraw.Draw(band).polygon([(x, 0), (x + bw, 0), (x + bw - h * 0.5, h), (x - h * 0.5, h)], fill=strength)
    a = np.minimum(np.array(band.filter(ImageFilter.GaussianBlur(bw * 0.2)), np.uint16), np.array(img.getchannel("A"), np.uint16))
    light = Image.new("RGBA", img.size, (255, 255, 255, 0)); light.putalpha(Image.fromarray(a.astype(np.uint8)))
    out = img.copy(); out.alpha_composite(light); return out

@lru_cache(None)
def coin_img(label="€"):
    S = 300; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=(190, 130, 10)); d.ellipse([10, 10, S - 11, S - 11], fill=GOLD)
    d.ellipse([34, 34, S - 35, S - 35], outline=(205, 140, 0), width=8)
    for k in range(36):
        a = 2 * math.pi * k / 36; d.line([(S / 2 + 132 * math.cos(a), S / 2 + 132 * math.sin(a)), (S / 2 + 142 * math.cos(a), S / 2 + 142 * math.sin(a))], fill=(215, 150, 10), width=4)
    t = text3d(label, 150, (255, 236, 160), (160, 100, 0), depth=8)
    im.alpha_composite(t, (int(S / 2 - t.width / 2 + 4), int(S / 2 - t.height / 2 + 4)))
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(hl).ellipse([40, 30, 170, 120], fill=(255, 255, 255, 90))
    im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(20)))
    return im

@lru_cache(None)
def bill_img():
    w, h = 440, 200; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = Image.linear_gradient("L").rotate(90).resize((w, h))
    base = Image.composite(Image.new("RGBA", (w, h), (150, 205, 140, 255)), Image.new("RGBA", (w, h), (110, 170, 105, 255)), g)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 10, fill=255)
    im.paste(base, (0, 0), m); d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, w - 11, h - 11], 8, outline=(40, 95, 45), width=4)
    d.rounded_rectangle([22, 22, w - 23, h - 23], 6, outline=(70, 130, 70), width=2)
    d.ellipse([w / 2 - 62, h / 2 - 62, w / 2 + 62, h / 2 + 62], fill=(95, 155, 95), outline=(40, 95, 45), width=4)
    d.text((w / 2, h / 2 + 4), "$", font=font("black", 100), fill=(30, 80, 35), anchor="mm")
    for x, y in [(52, 48), (w - 52, 48), (52, h - 48), (w - 52, h - 48)]:
        d.text((x, y), "100", font=font("xb", 30), fill=(30, 80, 35), anchor="mm")
    return im

# ------------------------------------------------------------------ phone
PW, PH, PD = 560, 1140, 54
@lru_cache(None)
def phone_slice(k, n):
    u = k / (n - 1); band = math.exp(-((u - 0.5) / 0.22) ** 2)
    col = mix((38, 40, 46), (175, 178, 188), band)
    im = Image.new("RGBA", (PW // 2, PH // 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, PW // 2 - 1, PH // 2 - 1], 40, fill=col)
    return im

@lru_cache(None)
def phone_back():
    im = Image.new("RGBA", (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, PW - 1, PH - 1], 80, fill=(52, 55, 64))
    d.rounded_rectangle([40, 40, 250, 250], 50, fill=(36, 38, 44))
    for cx, cy in [(95, 95), (195, 95), (95, 195)]:
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(15, 15, 18), outline=(90, 92, 100), width=6)
    return im

def phone_face(screen, glare):
    im = Image.new("RGBA", (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, PW - 1, PH - 1], 80, fill=(6, 6, 8))
    m = Image.new("L", (520, 1100), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, 519, 1099], 62, fill=255)
    im.paste(screen, (20, 20), m)
    d.rounded_rectangle([PW / 2 - 70, 36, PW / 2 + 70, 76], 20, fill=(0, 0, 0))
    g = Image.new("L", (PW, PH), 0); x = lerp(-300, PW + 300, glare)
    ImageDraw.Draw(g).polygon([(x, 0), (x + 220, 0), (x - 380, PH), (x - 600, PH)], fill=40)
    gl = Image.new("RGBA", (PW, PH), (255, 255, 255, 0))
    gl.putalpha(Image.fromarray(np.minimum(np.array(g.filter(ImageFilter.GaussianBlur(30))), np.array(im.getchannel("A")))))
    im.alpha_composite(gl); return im

def draw_phone(L, C, M, screen, glare=0.5):
    face = plane(C, M, PW, PH, -PD / 2)
    n = 12; vis = front_visible(face)
    order = range(n) if vis else range(n - 1, -1, -1)
    for k in order:
        dz = lerp(PD / 2, -PD / 2 + 1, k / (n - 1))
        quad(L, phone_slice(k, n), plane(C, M, PW, PH, dz), cull=False)
    if vis: quad(L, phone_face(screen, glare), face, cull=False)
    else:
        b = plane(C, M, PW, PH, PD / 2 + 1); quad(L, phone_back(), [b[1], b[0], b[3], b[2]], cull=False)

# ------------------------------------------------------------------ laptop
BW, BD, BT, LH = 1000, 680, 26, 640
@lru_cache(None)
def deck_img():
    im = Image.new("RGBA", (BW, BD), (0, 0, 0, 0))
    g = Image.linear_gradient("L").resize((BW, BD))
    im.paste(Image.composite(Image.new("RGBA", (BW, BD), (150, 153, 162, 255)), Image.new("RGBA", (BW, BD), (196, 199, 207, 255)), g))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([110, 50, BW - 110, 400], 14, fill=(34, 35, 40))
    kw, kh = (BW - 240) / 14, (350 - 20) / 6
    for r in range(6):
        for c in range(14):
            x0, y0 = 120 + c * kw + 4, 60 + r * kh + 4
            d.rounded_rectangle([x0, y0, x0 + kw - 8, y0 + kh - 8], 6, fill=(18, 18, 21), outline=(48, 49, 55))
    d.rounded_rectangle([330, 440, BW - 330, BD - 30], 18, fill=(178, 181, 190), outline=(135, 138, 146), width=3)
    return im

@lru_cache(None)
def alu(w, h, c1=(170, 173, 182), c2=(120, 123, 132)):
    g = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGBA", (w, h), c2 + (255,)), Image.new("RGBA", (w, h), c1 + (255,)), g)

@lru_cache(None)
def lid_back():
    im = alu(BW, LH, (185, 188, 196), (150, 153, 162)).copy()
    m = Image.new("L", (BW, LH), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, BW - 1, LH - 1], 30, fill=255)
    out = Image.new("RGBA", (BW, LH), (0, 0, 0, 0)); out.paste(im, (0, 0), m); return out

def lid_face(screen):
    im = Image.new("RGBA", (BW, LH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, BW - 1, LH - 1], 30, fill=(8, 8, 10)); d.rectangle([0, LH - 40, BW, LH], fill=(8, 8, 10))
    im.paste(screen, (40, 30)); d.ellipse([BW / 2 - 6, 10, BW / 2 + 6, 22], fill=(30, 30, 36))
    d.rectangle([0, LH - 22, BW, LH], fill=(28, 29, 33))
    return im

def draw_laptop(L, C, M, theta, screen):
    def w(p): return np.array(p, float) @ M.T + C
    hb, hd = BW / 2, BD / 2
    quad(L, deck_img(), w([[-hb, 0, hd], [hb, 0, hd], [hb, 0, -hd], [-hb, 0, -hd]]))
    quad(L, alu(BW, BT, (150, 153, 162), (95, 98, 106)), w([[-hb, 0, -hd], [hb, 0, -hd], [hb, BT, -hd], [-hb, BT, -hd]]))
    quad(L, alu(BD, BT, (140, 143, 152), (90, 93, 100)), w([[hb, 0, -hd], [hb, 0, hd], [hb, BT, hd], [hb, BT, -hd]]))
    quad(L, alu(BD, BT, (140, 143, 152), (90, 93, 100)), w([[-hb, 0, hd], [-hb, 0, -hd], [-hb, BT, -hd], [-hb, BT, hd]]))
    th = math.radians(theta); hz = hd - 12
    v = np.array([0, -math.sin(th), -math.cos(th)]); nb = np.array([0, -math.cos(th), math.sin(th)])
    hl, hr = np.array([-hb, -2, hz]), np.array([hb, -2, hz])
    scr = w([hl + v * LH, hr + v * LH, hr, hl])
    back = w([hr + v * LH + nb * 14, hl + v * LH + nb * 14, hl + nb * 14, hr + nb * 14])
    vis = front_visible(scr)
    if vis:
        quad(L, lid_back(), back, cull=False)
        for k in range(1, 4): quad(L, alu(BW // 4, LH // 4, (120, 123, 132), (100, 103, 110)), w([hl + v * LH + nb * 3.5 * k, hr + v * LH + nb * 3.5 * k, hr + nb * 3.5 * k, hl + nb * 3.5 * k]), cull=False)
        quad(L, lid_face(screen), scr, cull=False)
    else:
        for k in range(1, 4): quad(L, alu(BW // 4, LH // 4, (120, 123, 132), (100, 103, 110)), w([hl + v * LH + nb * 3.5 * k, hr + v * LH + nb * 3.5 * k, hr + nb * 3.5 * k, hl + nb * 3.5 * k]), cull=False)
        quad(L, lid_back(), back, cull=False)

# ------------------------------------------------------------------ app screens
@lru_cache(None)
def app_bg(w, h):
    im = Image.new("RGBA", (w, h), (12, 14, 20, 255))
    gl = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse([-w * 0.3, -h * 0.25, w * 1.3, h * 0.25], fill=ACC + (34,))
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(60))); return im

def status_bar(d, w):
    d.text((40, 26), "9:41", font=font("sb", 28), fill=WHITE)
    d.rounded_rectangle([w - 92, 32, w - 48, 52], 6, outline=WHITE, width=3); d.rectangle([w - 87, 37, w - 60, 47], fill=WHITE)

def check(d, x, y, r=18):
    d.ellipse([x - r, y - r, x + r, y + r], fill=ACC); d.line([(x - 8, y), (x - 2, y + 7), (x + 9, y - 7)], fill=DARK, width=5)

def screen_offer(t):
    S = app_bg(520, 1100).copy(); d = ImageDraw.Draw(S); status_bar(d, 520)
    d.text((36, 100), "Abonnements", font=font("xb", 46), fill=WHITE)
    d.text((36, 160), "Salle de sport · mensuel", font=font("sb", 26), fill=GREY)
    d.rounded_rectangle([28, 220, 492, 700], 34, fill=(26, 28, 38), outline=(52, 56, 72), width=2)
    d.rounded_rectangle([56, 250, 196, 292], 21, fill=ACC); d.text((126, 271), "MENSUEL", font=font("b", 22), fill=DARK, anchor="mm")
    d.text((56, 316), "Basic-Fit", font=font("xb", 46), fill=WHITE)
    d.text((56, 376), "Accès salle · paiement au mois", font=font("sb", 23), fill=GREY)
    pr = prog(t, 3.0, 3.8); val = lerp(34, 20, out_cubic(pr))
    box = Image.new("RGBA", (440, 120), (0, 0, 0, 0)); bd = ImageDraw.Draw(box); f = font("black", 92)
    col = ACC if pr >= 1 else WHITE
    n = math.ceil(val - 1e-6); fr = n - val
    bd.text((0, 10 - fr * 110), f"{n},00 €", font=f, fill=col)
    if fr > 0.001: bd.text((0, 10 + (1 - fr) * 110), f"{n - 1},00 €", font=f, fill=col)
    S.alpha_composite(box, (52, 430))
    d.text((58, 552), "par mois", font=font("sb", 28), fill=GREY)
    if t > 3.8:
        a = int(255 * out_cubic(prog(t, 3.8, 4.1)))
        d.text((58, 610), "34,00 €", font=font("xb", 34), fill=GREY + (a,))
        d.line([(54, 634), (196, 622)], fill=RED + (a,), width=5)
        sc = out_back(prog(t, 3.85, 4.2))
        if sc > 0.05:
            pill = Image.new("RGBA", (150, 56), (0, 0, 0, 0)); pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle([0, 0, 149, 55], 28, fill=RED); pd.text((75, 28), "-41 %", font=font("black", 30), fill=WHITE, anchor="mm")
            pill = pill.resize((max(1, int(150 * sc)), max(1, int(56 * sc))), Image.LANCZOS)
            S.alpha_composite(pill, (int(300 - pill.width / 2), int(628 - pill.height / 2)))
    for i, s in enumerate(["Paiement mensuel", "Activation rapide"]):
        check(d, 52, 760 + i * 62); d.text((86, 760 + i * 62), s, font=font("sb", 28), fill=WHITE, anchor="lm")
    btn = Image.new("RGBA", (464, 100), (0, 0, 0, 0)); b = ImageDraw.Draw(btn)
    press = 1 - 0.04 * math.sin(math.pi * prog(t, 4.3, 4.5))
    b.rounded_rectangle([0, 0, 463, 99], 50, fill=ACC); b.text((232, 50), "Je m'abonne", font=font("xb", 38), fill=DARK, anchor="mm")
    rp = prog(t, 4.3, 4.9)
    if 0 < rp < 1:
        rip = Image.new("RGBA", btn.size, (0, 0, 0, 0)); r = 30 + 300 * out_cubic(rp)
        ImageDraw.Draw(rip).ellipse([300 - r, 50 - r, 300 + r, 50 + r], fill=(255, 255, 255, int(130 * (1 - rp))))
        rip.putalpha(Image.fromarray(np.minimum(np.array(rip.getchannel("A")), np.array(btn.getchannel("A"))))); btn.alpha_composite(rip)
    btn = shine(btn, prog(t, 2.0, 2.7))
    if press != 1: btn = btn.resize((int(464 * press), int(100 * press)), Image.LANCZOS)
    S.alpha_composite(btn, (int(260 - btn.width / 2), int(950 - btn.height / 2)))
    ty = lerp(-130, 36, out_back(prog(t, 4.6, 4.95)))
    if t > 4.6:
        d.rounded_rectangle([24, ty, 496, ty + 104], 28, fill=(30, 34, 44), outline=ACC, width=3)
        check(d, 72, ty + 52, 24)
        d.text((112, ty + 22), "Paiement validé", font=font("xb", 30), fill=WHITE)
        d.text((112, ty + 60), "20,00 € / mois", font=font("sb", 24), fill=ACC)
    d.rounded_rectangle([190, 1070, 330, 1078], 4, fill=(255, 255, 255, 200))
    return S

def screen_dash(t):
    S = app_bg(920, 580).copy(); d = ImageDraw.Draw(S)
    d.rectangle([0, 0, 170, 580], fill=(20, 22, 30)); d.ellipse([30, 28, 74, 72], fill=ACC)
    for k in range(5): d.rounded_rectangle([30, 120 + k * 52, 140, 140 + k * 52], 8, fill=(52, 56, 70) if k else ACC)
    d.text((200, 26), "Tes économies", font=font("xb", 40), fill=WHITE)
    d.text((200, 78), "Comparatif sur 12 mois", font=font("sb", 22), fill=GREY)
    d.rounded_rectangle([200, 126, 530, 330], 24, fill=(26, 28, 38))
    d.text((225, 146), "Économisé / an", font=font("sb", 24), fill=GREY)
    n = int(round(168 * out_cubic(prog(t, 7.0, 8.2))))
    d.text((222, 186), f"+{n} €", font=font("black", 90), fill=ACC)
    d.text((225, 292), "soit 14 € de moins par mois", font=font("sb", 21), fill=WHITE)
    d.rounded_rectangle([550, 126, 895, 552], 24, fill=(26, 28, 38))
    base = 480
    for x, val, col, lab, gp in [(600, 408, RED, "Prix habituel", prog(t, 6.9, 7.6)), (760, 240, ACC, "Avec moi", prog(t, 7.3, 8.0))]:
        hgt = 300 * val / 408 * out_cubic(gp)
        if hgt > 1: d.rounded_rectangle([x, base - hgt, x + 90, base], 14, fill=col)
        if gp > 0.6: d.text((x + 45, base - hgt - 26), f"{int(val * out_cubic(gp))} €", font=font("xb", 28), fill=WHITE, anchor="mm")
        d.text((x + 45, base + 32), lab, font=font("sb", 19), fill=GREY, anchor="mm")
    d.rounded_rectangle([200, 350, 530, 552], 24, fill=(26, 28, 38))
    d.text((222, 366), "Cumul économisé", font=font("sb", 20), fill=GREY)
    lp = out_cubic(prog(t, 7.2, 8.5))
    pts = [(222 + i * 26, 530 - i * i * 1.1 - i * 2) for i in range(12)]
    k = max(2, int(len(pts) * lp))
    if lp > 0:
        poly = pts[:k] + [(pts[k - 1][0], 535), (222, 535)]
        ar = Image.new("RGBA", S.size, (0, 0, 0, 0)); ImageDraw.Draw(ar).polygon(poly, fill=ACC + (50,)); S.alpha_composite(ar)
        d = ImageDraw.Draw(S); d.line(pts[:k], fill=ACC, width=5, joint="curve"); x, y = pts[k - 1]; d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=WHITE)
    return S

MSGS = [(10.9, "in", ["Salut ! La salle à", "20 € par mois, c'est vrai ?"]),
        (11.9, "out", ["Oui ! Au lieu de 34 €"]),
        (12.6, "out", ["Tu économises 168 € par an"]),
        (13.3, "in", ["Je prends !"])]

def bubble(lines, side):
    f = font("sb", 28); wd = max(f.getlength(s) for s in lines) + 44; ht = 38 * len(lines) + 30
    im = Image.new("RGBA", (int(wd), int(ht)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, wd - 1, ht - 1], 26, fill=(40, 43, 56) if side == "in" else ACC)
    for i, s in enumerate(lines): d.text((22, 15 + i * 38), s, font=f, fill=WHITE if side == "in" else DARK)
    return im

def screen_chat(t):
    S = app_bg(520, 1100).copy(); d = ImageDraw.Draw(S); status_bar(d, 520)
    d.rectangle([0, 80, 520, 190], fill=(20, 22, 30))
    d.text((30, 135), "‹", font=font("b", 60), fill=WHITE, anchor="lm")
    d.ellipse([70, 100, 140, 170], fill=ACC); d.text((105, 136), "€", font=font("black", 40), fill=DARK, anchor="mm")
    d.text((160, 104), "Abonnement 20 €", font=font("xb", 30), fill=WHITE)
    d.text((160, 146), "en ligne", font=font("sb", 22), fill=ACC)
    y = 230
    for t0, side, lines in MSGS:
        if side == "out" and t0 - 0.55 < t < t0:   # typing dots
            dots = Image.new("RGBA", (110, 60), (0, 0, 0, 0)); dd = ImageDraw.Draw(dots)
            dd.rounded_rectangle([0, 0, 109, 59], 28, fill=(40, 43, 56))
            for k in range(3):
                o = 6 * math.sin(t * 14 - k)
                dd.ellipse([24 + k * 24, 24 + o, 38 + k * 24, 38 + o], fill=GREY)
            S.alpha_composite(dots, (496 - 110, y))
        if t < t0: break
        b = bubble(lines, side); p = out_back(prog(t, t0, t0 + 0.3))
        bs = b.resize((max(1, int(b.width * p)), max(1, int(b.height * p))), Image.LANCZOS)
        x = 24 if side == "in" else 496 - bs.width
        S.alpha_composite(fade(bs, clamp(p)), (int(x), int(y + (b.height - bs.height))))
        y += b.height + 22
    d = ImageDraw.Draw(S)
    d.rounded_rectangle([24, 990, 430, 1050], 30, fill=(30, 33, 44)); d.text((50, 1020), "Écris un message…", font=font("sb", 24), fill=GREY, anchor="lm")
    d.ellipse([440, 990, 500, 1050], fill=ACC); d.polygon([(460, 1005), (488, 1020), (460, 1035)], fill=DARK)
    d.rounded_rectangle([190, 1070, 330, 1078], 4, fill=(255, 255, 255, 200))
    return S

# ------------------------------------------------------------------ particles (3D coins & bills)
R = np.random.default_rng(5)
BURSTS = [(4.9, (0, 140, 1350), 26), (8.2, (0, -60, 1700), 22), (13.9, (0, 40, 1850), 34)]
BURST_P = {t0: [(R.uniform(-1100, 1100), R.uniform(-2100, -700), R.uniform(-900, 500), R.uniform(-500, 500), R.uniform(-500, 500),
                 R.uniform(0, 360), R.uniform(0.8, 1.3), "€" if R.random() < 0.75 else "$") for _ in range(n)] for t0, _, n in BURSTS}
RAIN_B = [(R.uniform(-1000, 1000), R.uniform(0, 1), R.uniform(1250, 2700), R.uniform(0.6, 1.4), R.uniform(0, 6.3)) for _ in range(18)]
RAIN_C = [(R.uniform(-1000, 1000), R.uniform(0, 1), R.uniform(1200, 2800), R.uniform(0.8, 1.6), R.uniform(0, 6.3)) for _ in range(12)]

def rain_amount(t): return smooth(prog(t, 5.6, 6.3)) * (1 - smooth(prog(t, 9.9, 10.5))) + smooth(prog(t, 13.9, 14.5))

def particles(t):
    """List of (view_z, draw_fn)."""
    out = []
    for t0, org, n in BURSTS:
        dt = t - t0
        if not 0 < dt < 2.6: continue
        a = 1 - prog(dt, 1.9, 2.6)
        for vx, vy, vz, sx, sy, r0, sc, lab in BURST_P[t0]:
            P = np.array(org, float) + np.array([vx, vy, vz]) * dt + np.array([0, 0.5 * 2400 * dt * dt, 0])
            M = rotm(r0 + sx * dt, r0 * 0.5 + sy * dt, r0); sz = 150 * sc
            out.append((view([P])[0][2], lambda L, P=P, M=M, sz=sz, a=a, lab=lab: quad(L, coin_img(lab), plane(P, M, sz, sz), a, cull=False, dof=True)))
    ra = rain_amount(t)
    if ra > 0.01:
        for x, ph, z, sp, wph in RAIN_B:
            y = -1700 + ((t * 420 * sp + ph * 3400) % 3400)
            P = np.array([x + 140 * math.sin(t * 1.3 + wph), y, z])
            M = rotm(55 * math.sin(t * 2.1 * sp + wph), 40 * math.sin(t * 1.4 + wph), 25 * math.sin(t * 1.7 + wph))
            out.append((view([P])[0][2], lambda L, P=P, M=M: quad(L, bill_img(), plane(P, M, 330, 150), ra, cull=False, dof=True)))
        for x, ph, z, sp, wph in RAIN_C:
            y = -1700 + ((t * 650 * sp + ph * 3400) % 3400)
            P = np.array([x, y, z]); M = rotm(t * 300 * sp + wph * 50, t * 200 + wph * 30, 10)
            out.append((view([P])[0][2], lambda L, P=P, M=M: quad(L, coin_img("€"), plane(P, M, 130, 130), ra, cull=False, dof=True)))
    return out

# ------------------------------------------------------------------ timeline
IMPACTS = [(0.9, 0.5), (3.8, 0.7), (4.9, 1.0), (6.9, 0.5), (8.2, 0.8), (11.0, 0.5), (13.9, 1.0)]
LEAKS = [(5.3, 5.9, ACC), (10.2, 10.8, (120, 90, 255))]

def impact(t, rate=8.0): return sum(s * math.exp(-(t - t0) * rate) for t0, s in IMPACTS if t >= t0)

def shake(t):
    x = y = 0.0
    for t0, s in IMPACTS:
        if t >= t0:
            e = s * math.exp(-(t - t0) * 10) * 16; x += e * math.sin((t - t0) * 70 + t0); y += e * math.cos((t - t0) * 57 + t0)
    return x, y

def setup_camera(t):
    yaw = 7 * math.sin(t * 0.6) + 4 * math.sin(t * 1.7)
    pitch = 3 * math.sin(t * 0.45)
    CAM["R"] = rotm(pitch, yaw, 0.6 * math.sin(t * 0.8))
    CAM["f"] = 1600 * (1 + 0.045 * impact(t, 6))
    CAM["sh"] = shake(t)

def device(t):
    """Returns (draw_fn, view_z) for the hero device of the moment."""
    if t < 5.75:
        pin = out_cubic(prog(t, 0.0, 0.9)); pout = in_cubic(prog(t, 5.25, 5.75)); zoom = in_out(prog(t, 2.7, 3.3)) * (1 - in_out(prog(t, 4.95, 5.3)))
        x = lerp(0, 1500, pout); y = lerp(1900, 150, pin) + lerp(0, -900, pout) + 14 * math.sin(t * 2)
        z = lerp(1650, 1380, zoom)
        ry = lerp(-75, -18, pin) + 10 * math.sin(t * 0.9) * (1 - zoom * 0.7) + lerp(0, 14, zoom) + 320 * pout
        rx = 7 * math.sin(t * 0.7) + lerp(-30, 0, pin); rz = lerp(-12, 0, pin) + 2 * math.sin(t * 0.8) + 25 * pout
        C = np.array([x, y, z]); M = rotm(rx, ry, rz); scr = screen_offer(t)
        return (lambda L: draw_phone(L, C, M, scr, 0.3 + 0.004 * ry)), view([C])[0][2]
    if t < 10.45:
        pin = out_back(prog(t, 5.6, 6.3), 1.2); pout = in_cubic(prog(t, 10.0, 10.45))
        theta = lerp(0, 106, out_back(prog(t, 6.1, 7.0), 1.4)) * (1 - in_out(prog(t, 9.85, 10.2)))
        y = lerp(1500, 300, pin) + lerp(0, 1400, pout); z = 1820 + lerp(0, -180, smooth(prog(t, 7.0, 9.8)))
        yaw = lerp(-45, 0, pin) + 9 * math.sin((t - 5.6) * 0.8) + lerp(0, -40, pout)
        C = np.array([0, y, z]); M = rotm(12 + lerp(25, 0, pin), yaw, 0); scr = screen_dash(t)
        return (lambda L: draw_laptop(L, C, M, theta, scr)), view([C])[0][2]
    pin = prog(t, 10.4, 11.05); yb = lerp(-2000, 40, out_back(pin, 1.6)) if pin < 1 else 40 + 12 * math.sin(t * 2)
    C = np.array([0, yb, 1900]); M = rotm(5 * math.sin(t * 0.8), lerp(40, 12, out_cubic(pin)) + 9 * math.sin(t * 0.9), lerp(15, 0, out_cubic(pin)))
    scr = screen_chat(t)
    return (lambda L: draw_phone(L, C, M, scr, 0.5)), view([C])[0][2]

# ------------------------------------------------------------------ background (studio)
BASE = None
def base_bg():
    global BASE
    if BASE is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.9)) ** 2 + ((yy - H * 0.42) / (H * 0.55)) ** 2)
        c0, c1 = np.array([30, 34, 52], np.float32), np.array([5, 6, 10], np.float32)
        k = np.clip(r, 0, 1)[..., None] ** 1.2
        arr = c0 * (1 - k) + c1 * k
        fl = np.clip((yy - H * 0.80) / (H * 0.2), 0, 1)[..., None]   # floor glossy band
        arr = arr * (1 - fl * 0.4) + np.array([14, 16, 24]) * fl * 0.4
        BASE = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    return BASE

def background(t):
    im = base_bg().copy()
    sm = Image.new("RGBA", (W // 6, H // 6), (0, 0, 0, 0)); d = ImageDraw.Draw(sm)
    pulse = 1 + 0.6 * impact(t, 5)
    for cx, cy, r, col, al in [(W / 12 + 40 * math.sin(t * 0.7), H / 12 + 30 * math.cos(t * 0.5), 70, ACC, 34),
                               (W / 12 - 60 * math.cos(t * 0.4), H / 15 + 50 * math.sin(t * 0.6), 90, (120, 90, 255), 30)]:
        r *= pulse; d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (int(min(80, al * pulse)),))
    for k in range(4):   # soft light beams from the top
        a = math.radians(-30 + k * 20 + 6 * math.sin(t * 0.3 + k)); x0 = W / 12
        d.polygon([(x0, -10), (x0 + 400 * math.sin(a) - 12, 400 * math.cos(a)), (x0 + 400 * math.sin(a) + 12, 400 * math.cos(a))], fill=(255, 255, 255, 10))
    im.alpha_composite(sm.filter(ImageFilter.GaussianBlur(22)).resize((W, H), Image.BILINEAR))
    return im

# ------------------------------------------------------------------ overlay typography
def overlay(L, t):
    def out_a(a, b): return 1 - smooth(prog(t, a, b))
    if t < 2.95:
        a = out_a(2.6, 2.9); up = smooth(prog(t, 2.6, 2.9)) * -60
        reveal(L, text3d("TA SALLE DE SPORT", 88), W / 2, 230 + up, prog(t, 0.25, 0.7), a)
        bw = 760 * out_cubic(prog(t, 0.75, 1.1))
        if bw > 4:
            bar = Image.new("RGBA", (int(bw), 150), (0, 0, 0, 0)); ImageDraw.Draw(bar).rounded_rectangle([0, 0, bw - 1, 149], 22, fill=ACC)
            bar = bar.rotate(2, Image.BICUBIC, expand=True); safe_comp(L, fade(bar, a), W / 2 - 380, 300 + up)
        reveal(L, text3d("TROP CHÈRE ?", 112, DARK, OLIVE), W / 2, 378 + up, prog(t, 0.95, 1.3), a)
    elif t < 5.4:
        a = out_a(5.05, 5.35)
        reveal(L, text3d("34 €", 130, GREY), 270, 300, prog(t, 3.0, 3.35), a)
        if t > 3.3: ImageDraw.Draw(L).line([(160, 330), (160 + 220 * out_cubic(prog(t, 3.3, 3.6)), 286)], fill=RED + (int(255 * a),), width=14)
        reveal(L, text3d("→", 110, WHITE), 520, 292, prog(t, 3.35, 3.6), a)
        p = out_back(prog(t, 3.75, 4.1))
        if p > 0: safe_comp(L, fade(text3d("20 €", 170, ACC, OLIVE).resize((max(1, int(text3d("20 €", 170, ACC, OLIVE).width * p)), max(1, int(text3d("20 €", 170, ACC, OLIVE).height * p)))), a), 790 - text3d("20 €", 170, ACC, OLIVE).width * p / 2, 300 - text3d("20 €", 170, ACC, OLIVE).height * p / 2)
        reveal(L, text3d("PAR MOIS", 58, WHITE, weight="xb"), W / 2, 450, prog(t, 4.0, 4.3), a)
    elif 5.8 < t < 10.3:
        a = out_a(9.9, 10.2)
        reveal(L, text3d("TU ÉCONOMISES", 92), W / 2, 260, prog(t, 6.2, 6.6), a)
        n = int(round(168 * out_cubic(prog(t, 7.0, 8.2))))
        s = 1 + 0.12 * math.exp(-(t - 8.2) * 7) if t > 8.2 else 1
        reveal(L, text3d(f"{n} € / AN", 140, ACC, OLIVE), W / 2, 420, prog(t, 6.9, 7.3), a, s)
    elif t > 10.6:
        reveal(L, text3d("20 € / MOIS", 132, ACC, OLIVE), W / 2, 250, prog(t, 10.7, 11.1))
        reveal(L, text3d("au lieu de 34 €", 56, WHITE, weight="xb"), W / 2, 390, prog(t, 11.0, 11.3))
        pb = out_back(prog(t, 13.9, 14.3))
        if pb > 0.02:
            btn = Image.new("RGBA", (860, 170), (0, 0, 0, 0)); bd = ImageDraw.Draw(btn)
            bd.rounded_rectangle([0, 0, 859, 169], 85, fill=ACC)
            tx = text3d("ÉCRIS-MOI EN DM", 66, DARK, OLIVE, depth=4); btn.alpha_composite(tx, (int(430 - tx.width / 2), int(85 - tx.height / 2)))
            for k in range(3): btn = shine(btn, prog(t, 14.4 + k * 0.55, 14.85 + k * 0.55), 0.16, 110)
            pulse = pb * (1 + 0.04 * math.sin((t - 14.3) * 7) if t > 14.3 else 1)
            btn = btn.resize((int(860 * pulse), int(170 * pulse)), Image.LANCZOS)
            gl = Image.new("RGBA", (W, 400), (0, 0, 0, 0)); ImageDraw.Draw(gl).rounded_rectangle([W / 2 - 430, 120, W / 2 + 430, 280], 80, fill=ACC + (90,))
            safe_comp(L, gl.filter(ImageFilter.GaussianBlur(40)), 0, 1630 - 200)
            safe_comp(L, btn, W / 2 - btn.width / 2, 1630 - btn.height / 2)
        reveal(L, text3d(HANDLE, 64, WHITE, weight="xb"), W / 2, 1790, prog(t, 14.3, 14.6))

# ------------------------------------------------------------------ compose & post
def compose(t):
    setup_camera(t)
    img = background(t)
    dev_draw, dz = device(t)
    parts = sorted(particles(t), key=lambda p: -p[0])
    for z, fn in parts:
        if z >= dz: fn(img)
    D = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dev_draw(D)
    bb = D.getbbox()
    if bb:   # glossy floor reflection + contact shadow
        x0, y0, x1, y1 = bb; fy = min(y1, H - 10)
        sh = Image.new("RGBA", (W // 4, 60), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([x0 / 4 + 10, 20, x1 / 4 - 10, 40], fill=(0, 0, 0, 170))
        safe_comp(img, sh.filter(ImageFilter.GaussianBlur(6)).resize((W, 240), Image.BILINEAR), 0, fy - 120)
        ref = D.crop((0, max(0, y0), W, y1)).transpose(Image.FLIP_TOP_BOTTOM)
        hh = ref.height; g = np.clip(1 - np.arange(hh) / (hh * 0.45), 0, 1) * 0.28
        al = (np.asarray(ref.getchannel("A"), np.float32) * g[:, None]).astype(np.uint8)
        ref.putalpha(Image.fromarray(al)); ref = ref.resize((W // 2, max(1, hh // 2))).filter(ImageFilter.GaussianBlur(2)).resize((W, hh))
        safe_comp(img, ref, 0, fy + 4)
    img.alpha_composite(D)
    for z, fn in parts:
        if z < dz: fn(img)
    overlay(img, t)
    return img

VIG = None; GRAIN = None
def post(img, t, fi):
    global VIG, GRAIN
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        VIG = (1 - 0.5 * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None].astype(np.float32)
        g = np.random.default_rng(3); GRAIN = [g.normal(0, 2.5, (H, W, 1)).astype(np.float32) for _ in range(3)]
    rgb = img.convert("RGB"); arr = np.asarray(rgb, np.float32)
    small = np.clip(np.asarray(rgb.resize((W // 4, H // 4), Image.BILINEAR), np.float32) - 120, 0, 255).astype(np.uint8)
    arr += np.asarray(Image.fromarray(small).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR), np.float32) * 0.7
    for a, b, col in LEAKS:   # light-leak transitions
        p = prog(t, a, b)
        if 0 < p < 1:
            lk = Image.new("RGB", (W // 8, H // 8), (0, 0, 0)); d = ImageDraw.Draw(lk)
            cx = lerp(-40, W / 8 + 40, in_out(p)); d.ellipse([cx - 60, -20, cx + 60, H / 8 + 20], fill=col)
            d.ellipse([cx - 25, H / 16 - 50, cx + 25, H / 16 + 50], fill=(255, 255, 255))
            arr += np.asarray(lk.filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BILINEAR), np.float32) * math.sin(math.pi * p) * 1.1
    ca = int(impact(t, 10) * 7)
    if ca > 0: arr[..., 0] = np.roll(arr[..., 0], ca, axis=1); arr[..., 2] = np.roll(arr[..., 2], -ca, axis=1)
    fl = sum(s * math.exp(-(t - t0) * 16) * 0.3 for t0, s in IMPACTS if t >= t0)
    arr = arr + (255 - arr) * min(fl, 0.5)
    arr = arr * VIG + GRAIN[fi % 3]
    arr *= 1 - prog(t, 15.5, 16.0)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def frame_rgb(i):
    t = i / FPS; return post(compose(t), t, i).tobytes()

# ------------------------------------------------------------------ audio
def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); Rn = np.random.default_rng(1)
    def add(sig, t0):
        i = int(t0 * sr)
        if i >= n or i < 0: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    beat = 60 / 124
    tk = T(0.35); kick = np.sin(2 * np.pi * (48 + 120 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 8)
    th = T(0.04); hat = Rn.uniform(-1, 1, len(th)) * np.exp(-th * 110) * 0.13
    ts = T(0.2); clap = Rn.uniform(-1, 1, len(ts)) * np.exp(-ts * 22) * 0.32
    tb = T(beat); k = 0
    chords = [(55, 110, 164.8), (49, 98, 146.8), (65.4, 130.8, 196), (58.3, 116.5, 174.6)]
    while k * beat < 15.4:
        t0 = k * beat
        add(kick * 0.9, t0); add(hat, t0 + beat / 2); add(hat * 0.6, t0 + beat * 0.75)
        if k % 2 == 1: add(clap, t0)
        root, a2, a3 = chords[(k // 4) % 4]
        add((np.sign(np.sin(2 * np.pi * root * tb)) * 0.09 + np.sin(2 * np.pi * a2 * tb) * 0.05) * np.exp(-tb * 4), t0)
        if k % 4 == 0:
            tp = T(beat * 4); pad = sum(np.sin(2 * np.pi * f * tp + np.sin(2 * np.pi * 0.5 * tp)) for f in (a2 * 2, a3 * 2, a2 * 3)) * 0.025
            add(pad * np.minimum(1, tp / 0.3) * np.minimum(1, (beat * 4 - tp) / 0.3), t0)
        k += 1
    for t0, s in IMPACTS:
        tt = T(1.0); boom = np.sin(2 * np.pi * (40 + 55 * np.exp(-tt * 10)) * tt) * np.exp(-tt * 4)
        add((boom + Rn.normal(0, 1, len(tt)) * np.exp(-tt * 16) * 0.35) * 0.5 * s, t0)
    for a, b, _ in LEAKS:
        tr = T(0.8); env = np.sin(np.pi * tr / 0.8) ** 2
        add(Rn.normal(0, 1, len(tr)) * env * 0.2, a - 0.1)
    tc = T(0.12); ping = lambda f: np.sin(2 * np.pi * f * tc) * np.exp(-tc * 30) * 0.12
    for t0, _, nb in BURSTS:   # coins
        for j in range(16): add(ping(Rn.uniform(2500, 4200)), t0 + Rn.uniform(0, 0.9))
        tch = T(0.9); ch = (np.sin(2 * np.pi * 1568 * tch) + 0.6 * np.sin(2 * np.pi * 2349 * tch)) * np.exp(-tch * 5) * 0.25
        add(ch, t0 + 0.05)
    for t0, _, _ in MSGS: add(np.sin(2 * np.pi * 880 * T(0.1)) * np.exp(-T(0.1) * 30) * 0.18, t0)
    add(np.sin(2 * np.pi * 1200 * T(0.06)) * 0.15, 4.3)
    env = np.ones(n); fo = int(0.6 * sr); env[-fo:] = np.linspace(1, 0, fo)
    out = np.tanh(out * env * 1.3) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            t = float(s); post(compose(t), t, int(t * FPS)).save(f"preview_{s}.png")
        sys.exit()
    wav = OUT.replace(".mp4", ".wav"); make_audio(wav)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264",
                          "-preset", "slow", "-crf", "21", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(frame_rgb, range(int(DUR * FPS)), chunksize=4)):
            p.stdin.write(buf)
            if i % 60 == 0: print(f"frame {i}", flush=True)
    p.stdin.close(); p.wait(); os.remove(wav); print("OK ->", OUT)
