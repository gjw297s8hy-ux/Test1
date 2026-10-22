"""
Teaser NPNG — STUDIO D'ENREGISTREMENT photoréaliste (Blender / Cycles).

Plan 1 (A) : studio isométrique (murs acoustiques rayés rouge/noir, LED bleues, parquet, console, écrans, enceintes, racks).
             La caméra s'approche de l'ordinateur et PLONGE dans l'écran (lecteur « now playing »).
Plans 2-4 (B, C, D) : « dans l'écran » — plateau noir brillant, caméra de cinéma (perspective, profondeur de champ),
             changements de plan et mouvements sur le tempo : NO PAIN / NO GAIN, pochette qui s'écrase, clip + photos.
Plan 5 (E) : on ressort de l'écran, retour au studio isométrique, carton final en 3D au sol.

Usage :
  python3 blender/studio_scene.py build
  python3 blender/studio_scene.py still 3.4 out.jpg
  python3 blender/studio_scene.py render START END      (→ public/npng_pr/f####.jpg)
"""
import sys, os, math
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diorama as D
import npng_scene as P
from npng_scene import (ROOT, FPS, N, beat, SH, clamp, prog, mix, outCubic, inCubic, inOutCubic, outExpo, inOutExpo, outBack, rng,
                        word, screen_stand, image_mat, drop_fn, slam, near, shake, IMPACTS)

