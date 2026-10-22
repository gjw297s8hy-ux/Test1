import sys, time, math, bpy
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import diorama as D
sc = D.reset(samples=int(sys.argv[-2]))
sc.render.use_persistent_data = True
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
D.build_diorama()
sun = bpy.data.lights.new('Sun', 'SUN'); sun.energy = 2.2; sun.angle = math.radians(6); sun.color = (0.92, 0.94, 1.0)
so = bpy.data.objects.new('Sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(40), math.radians(-20), math.radians(35))
area = bpy.data.lights.new('KeyRed', 'AREA'); area.energy = 900; area.color = (1, 0.08, 0.08); area.size = 3
ao = bpy.data.objects.new('KeyRed', area); sc.collection.objects.link(ao); ao.location = D.T(5, 8, 5)
ao.rotation_euler = (math.radians(50), 0, math.radians(135))
D.iso_camera(target=(-0.3, 2.4, -0.3), zoom=100)
sc.render.filepath = sys.argv[-1]
t0 = time.time(); bpy.ops.render.render(write_still=True); print('RENDER_TIME', round(time.time() - t0, 1))
