"""Put a prop with a normalised unit model (front -Y in Blender, feet at z=0, metres).

Args (after --): MODE BASE.glb PROP OUT.glb [options as key=value]
MODE hand: prop upright in the figure's right hand (its -X side). Options: height (prop height, m), grip (fraction up
  the prop held at, default 0.4), texture (image for an FBX prop with no texture). With `posed` (x,y,z in the file's
  axes: x across, y up, z the figure's front) and `stance` (the stance rule's file, which build.py gives), the prop is
  laid along its own length (its top the end nearer `top`, x,y,z in the prop file's axes, or else its narrow end, or
  its wide end with end=wide; turned `roll` degrees about its length from its fuller side facing the front) and turned
  so that, once stance.py has posed the figure and carried it with the right hand (the stance holds it whole on
  hand.R), its top points that way; or, where the stance gives the right hand's `fingers`, held in its fist: laid
  across the palm on the axis the fingers curl round, its top the end that, posed, points nearer that way (the
  stance's own turn of the hand points it); with ground=1 its grip is where its foot, so posed, rests 5 mm above
  the body's lowest point (as the figure stands, so the stance mustn't move the legs, which would stand him higher
  or lower).
MODE chute: prop centred above the figure. Options: width (prop's widest horizontal size, m), bottom (height of the
  prop's lowest point, m).
MODE hat: prop on the head. Options: width (brim width, m), sink (how far down over the head, m).
MODE bonehat: as hat, but BASE is rigged and the hat is parented to bone=NAME, posed by action=NAME at frame 0.
PROP may be .glb or .fbx (FBX read as data). Output keeps BASE's skeleton and animations in bonehat mode; otherwise all
meshes are joined into one. Prints placement for the record."""
import bpy, sys, os, math, json, mathutils, tempfile

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
# Only the prop's colour is kept, opaque, at no more than PROP_TEXTURE px: its other maps (normal, roughness, emission,
# alpha) are let go, so it exports as one JPEG, like the model it goes with.
PROP_TEXTURE = 512
for slot in P.material_slots:
    m = slot.material
    if not (m and m.use_nodes):
        continue
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        continue
    for link in list(nt.links):
        to_gltf_output = link.to_node.type == "GROUP" and link.to_node.node_tree and "glTF" in link.to_node.node_tree.name
        if (link.to_node == bsdf and link.to_socket.name != "Base Color") or to_gltf_output:  # occlusion goes there
            nt.links.remove(link)
    if bsdf.inputs.get("Alpha") is not None:
        bsdf.inputs["Alpha"].default_value = 1.0
    m.blend_method = "OPAQUE"
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    done = {}
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None:
            img = n.image
            if img.name in done:  # an image two nodes share is made once
                n.image = done[img.name]
                continue
            img.alpha_mode = "NONE"  # first: changing it reloads the image, which would undo a scale
            if max(img.size) > PROP_TEXTURE:
                f = PROP_TEXTURE / max(img.size)
                img.scale(max(1, round(img.size[0] * f)), max(1, round(img.size[1] * f)))
            new = img
            if img.packed_file is not None:  # the exporter copies packed bytes as they are: save what's there now
                path = os.path.join(tempfile.mkdtemp(prefix="prop-texture."), "texture.png")
                img.filepath_raw = path; img.file_format = "PNG"; img.save()
                new = bpy.data.images.load(path); new.alpha_mode = "NONE"; n.image = new
            done[img.name] = new
            if max(new.size) > PROP_TEXTURE:
                raise RuntimeError(f"Error: the prop's texture {new.name} is still {tuple(new.size)}")
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
if mode == "hand" and opt.get("posed"):
    hand_band = [p for p in base_pts if p.x < bmn.x + 0.07 * (bmx.z - bmn.z) and p.z > 0.25 * bmx.z]
    hand = sum(hand_band, mathutils.Vector()) / len(hand_band)
    hand.x += 0.02 * bmx.z
    # the prop along its own length, in the file's axes (glTF: x, y up, z front): its length up, its fuller side front
    G = mathutils.Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))  # Blender -> glTF
    vs = [G @ v.co for v in P.data.vertices]; c = sum(vs, mathutils.Vector()) / len(vs)
    cov = mathutils.Matrix(((0.0,) * 3,) * 3)
    for v in vs:
        d = v - c
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    e1 = mathutils.Vector((0.3, 1, 0.2)).normalized()
    for _ in range(100):
        e1 = (cov @ e1).normalized()
    t1 = [(v - c).dot(e1) for v in vs]; lo_, hi_ = min(t1), max(t1)
    def spread(sel):
        return sum(((v - c) - e1 * (v - c).dot(e1)).length for v in sel) / max(1, len(sel))
    if opt.get("top"):  # the end nearer this place (x,y,z in the prop file's own axes) is its top
        top = mathutils.Vector([float(x) for x in opt["top"].split(",")])
        if (top - c).dot(e1) < 0:
            e1 = -e1
    else:
        narrow_up = spread([v for v, t in zip(vs, t1) if t > hi_ - 0.15 * (hi_ - lo_)]) <= spread([v for v, t in zip(vs, t1) if t < lo_ + 0.15 * (hi_ - lo_)])
        if narrow_up != (opt.get("end", "narrow") == "narrow"):
            e1 = -e1
    rest = [(v - c) - e1 * (v - c).dot(e1) for v in vs]
    e2 = mathutils.Vector((1, 0, 0)) if abs(e1.x) < 0.9 else mathutils.Vector((0, 0, 1))
    e2 = (e2 - e1 * e2.dot(e1)).normalized()
    for _ in range(100):  # the widest way across the length
        acc = mathutils.Vector()
        for r in rest:
            acc += r * r.dot(e2)
        e2 = (acc - e1 * acc.dot(e1)).normalized()
    if sum(r.dot(e2) ** 3 for r in rest) < 0:  # towards its fuller side
        e2 = -e2
    e3 = e1.cross(e2)  # x
    B = mathutils.Matrix((e3, e1, e2))  # rows: prop -> canonical (x, length, front)
    roll = mathutils.Matrix.Rotation(math.radians(float(opt.get("roll", 0))), 3, "Y")
    canon = [roll @ (B @ (v - c)) for v in vs]
    lo_y, hi_y = min(v.y for v in canon), max(v.y for v in canon)
    s = float(opt["height"]) / (hi_y - lo_y)
    # the hand's turn once posed, from the stance (as stance.py turns a piece held whole on hand.R)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from skeleton import forward, read_fingers, read_rule
    st = json.load(open(opt["stance"]))
    J, skel = read_rule(st)
    rot, moved = forward(skel, st.get("aim", {}), st.get("twist", {}))
    Rh = mathutils.Matrix(rot["hand.R"].tolist())
    want = mathutils.Vector([float(x) for x in opt["posed"].split(",")]).normalized()
    F = mathutils.Vector((0, 1, 0)).rotation_difference(want).to_matrix()
    A = Rh.transposed() @ F  # canonical -> the A-posed figure, glTF axes
    fist = read_fingers(st, J).get("R")
    if fist is not None:  # held in a fist: across the palm, on the axis its fingers curl round, its top the end that,
        #  posed, points nearer `posed` (the stance turns the hand to point it there)
        way = mathutils.Vector(fist["across"].tolist())
        if (Rh @ way).dot(want) < 0:
            way = -way
        A = mathutils.Vector((0, 1, 0)).rotation_difference(way).to_matrix()
        want = (Rh @ way).normalized()
        F = Rh @ A
        hand = G.inverted() @ mathutils.Vector(fist["centre"].tolist())
    hand_g = G @ hand
    posed_hand = Rh @ (hand_g - mathutils.Vector(J["wrist.R"].tolist())) + mathutils.Vector(moved["hand.R"].tolist())
    if opt.get("ground") == "1":
        foot_gap = 0.005  # its lowest point just off the ground, so the figure is still stood on its own feet
        a0 = mathutils.Vector(((min(v.x for v in canon) + max(v.x for v in canon)) / 2, lo_y,
                               (min(v.z for v in canon) + max(v.z for v in canon)) / 2))
        low = min((F @ (cv - a0)).y for cv in canon)  # the lowest point, held by its foot's end and turned
        ground = bmn.z  # the body's own lowest point: the original it was split from may have reached lower
        grip = (posed_hand.y - ground - foot_gap + s * low) / (s * (hi_y - lo_y) * want.y)
        if not 0 < grip < 1:
            raise RuntimeError(f"Error: the hand, posed, is {posed_hand.y:.3f} up, so the prop can't rest on the ground")
    else:
        grip = float(opt.get("grip", 0.4))
    anchor = mathutils.Vector((0, lo_y + grip * (hi_y - lo_y), 0))
    canon_mid = [(min(v[i] for v in canon) + max(v[i] for v in canon)) / 2 for i in (0, 2)]
    anchor.x, anchor.z = canon_mid
    # one matrix, so the transform also turns the prop's normals
    G3 = G.to_3x3(); Gi3 = G3.inverted()
    lin = Gi3 @ A @ roll @ B @ G3 * s
    M = mathutils.Matrix.Translation(hand - Gi3 @ A @ (roll @ (B @ c) + anchor) * s) @ lin.to_4x4()
    placed = {"hand": [round(x, 3) for x in hand], "scale": round(s, 4), "grip": round(grip, 4),
              "posed hand": [round(x, 3) for x in posed_hand], "posed": [round(x, 3) for x in want]}
    if fist is not None:  # the prop's radius where it's held (by its points nearest the grip along it, as a shaft may
        #  have points only at its ends), beside the fist's: best that and half a finger
        near = sorted(canon, key=lambda v: abs(v.y - anchor.y))[:max(8, len(canon) // 20)]
        band = sorted(math.hypot(v.x - anchor.x, v.z - anchor.z) * s for v in near)
        placed.update({"fist": True, "fist radius": round(float(fist["radius"]), 4),
                       "radius at grip": round(band[len(band) // 2], 4)})
elif mode == "hand":
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