H = 4.5          # demi-taille de la pièce
WALL_H = 4.2
AZ = math.radians(45)
EL = math.asin(1 / math.sqrt(3))
S = (200.0, 0.0, 0.0)  # origine du plateau « dans l'écran »
DESK = (-1.45, 1.45, 0.0)
SHOTS = {}
def show(o, *r): SHOTS.setdefault(o, []).extend(r)
def E(name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(o); o.location = loc; o.rotation_euler = rot
    if parent: o.parent = parent
    return o
def face(name, loc, yaw=AZ, parent=None):
    """Groupe dont le repère local a y = haut et z = vers la caméra isométrique (lacet 45°)."""
    return E(name, loc, (math.radians(90), 0, yaw), parent)
def lsx(sx): return S[0] + sx  # utilitaire plateau

# ---------- matériaux ----------
def m_wood():
    m, nt, p = D.node_mat('Parquet'); N_ = nt.nodes; L = nt.links
    tc = N_.new('ShaderNodeTexCoord'); mp = N_.new('ShaderNodeMapping'); L.new(tc.outputs['Object'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1.0, 7.0, 1.0)
    br = N_.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 1.3; br.inputs['Mortar Size'].default_value = 0.004
    br.inputs['Color1'].default_value = (0.42, 0.24, 0.12, 1); br.inputs['Color2'].default_value = (0.5, 0.31, 0.16, 1); br.inputs['Mortar'].default_value = (0.12, 0.07, 0.04, 1)
    br.offset = 0.37; L.new(mp.outputs['Vector'], br.inputs['Vector'])
    gr = N_.new('ShaderNodeTexWave'); gr.inputs['Scale'].default_value = 9; gr.inputs['Distortion'].default_value = 6; gr.inputs['Detail'].default_value = 4
    gr.bands_direction = 'Y'; L.new(tc.outputs['Object'], gr.inputs['Vector'])
    mixc = N_.new('ShaderNodeMixRGB'); mixc.blend_type = 'MULTIPLY'; mixc.inputs['Fac'].default_value = 0.35
    L.new(br.outputs['Color'], mixc.inputs['Color1']); L.new(gr.outputs['Color'], mixc.inputs['Color2']); L.new(mixc.outputs[0], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.32
    try: p.inputs['Coat Weight'].default_value = 0.6; p.inputs['Coat Roughness'].default_value = 0.12
    except Exception: pass
    bump = N_.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.15; L.new(br.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m

def m_felt(name, color):
    m, nt, p = D.node_mat(name); N_ = nt.nodes; L = nt.links
    n = N_.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 220; n.inputs['Detail'].default_value = 4
    ramp = N_.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (*[c * 0.7 for c in color], 1); ramp.color_ramp.elements[1].color = (*color, 1)
    L.new(n.outputs['Fac'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.95
    try: p.inputs['Sheen Weight'].default_value = 0.6
    except Exception: pass
    bump = N_.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.2; L.new(n.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m

def m_glossy_floor():
    m, nt, p = D.node_mat('StageFloor'); N_ = nt.nodes; L = nt.links
    p.inputs['Base Color'].default_value = (0.004, 0.004, 0.005, 1); p.inputs['Metallic'].default_value = 0.2
    n = N_.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 0.6; n.inputs['Detail'].default_value = 6
    ramp = N_.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1); ramp.color_ramp.elements[1].color = (0.22, 0.22, 0.22, 1)
    L.new(n.outputs['Fac'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], p.inputs['Roughness'])
    return m

# ---------- studio ----------
def build_studio(M):
    W = H * 2
    wood, red, black = m_wood(), m_felt('RedFelt', (0.62, 0.018, 0.03)), m_felt('BlackFoam', (0.012, 0.011, 0.012))
    objs = []
    objs.append(D.box('st_slab', (W + 0.6, W + 0.6, 0.5), (0, 0, -0.25), bpy.data.materials['Slab'], bevel=0.03))
    objs.append(D.plane('st_floor', (W + 0.5, W + 0.5), (0, 0, 0.004), (0, 0, 0), wood))
    # murs acoustiques : bandes horizontales rouges (feutre) / noires (mousse en relief)
    for wi, (axis, pos) in enumerate([('x', -H - 0.15), ('y', H + 0.15)]):
        objs.append(D.box(f'st_wallcore{wi}', (0.3, W + 0.6, WALL_H) if axis == 'x' else (W + 0.6, 0.3, WALL_H),
                          (pos, 0, WALL_H / 2) if axis == 'x' else (0, pos, WALL_H / 2), black, bevel=0.0))
        z, i = 0.0, 0
        while z < WALL_H - 0.05:
            h = 0.32 if z < 0.3 else 0.13 + (i % 3) * 0.03
            is_black = (i % 2 == 0)
            d = 0.16 if is_black else 0.05
            if axis == 'x': size, loc = (d, W + 0.4, h), (pos + 0.15 + d / 2, 0.1, z + h / 2)
            else: size, loc = (W + 0.4, d, h), (-0.1, pos - 0.15 - d / 2, z + h / 2)
            objs.append(D.box(f'st_band{wi}_{i}', size, loc, black if is_black else red, bevel=0.012))
            z += h; i += 1
        # bande LED bleue (corniche) + liseré rouge
        led = D.mat_simple('LedBlue', (0, 0, 0), emit=(0.1, 0.25, 1.0), emit_strength=35)
        if axis == 'x': objs.append(D.box(f'st_led{wi}', (0.05, W + 0.3, 0.05), (pos + 0.4, 0, WALL_H + 0.02), led, bevel=0))
        else: objs.append(D.box(f'st_led{wi}', (W + 0.3, 0.05, 0.05), (0, pos - 0.4, WALL_H + 0.02), led, bevel=0))
    # TV murale (fond)
    tv = image_mat('TV', os.path.join(ROOT, 'blender/tex/tv.png'), 3.0)
    tvg = E('st_tv', (1.9, H - 0.05, 2.75), (math.radians(90), 0, 0))
    objs += [tvg, D.box('st_tvframe', (2.3, 1.35, 0.08), (0, 0, -0.05), M['blackGloss'], bevel=0.02, parent=tvg)]
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.0)); pl = bpy.context.active_object; pl.scale = (2.2, 1.24, 1); bpy.ops.object.transform_apply(scale=True)
    pl.data.materials.append(tv); pl.parent = tvg; objs.append(pl)
    # bureau en diagonale dans l'angle, face caméra
    dg = face('st_desk', DESK); objs.append(dg)
    leather = D.mat_simple('Leather', (0.012, 0.011, 0.012), rough=0.45, coat=0.4)
    objs.append(D.box('desk_top', (4.6, 0.09, 1.25), (0, 0.95, 0), M['blackGloss'], bevel=0.03, parent=dg))
    objs.append(D.box('desk_arm', (4.6, 0.11, 0.22), (0, 0.97, 0.66), leather, bevel=0.05, parent=dg))
    rackm = [image_mat(f'Rack{i}', os.path.join(ROOT, f'blender/tex/rack{i}.png'), 0.9) for i in range(6)]
    for k, x in enumerate((-1.75, 1.75)):
        objs.append(D.box(f'desk_bay{k}', (0.9, 0.9, 1.05), (x, 0.45, -0.05), M['blackGloss'], bevel=0.02, parent=dg))
        for j in range(3):
            bpy.ops.mesh.primitive_plane_add(size=1, location=(x, 0.18 + j * 0.26, 0.48)); r_ = bpy.context.active_object
            r_.scale = (0.8, 0.2, 1); bpy.ops.object.transform_apply(scale=True); r_.data.materials.append(rackm[(k * 3 + j) % 6]); r_.parent = dg; objs.append(r_)
    # contrôleurs tactiles sur le bureau
    touch = image_mat('Touch', os.path.join(ROOT, 'blender/tex/touch.png'), 1.1)
    for i in range(4):
        x = -1.35 + i * 0.9
        t_ = E(f'touch{i}', (x, 1.04, 0.25), (math.radians(-25), 0, 0), dg); objs.append(t_)
        objs.append(D.box(f'touchbody{i}', (0.8, 0.06, 0.48), (0, 0, 0), M['blackGloss'], bevel=0.015, parent=t_))
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.032, 0), rotation=(math.radians(-90), 0, 0)); tp = bpy.context.active_object
        tp.scale = (0.72, 0.4, 1); bpy.ops.object.transform_apply(scale=True); tp.data.materials.append(touch); tp.parent = t_; objs.append(tp)
    objs.append(D.box('keyboard', (1.1, 0.03, 0.3), (0, 1.02, 0.42), D.mat_simple('KeyAlu', (0.6, 0.6, 0.62), metal=0.9, rough=0.3), bevel=0.01, parent=dg))
    # écrans latéraux (DAW) + écran principal portrait (celui dans lequel on plonge)
    daw = image_mat('DAW', os.path.join(ROOT, 'blender/tex/daw.png'), 1.15)
    for k, (x, yaw) in enumerate(((-1.45, 0.32), (1.45, -0.32))):
        g = E(f'sidemon{k}', (x, 1.65, -0.38), (0, yaw, 0), dg); objs.append(g)
        _, parts = screen_stand(f'sidemonS{k}', g, 1.45, 16 / 9, daw, 0.0, M); objs += parts
    mon = image_mat('Monitor', os.path.join(ROOT, 'out/npng_seq/monitor/f0001.jpg'), 1.25, sequence=True)
    mg = E('mainmon', (0, 1.0, -0.42), (0, 0, 0), dg); objs.append(mg)
    _, parts = screen_stand('mainmonS', mg, 0.98, 9 / 16, mon, 1.0, M); objs += parts
    # enceintes de monitoring sur pieds
    wood_dark = D.mat_simple('SpeakerWood', (0.12, 0.03, 0.025), rough=0.4, coat=0.5)
    cone = D.mat_simple('Cone', (0.02, 0.02, 0.022), rough=0.6)
    for k, x in enumerate((-2.75, 2.75)):
        sg = E(f'spk{k}', (x, 1.0, -0.2), (0, -0.35 if x > 0 else 0.35, 0), dg); objs.append(sg)
        objs.append(D.box(f'spkbox{k}', (0.62, 0.9, 0.55), (0, 0.45, 0), wood_dark, bevel=0.04, parent=sg))
        for j, (yy, rr) in enumerate(((0.3, 0.2), (0.68, 0.08))):
            bpy.ops.mesh.primitive_cylinder_add(radius=rr, depth=0.06, location=(0, yy, 0.28), rotation=(0, 0, 0)); c_ = bpy.context.active_object
            c_.data.materials.append(cone); c_.parent = sg; objs.append(c_)
        objs.append(D.box(f'spkstand{k}', (0.12, 1.0, 0.12), (x, -0.5 + 0.95 * 0, -0.2), M['steel'], bevel=0.01, parent=dg)) if False else None
    # racks latéraux contre les murs
    for k, (x, y, yaw) in enumerate(((-H + 0.55, -1.6, math.radians(90)), (1.9 + 1.4, H - 0.6, math.radians(0)))):
        g = E(f'siderack{k}', (x, y, 0), (math.radians(90), 0, yaw - math.radians(90) if k == 0 else 0)); objs.append(g)
        objs.append(D.box(f'siderackbox{k}', (1.8, 0.95, 0.8), (0, 0.475, 0), M['blackGloss'], bevel=0.02, parent=g))
        for j in range(3):
            bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.2 + j * 0.26, -0.405), rotation=(0, math.pi, 0)); r_ = bpy.context.active_object
            r_.scale = (1.6, 0.22, 1); bpy.ops.object.transform_apply(scale=True); r_.data.materials.append(rackm[(j + 2 * k) % 6]); r_.parent = g; objs.append(r_)
    # fauteuil
    ch = face('chair', (0.55, -0.6, 0)); objs.append(ch)
    objs.append(D.box('chair_seat', (0.6, 0.1, 0.6), (0, 0.55, 0), leather, bevel=0.05, parent=ch))
    objs.append(D.box('chair_back', (0.58, 0.75, 0.1), (0, 0.98, -0.28), leather, bevel=0.05, parent=ch))
    objs.append(D.box('chair_post', (0.06, 0.5, 0.06), (0, 0.27, 0), M['steel'], bevel=0.01, parent=ch))
    objs.append(D.box('chair_base', (0.6, 0.04, 0.6), (0, 0.03, 0), M['steel'], bevel=0.01, parent=ch))
    # éclairage studio : spots chauds au plafond, appoint bleu, contre rouge
    lights = []
    for i, (x, y) in enumerate(((-1.0, 1.0), (1.5, -1.0), (-2.6, -1.8), (1.6, 2.6))):
        l = bpy.data.lights.new(f'down{i}', 'SPOT'); l.energy = 950; l.spot_size = math.radians(75); l.spot_blend = 0.7; l.color = (1.0, 0.86, 0.7); l.shadow_soft_size = 0.25
        o = bpy.data.objects.new(f'down{i}', l); bpy.context.scene.collection.objects.link(o); o.location = (x, y, WALL_H + 0.3); lights.append(o)
    # lèche-murs chauds pour révéler les rayures rouges
    for i, (loc, rot) in enumerate((((-1.2, -0.5, WALL_H - 0.2), (math.radians(62), 0, math.radians(90))), ((0.5, 1.2, WALL_H - 0.2), (math.radians(62), 0, math.radians(180))))):
        l = bpy.data.lights.new(f'wash{i}', 'AREA'); l.energy = 650; l.shape = 'RECTANGLE'; l.size = 7; l.size_y = 0.6; l.color = (1.0, 0.72, 0.5)
        o = bpy.data.objects.new(f'wash{i}', l); bpy.context.scene.collection.objects.link(o); o.location = loc; o.rotation_euler = rot; o.visible_camera = False; lights.append(o)
    b = bpy.data.lights.new('blueFill', 'AREA'); b.energy = 420; b.size = 5; b.color = (0.2, 0.35, 1.0)
    bo = bpy.data.objects.new('blueFill', b); bpy.context.scene.collection.objects.link(bo); bo.location = (-2, 2, WALL_H + 0.2); lights.append(bo)
    r = bpy.data.lights.new('redBounce', 'AREA'); r.energy = 300; r.size = 4; r.color = (1.0, 0.08, 0.08)
    ro = bpy.data.objects.new('redBounce', r); bpy.context.scene.collection.objects.link(ro); ro.location = (3, -3, 3); ro.rotation_euler = (math.radians(55), 0, math.radians(45)); lights.append(ro)
    return [o for o in objs if o] + lights, mg

