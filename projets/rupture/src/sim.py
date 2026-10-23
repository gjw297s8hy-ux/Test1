"""RUPTURE - animation procedurale deterministe (numpy pur, sans Blender).

Chaque fonction publique prend un temps t (secondes, camera) et rend un etat.
Le temps des objets (tau) est separe du temps camera : il se fige entre 7 et 10 s.
Toutes les graines sont fixes : une image ne depend que de son numero.
"""
import math
import numpy as np

_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")

# ---------------------------------------------------------------- timeline
FPS = 30
N_FRAMES = 540
T_IMPACT = 2.5
T_CUT = 6.0          # raccord sous occultation satin
T_FREEZE = 7.0
T_RESUME = 10.0
T_REVEAL = 14.0
T_END = 18.0
SEED = 1977
import os as _os
# variantes de comparaison (meme cadrage, meme lumiere) : RUPTURE_FRONT=A|B, RUPTURE_ASSEMBLY=A|B
FRONT_VARIANT = _os.environ.get("RUPTURE_FRONT", "A")
ASSEMBLY_VARIANT = _os.environ.get("RUPTURE_ASSEMBLY", "A")

Y0 = 28.0            # centre des gradins / de la scene finale

SUN_DIR = np.array([-0.403, 0.905, 0.139])
SUN_DIR = SUN_DIR / np.linalg.norm(SUN_DIR)


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(e0, e1, x):
    t = clamp01((np.asarray(x, dtype=float) - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def smoother(e0, e1, x):
    t = clamp01((np.asarray(x, dtype=float) - e0) / (e1 - e0))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def object_time(t):
    """Temps des objets : normal, fige 7-10 s, courte inversion puis reprise."""
    if t < T_FREEZE:
        return t
    if t < T_RESUME:
        return T_FREEZE
    u = t - T_RESUME
    if u < 0.5:
        # recul bref (souffle inverse) puis retour : derivee continue en u=0.5
        return T_FREEZE - 0.16 * math.sin(math.pi * u / 0.5)
    return T_FREEZE + 1.0 * (u - 0.5)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def axis_angle(axis, a):
    axis = np.asarray(axis, float)
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    x, y, z = axis
    c, s = math.cos(a), math.sin(a)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def mat_to_quat(m):
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    return q / np.linalg.norm(q)


def quat_to_mat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(q0, q1, u):
    d = float(np.dot(q0, q1))
    if d < 0:
        q1 = -q1
        d = -d
    if d > 0.9995:
        q = q0 + u * (q1 - q0)
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - u) * th) * q0 + math.sin(u * th) * q1) / math.sin(th)


def catmull(keys, t):
    """Catmull-Rom non uniforme (noeuds = temps), C1. keys: [(t, np.array)]"""
    ts = [k[0] for k in keys]
    vs = [np.asarray(k[1], float) for k in keys]
    if t <= ts[0]:
        return vs[0].copy()
    if t >= ts[-1]:
        return vs[-1].copy()
    i = 0
    while ts[i + 1] < t:
        i += 1
    t1, t2 = ts[i], ts[i + 1]
    p1, p2 = vs[i], vs[i + 1]
    t0 = ts[i - 1] if i > 0 else t1 - (t2 - t1)
    p0 = vs[i - 1] if i > 0 else p1 - (p2 - p1)
    t3 = ts[i + 2] if i + 2 < len(ts) else t2 + (t2 - t1)
    p3 = vs[i + 2] if i + 2 < len(ts) else p2 + (p2 - p1)
    # tangentes cardinales non uniformes
    m1 = (p2 - p0) / (t2 - t0)
    m2 = (p3 - p1) / (t3 - t1)
    h = t2 - t1
    s = (t - t1) / h
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    return h00 * p1 + h10 * h * m1 + h01 * p2 + h11 * h * m2


def vnoise1(x, seed):
    """bruit de valeur 1D lisse, deterministe"""
    rng = np.random.RandomState(seed)
    tab = rng.uniform(-1, 1, 512)
    x = np.asarray(x, float)
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    a = tab[i % 512]
    b = tab[(i + 1) % 512]
    return a + (b - a) * f


# ---------------------------------------------------------------- camera
# Plan A : 0 -> 6 s (macro puis vol au ras du sol sous la vague)
CAM_A = [
    # t,    position,                 cible,                  focale
    (0.0, (-0.075, -0.62, 0.30), (0.01, 0.0, 0.165), 85.0),
    (1.2, (-0.068, -0.58, 0.17), (0.008, 0.0, 0.11), 85.0),
    (2.5, (-0.055, -0.54, 0.036), (0.0, 0.0, 0.03), 85.0),
    (2.9, (-0.07, -0.5, 0.045), (0.25, 0.8, 0.08), 70.0),
    (3.35, (-0.2, -0.3, 0.1), (3.5, 9.0, 1.8), 30.0),
    (3.85, (-0.3, 0.8, 0.35), (4.65, 23.97, 7.0), 20.0),
    (4.45, (3.04, 7.92, 0.9), (7.28, 42.65, 12.0), 18.0),
    (5.05, (9.33, 18.38, 1.6), (9.1, 53.31, 16.0), 18.0),
    (5.55, (16.94, 28.34, 2.6), (12.55, 60.32, 20.0), 18.0),
    (6.0, (23.63, 37.89, 4.6), (17.83, 58.29, 24.0), 18.0),
]

# Plan B : 6 -> 18 s (blocs, arret, reconstruction, revelation)
ORBIT_C = np.array([0.0, 33.0, 8.0])
ORBIT_R = 21.0


def _orbit(phi_deg, z):
    p = math.radians(phi_deg)
    return (ORBIT_C[0] + ORBIT_R * math.cos(p), ORBIT_C[1] + ORBIT_R * math.sin(p), z)


CAM_FINAL = (-0.34, -0.92, 0.30)
TGT_FINAL = (-1.4, 28.0, 5.2)

