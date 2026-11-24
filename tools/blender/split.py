"""split.py : splits a piece a figure holds or carries (a slung rifle, say) off it, where its original fuses the piece to
the body as one skin, so the piece can be put back as a prop of its own and move with a hand.

Args (after --): GLB BODY.glb PIECE.glb RULE.json. Writes the body without the piece, in the original's frame, and the
piece, in the staged frame below, each with the original's material. Blender is started with factory settings and scripts in files turned off, and
reads the GLB only as data.

The rule (a model's `split` in the roster, with its `stage`) gives `chains` of stations along the piece, in the frame
stance.py's joints use: the original as normalise.py would turn, size and ground it (metres, x across with the figure's
left at +x, y up, facing +z). Each station is [place, across, deep, gap]:
- `place`, [x, y, z]: a point on the piece's middle line;
- `across` and `deep`: how far the piece reaches from that line, across it and along `depth` (default [0, 0, 1], the
  figure's front), as the half-widths of an ellipse;
- `gap`: inside the ellipse, a face further than this towards the figure's middle (its upright line through x = 0,
  z = 0) that faces away from the middle is the body's skin, under the piece, and stays with the body.
Between stations the ellipse's middle and sizes go in a straight line; it reaches 1 cm past a chain's ends.

`drop` gives chains the same way for what goes with neither: where the original has made a piece twice over, say, or a
sling left hanging once its rifle has gone. The piece's chains come first where they overlap.

Whatever of the body the cut leaves unconnected (points joined by place, as originals split them along texture seams)
goes too: scraps of the piece left behind. Each connected piece of the original keeps its largest remaining part; a
part the cut didn't touch stays as it was.

The holes the cut leaves in the body are closed, the closing faces coloured with the average colour of the faces round
their edges (a material of their own, `split-fill`), so it has no gap where the piece lay against it. The piece's are
left open: a cut along a piece's length, closed, fills across its hollows (a sheet across a rifle's stock).

With `mirror` true, the piece is given its mirror image as well, across its middle: the plane across its thinnest
reach, through the middle of each slice along it (a running median, so a stray scrap doesn't bend it). Where the
original made only the outer half of the piece (a rifle's stock lying flat on a back), the two halves interlock into a
whole; where it made all of it, the copy lies on the piece. Either way, cut it with `rewrap` and `close` (see cut.py),
which wraps both in one closed surface and seals the slits left along the edge that lay against the body; without
`mirror`, cut it with `parts`, which keeps its open shape as it is.

Prints SPLIT with the counts, for the record."""
import bmesh
import bpy
import json
import math
import os
import sys

import mathutils
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
src, body_out, piece_out, rule_path = a[:4]
rule = json.load(open(rule_path))
stage, chains = rule['stage'], rule['chains']
depth = np.array(rule.get('depth', [0, 0, 1]), dtype=float)
depth /= np.linalg.norm(depth)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
junk = bpy.data.collections.get('glTF_not_exported')
if junk:
    for o in list(junk.objects):
        bpy.data.objects.remove(o)
meshes = [o for o in sc.objects if o.type == 'MESH']
if not meshes:
    raise RuntimeError('Error: the original has no mesh')
dg = bpy.context.evaluated_depsgraph_get()
flat = []
for o in meshes:
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
    n = bpy.data.objects.new(o.name, me); sc.collection.objects.link(n); flat.append(n)
for o in list(sc.objects):
    if o not in flat:
        bpy.data.objects.remove(o)
for x in sc.objects: x.select_set(False)
for o in flat: o.select_set(True)
bpy.context.view_layer.objects.active = flat[0]
if len(flat) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
me = obj.data


def arr(seq, attr, n, k, dtype=float):
    out = np.empty(n * k, dtype=dtype); seq.foreach_get(attr, out)
    return out.reshape(n, k) if k > 1 else out


V = arr(me.vertices, 'co', len(me.vertices), 3)
nf = len(me.polygons)
centre_b = arr(me.polygons, 'center', nf, 3)
normal_b = arr(me.polygons, 'normal', nf, 3)

# The staged frame, as normalise.py makes it: centred on the box across and along, grounded, turned, sized, centred again.
mn, mx = V.min(0), V.max(0)
c = np.array([(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]])
t = math.radians(stage.get('turn', 0))
R = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
P1 = (V - c) @ R.T
ext = P1.max(0) - P1.min(0)
s = stage['size'] / (ext[2] if stage['measure'] == 'height' else ext[1])
P2 = P1 * s
fix = -np.array([(P2[:, 0].min() + P2[:, 0].max()) / 2, (P2[:, 1].min() + P2[:, 1].max()) / 2, P2[:, 2].min()])


def staged(p, normal=False):
    """Blender points (or normals) to the staged frame's glTF axes."""
    q = p @ R.T if normal else ((p - c) @ R.T) * s + fix
    return np.stack([q[:, 0], q[:, 2], -q[:, 1]], 1)


F = staged(centre_b)
N = staged(normal_b, normal=True)

