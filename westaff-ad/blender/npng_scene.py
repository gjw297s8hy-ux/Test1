"""
Teaser NPNG — version PHOTORÉALISTE (Blender / Cycles).
Même découpage, même timing et même caméra isométrique que la version temps réel (src/release/*),
mais rendu en lancer de rayons : vraie lumière des néons, ombres douces, reflets, matières PBR.

Usage :
  python3 blender/npng_scene.py build            → construit et sauvegarde out/npng_photoreal.blend
  python3 blender/npng_scene.py still 3.4 out.jpg → image de contrôle à t = 3,4 s
  python3 blender/npng_scene.py render START END → rend les frames [START, END] dans out/npng_pr/
"""
import sys, os, math
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diorama as D
from diorama import T

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FPS, N = 30, 450
BEAT, B0 = 0.508, 0.396
beat = lambda k: B0 + BEAT * k
SH = dict(A=(0, beat(4)), B=(beat(4), beat(8)), C=(beat(8), beat(11)), D=(beat(11), beat(22)), E=(beat(22), 15.0))
FACE = math.pi / 4
EL = math.asin(1 / math.sqrt(3))
PORTRAIT = (8.2, 0, -8.2)
ARTIST, TITLE, KICKER, CTA = "O'NEAL", 'NPNG', 'NOUVEAU SON', 'DISPONIBLE MAINTENANT'