CAM_B = [
    (6.0, (-6.6, 6.8, 2.4), (-1.0, 30.0, 9.0), 22.0),
    (6.5, (-8.4, 10.6, 7.4), (-0.5, 32.0, 8.5), 23.0),
    (7.0, _orbit(-114.0, 12.0), tuple(ORBIT_C), 24.0),
    (7.75, _orbit(-101.5, 13.2), tuple(ORBIT_C), 24.0),
    (8.5, _orbit(-89.0, 14.4), tuple(ORBIT_C), 24.0),
    (9.25, _orbit(-76.5, 15.6), tuple(ORBIT_C), 24.0),
    (10.0, _orbit(-64.0, 16.6), (0.0, 32.0, 7.0), 24.0),
    (11.0, (8.6, 6.5, 12.5), (0.0, 30.5, 5.5), 23.0),
    (12.2, (4.0, 0.6, 5.2), (-0.5, 29.0, 4.8), 21.5),
    (13.2, (0.55, -1.0, 1.0), (-1.2, 28.0, 5.0), 22.5),
    (14.0, (-0.12, -0.60, 0.25), TGT_FINAL, 24.0),
    (16.0, (-0.145, -0.612, 0.243), TGT_FINAL, 24.0),
    (18.0, (-0.165, -0.622, 0.238), TGT_FINAL, 24.0),
]


def _cam_eval(keys, t):
    pos = catmull([(k[0], np.array(k[1])) for k in keys], t)
    tgt = catmull([(k[0], np.array(k[2])) for k in keys], t)
    foc = float(catmull([(k[0], np.array([k[3]])) for k in keys], t)[0])
    return pos, tgt, foc


def card_contact_point():
    return np.array([0.0, 0.0, 0.0])


def camera(t):
    """-> dict(pos, target, roll(rad), focal(mm), focus(m), fstop, shot)"""
    if t < T_CUT:
        pos, tgt, foc = _cam_eval(CAM_A, t)
        shot = "A"
        if t < 2.75:
            # suivi de la carte pendant sa descente (avec un leger retard)
            Rc, tc = card_pose(max(t - 0.12, 0.0))
            cc = tc + Rc @ np.array([0.0, 0.0, 0.0])
            w = 1.0 - float(smoother(2.25, 2.75, t))
            tgt = tgt * (1 - w) + (cc + np.array([0.0, 0.0, -0.035])) * w
    else:
        pos, tgt, foc = _cam_eval(CAM_B, t)
        shot = "B"
    roll = 0.0
    # tremblement a l'impact (decroissant), deterministe
    if T_IMPACT <= t < T_IMPACT + 0.45:
        u = t - T_IMPACT
        amp = 0.0016 * math.exp(-u * 9.0)
        pos = pos + amp * np.array([vnoise1(u * 60, 11), vnoise1(u * 60, 12) * 0.4, vnoise1(u * 60, 13)])
        roll += 0.004 * math.exp(-u * 9.0) * float(vnoise1(u * 50, 14))
    # roulis sous la vague
    if 4.9 < t < T_CUT:
        roll += math.radians(5.0) * float(smoothstep(4.9, 5.6, t)) * math.sin((t - 4.9) * 2.2)
    # mise au point
    if shot == "A":
        d_card = float(np.linalg.norm(card_pose(t)[1] + card_pose(t)[0] @ np.array([0, 0.0, 0]) - pos))
        d_ground = float(np.linalg.norm(np.array([0.0, 0.0, 0.0]) - pos))
        if t < 1.5:
            focus = d_card
        elif t < 2.3:
            k = float(smoother(1.5, 2.3, t))
            focus = d_card * (1 - k) + d_ground * k
        elif t < 3.3:
            focus = d_ground + (t - 2.3) * 2.0 * float(smoothstep(2.6, 3.3, t))
        else:
            focus = 30.0
        fstop = 2.8 if t < 3.0 else 2.8 + 8.0 * float(smoothstep(3.0, 3.9, t))
    else:
        if t < 10.0:
            focus = float(np.linalg.norm(ORBIT_C - pos))
            fstop = 7.0
        else:
            k = float(smoother(11.5, 13.6, t))
            focus = float(np.linalg.norm(ORBIT_C - pos)) * (1 - k) + 14.0 * k
            fstop = 7.0 + 4.0 * k
    return dict(pos=np.asarray(pos), target=np.asarray(tgt), roll=roll, focal=foc,
                focus=max(focus, 0.05), fstop=fstop, shot=shot)


# ---------------------------------------------------------------- carte
CARD_W, CARD_H, CARD_T, CARD_R = 0.085, 0.135, 0.0028, 0.009


def card_outline(n_per_corner=12):
    """contour du rectangle arrondi (plan local XY), sens trigo"""
    hw, hh, r = CARD_W / 2, CARD_H / 2, CARD_R
    pts = []
    centers = [(hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180), (hw - r, -hh + r, 270)]
    for cx, cy, a0 in centers:
        for i in range(n_per_corner + 1):
            a = math.radians(a0 + 90.0 * i / n_per_corner)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


_CARD_PTS = None


def _card_pts():
    global _CARD_PTS
    if _CARD_PTS is None:
        o = card_outline(16)
        top = np.c_[o, np.full(len(o), CARD_T / 2)]
        bot = np.c_[o, np.full(len(o), -CARD_T / 2)]
        _CARD_PTS = np.vstack([top, bot])
    return _CARD_PTS


def _card_rot(t):
    tt = min(t, T_IMPACT)
    k = tt / T_IMPACT
    roll = math.radians(40.0 - 7.0 * k)       # rotation dans le plan : un angle vers le bas
    pitch = math.radians(58.0 + 6.0 * k)      # carte inclinee vers l'arriere
    yaw = math.radians(-20.0 + 6.0 * k + 1.2 * math.sin(tt * 1.7))
    R = rot_z(yaw) @ rot_x(pitch) @ rot_z(roll)
    if t > T_IMPACT:
        # leger tassement apres l'impact
        s = float(smoothstep(T_IMPACT, T_IMPACT + 0.18, t))
        R = rot_z(yaw) @ rot_x(pitch + math.radians(1.6) * s) @ rot_z(roll)
    return R