# Faces in a chain's ellipses, less the body's skin under them.
def picked_by(chains):
    pick = np.zeros(nf, dtype=bool)
    for chain in chains:
        st = [(np.array(p, dtype=float), float(w), float(d), float(g)) for p, w, d, g in chain]
        best = np.full(nf, np.inf)
        skin = np.zeros(nf, dtype=bool)
        for i in range(len(st) - 1):
            (pa, wa, da, ga), (pb, wb, db, gb) = st[i], st[i + 1]
            ab = pb - pa; L = np.linalg.norm(ab); ax = ab / L
            u = (F - pa) @ ax / L
            over = np.where(u < 0, -u * L, np.where(u > 1, (u - 1) * L, 0.0))
            reach_ok = (over <= 0.01) & ((over == 0) | ((u < 0) & (i == 0)) | ((u > 1) & (i == len(st) - 2)))
            u = np.clip(u, 0, 1)
            q = pa + np.outer(u, ab)
            w = wa + (wb - wa) * u; d = da + (db - da) * u; g = ga + (gb - ga) * u
            dd = depth - ax * depth.dot(ax); dd /= np.linalg.norm(dd); ww = np.cross(ax, dd)
            off = F - q
            e = ((off @ ww) / w) ** 2 + ((off @ dd) / d) ** 2
            e = np.where(reach_ok, e, np.inf)
            tb = -q * np.array([1, 0, 1]); tb -= np.outer(tb @ ax, ax)
            tl = np.linalg.norm(tb, axis=1); tb = tb / np.maximum(tl, 1e-9)[:, None]
            sk = (tl > 1e-6) & (np.einsum('ij,ij->i', off, tb) > g) & (np.einsum('ij,ij->i', N, tb) < -0.2)
            better = e < best
            best = np.where(better, e, best); skin = np.where(better, sk, skin)
        pick |= (best <= 1) & ~skin
    return pick


pick = picked_by(chains)
drop = picked_by(rule.get('drop', [])) & ~pick
picked = int(pick.sum())
if picked == 0 or picked == nf:
    raise RuntimeError(f'Error: the chains pick {picked} of the {nf} faces')

# Points joined by place; each connected piece of the original keeps its largest part left by the cut.
key = np.round(V / (np.linalg.norm(mx - mn) * 1e-6)).astype(np.int64)
_, weld = np.unique(key, axis=0, return_inverse=True); weld = weld.ravel()
loop_v = arr(me.loops, 'vertex_index', len(me.loops), 1, dtype=np.int64)
loop_start = arr(me.polygons, 'loop_start', nf, 1, dtype=np.int64)
loop_total = arr(me.polygons, 'loop_total', nf, 1, dtype=np.int64)


def components(faces):
    """A label for each of these faces' connected piece (joined through shared points)."""
    lab = np.arange(weld.max() + 1)
    edges = []
    for k in range(int(loop_total[faces].max()) - 1 if len(faces) else 0):
        has = loop_total[faces] > k + 1
        f = faces[has]
        edges.append(np.stack([weld[loop_v[loop_start[f] + k]], weld[loop_v[loop_start[f] + k + 1]]], 1))
    E = np.concatenate(edges) if edges else np.zeros((0, 2), dtype=np.int64)
    while len(E):
        m = np.minimum(lab[E[:, 0]], lab[E[:, 1]]); new = lab.copy()
        np.minimum.at(new, E[:, 0], m); np.minimum.at(new, E[:, 1], m); new = new[new]
        if (new == lab).all():
            break
        lab = new
    return lab[weld[loop_v[loop_start[faces]]]]


every = np.arange(nf)
whole = components(every)
kept = np.where(~pick & ~drop)[0]
part = components(kept)
debris = np.zeros(nf, dtype=bool)
for w in np.unique(whole[pick | drop]):  # the original's pieces the cut touched
    mine = whole[kept] == w
    if not mine.any():
        continue
    ids, counts = np.unique(part[mine], return_counts=True)
    largest = ids[np.argmax(counts)]
    debris[kept[mine & (part != largest)]] = True
drop |= debris

# The colour texture, to colour the closing faces.
img = None
for m in me.materials:
    if m and m.use_nodes:
        bsdf = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf and bsdf.inputs['Base Color'].is_linked:
            node = bsdf.inputs['Base Color'].links[0].from_node
            while node.type != 'TEX_IMAGE' and any(i.is_linked for i in node.inputs):
                node = next(i for i in node.inputs if i.is_linked).links[0].from_node
            if node.type == 'TEX_IMAGE':
                img = node.image
                break
pixels = None
if img is not None:
    W, H = img.size
    pixels = np.empty(W * H * 4, dtype=np.float32); img.pixels.foreach_get(pixels); pixels = pixels.reshape(H, W, 4)