# ---------- easing (identiques à src/lib/anim.ts) ----------
clamp = lambda x, a=0.0, b=1.0: min(b, max(a, x))
prog = lambda t, a, b: clamp((t - a) / (b - a))
mix = lambda a, b, k: a + (b - a) * k
outCubic = lambda x: 1 - (1 - x) ** 3
inCubic = lambda x: x ** 3
inOutCubic = lambda x: 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
outExpo = lambda x: 1.0 if x == 1 else 1 - 2 ** (-10 * x)
def inOutExpo(x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 2 ** (20 * x - 10) / 2 if x < 0.5 else (2 - 2 ** (-20 * x + 10)) / 2
def outBack(x, c1=1.4):
    c3 = c1 + 1; return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def rng(seed):
    s = [seed]
    def r():
        s[0] = (s[0] * 16807) % 2147483647; return s[0] / 2147483647
    return r

# ---------- matériaux ----------
def mats():
    M = {}
    M['redChrome'] = D.mat_simple('RedChrome', (0.62, 0.012, 0.02), metal=0.55, rough=0.2, coat=1.0, emit=(1.0, 0.02, 0.03), emit_strength=0.9)
    M['white'] = D.mat_simple('WhiteChrome', (0.92, 0.91, 0.89), metal=0.35, rough=0.22, coat=1.0, emit=(1, 1, 1), emit_strength=0.55)
    M['glowWhite'] = D.mat_simple('GlowWhite', (1, 1, 1), rough=0.3, emit=(1, 1, 1), emit_strength=6)
    M['blackGloss'] = D.mat_simple('BlackGloss', (0.01, 0.01, 0.012), metal=0.4, rough=0.12, coat=1.0)
    M['steel'] = D.mat_simple('Steel', (0.25, 0.25, 0.27), metal=1.0, rough=0.32)
    M['neonText'] = D.mat_simple('NeonText', (0, 0, 0), emit=(1.0, 0.04, 0.05), emit_strength=55)
    M['petalRed'] = D.mat_simple('PetalRed', (0.24, 0.005, 0.015), rough=0.55)
    M['petalBlack'] = D.mat_simple('PetalBlack', (0.012, 0.01, 0.011), rough=0.5)
    for k in ('petalRed', 'petalBlack'):
        p = M[k].node_tree.nodes['Principled BSDF']
        try: p.inputs['Sheen Weight'].default_value = 1.0; p.inputs['Sheen Tint'].default_value = (1, 0.2, 0.25, 1)
        except Exception: pass
    return M

def image_mat(name, path, strength=1.2, sequence=False, emissive=True):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N_ = nt.nodes; L = nt.links
    for n in list(N_): N_.remove(n)
    out = N_.new('ShaderNodeOutputMaterial'); tex = N_.new('ShaderNodeTexImage')
    img = bpy.data.images.load(path)
    if sequence:
        img.source = 'SEQUENCE'
        tex.image_user.frame_duration = N; tex.image_user.frame_start = 1; tex.image_user.frame_offset = 0; tex.image_user.use_auto_refresh = True
    tex.image = img
    if emissive:
        em = N_.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
        L.new(tex.outputs['Color'], em.inputs['Color']); L.new(em.outputs[0], out.inputs['Surface'])
    else:
        p = N_.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.5
        p.inputs['Emission Strength'].default_value = strength
        L.new(tex.outputs['Color'], p.inputs['Base Color']); L.new(tex.outputs['Color'], p.inputs['Emission Color']); L.new(p.outputs[0], out.inputs['Surface'])
    return m

# ---------- outils ----------
SHOTS = {}  # objet -> liste d'intervalles visibles (s)
def show(obj, *ranges):
    SHOTS.setdefault(obj, []).extend(ranges)
def empty(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot
    if parent: o.parent = parent
    return o
def facing_group(name, three_pos, parent=None, extra_rot=0.0):
    """Groupe orienté face caméra (équivalent rotation-y FACE dans three.js)."""
    return empty(name, T(*three_pos), (math.radians(90), 0, FACE + extra_rot), parent)

FONTS = {}
def font(path):
    if path not in FONTS: FONTS[path] = bpy.data.fonts.load(path)
    return FONTS[path]

def word(name, text, size, depth, mat, parent, pos=(0, 0, 0), tracking=0.0, fontfile='public/fonts/InterDisplay-Black.otf'):
    """Texte 3D lettre par lettre (posé sur la ligne de base), dans le repère local du groupe face caméra."""
    g = empty(name, pos, (0, 0, 0), parent)
    letters = []
    for i, ch in enumerate(text):
        if ch == ' ': letters.append(None); continue
        cu = bpy.data.curves.new(f'{name}_{i}', 'FONT'); cu.body = ch; cu.font = font(os.path.join(ROOT, fontfile))
        cu.size = size; cu.extrude = depth / 2; cu.bevel_depth = size * 0.018; cu.bevel_resolution = 3
        cu.align_x = 'CENTER'; cu.align_y = 'BOTTOM_BASELINE'
        ob = bpy.data.objects.new(f'{name}_{i}', cu); bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(mat); ob.parent = g
        letters.append(ob)
    bpy.context.view_layer.update()
    widths = [(l.dimensions.x if l else size * 0.3) for l in letters]
    total = sum(widths) + tracking * size * (len(widths) - 1) - 0.01 * size * (len(widths) - 1)
    x = -total / 2
    out = []
    for l, w in zip(letters, widths):
        if l: l.location = (x + w / 2, 0, 0); out.append(l)
        x += w + tracking * size - 0.01 * size
    return g, out

def screen_stand(name, parent, w, aspect, mat, y, m, pos=(0, 0, 0)):
    """Écran sur pied : cadre laqué biseauté, dalle émissive, montants + pieds acier."""
    g = empty(name, pos, (0, 0, 0), parent)
    h = w / aspect
    fr = D.box(f'{name}_frame', (w + 0.22, h + 0.22, 0.22), (0, y, -0.12), m['blackGloss'], bevel=0.05, parent=g)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, y, 0.005)); pl = bpy.context.active_object
    pl.name = f'{name}_panel'; pl.scale = (w, h, 1); bpy.ops.object.transform_apply(scale=True)
    pl.data.materials.append(mat); pl.parent = g
    bottom = y - h / 2 - 0.11
    parts = [fr, pl]
    for i, x in enumerate((-w * 0.3, w * 0.3)):
        parts.append(D.box(f'{name}_leg{i}', (0.08, max(0.01, bottom), 0.08), (x, bottom / 2, -0.12), m['steel'], bevel=0.01, parent=g))
        parts.append(D.box(f'{name}_foot{i}', (0.12, 0.05, 1.1), (x, 0.025, -0.12), m['steel'], bevel=0.01, parent=g))
    # la géométrie a été créée dans le repère du groupe (y = haut, z = vers la caméra) : rien d'autre à faire
    return g, parts