def card_pose(t):
    """-> (R 3x3, translation). L'angle le plus bas touche (0,0,0) a 2.50 s."""
    R = _card_rot(t)
    pts = _card_pts() @ R.T
    low = pts[np.argmin(pts[:, 2])]
    if t < T_IMPACT:
        k = t / T_IMPACT
        h = 0.40 * (1.0 - k ** 1.55)              # descend lentement puis prend du poids
        sway = np.array([0.006 * math.sin(t * 1.3), 0.004 * math.sin(t * 0.9 + 1), 0.0]) * (1 - k)
    else:
        h = -0.0055 * float(smoothstep(T_IMPACT, T_IMPACT + 0.07, t))   # l'angle s'enfonce dans le sel
        sway = np.zeros(3)
    tr = np.array([0.0, 0.0, h]) - low + sway
    return R, tr


# ---------------------------------------------------------------- onde au sol
def ring_radius(t):
    tau = t - T_IMPACT
    if tau <= 0:
        return -1.0
    return 6.0 * tau + 40.0 * tau ** 3


def ring_field(px, py, t):
    """deplacement vertical de l'onde + masque de fissures (0..1) en (px, py)"""
    tau = t - T_IMPACT
    r = np.sqrt(px * px + py * py)
    if tau <= 0:
        return np.zeros_like(r), np.zeros_like(r)
    rf = ring_radius(t)
    w = 0.08 + 0.07 * rf
    amp = (0.008 + 0.022 * rf) * min(1.0, 1.0)
    amp = np.minimum(amp, 1.1)
    d = (r - rf) / w
    # front avance + petit creux arriere ; s'amortit derriere le front
    bump = amp * (np.exp(-d * d) - 0.35 * np.exp(-((d + 1.6) ** 2)))
    bump *= np.exp(-np.clip(rf - r, 0, None) / (2.0 + 0.4 * rf)) * (r < rf + 4 * w)
    crack = clamp01((rf - r) / (0.3 + 0.1 * rf) + 0.5) * (r < 140)
    return bump, crack


# ---------------------------------------------------------------- nappe : la croute s'arrache, sa doublure est du satin
# Bande de croute. Le front d'arrachement (une ligne perpendiculaire a D) part du point
# de contact et file vers D. La croute arrachee se dresse depuis le pied (au front) et
# deferle vers l'impact : vue depuis la camera, on file le long du rouleau (ref. 02).
# Face superieure d'origine = exterieur (sel). Face inferieure revelee = interieur du
# rouleau : le sel s'en detache et le satin apparait, de la levre vers le pied.
ALPHA = math.radians(24.0)
D_DIR = np.array([math.cos(ALPHA), math.sin(ALPHA), 0.0])     # sens de propagation
E_DIR = np.array([-math.sin(ALPHA), math.cos(ALPHA), 0.0])    # le long de la crete
R0 = 2.2             # la carte reste sur une ile intacte
R_MAX = 62.0
E_MIN, E_MAX = -16.0, 78.0
SHEET_NPSI = 377     # echantillons le long de la crete (e)
SHEET_NR = 301       # echantillons dans le sens de propagation (d)
CRUST_T = 0.8        # epaisseur de la croute
T_TEAR0 = 2.80
T_TEAR1 = 6.0
TEAR_GAIN = 56.0
T_SAT0 = 3.75
T_SAT1 = 5.55


def _e_profile(e):
    """facteur de taille le long de la crete : extremites dechirees plus basses"""
    e = np.asarray(e, float)
    a = smoothstep(E_MIN, E_MIN + 22.0, e) * smoothstep(E_MAX, E_MAX - 26.0, e)
    return 0.35 + 0.65 * a


def tear_radius(t, e=0.0):
    u = np.clip((t - T_TEAR0) / (T_TEAR1 - T_TEAR0), 0.0, None)
    return R0 + TEAR_GAIN * u ** 1.15 * _e_profile(e)


def _curl_amount(t):
    # la levre se cambre puis plonge : 120 -> 205 -> 262 degres
    a = 120.0 + 85.0 * float(smoothstep(3.2, 5.4, t)) + 57.0 * float(smoothstep(5.2, 6.05, t))
    return math.radians(a)


def _profile(sig, ell, A):
    """angle phi(sigma) de la tangente (plan d-z). 180 = vers l'impact."""
    a = 0.20 * ell
    u1 = np.clip(sig / np.maximum(a, 1e-6), 0, 1)
    phi = math.pi - 0.5 * math.pi * (u1 * u1 * (3 - 2 * u1))
    u2 = np.clip((sig - a) / np.maximum(ell - a, 1e-6), 0, 1)
    phi = phi + A * (0.35 * u2 ** 1.3 + 0.65 * u2 ** 3.0)
    return phi


_SHEET_GRID = None


def sheet_grid():
    global _SHEET_GRID
    if _SHEET_GRID is None:
        es = np.linspace(E_MIN, E_MAX, SHEET_NPSI)
        ds = np.linspace(R0, R_MAX, SHEET_NR)
        _SHEET_GRID = (es, ds)
    return _SHEET_GRID


def sheet_rest(ES, DS):
    return ES[..., None] * E_DIR + DS[..., None] * D_DIR


