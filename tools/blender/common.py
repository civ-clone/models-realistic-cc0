"""Shared helpers for the Blender scripts: a camera, the workbench renderer and a render."""
import bpy, mathutils, math

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
