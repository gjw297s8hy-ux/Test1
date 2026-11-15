"""Motion design v3 (profondeur : DOF, parallaxe, objets 3D) : abonnement salle de sport 20 €/mois au lieu de 34 €.
Rendu :   python3 render_v3.py            -> promo_abonnement_v3.mp4 (1080x1920, 30 fps, 16 s)
Aperçu :  python3 render_v3.py 1.2 6.7    -> preview_1.2.png, preview_6.7.png"""
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 16.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "promo_abonnement_v3.mp4")
HANDLE = "@toncompte"   # <- remplace par ton pseudo / numéro

BG = (10, 10, 16); WHITE = (248, 248, 248); GREY = (160, 160, 172)
ACC = (196, 255, 46); RED = (255, 56, 78); DARK = (18, 18, 22); BLUE = (80, 200, 255)
OLIVE = (70, 98, 8)
FONTS = "/usr/share/fonts/opentype/inter/"
FW = {"black": "Inter-Black.otf", "xb": "Inter-ExtraBold.otf", "b": "Inter-Bold.otf", "sb": "Inter-SemiBold.otf"}

@lru_cache(None)
def font(w, s): return ImageFont.truetype(FONTS + FW[w], s)

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def out_cubic(x): return 1 - (1 - x) ** 3
def in_cubic(x): return x ** 3
def smooth(x): return x * x * (3 - 2 * x)
def out_back(x, s=1.9): x -= 1; return x * x * ((s + 1) * x + s) + 1
def out_elastic(x):
    if x <= 0 or x >= 1: return clamp(x)
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1
def lerp(a, b, x): return a + (b - a) * x
def mix(c1, c2, x): return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))

# ---------------------------------------------------------------- compositing
def safe_comp(L, im, x, y):
    x, y = int(x), int(y)
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, W - x), min(im.height, H - y)
    if ex <= sx or ey <= sy: return
    L.alpha_composite(im, (x + sx, y + sy), (sx, sy, ex, ey))

def fade(im, a):
    if a >= 1: return im
    im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a))); return im

def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def proj(img, s=1.0, rx=0.0, ry=0.0, rz=0.0, f=1800):
    """Perspective-project an image. Returns (image, x0, y0) with x0/y0 relative to its centre."""
    if abs(rx) < 0.05 and abs(ry) < 0.05:
        im = img if s == 1 else img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
        if abs(rz) > 0.05: im = im.rotate(-rz, Image.BICUBIC, expand=True)
        return im, -im.width / 2, -im.height / 2
    if abs(math.cos(math.radians(rx))) < 0.03 or abs(math.cos(math.radians(ry))) < 0.03: return None
    w, h = img.size; hw, hh = w * s / 2, h * s / 2
    ax, ay, az = map(math.radians, (rx, ry, rz)); quad = []
    for x, y in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
        y, z = y * math.cos(ax), y * math.sin(ax)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        z += f
        if z < 50: return None
        quad.append((x * f / z, y * f / z))
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    x0, y0, x1, y1 = math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys))
    if x1 - x0 < 3 or y1 - y0 < 3 or x1 - x0 > 4 * W or y1 - y0 > 4 * H: return None
    try: co = persp_coeffs([(px - x0, py - y0) for px, py in quad], [(0, 0), (w, 0), (w, h), (0, h)])
    except np.linalg.LinAlgError: return None
    return img.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, co, Image.BICUBIC), x0, y0

def blurred(im, r):
    if r < 0.6: return im, 0
    pad = int(r * 2.5) + 2
    c = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); c.paste(im, (pad, pad))
    return c.filter(ImageFilter.GaussianBlur(r)), pad

def put(L, img, cx, cy, s=1.0, a=1.0, rx=0.0, ry=0.0, rz=0.0, f=1800, blur=0.0):
    """Place an image in 3D: rotations in degrees around X / Y / Z, perspective, optional depth blur."""
    if a <= 0.01 or s <= 0.01: return
    r = proj(img, s, rx, ry, rz, f)
    if r is None: return
    im, ox, oy = r; im, pad = blurred(im, blur)
    safe_comp(L, fade(im, a), cx + ox - pad, cy + oy - pad)