def _sheet_eval(ES, DS, t):
    """ES, DS : (n, m). -> P, N(dessus), sigma, ell"""
    rf = tear_radius(t, ES[:, :1])
    ell = np.maximum(rf - R0, 1e-4)
    sig = np.clip(rf - DS, 0, None)
    A = _curl_amount(t)
    m = 400
    sg = np.linspace(0, 1, m)[None, :] * ell
    ph = _profile(sg, ell, A)
    dsg = ell / (m - 1)
    cr = np.cumsum(np.c_[np.zeros((len(ell), 1)), 0.5 * (np.cos(ph[:, 1:]) + np.cos(ph[:, :-1]))], axis=1) * dsg
    cz = np.cumsum(np.c_[np.zeros((len(ell), 1)), 0.5 * (np.sin(ph[:, 1:]) + np.sin(ph[:, :-1]))], axis=1) * dsg
    frac = np.clip(sig / ell, 0, 1) * (m - 1)
    i0 = np.clip(np.floor(frac).astype(int), 0, m - 2)
    w = frac - i0
    rows = np.arange(len(ell))[:, None]
    rad = cr[rows, i0] * (1 - w) + cr[rows, i0 + 1] * w
    z = cz[rows, i0] * (1 - w) + cz[rows, i0 + 1] * w
    phv = ph[rows, i0] * (1 - w) + ph[rows, i0 + 1] * w
    lifted = sig > 0
    rho = np.where(lifted, rf + rad, DS)
    z = np.where(lifted, z, 0.0)
    phv = np.where(lifted, phv, math.pi)
    P = ES[..., None] * E_DIR + rho[..., None] * D_DIR
    P[..., 2] = z
    nr_, nz_ = np.sin(phv), -np.cos(phv)
    N = nr_[..., None] * D_DIR
    N[..., 2] = nz_
    d = DS - rf
    swell = (0.05 * ell + 0.05) * np.exp(-((d - 0.6 - 0.04 * ell) / (0.9 + 0.06 * ell)) ** 2) * (d > 0)
    P[..., 2] += swell
    return P, N, sig, np.broadcast_to(ell, sig.shape)


def satin_front(t, ell):
    """sigma au-dela duquel la face interieure est du satin.
    A : part de la levre (premiere matiere arrachee, cote impact) et descend vers le pied.
    B : suit le pied a distance fixe (le satin apparait des que la croute se dresse)."""
    if FRONT_VARIANT == "B":
        return 1.2 + 0.07 * ell + 0.0 * t
    g = float(smoother(T_SAT0, T_SAT1, t))
    return ell * (1.0 - g) + 1.0 - 2.0 * g


def sheet_state(t):
    """-> P (NE,ND,3), N dessus, sat (0..1 face interieure), sig, crack"""
    es, ds = sheet_grid()
    ES, DS = np.meshgrid(es, ds, indexing="ij")
    P, N, sig, ell = _sheet_eval(ES, DS, t)
    front = satin_front(t, ell)
    behind = sig - front
    sat = clamp01(behind / 2.0 + 0.5) * (sig > 0)
    # les fissures deviennent des plis (dans le sens du deferlement)
    fold_amp = sat * smoothstep(0.0, 5.0, behind) * (0.35 + 0.65 * smoothstep(3, 25, ell))
    ph = 0.35 * DS + 0.8 * np.sin(DS * 0.11 + ES * 0.05)
    folds = (0.42 * np.sin(ES * (2 * math.pi / 3.6) + ph) +
             0.10 * np.sin(ES * (2 * math.pi / 2.3) - 1.3 * ph + 1.7) +
             0.12 * np.sin(ES * (2 * math.pi / 8.3) + 0.08 * DS))
    P = P - N * (folds * fold_amp)[..., None]
    _, crack = ring_field(P[..., 0], P[..., 1], t)
    return P, N, sat, sig, crack


def sheet_visible(t):
    return t < T_CUT


# ---------------------------------------------------------------- eclats qui se detachent du front
def _sheet_points(es, ds, t):
    P, N, sig, ell = _sheet_eval(np.asarray(es)[:, None], np.asarray(ds)[:, None], t)
    return P[:, 0], N[:, 0]


_DETACH_TSP = None


def detach_particles(t, n=2600, seed=SEED + 5):
    """morceaux de sel qui se detachent de la face inferieure au passage du front satin"""
    rng = np.random.RandomState(seed)
    e = rng.uniform(E_MIN + 3, E_MAX - 3, n)
    d = R0 + 0.5 + (R_MAX - R0 - 6.0) * rng.uniform(0, 1, n)
    size = 0.05 + 0.32 * rng.power(3.0, n) * rng.uniform(0.3, 1.0, n)
    size = np.where(rng.uniform(0, 1, n) < 0.07, size * 2.4, size)
    pid = rng.randint(0, 6, n)
    jit = rng.normal(0, 1, (n, 3))
    spin = rng.normal(0, 1, (n, 3)) * 3.0
    rot0 = rng.uniform(0, 2 * math.pi, (n, 3))
    global _DETACH_TSP
    if _DETACH_TSP is None:
        tt = np.linspace(T_TEAR0, T_TEAR1 + 0.3, 330)[:, None]
        rf = tear_radius(tt, e[None, :])
        ell = np.maximum(rf - R0, 1e-4)
        sig = rf - d[None, :]
        gg = smoother(T_SAT0, T_SAT1, tt)
        fr = ell * (1.0 - gg) + 1.0 - 2.0 * gg
        ok = (sig > 0.3) & (sig - fr > 0)
        first = np.argmax(ok, axis=0)
        _DETACH_TSP = np.where(ok.any(axis=0), tt[first, 0], 99.0)
    t_sp = _DETACH_TSP.copy()
    t_sp += rng.uniform(0.0, 0.1, n)
    pos = np.zeros((n, 3))
    rot = rot0.copy()
    scale = np.zeros(n)
    idx = np.where(t >= t_sp)[0]
    if len(idx):
        q = np.round(t_sp[idx] * 30.0) / 30.0
        p0 = np.zeros((len(idx), 3))
        v0 = np.zeros((len(idx), 3))
        nrm = np.zeros((len(idx), 3))
        for qv in np.unique(q):
            sel = np.where(q == qv)[0]
            Pa, Na = _sheet_points(e[idx[sel]], d[idx[sel]], qv)
            Pb, _ = _sheet_points(e[idx[sel]], d[idx[sel]], qv + 1.0 / 30.0)
            p0[sel] = Pa
            v0[sel] = (Pb - Pa) * 30.0
            nrm[sel] = Na
        p0 = p0 - nrm * (CRUST_T + size[idx, None] * 0.3)
        dt = t - t_sp[idx]
        v = v0 * 0.7 - nrm * 1.0 + jit[idx] * 0.9
        g = np.array([0, 0, -9.81])
        p = p0 + v * dt[:, None] + 0.5 * g * (dt ** 2)[:, None]
        floor = size[idx] * 0.35 + pit_depth(p[:, 0], p[:, 1], t)
        landed = p[:, 2] < floor
        p[landed, 2] = floor[landed]
        pos[idx] = p
        rot[idx] = rot0[idx] + spin[idx] * np.minimum(dt, 1.2)[:, None]
        scale[idx] = size[idx] * clamp01(dt / 0.06)
    return pos, rot, scale, pid


