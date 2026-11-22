"""Put a prop with a normalised unit model (front -Y in Blender, feet at z=0, metres).

Args (after --): MODE BASE.glb PROP OUT.glb [options as key=value]
MODE hand: prop upright in the figure's right hand (its -X side). Options: height (prop height, m), grip (fraction up
  the prop held at, default 0.4), texture (image for an FBX prop with no texture).
MODE chute: prop centred above the figure. Options: width (prop's widest horizontal size, m), bottom (height of the
  prop's lowest point, m).
MODE hat: prop on the head. Options: width (brim width, m), sink (how far down over the head, m).
MODE bonehat: as hat, but BASE is rigged and the hat is parented to bone=NAME, posed by action=NAME at frame 0.
PROP may be .glb or .fbx (FBX read as data). Output keeps BASE's skeleton and animations in bonehat mode; otherwise all
meshes are joined into one. Prints placement for the record."""
import bpy, sys, os, math, json, mathutils

a = sys.argv[sys.argv.index("--") + 1:]
mode, base, prop, out = a[:4]
opt = dict(x.split("=", 1) for x in a[4:])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def imp(path):
    before = set(sc.objects)
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    junk = bpy.data.collections.get("glTF_not_exported")
    if junk:
        for o in list(junk.objects):
            bpy.data.objects.remove(o)
    return [o for o in sc.objects if o not in before]


def pts_of(objs):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ps = []
    for o in objs:
        if o.type != "MESH": continue
        e = o.evaluated_get(dg); m = e.to_mesh(); ps += [o.matrix_world @ v.co for v in m.vertices]; e.to_mesh_clear()
    return ps


def bounds(ps):
    return (mathutils.Vector([min(p[i] for p in ps) for i in range(3)]), mathutils.Vector([max(p[i] for p in ps) for i in range(3)]))


base_objs = imp(base)
arm = next((o for o in base_objs if o.type == "ARMATURE"), None)
if mode == "bonehat" and arm:
    act = bpy.data.actions[opt["action"]]
    ad = arm.animation_data or arm.animation_data_create(); ad.action = act
    if getattr(ad, "action_slot", None) is None and getattr(act, "slots", None): ad.action_slot = act.slots[0]
    sc.frame_set(0)
base_pts = pts_of(base_objs); bmn, bmx = bounds(base_pts)

prop_objs = imp(prop)
prop_meshes = [o for o in prop_objs if o.type == "MESH"]
# flatten the prop into one world-space mesh
dg = bpy.context.evaluated_depsgraph_get()
pm = []
for o in prop_meshes:
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
    n = bpy.data.objects.new("prop_" + o.name, me); sc.collection.objects.link(n); pm.append(n)
for o in prop_objs:
    bpy.data.objects.remove(o)
for x in sc.objects: x.select_set(False)
for o in pm: o.select_set(True)
bpy.context.view_layer.objects.active = pm[0]
if len(pm) > 1: bpy.ops.object.join()
P = bpy.context.view_layer.objects.active; P.name = "prop"
while len(P.data.uv_layers) > 1:  # keep only the texture's own UV layer
    P.data.uv_layers.remove(P.data.uv_layers[len(P.data.uv_layers) - 1])
for slot in P.material_slots:  # plain specular, so the export names no extension
    m = slot.material
    if m and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                for name, val in (("Specular IOR Level", 0.5), ("IOR", 1.5)):
                    if n.inputs.get(name) is not None and not n.inputs[name].is_linked: n.inputs[name].default_value = val
                if n.inputs.get("Specular Tint") is not None and not n.inputs["Specular Tint"].is_linked:
                    n.inputs["Specular Tint"].default_value = (1, 1, 1, 1)
if opt.get("tris"):  # trim the prop
    n = sum(len(f.vertices) - 2 for f in P.data.polygons)
    if n > int(opt["tris"]):
        dm = P.modifiers.new("dec", "DECIMATE"); dm.ratio = int(opt["tris"]) / n; dm.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=dm.name)
if opt.get("texture"):  # FBX props whose texture path didn't resolve
    img = bpy.data.images.load(opt["texture"])
    for slot in P.material_slots:
        m = slot.material
        if not m: continue
        m.use_nodes = True; nt = m.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None) or nt.nodes.new("ShaderNodeTexImage")
        tex.image = img; nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
