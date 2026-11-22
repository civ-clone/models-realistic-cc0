"""Cut a hard-surface model (vehicle, ship, aircraft, prop, or an unrigged figure) to a triangle budget,
keeping its parts, hierarchy and animations, and bake all its colour into one new texture.

Args (after --): GLB OUTDIR TARGET [TEXSIZE] [MODE] [DEPTH]
MODE "none" only takes the 'before' pictures (for models already within budget).
MODE "parts" (default) cuts each part separately and keeps parts, hierarchy and animations.
MODE "rewrap" wraps the whole model in one new surface (octree remesh at DEPTH, default 9), cuts that,
and bakes from all the original parts: for models with too many parts to cut each one far enough.
Writes OUTDIR/cut.glb, OUTDIR/colour.png, OUTDIR/compare.png (original above, cut below) and OUTDIR/stats.json.
Only reads the GLB as data; no scripts from it run (Blender is started with -Y and factory settings)."""
import bpy, bmesh, sys, os, math, json, mathutils
sys.path.insert(0, os.path.dirname(__file__))
import common

args = sys.argv[sys.argv.index("--") + 1:]
glb, out, target = args[0], args[1], int(args[2])
texsize = int(args[3]) if len(args) > 3 else 1024
mode = args[4] if len(args) > 4 else "parts"
depth = int(args[5]) if len(args) > 5 else 9
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.threads_mode = "FIXED"; sc.render.threads = 2
bpy.ops.import_scene.gltf(filepath=glb)
sc.frame_set(0)
arms = [o for o in sc.objects if o.type == "ARMATURE"]
for a in arms:
    a.data.pose_position = "REST"  # copy, cut and bake skinned parts in their bind shape
objs = [o for o in sc.objects if o.type == "MESH" and not o.hide_render and o.visible_get()]
skinned = [o for o in objs if any(m.type == "ARMATURE" for m in o.modifiers)]
stats = {"glb": glb, "target": target, "mode": mode, "parts_in": len(objs), "skinned_parts": len(skinned),
         "anims": [a.name for a in bpy.data.actions]}

def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)

def scene_tris():
    return sum(tri_count(o.data) for o in objs)

stats["tris_in"] = scene_tris()
print("parts", len(objs), "triangles", stats["tris_in"], "unique meshes", len({o.data for o in objs}))

# world-space copies of the original, for the bake and the 'before' picture
hi_col = bpy.data.collections.new("hi"); sc.collection.children.link(hi_col)
dg = bpy.context.evaluated_depsgraph_get()
pairs = []  # (lo object, hi object) for one user of each unique mesh
seen = {}
for o in objs:
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
    hi = bpy.data.objects.new("hi_" + o.name, me); hi_col.objects.link(hi)
    if o.data not in seen:
        seen[o.data] = o; pairs.append((o, hi))
    else:
        hi.hide_render = True  # instances share the first user's texture area; bake from that one only

# bounds of the whole model, for welding and framing
pts = [h.matrix_world @ mathutils.Vector(c) for h in hi_col.objects for c in h.bound_box]
mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
size = max(mx - mn); centre = (mn + mx) / 2
stats["size"] = round(size, 3)

# pictures of the original first; a rigged figure is shown in its first animation's pose, not lying in its bind pose
def set_pose(on):
    for a in arms:
        a.data.pose_position = "POSE" if on else "REST"
    bpy.context.view_layer.update()

def shown_points():
    d = bpy.context.evaluated_depsgraph_get(); ps = []
    for o in objs:
        e = o.evaluated_get(d); m = e.to_mesh()
        step = max(1, len(m.vertices) // 500); ps += [o.matrix_world @ m.vertices[i].co for i in range(0, len(m.vertices), step)]
        e.to_mesh_clear()
    return ps

set_pose(True)
pts = shown_points()
mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
centre = (mn + mx) / 2

def frame_cams():
    d = mx - mn
    long_axis = 0 if d.x >= d.y else 1
    side = mathutils.Vector((0, -1, 0)) if long_axis == 0 else mathutils.Vector((-1, 0, 0))  # glTF fronts face -y
    along = mathutils.Vector((1, 0, 0)) if long_axis == 0 else mathutils.Vector((0, 1, 0))
    up = mathutils.Vector((0, 0, 1))
    game = fit(common.camera("game", centre + (side * 1.0 + along * 0.6 + up * 1.1).normalized() * size * 3, centre, ortho=size), 1.06)
    close = fit(common.camera("close", centre + (side * 1.0 - along * 0.35 + up * 0.35).normalized() * size * 3, centre, ortho=size), 1.0 if arms else 0.8)
    return game, close

def fit(cam, zoom):
    """Centre the camera on the model's projected extent and size the view to it (480x300 frame)."""
    cam.data.clip_start = size * 0.01; cam.data.clip_end = size * 10
    bpy.context.view_layer.update()
    rot = cam.matrix_world.to_3x3(); inv = rot.inverted()
    vs = [inv @ (p - cam.location) for p in pts]
    x0, x1 = min(v.x for v in vs), max(v.x for v in vs); y0, y1 = min(v.y for v in vs), max(v.y for v in vs)
    cam.location = cam.location + rot @ mathutils.Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0))
    cam.data.ortho_scale = max(x1 - x0, (y1 - y0) * 480 / 300) * 1.06 * zoom
    return cam

