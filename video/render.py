"""Motion design : offre abonnement salle de sport 20 €/mois au lieu de 34 €.
Rendu : python3 render.py  ->  promo_abonnement.mp4 (1080x1920, 30 fps)"""
import math, subprocess, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 15.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promo_abonnement.mp4")
HANDLE = "@toncompte"   # <- remplace par ton pseudo / numéro

BG = (14, 14, 18); WHITE = (245, 245, 245); GREY = (150, 150, 160)
ACC = (196, 255, 46); RED = (255, 64, 80); DARK = (20, 20, 24)
F = "/usr/share/fonts/opentype/inter/"
def font(w, s): return ImageFont.truetype(F + {"black": "Inter-Black.otf", "xb": "Inter-ExtraBold.otf",
                                                "b": "Inter-Bold.otf", "sb": "Inter-SemiBold.otf"}[w], s)
if not os.path.exists(F + "Inter-Black.otf"):
    def font(w, s): return ImageFont.truetype(F + ("Inter-ExtraBold.otf" if w in ("black", "xb") else "Inter-Bold.otf"), s)

def clamp(x, a=0, b=1): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def out_cubic(x): return 1 - (1 - x) ** 3
def in_cubic(x): return x ** 3
def out_back(x, s=1.9): x -= 1; return x * x * ((s + 1) * x + s) + 1
def out_elastic(x):
    if x in (0, 1): return x
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1
def lerp(a, b, x): return a + (b - a) * x
def mix(c1, c2, x): return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))

def text_img(txt, f, color):
    l, t, r, b = f.getbbox(txt)
    im = Image.new("RGBA", (r - l + 20, b - t + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - l, 10 - t), txt, font=f, fill=color)
    return im

def paste(canvas, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0 or scale <= 0.01: return
    if scale != 1: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

def txt(canvas, s, f, color, cx, cy, **k): paste(canvas, text_img(s, f, color), cx, cy, **k)

# animated in/out helper: slide up + fade
def show(t, t_in, t_out, d=0.45):
    a = out_cubic(prog(t, t_in, t_in + d)); b = in_cubic(prog(t, t_out - 0.3, t_out))
    return a * (1 - b), (1 - a) * 80 - b * 60

rng = np.random.default_rng(7)
PART = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2, 6), rng.uniform(20, 90)) for _ in range(40)]

def background(t, flash):
    im = Image.new("RGBA", (W, H), BG + (255,)); d = ImageDraw.Draw(im)
    # diagonal moving stripes
    off = (t * 120) % 240
    for i in range(-10, 20):
        x = i * 240 + off
        d.polygon([(x, 0), (x + 60, 0), (x + 60 - H * 0.5, H), (x - H * 0.5, H)], fill=(22, 22, 28, 255))
    # glow blob
    gx = W / 2 + math.sin(t * 0.8) * 250; gy = H * 0.45 + math.cos(t * 0.6) * 300
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([gx - 420, gy - 420, gx + 420, gy + 420], fill=ACC + (38,))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    for (x, y, r, v) in PART:
        yy = (y - t * v) % H
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=ACC + (90,))
    if flash > 0: im.alpha_composite(Image.new("RGBA", (W, H), WHITE + (int(110 * flash),)))
    return im

