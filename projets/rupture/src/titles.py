"""RUPTURE - textes en calques, ajoutes apres le rendu 3D.

Usage :
  python3 src/titles.py composite <images_rendues> <images_finales>   (textes + vignettage)
  python3 src/titles.py calques <dossier>                             (PNG transparents + SVG editable)
La mise en page lit titres.json : titre, signature, artiste, date, lieu, mention.
Un champ vide n'est pas affiche.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
W, H = 1080, 1920
SS = 2  # sur-echantillonnage du trace


def load_cfg():
    with open(os.path.join(ROOT, "titres.json"), encoding="utf-8") as f:
        return json.load(f)


def smooth(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def font(path, size, wght=None, opsz=None):
    f = ImageFont.truetype(os.path.join(ROOT, path), int(size))
    if wght is not None:
        try:
            f.set_variation_by_axes([wght, opsz or 96])
        except Exception:
            pass
    return f


def text_width(f, s, track):
    return sum(f.getlength(c) for c in s) + track * (len(s) - 1)


def draw_tracked(draw, f, s, cx, y, track, fill):
    x = cx - text_width(f, s, track) / 2
    for c in s:
        draw.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + track


def layout(cfg):
    """elements : (cle, texte, police, taille, interlettrage en em, y du haut)"""
    els = []
    y = 205
    if cfg.get("titre"):
        els.append(("titre", cfg["titre"], cfg["police_titre"], 150, 0.07, y, cfg.get("graisse_titre", 700)))
        y += 238
    if cfg.get("signature"):
        els.append(("signature", cfg["signature"], cfg["police_texte"], 32, 0.30, y, None))
        y += 70
    infos = "  ·  ".join(v for v in (cfg.get("artiste"), cfg.get("date"), cfg.get("lieu")) if v)
    if infos:
        els.append(("infos", infos.upper(), cfg["police_texte"], 26, 0.22, y, None))
        y += 60
    if cfg.get("mention"):
        els.append(("mention", cfg["mention"], cfg["police_mention"], 26, 0.55, y + 8, None))
    return els


def overlay(cfg, t, only=None):
    """calque RGBA des textes a l'instant t"""
    img = Image.new("L", (W * SS, H * SS), 0)
    col = tuple(cfg["couleur"])
    full = Image.new("L", (W * SS, H * SS), 0)
    for key, txt, fpath, size, track_em, y, wght in layout(cfg):
        if only and key != only:
            continue
        a, b = cfg["apparition"].get(key, [14.0, 14.5])
        p = smooth(a, b, t)
        if p <= 0:
            continue
        f = font(fpath, size * SS, wght, 96)
        track = (track_em + (1 - p) * (0.10 if key == "titre" else 0.06)) * size * SS
        layer = Image.new("L", (W * SS, H * SS), 0)
        d = ImageDraw.Draw(layer)
        dy = (1 - p) * 16 * SS
        draw_tracked(d, f, txt, W * SS / 2, y * SS + dy, track, 255)
        if key == "titre" and p < 1:
            layer = layer.filter(ImageFilter.GaussianBlur((1 - p) * 7 * SS))
        if key == "signature":
            # filet fin entre le titre et la signature
            lw = int(64 * SS * p)
            d.rectangle([W * SS / 2 - lw, (y - 42) * SS, W * SS / 2 + lw, (y - 42) * SS + 2 * SS], fill=255)
        arr = np.asarray(layer, dtype=np.float32) * p
        full = Image.fromarray(np.maximum(np.asarray(full, dtype=np.float32), arr).astype(np.uint8))
    alpha = full.resize((W, H), Image.LANCZOS)
    rgba = Image.new("RGBA", (W, H), col + (0,))
    rgba.putalpha(alpha)
    return rgba


_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        y, x = np.mgrid[0:H, 0:W]
        dx = (x - W / 2) / (W / 2)
        dy = (y - H / 2) / (H / 2)
        r = np.sqrt(dx * dx * 0.9 + dy * dy * 0.55)
        _VIG = (1.0 - 0.14 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None]
    return _VIG


def composite(src_dir, dst_dir):
    cfg = load_cfg()
    os.makedirs(dst_dir, exist_ok=True)
    files = sorted(f for f in os.listdir(src_dir) if f.endswith(".png"))
    cache = {}
    for fn in files:
        fr = int(fn[1:5])
        t = fr / FPS
        im = Image.open(os.path.join(src_dir, fn)).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        a = np.asarray(im, dtype=np.float32) * vignette()
        key = round(min(t, 15.0), 4)
        if t >= 13.9:
            if key not in cache:
                cache[key] = overlay(cfg, t)
            ov = cache[key]
            al = np.asarray(ov.getchannel("A"), dtype=np.float32)[..., None] / 255.0
            a = a * (1 - al) + np.array(cfg["couleur"], dtype=np.float32) * al
        Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(dst_dir, fn))
    print(f"{len(files)} images composees -> {dst_dir}")


def export_layers(out_dir):
    """un PNG transparent par element (etat final) + une maquette SVG editable"""
    cfg = load_cfg()
    os.makedirs(out_dir, exist_ok=True)
    els = layout(cfg)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '  <!-- Calques de titres RUPTURE. Polices : Bodoni Moda (OFL), Inter (OFL). -->']
    col = "#%02x%02x%02x" % tuple(cfg["couleur"])
    for key, txt, fpath, size, track_em, y, wght in els:
        overlay(cfg, 30.0, only=key).save(os.path.join(out_dir, f"calque_{key}.png"))
        fam = "Bodoni Moda" if "Bodoni" in fpath else "Inter"
        weight = wght or (600 if "SemiBold" in fpath else 500)
        f = font(fpath, size, wght, 96)
        asc = f.getbbox("H")[1]
        svg.append(f'  <text id="{key}" x="{W / 2}" y="{y + size * 0.86:.1f}" text-anchor="middle" '
                   f'font-family="{fam}" font-weight="{weight}" font-size="{size}" '
                   f'letter-spacing="{track_em * size:.1f}" fill="{col}">{txt}</text>')
    svg.append("</svg>")
    with open(os.path.join(out_dir, "titres.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"calques -> {out_dir}")


if __name__ == "__main__":
    if sys.argv[1] == "composite":
        composite(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "calques":
        export_layers(sys.argv[2])