def fix_local(objs):
    """Les primitives Blender sont créées en coordonnées monde ; on les ré-exprime dans le repère du parent."""
    for o in objs:
        if o.parent:
            loc = o.location.copy(); o.matrix_parent_inverse.identity(); o.location = loc

# ---------- construction ----------
def build():
    sc = D.reset(samples=14)
    sc.render.use_persistent_data = True
    sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
    m = mats(); dm = D.build_diorama()
    # éclairage : soleil froid doux, softbox (reflets lisibles sur le chrome), contre-jour rouge
    sun = bpy.data.lights.new('Sun', 'SUN'); sun.energy = 1.4; sun.angle = math.radians(8); sun.color = (0.9, 0.93, 1.0)
    so = bpy.data.objects.new('Sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(42), math.radians(-18), math.radians(38))
    soft = bpy.data.lights.new('Softbox', 'AREA'); soft.energy = 700; soft.size = 6; soft.color = (0.95, 0.96, 1.0)
    sb = bpy.data.objects.new('Softbox', soft); sc.collection.objects.link(sb); sb.location = T(6, 7, 7); sb.rotation_euler = (math.radians(55), 0, math.radians(140))
    red = bpy.data.lights.new('KeyRed', 'AREA'); red.energy = 650; red.color = (1, 0.06, 0.07); red.size = 3
    ro = bpy.data.objects.new('KeyRed', red); sc.collection.objects.link(ro); ro.location = T(5, 8, 5); ro.rotation_euler = (math.radians(50), 0, math.radians(135))

    seq = lambda n: os.path.join(ROOT, f'out/npng_seq/{n}/f0001.jpg')
    rose_m = image_mat('RoseScreen', seq('rose'), 1.3, sequence=True)
    rose_dim = image_mat('RoseScreenDim', seq('rose'), 0.55, sequence=True)
    clip_m = image_mat('ClipScreen', seq('clip'), 1.3, sequence=True)
    cover_m = image_mat('Cover', os.path.join(ROOT, 'public/npng/cover.jpg'), 1.1)
    ph = {k: image_mat(f'Photo_{k}', os.path.join(ROOT, f'public/npng/photo_{k}.jpg'), 1.6) for k in ('studio', 'duo', 'profile')}
    A, B, C, Dd, E = SH['A'], SH['B'], SH['C'], SH['D'], SH['E']
    anim = []  # (objet, fonction(t) -> dict(loc=, rot=, scale=))

    # enseigne néon NPNG au mur (plans D et E)
    neon_g = empty('NeonSign', T(2.65, 4.0, -D.HALF + 0.05), (math.radians(90), 0, 0))
    ng, nl = word('neonNPNG', TITLE, 0.72, 0.06, m['neonText'], neon_g, tracking=0.08)
    for o in [neon_g, *nl]: show(o, (Dd[0], 15.01))

    # A — écran rose + O'NEAL au sol
    gA = facing_group('A_screen', (-1.2, 0, -1.2))
    sA, partsA = screen_stand('A_stand', gA, 4.8, 4 / 3, rose_m, 3.0, m)
    anim.append((sA, lambda t: dict(scale=(1, max(0.001, outBack(prog(t, 0.05, 0.55))), 1))))
    gA2 = facing_group('A_name', (1.0, 0, 1.0))
    _, lettersA = word('A_oneal', ARTIST, 1.3, 0.45, m['white'], gA2, tracking=0.04)
    for o in [gA, sA, *partsA, gA2, *lettersA]: show(o, A)
    for i, l in enumerate(lettersA): anim.append((l, drop_fn(l.location.x, beat(1) + i * 0.085)))

    # B — NO PAIN / NO GAIN monumental
    gB = facing_group('B_screen', (-1.6, 0, -1.6))
    sB, partsB = screen_stand('B_stand', gB, 4.8, 4 / 3, rose_dim, 3.4, m)
    gB2 = facing_group('B_title', (0.7, 0, 0.7))
    w1, l1 = word('B_l1', 'NO PAIN', 1.25, 0.5, m['redChrome'], gB2, pos=(0, 1.75, -0.6))
    w2, l2 = word('B_l2', 'NO GAIN', 1.25, 0.5, m['redChrome'], gB2, pos=(0, 0, 0.3))
    for o in [gB, sB, *partsB, gB2, w1, w2, *l1, *l2]: show(o, B)
    anim.append((w1, lambda t: slam(t, B[0], (0, 1.75, -0.6))))
    anim.append((w2, lambda t: slam(t, beat(5), (0, 0, 0.3))))

    # C — la pochette s'écrase puis se redresse
    gC = facing_group('C_cover', (0.4, 0, 0.4))
    tilt = empty('C_tilt', (0, 0, 0), (0, 0, 0), gC)
    slab = D.box('C_slab', (4.0, 0.3, 4.0), (0, 0, 0), m['blackGloss'], bevel=0.04, parent=tilt)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.152, 0), rotation=(math.radians(-90), 0, 0)); cpl = bpy.context.active_object
    cpl.scale = (3.8, 3.8, 1); bpy.ops.object.transform_apply(scale=True); cpl.data.materials.append(cover_m); cpl.parent = tilt
    land = C[0] + 0.28
    def c_tilt(t):
        fall = inCubic(prog(t, C[0], land)); stand = inOutCubic(prog(t, beat(9.5), C[1] - 0.05))
        bounce = math.exp(-(t - land) * 7) * abs(math.sin((t - land) * 22)) * 0.3 if t > land else 0
        return dict(loc=(0, mix(mix(12, 0.17, fall) + bounce, 2.35, stand), 0), rot=(mix(0, math.pi / 2 - 0.15, stand), 0, 0))
    anim.append((tilt, c_tilt))
    gC2 = facing_group('C_kicker', (0.4, 0, 0.4))
    _, lk = word('C_kick', KICKER, 0.72, 0.35, m['white'], gC2, pos=(0, 4.8, -0.6))
    for i, l in enumerate(lk): anim.append((l, drop_fn(l.location.x, beat(9) + i * 0.04, 0.35)))
    for o in [gC, tilt, slab, cpl, gC2, *lk]: show(o, C)

    # D — écran clip, photos, O'NEAL, îlot portrait
    gD = facing_group('D_screen', (-1.4, 0, -1.4))
    sD, partsD = screen_stand('D_stand', gD, 6.0, 4 / 3, clip_m, 3.5, m)
    tg = empty('D_title', (0, 3.5, 0.6), (0, 0, 0), gD)
    _, g1 = word('D_np', 'No Pain', 0.9, 0.22, m['glowWhite'], tg, pos=(0, 0.35, 0), fontfile='blender/UnifrakturMaguntia.ttf')
    _, g2 = word('D_ng', 'No Gain', 0.9, 0.22, m['glowWhite'], tg, pos=(0, -1.0, 0), fontfile='blender/UnifrakturMaguntia.ttf')
    def title_k(t):
        return outExpo(prog(t, 7.55, 7.75)) * (1 - inCubic(prog(t, 8.5, 8.7)))
    anim.append((tg, lambda t: dict(scale=(lambda k: (max(0.001, mix(1.8, 1, k) * (1 if k > 0.001 else 0.001)),) * 3)(title_k(t)))))
    side = []
    for i, (x, z, key) in enumerate([(-3.2, 1.7, 'studio'), (1.7, -3.2, 'duo')]):
        gs = facing_group(f'D_side{i}', (x, 0, z), extra_rot=(0.15 if i == 0 else -0.15))
        s_, p_ = screen_stand(f'D_sideStand{i}', gs, 1.9, 3 / 4, ph[key], 2.0, m)
        side += [gs, s_, *p_]
    gD2 = facing_group('D_name', (1.4, 0, 1.4))
    _, ld = word('D_oneal', ARTIST, 0.95, 0.4, m['redChrome'], gD2, tracking=0.05)
    for i, l in enumerate(ld): anim.append((l, drop_fn(l.location.x, Dd[0] + 0.1 + i * 0.06)))
    isl = empty('D_island', T(*PORTRAIT))
    islab = D.box('D_islandSlab', (4.6, 4.6, 0.6), T(*PORTRAIT)[:2] + (-0.3,), bpy.data.materials['Slab'], bevel=0.03)
    ifl = D.plane('D_islandFloor', (4.6, 4.6), T(PORTRAIT[0], 0.004, PORTRAIT[2]), (0, 0, 0), bpy.data.materials['Asphalt'])
    gP = facing_group('D_portrait', PORTRAIT)
    sP, pP = screen_stand('D_portraitStand', gP, 2.9, 3 / 4, ph['profile'], 2.4, m, pos=(0, 0, -0.6))
    _, lp = word('D_pname', ARTIST, 0.85, 0.35, m['white'], gP, pos=(0, 0, 1.1), tracking=0.05)
    for i, l in enumerate(lp): anim.append((l, drop_fn(l.location.x, beat(16.6) + 0.1 + i * 0.06, 0.35)))
    for o in [gD, sD, *partsD, tg, *g1, *g2, *side, gD2, *ld, isl, islab, ifl, gP, sP, *pP, *lp]: show(o, Dd)

    # E — carton final
    gE = facing_group('E_cover', (-1.3, 0, -1.3))
    ce = empty('E_coverPivot', (0, 3.2, 0), (-0.1, 0, 0), gE)
    eb = D.box('E_coverBox', (3.6, 3.6, 0.26), (0, 0, -0.16), m['blackGloss'], bevel=0.03, parent=ce)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.0)); ep = bpy.context.active_object
    ep.scale = (3.4, 3.4, 1); bpy.ops.object.transform_apply(scale=True); ep.data.materials.append(cover_m); ep.parent = ce
    est = D.box('E_stand', (0.1, 1.4, 0.1), (0, 0.7, -0.4), m['steel'], bevel=0.01, parent=gE)
    anim.append((ce, lambda t: dict(scale=(max(0.001, outBack(prog(t, E[0], E[0] + 0.5))),) * 3)))
    gE2 = facing_group('E_titles', (1.1, 0, 1.1))
    _, lt = word('E_npng', TITLE, 1.45, 0.5, m['redChrome'], gE2, pos=(0, 0, -0.9), tracking=0.03)
    _, ln = word('E_oneal', ARTIST, 0.72, 0.35, m['white'], gE2, pos=(0, 0, 0.45), tracking=0.08)
    _, lc = word('E_cta', CTA, 0.3, 0.22, m['white'], gE2, pos=(0, 0, 1.35), tracking=0.12, fontfile='public/fonts/Inter-ExtraBold.otf')
    for i, l in enumerate(lt): anim.append((l, drop_fn(l.location.x, E[0] + 0.25 + i * 0.08, 0.45)))
    for i, l in enumerate(ln): anim.append((l, drop_fn(l.location.x, E[0] + 0.6 + i * 0.05)))
    for i, l in enumerate(lc): anim.append((l, drop_fn(l.location.x, E[0] + 1.0 + i * 0.025, 0.3)))
    for o in [gE, ce, eb, ep, est, gE2, *lt, *ln, *lc]: show(o, E)

    # pétales (rouges et noirs) — A/B et E
    petals = build_petals(m, [(0.4, A[0], B[1], 2, 30), (B[0] - 1.5, B[0], B[1], 3, 30), (E[0] - 0.8, E[0], 15.01, 5, 28)], anim)

    # ---------- keyframes ----------
    cam, tgt, cam_data, place = D.iso_camera()
    def active(ob, t, pad=0.07):
        r = SHOTS.get(ob)
        return r is None or any(a - pad <= t < b + pad for a, b in r)
    for f in range(1, N + 1):
        t = (f - 1) / FPS
        c = cam_at(t)
        punch = near(t, IMPACTS(), 0.09)
        shk = shake(t, SH['B'][0], 0.1) + shake(t, beat(5), 0.08) + shake(t, SH['C'][0] + 0.28, 0.25) + shake(t, SH['E'][0], 0.08)
        tx, ty, tz = c['target']
        place((tx + math.sin(t * 70) * shk, ty + math.cos(t * 63) * shk, tz), c['zoom'] * (1 + punch * 0.14), c['az'])
        cam.keyframe_insert('location', frame=f); tgt.keyframe_insert('location', frame=f); cam_data.keyframe_insert('ortho_scale', frame=f)
        for ob, fn in anim:
            if not active(ob, t) and not active(ob.parent, t) if ob.parent else not active(ob, t):
                continue
            d = fn(t)
            if 'loc' in d: ob.location = d['loc']; ob.keyframe_insert('location', frame=f)
            if 'rot' in d: ob.rotation_euler = d['rot']; ob.keyframe_insert('rotation_euler', frame=f)
            if 'scale' in d: ob.scale = d['scale']; ob.keyframe_insert('scale', frame=f)
    # visibilité par plan (clés constantes aux changements d'état)
    for ob, ranges in SHOTS.items():
        last = None
        for f in range(1, N + 1):
            t = (f - 1) / FPS
            vis = any(a <= t < b for a, b in ranges)
            if vis != last:
                ob.hide_render = not vis; ob.keyframe_insert('hide_render', frame=f)
                ob.hide_viewport = not vis; ob.keyframe_insert('hide_viewport', frame=f)
                last = vis
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'out/npng_photoreal.blend'))
    print('BUILD_OK')


