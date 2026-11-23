"""stance.py : stands a figure in a natural pose, as its roster entry's `stance` says, for civ.one's 3D map.

Args (after --): GLB RULE.json. Rewrites GLB in place. Run it as build.py does, with `--python-exit-code 1`, so that a
failure ends Blender with an error code.

The rule gives the figure's skeleton as it stands in the file, and how to pose it:
- `joints`: each joint's place in metres, in the file's axes (x across, the figure's left at +x, y up, facing +z):
  `pelvis`, `chest`, `neck`, `head`, `top`, and on each side (`.L`, `.R`) `shoulder`, `elbow`, `wrist`, `hand` (the
  fingertips), `hip`, `knee`, `ankle` and `toe`.
- `aim`: for any bone, the way it points once posed, as [x, y, z]. A bone not named keeps its place on its parent.
  The bones run `hips` (from the pelvis down), `spine` (pelvis to chest), `chest` (to the neck), `neck` (to the head),
  `head` (to the top), and on each side `shoulder` (from the chest to the shoulder joint), `upper_arm`, `forearm`,
  `hand`, `thigh`, `shin` and `foot`.
- `twist`: for any bone, degrees to turn it about its own length once aimed (positive turns it anticlockwise, looking
  from its end back to the joint).
- `whole`: boxes (metres, as `owner`'s) or parts (`part`, a primitive counted as `owner` counts them), each with a
  `bone`: their points move with that bone alone, for things that must stay rigid, such as a rifle or a torch.

Each point moves with the bones near it, as Blender's automatic weights share it among them; the file's own points and
normals are moved, and nothing else in it changes. The figure is then stood on the ground and centred again.
"""
import json
import math
import os
import struct
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glb  # noqa: E402

RULE = {'joints', 'aim', 'twist', 'whole'}
SIDES = ('L', 'R')
JOINTS = {'pelvis', 'chest', 'neck', 'head', 'top'} | {f'{j}.{s}' for s in SIDES for j in (
    'shoulder', 'elbow', 'wrist', 'hand', 'hip', 'knee', 'ankle', 'toe')}


def bones(J):
    """The skeleton: name -> (head, tail, parent), parents before children."""
    out = {'hips': (J['pelvis'], J['pelvis'] - np.array([0, 0.12, 0]), None),
           'spine': (J['pelvis'], J['chest'], 'hips'),
           'chest': (J['chest'], J['neck'], 'spine'),
           'neck': (J['neck'], J['head'], 'chest'),
           'head': (J['head'], J['top'], 'neck')}
    for s in SIDES:
        sgn = 1 if s == 'L' else -1
        root = J['chest'] + 0.7 * (J['neck'] - J['chest']) + np.array([sgn * 0.03, 0, 0])
        out[f'shoulder.{s}'] = (root, J[f'shoulder.{s}'], 'chest')
        out[f'upper_arm.{s}'] = (J[f'shoulder.{s}'], J[f'elbow.{s}'], f'shoulder.{s}')
        out[f'forearm.{s}'] = (J[f'elbow.{s}'], J[f'wrist.{s}'], f'upper_arm.{s}')
        out[f'hand.{s}'] = (J[f'wrist.{s}'], J[f'hand.{s}'], f'forearm.{s}')
        out[f'thigh.{s}'] = (J[f'hip.{s}'], J[f'knee.{s}'], 'hips')
        out[f'shin.{s}'] = (J[f'knee.{s}'], J[f'ankle.{s}'], f'thigh.{s}')
        out[f'foot.{s}'] = (J[f'ankle.{s}'], J[f'toe.{s}'], f'shin.{s}')
    return out


def fail(text):
    raise RuntimeError(f'Error: {text}')