# ---------------------------------------------------------------- 3D text & objects
@lru_cache(None)
def text3d(s, size, face=WHITE, side=None, weight="black", depth=None):
    """Extruded 3D text with a soft shadow."""
    f = font(weight, size); l, t, r, b = f.getbbox(s)
    depth = depth if depth is not None else max(5, int(size * 0.17))
    side = side or mix(face, (0, 0, 0), 0.55)
    pad = 30; tw, th = r - l, b - t
    mask = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), s, font=f, fill=255)
    dx, dy = 0.4, 0.85
    cw, ch = mask.width + int(depth * dx * 2) + 10, mask.height + int(depth * 2) + 10
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 170), (int(depth * 0.9), int(depth * 1.8)), mask)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(3, depth * 0.7))))
    far = mix(side, (0, 0, 0), 0.55)
    for k in range(depth, 0, -1):
        im.paste(mix(side, far, k / depth) + (255,), (int(k * dx), int(k * dy)), mask)
    grad = Image.linear_gradient("L").resize(mask.size)
    top, bot = Image.new("RGBA", mask.size, face + (255,)), Image.new("RGBA", mask.size, mix(face, (0, 0, 0), 0.2) + (255,))
    faceim = Image.composite(bot, top, grad)
    im.paste(faceim, (0, 0), mask)
    return im

def shine(img, p, width=0.18, strength=170):
    """Diagonal light sweep across an image (p from 0 to 1)."""
    if p <= 0 or p >= 1: return img
    w, h = img.size; x = lerp(-0.4 * w, 1.4 * w, p); bw = w * width
    band = Image.new("L", img.size, 0)
    ImageDraw.Draw(band).polygon([(x, 0), (x + bw, 0), (x + bw - h * 0.5, h), (x - h * 0.5, h)], fill=strength)
    band = band.filter(ImageFilter.GaussianBlur(bw * 0.2))
    a = np.minimum(np.array(band, np.uint16), np.array(img.getchannel("A"), np.uint16)).astype(np.uint8)
    light = Image.new("RGBA", img.size, (255, 255, 255, 0)); light.putalpha(Image.fromarray(a))
    out = img.copy(); out.alpha_composite(light); return out

def card(w, h, fill, border=None, radius=48, depth=56):
    """Rounded slab with thickness, gradient and top highlight."""
    im = Image.new("RGBA", (w + depth + 10, h + depth + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    side = mix(fill, (0, 0, 0), 0.6)
    for k in range(depth, 0, -1):
        d.rounded_rectangle([k * 0.4, k * 0.85, w + k * 0.4, h + k * 0.85], radius, fill=mix(mix(fill, (255, 255, 255), 0.15) if k < 3 else side, (0, 0, 0), k / depth * 0.6))
    face = Image.new("RGBA", (w, h), (0, 0, 0, 0)); fd = ImageDraw.Draw(face)
    fd.rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=fill)
    g = Image.linear_gradient("L").resize((w, h)).point(lambda v: int(v * 0.35))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 255)); dark.putalpha(Image.fromarray(np.minimum(np.array(g), np.array(face.getchannel("A")))))
    face.alpha_composite(dark)
    if border: fd = ImageDraw.Draw(face); fd.rounded_rectangle([3, 3, w - 4, h - 4], radius - 3, outline=border, width=7)
    ImageDraw.Draw(face).rounded_rectangle([18, 10, w - 18, 16], 4, fill=(255, 255, 255, 60))
    im.alpha_composite(face); return im

def center_on(base, im, cx, cy):
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