def dumbbell(canvas, cx, cy, s, rot, alpha):
    im = Image.new("RGBA", (500, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([90, 98, 410, 122], 10, fill=WHITE)
    for x in (60, 400): d.rounded_rectangle([x, 20, x + 40, 200], 14, fill=ACC)
    for x in (20, 440): d.rounded_rectangle([x, 55, x + 40, 165], 14, fill=ACC)
    paste(canvas, im, cx, cy, s, alpha, rot)

def frame(t):
    flashes = [3.0, 6.0, 9.6, 12.4]
    flash = max([1 - prog(t, f, f + 0.25) if t >= f else 0 for f in flashes])
    c = background(t, flash)
    d = ImageDraw.Draw(c)

    # ---- Scene 1 : hook (0 - 3s)
    if t < 3.1:
        a, dy = show(t, 0.1, 3.0)
        txt(c, "TA SALLE", font("black", 150), WHITE, W / 2, 700 + dy, alpha=a)
        a2, dy2 = show(t, 0.35, 3.0)
        txt(c, "DE SPORT", font("black", 150), WHITE, W / 2, 870 + dy2, alpha=a2)
        p = out_back(prog(t, 0.8, 1.3))
        a3, _ = show(t, 0.8, 3.0)
        txt(c, "TROP CHÈRE ?", font("black", 120), ACC, W / 2, 1080, scale=p, alpha=a3, rot=math.sin(t * 6) * 2)
        dumbbell(c, W / 2, 1400, out_back(prog(t, 1.2, 1.7)) * 0.9, math.sin(t * 3) * 12, a3)

    # ---- Scene 2 : prix normal (3 - 6s)
    if 2.9 < t < 6.1:
        a, dy = show(t, 3.0, 6.0)
        txt(c, "Abonnement Basic-Fit", font("b", 72), GREY, W / 2, 620 + dy, alpha=a)
        txt(c, "prix habituel", font("sb", 56), GREY, W / 2, 710 + dy, alpha=a)
        n = int(round(lerp(0, 34, out_cubic(prog(t, 3.2, 4.2)))))
        p = out_back(prog(t, 3.1, 3.6))
        txt(c, f"{n} €", font("black", 330), WHITE, W / 2, 980, scale=p, alpha=a)
        txt(c, "/ mois", font("b", 80), GREY, W / 2, 1210, alpha=a)
        s = out_cubic(prog(t, 4.6, 5.0))  # strike-through
        if s > 0:
            x0, x1 = 170, 910; xe = lerp(x0, x1, s)
            line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(line).line([(x0, 1060), (xe, 1060 - (xe - x0) * 0.22)], fill=RED + (int(255 * a),), width=34)
            c.alpha_composite(line)
        if t > 5.0:
            sh = math.sin(t * 60) * 10 * (1 - prog(t, 5.0, 5.4))
            txt(c, "TROP CHER.", font("black", 96), RED, W / 2 + sh, 1420, alpha=a * out_cubic(prog(t, 5.0, 5.2)))

    # ---- Scene 3 : nouveau prix (6 - 9.6s)
    if 5.9 < t < 9.7:
        a, dy = show(t, 6.0, 9.6)
        txt(c, "AVEC MOI", font("black", 110), WHITE, W / 2, 470 + dy, alpha=a)
        p = out_elastic(prog(t, 6.2, 7.2))
        # circle burst
        r = lerp(0, 430, out_cubic(prog(t, 6.2, 6.8)))
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([W / 2 - r, 1000 - r, W / 2 + r, 1000 + r], fill=ACC + (int(255 * a),))
        c.alpha_composite(ring)
        pulse = 1 + 0.03 * math.sin((t - 7.2) * 8) if t > 7.2 else 1
        txt(c, "20 €", font("black", 300), DARK, W / 2, 970, scale=p * pulse, alpha=a)
        txt(c, "/ MOIS", font("black", 80), DARK, W / 2, 1180, scale=p, alpha=a)
        b = out_back(prog(t, 7.4, 7.9))
        badge = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); bd = ImageDraw.Draw(badge)
        bd.ellipse([0, 0, 299, 299], fill=RED)
        bd.text((150, 150), "-41%", font=font("black", 90), fill=WHITE, anchor="mm")
        paste(c, badge, 860, 700, b * 0.95, a, 15 + math.sin(t * 4) * 6)
        txt(c, "au lieu de 34 €", font("xb", 76), WHITE, W / 2, 1530 + dy, alpha=a * out_cubic(prog(t, 7.8, 8.2)))

    # ---- Scene 4 : bénéfices (9.6 - 12.4s)
    if 9.5 < t < 12.5:
        a, dy = show(t, 9.6, 12.4)
        txt(c, "TU ÉCONOMISES", font("black", 100), WHITE, W / 2, 560 + dy, alpha=a)
        n = int(round(lerp(0, 168, out_cubic(prog(t, 9.8, 10.8)))))
        txt(c, f"{n} €", font("black", 260), ACC, W / 2, 800, scale=out_back(prog(t, 9.7, 10.2)), alpha=a)
        txt(c, "PAR AN", font("black", 90), WHITE, W / 2, 990 + dy, alpha=a)
        items = ["Paiement au mois", "Même prix chaque mois", "Simple et rapide"]
        for i, s in enumerate(items):
            ai, dyi = show(t, 10.6 + i * 0.3, 12.4)
            y = 1220 + i * 150
            x = 130 + (1 - out_cubic(prog(t, 10.6 + i * 0.3, 11.0 + i * 0.3))) * -300
            row = Image.new("RGBA", (W, H), (0, 0, 0, 0)); rd = ImageDraw.Draw(row)
            rd.rounded_rectangle([x, y - 55, x + 820, y + 55], 30, fill=(32, 32, 40, int(255 * ai)))
            rd.ellipse([x + 20, y - 35, x + 90, y + 35], fill=ACC + (int(255 * ai),))
            rd.line([(x + 38, y), (x + 52, y + 15), (x + 74, y - 14)], fill=DARK + (int(255 * ai),), width=10)
            rd.text((x + 120, y), s, font=font("b", 58), fill=WHITE + (int(255 * ai),), anchor="lm")
            c.alpha_composite(row)

    # ---- Scene 5 : CTA (12.4 - 15s)
    if t > 12.3:
        a = out_cubic(prog(t, 12.4, 12.8))
        txt(c, "INTÉRESSÉ ?", font("black", 130), WHITE, W / 2, 680 + (1 - a) * 80, alpha=a)
        txt(c, "20 € / mois", font("black", 150), ACC, W / 2, 880, scale=out_back(prog(t, 12.6, 13.1)), alpha=a)
        b = out_back(prog(t, 13.0, 13.5)); pulse = 1 + 0.04 * math.sin((t - 13.5) * 7) if t > 13.5 else 1
        btn = Image.new("RGBA", (820, 190), (0, 0, 0, 0)); bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle([0, 0, 819, 189], 95, fill=ACC)
        bd.text((410, 95), "ÉCRIS-MOI EN DM", font=font("black", 72), fill=DARK, anchor="mm")
        paste(c, btn, W / 2, 1180, b * pulse, a)
        txt(c, HANDLE, font("xb", 80), WHITE, W / 2, 1380, alpha=out_cubic(prog(t, 13.4, 13.8)))
        txt(c, "Places limitées", font("sb", 52), GREY, W / 2, 1490, alpha=out_cubic(prog(t, 13.7, 14.1)))
        # final fade
        fo = prog(t, 14.6, 15.0)
        if fo > 0: c.alpha_composite(Image.new("RGBA", (W, H), BG + (int(255 * fo),)))

    # progress bar
    d = ImageDraw.Draw(c); d.rectangle([0, H - 14, W * t / DUR, H], fill=ACC)
    return c.convert("RGB")

def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n)
    bpm = 120; beat = 60 / bpm
    def add(sig, t0):
        i = int(t0 * sr); j = min(n, i + len(sig)); out[i:j] += sig[: j - i]
    tk = np.arange(int(0.35 * sr)) / sr
    kick = np.sin(2 * np.pi * (50 + 110 * np.exp(-tk * 25)) * tk) * np.exp(-tk * 9)
    th = np.arange(int(0.05 * sr)) / sr
    hat = np.random.default_rng(1).uniform(-1, 1, len(th)) * np.exp(-th * 90) * 0.18
    tb = np.arange(int(beat * sr)) / sr
    for k in range(int(DUR / beat)):
        t0 = k * beat
        if t0 > 14.6: break
        add(kick * 0.8, t0); add(hat, t0 + beat / 2)
        note = [55, 55, 65.4, 49][(k // 4) % 4]
        add(np.sign(np.sin(2 * np.pi * note * tb)) * np.exp(-tb * 6) * 0.12, t0)
    tw = np.arange(int(0.5 * sr)) / sr
    whoosh = np.random.default_rng(2).normal(0, 1, len(tw)) * np.sin(np.pi * tw / 0.5) ** 2 * 0.25
    for f in [2.75, 5.75, 9.35, 12.15]: add(whoosh, f)
    tc = np.arange(int(0.6 * sr)) / sr
    ding = (np.sin(2 * np.pi * 1318 * tc) + 0.5 * np.sin(2 * np.pi * 1975 * tc)) * np.exp(-tc * 6) * 0.3
    add(ding, 6.2); add(ding, 13.0)
    env = np.ones(n); fo = int(0.5 * sr); env[-fo:] = np.linspace(1, 0, fo)
    out = np.tanh(out * env * 1.2) * 0.8
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:  # preview frames: python3 render.py 1.5 7 ...
        for s in sys.argv[1:]: frame(float(s)).save(f"preview_{s}.png")
        sys.exit()
    wav = OUT.replace(".mp4", ".wav"); make_audio(wav)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264",
                          "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
                          "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait(); os.remove(wav); print("OK ->", OUT)
