"""stance.py : stands a figure in a natural pose, as its roster entry's `stance` says, for civ.one's 3D map.

Args (after --): GLB RULE.json [WEIGHTS.json]. Rewrites GLB in place, and writes each of its points' weights
to WEIGHTS.json where that's given, for rig.py. Run it as build.py does, with `--python-exit-code 1`, so that a
failure ends Blender with an error code.

The rule gives the figure's skeleton as it stands in the file, and how to pose it:
- `joints`: each joint's place in metres, in the file's axes (x across, the figure's left at +x, y up, facing +z):
  `pelvis`, `chest`, `neck`, `head`, `top`, and on each side (`.L`, `.R`) `shoulder`, `elbow`, `wrist`, `hand` (the
  fingertips), `hip`, `knee`, `ankle` and `toe`. A rider's give his mount's too: `mount_pelvis` (over its hip joints),
  `mount_withers`, `mount_poll` (the top of its head), `mount_nose`, `mount_dock` (the root of its tail) and
  `mount_tail` (its end), and on each side its foreleg's `mount_fore_top`, `_elbow`, `_knee`, `_fetlock` and `_toe`
  (the front of the hoof, on the ground) and its hind leg's `mount_hind_top`, `_stifle`, `_hock`, `_fetlock` and
  `_toe`.
- `aim`: for any bone, the way it points once posed, as [x, y, z]. A bone not named keeps its place on its parent.
  The bones run `hips` (from the pelvis down), `spine` (pelvis to chest), `chest` (to the neck), `neck` (to the head),
  `head` (to the top), and on each side `shoulder` (from the chest to the shoulder joint), `upper_arm`, `forearm`,
  `hand`, `thigh`, `shin` and `foot`. A rider's mount's run `mount_hips` (the root, from its pelvis down; the rider's
  `hips` ride on its back), `mount_back` (its pelvis to its withers), `mount_neck`, `mount_head` and `mount_tail`, and
  on each side, from the top of each leg down, `mount_fore_upper`, `_lower`, `_cannon` and `_hoof` (hung from its
  back) and `mount_hind_upper`, `_lower`, `_cannon` and `_hoof` (from its hips).
- `twist`: for any bone, degrees to turn it about its own length once aimed (positive turns it anticlockwise, looking
  from its end back to the joint).
- `whole`: boxes (metres, as `owner`'s), lines (`line`, two places, and a `radius`: the points within the radius of
  the line between them) or parts (`part`, a primitive, counted through the mesh's primitives as the file has them,
  after owner.py has added its own), each with a `bone`: their points (of a part, those its faces use) move with that
  bone alone, for things that must stay rigid, such as a slung rifle or a held torch.
- `fingers`: for a hand (`L`, `R`), its fingers curled, as a figure made with its hands open can't hold a prop or let
  a hand hang naturally: `palm`, the way the palm faces as the figure stands in the file; `knuckles`, where the
  fingers start, a share of the way from the wrist to the fingertips; and how they curl, round an axis across the hand
  `radius` (metres) towards the palm from the knuckles, each point past them turned by how far past over the radius
  (so a finger's length wraps it), up to `curl` degrees. It may draw them `together` (a share of each finger's run
  across the hand) so splayed fingers close, and close them on a held prop with `grip` (metres, under the radius):
  each finger comes in (or goes out) as it wraps the axis, until its side nearest the palm lies that far from it, and
  turns further for it (see skeleton.curl()). It curls the points the hand's bone weighs half or more (not those of a
  part held whole), before the figure is posed, and reports what it did (`curled`), with how many faces a bent finger
  folded over (a long face can't bend). A point that would come nearer the axis than a fifth of the radius (or of the
  grip) is held that far from it, as it would otherwise be turned through it, inside out, and it fails where over a
  third of a hand's points are held (a radius too small for the palm's depth). A palm given the wrong way round curls
  the fingers back, which it can't tell. assemble.py puts a prop held in the right hand across its palm, on the axis,
  where `fingers.R` is given. The radius is then best the palm's depth (below the line from the wrist to the
  fingertips, which a cupped palm may lie well below) and the prop's radius where it's held, and the grip a little
  over the prop's radius there.

Each point moves with the bones near it, as Blender's automatic weights share it among them; the file's own points and
normals are moved, and nothing else in it changes but for the mesh's `extras`, which then say it's posed (so it isn't
posed twice). Where a point's normal was its face's (flat shading), it's the posed face's again. The figure is then
stood on the ground by its lowest point, and centred again on the figure itself (leaving out any part held whole, such
as a prop).
"""
import json
import os
import struct
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb  # noqa: E402
from skeleton import curl, fail, forward, read_fingers, read_rule  # noqa: E402