# ---------- plateau « dans l'écran » ----------
def build_stage(M):
    floor = m_glossy_floor()
    objs = [D.plane('stage_floor', (90, 90), (S[0], 30, 0), (0, 0, 0), floor)]
    # cyclo : quart de cylindre derrière
    bpy.ops.mesh.primitive_cylinder_add(radius=14, depth=90, vertices=64, end_fill_type='NOTHING', location=(S[0], 34, 14), rotation=(0, math.radians(90), 0))
    cy = bpy.context.active_object; cy.name = 'stage_cyc'; cy.data.materials.append(D.mat_simple('Cyc', (0.006, 0.006, 0.007), rough=0.6)); objs.append(cy)
    lights = []
    for i, (x, y, z, e, c) in enumerate(((-6, 4, 5, 1600, (1, 0.05, 0.06)), (6, 4, 5, 1600, (1, 0.05, 0.06)), (0, -7, 9, 900, (0.95, 0.96, 1.0)), (0, 10, 3, 1200, (1, 0.08, 0.1)))):
        l = bpy.data.lights.new(f'stageL{i}', 'AREA'); l.energy = e; l.size = 4; l.color = c
        o = bpy.data.objects.new(f'stageL{i}', l); bpy.context.scene.collection.objects.link(o); o.location = (S[0] + x, y, z)
        tc = o.constraints.new('TRACK_TO'); tc.target = E(f'stageT{i}', (S[0], 2, 1.2)); tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
        o.visible_camera = False; lights.append(o)
    recv = bpy.data.collections.new('stageNoFloor'); recv.objects.link(objs[0])
    for co in recv.collection_objects: co.light_linking.link_state = 'EXCLUDE'
    for o in (lights[0], lights[1], lights[3]): o.light_linking.receiver_collection = recv
    neon = D.mat_simple('NeonRed', (0.05, 0.0, 0.0), emit=(1.0, 0.0, 0.015), emit_strength=1.3)
    gN = E('stage_neon', (S[0], 9.0, 0), (math.radians(90), 0, 0))
    _, ln = word('stage_neonW', P.TITLE, 2.0, 0.06, neon, gN, pos=(0, 8.5, 0), tracking=0.06)
    return objs + lights + [gN, *ln]