@lru_cache(None)
def coin(label, size=300, fill=RED, face=WHITE, side=(120, 10, 25)):
    d = 34; im = Image.new("RGBA", (size + d + 4, size + d + 4), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    for k in range(d, 0, -1): dr.ellipse([k * 0.4, k, size + k * 0.4, size + k], fill=mix(fill, (0, 0, 0), 0.45 + 0.3 * k / d))
    dr.ellipse([0, 0, size, size], fill=fill); dr.ellipse([16, 16, size - 16, size - 16], outline=(255, 255, 255, 120), width=5)
    center_on(im, text3d(label, int(size * 0.3) if len(label) > 1 else int(size * 0.55), face, side), size / 2 + 6, size / 2 + 6)
    return im

def dumbbell3d(L, cx, cy, s, ay, ax, a):
    """Real 3D dumbbell : cylinders sliced, rotated, projected, painter-sorted."""
    if a <= 0 or s <= 0.01: return
    ay, ax = math.radians(ay), math.radians(ax); f = 6.0
    polys = []
    def rot(x, y, z):
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        return x, y, z
    def cyl(x0, x1, r, col, n=6):
        for i in range(n + 1):
            x = lerp(x0, x1, i / n); pts = []; zs = 0
            for k in range(20):
                th = 2 * math.pi * k / 20
                X, Y, Z = rot(x, r * math.cos(th), r * math.sin(th)); zs += Z
                pz = Z + f; pts.append((cx + X * 260 * s * f / pz, cy + Y * 260 * s * f / pz))
            edge = i in (0, n)
            shade = 1.0 if edge else 0.62
            polys.append((zs / 20, pts, mix(col, (0, 0, 0), 1 - shade)))
    cyl(-1.75, 1.75, 0.11, (200, 200, 210), 24)
    for sgn in (-1, 1):
        cyl(sgn * 1.0, sgn * 1.28, 0.9, ACC); cyl(sgn * 1.32, sgn * 1.55, 0.62, (150, 210, 30))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    for z, pts, col in sorted(polys, key=lambda p: -p[0]):
        d.polygon(pts, fill=col + (int(255 * a),))
    L.alpha_composite(layer)

# ---------------------------------------------------------------- depth objects
def cam_x(t): return math.sin(t * 0.45) * 1.0 + 0.35 * math.sin(t * 1.1)

def cube_img(size, ax, ay, col):
    S = int(size * 2.0) + 4; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    V = []
    for i in range(8):
        x, y, z = (1 if i & 4 else -1), (1 if i & 2 else -1), (1 if i & 1 else -1)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        V.append((x, y, z))
    faces = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
    lx, ly, lz = -0.45, -0.7, -0.55; out = []
    for fc in faces:
        cxx = sum(V[i][0] for i in fc) / 4; cyy = sum(V[i][1] for i in fc) / 4; czz = sum(V[i][2] for i in fc) / 4
        if czz > 0.02: continue
        sh = 0.35 + 0.65 * max(0, cxx * lx + cyy * ly + czz * lz) / 0.9
        pts = [(S / 2 + V[i][0] * size * 0.55, S / 2 + V[i][1] * size * 0.55) for i in fc]
        out.append((czz, pts, mix(col, (0, 0, 0), 1 - min(1, sh))))
    for _, pts, c in sorted(out, key=lambda o: -o[0]):
        d.polygon(pts, fill=c); d.line(pts + [pts[0]], fill=mix(c, (255, 255, 255), 0.35), width=max(1, size // 40))
    return im

@lru_cache(None)
def bokeh_img(col):
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([20, 20, 180, 180], fill=col + (70,), outline=col + (120,), width=6)
    return im.filter(ImageFilter.GaussianBlur(5))

GOLD = (255, 196, 40)
r2 = np.random.default_rng(11); OBJ = []
for i in range(28):
    kind = ["cube", "coin", "cube", "bokeh", "coin", "bokeh"][i % 6]
    x = float(r2.choice([-1, 1]) * r2.uniform(0.6, 1.5)); y = float(r2.uniform(-2.3, 2.3))
    col = [ACC, (60, 70, 90), GOLD, BLUE, WHITE][int(r2.integers(0, 5))] if kind != "coin" else GOLD
    OBJ.append((kind, x, y, float(r2.uniform(0, 9)), float(r2.uniform(0.6, 1.6)), float(r2.uniform(0, 6.3)), col))

def depth_objects(L, t, front):
    """3D objects at many depths with depth-of-field blur and parallax. Focus plane ~ z=2.6."""
    cz = cam_z(t) * 0.55; cx = cam_x(t); items = []
    for kind, x, y, z0, spin, ph, col in OBJ:
        z = ((z0 - cz) % 9.0) + 0.5
        if front != (z < 1.5): continue
        items.append((z, kind, x, y, spin, ph, col))
    for z, kind, x, y, spin, ph, col in sorted(items, key=lambda o: -o[0]):
        a = clamp((9.4 - z) / 2.5) * clamp((z - 0.5) / 0.35)
        size = 230 / z; blur = min(24, abs(1 / z - 1 / 2.6) * 24)
        if a < 0.02 or size < 5: continue
        px = W / 2 + (x - cx * 0.35) * 560 / z; py = H / 2 + y * 520 / z
        if front: a *= clamp((abs(px - W / 2) - 330) / 220)   # keep the text readable
        if kind == "cube": im = cube_img(int(size), t * spin + ph, t * spin * 0.7 + ph, col)
        elif kind == "coin":
            r = proj(coin("€", 300, GOLD, (255, 240, 170), (150, 95, 0)), size / 260, ry=(t * spin * 90 + ph * 57) % 180 - 90, rz=20)
            if r is None: continue
            im = r[0]
        else: im = bokeh_img(col).resize((int(size * 1.5) + 1, int(size * 1.5) + 1), Image.BILINEAR); a *= 0.8
        im, pad = blurred(im, blur)
        safe_comp(L, fade(im, a * (0.85 if front else 1)), px - im.width / 2, py - im.height / 2)

@lru_cache(None)
def shadow_img(w):
    im = Image.new("RGBA", (w + 200, 260), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([100, 100, w + 100, 160], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(30))

def floor_shadow(L, cx, y, w, a, s=1.0):
    if a > 0.02: put(L, shadow_img(w), cx, y, s=s, a=a)

# ---------------------------------------------------------------- particles
rng = np.random.default_rng(7)
STARS = [(rng.uniform(-1.6, 1.6), rng.uniform(-2.6, 2.6), rng.uniform(0.1, 4.0)) for _ in range(170)]
CONF = [(rng.uniform(0, 2 * math.pi), rng.uniform(900, 2100), rng.uniform(12, 26), rng.uniform(5, 14),
         rng.uniform(0, 360), rng.uniform(-600, 600), int(rng.integers(0, 4))) for _ in range(110)]
CCOL = [ACC, WHITE, RED, BLUE]

def confetti(L, t, t0, cx, cy):
    dt = t - t0
    if dt <= 0 or dt > 2.4: return
    d = ImageDraw.Draw(L); a = 1 - prog(dt, 1.6, 2.4)
    for ang, sp, sz, spin, rot0, rspeed, ci in CONF:
        vx, vy = math.cos(ang) * sp, math.sin(ang) * sp * 0.8 - 700
        k = 2.2; m = (1 - math.exp(-k * dt)) / k
        x, y = cx + vx * m, cy + vy * m + 0.5 * 1500 * dt * dt * 0.6
        w = sz * abs(math.cos(spin * dt)); h = sz * 0.55; r = math.radians(rot0 + rspeed * dt)
        pts = [(x + px * math.cos(r) - py * math.sin(r), y + px * math.sin(r) + py * math.cos(r))
               for px, py in [(-w, -h), (w, -h), (w, h), (-w, h)]]
        d.polygon(pts, fill=CCOL[ci] + (int(255 * a),))

def shockwave(L, t, t0, cx, cy, col=ACC):
    d = ImageDraw.Draw(L)
    for k in range(3):
        p = prog(t, t0 + k * 0.09, t0 + k * 0.09 + 0.8)
        if 0 < p < 1:
            r = lerp(120, 1000, out_cubic(p)); fy = 0.42
            d.ellipse([cx - r, cy - r * fy, cx + r, cy + r * fy], outline=col + (int(230 * (1 - p)),), width=int(lerp(26, 3, p)))

# ---------------------------------------------------------------- timeline
IMPACTS = [(1.15, 1.0), (3.0, 0.7), (5.0, 0.9), (6.6, 1.3), (11.0, 0.6), (13.5, 1.0)]
GLITCH = [(2.85, 3.18), (5.0, 5.22), (6.55, 6.7)]

def impact(t, rate=8.0):
    return sum(s * math.exp(-(t - t0) * rate) for t0, s in IMPACTS if t >= t0)

def shake(t):
    x = y = 0.0
    for t0, s in IMPACTS:
        if t >= t0:
            e = s * math.exp(-(t - t0) * 9) * 34
            x += e * math.sin((t - t0) * 73 + t0); y += e * math.cos((t - t0) * 61 + 2 * t0)
    return x, y

def cam_z(t):  # forward travel of the 3D tunnel, with speed boosts on transitions
    return 1.4 * t + 2.5 * smooth(prog(t, 2.8, 3.3)) + 2.0 * smooth(prog(t, 5.9, 6.6)) + \
           6.0 * smooth(prog(t, 9.7, 10.3)) + 2.5 * smooth(prog(t, 12.8, 13.3))

def redness(t): return smooth(prog(t, 2.9, 3.2)) * (1 - smooth(prog(t, 5.95, 6.4)))

# ---------------------------------------------------------------- background
BASE = None
def base_bg():
    global BASE
    if BASE is None:
        y = np.linspace(0, 1, H)[:, None]; mid = np.exp(-((y - 0.5) / 0.22) ** 2)
        arr = np.zeros((H, W, 3)); arr[:] = np.array(BG)
        arr += mid[..., None] * np.array([14, 14, 24])
        BASE = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    return BASE

def background(t):
    im = base_bg().copy(); col = mix(ACC, RED, redness(t))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cz = cam_z(t); F = 420; cx = W / 2 - cam_x(t) * 70
    for yh, sgn in ((H * 0.70, 1), (H * 0.30, -1)):       # floor + ceiling grids
        for k in range(1, 26):
            z = k - (cz % 1.0)
            if z < 0.45: continue
            y = yh + sgn * F / z; al = int(190 * clamp(1 - z / 20) ** 2 * clamp((z - 0.45) * 2))
            if al > 4: d.line([(0, y), (W, y)], fill=col + (min(al, 170),), width=3 if z < 4 else 2)
        for xi in range(-14, 15):
            xa, ya = cx + F * xi * 0.9 / 0.45, yh + sgn * F / 0.45
            xb, yb = cx + F * xi * 0.9 / 26, yh + sgn * F / 26
            d.line([(xa, ya), (xb, yb)], fill=col + (80,), width=2)
    for x, y, z0 in STARS:                                # 3D star field with speed streaks
        z = ((z0 - cz * 0.9) % 4.0) + 0.06; z2 = z + 0.05 + 0.25 * impact(t, 4)
        ox = -cam_x(t) * 0.35 * 420
        px, py = W / 2 + (x * 420 + ox) / z, H / 2 + y * 420 / z
        qx, qy = W / 2 + (x * 420 + ox) / z2, H / 2 + y * 420 / z2
        al = int(255 * clamp(1 - z / 4) ** 1.5); wdt = max(1, int(5 / z ** 0.8))
        d.line([(qx, qy), (px, py)], fill=mix(WHITE, col, 0.4) + (al,), width=min(wdt, 10))
    im.alpha_composite(lay)
    # moving glow orb
    glow = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gx, gy = W / 8 + math.sin(t * 0.8) * 60, H / 8 + math.cos(t * 0.6) * 80
    gd.ellipse([gx - 110, gy - 110, gx + 110, gy + 110], fill=col + (60,))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)).resize((W, H), Image.BILINEAR))
    return im

# ---------------------------------------------------------------- scenes
def scene1(L, t):
    sw = math.sin(t * 2.2) * 14
    for i, (s, y) in enumerate((("TA SALLE", 640), ("DE SPORT", 810))):
        p = out_cubic(prog(t, 0.05 + i * 0.2, 0.75 + i * 0.2))
        put(L, text3d(s, 150), W / 2, y, s=lerp(0.15, 1, p), a=p, ry=sw + (1 - p) * 70, rx=(1 - p) * -40)
    p = prog(t, 0.85, 1.15)
    if p > 0:
        sc = lerp(3.2, 1, in_cubic(p)) if p < 1 else 1 + 0.12 * math.exp(-(t - 1.15) * 7) * math.cos((t - 1.15) * 30)
        put(L, text3d("TROP CHÈRE ?", 122, ACC, OLIVE), W / 2, 1020, s=sc, a=clamp(p * 2), rz=-4 + math.sin(t * 5) * 2, ry=sw * 0.5)
    pd = out_back(prog(t, 1.3, 1.9))
    floor_shadow(L, W / 2, 1640, 520, clamp(pd) * 0.9, 0.8 + 0.1 * math.sin(t * 2))
    dumbbell3d(L, W / 2, 1430, pd * 0.62, t * 140, 18 + math.sin(t * 2) * 12, clamp(pd))

def scene2(L, t):
    a = out_cubic(prog(t, 3.0, 3.4))
    put(L, text3d("Abonnement Basic-Fit", 70, GREY, weight="b"), W / 2, 520 + (1 - a) * -80, a=a, rx=(1 - a) * 60)
    put(L, text3d("prix habituel", 54, GREY, weight="sb"), W / 2, 610 + (1 - a) * -80, a=a)
    n = int(round(lerp(0, 34, out_cubic(prog(t, 3.3, 4.3)))))
    c = card(820, 560, (32, 30, 40), RED)
    center_on(c, text3d(f"{n} €", 290, WHITE), 410, 250)
    center_on(c, text3d("/ mois", 70, GREY, weight="b"), 410, 470)
    sp = out_cubic(prog(t, 4.6, 5.0))
    if sp > 0:
        d = ImageDraw.Draw(c); x0, x1 = 70, 760; xe = lerp(x0, x1, sp)
        d.line([(x0, 380), (xe, 380 - (xe - x0) * 0.32)], fill=RED, width=36)
    pin = prog(t, 3.0, 3.6); pout = in_cubic(prog(t, 5.88, 6.2))
    rx = lerp(-88, 0, out_back(pin)) + math.sin(t * 1.4) * 6
    ry = math.sin(t * 1.1) * 10 + pout * 90
    floor_shadow(L, W / 2, 1520, 760, clamp(pin * 2) * (1 - pout), 1 - 0.06 * math.sin(t * 1.4))
    put(L, c, W / 2, 1010, s=1.0, rx=rx, ry=ry)
    if t > 5.0:
        sh = math.sin(t * 70) * 14 * (1 - prog(t, 5.0, 5.5)); p = out_back(prog(t, 5.0, 5.25))
        put(L, text3d("TROP CHER.", 100, RED, (110, 10, 25)), W / 2 + sh, 1470, s=p, a=clamp(p), rz=3)

def scene3(L, t):
    a = out_cubic(prog(t, 6.25, 6.6))
    put(L, text3d("AVEC MOI", 115), W / 2, 450, s=lerp(1.6, 1, a), a=a, rx=(1 - a) * -50)
    shockwave(L, t, 6.6, W / 2, 1010)
    c = card(820, 560, ACC, None)
    center_on(c, text3d("20 €", 300, DARK, OLIVE), 410, 240)
    center_on(c, text3d("/ MOIS", 74, DARK, OLIVE), 410, 470)
    c = shine(c, prog(t, 7.4, 8.1)); c = shine(c, prog(t, 9.0, 9.6))
    pin = prog(t, 6.2, 6.62)
    ry = lerp(-90, 0, out_back(pin, 2.4)) + math.sin((t - 6.6) * 1.3) * 9
    rx = math.sin(t * 1.6) * 6
    pulse = 1 + 0.025 * math.sin((t - 6.6) * 8) if t > 6.6 else 1
    floor_shadow(L, W / 2, 1560, 760, clamp(pin * 2), 1 - 0.06 * math.sin(t * 1.6))
    put(L, c, W / 2, 1010, s=pulse, rx=rx, ry=ry)
    pb = prog(t, 6.9, 7.9)
    if pb > 0:
        ang = (900 * (1 - out_cubic(pb)) + math.sin(t * 3) * 15) % 360
        if 90 < ang < 270: ang -= 180
        put(L, coin("-41%"), 870, 690, s=out_back(clamp(pb * 3)) * 0.95, ry=ang, rz=14)
    al = out_cubic(prog(t, 7.7, 8.1))
    put(L, text3d("au lieu de 34 €", 78), W / 2, 1450 + (1 - al) * 70, a=al, rx=(1 - al) * 60)
    confetti(L, t, 6.6, W / 2, 1010)

def scene4(L, t):
    a = out_cubic(prog(t, 9.95, 10.2))
    put(L, text3d("TU ÉCONOMISES", 100), W / 2, 500, a=a, rx=(1 - a) * -70 + math.sin(t * 1.5) * 5)
    pc = prog(t, 10.1, 11.0); n = int(round(lerp(0, 168, out_cubic(pc))))
    sc = out_back(prog(t, 9.95, 10.25)) * (1 + 0.15 * math.exp(-(t - 11.0) * 7) if t > 11 else 1)
    put(L, text3d(f"{n} €", 260, ACC, OLIVE), W / 2, 740, s=sc, ry=math.sin(t * 1.8) * 12)
    put(L, text3d("PAR AN", 90), W / 2, 950, a=out_cubic(prog(t, 10.3, 10.6)))
    items = ["Paiement au mois", "Même prix chaque mois", "Simple et rapide"]
    for i, s in enumerate(items):
        p = prog(t, 11.1 + i * 0.22, 11.55 + i * 0.22)
        if p <= 0: continue
        row = card(840, 124, (34, 34, 44), None, 40, 14); d = ImageDraw.Draw(row)
        d.ellipse([22, 22, 102, 102], fill=ACC); d.line([(42, 62), (58, 80), (84, 46)], fill=DARK, width=11)
        center_on(row, text3d(s, 56, WHITE, weight="b", depth=4), 140 + text3d(s, 56, WHITE, weight="b", depth=4).width / 2, 62)
        row = shine(row, prog(t, 11.9 + i * 0.15, 12.5 + i * 0.15))
        put(L, row, W / 2 + (1 - out_cubic(p)) * -500, 1190 + i * 160, a=clamp(p * 1.5),
            ry=lerp(-85, 0, out_back(p)) + math.sin(t * 2 + i) * 6)

def scene5(L, t):
    a = out_cubic(prog(t, 13.1, 13.45))
    put(L, text3d("INTÉRESSÉ ?", 128), W / 2, 600, a=a, ry=(1 - a) * 80 + math.sin(t * 1.7) * 10)
    p = prog(t, 13.25, 13.5)
    if p > 0:
        sc = lerp(2.8, 1, in_cubic(p)) if p < 1 else 1 + 0.12 * math.exp(-(t - 13.5) * 7) * math.cos((t - 13.5) * 30)
        put(L, text3d("20 € / mois", 150, ACC, OLIVE), W / 2, 820, s=sc, a=clamp(p * 2), rx=math.sin(t * 1.3) * 8)
    shockwave(L, t, 13.5, W / 2, 820)
    pb = out_back(prog(t, 13.7, 14.1))
    if pb > 0:
        btn = card(840, 190, ACC, None, 95, 18)
        center_on(btn, text3d("ÉCRIS-MOI EN DM", 70, DARK, OLIVE, depth=5), 420, 95)
        for k in range(3): btn = shine(btn, prog(t, 14.2 + k * 0.6, 14.65 + k * 0.6), 0.22, 200)
        pulse = 1 + 0.045 * math.sin((t - 14.1) * 7) if t > 14.1 else 1
        put(L, btn, W / 2, 1130, s=pb * pulse, rx=math.sin(t * 2.0) * 10, ry=math.sin(t * 1.4) * 12)
    ah = out_cubic(prog(t, 14.1, 14.45))
    put(L, text3d(HANDLE, 82, WHITE, weight="xb"), W / 2, 1340 + (1 - ah) * 60, a=ah)
    al = out_cubic(prog(t, 14.4, 14.7))
    put(L, text3d("Places limitées", 52, GREY, weight="sb", depth=3), W / 2 + 20, 1450, a=al)
    if al > 0 and math.sin(t * 9) > -0.3:
        ImageDraw.Draw(L).ellipse([W / 2 - 230, 1435, W / 2 - 200, 1465], fill=RED + (int(255 * al),))
    confetti(L, t, 13.5, W / 2, 820)

def scene_for(L, t):
    if t < 3.0: scene1(L, t)
    elif t < 6.2: scene2(L, t)
    elif t < 10.0: scene3(L, t)
    elif t < 13.0: scene4(L, t)
    else: scene5(L, t)

# ---------------------------------------------------------------- transitions & post
def zoom_layer(L, s, blur):
    def sc(z):
        w, h = int(W * z), int(H * z); im = L.resize((w, h), Image.BILINEAR); out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        safe_comp(out, im, (W - w) / 2, (H - h) / 2); return out
    if blur < 0.02: return sc(s)
    acc = None
    for k in range(6):
        im = sc(s * (1 + 0.05 * k * blur))
        acc = im if acc is None else Image.blend(acc, im, 1 / (k + 1))
    return acc

def shift_layer(L, dx, blur):
    out = np.zeros((H, W, 4), np.float32); arr = np.asarray(L, np.float32); n = 7 if blur > 2 else 1
    for k in range(n):
        o = int(dx + (k - n / 2) * blur / n)
        if abs(o) >= W: continue
        if o >= 0: out[:, o:] += arr[:, :W - o]
        else: out[:, :W + o] += arr[:, -o:]
    return Image.fromarray((out / n).clip(0, 255).astype(np.uint8), "RGBA")

VIG = None; GRAIN = None
def post(img, t, fi):
    global VIG, GRAIN
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
        VIG = (1 - 0.55 * np.clip(r - 0.35, 0, 1) ** 1.4)[..., None].astype(np.float32)
        g = np.random.default_rng(3); GRAIN = [g.normal(0, 5, (H, W, 1)).astype(np.float32) for _ in range(4)]
    arr = np.asarray(img.convert("RGB"), np.float32)
    small = img.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)              # bloom
    s = np.clip(np.asarray(small, np.float32) - 90, 0, 255).astype(np.uint8)
    bloom = Image.fromarray(s).filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)
    arr += np.asarray(bloom, np.float32) * 0.9
    ca = int(impact(t, 9) * 14)                                                       # chromatic aberration
    g = 0.0
    for a, b in GLITCH:
        if a <= t <= b: g = math.sin(math.pi * prog(t, a, b))
    ca += int(g * 22)
    if ca > 0:
        arr[..., 0] = np.roll(arr[..., 0], ca, axis=1); arr[..., 2] = np.roll(arr[..., 2], -ca, axis=1)
    if g > 0:                                                                         # glitch slices
        r = np.random.default_rng(fi)
        for _ in range(10):
            y0 = int(r.integers(0, H - 40)); hgt = int(r.integers(10, 140)); dx = int(r.normal(0, 90 * g))
            arr[y0:y0 + hgt] = np.roll(arr[y0:y0 + hgt], dx, axis=1)
            if r.random() < 0.3: arr[y0:y0 + hgt, :, 1] *= 0.4
    fl = 0.0
    for t0, s_ in IMPACTS:
        if t >= t0: fl += s_ * math.exp(-(t - t0) * 14) * 0.45
    arr = arr + (255 - arr) * min(fl, 0.7)
    arr = arr * VIG + GRAIN[fi % 4]
    fo = prog(t, 15.5, 16.0); arr *= 1 - fo
    out = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out); d.rectangle([0, H - 12, W * t / DUR, H], fill=ACC)
    return out