# the preview shows each material's active image node: make that the base colour's image
for m in {s.material for o in objs for s in o.material_slots if s.material and s.material.use_nodes}:
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED" and n.inputs["Base Color"].is_linked:
            src = n.inputs["Base Color"].links[0].from_node
            while src.type != "TEX_IMAGE" and src.inputs and any(i.is_linked for i in src.inputs):
                src = next(i for i in src.inputs if i.is_linked).links[0].from_node
            if src.type == "TEX_IMAGE":
                m.node_tree.nodes.active = src
common.workbench(480, 300); sc.view_settings.exposure = 1.0; sc.display.shading.show_specular_highlight = False
sc.display.shading.show_backface_culling = False
game, close = frame_cams()
hi_col.hide_render = True
for v, cam in (("game", game), ("close", close)):
    common.render(cam, os.path.join(out, f"orig_{v}.png"))
set_pose(False)
if mode == "none":
    stats["tris_out"] = stats["tris_in"]; stats["parts_out"] = len(objs)
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print("STATS", json.dumps(stats)); sys.exit(0)

def decimate_to(o, n_target):
    for _ in range(10):
        n = tri_count(o.data)
        if n <= n_target * 1.02:
            break
        for x in sc.objects: x.select_set(False)
        o.select_set(True); bpy.context.view_layer.objects.active = o
        d = o.modifiers.new("dec", "DECIMATE"); d.ratio = n_target / n; d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)

if mode == "rewrap":
    bm = bmesh.new()
    for h in hi_col.objects:
        bm.from_mesh(h.data)
    me = bpy.data.meshes.new("rewrap"); bm.to_mesh(me); bm.free()
    lo = bpy.data.objects.new("rewrapped", me); sc.collection.objects.link(lo)
    for x in sc.objects: x.select_set(False)
    lo.select_set(True); bpy.context.view_layer.objects.active = lo
    if os.environ.get("REWRAP_SOLIDIFY"):  # thicken thin sheets (sails) so a coarse remesh keeps them
        so = lo.modifiers.new("solid", "SOLIDIFY"); so.thickness = size * float(os.environ["REWRAP_SOLIDIFY"]); so.offset = 0.0
        bpy.ops.object.modifier_apply(modifier=so.name)
        stats["solidify"] = float(os.environ["REWRAP_SOLIDIFY"])
    r = lo.modifiers.new("remesh", "REMESH")
    if os.environ.get("REWRAP_METHOD", "voxel") == "voxel":
        r.mode = "VOXEL"; r.voxel_size = size / 2 ** depth; r.adaptivity = 0.0
    else:
        r.mode = "SHARP"; r.octree_depth = depth; r.scale = 0.99; r.sharpness = 1.0
        r.use_remove_disconnected = True; r.threshold = 0.02
    bpy.ops.object.modifier_apply(modifier=r.name)
    stats["tris_remeshed"] = tri_count(lo.data)
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=size * 1e-4); bpy.ops.object.mode_set(mode="OBJECT")
    print("remeshed", stats["tris_remeshed"])
    decimate_to(lo, target)
    for p_ in lo.data.polygons: p_.use_smooth = False
    for o in objs:
        o.hide_render = True
    stats["tris_out"] = tri_count(lo.data); stats["parts_out"] = 1
    lo.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")

# weld and cut each unique mesh, in rounds, until the scene meets the budget
def mesh_users(me):
    return [o for o in objs if o.data == me]

for o, _ in (pairs if mode == "parts" else []):
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    dims = max(max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts) for i in range(3)) if bm.verts else 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=max(dims * 2e-4, 1e-7))
    bm.to_mesh(me); bm.free(); me.update()
stats["tris_welded"] = scene_tris()

for rnd in range(6 if mode == "parts" else 0):
    total = scene_tris()
    if total <= target * 1.02:
        break
    ratio = target / total
    for o, _ in pairs:
        me = o.data
        n = tri_count(me)
        if n <= 4:
            continue
        tmp = bpy.data.objects.new("tmp", me); sc.collection.objects.link(tmp)
        d = tmp.modifiers.new("dec", "DECIMATE"); d.ratio = max(ratio, 4 / n); d.use_collapse_triangulate = True
        tdg = bpy.context.evaluated_depsgraph_get(); tdg.update()
        new = bpy.data.meshes.new_from_object(tmp.evaluated_get(tdg))
        bpy.data.objects.remove(tmp)
        for u in mesh_users(me):
            u.data = new
        if me.users == 0:
            bpy.data.meshes.remove(me)
    pairs = [(o, h) for o, h in pairs]
    print("round", rnd, "ratio", round(ratio, 4), "triangles", scene_tris())
