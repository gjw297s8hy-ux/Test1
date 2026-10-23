"""RUPTURE - construction de la scene Blender et rendu.

Usage :
  blender -b -P src/build.py -- --out renders/frames --res 1080 --samples 64 --frames 0-539
  blender -b -P src/build.py -- --save rupture.blend          (scene inspectable)
Options : --res (hauteur = res*16/9), --samples, --frames "a-b" ou "a,b,c", --step n,
          --noblur, --variant NAME=VALUE (parametres de comparaison).
Toute l'animation vient de sim.py et ne depend que du numero d'image.
"""
import os
import sys
import math
import argparse

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402

FPS = sim.FPS
RNG = np.random.RandomState(sim.SEED + 1)

# --------------------------------------------------------------------- utilitaires mesh


def make_mesh(name, verts, faces=None, quads=True):
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    if faces is not None and len(faces):
        faces = np.asarray(faces, dtype=np.int32)
        n = faces.shape[1]
        me.loops.add(faces.size)
        me.loops.foreach_set("vertex_index", faces.ravel())
        me.polygons.add(len(faces))
        me.polygons.foreach_set("loop_start", np.arange(0, faces.size, n, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    return me


def grid_faces(nu, nv, offset=0):
    i, j = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1), indexing="ij")
    a = (i * nv + j).ravel() + offset
    return np.stack([a, a + nv, a + nv + 1, a + 1], axis=1)


def add_float_attr(me, name, domain="POINT", dtype="FLOAT"):
    if name not in me.attributes:
        me.attributes.new(name, dtype, domain)
    return me.attributes[name]


def set_attr(me, name, values):
    me.attributes[name].data.foreach_set("value", np.asarray(values, dtype=np.float32).ravel())


def set_vec_attr(me, name, values):
    me.attributes[name].data.foreach_set("vector", np.asarray(values, dtype=np.float32).ravel())


def set_uv(me, uv_per_vertex, name="UVMap"):
    if name not in me.uv_layers:
        me.uv_layers.new(name=name)
    loops = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", loops)
    uv = np.asarray(uv_per_vertex, dtype=np.float32)[loops]
    me.uv_layers[name].data.foreach_set("uv", uv.ravel())


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def new_obj(name, me, coll=None):
    ob = bpy.data.objects.new(name, me)
    return link(ob, coll)


def set_coords(me, P):
    me.vertices.foreach_set("co", np.asarray(P, dtype=np.float32).ravel())
    me.update()


def shade_smooth(me):
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))


# --------------------------------------------------------------------- noeuds