# ---------- caméras ----------
def iso_cam():
    cd = bpy.data.cameras.new('IsoCam'); cd.type = 'ORTHO'; cd.clip_start = 0.1; cd.clip_end = 300
    cam = bpy.data.objects.new('IsoCam', cd); bpy.context.scene.collection.objects.link(cam)
    tgt = E('IsoTarget'); c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam, cd, tgt
def persp_cam():
    cd = bpy.data.cameras.new('CineCam'); cd.type = 'PERSP'; cd.lens = 32; cd.clip_start = 0.05; cd.clip_end = 300
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.2
    cam = bpy.data.objects.new('CineCam', cd); bpy.context.scene.collection.objects.link(cam)
    tgt = E('CineTarget'); c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    cd.dof.focus_object = tgt
    return cam, cd, tgt

MON = None  # position monde du centre de l'écran principal (calculée après construction)
def iso_state(t):
    """Studio isométrique : approche puis plongée dans l'écran (A), sortie de l'écran (E)."""
    wide_t, wide_z = (-0.4, 0.4, 1.7), 1920 / 102
    mon_t, mon_z = tuple(MON), 1.25          # cadre ≈ écran plein cadre
    if t < SH['A'][1]:
        e = inOutCubic(prog(t, 0.0, 1.75)); dive = inOutExpo(prog(t, 1.55, SH['A'][1]))
        tz = mix(wide_z, 1920 / 125, e); tt = tuple(mix(wide_t[i], mix(wide_t[i], MON[i], 0.55), e) for i in range(3))
        return tuple(mix(tt[i], mon_t[i], dive) for i in range(3)), mix(tz, mon_z, dive), AZ - 0.25 + 0.25 * outCubic(prog(t, 0, 1.6))
    e = inOutExpo(prog(t, SH['E'][0], SH['E'][0] + 1.0)); s = outCubic(prog(t, SH['E'][0] + 0.8, 15))
    end_t = (0.6, -0.4, 1.4)
    return tuple(mix(mon_t[i], end_t[i], e) for i in range(3)), mix(mon_z, 1920 / 108, e) * (1 - s * 0.06), AZ + 0.12 * (1 - e)