def pit_depth(px, py, t):
    """logement de la croute : creux de la bande arrachee (comble pendant la reconstruction)"""
    px = np.asarray(px, float)
    py = np.asarray(py, float)
    d = px * D_DIR[0] + py * D_DIR[1]
    e = px * E_DIR[0] + py * E_DIR[1]
    ins = (smoothstep(R0 - 0.05, R0 + 0.05, d) * smoothstep(R_MAX + 0.05, R_MAX - 0.05, d)
           * smoothstep(E_MIN - 0.05, E_MIN + 0.05, e) * smoothstep(E_MAX + 0.05, E_MAX - 0.05, e))
    heal = 1.0 - float(smoother(10.3, 11.8, t))
    return -CRUST_T * ins * heal


# ---------------------------------------------------------------- gradins / blocs
TIERS = [
    # x0, x1, y0, y1, z_bas, z_haut, colonnes, rangs
    (-10.5, 10.5, Y0 - 4.6, Y0 + 4.4, 0.0, 0.50, 6, 3),
    (-8.9, 8.9, Y0 - 3.5, Y0 + 3.8, 0.50, 1.00, 5, 3),
    (-7.3, 7.3, Y0 - 2.5, Y0 + 3.2, 1.00, 1.45, 4, 2),
]
STAGE_FLOOR = (-6.0, 6.0, Y0 - 1.3, Y0 + 2.6, 1.45, 1.60)
BACKDROP = (-3.9, 3.9, Y0 + 2.15, Y0 + 2.6, 1.60, 5.55)
GAP = 0.012


def block_cells():
    """decoupe des gradins en cellules (appareillage decale). -> liste de dicts"""
    rng = np.random.RandomState(SEED + 21)
    cells = []
    for ti, (x0, x1, y0, y1, zb, zt, nc, nr) in enumerate(TIERS):
        yb = np.linspace(y0, y1, nr + 1)
        yb[1:-1] += rng.uniform(-0.25, 0.25, nr - 1)
        for r in range(nr):
            off = 0.5 if (r % 2) else 0.0
            xb = np.linspace(x0, x1, nc + 1)
            step = (x1 - x0) / nc
            inner = xb[1:-1] + (off - 0.25) * step * 0.5 + rng.uniform(-0.3, 0.3, nc - 1)
            xb = np.concatenate([[x0], np.sort(inner), [x1]])
            for c in range(nc):
                cells.append(dict(tier=ti, x0=xb[c] + GAP, x1=xb[c + 1] - GAP,
                                  y0=yb[r] + GAP, y1=yb[r + 1] - GAP, zb=zb, zt=zt))
    return cells


def _poisson(rng, n, lo, hi, dmin, avoid=None, tries=4000):
    pts = []
    for _ in range(tries):
        p = rng.uniform(lo, hi)
        if avoid is not None and not avoid(p):
            continue
        if all(np.linalg.norm((p - q) * np.array([1, 1, 1.4])) > dmin for q in pts):
            pts.append(p)
            if len(pts) == n:
                break
    return np.array(pts)


_LAYOUT = None