def frame_rgb(i):
    t = i / FPS
    bg_img = _compose(t); return post(bg_img, t, i).tobytes()

def _compose(t):
    bg = background(t)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); scene_for(L, t)
    if 9.72 <= t < 10.0:
        p = in_cubic(prog(t, 9.72, 10.0)); L = fade(zoom_layer(L, 1 + 3.5 * p, p * 3), 1 - p * 0.7)
    elif 10.0 <= t < 10.32:
        p = out_cubic(prog(t, 10.0, 10.32)); L = zoom_layer(L, lerp(0.25, 1, p), (1 - p) * 3)
    elif 12.78 <= t < 13.0:
        p = in_cubic(prog(t, 12.78, 13.0)); L = shift_layer(L, -W * 1.1 * p, 260 * p)
    elif 13.0 <= t < 13.22:
        p = out_cubic(prog(t, 13.0, 13.22)); L = shift_layer(L, W * 1.1 * (1 - p), 260 * (1 - p))
    sx, sy = shake(t); cx = cam_x(t)
    L2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # camera orbit + parallax on the content plane
    put(L2, L, W / 2 - cx * 40 + sx, H / 2 + sy, rx=3.5 * math.sin(t * 0.37), ry=cx * 7)
    depth_objects(bg, t, front=False)
    bg.alpha_composite(L2)
    depth_objects(bg, t, front=True)
    return bg