def drop_fn(x, start, dur=0.4):
    def f(t):
        k = outBack(prog(t, start, start + dur))
        s = max(0.001, min(1.06, k))
        return dict(loc=(x, (1 - k) * 1.5, 0), rot=((1 - k) * -1.3, 0, 0), scale=(s, s, s))
    return f

def slam(t, start, base):
    k = outExpo(prog(t, start, start + 0.25))
    s = 0.001 if t < start else mix(2.4, 1, k)
    return dict(loc=(base[0], base[1], base[2] + (1 - k) * 4), scale=(s, s, s))

def IMPACTS(): return [SH['B'][0], beat(5), SH['C'][0] + 0.28, SH['E'][0]]
def near(t, lst, w): return max(math.exp(-((t - b) / w) ** 2) for b in lst)
def shake(t, at, amp): return math.exp(-(t - at) * 9) * amp if t >= at else 0

def cam_at(t):
    sway = math.sin(t * 0.6) * 0.05
    if t < SH['A'][1]:
        e = outCubic(prog(t, 0, 2.4)); return dict(target=(-0.3, 2.4, -0.3), zoom=mix(88, 118, e), az=FACE - 0.3 + e * 0.3 + sway)
    if t < SH['B'][1]: return dict(target=(0.2, 2.2, 0.2), zoom=mix(112, 124, prog(t, *SH['B'])), az=FACE + sway)
    if t < SH['C'][1]: return dict(target=(0.2, mix(1.2, 2.2, inOutCubic(prog(t, beat(9.5), SH['C'][1]))), 0.2), zoom=mix(100, 116, prog(t, *SH['C'])), az=FACE + 0.1 * math.sin(t))
    if t < SH['D'][1]:
        shots = [(SH['D'][0], ((-0.6, 2.6, -0.6), 84, FACE - 0.18)), (beat(14), ((-1.4, 3.4, -1.4), 140, FACE)),
                 (beat(16.6), ((PORTRAIT[0], 2.8, PORTRAIT[2]), 150, FACE)), (beat(19), ((1.8, 2.4, -1.8), 74, FACE + 0.2))]
        i = len(shots) - 1
        while i > 0 and t < shots[i][0]: i -= 1
        s0, a = shots[i]; nxt, b = shots[min(i + 1, len(shots) - 1)]
        k = 0 if i == len(shots) - 1 else inOutExpo(prog(t, nxt - 0.22, nxt + 0.06))
        drift = (t - s0) * 0.02
        return dict(target=tuple(mix(a[0][j], b[0][j], k) for j in range(3)), zoom=mix(a[1], b[1], k) * (1 + drift), az=mix(a[2], b[2], k) + sway * 0.5)
    e = outCubic(prog(t, SH['E'][0], SH['E'][0] + 1.2))
    return dict(target=(0, mix(2.6, 1.5, e), 0), zoom=mix(105, 128, e) + (t - SH['E'][0]) * 2, az=FACE + mix(0.3, 0, e) + sway * 0.4)

