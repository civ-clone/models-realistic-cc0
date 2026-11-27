"""split.py : splits a piece a figure holds or carries (a slung rifle, say) off it, where its original fuses the piece to
the body as one skin, so the piece can be put back as a prop of its own and move with a hand; or only drops something
fused to it that the cut can't draw.

Args (after --): GLB BODY.glb PIECE.glb RULE.json STAGING.json. Writes the body without the piece, in the original's
frame, and the piece, in the staged frame below, each with the original's material; and the staging (the matrix taking
the original's frame to the staged one), which build.py hands normalise.py for the body. Staged by its own box, the
body would move wherever the piece reached past it, away from the stance's joints, fitted to the original. Blender is
started with factory settings and scripts in files turned off, and reads the GLB only as data.

The rule (a model's `split` in the roster, with its `stage`) gives `chains` of stations along the piece, in the frame
stance.py's joints use: the original as normalise.py would mirror (first), turn, size and ground it (metres, x across
with the figure's left at +x, y up, facing +z). Each station is [place, across, deep, gap]:
- `place`, [x, y, z]: a point on the piece's middle line;
- `across` and `deep`: how far the piece reaches from that line, across it and along `depth` (default [0, 0, 1], the
  figure's front), as the half-widths of an ellipse;
- `gap`: inside the ellipse, a face further than this towards the figure's middle (its upright line through x = 0,
  z = 0) that faces away from the middle is the body's skin, under the piece, and stays with the body.
Between stations the ellipse's middle and sizes go in a straight line, no stretch within 10° of `depth`; each stretch
reaches 1 cm past its ends, so a chain's ends and the outside of its bends are covered (check.py holds a bend to
what that covers).

`drop` gives chains the same way for what goes with neither: where the original has made a piece twice over, say, or a
sling left hanging once its rifle has gone. The piece's chains come first where they overlap. A rule may have only
`drop`, for something the cut can't draw (the Explorer's coil of rope): then nothing is split off, no PIECE is written,
and build.py stages the body by its own box, as it would without a split (STAGING is written all the same). So it fails
if what it drops moves that box by more than a millimetre (something reaching past the rest of the figure, below his
boots, say): the stance's joints were fitted to the box as it was.

Whatever of the body the cut leaves unconnected (points joined by place, as originals split them along texture seams)
goes too: scraps of the piece left behind. Each connected piece of the original keeps its largest remaining part; a
part the cut didn't touch stays as it was.

The holes the cut leaves in the body are closed, each hole's closing faces coloured with the average colour of the
faces round its edges (a material of their own, `split-fill`; the colours come from the first textured material's
image), so it has no gap where the piece lay against it. Each is zipped from side to side, so a long hole curving
round a leg doesn't fold (though one wrapping most of the way round a limb may dip inside it). A ring of open edges
that touches itself is closed as the holes it is, each on its own. Faces the cut leaves as teeth along a rim, hanging
by a corner or bridging a hole are dropped first. Only the cut's own edges (between a face kept and one taken or
dropped) are closed: holes the original had, and the outlines of two-layer sheets, are left as they were, unless the
cut ran into one, when it's closed with the cut's; faces lying on another's points (a two-layer sheet) are left out of
the weld, so their layers aren't merged (their points are left out of the weld where only such faces use them). It
fails if any edge the cut opened is left open, or Blender's own check finds a face it won't keep. The piece's holes
are left open: a cut along a piece's length, closed, fills across its hollows (a sheet across a rifle's stock).

With `mirror` true, the piece is given its mirror image as well, across its middle: the plane across its thinnest
reach, through the middle of each slice along it (a running median, so a stray scrap doesn't bend it). Where the
original made the piece's sides but not the face it lay on (a rifle's stock flat on a back, its near face fused), the
two interlock into a whole as wide across as the sides reach; where it made all of it, the copy lies on the piece. (A
piece cut away down its middle comes out as thick as that half.) Either way, cut it with `rewrap` and `close` (see
cut.py), which wraps both in one closed surface and seals the slits left along the edge that lay against the body;
without `mirror`, cut it with `parts`, which keeps its open shape as it is.

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
src, body_out, piece_out, rule_path, staging_out = a[:5]
rule = json.load(open(rule_path))
stage, chains = rule['stage'], rule.get('chains', [])
depth = np.array(rule.get('depth', [0, 0, 1]), dtype=float)
depth /= np.linalg.norm(depth)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
junk = bpy.data.collections.get('glTF_not_exported')
if junk:
    for o in list(junk.objects):
        bpy.data.objects.remove(o)
for arm in (o for o in sc.objects if o.type == 'ARMATURE'):
    arm.data.pose_position = 'REST'  # as cut.py cuts a skinned figure, in its bind shape
bpy.context.view_layer.update()
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
if stage.get('mirror'):  # its left and right swapped before it's turned, as normalise.py does
    R = R @ np.diag([-1.0, 1.0, 1.0])
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
            reach_ok = over <= 0.01  # past its ends too, so the outside of a bend is covered
            u = np.clip(u, 0, 1)
            q = pa + np.outer(u, ab)
            w = wa + (wb - wa) * u; d = da + (db - da) * u; g = ga + (gb - ga) * u
            dd = depth - ax * depth.dot(ax)
            if np.linalg.norm(dd) < math.sin(math.radians(10)):
                raise RuntimeError(f'Error: the stretch from {pa.tolist()} runs within 10° of depth')
            dd /= np.linalg.norm(dd); ww = np.cross(ax, dd)
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
if chains and (picked == 0 or picked == nf):
    raise RuntimeError(f'Error: the chains pick {picked} of the {nf} faces')
if not chains and not drop.any():
    raise RuntimeError('Error: a rule with only drop should drop something')
if (pick | drop).all():
    raise RuntimeError(f'Error: the rule takes all {nf} faces, leaving no body')

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
sides, side_face = [], []
for k in range(int(loop_total.max())):  # each face's k-th side, where it has one
    has = loop_total > k
    f0, n = loop_start[has], loop_total[has]
    sides.append(np.stack([weld[loop_v[f0 + k]], weld[loop_v[f0 + (k + 1) % n]]], 1))
    side_face.append(np.where(has)[0])
sides, side_face = np.sort(np.concatenate(sides), axis=1), np.concatenate(side_face)
n_weld = int(weld.max()) + 1
side_key = sides[:, 0] * n_weld + sides[:, 1]  # an edge, by its welded ends
key_weld = {tuple(k): int(w) for k, w in zip(key.tolist(), weld.tolist())}
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
# The cut's own edges: those between a face kept and a face taken or dropped. Only these, and those of faces peeled
# off along them, are closed; any other open edge (an original's hole, a two-layer sheet's outline) is left.
removed_face = pick | drop
cut_keys = set(np.intersect1d(side_key[~removed_face[side_face]], side_key[removed_face[side_face]]).tolist())

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


def hole_cycles(bm):
    """Each hole's edge as a cycle of points, in the order a face closing it runs (against most of the faces round
    it). A ring that touches itself (holes meeting at a point, or one pinched there) comes apart into cycles that
    don't: found by turning round each point through the faces, whichever way they're wound, to the next open edge,
    then cut where a cycle comes back to a point. A walk that doesn't come back to its start is left out (and the
    check after the closing fails on its open edges)."""
    cycles, used = [], set()
    for e0 in bm.edges:
        if not e0.is_boundary or e0 in used:
            continue
        lp0 = e0.link_loops[0]  # runs a -> b in its face; the hole runs b -> a
        cycle, e, v, ok = [lp0.link_loop_next.vert], e0, lp0.vert, False
        for _ in range(len(bm.edges)):
            used.add(e)
            f, cur, nxt = e.link_faces[0], e, None
            for _ in range(len(v.link_edges) + 1):  # round v through the faces, from e to the next open edge
                other = next((x for x in f.edges if x is not cur and v in x.verts), None)
                if other is None:
                    break
                if other.is_boundary:
                    nxt = other
                    break
                across = [g for g in other.link_faces if g is not f]
                if len(across) != 1:
                    break  # an edge of more than two faces: no clear way round
                f, cur = across[0], other
            if nxt is None:
                break
            if nxt is e0:
                ok = True
                break
            cycle.append(v)
            e, v = nxt, nxt.other_vert(v)
        if not ok:
            continue
        stack, at = [], {}  # a hole pinched at a point passes it twice: its lobes, each a cycle of its own
        for v in cycle:
            if v in at:
                i = at[v]
                cycles.append(stack[i:])
                for w in stack[i + 1:]:
                    del at[w]
                del stack[i + 1:]
            else:
                at[v] = len(stack); stack.append(v)
        cycles.append(stack)
    out = []
    for c in cycles:
        if len(c) < 3:
            continue
        votes = 0  # which way the faces round it run it, by most of them (one face wound the other way can't turn it)
        for i in range(len(c)):
            e = bm.edges.get((c[i], c[(i + 1) % len(c)]))
            if e is not None and e.link_loops:
                votes += 1 if e.link_loops[0].vert is c[(i + 1) % len(c)] else -1
        out.append(c[::-1] if votes < 0 else c)
    return out


def zip_up(bm, cycle):
    """Closes a hole by zipping its two sides together: the cycle split at its two ends (the points furthest apart
    along its length), and triangles laid across from side to side, each taking the shorter way on. Unlike one face cut
    into triangles in a plane, it can't fold over where a long hole curves round a leg. Returns the new faces, or None
    (and makes none) where one of them is there already."""
    P = np.array([v.co[:] for v in cycle])
    w, U = np.linalg.eigh(np.cov((P - P.mean(0)).T))
    t = (P - P.mean(0)) @ U[:, 2]
    i0, i1 = int(np.argmin(t)), int(np.argmax(t))
    n = len(cycle)
    A = [cycle[(i0 + k) % n] for k in range((i1 - i0) % n + 1)]  # i0 to i1, the way the cycle runs
    B = [cycle[(i0 - k) % n] for k in range((i0 - i1) % n + 1)]  # i0 to i1 the other way
    tris, a, b = [], 0, 0
    while a < len(A) - 1 or b < len(B) - 1:
        go_a = b == len(B) - 1 or (a < len(A) - 1 and (A[a + 1].co - B[b].co).length <= (A[a].co - B[b + 1].co).length)
        if a < len(A) - 1 and b < len(B) - 1:  # not a flat triangle where the other way gives a real one
            def flat(p, q, r):  # next to nothing for its size, in whatever units the original has
                return mathutils.geometry.area_tri(p, q, r) < 1e-9 * max((p - q).length, (q - r).length,
                                                                          (r - p).length) ** 2
            fa_, fb_ = flat(A[a].co, A[a + 1].co, B[b].co), flat(B[b + 1].co, B[b].co, A[a].co)
            if (fa_ if go_a else fb_) and not (fb_ if go_a else fa_):
                go_a = not go_a
        if go_a:
            tri = (A[a], A[a + 1], B[b]); a += 1  # A runs with the cycle
        else:
            tri = (B[b + 1], B[b], A[a]); b += 1  # B runs against it
        if len(set(tri)) == 3:
            tris.append(tri)
    if any(bm.faces.get(tri) for tri in tris) or len(set(frozenset(tri) for tri in tris)) != len(tris):
        return None
    return [bm.faces.new(tri) for tri in tris]


def close_holes(ob):
    """Joins the points by place and closes each hole the cut made with faces of a material of its own, coloured as
    the faces round its edges are. Returns how many it closed, how many the original had (left), and how many open
    edges are left."""
    m = ob.data
    bm = bmesh.new(); bm.from_mesh(m)
    unit = float(np.linalg.norm(mx - mn)) * 1e-6
    unit_key = lambda v: tuple(np.round(np.array(v.co[:]) / unit).astype(np.int64).tolist())

    def welded(v):
        return key_weld.get(unit_key(v))

    # Faces lying on another face's points (a sheet made two-sided by a second layer, or a face made twice): welding
    # would merge the layers, so the points only such faces use are left out of the weld (their neighbours' copies of
    # the same places, across a texture seam, still join).
    sig = {f: tuple(sorted(welded(v) for v in f.verts)) for f in bm.faces}
    count = {}
    for t in sig.values():
        count[t] = count.get(t, 0) + 1
    apart = {v for f in bm.faces if count[sig[f]] > 1 for v in f.verts
             if all(count[sig[g]] > 1 for g in v.link_faces)}
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v not in apart], dist=unit)
    uv = bm.loops.layers.uv.active

    def key_of(e):
        w0, w1 = welded(e.verts[0]), welded(e.verts[1])
        return None if None in (w0, w1) else min(w0, w1) * n_weld + max(w0, w1)

    def cut_open(e):  # an open edge the cut made
        return e.is_boundary and key_of(e) in cut_keys

    def on_rim(v):
        return any(cut_open(e) for e in v.link_edges)

    peeled = 0
    for _ in range(8):  # faces the cut left as teeth along a hole's rim (two edges open), hanging by a corner, or
        # bridging it (an edge on the rim and the far corner on it too), which a closing face would lie on twice
        loose = [f for f in bm.faces if sum(cut_open(e) for e in f.edges) >= 2 or (
            any(cut_open(e) for e in f.edges) and all(on_rim(v) for v in f.verts))]
        if not loose:
            break
        peeled += len(loose)
        cut_keys.update(key_of(e) for f in loose for e in f.edges)  # their edges are the cut's now
        bmesh.ops.delete(bm, geom=loose, context='FACES')

    closed, kept = 0, 0
    for cycle in hole_cycles(bm):
        ring = [bm.edges.get((cycle[i], cycle[(i + 1) % len(cycle)])) for i in range(len(cycle))]
        if not any(key_of(e) in cut_keys for e in ring):
            kept += 1  # a hole the original had, or a two-layer sheet's outline
            continue
        colour = (0.5, 0.5, 0.5, 1.0)
        if pixels is not None and uv is not None:
            samples = []
            bm.faces.index_update()
            for f in sorted({f for e in ring for f in e.link_faces}, key=lambda f: f.index):  # in each face along
                # the edge, not at its corners, in a fixed order so the sum comes out the same each run
                x, y = sum((lp[uv].uv for lp in f.loops), mathutils.Vector((0, 0))) / len(f.loops)
                samples.append(pixels[min(H - 1, max(0, int((y % 1) * H))), min(W - 1, max(0, int((x % 1) * W))), :3])
            mean = np.mean(samples, axis=0)
            if img.colorspace_settings.name == 'sRGB' and not img.is_float:  # stored as sRGB; the colour wants linear
                mean = np.where(mean <= 0.04045, mean / 12.92, ((mean + 0.055) / 1.055) ** 2.4)
            colour = (*[float(v) for v in mean], 1.0)
        new = zip_up(bm, cycle)
        if new is None:  # a triangle of the zip is there already: one face, cut into triangles, instead
            try:
                face = bm.faces.new(cycle)
            except ValueError:
                continue  # that face is there already
            new = bmesh.ops.triangulate(bm, faces=[face], quad_method='BEAUTY', ngon_method='BEAUTY')['faces']
        if not m.materials:  # an original with no material: give its faces one, so the fill doesn't take them all
            m.materials.append(bpy.data.materials.new('body'))
        fill = bpy.data.materials.new('split-fill'); fill.use_nodes = True
        bsdf = next(n for n in fill.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = colour
        bsdf.inputs['Roughness'].default_value = 0.8
        m.materials.append(fill)
        for f in new:
            f.material_index = len(m.materials) - 1
            f.smooth = False
        closed += 1
    left = sum(1 for e in bm.edges if cut_open(e))
    if left:
        raise RuntimeError(f'Error: closing the holes left {left} edges the cut opened open')
    bm.to_mesh(m); bm.free(); m.update()
    faces = len(m.polygons)
    if m.validate(verbose=True) or len(m.polygons) != faces:
        raise RuntimeError(f'Error: closing the holes left faces Blender won\'t keep ({faces - len(m.polygons)})')
    return closed, kept, peeled


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
    if not ok.any():
        raise RuntimeError('Error: the piece is too small to find its middle to mirror it across')
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
Mb = np.eye(4); Mb[:3, :3] = R * s; Mb[:3, 3] = fix - (R @ c) * s  # the original's frame to the staged one
json.dump({'matrix': Mb.tolist()}, open(staging_out, 'w'))
report = {'faces': nf, 'picked': int(pick.sum()), 'dropped': int(drop.sum()), 'debris': int(debris.sum())}
for ob, name, out in ((obj, 'body', body_out),) + (((piece, 'piece', piece_out),) if chains else ()):
    if name == 'body':
        closed, kept, peeled = close_holes(ob)
        Vb = np.array([v.co[:] for v in ob.data.vertices])  # how far its own box is from the original's (staged)
        Sa, Sb = (V - c) @ R.T * s + fix, (Vb - c) @ R.T * s + fix
        off = max(float(np.abs(Sa.min(0) - Sb.min(0)).max()), float(np.abs(Sa.max(0) - Sb.max(0)).max()))
        report[name] = {'holes closed': closed, 'holes the original had': kept, 'faces peeled': peeled,
                        'own box off (mm)': round(off * 1000, 1)}
        if not chains and off > 0.001:  # staged by its own box, it would be sized and placed away from its joints
            raise RuntimeError(f'Error: what the rule drops moves the body\'s box by {off * 1000:.1f} mm: '
                               'one that only drops should leave the box as it was')
    else:  # in the staged frame, where the rule (and a prop's `top`) gives places
        ob.data.transform(mathutils.Matrix(Mb.tolist()))
        if np.linalg.det(Mb) < 0:  # mirrored: its faces wound back the right way round
            ob.data.flip_normals()
        ob.data.update()
        if rule.get('mirror'):
            report['mirror'] = mirror(ob)
    for x in sc.objects: x.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_yup=True,
                              export_image_format='AUTO', export_animations=False)
print('SPLIT', json.dumps(report))