# ---------------------------------------------------------------- audio
def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n); R = np.random.default_rng(1)
    def add(sig, t0):
        i = int(t0 * sr)
        if i >= n: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    def T(d): return np.arange(int(d * sr)) / sr
    beat = 60 / 124
    tk = T(0.35); kick = np.sin(2 * np.pi * (48 + 130 * np.exp(-tk * 28)) * tk) * np.exp(-tk * 8)
    th = T(0.05); hat = R.uniform(-1, 1, len(th)) * np.exp(-th * 90) * 0.16
    tb = T(beat); ts = T(0.18); snare = (R.uniform(-1, 1, len(ts)) * 0.5 + np.sin(2 * np.pi * 190 * ts)) * np.exp(-ts * 18) * 0.35
    k = 0
    while k * beat < 15.4:
        t0 = k * beat
        add(kick * 0.85, t0); add(hat, t0 + beat / 2)
        if k % 2 == 1 and t0 > 3: add(snare, t0)
        note = [55, 55, 65.4, 49][(k // 4) % 4]
        bass = np.sign(np.sin(2 * np.pi * note * tb)) * np.exp(-tb * 5) * 0.11
        add(bass, t0); k += 1
    for t0, s in IMPACTS:                                   # booms
        tt = T(1.2); boom = np.sin(2 * np.pi * (38 + 60 * np.exp(-tt * 10)) * tt) * np.exp(-tt * 3.5)
        nz = R.normal(0, 1, len(tt)) * np.exp(-tt * 14) * 0.5
        add((boom + nz) * 0.55 * s, t0)
    for t1 in [3.0, 6.2, 10.0, 13.0]:                       # risers into transitions
        tr = T(0.7); env = (tr / 0.7) ** 2.5
        sweep = np.sin(2 * np.pi * np.cumsum(300 + 2400 * (tr / 0.7) ** 2) / sr) * 0.12
        add((R.normal(0, 1, len(tr)) * 0.22 + sweep) * env, t1 - 0.7)
    for a, b in GLITCH:                                     # glitch stutter
        tg = T(b - a); sq = np.sign(np.sin(2 * np.pi * 820 * tg)) * (np.sin(2 * np.pi * 28 * tg) > 0) * 0.12
        add(sq, a)
    tc = T(0.8); ding = (np.sin(2 * np.pi * 1318 * tc) + 0.6 * np.sin(2 * np.pi * 1975 * tc) + 0.3 * np.sin(2 * np.pi * 2637 * tc)) * np.exp(-tc * 5) * 0.28
    add(ding, 6.62); add(ding, 13.52)
    env = np.ones(n); fo = int(0.6 * sr); env[-fo:] = np.linspace(1, 0, fo)
    out = np.tanh(out * env * 1.3) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            t = float(s); post(_compose(t), t, int(t * FPS)).save(f"preview_{s}.png")
        sys.exit()
    wav = OUT.replace(".mp4", ".wav"); make_audio(wav)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264",
                          "-preset", "medium", "-crf", "22", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-c:a", "aac",
                          "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(frame_rgb, range(int(DUR * FPS)), chunksize=4)):
            p.stdin.write(buf)
            if i % 60 == 0: print(f"frame {i}", flush=True)
    p.stdin.close(); p.wait(); os.remove(wav); print("OK ->", OUT)
