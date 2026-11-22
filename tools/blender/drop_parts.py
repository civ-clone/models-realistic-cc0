"""Delete named mesh objects from a GLB and save the rest unchanged. Args: IN.glb OUT.glb NAME [NAME ...]"""
import bpy, sys
args = sys.argv[sys.argv.index("--") + 1:]
src, dst, names = args[0], args[1], set(args[2:])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
gone = [o.name for o in list(bpy.context.scene.objects) if o.name in names]
for n in gone:
    bpy.data.objects.remove(bpy.data.objects[n])
print("DROPPED", sorted(gone), "missing", sorted(names - set(gone)))
if names - set(gone):
    raise RuntimeError(f"Error: no part named {sorted(names - set(gone))}")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_animations=True)
