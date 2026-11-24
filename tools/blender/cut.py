"""Cut a hard-surface model (vehicle, ship, aircraft, prop, or an unrigged figure) to a triangle budget,
keeping its parts, hierarchy and animations, and bake all its colour into one new texture.

Args (after --): GLB OUTDIR TARGET [TEXSIZE] [MODE] [DEPTH]
MODE "none" only takes the 'before' pictures (for models already within budget).
MODE "parts" (default) cuts each part separately and keeps parts, hierarchy and animations.
MODE "rewrap" wraps the whole model in one new surface (a voxel remesh, its voxels the model's size / 2^DEPTH, DEPTH
defaulting to 9; REWRAP_SOLIDIFY first thickens thin sheets by that fraction of its size), cuts that,
and bakes from all the original parts: for models with too many parts to cut each one far enough.
REWRAP_CLOSE wraps it instead in what reaches that fraction of its size round it, then pulls that back in by as much
(a closing, with OpenVDB): it seals slits and hollows up to twice that across, such as those along a piece split.py
cut off a figure, which an open surface's voxels would leave a sliver of, and keeps the rest of the shape to about a
voxel (a little thinner, smoothed). The reach should be at least one and a half voxels (check.py holds it to that, and
DEPTH to 8 or under, as the closing works in a box of voxels). A long thin piece wants a coarse DEPTH (7): cut far
down from fine voxels, a rifle's barrel collapses to a spike.
Writes OUTDIR/cut.glb, OUTDIR/colour.png, pictures before and after (OUTDIR/orig_*.png, cut_*.png) and OUTDIR/stats.json.
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

def closing(me, voxel, reach):
    """Replaces the mesh with its closing (see above). Returns what it did: the wrap's outward pieces it kept, the
    hollows inside them it left out (wrapped from within, so turned the other way), the pieces of the result, and its
    mean thickness (2 x volume / area). Pieces of the result thinner than a voxel are wisps the closing couldn't fill,
    left out. Fails where a piece wears away (fewer pieces come out than went in, counting a piece inside another's box
    as part of it, or the wisps are over a tenth of the surface) or the result is thinner than a voxel: a reach too
    short for the voxels, or a piece open wider than twice the reach, comes out a sheet of no thickness."""
    import numpy as np
    import openvdb as vdb
    bm = bmesh.new(); bm.from_mesh(me)
    P = np.array([v.co[:] for v in bm.verts], dtype=np.float32)
    T = np.array([[lp.vert.index for lp in tri] for tri in bm.calc_loop_triangles()], dtype=np.uint32)
    bm.free()
    xf = vdb.createLinearTransform(voxelSize=voxel)
    band = reach / voxel + 3
    # Every point within `reach`: the distance to the surface less `reach`, its sign ignored (an open surface has no
    # inside), meshed where it is 0.
    g = vdb.FloatGrid.createLevelSetFromPolygons(P, triangles=T, transform=xf, halfWidth=band)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    lo_ijk = (i0 - 2, j0 - 2, k0 - 2)
    A = np.empty((i1 - i0 + 5, j1 - j0 + 5, k1 - k0 + 5), np.float32)
    g.copyToArray(A, ijk=lo_ijk)
    d = vdb.FloatGrid(background=float(g.background - reach)); d.transform = xf
    d.copyFromArray(np.abs(A) - reach, ijk=lo_ijk, tolerance=0)
    pts, tris, quads = d.convertToPolygons(isovalue=0.0, adaptivity=0.0)
    tri_list = [np.asarray(f, dtype=np.int64) for f in (tris, quads) if len(f)]
    tri_list = [f if f.shape[1] == 3 else np.concatenate([f[:, [0, 1, 2]], f[:, [0, 2, 3]]]) for f in tri_list]
    F3 = np.concatenate(tri_list)
    # Its pieces: each turned outward, away from the surface, so the outer wraps enclose a volume and the hollows
    # inside them (wrapped from within) a negative one. The outer wrap with the largest reach sets which sign is out.
    lab = np.arange(len(pts))
    E = np.concatenate([F3[:, [0, 1]], F3[:, [1, 2]], F3[:, [2, 0]]])
    while True:
        m = np.minimum(lab[E[:, 0]], lab[E[:, 1]]); new = lab.copy()
        np.minimum.at(new, E[:, 0], m); np.minimum.at(new, E[:, 1], m); new = new[new]
        if (new == lab).all():
            break
        lab = new
    p64 = np.asarray(pts, dtype=np.float64)
    vol = np.einsum('ij,ij->i', p64[F3[:, 0]], np.cross(p64[F3[:, 1]], p64[F3[:, 2]])) / 6
    face_lab = lab[F3[:, 0]]
    ids = np.unique(face_lab)
    volume = {i: float(vol[face_lab == i].sum()) for i in ids}
    reach_of = {i: float(np.linalg.norm(np.ptp(p64[np.unique(F3[face_lab == i])], axis=0))) for i in ids}
    outer = max(ids, key=reach_of.get)
    out_sign = np.sign(volume[outer])
    kept_ids = [i for i in ids if np.sign(volume[i]) == out_sign]
    keep_face = np.isin(face_lab, kept_ids)
    box = {i: (p64[np.unique(F3[face_lab == i])].min(0), p64[np.unique(F3[face_lab == i])].max(0)) for i in kept_ids}
    apart = sum(1 for i in kept_ids if not any(j != i and (box[j][0] <= box[i][0]).all() and (box[i][1] <= box[j][1]).all()
                                                for j in kept_ids))
    # ...then pulled back in by `reach`: their own distance (now with an inside), meshed at -reach.
    s = vdb.FloatGrid.createLevelSetFromPolygons(np.asarray(pts, dtype=np.float32),
                                                 triangles=F3[keep_face].astype(np.uint32), transform=xf,
                                                 halfWidth=band)
    pts, tris, quads = s.convertToPolygons(isovalue=-reach, adaptivity=0.0)
    out_faces = [np.asarray(f, dtype=np.int64) for f in (tris, quads) if len(f)]
    lab = np.arange(len(pts))
    E = np.concatenate([f[:, [i, (i + 1) % f.shape[1]]] for f in out_faces for i in range(f.shape[1])]) if out_faces \
        else np.zeros((0, 2), dtype=np.int64)
    while len(E):
        m = np.minimum(lab[E[:, 0]], lab[E[:, 1]]); new = lab.copy()
        np.minimum.at(new, E[:, 0], m); np.minimum.at(new, E[:, 1], m); new = new[new]
        if (new == lab).all():
            break
        lab = new
    # Each piece of the result: one thinner than a voxel is a wisp the closing couldn't fill (a sheet worn to nothing,
    # or a scrap), left out.
    q = np.asarray(pts, dtype=np.float64)
    T3 = np.concatenate([f if f.shape[1] == 3 else np.concatenate([f[:, [0, 1, 2]], f[:, [0, 2, 3]]])
                         for f in out_faces]) if out_faces else np.zeros((0, 3), dtype=np.int64)
    tl = lab[T3[:, 0]]
    cr = np.cross(q[T3[:, 1]] - q[T3[:, 0]], q[T3[:, 2]] - q[T3[:, 0]])
    t_area = 0.5 * np.linalg.norm(cr, axis=1)
    t_vol = np.einsum('ij,ij->i', q[T3[:, 0]], np.cross(q[T3[:, 1]], q[T3[:, 2]])) / 6
    wisps, wisp_area = [], 0.0
    for i in np.unique(tl):
        A_i = float(t_area[tl == i].sum()); V_i = abs(float(t_vol[tl == i].sum()))
        if not A_i or 2 * V_i / A_i < voxel:
            wisps.append(i); wisp_area += A_i
    pieces = len(np.unique(tl)) - len(wisps)
    keep_out = [f[~np.isin(lab[f[:, 0]], wisps)] for f in out_faces]
    me.clear_geometry()
    me.from_pydata(q.tolist(), [], [list(f) for f in keep_out[0].tolist()] +
                   ([list(f) for f in keep_out[1].tolist()] if len(keep_out) > 1 else []))
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS'); bm.to_mesh(me); bm.free()
    me.materials.clear(); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    for _ in range(2):  # the voxels' steps smoothed away, which the cut would otherwise spend its triangles on
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    closed_volume, area = abs(bm.calc_volume(signed=True)), sum(f.calc_area() for f in bm.faces)
    bm.to_mesh(me); bm.free(); me.update()
    done = {"kept": len(kept_ids), "apart": apart, "hollows": len(ids) - len(kept_ids), "pieces": pieces,
            "wisps": len(wisps), "wisps' share": round(wisp_area / max(float(t_area.sum()), 1e-12), 4),
            "thickness": round(2 * closed_volume / area, 4) if area else 0.0, "voxel": round(voxel, 4)}
    print("CLOSE", json.dumps(done))
    if pieces < apart or done["wisps' share"] > 0.1:
        raise RuntimeError(f"Error: the closing wore a piece away ({done}): a longer reach, or finer voxels")
    if not area or done["thickness"] < voxel:
        raise RuntimeError(f"Error: the closing came out a sheet ({done}): a longer reach, or finer voxels")
    return done

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
    if os.environ.get("REWRAP_CLOSE"):
        stats["close"] = float(os.environ["REWRAP_CLOSE"])
        stats["closing"] = closing(lo.data, size / 2 ** depth, size * stats["close"])
    else:
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
    # found by testing on a part under a x100 parent: the bake measures the cage's
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
if os.environ.get("DROP_ANIMS"):  # animations that came with a model under other terms than its own are left out
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