def block_layout():
    """poses : origine (6 s), vitesse initiale, suspendue (7 s), finale. Fixe par graine."""
    global _LAYOUT
    if _LAYOUT is not None:
        return _LAYOUT
    rng = np.random.RandomState(SEED + 33)
    cells = block_cells()
    n = len(cells)

    def avoid(p):
        # dans une ellipse autour du centre, hors de la trajectoire d'orbite
        dx, dy = (p[0] - ORBIT_C[0]) / 17.5, (p[1] - ORBIT_C[1]) / 15.0
        return dx * dx + dy * dy < 1.0
    sus = _poisson(rng, n, np.array([-18, 18, 3.0]), np.array([18, 48, 19.0]), 5.2, avoid)
    while len(sus) < n:
        sus = np.vstack([sus, rng.uniform([-12, 22, 4], [12, 44, 17])])
    # les grandes cellules (rang bas) plutot en bas, les hautes plutot au centre
    area = np.array([(c["x1"] - c["x0"]) * (c["y1"] - c["y0"]) for c in cells])
    order_cells = np.argsort(-area)
    order_pos = np.argsort(sus[:, 2] + rng.uniform(-3, 3, n))
    sus_assigned = np.zeros((n, 3))
    sus_assigned[order_cells] = sus[order_pos]
    k = 2.3
    blocks = []
    C0 = np.array([0.0, 34.0, 6.5])
    for i, c in enumerate(cells):
        S = sus_assigned[i]
        P0 = C0 + (S - C0) * np.array([0.42, 0.35, 0.25]) + np.array([0, -3.0, -1.0]) + rng.uniform(-1, 1, 3)
        V = (S - P0) * k / (1 - math.exp(-k))
        Rs = rot_z(rng.uniform(-0.7, 0.7)) @ rot_x(rng.uniform(-0.2, 0.2)) @ rot_y(rng.uniform(-0.2, 0.2))
        spin_axis = rng.normal(0, 1, 3)
        spin_ang = rng.uniform(0.4, 0.9) * rng.choice([-1, 1])
        F = np.array([(c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2, c["zt"]])
        blocks.append(dict(cell=c, S=S, P0=P0, V=V, k=k, Rs=Rs, spin_axis=spin_axis,
                           spin_ang=spin_ang, F=F, root=rng.uniform(0.8, 1.5)))
    # ordre de construction : gradin du bas d'abord, du centre vers l'exterieur
    for b in blocks:
        c = b["cell"]
        r = math.hypot(b["F"][0] / 10.0, (b["F"][1] - Y0) / 4.5)
        if ASSEMBLY_VARIANT == "B":
            # vague unique d'ouest en est, tous gradins confondus
            b["t0"] = 10.38 + 0.085 * (b["F"][0] + 10.5) + 0.25 * c["tier"] + rng.uniform(0, 0.1)
        else:
            # gradin par gradin, du centre vers l'exterieur
            b["t0"] = 10.38 + 0.62 * c["tier"] + 0.42 * r + rng.uniform(0, 0.12)
        b["dur"] = 1.55 + rng.uniform(-0.12, 0.12)
    _LAYOUT = blocks
    return blocks


def _rise(b, tau):
    """trajectoire de montee avec inertie (6 -> 7 s, prolongeable)"""
    d = max(tau - T_CUT, -0.3)
    k = b["k"]
    disp = b["V"] * (1 - math.exp(-k * d)) / k
    P = b["P0"] + disp
    ang = b["spin_ang"] * (1 - math.exp(-k * d)) / (1 - math.exp(-k))
    R = b["Rs"] @ axis_angle(b["spin_axis"], ang - b["spin_ang"])
    return P, R


def block_pose(b, t):
    """-> (R, P, root_retract 0..1, landed_time or None)"""
    tau = object_time(t)
    P, R = _rise(b, tau)
    t0, dur = b["t0"], b["dur"]
    if t <= t0:
        return R, P, 0.0
    u = clamp01((t - t0) / dur)
    # parametre : depart dans la direction de la trajectoire precedente, puis descente dans la loge
    e = float(smoother(0, 1, u))
    Ps, Rs = _rise(b, object_time(t0))
    v_dir = b["V"] / (np.linalg.norm(b["V"]) + 1e-9)
    c1 = Ps + v_dir * 3.0
    c2 = b["F"] + np.array([0, 0, 4.5])
    p = ((1 - e) ** 3) * Ps + 3 * ((1 - e) ** 2) * e * c1 + 3 * (1 - e) * e * e * c2 + e ** 3 * b["F"]
    q = slerp(mat_to_quat(Rs), np.array([1.0, 0, 0, 0]), float(smoother(0.1, 0.95, u)))
    R = quat_to_mat(q)
    # contact : petit rebond amorti apres la pose
    t_land = t0 + dur
    if t > t_land:
        dt = t - t_land
        p = b["F"] + np.array([0, 0, 0.05 * math.exp(-dt * 7.0) * math.sin(dt * 26.0)])
    root = float(smoothstep(0.55, 1.0, u))
    return R, p, root


def block_land_time(b):
    return b["t0"] + b["dur"]


# ---------------------------------------------------------------- scene noire
STAGE_SUS = np.array([1.2, 37.5, 7.2])


def stage_pose(t):
    """la scene monte du logement de la croute, flotte, puis s'aligne au centre."""
    tau = object_time(t)
    F = np.array([0.0, 0.0, 0.0])  # la scene est modelisee directement a sa place finale
    S_off = STAGE_SUS - np.array([0.0, Y0 + 0.65, 1.45])
    start_off = S_off + np.array([0, 0, -11.5])
    k = 2.0
    d = max(tau - T_CUT, 0.0)
    rise = (1 - math.exp(-k * d)) / (1 - math.exp(-k))
    off = start_off + (S_off - start_off) * rise
    Rsus = rot_z(math.radians(14.0)) @ rot_x(math.radians(-7.0)) @ rot_y(math.radians(5.0))
    R = Rsus
    t0, t1 = 12.15, 13.45
    if t > t0:
        u = float(smoother(t0, t1, t))
        off_s = off
        off = off_s * (1 - u) + np.array([0, 0, 0.9]) * math.sin(math.pi * u) * (1 - u)
        R = quat_to_mat(slerp(mat_to_quat(Rsus), np.array([1.0, 0, 0, 0]), u))
        if t > t1:
            dt = t - t1
            off = np.array([0, 0, 0.035 * math.exp(-dt * 8) * math.sin(dt * 30)])
    return R, off


def amber_lines(t):
    """intensite des trois lignes ambrees (allumage successif)"""
    return [float(smoothstep(a, a + 0.22, t)) for a in (13.25, 13.5, 13.75)]


# ---------------------------------------------------------------- satin : rubans -> auvent
K_STRIPS = 10
NU = 150
NV = 9


def _canopy_spine():
    pts = [(-0.02, (-13.0, Y0 + 1.4, 0.5)),
           (0.10, (-11.6, Y0 + 1.1, 6.5)),
           (0.24, (-9.0, Y0 + 0.4, 12.4)),
           (0.33, (-6.6, Y0 + 0.0, 13.6)),
           (0.47, (-2.0, Y0 - 0.7, 12.0)),
           (0.64, (3.6, Y0 - 1.4, 9.3)),
           (0.82, (9.0, Y0 - 2.1, 4.8)),
           (1.0, (13.6, Y0 - 2.8, 0.05))]
    return [(u, np.array(p)) for u, p in pts]


def canopy_final(u, v):
    """surface finale (u le long de l'arche, v dans la largeur, 0..1). L'echine est le bord haut,
    le tissu retombe : grand rideau a gauche jusqu'au sol, bras qui s'affine vers la droite."""
    keys = _canopy_spine()
    us = np.linspace(0, 1, 400)
    sp = np.array([catmull(keys, x) for x in us])
    B = np.stack([np.interp(u, us, sp[:, i]) for i in range(3)], axis=-1)
    du = 1e-3
    B2 = np.stack([np.interp(np.clip(u + du, 0, 1), us, sp[:, i]) for i in range(3)], axis=-1)
    T = B2 - B
    T /= np.linalg.norm(T, axis=-1, keepdims=True) + 1e-9
    W = np.interp(u, [0.0, 0.12, 0.28, 0.42, 0.6, 0.8, 0.93, 1.0], [10.0, 13.0, 13.5, 8.0, 5.0, 3.2, 1.4, 0.3])
    k = smoothstep(0.30, 0.48, u)[..., None]
    a_left = np.array([-0.30, 0.25, -0.92])     # rideau : retombe vers le bas, un peu vers l'exterieur
    a_arm = np.array([0.05, 0.62, -0.78])       # bras : retombe en arriere, au-dessus du fond de scene
    across = a_left * (1 - k) + a_arm * k
    across /= np.linalg.norm(across, axis=-1, keepdims=True)
    vv = np.asarray(v, float)
    P = B + (vv * W)[..., None] * across
    nrm = np.cross(T, across)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-9
    # gonflement doux au milieu de la largeur, bord libre qui ondule
    billow = (0.9 * np.sin(np.pi * vv) * np.interp(u, [0, 0.3, 0.6, 1], [0.6, 1.4, 1.0, 0.2])
              + 0.35 * vv ** 2 * np.sin(u * 30.0))
    # plis lourds orientes dans le sens de la chute, plus nombreux pres du sol
    foot = np.interp(u, [0, 0.15, 0.35, 1], [1.0, 0.8, 0.3, 0.15])
    fz = (0.45 * np.sin(u * 95.0 + vv * 2.0) + 0.2 * np.sin(u * 210.0 - vv * 3.0 + 1.3)) * (0.3 + foot) * (0.25 + vv)
    P += nrm * (billow + fz)[..., None]
    # au sol le tissu s'accumule et s'etale
    under = np.clip(0.04 - P[..., 2], 0, None)
    P[..., 2] = np.maximum(P[..., 2], 0.03 + 0.03 * np.abs(np.sin(u * 60 + vv * 9)))
    P[..., 0] += -under * 0.4
    P[..., 1] += -under * 0.25
    return P


# attaches des rubans en suspension : sequences d'indices de blocs
def ribbon_anchors():
    blocks = block_layout()
    S = np.array([b["S"] for b in blocks])
    rng = np.random.RandomState(SEED + 44)
    used = set()
    seqs = []
    # rubans ordonnes d'ouest en est pour correspondre aux bandes de l'auvent
    centers = np.linspace(-14, 14, K_STRIPS)
    for k in range(K_STRIPS):
        target = np.array([centers[k], 33.0 + rng.uniform(-8, 8), 10.0])
        d = np.linalg.norm((S - target) * np.array([1, 0.7, 0.6]), axis=1)
        for j in used:
            d[j] += 3.0
        a = int(np.argmin(d))
        used.add(a)
        d2 = np.linalg.norm(S - S[a], axis=1)
        d2 = np.abs(d2 - 10.0)
        d2[a] = 1e9
        cand = np.argsort(d2)[:4]
        b_ = int(cand[rng.randint(0, 3)])
        seq = [a, b_]
        if rng.uniform() < 0.5:
            d3 = np.linalg.norm(S - S[b_], axis=1)
            d3[a] = d3[b_] = 1e9
            seq.append(int(np.argmin(d3)))
        seqs.append(seq)
    return seqs


_RIB = None


def _rib_static():
    global _RIB
    if _RIB is None:
        rng = np.random.RandomState(SEED + 55)
        _RIB = dict(anchors=ribbon_anchors(),
                    tail0=rng.uniform(1.2, 3.0, K_STRIPS), tail1=rng.uniform(1.2, 3.5, K_STRIPS),
                    width=rng.uniform(2.0, 3.0, K_STRIPS), twist=rng.uniform(-1.2, 1.2, K_STRIPS),
                    t0=np.linspace(10.55, 11.35, K_STRIPS) + rng.uniform(0, 0.15, K_STRIPS),
                    phase=rng.uniform(0, 6.28, K_STRIPS))
    return _RIB


def _resample(poly, n):
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, L[-1], n)
    return np.stack([np.interp(s, L, poly[:, i]) for i in range(3)], axis=-1), L[-1]