class NB:
    """petit assistant de construction de graphes de noeuds"""

    def __init__(self, tree):
        self.t = tree
        self.n = tree.nodes
        self.l = tree.links
        self.x = 0

    def node(self, kind, **props):
        nd = self.n.new(kind)
        nd.location = (self.x, 0)
        self.x += 40
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def math(self, op, a=None, b=None, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1], b)
        return nd.outputs[0]

    def vmath(self, op, a=None, b=None):
        nd = self.node("ShaderNodeVectorMath", operation=op)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1], b)
        return nd.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs[0]

    def _in(self, sock, v):
        if v is None:
            return
        if hasattr(v, "is_output") or isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        else:
            try:
                sock.default_value = v
            except (TypeError, ValueError):
                sock.default_value = tuple(v) + ((1.0,) if len(v) == 3 and len(sock.default_value) == 4 else ())

    def mix(self, fac, a, b, dtype="RGBA", blend="MIX"):
        nd = self.node("ShaderNodeMix", data_type=dtype, blend_type=blend)
        if dtype == "RGBA":
            ia, ib, o = nd.inputs[6], nd.inputs[7], nd.outputs[2]
        elif dtype == "FLOAT":
            ia, ib, o = nd.inputs[2], nd.inputs[3], nd.outputs[0]
        else:
            ia, ib, o = nd.inputs[4], nd.inputs[5], nd.outputs[1]
        self._in(nd.inputs[0], fac)
        self._in(ia, a)
        self._in(ib, b)
        return o

    def maprange(self, v, a0, a1, b0=0.0, b1=1.0, interp="LINEAR", clamp=True):
        nd = self.node("ShaderNodeMapRange", interpolation_type=interp, clamp=clamp)
        self._in(nd.inputs[0], v)
        nd.inputs[1].default_value = a0
        nd.inputs[2].default_value = a1
        nd.inputs[3].default_value = b0
        nd.inputs[4].default_value = b1
        return nd.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dim="3D", dist=0.0):
        nd = self.node("ShaderNodeTexNoise", noise_dimensions=dim)
        self._in(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = dist
        return nd

    def voronoi(self, vec, scale, feature="F1", rand=1.0, metric="EUCLIDEAN"):
        nd = self.node("ShaderNodeTexVoronoi", feature=feature, distance=metric)
        self._in(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Randomness"].default_value = rand
        return nd

    def rgb(self, c):
        nd = self.node("ShaderNodeRGB")
        nd.outputs[0].default_value = tuple(c) + (1.0,)
        return nd.outputs[0]

    def combine(self, x, y, z):
        nd = self.node("ShaderNodeCombineXYZ")
        self._in(nd.inputs[0], x)
        self._in(nd.inputs[1], y)
        self._in(nd.inputs[2], z)
        return nd.outputs[0]

    def sep(self, v):
        nd = self.node("ShaderNodeSeparateXYZ")
        self._in(nd.inputs[0], v)
        return nd.outputs

    def attr(self, name, kind="GEOMETRY"):
        nd = self.node("ShaderNodeAttribute", attribute_name=name, attribute_type=kind)
        return nd

    def group(self, tree):
        nd = self.node("ShaderNodeGroup")
        nd.node_tree = tree
        return nd


def new_group(name, inputs, outputs):
    g = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for nm, tp in inputs:
        g.interface.new_socket(nm, in_out="INPUT", socket_type=tp)
    for nm, tp in outputs:
        g.interface.new_socket(nm, in_out="OUTPUT", socket_type=tp)
    gi = g.nodes.new("NodeGroupInput")
    go = g.nodes.new("NodeGroupOutput")
    return g, NB(g), gi, go


# --------------------------------------------------------------------- ciel et brume

SUN = Vector(tuple(sim.SUN_DIR))


def build_sky_image():
    import sky
    w, h = 4096, 2048
    img = bpy.data.images.new("DesertSky", w, h, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709"
    img.pixels.foreach_set(sky.equirect(w, h).ravel())
    img.pack()
    return img


def env_node(b, img, vec=None):
    nd = b.node("ShaderNodeTexEnvironment")
    nd.image = img
    nd.interpolation = "Linear"
    if vec is not None:
        b.link(vec, nd.inputs[0])
    return nd


def build_haze_group(img):
    """brume atmospherique : melange vers la couleur du ciel a l'horizon (rayons camera)"""
    g, b, gi, go = new_group("Haze", [("Shader", "NodeSocketShader")], [("Shader", "NodeSocketShader")])
    lp = b.node("ShaderNodeLightPath")
    geo = b.node("ShaderNodeNewGeometry")
    d = b.vmath("SCALE", geo.outputs["Incoming"])
    d.node.inputs["Scale"].default_value = -1.0
    x, y, z = b.sep(d)
    dh = b.combine(x, y, b.math("MINIMUM", z, 0.004))
    sky = env_node(b, img, dh)
    em = b.node("ShaderNodeEmission")
    b.link(sky.outputs[0], em.inputs[0])
    fog = b.math("MULTIPLY", lp.outputs["Ray Length"], -1.0 / 1100.0)
    fog = b.math("EXPONENT", fog)
    fog = b.math("SUBTRACT", 1.0, fog)
    fog = b.math("MULTIPLY", fog, lp.outputs["Is Camera Ray"])
    mx = b.node("ShaderNodeMixShader")
    b.link(fog, mx.inputs[0])
    b.link(gi.outputs[0], mx.inputs[1])
    b.link(em.outputs[0], mx.inputs[2])
    b.link(mx.outputs[0], go.inputs[0])
    return g


def setup_world(img):
    w = bpy.data.worlds.new("Desert")
    bpy.context.scene.world = w
    w.use_nodes = True
    b = NB(w.node_tree)
    b.n.clear()
    tc = b.node("ShaderNodeTexCoord")
    env = env_node(b, img, tc.outputs["Generated"])
    bg = b.node("ShaderNodeBackground")
    b.link(env.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    out = b.node("ShaderNodeOutputWorld")
    b.link(bg.outputs[0], out.inputs[0])
    w.cycles.sampling_method = "MANUAL"
    w.cycles.sample_map_resolution = 1024


# --------------------------------------------------------------------- materiaux

def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, NB(m.node_tree)


def finish(m, b, shader, haze):
    m.cycles.emission_sampling = "NONE"   # la brume n'est pas une source de lumiere
    h = b.group(haze)
    b.link(shader, h.inputs[0])
    out = b.node("ShaderNodeOutputMaterial")
    b.link(h.outputs[0], out.inputs["Surface"])
    return m


def principled(b, **kw):
    p = b.node("ShaderNodeBsdfPrincipled")
    for k, v in kw.items():
        b._in(p.inputs[k], v)
    return p


def bump(b, height, strength, dist=1.0, normal=None):
    bp = b.node("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = dist
    b.link(height, bp.inputs["Height"])
    if normal is not None:
        b.link(normal, bp.inputs["Normal"])
    return bp.outputs[0]


def build_salt_group(with_crack=False):
    """surface de sel : couleur, rugosite, hauteur (bump) a partir d'une coordonnee en metres.
    Volontairement econome : le bump reevalue la hauteur trois fois."""
    g, b, gi, go = new_group("SaltSurface" + ("Crack" if with_crack else ""),
                             [("Coord", "NodeSocketVector"), ("Crack", "NodeSocketFloat"),
                              ("Damp", "NodeSocketFloat")],
                             [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"),
                              ("Height", "NodeSocketFloat"), ("Spec", "NodeSocketFloat")])
    co = gi.outputs[0]
    vo = b.voronoi(co, 0.55, feature="DISTANCE_TO_EDGE", rand=0.85)
    ridge = b.maprange(vo.outputs["Distance"], 0.07, 0.0, interp="SMOOTHSTEP")
    n1 = b.noise(co, 3.0, detail=2.0, rough=0.6)
    n2 = b.noise(co, 42.0, detail=1.0, rough=0.6)
    # paillettes : une cellule sur ~40 brille (bruit blanc par cellule, tres economique)
    scaled = b.vmath("SCALE", co)
    scaled.node.inputs["Scale"].default_value = 160.0
    cell = b.vmath("FLOOR", scaled)
    wn = b.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    b.link(cell, wn.inputs[0])
    glint = b.maprange(wn.outputs["Value"], 0.972, 0.985)
    h = b.math("ADD", b.math("MULTIPLY", ridge, 0.6), b.math("MULTIPLY", n1.outputs["Fac"], 0.35))
    h = b.math("ADD", h, b.math("MULTIPLY", n2.outputs["Fac"], 0.25))
    base = b.mix(n1.outputs["Fac"], (0.70, 0.665, 0.62), (0.82, 0.79, 0.745))
    base = b.mix(b.math("MULTIPLY", ridge, 0.6), base, (0.86, 0.835, 0.80))
    if with_crack:
        vc = b.voronoi(co, 1.7, feature="DISTANCE_TO_EDGE", rand=1.0)
        crack = b.maprange(vc.outputs["Distance"], 0.012, 0.0)
        crack = b.math("MULTIPLY", crack, gi.outputs[1])
        h = b.math("SUBTRACT", h, b.math("MULTIPLY", crack, 0.9))
        base = b.mix(b.math("MULTIPLY", crack, 0.85), base, (0.26, 0.22, 0.19))
    base = b.mix(gi.outputs[2], base, (0.47, 0.42, 0.37))
    rough = b.math("SUBTRACT", 0.62, b.math("MULTIPLY", glint, 0.5))
    rough = b.math("SUBTRACT", rough, b.math("MULTIPLY", gi.outputs[2], 0.25))
    b.link(base, go.inputs[0])
    b.link(rough, go.inputs[1])
    b.link(h, go.inputs[2])
    b.link(glint, go.inputs[3])
    return g


def mat_ground(salt, haze):
    m, b = new_mat("Salt_Ground")
    tc = b.node("ShaderNodeTexCoord")
    s = b.group(salt)
    b.link(tc.outputs["Object"], s.inputs[0])
    b.link(b.attr("crack").outputs["Fac"], s.inputs[1])
    b.link(b.attr("pit").outputs["Fac"], s.inputs[2])
    nrm = bump(b, s.outputs["Height"], 0.35, 0.02)
    p = principled(b, **{"Base Color": s.outputs["Color"], "Roughness": s.outputs["Rough"], "Normal": nrm,
                         "Specular IOR Level": 0.45})
    return finish(m, b, p.outputs[0], haze)


def mat_crust(salt, haze, name, damp=0.0, coord="UV"):
    m, b = new_mat(name)
    if coord == "UV":
        uv = b.node("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        co = uv.outputs[0]
    else:
        co = b.node("ShaderNodeTexCoord").outputs["Object"]
    s = b.group(salt)
    b.link(co, s.inputs[0])
    s.inputs[1].default_value = 0.0
    s.inputs[2].default_value = damp
    nrm = bump(b, s.outputs["Height"], 0.6, 0.05)
    p = principled(b, **{"Base Color": s.outputs["Color"], "Roughness": s.outputs["Rough"], "Normal": nrm})
    return finish(m, b, p.outputs[0], haze)


def satin_shader(b, uvsock, scale_weave=220.0):
    """satin : rouge carmin, reflets vermillon orientes par le tissu, leger tissage"""
    tg = b.node("ShaderNodeTangent", direction_type="UV_MAP")
    tg.uv_map = "UVMap"
    weave = b.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y")
    b.link(uvsock, weave.inputs["Vector"])
    weave.inputs["Scale"].default_value = scale_weave
    weave.inputs["Distortion"].default_value = 0.6
    weave.inputs["Detail"].default_value = 1.0
    nn = b.noise(uvsock, 1.2, detail=3.0)
    col = b.mix(nn.outputs["Fac"], (0.24, 0.006, 0.010), (0.36, 0.014, 0.016))
    nrm = bump(b, weave.outputs["Fac"], 0.06, 0.002)
    p = principled(b, **{"Base Color": col, "Roughness": 0.24, "Anisotropic": 0.72, "Tangent": tg.outputs[0],
                         "Specular IOR Level": 0.62, "Specular Tint": (1.0, 0.42, 0.30),
                         "Sheen Weight": 0.55, "Sheen Roughness": 0.35, "Sheen Tint": (1.0, 0.30, 0.22),
                         "Normal": nrm})
    tr = b.node("ShaderNodeBsdfTranslucent")
    tr.inputs[0].default_value = (0.75, 0.02, 0.02, 1)
    mx = b.node("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.14
    b.link(p.outputs[0], mx.inputs[1])
    b.link(tr.outputs[0], mx.inputs[2])
    return mx.outputs[0]


def mat_satin(haze):
    m, b = new_mat("Satin")
    uv = b.node("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    sh = satin_shader(b, uv.outputs[0])
    return finish(m, b, sh, haze)


def mat_crust_inner(salt, haze):
    """face inferieure revelee : sel humide qui s'effrite -> satin, selon l'attribut 'sat'"""
    m, b = new_mat("Crust_Inner")
    uv = b.node("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    s = b.group(salt)
    b.link(uv.outputs[0], s.inputs[0])
    s.inputs[2].default_value = 0.55
    nrm_salt = bump(b, s.outputs["Height"], 0.9, 0.08)
    salt_bsdf = principled(b, **{"Base Color": s.outputs["Color"], "Roughness": s.outputs["Rough"],
                                 "Normal": nrm_salt})
    satin = satin_shader(b, uv.outputs[0])
    sat = b.attr("sat").outputs["Fac"]
    nz = b.noise(uv.outputs[0], 0.35, detail=6.0, rough=0.7)
    v = b.math("ADD", sat, b.math("MULTIPLY", b.math("SUBTRACT", nz.outputs["Fac"], 0.5), 0.9))
    mask = b.maprange(v, 0.46, 0.54, interp="SMOOTHSTEP")
    mx = b.node("ShaderNodeMixShader")
    b.link(mask, mx.inputs[0])
    b.link(salt_bsdf.outputs[0], mx.inputs[1])
    b.link(satin, mx.inputs[2])
    return finish(m, b, mx.outputs[0], haze)


def mat_crystal(haze):
    m, b = new_mat("Salt_Crystal")
    tc = b.node("ShaderNodeTexCoord")
    nz = b.noise(tc.outputs["Object"], 6.0, detail=3.0)
    col = b.mix(nz.outputs["Fac"], (0.86, 0.84, 0.80), (0.96, 0.95, 0.92))
    p = principled(b, **{"Base Color": col, "Roughness": 0.22, "Transmission Weight": 0.2, "IOR": 1.54,
                         "Subsurface Weight": 0.0, "Coat Weight": 0.2})
    return finish(m, b, p.outputs[0], haze)


def mat_stone(salt, haze):
    """blocs : dessus croute blanche, strates, dessous cristallin sombre (attribut 'root')"""
    m, b = new_mat("Salt_Stone")
    tc = b.node("ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    s = b.group(salt)
    b.link(co, s.inputs[0])
    x, y, z = b.sep(co)
    wv = b.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    b.link(co, wv.inputs["Vector"])
    wv.inputs["Scale"].default_value = 1.4
    wv.inputs["Distortion"].default_value = 3.0
    wv.inputs["Detail"].default_value = 1.5
    strata = b.mix(wv.outputs["Fac"], (0.74, 0.70, 0.64), (0.88, 0.85, 0.80))
    top = b.maprange(z, -0.10, -0.02)
    col = b.mix(top, strata, s.outputs["Color"])
    root = b.attr("root").outputs["Fac"]
    rn = b.noise(co, 7.0, detail=1.0)
    rootcol = b.mix(rn.outputs["Fac"], (0.10, 0.085, 0.075), (0.32, 0.27, 0.23))
    col = b.mix(root, col, rootcol)
    rough = b.mix(root, s.outputs["Rough"], 0.35, dtype="FLOAT")
    nrm = bump(b, s.outputs["Height"], 0.45, 0.04)
    p = principled(b, **{"Base Color": col, "Roughness": rough, "Normal": nrm, "Metallic": 0.0})
    return finish(m, b, p.outputs[0], haze)


def mat_card(haze, edge=False):
    m, b = new_mat("Card_Edge" if edge else "Card_Metal")
    uv = b.node("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tg = b.node("ShaderNodeTangent", direction_type="UV_MAP")
    tg.uv_map = "UVMap"
    x, y, z = b.sep(uv.outputs[0])
    brushed = b.noise(b.combine(b.math("MULTIPLY", x, 2.0), b.math("MULTIPLY", y, 2400.0), 0.0), 1.0, detail=2.0)
    var = b.noise(uv.outputs[0], 40.0, detail=4.0)
    rough = b.maprange(var.outputs["Fac"], 0.3, 0.7, 0.24 if not edge else 0.12, 0.34 if not edge else 0.18)
    nrm = bump(b, brushed.outputs["Fac"], 0.08, 0.0005)
    p = principled(b, **{"Base Color": (0.075, 0.072, 0.075) if not edge else (0.16, 0.15, 0.14),
                         "Metallic": 1.0, "Roughness": rough, "Anisotropic": 0.8 if not edge else 0.3,
                         "Tangent": tg.outputs[0], "Normal": nrm})
    return finish(m, b, p.outputs[0], haze)


def mat_black(haze, name, rough=0.3, metal=0.5):
    m, b = new_mat(name)
    tc = b.node("ShaderNodeTexCoord")
    nz = b.noise(tc.outputs["Object"], 8.0, detail=5.0)
    r = b.maprange(nz.outputs["Fac"], 0.3, 0.7, rough * 0.8, rough * 1.25)
    p = principled(b, **{"Base Color": (0.018, 0.017, 0.017), "Metallic": metal, "Roughness": r})
    return finish(m, b, p.outputs[0], haze)


def mat_amber(haze):
    m, b = new_mat("Amber")
    em = b.node("ShaderNodeEmission")
    em.inputs[0].default_value = (1.0, 0.42, 0.10, 1)
    em.inputs[1].default_value = 0.0
    m["emit_node"] = em.name
    finish(m, b, em.outputs[0], haze)
    m.cycles.emission_sampling = "FRONT"
    return m


def mat_dust(haze):
    m, b = new_mat("Dust")
    p = principled(b, **{"Base Color": (0.9, 0.84, 0.75), "Roughness": 0.9,
                         "Emission Color": (1.0, 0.8, 0.6), "Emission Strength": 0.6})
    tr = b.node("ShaderNodeBsdfTranslucent")
    tr.inputs[0].default_value = (0.9, 0.8, 0.65, 1)
    mx = b.node("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.35
    b.link(p.outputs[0], mx.inputs[1])
    b.link(tr.outputs[0], mx.inputs[2])
    return finish(m, b, mx.outputs[0], haze)


# --------------------------------------------------------------------- geometrie de base

def crystal_mesh(name, rng, elong=1.0, flat=1.0):
    bm = bmesh.new()
    pts = rng.normal(0, 1, (14, 3)) * np.array([1.0, 1.0 * elong, 0.8 * flat])
    pts /= np.max(np.abs(pts))
    pts *= 0.5
    for p in pts:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def instance_collection(name, meshes, mat):
    coll = bpy.data.collections.new(name)
    for i, me in enumerate(meshes):
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"{name}_{i}", me)
        coll.objects.link(ob)
    return coll


def gn_instancer(name, coll):
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = tree.nodes
    gi = n.new("NodeGroupInput")
    go = n.new("NodeGroupOutput")
    ci = n.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = n.new("GeometryNodeInstanceOnPoints")
    pid = n.new("GeometryNodeInputNamedAttribute")
    pid.data_type = "INT"
    pid.inputs["Name"].default_value = "pid"
    rot = n.new("GeometryNodeInputNamedAttribute")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs["Name"].default_value = "rot"
    sc = n.new("GeometryNodeInputNamedAttribute")
    sc.data_type = "FLOAT"
    sc.inputs["Name"].default_value = "scale"
    e2r = n.new("FunctionNodeEulerToRotation")
    L = tree.links
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    L.new(pid.outputs["Attribute"], iop.inputs["Instance Index"])
    L.new(rot.outputs["Attribute"], e2r.inputs[0])
    L.new(e2r.outputs[0], iop.inputs["Rotation"])
    L.new(sc.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs[0], go.inputs[0])
    return tree


class PointCloud:
    def __init__(self, name, n, coll, coll_parent=None):
        self.n = n
        me = make_mesh(name, np.zeros((n, 3)))
        me.attributes.new("pid", "INT", "POINT")
        me.attributes.new("rot", "FLOAT_VECTOR", "POINT")
        me.attributes.new("scale", "FLOAT", "POINT")
        self.me = me
        self.ob = new_obj(name, me, coll_parent)
        mod = self.ob.modifiers.new("inst", "NODES")
        mod.node_group = gn_instancer(name + "_GN", coll)

    def update(self, pos, rot, scale, pid=None):
        set_coords(self.me, pos)
        self.me.attributes["rot"].data.foreach_set("vector", np.asarray(rot, np.float32).ravel())
        self.me.attributes["scale"].data.foreach_set("value", np.asarray(scale, np.float32).ravel())
        if pid is not None:
            self.me.attributes["pid"].data.foreach_set("value", np.asarray(pid, np.int32).ravel())
        self.me.update()


# --------------------------------------------------------------------- objets


def build_card(m_metal, m_edge):
    o = sim.card_outline(14)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, -sim.CARD_T / 2)) for x, y in o]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in top:
        v.co.z += sim.CARD_T
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and
             abs(e.link_faces[0].normal.dot(e.link_faces[1].normal)) < 0.5]
    bmesh.ops.bevel(bm, geom=edges, offset=0.0006, segments=3, affect="EDGES", profile=0.5)
    for fc in bm.faces:
        fc.material_index = 0 if abs(fc.normal.z) > 0.99 else 1
        fc.smooth = True
    me = bpy.data.meshes.new("Card")
    bm.to_mesh(me)
    bm.free()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    set_uv(me, np.c_[co[:, 0] / sim.CARD_W + 0.5, co[:, 1] / sim.CARD_H + 0.5])
    me.materials.append(m_metal)
    me.materials.append(m_edge)
    ob = new_obj("Card", me)
    return ob


def build_ground(m_ground):
    # grand disque lointain
    far = make_mesh("GroundFar", [(-6000, -6000, -0.03), (6000, -6000, -0.03), (6000, 6000, -0.03), (-6000, 6000, -0.03)],
                    [(0, 1, 2, 3)])
    far.materials.append(m_ground)
    add_float_attr(far, "crack")
    add_float_attr(far, "pit")
    new_obj("GroundFar", far)
    # sol deformable (onde, logement de la croute), troue au centre pour le patch macro
    res = 0.4
    xs = np.arange(-56.0, 56.0 + 1e-6, res)
    ys = np.arange(-24.0, 112.0 + 1e-6, res)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    V = np.stack([X, Y, np.zeros_like(X)], axis=-1).reshape(-1, 3)
    F = grid_faces(len(xs), len(ys))
    cx = V[F[:, 0], 0] + res / 2
    cy = V[F[:, 0], 1] + res / 2
    keep = ~((np.abs(cx) < 1.6) & (np.abs(cy) < 1.6))
    F = F[keep]
    me = make_mesh("GroundMid", V, F)
    add_float_attr(me, "crack")
    add_float_attr(me, "pit")
    me.materials.append(m_ground)
    shade_smooth(me)
    ob = new_obj("GroundMid", me)
    # patch macro autour de la carte
    pr = 0.01
    px = np.arange(-1.6, 1.6 + 1e-6, pr)
    PX, PY = np.meshgrid(px, px, indexing="ij")
    rng = np.random.RandomState(sim.SEED + 3)
    # micro relief : grains et petits polygones (hauteur en m)
    h = np.zeros_like(PX)
    for k, (sc, a) in enumerate([(0.9, 0.006), (0.35, 0.004), (0.12, 0.0025), (0.05, 0.0012)]):
        ph = rng.uniform(0, 6.28, 4)
        h += a * (np.sin(PX / sc * 2.1 + ph[0]) * np.sin(PY / sc * 1.7 + ph[1]) +
                  0.5 * np.sin((PX + PY) / sc * 1.3 + ph[2]))
    edge = np.clip((1.6 - np.maximum(np.abs(PX), np.abs(PY))) / 0.25, 0, 1)
    h *= edge
    PV = np.stack([PX, PY, h], axis=-1).reshape(-1, 3)
    PF = grid_faces(len(px), len(px))
    pme = make_mesh("GroundPatch", PV, PF)
    add_float_attr(pme, "crack")
    add_float_attr(pme, "pit")
    pme.materials.append(m_ground)
    shade_smooth(pme)
    pob = new_obj("GroundPatch", pme)
    return ob, V, pob, PV


def build_sheet(m_top, m_inner, m_rim):
    ps, rs = sim.sheet_grid()
    PS, RS = np.meshgrid(ps, rs, indexing="ij")
    rest = np.stack([RS * np.sin(PS), RS * np.cos(PS), np.zeros_like(PS)], axis=-1).reshape(-1, 3)
    F = grid_faces(len(ps), len(rs))[:, ::-1]   # normale = face superieure d'origine
    me = make_mesh("CrustSheet", rest, F)
    add_float_attr(me, "sat")
    set_uv(me, rest[:, :2])
    me.materials.append(m_top)
    me.materials.append(m_inner)
    me.materials.append(m_rim)
    shade_smooth(me)
    ob = new_obj("CrustSheet", me)
    so = ob.modifiers.new("thickness", "SOLIDIFY")
    so.thickness = sim.CRUST_T
    so.offset = -1.0
    so.use_even_offset = True
    so.material_offset = 1
    so.material_offset_rim = 2
    so.use_rim = True
    return ob


def build_block_mesh(i, b, m_stone):
    c = b["cell"]
    hx = (c["x1"] - c["x0"]) / 2
    hy = (c["y1"] - c["y0"]) / 2
    h = (c["zt"] - c["zb"]) + (0.08 if c["tier"] == 0 else 0.02)
    rng = np.random.RandomState(sim.SEED + 100 + i)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 2 * hx
        v.co.y *= 2 * hy
        v.co.z = (v.co.z + 0.5) * h - h
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.035, segments=2, affect="EDGES", profile=0.6)
    box_verts = set(bm.verts)
    # racine cristalline (ile flottante) : enveloppe convexe irreguliere
    depth = b["root"]
    pts = [(sx * hx * 0.97, sy * hy * 0.97, -h) for sx in (-1, 1) for sy in (-1, 1)]
    for _ in range(34):
        u = rng.uniform(0, 1) ** 1.4
        r = (1 - u) ** 0.45
        pts.append((rng.uniform(-1, 1) * hx * r, rng.uniform(-1, 1) * hy * r, -h - depth * u * rng.uniform(0.5, 1.0)))
    nv0 = [bm.verts.new(p) for p in pts]
    hull = bmesh.ops.convex_hull(bm, input=nv0)
    bmesh.ops.delete(bm, geom=[g for g in hull.get("geom_interior", []) if isinstance(g, bmesh.types.BMVert)], context="VERTS")
    bm.verts.ensure_lookup_table()
    me = bpy.data.meshes.new(f"Block_{i:02d}")
    bm.to_mesh(me)
    bm.free()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    rootm = (co[:, 2] < -h - 0.01).astype(np.float32)
    add_float_attr(me, "root")
    set_attr(me, "root", rootm)
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(m_stone)
    ob = new_obj(f"Block_{i:02d}", me)
    # cle de forme : racine retractee sous le bloc (emboitement)
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="retract")
    for j, v in enumerate(sk.data):
        z = co[j, 2]
        if z < -h:
            v.co.z = -h + (z + h) * 0.04
            v.co.x = co[j, 0] * 0.9
            v.co.y = co[j, 1] * 0.9
    return ob, h


def build_stage(m_black, m_floor, m_amber):
    root = bpy.data.objects.new("StageRoot", None)
    link(root)
    parts = []
    x0, x1, y0, y1, z0, z1 = sim.STAGE_FLOOR

    def box(name, x0, x1, y0, y1, z0, z1, mat, bev=0.01):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
            v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
            v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, segments=2, affect="EDGES")
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        ob = new_obj(name, me)
        ob.parent = root
        parts.append(ob)
        return ob
    box("StageFloor", x0, x1, y0, y1, z0, z1, m_floor, 0.015)
    box("StageFloor2", x0 + 0.3, x1 - 0.3, y0 + 0.25, y1, z1, z1 + 0.08, m_floor, 0.01)
    bx0, bx1, by0, by1, bz0, bz1 = sim.BACKDROP
    w = (bx1 - bx0) / 4
    gap = 0.07
    for k in range(4):
        box(f"Panel_{k}", bx0 + k * w + gap / 2, bx0 + (k + 1) * w - gap / 2, by0, by1, bz0, bz1, m_black, 0.012)
    lines = []
    for k in range(3):
        xc = bx0 + (k + 1) * w
        ln = box(f"AmberLine_{k}", xc - 0.022, xc + 0.022, by0 + 0.06, by0 + 0.12, bz0 + 0.08, bz1 - 0.08, m_amber[k], 0.004)
        L = bpy.data.lights.new(f"AmberLight_{k}", "AREA")
        L.shape = "RECTANGLE"
        L.size = 0.05
        L.size_y = bz1 - bz0 - 0.2
        L.color = (1.0, 0.45, 0.12)
        L.energy = 0.0
        L.cycles.cast_shadow = True
        lo = bpy.data.objects.new(f"AmberLight_{k}", L)
        link(lo)
        lo.parent = root
        lo.location = (xc, by0 - 0.05, (bz0 + bz1) / 2)
        lo.rotation_euler = (math.radians(-90), 0, 0)
        lo.visible_camera = False
        lines.append((ln, L))
    return root, parts, lines


def build_satin(m_satin):
    K, NU, NV = sim.K_STRIPS, sim.NU, sim.NV
    verts = np.zeros((K * NU * NV, 3))
    faces = []
    uvs = []
    for k in range(K):
        faces.append(grid_faces(NU, NV, offset=k * NU * NV))
        uu = np.linspace(0, 1, NU)
        vv = np.linspace(0, 1, NV)
        U, Vv = np.meshgrid(uu, vv, indexing="ij")
        uvs.append(np.stack([U.ravel() * 70.0, ((k + Vv) / K).ravel() * 12.0], axis=-1))
    me = make_mesh("Satin", verts, np.vstack(faces))
    set_uv(me, np.vstack(uvs))
    me.materials.append(m_satin)
    shade_smooth(me)
    ob = new_obj("Satin", me)
    wm = ob.modifiers.new("weld", "WELD")
    wm.merge_threshold = 0.004
    return ob


def build_veil(m_satin):
    nu, nv = 48, 28
    me = make_mesh("Veil", np.zeros((nu * nv, 3)), grid_faces(nu, nv))
    U, V = np.meshgrid(np.linspace(0, 6.4, nu), np.linspace(0, 3.6, nv), indexing="ij")
    set_uv(me, np.stack([U.ravel(), V.ravel()], axis=-1))
    me.materials.append(m_satin)
    shade_smooth(me)
    ob = new_obj("Veil", me)
    so = ob.modifiers.new("thick", "SOLIDIFY")
    so.thickness = 0.004
    return ob


# --------------------------------------------------------------------- scene


class Rig:
    pass


def look_at(pos, tgt, roll):
    f = Vector(tuple(tgt)) - Vector(tuple(pos))
    f.normalize()
    up = Vector((0, 0, 1))
    r = f.cross(up)
    if r.length < 1e-6:
        r = Vector((1, 0, 0))
    r.normalize()
    u = r.cross(f)
    cr, sr = math.cos(roll), math.sin(roll)
    r2 = r * cr + u * sr
    u2 = -r * sr + u * cr
    m = Matrix((r2, u2, -f)).transposed().to_4x4()
    m.translation = Vector(tuple(pos))
    return m


def np_to_matrix(R, P):
    m = Matrix([list(R[0]) + [P[0]], list(R[1]) + [P[1]], list(R[2]) + [P[2]], [0, 0, 0, 1]])
    return m


def build_scene(args):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start = 0
    sc.frame_end = sim.N_FRAMES - 1

    skyimg = build_sky_image()
    haze = build_haze_group(skyimg)
    salt = build_salt_group()
    salt_c = build_salt_group(with_crack=True)
    setup_world(skyimg)

    M = dict(ground=mat_ground(salt_c, haze), crust_top=mat_crust(salt, haze, "Crust_Top"),
             crust_rim=mat_crust(salt, haze, "Crust_Rim", damp=0.25), crust_inner=mat_crust_inner(salt, haze),
             satin=mat_satin(haze), crystal=mat_crystal(haze), stone=mat_stone(salt, haze),
             card=mat_card(haze), card_edge=mat_card(haze, True), black=mat_black(haze, "Stage_Black", 0.32, 0.55),
             floor=mat_black(haze, "Stage_Floor", 0.16, 0.7), dust=mat_dust(haze),
             chunk=mat_crust(salt, haze, "Chunk", damp=0.15, coord="OBJ"))
    amber = [mat_amber(haze) for _ in range(3)]

    rig = Rig()
    # soleil
    L = bpy.data.lights.new("Sun", "SUN")
    L.energy = 5.2
    L.color = (1.0, 0.76, 0.52)
    L.angle = math.radians(0.9)
    sun = bpy.data.objects.new("Sun", L)
    link(sun)
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = SUN.to_track_quat("Z", "Y")
    # filet de lumiere rouge sur la tranche
    RL = bpy.data.lights.new("RedEdge", "AREA")
    RL.shape = "DISK"
    RL.size = 0.03
    RL.color = (1.0, 0.06, 0.03)
    RL.energy = 0.0
    rig.red = bpy.data.objects.new("RedEdge", RL)
    rig.red.visible_camera = False
    link(rig.red)

    rig.card = build_card(M["card"], M["card_edge"])
    rig.ground, rig.ground_rest, rig.patch, rig.patch_rest = build_ground(M["ground"])
    rig.sheet = build_sheet(M["crust_top"], M["crust_inner"], M["crust_rim"])

    # cristaux (sources d'instances)
    rngc = np.random.RandomState(sim.SEED + 7)
    cry = [crystal_mesh(f"cry{i}", rngc, elong=rngc.uniform(0.7, 1.6), flat=rngc.uniform(0.5, 1.2)) for i in range(6)]
    c_cry = instance_collection("CrystalSrc", cry, M["crystal"])
    chk = [crystal_mesh(f"chk{i}", rngc, elong=rngc.uniform(0.8, 1.4), flat=rngc.uniform(0.25, 0.5)) for i in range(6)]
    c_chk = instance_collection("ChunkSrc", chk, M["chunk"])
    dst = [crystal_mesh(f"dst{i}", rngc) for i in range(2)]
    c_dst = instance_collection("DustSrc", dst, M["dust"])

    # cristaux macro autour du point de contact
    n_macro = 9000
    rr = np.random.RandomState(sim.SEED + 9)
    ang = rr.uniform(0, 2 * math.pi, n_macro)
    rad = 1.45 * rr.uniform(0, 1, n_macro) ** 1.6
    pos = np.c_[rad * np.sin(ang), rad * np.cos(ang), np.zeros(n_macro)]
    size = 0.0012 + 0.008 * rr.power(4.0, n_macro) * (0.35 + 0.65 * np.exp(-rad / 0.4))
    size *= np.where(rr.uniform(0, 1, n_macro) < 0.04, 2.2, 1.0)
    pos[:, 2] = size * rr.uniform(0.0, 0.25, n_macro)
    # pas de cristal a l'interieur de la carte
    rig.macro = PointCloud("MacroCrystals", n_macro, c_cry)
    rig.macro_rest = dict(pos=pos, size=size, rot=rr.uniform(0, 6.28, (n_macro, 3)), pid=rr.randint(0, 6, n_macro),
                          phase=rr.uniform(0, 6.28, n_macro))
    rig.macro.update(pos, rig.macro_rest["rot"], size, rig.macro_rest["pid"])

    rig.grains = PointCloud("ImpactGrains", 400, c_cry)
    rig.chunks = PointCloud("DetachChunks", 2600, c_chk)
    rig.shards = PointCloud("Shards", 520, c_chk)
    rig.dust = PointCloud("Dust", 1500, c_dst)

    # blocs
    rig.blocks = []
    for i, b in enumerate(sim.block_layout()):
        ob, h = build_block_mesh(i, b, M["stone"])
        rig.blocks.append(ob)
    rig.stage, rig.stage_parts, rig.stage_lines = build_stage(M["black"], M["floor"], amber)
    rig.amber_mats = amber
    rig.satin = build_satin(M["satin"])
    rig.veil = build_veil(M["satin"])

    # camera
    cd = bpy.data.cameras.new("Cam")
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36.0
    cd.sensor_width = 36.0
    cd.clip_start = 0.004
    cd.clip_end = 9000
    cd.dof.use_dof = True
    rig.cam = bpy.data.objects.new("Cam", cd)
    link(rig.cam)
    sc.camera = rig.cam
    return rig


# --------------------------------------------------------------------- mise a jour par image

STATE = {}


def update(scene, depsgraph=None):
    rig = STATE["rig"]
    f = scene.frame_current + scene.frame_subframe
    t = f / FPS
    cam = sim.camera(t)
    rig.cam.matrix_world = look_at(cam["pos"], cam["target"], cam["roll"])
    cd = rig.cam.data
    cd.lens = cam["focal"]
    cd.dof.focus_distance = cam["focus"]
    cd.dof.aperture_fstop = cam["fstop"]

    # carte
    R, tr = sim.card_pose(t)
    rig.card.matrix_world = np_to_matrix(R, tr)
    # filet rouge : glisse le long de la tranche pendant la descente
    if t < 3.2:
        u = min(t / sim.T_IMPACT, 1.0)
        edge_local = np.array([-sim.CARD_W / 2 + sim.CARD_W * (0.15 + 0.7 * u), sim.CARD_H / 2 + 0.02, 0.006])
        p = R @ edge_local + tr
        rig.red.location = tuple(p)
        rig.red.rotation_mode = "QUATERNION"
        n = Vector(tuple(R @ np.array([0, 1.0, 0.3])))
        rig.red.rotation_quaternion = (-n).to_track_quat("-Z", "Y")
        rig.red.data.energy = 0.06 * float(sim.smoothstep(0.2, 0.9, t)) * (1.0 - float(sim.smoothstep(2.3, 2.9, t)))
    else:
        rig.red.data.energy = 0.0

    # sol : onde + logement de la croute
    V = rig.ground_rest
    bump, crack = sim.ring_field(V[:, 0], V[:, 1], t)
    pit = sim.pit_depth(V[:, 0], V[:, 1], t)
    Z = bump * np.clip(1.0 - (sim.pit_depth(V[:, 0], V[:, 1], 0.0) < -0.01), 0, 1) + pit
    P = V.copy()
    P[:, 2] = Z
    set_coords(rig.ground.data, P)
    heal = 1.0 - float(sim.smoother(10.4, 12.8, t))
    set_attr(rig.ground.data, "crack", crack * heal)
    set_attr(rig.ground.data, "pit", np.clip(-pit / sim.CRUST_T, 0, 1))
    PV = rig.patch_rest
    pb, pc = sim.ring_field(PV[:, 0], PV[:, 1], t)
    PP = PV.copy()
    PP[:, 2] += pb
    set_coords(rig.patch.data, PP)
    set_attr(rig.patch.data, "crack", pc * heal)

    # cristaux macro : frisson avant l'impact, sursaut a l'impact
    mr = rig.macro_rest
    pos = mr["pos"].copy()
    rot = mr["rot"].copy()
    d = np.hypot(pos[:, 0], pos[:, 1])
    if 2.0 < t < 3.4:
        pre = float(sim.smoothstep(2.0, 2.5, t)) * (t < sim.T_IMPACT)
        jit = 0.0004 * pre * np.exp(-d / 0.08) * np.sin(t * 140 + mr["phase"])
        pos[:, 0] += jit
        pos[:, 2] += np.abs(jit)
        rb, _ = sim.ring_field(pos[:, 0], pos[:, 1], t)
        pos[:, 2] += rb * 1.6
        rot[:, 0] += rb * 30
    pos[:, 2] += sim.ring_field(pos[:, 0], pos[:, 1], t)[0] * 0.0
    rig.macro.update(pos, rot, mr["size"])

    # grains projetes a l'impact
    rg = np.random.RandomState(sim.SEED + 12)
    n = rig.grains.n
    v0 = np.c_[rg.normal(0, 0.25, n), rg.normal(-0.05, 0.25, n), rg.uniform(0.3, 1.1, n)]
    sz = 0.0008 + 0.003 * rg.power(3, n)
    dt = t - sim.T_IMPACT
    if 0 < dt < 3.5:
        p = np.c_[np.zeros(n), np.zeros(n), np.zeros(n)] + v0 * dt + 0.5 * np.array([0, 0, -9.81]) * dt * dt
        p[:, 2] = np.maximum(p[:, 2], sz * 0.4)
        rig.grains.update(p, rg.uniform(0, 6, (n, 3)) + dt * 20, sz, rg.randint(0, 6, n))
        rig.grains.ob.hide_render = False
    else:
        rig.grains.ob.hide_render = True

    # nappe
    vis_sheet = sim.sheet_visible(t)
    rig.sheet.hide_render = not vis_sheet
    if vis_sheet:
        Ps, Ns, sat, sig, crk = sim.sheet_state(t)
        set_coords(rig.sheet.data, Ps.reshape(-1, 3))
        set_attr(rig.sheet.data, "sat", sat.ravel())
    vis_chunks = 3.0 < t < sim.T_CUT
    rig.chunks.ob.hide_render = not vis_chunks
    if vis_chunks:
        p, r, s, pid = sim.detach_particles(t)
        rig.chunks.update(p, r, s, pid)

    # blocs, scene, satin
    after = t >= sim.T_CUT
    states = []
    for ob, b in zip(rig.blocks, sim.block_layout()):
        Rb, Pb, root = sim.block_pose(b, t)
        states.append((Rb, Pb))
        ob.hide_render = not after
        ob.matrix_world = np_to_matrix(Rb, Pb)
        ob.data.shape_keys.key_blocks["retract"].value = root
    rig.stage.hide_render = not after
    for p in rig.stage_parts:
        p.hide_render = not after
    Rs, off = sim.stage_pose(t)
    c = np.array([0.0, sim.Y0 + 0.65, 1.45])
    Mst = np.eye(4)
    Mst[:3, :3] = Rs
    Mst[:3, 3] = c + off - Rs @ c
    rig.stage.matrix_world = Matrix(Mst.tolist())
    lv = sim.amber_lines(t)
    for k, ((ln, Lk), mat) in enumerate(zip(rig.stage_lines, rig.amber_mats)):
        mat.node_tree.nodes[mat["emit_node"]].inputs[1].default_value = 38.0 * lv[k]
        Lk.energy = 260.0 * lv[k]
        rig.stage_lines[k][0].hide_render = not after
    rig.satin.hide_render = not after
    if after:
        rib = sim.ribbons_state(t, states)
        set_coords(rig.satin.data, rib.reshape(-1, 3))
    vv = sim.veil_state(t, sim.camera)
    rig.veil.hide_render = vv is None
    if vv is not None:
        set_coords(rig.veil.data, vv.reshape(-1, 3))

    # eclats flottants et poussiere
    sp, sr, ss, spid = shards_state(t, states)
    rig.shards.update(sp, sr, ss, spid)
    rig.shards.ob.hide_render = not after
    dp, dr, ds = dust_state(t)
    rig.dust.update(dp, dr, ds, np.zeros(len(ds), np.int32))


_SH = None


def shards_state(t, states):
    """eclats secondaires accroches aux blocs : montent avec eux, se figent, retombent pendant la reconstruction"""
    global _SH
    blocks = sim.block_layout()
    n = 520
    if _SH is None:
        r = np.random.RandomState(sim.SEED + 70)
        owner = r.randint(0, len(blocks), n)
        off = r.normal(0, 1, (n, 3)) * np.array([2.6, 2.6, 1.6]) + np.array([0, 0, -1.8])
        size = 0.05 + 0.35 * r.power(3, n)
        size[:3] = [0.55, 0.42, 0.35]   # cristaux nets qui passent pres de la camera
        _SH = dict(owner=owner, off=off, size=size, rot=r.uniform(0, 6.28, (n, 3)), pid=r.randint(0, 6, n),
                   spin=r.normal(0, 1, (n, 3)), fall=r.uniform(0, 0.6, n))
    S = _SH
    tau = sim.object_time(t)
    pos = np.zeros((n, 3))
    for i in range(n):
        Rb, Pb = states[S["owner"][i]]
        pos[i] = Pb + S["off"][i] * (1.0 + 0.6 * (1 - math.exp(-2.3 * max(tau - 6.0, 0))))
    # cristal pres de l'orbite (passage tres pres de l'objectif vers 8.3 s)
    c83 = sim.camera(8.3)
    fwd = c83["target"] - c83["pos"]
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1])
    right /= np.linalg.norm(right)
    pos[0] = c83["pos"] + fwd * 1.1 - right * 0.15 + np.array([0, 0, -0.25])
    c76 = sim.camera(7.6)
    pos[1] = c76["pos"] + (c76["target"] - c76["pos"]) / np.linalg.norm(c76["target"] - c76["pos"]) * 3.5 + np.array([1.2, 0, 0.6])
    c92 = sim.camera(9.2)
    pos[2] = c92["pos"] + (c92["target"] - c92["pos"]) / np.linalg.norm(c92["target"] - c92["pos"]) * 2.4 + np.array([-0.8, 0, -0.7])
    if t < 7.0:
        # les cristaux proches suivent l'elan general
        for i in range(3):
            pos[i] += np.array([0, 0, -3.0]) * (1 - math.exp(-2.3 * (7.0 - tau)))
    rot = S["rot"] + S["spin"] * min(tau - 6.0, 1.0) * 0.8
    scale = S["size"].copy()
    # reconstruction : chute et disparition dans les joints
    if t > 10.3:
        u = sim.clamp01((t - 10.3 - S["fall"]) / 1.8)
        pos[:, 2] -= 9.81 * 0.5 * (u * 1.8) ** 2 * 0.5
        pos[:, 2] = np.maximum(pos[:, 2], 0.0)
        scale *= (1 - sim.smoothstep(0.6, 1.0, u))
        scale[:3] *= 0
    return pos, rot, scale, S["pid"]


_DU = None


def dust_state(t):
    """poussiere : bouffees a la pose des blocs + poussieres en suspension qui se rarefient"""
    global _DU
    blocks = sim.block_layout()
    if _DU is None:
        r = np.random.RandomState(sim.SEED + 80)
        per = 24
        nb = len(blocks) * per
        owner = np.repeat(np.arange(len(blocks)), per)
        ang = r.uniform(0, 6.28, nb)
        spd = r.uniform(0.6, 2.4, nb)
        motes = 1500 - nb
        _DU = dict(nb=nb, owner=owner, ang=ang, spd=spd, up=r.uniform(0.1, 0.8, nb), sz=r.uniform(0.008, 0.03, nb),
                   mpos=np.c_[r.uniform(-14, 14, motes), r.uniform(8, 40, motes), r.uniform(0.3, 8, motes)],
                   msz=r.uniform(0.006, 0.02, motes) * (r.uniform(0, 1, motes) < 0.35), mph=r.uniform(0, 6.28, (motes, 3)),
                   mfade=r.uniform(14.2, 19.5, motes))
    D = _DU
    nb = D["nb"]
    pos = np.zeros((1500, 3))
    sz = np.zeros(1500)
    for i in range(len(blocks)):
        b = blocks[i]
        tl = sim.block_land_time(b)
        sel = slice(i * 24, (i + 1) * 24)
        dt = t - tl
        if dt <= 0:
            continue
        c = b["cell"]
        hx, hy = (c["x1"] - c["x0"]) / 2, (c["y1"] - c["y0"]) / 2
        a = D["ang"][sel]
        base = b["F"] + np.c_[np.cos(a) * hx, np.sin(a) * hy, np.full(24, -(c["zt"] - c["zb"]) + 0.05)]
        dist = D["spd"][sel] * (1 - np.exp(-dt * 2.2)) / 2.2
        p = base + np.c_[np.cos(a) * dist, np.sin(a) * dist, D["up"][sel] * (1 - np.exp(-dt * 1.5)) - 0.12 * dt]
        p[:, 2] = np.maximum(p[:, 2], 0.01)
        pos[sel] = p
        sz[sel] = D["sz"][sel] * float(sim.smoothstep(0, 0.08, dt)) * (1 - float(sim.smoothstep(0.8, 2.6, dt)))
    # poussieres en suspension dans la lumiere (plan final)
    m = D["mpos"].copy()
    m += 0.25 * np.sin(t * 0.4 + D["mph"]) + np.array([0.05, -0.03, -0.02]) * t
    pos[nb:] = m
    vis = sim.smoothstep(12.8, 13.8, t) * (1 - sim.smoothstep(D["mfade"] - 0.6, D["mfade"], t))
    sz[nb:] = D["msz"] * vis
    rot = np.zeros((1500, 3))
    return pos, rot, sz


# --------------------------------------------------------------------- rendu


def setup_render(args):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = args.samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.max_bounces = 8
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 4
    cy.transmission_bounces = 6
    cy.transparent_max_bounces = 8
    cy.volume_bounces = 0
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 6.0
    cy.blur_glossy = 0.5
    cy.use_light_tree = True
    sc.render.use_persistent_data = True
    sc.render.threads_mode = "AUTO"
    h = args.res * 16 // 9
    sc.render.resolution_x = args.res
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.filter_size = 1.2
    sc.render.use_motion_blur = not args.noblur
    sc.render.motion_blur_shutter = 0.35
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    vs = sc.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.exposure = args.exposure
    # compositing : halo doux sur les hautes lumieres + vignettage leger
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    gl = nt.nodes.new("CompositorNodeGlare")
    gl.glare_type = "FOG_GLOW"
    gl.quality = "HIGH"
    gl.threshold = 2.0
    gl.size = 7
    gl.mix = -0.82
    el = nt.nodes.new("CompositorNodeEllipseMask")
    el.width = 1.25
    el.height = 1.05
    bl = nt.nodes.new("CompositorNodeBlur")
    bl.filter_type = "GAUSS"
    bl.use_relative = True
    bl.factor_x = 0.25
    bl.factor_y = 0.25
    mi = nt.nodes.new("CompositorNodeMixRGB")
    mi.blend_type = "MULTIPLY"
    mx = nt.nodes.new("CompositorNodeMapRange")
    mx.inputs[1].default_value = 0.0
    mx.inputs[2].default_value = 1.0
    mx.inputs[3].default_value = 0.78
    mx.inputs[4].default_value = 1.0
    comp = nt.nodes.new("CompositorNodeComposite")
    L = nt.links
    L.new(rl.outputs["Image"], gl.inputs[0])
    L.new(gl.outputs[0], comp.inputs[0])
    for nd in (el, bl, mi, mx):
        nt.nodes.remove(nd)


def parse_frames(s, step):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1, step))
        elif part:
            out.append(int(part))
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "renders", "frames"))
    ap.add_argument("--res", type=int, default=1080)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--frames", default="")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--noblur", action="store_true")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--save", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--threads", type=int, default=0)
    args, _unknown = ap.parse_known_args(argv)
    rig = build_scene(args)
    STATE["rig"] = rig
    setup_render(args)
    if args.threads:
        bpy.context.scene.render.threads_mode = "FIXED"
        bpy.context.scene.render.threads = args.threads
    bpy.app.handlers.frame_change_pre.clear()
    bpy.app.handlers.frame_change_pre.append(update)
    if args.save:
        bpy.context.scene.frame_set(int(14.8 * FPS))
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
    if args.frames:
        os.makedirs(args.out, exist_ok=True)
        sc = bpy.context.scene
        for fr in parse_frames(args.frames, args.step):
            path = os.path.join(args.out, f"f{fr:04d}.png")
            if os.path.exists(path) and not args.force:
                continue
            sc.frame_set(fr)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print(f"RUPTURE frame {fr} -> {path}", flush=True)


if __name__ == "__main__":
    main()