EASE = 4  # rings of points round a rigid piece where its weights ease into the bone heat's,
EASE_NEAR = 0.12  # as far as this from it


def in_box(points, b):
    return np.all([(points[:, k] >= b[a][0]) & (points[:, k] <= b[a][1]) for k, a in enumerate('xyz')
                   if b.get(a) is not None] or [np.ones(len(points), dtype=bool)], axis=0)


def weights(welded, faces, skeleton, moving, apart=()):
    """Blender's automatic (bone heat) weights for each welded point: an array of points x bones. The bone heat fails
    to solve some figures at their own size and others made a hundred times bigger, so it tries both. Where neither
    weights the figure, it tries both again on the figure without the points `apart` (those of parts held whole, which
    take their bone's weights anyway, such as a long prop the heat can't get round). Where none of those weights it (or
    a bone that moves gets no points), it weights a copy remeshed in voxels instead, and each point takes the weights
    of the copy's points nearest it. Where the heat weights none of that copy (its loose bits, such as a horse's reins
    and buckles, can stop it), it weights the biggest piece of a copy of the figure without the points `apart`."""
    names = list(skeleton)
    all_faces = faces

    def heat(points, scale, remesh=None, biggest=False):
        """Bone heat on the welded figure (or a copy remeshed in voxels this big, or that copy's biggest piece alone),
        all made `scale` times bigger: the points weighted, and their weights."""
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        arm = bpy.data.armatures.new('skeleton')
        rig = bpy.data.objects.new('skeleton', arm)
        scene.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        for name, (head, tail, parent) in skeleton.items():
            eb = arm.edit_bones.new(name)
            eb.head, eb.tail = (head * scale).tolist(), (tail * scale).tolist()
            if parent:
                eb.parent = arm.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')
        mesh = bpy.data.meshes.new('figure')
        mesh.from_pydata((points * scale).tolist(), [], faces.tolist())
        mesh.validate()
        if len(mesh.vertices) != len(points):
            fail('the welded figure lost points when made into a mesh')
        obj = bpy.data.objects.new('figure', mesh)
        scene.collection.objects.link(obj)
        for o in scene.objects:
            o.select_set(False)
        obj.select_set(True)
        if remesh:
            bpy.context.view_layer.objects.active = obj
            mod = obj.modifiers.new('voxels', 'REMESH')
            mod.mode, mod.voxel_size = 'VOXEL', remesh * scale
            bpy.ops.object.modifier_apply(modifier='voxels')
        if biggest:  # the copy's pieces, by its edges: all but the biggest dropped
            parent = np.arange(len(obj.data.vertices))

            def root(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i
            ends = np.zeros(2 * len(obj.data.edges), dtype=np.int64)
            obj.data.edges.foreach_get('vertices', ends)
            for i, j in ends.reshape(-1, 2):
                parent[root(i)] = root(j)
            roots = np.array([root(i) for i in range(len(parent))])
            big = np.bincount(roots).argmax()
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.where(roots != big)[0]], context='VERTS')
            bm.to_mesh(obj.data)
            bm.free()
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        out = np.zeros((len(obj.data.vertices), len(names)))
        index = {g.index: names.index(g.name) for g in obj.vertex_groups if g.name in names}
        for v in obj.data.vertices:
            for ge in v.groups:
                if ge.group in index:
                    out[v.index, index[ge.group]] = ge.weight
        return np.array([v.co[:] for v in obj.data.vertices]) / scale, out

    def good(w):
        return (w.sum(axis=1) <= 1e-6).mean() <= 0.02 and all(w[:, b].max() > 0.5 for b in moving)

    for scale in (1, 100):
        _, w = heat(welded, scale)
        if good(w):
            return w, f'bone heat at {scale}x'
    if len(apart):
        rest = np.ones(len(welded), dtype=bool); rest[list(apart)] = False
        index = np.cumsum(rest) - 1
        faces = index[all_faces[rest[all_faces].all(axis=1)]]
        for scale in (1, 100):
            _, w_rest = heat(welded[rest], scale)
            if good(w_rest):
                w = np.zeros((len(welded), len(names))); w[rest] = w_rest
                return w, f'bone heat at {scale}x, without the parts held whole'
        faces = all_faces
    pp, pw = heat(welded, 1, remesh=0.012)
    keep = pw.sum(axis=1) > 1e-6
    how = 'bone heat on a copy remeshed in voxels'
    if not keep.any():  # the copy's biggest piece, of the figure without the parts held whole (a held sword's thin
        #  blade, fused into the copy, can stop the heat too); they take their bone's weights anyway
        rest = np.ones(len(welded), dtype=bool); rest[list(apart)] = False
        index = np.cumsum(rest) - 1
        faces = index[all_faces[rest[all_faces].all(axis=1)]]
        pp, pw = heat(welded[rest], 1, remesh=0.012, biggest=True)
        faces = all_faces
        keep = pw.sum(axis=1) > 1e-6
        how = 'bone heat on the biggest piece of a copy remeshed in voxels' + (', without the parts held whole' if len(apart) else '')
    if not keep.any():
        fail('the bone heat found no weights, on the figure or on a copy remeshed in voxels (or its biggest piece)')
    pp, pw = pp[keep], pw[keep]
    out = np.zeros((len(welded), len(names)))
    for chunk in np.array_split(np.arange(len(welded)), max(1, len(welded) // 256)):
        d2 = ((welded[chunk][:, None, :] - pp[None]) ** 2).sum(axis=2)
        near = np.argsort(d2, axis=1)[:, :4]
        inv = 1 / (np.sqrt(np.take_along_axis(d2, near, axis=1)) + 1e-4)
        out[chunk] = np.einsum('pk,pkb->pb', inv, pw[near]) / inv.sum(axis=1, keepdims=True)
    if not all(out[:, b].max() > 0.5 for b in moving):
        fail(f'no point moves mostly with {[n for i, n in enumerate(skeleton) if i in moving and out[:, i].max() <= 0.5]}, '
             'even on a copy remeshed in voxels')
    return out, how


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    path, rule = a[0], json.load(open(a[1], encoding='utf-8'))
    J, skeleton = read_rule(rule)
    hands = read_fingers(rule, J)

    gltf, binary = glb.read(path)
    placed = glb.placed_meshes(gltf)
    if len(placed) != 1 or any(abs(placed[0][1][r][c] - (r == c)) > 1e-9 for r in range(4) for c in range(4)):
        fail('the figure should be one mesh, placed as it is')
    mi = placed[0][0]
    if gltf['meshes'][mi].get('extras', {}).get('posed'):
        fail(f'{path} is posed already')
    prims = gltf['meshes'][mi]['primitives']
    if any(set(p['attributes']) - {'POSITION', 'NORMAL', 'TEXCOORD_0'} for p in prims):
        fail('a primitive has attributes besides POSITION, NORMAL and TEXCOORD_0, which would need posing too')
    # The points of all the primitives as one list (primitives sharing an accessor share its points).
    pairs = []
    for p in prims:
        pair = (p['attributes']['POSITION'], p['attributes'].get('NORMAL'))
        if pair[1] is None:
            fail('a primitive has no normals')
        if pair not in pairs:
            if any(pair[0] == q[0] or pair[1] == q[1] for q in pairs):
                fail('primitives share a POSITION accessor but not its NORMAL one, or the other way round')
            pairs.append(pair)
    start, pos, nor = {}, [], []
    for pa, na in pairs:
        start[pa] = sum(len(x) for x in pos)
        pos.append(np.array(glb.accessor(gltf, binary, pa), dtype=np.float64))
        nor.append(np.array(glb.accessor(gltf, binary, na), dtype=np.float64))
        if len(pos[-1]) != len(nor[-1]):
            fail('an accessor pair has more points than normals, or fewer')
    pos, nor = np.concatenate(pos), np.concatenate(nor)
    faces = np.array([[start[p['attributes']['POSITION']] + i for i in f]
                      for p in prims for f in glb.triangles(gltf, binary, p)], dtype=np.int64)

    # Points at the same place (seams in the texture) are one point to the weights, so they move as one.
    keys = np.round(pos, 4)
    welded, back = np.unique(keys, axis=0, return_inverse=True)
    back = back.ravel()
    wf = back[faces]
    wf = wf[(wf[:, 0] != wf[:, 1]) & (wf[:, 1] != wf[:, 2]) & (wf[:, 0] != wf[:, 2])]
    # each face once, keeping the way it winds (the bone heat reads its normals from it)
    _, first = np.unique(np.sort(wf, axis=1), axis=0, return_index=True)
    wf = wf[np.sort(first)]
    names = list(skeleton)
    moving = [names.index(n) for n in sorted(set(rule.get('aim', {})) | set(rule.get('twist', {})))]
    apart = set()  # the points of parts held whole, which the bone heat can do without
    for b in rule.get('whole', []):
        if 'part' in b and 0 <= b['part'] < len(prims):
            apart.update(back[start[prims[b['part']]['attributes']['POSITION']] +
                              np.unique(np.array(glb.triangles(gltf, binary, prims[b['part']])))].tolist())
    w, weighted = weights(welded, wf, skeleton, moving, sorted(apart))
    held = np.zeros(len(welded), dtype=bool)
    loose = np.zeros(len(pos), dtype=bool)  # points of parts held whole (props)
    for b in rule.get('whole', []):
        if 'part' in b:
            # a primitive: the points its faces use
            if not 0 <= b['part'] < len(prims):
                fail(f'whole: there is no part {b["part"]!r}; the mesh has {len(prims)}, numbered from 0')
            p = prims[b['part']]
            pa = p['attributes']['POSITION']
            if sum(q['attributes']['POSITION'] == pa for q in prims) > 1:
                fail(f'whole: part {b["part"]} shares its points with another part, so it is not a piece of its own')
            used = start[pa] + np.unique(np.array(glb.triangles(gltf, binary, p)))
            loose[used] = True
            inside = np.zeros(len(welded), dtype=bool)
            inside[back[used]] = True
        elif 'line' in b:
            a0, a1 = (np.array(e, dtype=float) for e in b['line'])
            d = a1 - a0
            s = np.clip((welded - a0) @ d / max(float(d @ d), 1e-12), 0, 1)
            inside = np.linalg.norm(welded - (a0 + s[:, None] * d), axis=1) <= b['radius']
        else:
            inside = in_box(welded, b)
        if not inside.any():
            fail(f'whole: {b!r} holds no points')
        w[inside] = 0
        w[inside, names.index(b['bone'])] = 1
        held |= inside
    if held.any():
        # Round each rigid piece, the weights eased from its bone to the bone heat's over a few rings of points (no
        #  farther than EASE_NEAR from it), so the faces between don't stretch.
        near = [set() for _ in range(len(welded))]
        for f in wf:
            for i in f:
                near[i].update(int(j) for j in f if j != i)
        ring, edge = set(np.where(held)[0].tolist()), np.where(held)[0].tolist()
        for _ in range(EASE):
            edge = [j for i in edge for j in near[i] if j not in ring]
            ring.update(edge)
        ease = np.array(sorted(ring - set(np.where(held)[0].tolist())), dtype=np.int64)
        if len(ease):
            # only those near the piece: on a coarse figure a few rings can reach far
            hp = welded[held]
            gap = np.array([np.sqrt(((hp - welded[i]) ** 2).sum(axis=1).min()) for i in ease])
            ease = ease[gap <= EASE_NEAR]
        for _ in range(4 * EASE if len(ease) else 0):
            w[ease] = np.array([w[list(near[i])].mean(axis=0) if near[i] else w[i] for i in ease])
    lost = w.sum(axis=1) <= 1e-6
    found = np.where(~lost)[0]
    if lost.any() and len(found):
        # Points the bone heat didn't reach (pieces it couldn't solve): the weights of the nearest point it did.
        for chunk in np.array_split(np.where(lost)[0], max(1, int(lost.sum()) // 512)):
            d2 = ((welded[chunk][:, None, :] - welded[found][None]) ** 2).sum(axis=2)
            w[chunk] = w[found[d2.argmin(axis=1)]]
    elif lost.any():
        # None reached: each point the nearest bone's, whole.
        heads = np.array([skeleton[n][0] for n in names])
        tails = np.array([skeleton[n][1] for n in names])
        d = tails - heads
        t = np.clip(np.einsum('pbk,bk->pb', welded[lost][:, None, :] - heads[None], d) / np.einsum('bk,bk->b', d, d), 0, 1)
        near = np.linalg.norm(welded[lost][:, None, :] - (heads[None] + t[..., None] * d[None]), axis=2).argmin(axis=1)
        w[lost] = 0
        w[np.where(lost)[0], near] = 1
    w /= w.sum(axis=1, keepdims=True)

    # Fingers curled, as the figure stands in the file: the points the hand's bone weighs half or more, not of a part
    #  held whole (a prop), past its knuckles. Their weights stay as the bone heat gave them, on the open hand. Which
    #  points are flat shaded, and how far each moves, are judged from the figure as it was.
    pos0, nor0 = pos.copy(), nor.copy()
    curled = {}
    for side, hand in hands.items():
        mine = (w[back][:, names.index(f'hand.{side}')] >= 0.5) & ~loose
        new_p, new_n, moved_p, curled[side] = curl(hand, pos, nor, mine, faces, back)
        if curled[side]['held'] * 3 > curled[side]['points']:
            fail(f"fingers.{side}: {curled[side]['held']} of its {curled[side]['points']} points past the knuckles "
                 'would come too near the axis they curl round, and are held short of it: its radius is too small '
                 'for its palm\'s depth')
        pos[moved_p], nor[moved_p] = new_p[moved_p], new_n[moved_p]

    # Each bone's turn, from the root out: aimed where the rule says, else carried by its parent.
    rot, moved = forward(skeleton, rule.get('aim', {}), rule.get('twist', {}))
    heads = np.array([skeleton[n][0] for n in names])
    R = np.array([rot[n] for n in names])
    T = np.array([moved[n] for n in names])
    # Each point from its own place, with the weights of its welded place (so points at one place stay together).
    wb = w[back]
    new_pos = np.einsum('pb,bij,pbj->pi', wb, R, pos[:, None, :] - heads[None]) + wb @ T
    new_nor = np.einsum('pb,bij,pj->pi', wb, R, nor)
    new_nor /= np.maximum(np.linalg.norm(new_nor, axis=1, keepdims=True), 1e-12)
    # Flat shading kept: where each face a point is on had the point's normal (either way round), it's the posed face's.
    def face_normals(p):
        n = np.cross(p[faces[:, 1]] - p[faces[:, 0]], p[faces[:, 2]] - p[faces[:, 0]])
        length = np.linalg.norm(n, axis=1)
        return n / np.maximum(length, 1e-30)[:, None], length > 1e-12
    fu, sound = face_normals(pos0)
    dots = np.einsum('fck,fk->fc', nor0[faces], fu)
    flat = np.ones(len(pos), dtype=bool)
    np.logical_and.at(flat, faces.ravel(), ((np.abs(dots) > 0.9999) | ~sound[:, None]).ravel())
    counted = np.zeros(len(pos), dtype=int)
    np.add.at(counted, faces.ravel(), np.repeat(sound, 3))
    flat &= counted > 0
    nu, _ = face_normals(new_pos)
    acc = np.zeros_like(pos)
    np.add.at(acc, faces.ravel(), (np.sign(dots)[..., None] * nu[:, None, :] * sound[:, None, None]).reshape(-1, 3))
    acc_len = np.linalg.norm(acc, axis=1)
    flat &= acc_len > 1e-9
    new_nor[flat] = acc[flat] / acc_len[flat][:, None]
    if not (np.isfinite(new_pos).all() and np.isfinite(new_nor).all()):
        fail('posing gave points or normals that are not numbers')

    # Stood on the ground by its lowest point, and centred across and along again on the figure itself, leaving out any
    #  part held whole (a prop such as a torch), which would pull the figure off its place.
    body = new_pos[~loose] if (~loose).any() else new_pos
    lo, hi = body.min(axis=0), body.max(axis=0)
    shift = np.array([(lo[0] + hi[0]) / 2, new_pos[:, 1].min(), (lo[2] + hi[2]) / 2])
    new_pos -= shift

    data = bytearray(binary)
    jobs = []
    for pa, na in pairs:
        n = gltf['accessors'][pa]['count']
        jobs += [(pa, new_pos[start[pa]:start[pa] + n]), (na, new_nor[start[pa]:start[pa] + n])]
    for acc_i, values in jobs:
        acc = gltf['accessors'][acc_i]
        view = gltf['bufferViews'][acc['bufferView']]
        if acc.get('componentType') != 5126 or acc.get('type') != 'VEC3':
            fail('the points and normals should be 32-bit floats')
        stride = view.get('byteStride') or 12
        at = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        for i, v in enumerate(values.astype(np.float32)):
            struct.pack_into('<3f', data, at + i * stride, *v.tolist())
    gltf['meshes'][mi]['extras'] = {**gltf['meshes'][mi].get('extras', {}), 'posed': True}
    f32 = new_pos.astype(np.float32)
    for pa, _ in pairs:
        part = f32[start[pa]:start[pa] + gltf['accessors'][pa]['count']]
        gltf['accessors'][pa]['min'] = [float(v) for v in part.min(axis=0)]
        gltf['accessors'][pa]['max'] = [float(v) for v in part.max(axis=0)]

    js = json.dumps(gltf, separators=(',', ':'), ensure_ascii=False).encode()
    js += b' ' * (-len(js) % 4)
    body = struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(data), 0x004E4942) + bytes(data)
    out = struct.pack('<III', 0x46546C67, 2, 12 + len(body)) + body
    glb.measure(*glb.read_bytes(out))
    open(path, 'wb').write(out)
    if len(a) > 2:
        # What rig.py binds the posed figure with: each point's weights (in the order the file's accessors hold
        #  them), the parts held whole, and how far the posed figure was moved to stand it on the ground.
        json.dump({'bones': names, 'accessors': [list(p) for p in pairs], 'shift': shift.tolist(),
                   'loose': np.where(loose)[0].tolist(),
                   'weights': [[[int(b), round(float(wb[i, b]), 6)] for b in np.where(wb[i] > 0)[0]] for i in range(len(pos))]},
                  open(a[2], 'w', encoding='utf-8'), separators=(',', ':'))
    moved_by = np.linalg.norm(new_pos - pos0, axis=1)
    print('POSE', path, json.dumps({'weights': weighted, 'points': len(pos), 'moved': int((moved_by > 0.005).sum()), 'flat': int(flat.sum()),
                                    'unreached': int(lost.sum()), 'height': round(float(f32[:, 1].max()), 4),
                                    **({'curled': curled} if hands else {})}))


main()