def _ribbon_curve(k, tau, block_states):
    st = _rib_static()
    seq = st["anchors"][k]
    pts = []
    sag_k = 0.22 + 0.25 * math.exp(-3.0 * max(tau - T_CUT, 0))   # le tissu traine en montant
    tops = []
    for j in seq:
        R, P = block_states[j]
        b = block_layout()[j]
        c = b["cell"]
        L = 0.4 * min(c["x1"] - c["x0"], c["y1"] - c["y0"])
        tops.append((R, P, L))
    # tangente moyenne
    first_dir = tops[1][1] - tops[0][1]
    first_dir /= np.linalg.norm(first_dir) + 1e-9
    last_dir = tops[-1][1] - tops[-2][1]
    last_dir /= np.linalg.norm(last_dir) + 1e-9
    # queue de depart qui pend
    R0, P0, L0 = tops[0]
    a0 = P0 - first_dir * L0 + R0 @ np.array([0, 0, 0.04])
    tail = [a0 - first_dir * 0.6 + np.array([0, 0, -0.5]),
            a0 - first_dir * 0.9 + np.array([0, 0, -st["tail0"][k] * 0.5]),
            a0 - first_dir * 1.0 + np.array([0, 0, -st["tail0"][k]])]
    pts.extend(tail[::-1])
    for i, (R, P, L) in enumerate(tops):
        dir_in = (P - tops[i - 1][1]) if i > 0 else first_dir
        dir_in = dir_in / (np.linalg.norm(dir_in) + 1e-9)
        dir_in_h = dir_in.copy()
        dir_in_h[2] = 0
        dir_in_h /= np.linalg.norm(dir_in_h) + 1e-9
        top = P + R @ np.array([0, 0, 0.05])
        if i > 0:
            # chainette depuis le bloc precedent
            Pa = pts[-1]
            Pb = top - dir_in_h * L
            span = np.linalg.norm(Pb - Pa)
            for s in np.linspace(0.08, 0.92, 9):
                q = Pa + (Pb - Pa) * s
                q[2] -= sag_k * span * 4 * s * (1 - s) * 0.55
                pts.append(q)
        pts.append(top - dir_in_h * L)
        pts.append(top + dir_in_h * L)
    Rl, Pl, Ll = tops[-1]
    e = pts[-1]
    pts += [e + last_dir * 0.7 + np.array([0, 0, -0.6]),
            e + last_dir * 1.0 + np.array([0, 0, -st["tail1"][k] * 0.5]),
            e + last_dir * 1.1 + np.array([0, 0, -st["tail1"][k]])]
    poly = np.array(pts)
    curve, length = _resample(poly, NU)
    return curve