def cine_state(t):
    """Plateau : (position caméra, cible) en coordonnées plateau, avec raccords rapides sur les temps forts."""
    shots = [
        (SH['B'][0], ((0, -6.2, 0.9), (0, 0, 1.35))), (SH['B'][0] + 1.9, ((1.2, -8.8, 1.9), (0, 0, 1.4))),
        (SH['C'][0], ((3.0, -5.0, 6.0), (0, 0, 0.3))), (SH['C'][0] + 0.75, ((2.4, -6.6, 4.6), (0, 0, 0.9))), (SH['C'][1] - 0.02, ((-1.2, -9.6, 2.6), (0, 0, 2.6))),
        (SH['D'][0], ((0, -12.5, 3.3), (0, 3, 2.9))), (beat(14), ((0, -4.6, 3.3), (0, 3, 3.3))),
        (beat(16.6), ((12.6, -1.8, 2.0), (12, 6, 2.0))), (beat(19), ((2.5, -14, 6.0), (1.5, 3, 2.6))), (SH['D'][1], ((2.0, -15.5, 6.5), (1.5, 3, 2.6))),
    ]
    i = len(shots) - 2
    while i > 0 and t < shots[i][0]: i -= 1
    t0, a = shots[i]; t1, b = shots[i + 1]
    # mouvement lent dans le plan, raccord rapide (0,25 s) au plan suivant
    hard = t1 in (SH['C'][0], SH['D'][0], beat(14), beat(16.6), beat(19))
    k = inOutExpo(prog(t, t1 - 0.25, t1 + 0.0)) if hard else inOutCubic(prog(t, t0, t1))
    if hard:
        drift = prog(t, t0, t1 - 0.25)
        a = (tuple(a[0][j] + (b[0][j] - a[0][j]) * 0 for j in range(3)), a[1])
        pa = tuple(a[0][j] * (1 - drift * 0.06) for j in range(3))
        return tuple(mix(pa[j], b[0][j], k) for j in range(3)), tuple(mix(a[1][j], b[1][j], k) for j in range(3))
    return tuple(mix(a[0][j], b[0][j], k) for j in range(3)), tuple(mix(a[1][j], b[1][j], k) for j in range(3))