def close_holes(ob, name):
    """Joins the points by place, closes each hole with faces of their own material, and returns how many holes."""
    m = ob.data
    bm = bmesh.new(); bm.from_mesh(m)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=float(np.linalg.norm(mx - mn)) * 1e-6)
    edge_ring = [e for e in bm.edges if e.is_boundary]
    colour = (0.5, 0.5, 0.5, 1.0)
    uv = bm.loops.layers.uv.active
    if pixels is not None and uv is not None and edge_ring:
        samples = []
        for f in {f for e in edge_ring for f in e.link_faces}:  # in each face along the edge, not at its corners
            x, y = sum((lp[uv].uv for lp in f.loops), mathutils.Vector((0, 0))) / len(f.loops)
            samples.append(pixels[min(H - 1, max(0, int((y % 1) * H))), min(W - 1, max(0, int((x % 1) * W))), :3])
        mean = np.mean(samples, axis=0)
        if img.colorspace_settings.name == 'sRGB' and not img.is_float:  # stored as sRGB; the colour wants linear
            mean = np.where(mean <= 0.04045, mean / 12.92, ((mean + 0.055) / 1.055) ** 2.4)
        colour = (*[float(v) for v in mean], 1.0)
    before = set(bm.faces)
    holes = bmesh.ops.holes_fill(bm, edges=edge_ring, sides=0)['faces']
    new = [f for f in bm.faces if f not in before]
    if new:
        bmesh.ops.triangulate(bm, faces=new, quad_method='BEAUTY', ngon_method='BEAUTY')
        new = [f for f in bm.faces if f not in before]
        fill = bpy.data.materials.new('split-fill'); fill.use_nodes = True
        bsdf = next(n for n in fill.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = colour
        bsdf.inputs['Roughness'].default_value = 0.8
        m.materials.append(fill)
        for f in new:
            f.material_index = len(m.materials) - 1
            f.smooth = False
    bm.to_mesh(m); bm.free(); m.update()
    return len(holes), len(new), colour


def keep_only(ob, mask):
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not mask[f.index]], context='FACES')
    bm.to_mesh(ob.data); bm.free(); ob.data.update()


def mirror(ob):
    """Adds the piece's mirror image across its middle (see above) and returns that middle, every 10 cm along it."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    P = np.array([v.co[:] for v in bm.verts])
    T = np.array([[lp.vert.index for lp in tri] for tri in bm.calc_loop_triangles()], dtype=np.int64)
    fc = P[T].mean(1)
    fa = 0.5 * np.linalg.norm(np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]), axis=1)
    mid = (fc * fa[:, None]).sum(0) / fa.sum()
    _, axes = np.linalg.eigh(np.cov((fc - mid).T, aweights=fa))
    along, across = axes[:, 2], axes[:, 0]
    ft, fu = (fc - mid) @ along, (fc - mid) @ across

    def weighted(x, w, q):
        o = np.argsort(x); cw = np.cumsum(w[o])
        return x[o][min(len(x) - 1, int(np.searchsorted(cw, q * cw[-1])))]

    step = 0.01  # slices 2 cm thick every 1 cm, smoothed over 9 cm
    ts = np.arange(ft.min(), ft.max() + step, step)
    middles = np.full(len(ts), np.nan)
    for i, t_ in enumerate(ts):
        m = np.abs(ft - t_) < step
        if m.sum() > 3:
            middles[i] = (weighted(fu[m], fa[m], 0.03) + weighted(fu[m], fa[m], 0.97)) / 2
    ok = ~np.isnan(middles)
    middles = np.interp(ts, ts[ok], middles[ok])
    middles = np.array([np.median(middles[max(0, i - 4):i + 5]) for i in range(len(middles))])
    old = list(bm.verts)
    dup = bmesh.ops.duplicate(bm, geom=old + list(bm.edges) + list(bm.faces))
    for v in old:
        q = np.array(v.co[:]); t_, u_ = (q - mid) @ along, (q - mid) @ across
        dup['vert_map'][v].co = mathutils.Vector(q + 2 * (np.interp(t_, ts, middles) - u_) * across)
    bmesh.ops.reverse_faces(bm, faces=[f for f in dup['geom'] if isinstance(f, bmesh.types.BMFace)])
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return [round(float(x), 4) for x in middles[::10]]


piece = obj.copy(); piece.data = me.copy(); piece.name = 'piece'; sc.collection.objects.link(piece)
obj.name = 'body'
keep_only(obj, ~pick & ~drop)
keep_only(piece, pick)
report = {'faces': nf, 'picked': int(pick.sum()), 'dropped': int(drop.sum()), 'debris': int(debris.sum())}
for ob, name, out in ((obj, 'body', body_out), (piece, 'piece', piece_out)):
    if name == 'body':
        holes, faces, colour = close_holes(ob, name)
        report[name] = {'holes': holes, 'closing faces': faces, 'colour': [round(x, 3) for x in colour[:3]]}
    else:  # in the staged frame, where the rule (and a prop's `top`) gives places
        Mb = np.eye(4); Mb[:3, :3] = R * s; Mb[:3, 3] = fix - (R @ c) * s
        ob.data.transform(mathutils.Matrix(Mb.tolist())); ob.data.update()
        if rule.get('mirror'):
            report['mirror'] = mirror(ob)
    for x in sc.objects: x.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_yup=True,
                              export_image_format='AUTO', export_animations=False)
print('SPLIT', json.dumps(report))