def build_petals(m, groups, anim):
    import bmesh
    me = bpy.data.meshes.new('petal'); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=0.16)
    for v in bm.verts:
        x, y = v.co.x, v.co.y
        v.co.z = (x * x) * 6 - abs(y) * 0.4; v.co.x = x * (1 - max(0, y) * 2.5)
    bm.to_mesh(me); bm.free()
    out = []
    for gi, (t0, a, b, seed, count) in enumerate(groups):
        r = rng(seed)
        for i in range(count):
            ob = bpy.data.objects.new(f'petal{gi}_{i}', me.copy()); bpy.context.scene.collection.objects.link(ob)
            ob.data.materials.append(m['petalRed'] if r() < 0.6 else m['petalBlack'])
            p = dict(x=(r() - 0.5) * 8, z=(r() - 0.5) * 8, y0=7 + r() * 6, v=0.7 + r() * 0.8, ph=r() * 6.3, sp=1 + r() * 3, sw=0.3 + r() * 0.6)
            def fn(t, p=p, t0=t0):
                s = max(0, t - t0); y = p['y0'] - p['v'] * s * 1.6
                if y > 0.03: rot = (s * p['sp'] + p['ph'], math.sin(s * 2 + p['ph']) * 0.8, s * p['sp'] * 0.6)
                else: rot = (0, 0, p['ph'])
                return dict(loc=T(p['x'] + math.sin(s * 1.4 + p['ph']) * p['sw'], max(0.03, y), p['z'] + math.cos(s * 1.1 + p['ph']) * p['sw']), rot=rot)
            anim.append((ob, fn)); show(ob, (max(a, t0), b)); out.append(ob)
    return out

def still(t, path):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'out/npng_photoreal.blend'))
    sc = bpy.context.scene; sc.frame_set(int(round(t * FPS)) + 1)
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)

def render(a, b):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'out/npng_photoreal.blend'))
    sc = bpy.context.scene; sc.frame_start, sc.frame_end = a, b
    sc.render.filepath = os.path.join(ROOT, 'public/npng_pr/f')
    sc.render.use_overwrite = False; sc.render.use_placeholder = True
    bpy.ops.render.render(animation=True)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'build': build()
    elif cmd == 'still': still(float(sys.argv[2]), sys.argv[3])
    elif cmd == 'render': render(int(sys.argv[2]), int(sys.argv[3]))