if opt.get("upright") == "pca":  # stand a tilted prop along its long axis, wider (burning) end up
    vs = [v.co.copy() for v in P.data.vertices]; c = sum(vs, mathutils.Vector()) / len(vs)
    cov = mathutils.Matrix(((0.0,) * 3,) * 3)
    for v in vs:
        d = v - c
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    ax = mathutils.Vector((1, 1, 1)).normalized()
    for _ in range(60):
        ax = (cov @ ax).normalized()
    R = ax.rotation_difference(mathutils.Vector((0, 0, 1))).to_matrix().to_4x4()
    P.data.transform(R @ mathutils.Matrix.Translation(-c)); P.data.update()
    zs = [v.co.z for v in P.data.vertices]; z0, z1 = min(zs), max(zs); h = z1 - z0
    def spread(sel):
        return sum(math.hypot(v.co.x, v.co.y) for v in sel) / max(1, len(sel))
    lo = [v for v in P.data.vertices if v.co.z < z0 + 0.15 * h]; hi = [v for v in P.data.vertices if v.co.z > z1 - 0.15 * h]
    if spread(lo) > spread(hi):
        P.data.transform(mathutils.Matrix.Rotation(math.pi, 4, "X")); P.data.update()
ppts = [P.matrix_world @ v.co for v in P.data.vertices]; pmn, pmx = bounds(ppts)
pd = pmx - pmn
placed = {}
if mode == "hand":
    s = float(opt["height"]) / pd.z
    grip = float(opt.get("grip", 0.4))
    hand_band = [p for p in base_pts if p.x < bmn.x + 0.07 * (bmx.z - bmn.z) and p.z > 0.25 * bmx.z]
    hand = sum(hand_band, mathutils.Vector()) / len(hand_band)
    hand.x += 0.02 * bmx.z
    anchor = mathutils.Vector(((pmn.x + pmx.x) / 2, (pmn.y + pmx.y) / 2, pmn.z + grip * pd.z))
    M = mathutils.Matrix.Translation(hand) @ mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation(-anchor)
    placed = {"hand": [round(x, 3) for x in hand], "scale": s}
elif mode == "chute":
    s = float(opt["width"]) / max(pd.x, pd.y)
    anchor = mathutils.Vector(((pmn.x + pmx.x) / 2, (pmn.y + pmx.y) / 2, pmn.z))
    to = mathutils.Vector(((bmn.x + bmx.x) / 2, (bmn.y + bmx.y) / 2, float(opt["bottom"])))
    M = mathutils.Matrix.Translation(to) @ mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation(-anchor)
    placed = {"bottom": float(opt["bottom"]), "scale": s}
else:  # hat / bonehat
    s = float(opt["width"]) / max(pd.x, pd.y)
    top = bmx.z
    head = [p for p in base_pts if p.z > top - 0.12 * (bmx.z - bmn.z)]
    hc = sum(head, mathutils.Vector()) / len(head)
    anchor = mathutils.Vector(((pmn.x + pmx.x) / 2, (pmn.y + pmx.y) / 2, pmn.z))
    to = mathutils.Vector((hc.x, hc.y, top - float(opt.get("sink", 0.05))))
    M = mathutils.Matrix.Translation(to) @ mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation(-anchor)
    placed = {"head": [round(x, 3) for x in to], "scale": s}
P.data.transform(M); P.data.update()

if mode == "bonehat" and arm:
    for x in sc.objects: x.select_set(False)
    P.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    arm.data.bones.active = arm.data.bones[opt["bone"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for x in sc.objects: x.select_set(False)
    P.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.object.parent_set(type="BONE", keep_transform=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    export_anims = True
else:
    meshes = [o for o in sc.objects if o.type == "MESH"]
    for x in sc.objects: x.select_set(False)
    for o in meshes: o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    for o in list(sc.objects):
        if o.type != "MESH": bpy.data.objects.remove(o)
    export_anims = False
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=export_anims,
                          export_image_format="JPEG", export_jpeg_quality=88)
print("ASSEMBLED", mode, out, json.dumps(placed))