# ---------- construction ----------
def build():
    global MON
    sc = D.reset(samples=14)
    sc.render.use_persistent_data = True
    sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
    M = P.mats()
    D.mat_concrete('Slab', False)
    studio, mg = build_studio(M)
    stage = build_stage(M)
    bpy.context.view_layer.update()
    MON = tuple(mg.matrix_world.translation + mg.matrix_world.to_3x3() @ __import__('mathutils').Vector((0, 1.0, 0)))
    A, B, C, Dd, Ee = SH['A'], SH['B'], SH['C'], SH['D'], SH['E']
    for o in studio: show(o, (A[0], A[1]), (Ee[0], 15.01))
    for o in studio:
        if o.name.startswith('chair'): SHOTS[o] = [(A[0], A[1])]  # le fauteuil gênerait le carton final
    for o in stage: show(o, (B[0], Dd[1]))
    anim = []
    seq = lambda n: os.path.join(ROOT, f'out/npng_seq/{n}/f0001.jpg')
    rose_dim = image_mat('RoseDim', seq('rose'), 0.6, sequence=True)
    clip_m = image_mat('ClipScreen', seq('clip'), 1.3, sequence=True)
    cover_m = image_mat('Cover', os.path.join(ROOT, 'public/npng/cover.jpg'), 1.9)
    ph = {k: image_mat(f'Photo_{k}', os.path.join(ROOT, f'public/npng/photo_{k}.jpg'), 1.6) for k in ('studio', 'duo', 'profile')}
    front = lambda name, loc, yaw=0.0: E(name, loc, (math.radians(90), 0, yaw))  # face caméra plateau (-Y)

    # B — NO PAIN / NO GAIN
    gB = front('B_title', (S[0], 0, 0))
    w1, l1 = word('B_l1', 'NO PAIN', 1.25, 0.5, M['redChrome'], gB, pos=(0, 1.75, -0.6))
    w2, l2 = word('B_l2', 'NO GAIN', 1.25, 0.5, M['redChrome'], gB, pos=(0, 0, 0.3))
    anim += [(w1, lambda t: slam(t, B[0], (0, 1.75, -0.6))), (w2, lambda t: slam(t, beat(5), (0, 0, 0.3)))]
    gBs = front('B_screen', (S[0], 3.5, 0)); sB, pB = screen_stand('B_stand', gBs, 4.8, 4 / 3, rose_dim, 3.0, M)
    for o in [gB, w1, w2, *l1, *l2, gBs, sB, *pB]: show(o, B)
    # C — pochette
    gC = front('C_cover', (S[0], 0, 0)); tilt = E('C_tilt', (0, 0, 0), (0, 0, 0), gC)
    slab = D.box('C_slab', (4.0, 0.3, 4.0), (0, 0, 0), M['blackGloss'], bevel=0.04, parent=tilt)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.152, 0), rotation=(math.radians(-90), 0, 0)); cpl = bpy.context.active_object
    cpl.scale = (3.8, 3.8, 1); bpy.ops.object.transform_apply(scale=True); cpl.data.materials.append(cover_m); cpl.parent = tilt
    land = C[0] + 0.28
    def c_tilt(t):
        fall = inCubic(prog(t, C[0], land)); stand = inOutCubic(prog(t, beat(9.5), C[1] - 0.05))
        bounce = math.exp(-(t - land) * 7) * abs(math.sin((t - land) * 22)) * 0.3 if t > land else 0
        return dict(loc=(0, mix(mix(12, 0.17, fall) + bounce, 2.2, stand), 0), rot=(mix(0, math.pi / 2 - 0.12, stand), 0, 0))
    anim.append((tilt, c_tilt))
    _, lk = word('C_kick', 'NOUVEAU SON', 0.72, 0.35, M['white'], gC, pos=(0, 4.6, -1.0))
    for i, l in enumerate(lk): anim.append((l, drop_fn(l.location.x, beat(9) + i * 0.04, 0.35)))
    for o in [gC, tilt, slab, cpl, *lk]: show(o, C)
    # D — clip + photos + portrait + titre gothique
    gD = front('D_screen', (S[0], 3, 0)); sD, pD = screen_stand('D_stand', gD, 6.0, 4 / 3, clip_m, 2.9, M)
    tg = E('D_title', (0, 2.9, 0.7), (0, 0, 0), gD)
    _, g1 = word('D_np', 'No Pain', 0.9, 0.22, M['glowWhite'], tg, pos=(0, 0.35, 0), fontfile='blender/UnifrakturMaguntia.ttf')
    _, g2 = word('D_ng', 'No Gain', 0.9, 0.22, M['glowWhite'], tg, pos=(0, -1.0, 0), fontfile='blender/UnifrakturMaguntia.ttf')
    anim.append((tg, lambda t: dict(scale=(lambda k: (max(0.001, mix(1.8, 1, k)) if k > 0.001 else 0.001,) * 3)(outExpo(prog(t, 7.55, 7.75)) * (1 - inCubic(prog(t, 8.5, 8.7)))))))
    side = []
    for i, (x, yaw, key) in enumerate(((-4.6, 0.35, 'studio'), (4.6, -0.35, 'duo'))):
        g = front(f'D_side{i}', (S[0] + x, 2.0, 0), yaw); s_, p_ = screen_stand(f'D_sideS{i}', g, 2.1, 3 / 4, ph[key], 1.9, M); side += [g, s_, *p_]
    gN = front('D_name', (S[0], -1.6, 0)); _, ld = word('D_oneal', P.ARTIST, 0.95, 0.4, M['redChrome'], gN, tracking=0.05)
    for i, l in enumerate(ld): anim.append((l, drop_fn(l.location.x, Dd[0] + 0.1 + i * 0.06)))
    gP = front('D_portrait', (S[0] + 12, 6, 0)); sP, pP = screen_stand('D_portraitS', gP, 2.9, 3 / 4, ph['profile'], 2.3, M)
    _, lp = word('D_pname', P.ARTIST, 0.85, 0.35, M['white'], gP, pos=(0, 0, 1.6), tracking=0.05)
    for i, l in enumerate(lp): anim.append((l, drop_fn(l.location.x, beat(16.6) + 0.1 + i * 0.06, 0.35)))
    for o in [gD, sD, *pD, tg, *g1, *g2, *side, gN, *ld, gP, sP, *pP, *lp]: show(o, Dd)
    # E — carton final dans le studio (textes 3D posés au sol devant le bureau)
    redDeep = D.mat_simple('RedDeep', (0.5, 0.004, 0.01), metal=0.5, rough=0.18, coat=1.0, emit=(1.0, 0.0, 0.02), emit_strength=0.25)
    gE = face('E_titles', (1.0, -1.0, 0), AZ - 0.3); gE2 = face('E_titles2', (1.0, -1.0, 0))
    satin = D.mat_simple('SatinBlack', (0.014, 0.013, 0.014), rough=0.42, coat=0.25)
    _, lt = word('E_npng', P.TITLE, 3.1, 1.0, redDeep, gE, pos=(0, 0, -1.2), tracking=0.03)
    _, ln = word('E_oneal', P.ARTIST, 1.0, 0.45, satin, gE2, pos=(0, 0, 0.9), tracking=0.06)
    _, lc = word('E_cta', P.CTA, 0.6, 0.4, satin, gE2, pos=(0, 0, 1.95), tracking=0.04, fontfile='public/fonts/Inter-ExtraBold.otf')
    for i, l in enumerate(lt): anim.append((l, drop_fn(l.location.x, Ee[0] + 0.9 + i * 0.08, 0.45)))
    for i, l in enumerate(ln): anim.append((l, drop_fn(l.location.x, Ee[0] + 1.2 + i * 0.05)))
    for i, l in enumerate(lc): anim.append((l, drop_fn(l.location.x, Ee[0] + 1.5 + i * 0.025, 0.3)))
    for o in [gE, gE2, *lt, *ln, *lc]: show(o, (Ee[0], 15.01))
    # pétales (plateau B, studio E)
    petals(M, anim, (S[0], 0, 0), B[0] - 1.5, (B[0], B[1]), 3, 34)
    petals(M, anim, (0, 0, 0), Ee[0] + 0.5, (Ee[0], 15.01), 5, 30)

    # caméras + marqueurs de bascule
    icam, icd, itgt = iso_cam(); ccam, ccd, ctgt = persp_cam()
    for f, cam in ((1, icam), (int(B[0] * FPS) + 1, ccam), (int(Ee[0] * FPS) + 1, icam)):
        mk = sc.timeline_markers.new(f'cam{f}', frame=f); mk.camera = cam
    sc.camera = icam
    for f in range(1, N + 1):
        t = (f - 1) / FPS
        tt, osc, az = iso_state(t)
        shk = shake(t, Ee[0] + 0.9, 0.05)
        itgt.location = (tt[0] + math.sin(t * 70) * shk, tt[1], tt[2] + math.cos(t * 63) * shk)
        icam.location = (itgt.location[0] + 40 * math.cos(EL) * math.sin(az), itgt.location[1] - 40 * math.cos(EL) * math.cos(az), itgt.location[2] + 40 * math.sin(EL))
        icd.ortho_scale = osc
        icam.keyframe_insert('location', frame=f); itgt.keyframe_insert('location', frame=f); icd.keyframe_insert('ortho_scale', frame=f)
        if B[0] - 0.1 <= t < Dd[1] + 0.1:
            pos, tg_ = cine_state(t)
            punch = near(t, IMPACTS(), 0.09); shk2 = shake(t, B[0], 0.06) + shake(t, beat(5), 0.05) + shake(t, C[0] + 0.28, 0.14)
            ccam.location = (S[0] + pos[0] + math.sin(t * 70) * shk2, pos[1] * (1 - punch * 0.08), pos[2] + math.cos(t * 63) * shk2)
            ctgt.location = (S[0] + tg_[0], tg_[1], tg_[2])
            ccam.keyframe_insert('location', frame=f); ctgt.keyframe_insert('location', frame=f)
        for ob, fn in anim:
            r = SHOTS.get(ob) or SHOTS.get(ob.parent) or [(0, 15.1)]
            if not any(a - 0.07 <= t < b + 0.07 for a, b in r): continue
            d = fn(t)
            if 'loc' in d: ob.location = d['loc']; ob.keyframe_insert('location', frame=f)
            if 'rot' in d: ob.rotation_euler = d['rot']; ob.keyframe_insert('rotation_euler', frame=f)
            if 'scale' in d: ob.scale = d['scale']; ob.keyframe_insert('scale', frame=f)
    for ob, ranges in SHOTS.items():
        last = None
        for f in range(1, N + 1):
            t = (f - 1) / FPS; vis = any(a <= t < b for a, b in ranges)
            if vis != last:
                ob.hide_render = not vis; ob.keyframe_insert('hide_render', frame=f); last = vis
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'out/npng_studio.blend'))
    print('BUILD_OK', MON)

