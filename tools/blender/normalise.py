"""Normalise cut models for civ.one's 3D map: front facing glTF +Z (Blender -Y), up +Y, base on the ground, centred,
real-world size in metres, JPEG textures. Static models are flattened into one mesh; models listed with "keep" keep
their hierarchy, skeleton and animations under a root node; "pose" freezes a rigged model in a clip's frame.

Args (after --): STAGE.json OUTDIR [key ...]
Each stage entry: src, measure ("height" or "along"), size (metres), turn (degrees about up, counter-clockwise from
above), optional mirror (true: its left and right swapped, across x, before it's turned; for a figure made the wrong
way round), keep (bool), pose ([action name, frame]), out (file name, default <key>.glb), and matrix (4x4, in
Blender's axes): the staging to use as it is instead of the one its own box gives, as split.py hands on for a body
whose piece reached past it.
Writes OUTDIR/<out> and OUTDIR/<key>.json (extent in glTF axes, triangles, sha256)."""
import bpy, sys, os, json, math, hashlib, mathutils

args = sys.argv[sys.argv.index("--") + 1:]
stage_path, outdir = args[0], args[1]
only = set(args[2:])
os.makedirs(outdir, exist_ok=True)
stage = json.load(open(stage_path))


def world_points(objs):
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in objs:
        e = o.evaluated_get(dg); m = e.to_mesh()
        pts += [o.matrix_world @ v.co for v in m.vertices]
        e.to_mesh_clear()
    return pts


for key, v in stage.items():
    if only and key not in only:
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=v["src"])
    junk = bpy.data.collections.get("glTF_not_exported")
    if junk:  # the importer's bone-display shapes
        for o in list(junk.objects):
            bpy.data.objects.remove(o)
    arms = [o for o in sc.objects if o.type == "ARMATURE"]
    if v.get("pose") and arms:
        name, frame = v["pose"]
        act = bpy.data.actions[name]
        ad = arms[0].animation_data or arms[0].animation_data_create()
        ad.action = act
        if getattr(ad, "action_slot", None) is None and getattr(act, "slots", None):
            ad.action_slot = act.slots[0]
        sc.frame_set(int(frame))
    else:
        sc.frame_set(0)
        for a in arms:
            a.data.pose_position = "REST" if not v.get("keep") else "POSE"
    bpy.context.view_layer.update()
    meshes = [o for o in sc.objects if o.type == "MESH"]

    if v.get("keep"):
        root = bpy.data.objects.new("root", None); sc.collection.objects.link(root)
        for o in list(sc.objects):
            if o is not root and o.parent is None:
                o.parent = root
        target = root
    else:
        dg = bpy.context.evaluated_depsgraph_get()
        flat = []
        for o in meshes:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
            n = bpy.data.objects.new(o.name, me); sc.collection.objects.link(n); flat.append(n)
        for o in list(sc.objects):
            if o not in flat:
                bpy.data.objects.remove(o)
        for a in list(bpy.data.actions):
            bpy.data.actions.remove(a)
        for x in sc.objects: x.select_set(False)
        for o in flat: o.select_set(True)
        bpy.context.view_layer.objects.active = flat[0]
        if len(flat) > 1:
            bpy.ops.object.join()
        target = bpy.context.view_layer.objects.active
        target.name = key
        meshes = [target]

    # turn about the vertical, then scale and place
    bpy.context.view_layer.update()
    pts = world_points(meshes)
    mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    centre = mathutils.Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    turn = mathutils.Matrix.Rotation(math.radians(v.get("turn", 0)), 4, "Z")
    if v.get("mirror"):  # its left and right swapped, across its middle, before it's turned
        turn = turn @ mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
    m1 = turn @ mathutils.Matrix.Translation(-centre)
    pts1 = [m1 @ p for p in pts]
    ext = {ax: max(p[i] for p in pts1) - min(p[i] for p in pts1) for i, ax in enumerate("xyz")}
    measured = ext["z"] if v["measure"] == "height" else ext["y"]
    s = v["size"] / measured
    m2 = mathutils.Matrix.Scale(s, 4) @ m1
    pts2 = [m2 @ p for p in pts]
    mn2 = mathutils.Vector([min(p[i] for p in pts2) for i in range(3)]); mx2 = mathutils.Vector([max(p[i] for p in pts2) for i in range(3)])
    draught = float(v.get("draught", 0))  # ships: the origin at the waterline, this far above the keel
    fix = mathutils.Matrix.Translation(mathutils.Vector((-(mn2.x + mx2.x) / 2, -(mn2.y + mx2.y) / 2, -mn2.z - draught)))
    M = fix @ m2
    if v.get("matrix"):  # staged as the original it was split from was (see split.py)
        M = mathutils.Matrix(v["matrix"]); s = M.to_3x3().median_scale
    if v.get("keep"):
        target.matrix_world = M @ target.matrix_world
    else:
        target.data.transform(M)
        if M.determinant() < 0:  # mirrored: its faces wound back the right way round, so they face out
            target.data.flip_normals()
        target.data.update()
    bpy.context.view_layer.update()
    pts3 = world_points(meshes)
    mn3 = mathutils.Vector([min(p[i] for p in pts3) for i in range(3)]); mx3 = mathutils.Vector([max(p[i] for p in pts3) for i in range(3)])
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)

    out = os.path.join(outdir, v.get("out", key + ".glb")); os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=bool(v.get("keep")),
                              export_image_format="JPEG", export_jpeg_quality=88, export_yup=True)
    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    # glTF axes: x = across, z = along (Blender -y), y = height (Blender z)
    info = {"file": os.path.basename(out), "sha256": sha, "triangles": tris, "bytes": os.path.getsize(out),
            "extent": {"across": [round(mn3.x, 3), round(mx3.x, 3)], "along": [round(-mx3.y, 3), round(-mn3.y, 3)],
                       "height": round(mx3.z, 3), **({"draught": round(-mn3.z, 3)} if draught else {})},
            "turn": v.get("turn", 0), "scaleApplied": s, "keep": bool(v.get("keep")), "pose": v.get("pose")}
    json.dump(info, open(os.path.join(outdir, key + ".json"), "w"), indent=1)
    print("NORMALISED", key, tris, info["extent"], round(os.path.getsize(out) / 1e6, 2), "MB")
