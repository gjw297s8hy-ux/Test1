"""Ciel du desert precalcule (numpy) en image equirectangulaire lineaire.

Gradient creme, horizon dore, halo et disque solaire, cirrus fins pres de l'horizon,
montagnes lointaines noyees dans la brume. Un seul calcul au lancement : le ciel est
ensuite lu comme une texture (rapide), pour le fond comme pour la brume des materiaux.
"""
import math
import numpy as np

import sim


def _vnoise2(x, y, seed):
    r = np.random.RandomState(seed)
    tab = r.uniform(0, 1, (256, 256))
    xi = np.floor(x).astype(int)
    yi = np.floor(y).astype(int)
    fx = x - xi
    fy = y - yi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = tab[xi % 256, yi % 256]
    b = tab[(xi + 1) % 256, yi % 256]
    c = tab[xi % 256, (yi + 1) % 256]
    d = tab[(xi + 1) % 256, (yi + 1) % 256]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm2(x, y, octaves, seed, gain=0.55):
    s = np.zeros_like(x)
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        s += amp * _vnoise2(x, y, seed + o)
        tot += amp
        x = x * 2.03 + 17.1
        y = y * 2.03 + 5.3
        amp *= gain
    return s / tot


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def sky_color(d):
    """d : (...,3) directions normalisees -> RGB lineaire"""
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    sun = sim.SUN_DIR
    dd = x * sun[0] + y * sun[1] + z * sun[2]
    dpos = np.clip(dd, 0, 1)
    hz = np.maximum(z, -0.2)
    g = smooth(0.0, 0.55, hz) ** 0.7
    horizon = np.array([1.0, 0.70, 0.45])
    zenith = np.array([0.62, 0.60, 0.585])
    col = horizon * (1 - g[..., None]) + zenith * g[..., None]
    # le cote du soleil est plus chaud et lumineux
    side = dpos ** 2
    col = col * (0.82 + 0.3 * side[..., None])
    below = smooth(0.0, -0.06, z)
    col = col * (1 - below[..., None]) + np.array([0.92, 0.70, 0.50]) * below[..., None]
    col = col + (dpos ** 5)[..., None] * np.array([0.42, 0.24, 0.09])
    col = col + (dpos ** 60)[..., None] * np.array([1.3, 0.85, 0.45])
    col = col + (dpos ** 900)[..., None] * np.array([6.0, 4.6, 3.0])
    # nuages fins (projection sur un plan)
    inv = 1.0 / (hz + 0.035)
    cx = x * inv * 0.55
    cy = y * inv * 0.55 * 0.25
    n = fbm2(cx * 4.0 + 50, cy * 4.0 + 50, 6, 9)
    cl = smooth(0.56, 0.78, n) * smooth(0.005, 0.03, hz) * smooth(0.22, 0.07, hz) * 0.55
    cloud = np.array([1.0, 0.84, 0.70]) * (1 - smooth(0.6, 1.0, dd))[..., None] + \
        np.array([2.2, 1.5, 0.9]) * smooth(0.6, 1.0, dd)[..., None]
    col = col * (1 - cl[..., None]) + cloud * cl[..., None]
    # montagnes lointaines
    az = np.arctan2(x, y)
    m = fbm2(np.cos(az) * 3.0 * 1.6 + 30, np.sin(az) * 3.0 * 1.6 + 30, 5, 21, 0.6)
    prof = m * 0.050 - 0.008 - 0.006
    mm = smooth(-0.0015, 0.0015, prof - z) * smooth(-0.01, 0.0, z)
    mcol = np.array([0.70, 0.56, 0.44]) * (1 - smooth(0.7, 1.0, dd))[..., None] + \
        np.array([1.0, 0.72, 0.48]) * smooth(0.7, 1.0, dd)[..., None]
    col = col * (1 - mm[..., None]) + mcol * mm[..., None]
    # disque solaire
    disc = smooth(math.cos(math.radians(0.62)), math.cos(math.radians(0.50)), dd)
    col = col * (1 - disc[..., None]) + np.array([60.0, 52.0, 40.0]) * disc[..., None]
    return col


def equirect(w=4096, h=2048):
    """image RGBA (h, w, 4), convention Blender (u = -atan2(y,x)/2pi + 0.5)"""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    U, V = np.meshgrid(u, v)
    phi = (0.5 - U) * 2 * math.pi
    th = (V - 0.5) * math.pi
    d = np.stack([np.cos(phi) * np.cos(th), np.sin(phi) * np.cos(th), np.sin(th)], axis=-1)
    col = sky_color(d)
    return np.concatenate([col, np.ones(col.shape[:2] + (1,))], axis=-1).astype(np.float32)