def ribbons_state(t, block_states):
    """positions de toutes les bandes (K, NU, NV, 3)"""
    st = _rib_static()
    tau = object_time(t)
    out = np.zeros((K_STRIPS, NU, NV, 3))
    uu = np.linspace(0, 1, NU)
    vv = np.linspace(0, 1, NV)
    up = np.array([0, 0, 1.0])
    for k in range(K_STRIPS):
        cur = _ribbon_curve(k, tau, block_states)
        T = np.gradient(cur, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
        Bn = np.cross(T, up)
        bl = np.linalg.norm(Bn, axis=1, keepdims=True)
        Bn = np.where(bl > 0.2, Bn / (bl + 1e-9), np.array([1.0, 0, 0]))
        # lissage du binormal
        for _ in range(6):
            Bn[1:-1] = (Bn[:-2] + Bn[1:-1] * 2 + Bn[2:]) / 4
            Bn /= np.linalg.norm(Bn, axis=1, keepdims=True) + 1e-9
        Nn = np.cross(Bn, T)
        tw = st["twist"][k] * np.sin(uu * math.pi * 2 + st["phase"][k])
        ripple = 0.25 * math.exp(-2.5 * max(tau - T_CUT, 0)) * np.sin(uu * 30 - tau * 9)
        tw = tw + ripple
        cb, sb = np.cos(tw)[:, None], np.sin(tw)[:, None]
        Bt = Bn * cb + Nn * sb
        Nt = -Bn * sb + Nn * cb
        w = st["width"][k]
        off = (vv - 0.5) * w
        fold = 0.07 * np.sin((vv[None, :] - 0.5) * 14 + uu[:, None] * 25 + k)
        S = cur[:, None, :] + Bt[:, None, :] * off[None, :, None] + Nt[:, None, :] * fold[..., None]
        # morphose vers l'auvent
        t0 = st["t0"][k]
        if t > t0:
            # tant que toutes les bandes ne sont pas posees, elles se chevauchent (pas de jour entre elles)
            g_all = float(smoother(0, 1, (t - st["t0"].max() - 0.55) / 1.75))
            ov = 0.3 * (1.0 - g_all)
            Ug, Vg = np.meshgrid(uu, np.clip((k + vv * (1 + 2 * ov) - ov) / K_STRIPS, 0, 1), indexing="ij")
            F = canopy_final(Ug, Vg)
            w_ = smoother(0, 1, (t - t0 - 0.55 * Ug) / 1.75)
            arc = np.sin(math.pi * w_) * (2.5 + 2.0 * np.sin(Ug * 3.0 + k))
            flutter = np.sin(math.pi * w_) * 0.5 * np.sin(Ug * 18 - (t - t0) * 9 + Vg * 4)
            P = S * (1 - w_[..., None]) + F * w_[..., None]
            P[..., 2] += arc + flutter
            out[k] = P
        else:
            out[k] = S
    # respiration finale tres legere
    if t > 13.0:
        a = 0.06 * float(smoothstep(13.0, 14.5, t)) * (1.0 - 0.4 * float(smoothstep(14.5, 18.0, t)))
        Ug = np.linspace(0, 1, NU)[None, :, None]
        out[..., 2] += a * np.sin(t * 1.6 + Ug * 6.0) * np.sin(Ug * math.pi)
    return out


def _veil_frame(cam):
    fwd = cam["target"] - cam["pos"]
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    return fwd, right, upv


VEIL_T0 = 5.55
VEIL_T1 = 6.45


def veil_state(t, cam_fn):
    """bande de satin arrachee a la levre : tombe sur l'objectif (raccord a 6.0 s),
    puis continue sa chute dans le plan suivant en decouvrant l'image par le haut."""
    if t < VEIL_T0 or t > VEIL_T1:
        return None
    nu, nv = 48, 28
    a = np.linspace(-1, 1, nu)[:, None]
    b = np.linspace(-1, 1, nv)[None, :]
    if t < T_CUT:
        cam_end = cam_fn(T_CUT - 1e-3)
        fwd, right, upv = _veil_frame(cam_end)
        lens = cam_end["pos"] + fwd * 0.24
        P_lip, _ = _sheet_points(np.array([24.0]), np.array([R0 + 0.3]), VEIL_T0)
        start = P_lip[0] + np.array([0, 0, -2.0])
        u = (t - VEIL_T0) / (T_CUT - VEIL_T0)
        e = u ** 2.2
        center = start * (1 - e) + lens * e
        center = center + np.array([0, 0, 2.5]) * math.sin(math.pi * u) * (1 - u)
        size = 1.0
        flap = 0.6 * (1 - e)
        P = (center[None, None, :] + right[None, None, :] * (a * 3.2 * size)[..., None]
             + upv[None, None, :] * (b * 1.8 * size)[..., None]
             + fwd[None, None, :] * (flap * np.sin(a * 4 + b * 2.5 + u * 9) + 0.25 * b * b)[..., None])
        # en s'approchant, la bande s'oriente face a l'objectif ; loin, elle pend
        hang = (center[None, None, :] + np.array([1.0, 0, 0])[None, None, :] * (a * 3.2)[..., None]
                + np.array([0, 0, 1.0])[None, None, :] * (b * 3.0)[..., None]
                + np.array([0, -1.0, 0])[None, None, :] * (0.5 * np.sin(a * 3 + u * 7) * b)[..., None])
        k = float(smoothstep(0.35, 0.85, u))
        return hang * (1 - k) + P * k
    cam = cam_fn(t)
    fwd, right, upv = _veil_frame(cam)
    u = (t - T_CUT) / (VEIL_T1 - T_CUT)
    e = u ** 1.5
    center = cam["pos"] + fwd * (0.24 + 0.9 * e) - upv * (7.5 * e) + right * (0.6 * e)
    P = (center[None, None, :] + right[None, None, :] * (a * 3.2)[..., None]
         + upv[None, None, :] * (b * 1.8)[..., None]
         + fwd[None, None, :] * (0.25 * b * b + 0.3 * e * np.sin(a * 4 + b * 2.5 + u * 9))[..., None])
    return P