def petals(M, anim, origin, t0, rng_, seed, count):
    import bmesh
    me = bpy.data.meshes.new('petal'); bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=0.16)
    for v in bm.verts:
        x, y = v.co.x, v.co.y; v.co.z = (x * x) * 6 - abs(y) * 0.4; v.co.x = x * (1 - max(0, y) * 2.5)
    bm.to_mesh(me); bm.free()
    r = rng(seed)
    for i in range(count):
        ob = bpy.data.objects.new(f'petal{seed}_{i}', me.copy()); bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(M['petalRed'] if r() < 0.6 else M['petalBlack'])
        p = dict(x=(r() - 0.5) * 7, y=(r() - 0.5) * 7, z0=6 + r() * 5, v=0.7 + r() * 0.8, ph=r() * 6.3, sp=1 + r() * 3, sw=0.3 + r() * 0.6)
        def fn(t, p=p):
            s = max(0, t - t0); z = p['z0'] - p['v'] * s * 1.6
            rot = (s * p['sp'] + p['ph'], math.sin(s * 2 + p['ph']) * 0.8, s * p['sp'] * 0.6) if z > 0.03 else (0, 0, p['ph'])
            return dict(loc=(origin[0] + p['x'] + math.sin(s * 1.4 + p['ph']) * p['sw'], origin[1] + p['y'] + math.cos(s * 1.1 + p['ph']) * p['sw'], max(0.03, z)), rot=rot)
        anim.append((ob, fn)); show(ob, rng_)

def still(t, path):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'out/npng_studio.blend'))
    sc = bpy.context.scene; sc.frame_set(int(round(t * FPS)) + 1); sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

def stills(pct, ts, outdir):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'out/npng_studio.blend'))
    sc = bpy.context.scene; sc.render.resolution_percentage = pct
    os.makedirs(outdir, exist_ok=True)
    for t in ts:
        sc.frame_set(int(round(t * FPS)) + 1); sc.render.filepath = os.path.join(outdir, f's_{t:05.2f}.jpg')
        bpy.ops.render.render(write_still=True)

def render(a, b):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'out/npng_studio.blend'))
    sc = bpy.context.scene; sc.frame_start, sc.frame_end = a, b
    sc.render.filepath = os.path.join(ROOT, 'public/npng_pr/f'); sc.render.use_overwrite = False; sc.render.use_placeholder = True
    bpy.ops.render.render(animation=True)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'build': build()
    elif cmd == 'still': still(float(sys.argv[2]), sys.argv[3])
    elif cmd == 'stills': stills(int(sys.argv[2]), [float(x) for x in sys.argv[3].split(',')], sys.argv[4])
    elif cmd == 'render': render(int(sys.argv[2]), int(sys.argv[3]))
