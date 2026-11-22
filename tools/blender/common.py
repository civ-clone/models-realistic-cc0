"""Shared helpers for the trial (imported by the other trial scripts)."""
import bpy, mathutils, math

def load_scan(glb, height):
    """Import the scan, join to one mesh, stand it on the origin with the given height. Returns the object."""
    bpy.ops.import_scene.gltf(filepath=glb)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.scene.objects: o.select_set(False)
    for o in meshes: o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.join()
    hi = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o.type == "EMPTY": bpy.data.objects.remove(o)
    hi.name = "hi"
    vs = [v.co for v in hi.data.vertices]
    mn = mathutils.Vector([min(v[i] for v in vs) for i in range(3)]); mx = mathutils.Vector([max(v[i] for v in vs) for i in range(3)])
    s = height / (mx.z - mn.z)
    centre = mathutils.Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    hi.data.transform(mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation(-centre))
    hi.data.update()
    return hi

def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)

def camera(name, loc, target, ortho=None, lens=50):
    cam = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = mathutils.Vector(target) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho: cam.type = "ORTHO"; cam.ortho_scale = ortho
    else: cam.lens = lens
    return ob

def workbench(res_x, res_y):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_shadows = False
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    if sc.world is None: sc.world = bpy.data.worlds.new("w")

def render(cam, path):
    sc = bpy.context.scene; sc.camera = cam; sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