def turn(a, b):
    """The least rotation taking direction a to direction b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(np.dot(a, b))
    if c < -0.999999:
        axis = np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0])
        return about(axis, math.pi)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def about(axis, angle):
    axis = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def in_box(points, b):
    return np.all([(points[:, k] >= b[a][0]) & (points[:, k] <= b[a][1]) for k, a in enumerate('xyz')
                   if b.get(a) is not None] or [np.ones(len(points), dtype=bool)], axis=0)


def weights(welded, faces, skeleton):
    """Blender's automatic (bone heat) weights for each welded point: an array of points x bones. Where the bone heat
    can't solve the figure as it is (some cut figures aren't closed and clean enough), it weights a copy remeshed in
    voxels instead, and each point takes the weights of the copy's points nearest it."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    arm = bpy.data.armatures.new('skeleton')
    rig = bpy.data.objects.new('skeleton', arm)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, tail, parent) in skeleton.items():
        eb = arm.edit_bones.new(name)
        eb.head, eb.tail = head.tolist(), tail.tolist()
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    names = list(skeleton)

    def heat(obj):
        for o in scene.objects:
            o.select_set(False)
        obj.select_set(True)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        out = np.zeros((len(obj.data.vertices), len(names)))
        index = {g.index: names.index(g.name) for g in obj.vertex_groups if g.name in names}
        for v in obj.data.vertices:
            for ge in v.groups:
                if ge.group in index:
                    out[v.index, index[ge.group]] = ge.weight
        return out

    mesh = bpy.data.meshes.new('figure')
    mesh.from_pydata(welded.tolist(), [], faces.tolist())
    mesh.validate()
    if len(mesh.vertices) != len(welded):
        fail('the welded figure lost points when made into a mesh')
    body = bpy.data.objects.new('figure', mesh)
    scene.collection.objects.link(body)
    w = heat(body)
    if (w.sum(axis=1) <= 1e-6).mean() <= 0.02:
        return w

    proxy = bpy.data.objects.new('proxy', mesh.copy())
    scene.collection.objects.link(proxy)
    mod = proxy.modifiers.new('voxels', 'REMESH')
    mod.mode, mod.voxel_size = 'VOXEL', 0.012
    bpy.context.view_layer.objects.active = proxy
    for o in scene.objects:
        o.select_set(False)
    proxy.select_set(True)
    bpy.ops.object.modifier_apply(modifier='voxels')
    pw = heat(proxy)
    pp = np.array([v.co[:] for v in proxy.data.vertices])
    keep = pw.sum(axis=1) > 1e-6
    if not keep.any():
        return w
    pp, pw = pp[keep], pw[keep]
    out = np.zeros_like(w)
    for chunk in np.array_split(np.arange(len(welded)), max(1, len(welded) // 256)):
        d2 = ((welded[chunk][:, None, :] - pp[None]) ** 2).sum(axis=2)
        near = np.argsort(d2, axis=1)[:, :4]
        inv = 1 / (np.sqrt(np.take_along_axis(d2, near, axis=1)) + 1e-4)
        out[chunk] = np.einsum('pk,pkb->pb', inv, pw[near]) / inv.sum(axis=1, keepdims=True)
    print('PROXY', json.dumps({'unweighted': int((w.sum(axis=1) <= 1e-6).sum()), 'proxy points': int(len(pp))}))
    return out


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    path, rule = a[0], json.load(open(a[1], encoding='utf-8'))
    if set(rule) - RULE:
        fail(f'the rule says {sorted(set(rule) - RULE)}, which this does not read')
    if set(rule.get('joints', {})) != JOINTS:
        fail(f'the joints should be exactly {sorted(JOINTS)}')
    J = {k: np.array(v, dtype=float) for k, v in rule['joints'].items()}
    skeleton = bones(J)
    for k in ('aim', 'twist'):
        if set(rule.get(k, {})) - set(skeleton):
            fail(f'{k} names bones there are none of: {sorted(set(rule[k]) - set(skeleton))}')

    gltf, binary = glb.read(path)
    placed = glb.placed_meshes(gltf)
    if len(placed) != 1 or any(abs(placed[0][1][r][c] - (r == c)) > 1e-9 for r in range(4) for c in range(4)):
        fail('the figure should be one mesh, placed as it is')
    mi = placed[0][0]
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
    wf = np.unique(np.sort(wf, axis=1), axis=0)
    w = weights(welded, wf, skeleton)
    names = list(skeleton)
    for b in rule.get('whole', []):
        if b.get('bone') not in names:
            fail(f'whole: {b.get("bone")!r} is not a bone')
        if 'part' in b:
            # a primitive (counted as `owner` counts parts), all its points
            if not isinstance(b['part'], int) or isinstance(b['part'], bool) or not 0 <= b['part'] < len(prims):
                fail(f'whole: there is no part {b["part"]!r}')
            pa = prims[b['part']]['attributes']['POSITION']
            mine = np.zeros(len(pos), dtype=bool)
            mine[start[pa]:start[pa] + gltf['accessors'][pa]['count']] = True
            inside = np.zeros(len(welded), dtype=bool)
            inside[back[mine]] = True
        else:
            inside = in_box(welded, b)
        w[inside] = 0
        w[inside, names.index(b['bone'])] = 1
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

    # Each bone's turn, from the root out: aimed where the rule says, else carried by its parent.
    rot, moved = {}, {}
    for name, (head, tail, parent) in skeleton.items():
        r_parent = rot[parent] if parent else np.eye(3)
        r = r_parent
        if name in rule.get('aim', {}):
            r = turn(r_parent @ (tail - head), np.array(rule['aim'][name], dtype=float)) @ r_parent
        if name in rule.get('twist', {}):
            r = about(r @ (tail - head), math.radians(rule['twist'][name])) @ r
        rot[name] = r
        moved[name] = head if not parent else rot[parent] @ (head - skeleton[parent][0]) + moved[parent]
    heads = np.array([skeleton[n][0] for n in names])
    R = np.array([rot[n] for n in names])
    T = np.array([moved[n] for n in names])
    wp = np.einsum('pb,bij,pbj->pi', w, R, welded[:, None, :] - heads[None]) + w @ T
    new_pos = wp[back]
    new_nor = np.einsum('pb,bij,pj->pi', w[back], R, nor)
    new_nor /= np.maximum(np.linalg.norm(new_nor, axis=1, keepdims=True), 1e-12)

    # Stood on the ground and centred across and along again.
    lo, hi = new_pos.min(axis=0), new_pos.max(axis=0)
    new_pos -= np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])

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
    moved_by = np.linalg.norm(new_pos - pos, axis=1)
    print('POSE', path, json.dumps({'points': len(pos), 'moved': int((moved_by > 0.005).sum()),
                                    'unreached': int(lost.sum()), 'height': round(float(f32[:, 1].max()), 4)}))


main()
