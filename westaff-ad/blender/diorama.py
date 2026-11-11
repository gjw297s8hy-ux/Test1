"""
Diorama isométrique PHOTORÉALISTE (Blender / Cycles) — parking souterrain en coupe, DA rouge & noir.
Coordonnées Blender (Z vers le haut). Conversion depuis la version three.js : (x, y, z)_three → (x, -z, y)_blender.
"""
import bpy, math
from mathutils import Vector

HALF = 4.5

def T(x, y, z):  # three.js -> Blender
    return (x, -z, y)

def reset(fps=30, frames=450, res=(1080, 1920), samples=48):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 3; sc.cycles.transmission_bounces = 2
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    sc.view_settings.view_transform = 'AgX'
    try: sc.view_settings.look = 'AgX - Punchy'
    except Exception: pass
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 94
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.012, 0.011, 0.013, 1); bg.inputs[1].default_value = 1.0
    return sc

def node_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; p = nt.nodes['Principled BSDF']
    return m, nt, p

def mat_concrete(name='Concrete', red_band=True):
    m, nt, p = node_mat(name); N = nt.nodes; L = nt.links
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); L.new(tc.outputs['Object'], mp.inputs['Vector'])
    n1 = N.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 3.0; n1.inputs['Detail'].default_value = 12; n1.inputs['Roughness'].default_value = 0.6
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 60; n2.inputs['Detail'].default_value = 8
    L.new(mp.outputs['Vector'], n1.inputs['Vector']); L.new(mp.outputs['Vector'], n2.inputs['Vector'])
    # planches de coffrage : rayures horizontales (sur Z)
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(mp.outputs['Vector'], sep.inputs['Vector'])
    planks = N.new('ShaderNodeMath'); planks.operation = 'FRACT'
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 1 / 0.6
    L.new(sep.outputs['Z'], mul.inputs[0]); L.new(mul.outputs[0], planks.inputs[0])
    seam = N.new('ShaderNodeMath'); seam.operation = 'LESS_THAN'; seam.inputs[1].default_value = 0.025; L.new(planks.outputs[0], seam.inputs[0])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.105, 1); ramp.color_ramp.elements[1].color = (0.32, 0.31, 0.31, 1)
    L.new(n1.outputs['Fac'], ramp.inputs['Fac'])
    darken = N.new('ShaderNodeMixRGB'); darken.blend_type = 'MULTIPLY'; darken.inputs['Color2'].default_value = (0.35, 0.35, 0.35, 1)
    L.new(seam.outputs[0], darken.inputs['Fac']); L.new(ramp.outputs['Color'], darken.inputs['Color1'])
    col = darken
    if red_band:
        band = N.new('ShaderNodeMath'); band.operation = 'COMPARE'; band.inputs[1].default_value = 1.15; band.inputs[2].default_value = 0.14
        L.new(sep.outputs['Z'], band.inputs[0])
        chip = N.new('ShaderNodeMath'); chip.operation = 'GREATER_THAN'; chip.inputs[1].default_value = 0.45; L.new(n2.outputs['Fac'], chip.inputs[0])
        both = N.new('ShaderNodeMath'); both.operation = 'MULTIPLY'; L.new(band.outputs[0], both.inputs[0]); L.new(chip.outputs[0], both.inputs[1])
        mixr = N.new('ShaderNodeMixRGB'); mixr.inputs['Color2'].default_value = (0.32, 0.01, 0.015, 1)
        L.new(both.outputs[0], mixr.inputs['Fac']); L.new(darken.outputs[0], mixr.inputs['Color1']); col = mixr
    L.new(col.outputs[0], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.88
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value = 0.02
    hmix = N.new('ShaderNodeMath'); hmix.operation = 'SUBTRACT'; L.new(n2.outputs['Fac'], hmix.inputs[0]); L.new(seam.outputs[0], hmix.inputs[1])
    L.new(hmix.outputs[0], bump.inputs['Height']); L.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m

def mat_asphalt(name='Asphalt'):
    m, nt, p = node_mat(name); N = nt.nodes; L = nt.links
    tc = N.new('ShaderNodeTexCoord')
    grain = N.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 140; grain.inputs['Detail'].default_value = 6
    big = N.new('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 1.2; big.inputs['Detail'].default_value = 6
    pud = N.new('ShaderNodeTexNoise'); pud.inputs['Scale'].default_value = 0.55; pud.inputs['Detail'].default_value = 4
    for n in (grain, big, pud): L.new(tc.outputs['Object'], n.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.010, 0.009, 0.010, 1); ramp.color_ramp.elements[1].color = (0.045, 0.043, 0.045, 1)
    L.new(big.outputs['Fac'], ramp.inputs['Fac'])
    spec = N.new('ShaderNodeMixRGB'); spec.blend_type = 'ADD'; spec.inputs['Fac'].default_value = 0.08
    L.new(ramp.outputs['Color'], spec.inputs['Color1']); L.new(grain.outputs['Color'], spec.inputs['Color2'])
    L.new(spec.outputs[0], p.inputs['Base Color'])
    pr = N.new('ShaderNodeValToRGB'); pr.color_ramp.elements[0].position = 0.52; pr.color_ramp.elements[1].position = 0.6
    pr.color_ramp.elements[0].color = (0.85, 0.85, 0.85, 1); pr.color_ramp.elements[1].color = (0.04, 0.04, 0.04, 1)
    L.new(pud.outputs['Fac'], pr.inputs['Fac']); L.new(pr.outputs['Color'], p.inputs['Roughness'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.01
    L.new(grain.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m

def mat_simple(name, color, metal=0.0, rough=0.5, coat=0.0, emit=None, emit_strength=0.0):
    m, nt, p = node_mat(name)
    p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Metallic'].default_value = metal; p.inputs['Roughness'].default_value = rough
    try: p.inputs['Coat Weight'].default_value = coat
    except Exception: pass
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = emit_strength
    return m

def box(name, size, loc, mat, bevel=0.015, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 2; b.limit_method = 'ANGLE'
    o.data.materials.append(mat)
    if parent: o.parent = parent
    return o

def plane(name, size, loc, rot, mat, parent=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    if parent: o.parent = parent
    return o

def build_diorama():
    W = HALF * 2
    conc = mat_concrete('Concrete', True); slabm = mat_concrete('Slab', False); asph = mat_asphalt()
    paint = mat_simple('Paint', (0.75, 0.74, 0.7), rough=0.6)
    red_paint = mat_simple('RedPaint', (0.42, 0.01, 0.02), rough=0.55)
    neon = mat_simple('Neon', (0.0, 0.0, 0.0), emit=(1.0, 0.03, 0.04), emit_strength=40)
    # dalle + sol
    box('slab', (W + 0.6, W + 0.6, 0.9), T(0, -0.45, 0), slabm, bevel=0.03)
    plane('floor', (W + 0.55, W + 0.55), T(0, 0.003, 0), (0, 0, 0), asph)
    # murs + poteaux
    box('wallL', (0.4, W + 0.6, 6.2), T(-HALF - 0.2, 3.1, 0), conc, bevel=0.02)
    box('wallB', (W + 0.6, 0.4, 6.2), T(0, 3.1, -HALF - 0.2), conc, bevel=0.02)
    for i, (x, z) in enumerate([(-HALF + 0.2, -HALF + 0.2), (-HALF + 0.2, 0.6), (0.6, -HALF + 0.2)]):
        box(f'pillar{i}', (0.7, 0.7, 6.2), T(x, 3.1, z), conc, bevel=0.03)
    # butées
    for i, x in enumerate([-2.6, -0.6, 1.4]):
        box(f'stop{i}', (1.1, 0.25, 0.18), T(x, 0.09, -HALF + 0.9), slabm, bevel=0.03)
    # marquages au sol (places de parking + zone hachurée)
    for i in range(5):
        x = -HALF + 1.2 + i * 1.7
        plane(f'line{i}', (0.09, 3.4), T(x, 0.006, -HALF + 1.9), (0, 0, 0), paint)
    # néons (vrais émetteurs : éclairent le béton)
    for i, (sx, sy, loc) in enumerate([((0.05, W - 0.4), None, T(-HALF + 0.03, 5.6, 0)), ((W - 0.4, 0.05), None, T(0, 5.6, -HALF + 0.03))]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=W - 0.6, location=loc,
            rotation=(math.radians(90), 0, 0) if i == 0 else (0, math.radians(90), 0))
        o = bpy.context.active_object; o.name = f'neon{i}'; o.data.materials.append(neon)
    return dict(conc=conc, asph=asph, neon=neon, paint=paint)

def iso_camera(target=(0, 2.3, 0), zoom=110, az=math.pi / 4, el=math.asin(1 / math.sqrt(3)), dist=40):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new('Cam'); cam_data.type = 'ORTHO'; cam_data.ortho_scale = 1920 / zoom
    cam_data.clip_start = 0.1; cam_data.clip_end = 200; cam_data.sensor_fit = 'AUTO'
    cam = bpy.data.objects.new('Cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
    tgt = bpy.data.objects.new('CamTarget', None); sc.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    def place(target, zoom, az, roll=0.0):
        tx, ty, tz = target
        px = tx + dist * math.cos(el) * math.sin(az); py = ty + dist * math.sin(el); pz = tz + dist * math.cos(el) * math.cos(az)
        cam.location = T(px, py, pz); tgt.location = T(tx, ty, tz); cam_data.ortho_scale = 1920 / zoom
    place(target, zoom, az)
    return cam, tgt, cam_data, place