if mode == "parts":
    stats["tris_out"] = scene_tris()
    stats["parts_out"] = sum(1 for o in objs if tri_count(o.data) > 0)

# one shared texture layout across all the cut parts
for x in sc.objects: x.select_set(False)
bake_objs = [o for o, _ in pairs if tri_count(o.data) > 0] if mode == "parts" else []
for o in bake_objs:
    me = o.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    o.select_set(True)
if bake_objs:
    bpy.context.view_layer.objects.active = bake_objs[0]
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

img = bpy.data.images.new("colour", texsize, texsize)
mat = bpy.data.materials.new("baked"); mat.use_nodes = True; nt = mat.node_tree
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"]); nt.nodes.active = tex
nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
for o in (objs if mode == "parts" else [lo]):
    o.data.materials.clear(); o.data.materials.append(mat)

# metallic or glassy surfaces have no diffuse colour, so they would bake black: make the originals plain
for h in hi_col.objects:
    for m in h.data.materials:
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    for inp in ("Metallic", "Transmission Weight"):
                        s = n.inputs.get(inp)
                        if s:
                            for l in list(s.links): m.node_tree.links.remove(l)
                            s.default_value = 0.0
sc.render.engine = "CYCLES"; sc.cycles.samples = 4; sc.cycles.device = "CPU"
b = sc.render.bake; b.use_selected_to_active = True; b.margin = 3
b.use_pass_direct = False; b.use_pass_indirect = False; b.use_pass_color = True
hi_col.hide_render = False
if mode == "rewrap":
    b.cage_extrusion = size * 0.01; b.max_ray_distance = size * 0.04
    for x in sc.objects: x.select_set(False)
    for h in hi_col.objects:
        h.hide_render = False; h.select_set(True)
    lo.select_set(True); bpy.context.view_layer.objects.active = lo
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
for i, (o, h) in enumerate(pairs if mode == "parts" else []):
    if tri_count(o.data) == 0:
        continue
    ps = max(h.dimensions) or size
    ws = max(o.matrix_world.to_scale()) or 1.0
    # found by testing on the Artillery (a part under a x100 parent): the bake measures the cage's
    # extrusion in the part's own units, but the ray distance in world units
    b.cage_extrusion = ps * 0.04 / ws; b.max_ray_distance = ps * 0.2
    for x in sc.objects: x.select_set(False)
    h.select_set(True); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_clear=(i == 0))
img.filepath_raw = os.path.join(out, "colour.png"); img.file_format = "PNG"; img.save()
hi_col.hide_render = True

# pictures of the cut version, and of a rigged one part-way through some of its animations
sc.render.engine = "BLENDER_WORKBENCH"
set_pose(True)
for v, cam in (("game", game), ("close", close)):
    common.render(cam, os.path.join(out, f"cut_{v}.png"))
if arms and arms[0].animation_data:
    ad = arms[0].animation_data; first = ad.action
    want = ("walk", "idle", "talk", "attack", "fire", "shoot", "death", "die", "run")
    acts = sorted(bpy.data.actions, key=lambda a: next((i for i, w in enumerate(want) if w in a.name.lower()), 99))[:3]
    stats["anim_pictures"] = []
    for i, act in enumerate(acts):
        ad.action = act
        if getattr(ad, "action_slot", None) is None and getattr(act, "slots", None):
            ad.action_slot = act.slots[0]
        f0, f1 = act.frame_range; sc.frame_set(int(f0 + (f1 - f0) * 0.3))
        common.render(close, os.path.join(out, f"anim_{i}.png")); stats["anim_pictures"].append(act.name)
    ad.action = first; sc.frame_set(0)

# export the cut version only, with its hierarchy, any skeleton and any animations
for a in arms:
    a.data.pose_position = "POSE"
for h in list(hi_col.objects):
    bpy.data.objects.remove(h)
for c in (game, close):
    bpy.data.objects.remove(c)
if mode == "rewrap":
    for o in list(sc.objects):
        if o is not lo:
            bpy.data.objects.remove(o)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
if os.environ.get("DROP_ANIMS"):  # animations whose licence isn't the model's (e.g. Mixamo) are left out
    for ob in sc.objects:
        if ob.animation_data:
            ob.animation_data.action = None
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    stats["anims_dropped"] = True
bpy.ops.export_scene.gltf(filepath=os.path.join(out, "cut.glb"), export_format="GLB", export_animations=True,
                          export_image_format="AUTO", use_selection=False)
stats["vertex_groups"] = {o.name: len(o.vertex_groups) for o in sc.objects if o.type == "MESH" and o.vertex_groups}
json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
print("STATS", json.dumps(stats))
