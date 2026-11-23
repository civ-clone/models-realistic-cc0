"""rig.py : rigs a posed figure for civ.one's 3D map, as its roster entry's `rig` says: binds it to the skeleton
stance.py posed it with, and gives it clips (idle, move, fight, die and the like) made from key poses.

Args (after --): POSED.glb WEIGHTS.json STANCE.json RIG.json OUT.glb. POSED is the figure as stance.py left it, and
WEIGHTS what it wrote of its points' weights then. OUT is POSED with a skin and the clips; its mesh, materials and
textures are POSED's, untouched, so it stands as POSED does until a clip moves it.

- **The skeleton** is stance.py's, bound where the stance put it: each bone a joint (named as the bone), under a root
  node `skeleton`. Each point keeps the four weights stance.py gave it that are biggest, shared again to add up to one.
- **`prop`:** a part (`part`, counted as stance.py counts them) on a joint of its own, which follows a bone (`bone`)
  unless a clip throws it.
- **`clips`:** by role: `idle`, `move` and `work` loop; `fight`, `die` and `settle` play once. Each has a `length` in
  seconds and its `keys`, each a pose at a time (`at`):
  - `aim` and `twist`, as a stance's, laid over the stance's own: a bone a key names is aimed (or twisted) as the key
    says, and a bone it aims at null keeps the turn on its parent that the stance gave it (a hand keeps its grip as
    the arm swings);
  - `turn`: the whole figure turned about a place (`about`), about an axis (`axis`), by `degrees`. A clip's turns
    share their axis and place;
  - `slide`: the whole figure moved across and along, [x, z], in metres.

  Between keys each bone turns smoothly, on a curve through them (eased to a stop at the ends of a clip that plays
  once). A clip that plays once starts at the stance, as the key at 0 must be; a loop's last frame is its first. The
  figure is stood on the ground in every frame (by its lowest point, leaving out the prop).
  - `throw`, in a clip: the prop leaves the hand at `at`, flies to land on the ground at `to` ([x, z]) at `lands`,
    turning over by `spin` degrees about the figure's x axis, is gone when it lands, and is back in the hand, grown
    from nothing, by `back`.

Every clip keys every joint's turn, the root's place, and the prop's place, turn and size, so none leaves a joint as
another left it. Clips are sampled at about FPS frames a second (a whole number of frames over each clip), played
between frames by turning each joint linearly. It prints a report: for each clip, how far its first frame is from the
bind, the most any edge of the figure grows and when, how many faces grow over 1.4 times, and the most weight any
point lost to the four kept.
"""
import json
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb  # noqa: E402
from check import BONES  # noqa: E402
from skeleton import about, fail, finite, forward, read_aim, read_rule, turn  # noqa: E402

FPS = 24
LOOPS = {'idle', 'move', 'work'}
ONCE = {'fight', 'die', 'settle'}
GRAVITY = 9.81
INFLUENCES = 4


def number(v, lo=-math.inf):
    return finite([v]) and v > lo


def read_rig(rig):
    """The rig rule, checked."""
    if not isinstance(rig, dict) or set(rig) - {'prop', 'clips'} or not isinstance(rig.get('clips'), dict) or not rig['clips']:
        fail('the rig should have clips, and may have a prop')
    prop = rig.get('prop')
    if prop is not None and not (isinstance(prop, dict) and set(prop) == {'part', 'bone'} and prop['bone'] in BONES and
                                 isinstance(prop['part'], int) and not isinstance(prop['part'], bool)):
        fail('prop should be a part and the bone it follows')
    for role, clip in rig['clips'].items():
        where = f'clip {role}'
        if role not in LOOPS | ONCE:
            fail(f'{where}: a clip is one of {sorted(LOOPS | ONCE)}')
        if not isinstance(clip, dict) or set(clip) - {'length', 'keys', 'throw'} or not number(clip.get('length'), 0):
            fail(f'{where}: a clip has a length over 0 and keys, and may have a throw')
        keys = clip.get('keys')
        if not isinstance(keys, list) or not keys:
            fail(f'{where}: keys should be a list of poses')
        turns = []
        for k in keys:
            if not isinstance(k, dict) or set(k) - {'at', 'aim', 'twist', 'turn', 'slide'} or not number(k.get('at'), -1e-9):
                fail(f'{where}: each key has a time (at, from 0), and may have aim, twist, turn and slide')
            aim = k.get('aim', {})
            if not isinstance(aim, dict):
                fail(f'{where}: aim should be an object')
            read_aim({b: d for b, d in aim.items() if d is not None}, k.get('twist', {}), where)
            if set(aim) - BONES:
                fail(f'{where}: aim names bones the skeleton hasn\'t: {sorted(set(aim) - BONES)}')
            if 'turn' in k:
                t = k['turn']
                if not (isinstance(t, dict) and set(t) == {'axis', 'degrees', 'about'} and finite(t['axis'], 3) and
                        np.linalg.norm(t['axis']) > 1e-6 and number(t['degrees']) and finite(t['about'], 3)):
                    fail(f'{where}: a turn has an axis, degrees and a place to turn about')
                turns.append(t)
            if 'slide' in k and not finite(k['slide'], 2):
                fail(f'{where}: slide should be [x, z]')
        if any(t['axis'] != turns[0]['axis'] or t['about'] != turns[0]['about'] for t in turns):
            fail(f'{where}: its turns should share their axis and the place they turn about')
        times = [k['at'] for k in keys]
        if any(b <= a for a, b in zip(times, times[1:])):
            fail(f'{where}: its keys should come in order of time, none at the same time')
        if role in LOOPS and not (times[0] == 0 and times[-1] < clip['length']):
            fail(f'{where}: a loop\'s keys run from 0 to before its length (its last frame is its first)')
        if role in ONCE:
            if not (times[0] == 0 and times[-1] == clip['length']):
                fail(f'{where}: a clip that plays once has keys at 0 and at its length')
            if set(keys[0]) != {'at'}:
                fail(f'{where}: a clip that plays once starts at the stance, its first key only a time')
        if 'throw' in clip:
            th = clip['throw']
            if prop is None:
                fail(f'{where}: a throw needs a prop')
            if not (isinstance(th, dict) and set(th) == {'at', 'lands', 'to', 'spin', 'back'} and finite(th['to'], 2) and
                    number(th['spin']) and all(number(th[k], 0) for k in ('at', 'lands', 'back')) and
                    th['at'] < th['lands'] < th['back'] - 0.2 + 1e-9 and th['back'] <= clip['length']):
                fail(f'{where}: a throw has at < lands < back - 0.2, back no later than the clip\'s length, a place to '
                     'land (to, [x, z]) and a spin')
    return rig


def quat(m):
    """A rotation matrix's quaternion, [x, y, z, w]."""
    t = np.trace(m)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, s / 4]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [s / 4, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, s / 4, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    else:
        s = math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, s / 4, (m[1, 0] - m[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def matrix(q):
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def curve(times, values, t, loop, length):
    """values (keys x n) at times, at each time in t, on a cubic curve through them: tangents from the keys either
    side (a loop wraps round; a clip played once stops at its ends)."""
    times, values = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    if loop:
        times = np.concatenate([[times[-1] - length], times, [times[0] + length, times[1 % len(times)] + length]])
        values = np.concatenate([values[-1:], values, values[:1], values[1 % len(values):][:1]])
    n = len(times)
    tangent = np.zeros_like(values)
    for k in range(n):
        if 0 < k < n - 1:
            tangent[k] = (values[k + 1] - values[k - 1]) / (times[k + 1] - times[k - 1])
    out = np.empty((len(t), values.shape[1]))
    for i, x in enumerate(t):
        k = int(np.clip(np.searchsorted(times, x, side='right') - 1, 0, n - 2))
        dt = times[k + 1] - times[k]
        u = (x - times[k]) / dt
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        out[i] = h00 * values[k] + h10 * dt * tangent[k] + h01 * values[k + 1] + h11 * dt * tangent[k + 1]
    return out


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    posed_path, weights_path, stance_path, rig_path, out_path = a[:5]
    stance = json.load(open(stance_path, encoding='utf-8'))
    J, skeleton = read_rule(stance)
    rig = read_rig(json.load(open(rig_path, encoding='utf-8')))
    side = json.load(open(weights_path, encoding='utf-8'))
    names = list(skeleton)
    if side.get('bones') != names:
        fail('the weights are for another skeleton')

    gltf, binary = glb.read(posed_path)
    placed = glb.placed_meshes(gltf)
    if len(placed) != 1 or any(abs(placed[0][1][r][c] - (r == c)) > 1e-9 for r in range(4) for c in range(4)):
        fail('the figure should be one mesh, placed as it is')
    if gltf.get('skins') or gltf.get('animations'):
        fail('the figure has a skin or animations already')
    mi = placed[0][0]
    if gltf['meshes'][mi].get('extras', {}).get('posed') is not True:
        fail(f'{posed_path} is not posed, so stance.py\'s weights are not for it')
    prims = gltf['meshes'][mi]['primitives']
    pairs = []
    for p in prims:
        pair = (p['attributes']['POSITION'], p['attributes'].get('NORMAL'))
        if pair not in pairs:
            pairs.append(pair)
    if [list(p) for p in pairs] != side['accessors']:
        fail('the weights are for points held otherwise than the figure holds them')
    start, pos = {}, []
    for pa, _ in pairs:
        start[pa] = sum(len(x) for x in pos)
        pos.append(np.array(glb.accessor(gltf, binary, pa), dtype=np.float64))
    pos = np.concatenate(pos)
    if len(side['weights']) != len(pos):
        fail('the weights are for another number of points')
    faces = np.array([[start[p['attributes']['POSITION']] + i for i in f]
                      for p in prims for f in glb.triangles(gltf, binary, p)], dtype=np.int64)

    # The joints: the bones, and the prop's.
    joints = names + (['prop'] if rig.get('prop') else [])
    nb = len(names)
    w = np.zeros((len(pos), len(joints)))
    for i, row in enumerate(side['weights']):
        for b, v in row:
            w[i, b] = v
    body = np.ones(len(pos), dtype=bool)
    body[side['loose']] = False
    if rig.get('prop'):
        part = rig['prop']['part']
        if not 0 <= part < len(prims):
            fail(f'prop: there is no part {part}')
        p = prims[part]
        used = start[p['attributes']['POSITION']] + np.unique(np.array(glb.triangles(gltf, binary, p)))
        if body[used].any():
            fail(f'prop: part {part} is not held whole in the stance, so it moves with the figure')
        w[used] = 0
        w[used, joints.index('prop')] = 1
    # The four biggest weights of each point, shared again to add up to one. Points at one place have the same
    #  weights (stance.py weighted them as one), so they keep the same four, and seams stay shut.
    order = np.argsort(-w, axis=1, kind='stable')[:, :INFLUENCES]
    top = np.take_along_axis(w, order, axis=1)
    dropped = 1 - top.sum(axis=1)
    top = top / top.sum(axis=1, keepdims=True)
    order = np.where(top > 0, order, 0)
    top32 = top.astype(np.float32)
    big = top32.argmax(axis=1)
    top32[np.arange(len(top32)), big] += np.float32(1) - top32.sum(axis=1, dtype=np.float32)
    skin_w = np.zeros_like(w)  # as the file's joints and weights share each point (unused ones are joint 0's, at 0)
    for k in range(INFLUENCES):
        np.add.at(skin_w, (np.arange(len(pos)), order[:, k]), top32[:, k].astype(np.float64))

    # The bind: each joint where the stance put it, in the posed file's place (stance.py moved the figure by `shift`
    #  to stand it on the ground).
    shift = np.array(side['shift'], dtype=float)
    heads = {n: skeleton[n][0] for n in names}
    parents = {n: skeleton[n][2] for n in names}
    rot_s, moved_s = forward(skeleton, stance.get('aim', {}), stance.get('twist', {}))

    def world(rot, moved):
        """4x4 world matrices of the bones, as turned (rot) and placed (moved, before the stance's shift)."""
        out = np.zeros((nb, 4, 4))
        for i, n in enumerate(names):
            out[i, :3, :3], out[i, :3, 3], out[i, 3, 3] = rot[n], moved[n] - shift, 1
        return out

    bind = world(rot_s, moved_s)
    if rig.get('prop'):  # the prop's joint bound where its bone is
        bind = np.concatenate([bind, bind[names.index(rig['prop']['bone'])][None]])
    inverse = np.linalg.inv(bind)
    stance_local = {n: rot_s[n] if parents[n] is None else rot_s[parents[n]].T @ rot_s[n] for n in names}

    def key_pose(k):
        """Each bone's turn in a key: the stance's aims and twists with the key's laid over them; a bone the key
        aims at null keeps the turn on its parent that the stance gave it (and any twist the key gives it)."""
        aim = {**stance.get('aim', {}), **k.get('aim', {})}
        twist = {**stance.get('twist', {}), **k.get('twist', {})}
        rot = {}
        for n, (head, tail, p) in skeleton.items():
            rp = rot[p] if p else np.eye(3)
            if n in k.get('aim', {}) and k['aim'][n] is None:
                r = rp @ stance_local[n]
                if n in k.get('twist', {}):
                    r = about(r @ (tail - head), math.radians(k['twist'][n])) @ r
            else:
                r = rp
                if n in aim:
                    r = turn(rp @ (tail - head), np.array(aim[n], dtype=float)) @ rp
                if n in twist:
                    r = about(r @ (tail - head), math.radians(twist[n])) @ r
            rot[n] = r
        return rot

    def skinned(frames):
        """Each point's place in each frame (frames: joints x 4 x 4), as civ.one's skinning puts it."""
        m = np.einsum('fjab,jbc->fjac', frames, inverse)
        ph = np.concatenate([pos, np.ones((len(pos), 1))], axis=1)
        return np.einsum('pj,fjab,pb->fpa', skin_w, m, ph)[..., :3]

    # The clips.
    animations, report = [], {}
    for role, clip in rig['clips'].items():
        loop, length = role in LOOPS, float(clip['length'])
        frames_n = max(2, int(round(length * FPS)))
        t = np.linspace(0, length, frames_n + 1)
        keys = clip['keys']
        kt = [k['at'] for k in keys]
        local_q, turns, slides = [], [], []
        axis = place = None
        for k in keys:
            rot = key_pose(k)
            local_q.append([quat(rot[n] if parents[n] is None else rot[parents[n]].T @ rot[n]) for n in names])
            if 'turn' in k:
                axis, place = np.array(k['turn']['axis'], dtype=float), np.array(k['turn']['about'], dtype=float)
            turns.append(float(k.get('turn', {}).get('degrees', 0)))
            slides.append(k.get('slide', [0, 0]))
        local_q = np.array(local_q)  # keys x bones x 4
        for k in range(1, len(keys)):  # each the nearer of q and -q to the key before it
            flip = np.einsum('bq,bq->b', local_q[k], local_q[k - 1]) < 0
            local_q[k, flip] *= -1
        q = curve(kt, local_q.reshape(len(keys), -1), t, loop, length).reshape(len(t), nb, 4)
        q /= np.linalg.norm(q, axis=2, keepdims=True)
        deg = curve(kt, np.array(turns)[:, None], t, loop, length)[:, 0]
        sl = curve(kt, np.array(slides, dtype=float), t, loop, length)
        if loop:  # the last frame is the first
            q[-1], deg[-1], sl[-1] = q[0], deg[0], sl[0]
        frames = np.zeros((len(t), len(joints), 4, 4))
        for f in range(len(t)):
            rot, moved = {}, {}
            for i, n in enumerate(names):
                p = parents[n]
                rot[n] = matrix(q[f, i]) if p is None else rot[p] @ matrix(q[f, i])
                moved[n] = heads[n] if p is None else rot[p] @ (heads[n] - heads[p]) + moved[p]
            m = world(rot, moved)
            whole = np.eye(4)
            if axis is not None and deg[f]:
                r = about(axis, math.radians(deg[f]))
                whole[:3, :3], whole[:3, 3] = r, place - r @ place
            whole[0, 3] += sl[f, 0]
            whole[2, 3] += sl[f, 1]
            frames[f, :nb] = np.einsum('ab,jbc->jac', whole, m)
            if rig.get('prop'):
                frames[f, nb] = frames[f, names.index(rig['prop']['bone'])]
        # Stood on the ground: each frame lifted or lowered so its lowest point (the prop left out) is on it.
        placed_pts = skinned(frames)
        low = placed_pts[:, body, 1].min(axis=1)
        frames[:, :, 1, 3] -= low[:, None]
        # The prop's own track: following its bone, or thrown.
        scale = np.ones(len(t))
        th = clip.get('throw')
        if th:
            hand = names.index(rig['prop']['bone'])
            f0 = int(np.searchsorted(t, th['at']))
            start_m = frames[f0, hand].copy()
            p0 = start_m[:3, 3]
            land = np.array([th['to'][0], 0.0, th['to'][1]])
            flight = th['lands'] - t[f0]
            v = (land - p0 - 0.5 * np.array([0, -GRAVITY, 0]) * flight ** 2) / flight
            for f in range(len(t)):
                if t[f] < t[f0]:
                    continue
                if t[f] < th['lands']:
                    tau = t[f] - t[f0]
                    m = start_m.copy()
                    m[:3, :3] = about([1, 0, 0], math.radians(th['spin']) * tau / flight) @ start_m[:3, :3]
                    m[:3, 3] = p0 + v * tau + 0.5 * np.array([0, -GRAVITY, 0]) * tau ** 2
                    frames[f, nb] = m
                elif t[f] < th['back'] - 0.2:
                    scale[f] = 0.001
                else:
                    scale[f] = max(0.001, min(1.0, 1 - (th['back'] - t[f]) / 0.2))
        # Joints' local turns (and the root's and the prop's places) for the file.
        rots = np.zeros((len(t), len(joints), 4))
        for f in range(len(t)):
            for i, n in enumerate(names):
                p = parents[n]
                lm = frames[f, i] if p is None else np.linalg.inv(frames[f, names.index(p)]) @ frames[f, i]
                rots[f, i] = quat(lm[:3, :3])
            if rig.get('prop'):
                rots[f, nb] = quat(frames[f, nb, :3, :3])
        for j in range(len(joints)):  # each the nearer of q and -q to the frame before
            for f in range(1, len(t)):
                if rots[f, j] @ rots[f - 1, j] < 0:
                    rots[f, j] *= -1
        root_t = frames[:, 0, :3, 3]
        prop_t = frames[:, nb, :3, 3] if rig.get('prop') else None
        animations.append((role, t, rots, root_t, prop_t, scale))
        # What it does to the figure, for the report: how far the first frame is from the bind, and how far the
        #  figure's edges grow (the prop's left out), frame by frame.
        final = skinned(frames)
        body_faces = body[faces].all(axis=1)
        e0 = np.stack([np.linalg.norm(pos[faces[:, i]] - pos[faces[:, (i + 1) % 3]], axis=1) for i in range(3)], 1)
        grown = []
        for f in range(len(t)):
            P = final[f]
            e1 = np.stack([np.linalg.norm(P[faces[:, i]] - P[faces[:, (i + 1) % 3]], axis=1) for i in range(3)], 1)
            g = (e1 / np.maximum(e0, 1e-6)).max(axis=1)
            g[~body_faces | (e0.max(axis=1) < 0.01)] = 1
            grown.append(g)
        grown = np.array(grown)
        worst = int(grown.max(axis=1).argmax())
        start_off = float(np.abs(frames[0] - bind).max())
        report[role] = {'from bind': round(start_off, 6), 'frames': len(t), 'grown': round(float(grown.max()), 2), 'at': round(float(t[worst]), 3),
                        'over 1.4x': int((grown > 1.4).any(axis=0).sum()), 'dropped': round(float(dropped.max()), 3)}
        if os.environ.get('RIG_FRAMES'):  # each frame's points, to check a player against
            np.save(os.path.join(os.environ['RIG_FRAMES'], f'{role}.npy'), final.astype(np.float32))

    # The file: POSED's, with the skin's and clips' data after its own.
    data = bytearray(binary)
    gltf.setdefault('bufferViews', [])
    gltf.setdefault('accessors', [])

    def add(values, kind, ctype, target=None, minmax=False):
        values = np.ascontiguousarray(values)
        while len(data) % 4:
            data.append(0)
        view = {'buffer': 0, 'byteOffset': len(data), 'byteLength': values.nbytes}
        if target:
            view['target'] = target
        data.extend(values.tobytes())
        gltf['bufferViews'].append(view)
        acc = {'bufferView': len(gltf['bufferViews']) - 1, 'componentType': ctype, 'count': int(len(values)),
               'type': kind}
        if minmax:
            flat = values.reshape(len(values), -1)
            acc['min'], acc['max'] = [float(v) for v in flat.min(axis=0)], [float(v) for v in flat.max(axis=0)]
        gltf['accessors'].append(acc)
        return len(gltf['accessors']) - 1

    nodes = gltf['nodes']
    first = len(nodes)
    index = {n: first + 1 + i for i, n in enumerate(joints)}
    root = {'name': 'skeleton', 'children': [index[n] for n in names if parents[n] is None] + ([index['prop']] if 'prop' in index else [])}
    nodes.append(root)
    for i, n in enumerate(joints):
        p = parents.get(n)
        lm = bind[i] if p is None else np.linalg.inv(bind[names.index(p)]) @ bind[i]
        node = {'name': n, 'rotation': [float(v) for v in quat(lm[:3, :3]).astype(np.float32)],
                'translation': [float(v) for v in lm[:3, 3].astype(np.float32)]}
        kids = [index[c] for c in names if parents[c] == n]
        if kids:
            node['children'] = kids
        nodes.append(node)
    gltf['scenes'][gltf.get('scene', 0)]['nodes'].append(first)
    ibm = add(np.ascontiguousarray(inverse.transpose(0, 2, 1)).astype(np.float32).reshape(-1, 16), 'MAT4', 5126)
    gltf['skins'] = [{'name': 'skeleton', 'joints': [index[n] for n in joints], 'inverseBindMatrices': ibm,
                      'skeleton': first}]
    mesh_node = next(n for n in nodes[:first] if n.get('mesh') == mi)
    mesh_node['skin'] = 0
    done = {}
    for p in prims:
        pa = p['attributes']['POSITION']
        if pa not in done:
            s, n = start[pa], gltf['accessors'][pa]['count']
            done[pa] = (add(order[s:s + n].astype(np.uint8), 'VEC4', 5121, 34962),
                        add(top32[s:s + n], 'VEC4', 5126, 34962))
        p['attributes']['JOINTS_0'], p['attributes']['WEIGHTS_0'] = done[pa]
    gltf['animations'] = []
    for role, t, rots, root_t, prop_t, scale in animations:
        anim = {'name': role, 'samplers': [], 'channels': []}
        times = add(t.astype(np.float32), 'SCALAR', 5126, minmax=True)

        def channel(node, path, values, kind):
            anim['samplers'].append({'input': times, 'output': add(values.astype(np.float32), kind, 5126),
                                     'interpolation': 'LINEAR'})
            anim['channels'].append({'sampler': len(anim['samplers']) - 1, 'target': {'node': node, 'path': path}})

        for j, n in enumerate(joints):
            channel(index[n], 'rotation', rots[:, j], 'VEC4')
        channel(index[names[0]], 'translation', root_t, 'VEC3')
        if prop_t is not None:
            channel(index['prop'], 'translation', prop_t, 'VEC3')
            channel(index['prop'], 'scale', np.repeat(scale[:, None], 3, axis=1), 'VEC3')
        gltf['animations'].append(anim)
    while len(data) % 4:
        data.append(0)
    gltf['buffers'][0]['byteLength'] = len(data)

    js = json.dumps(gltf, separators=(',', ':'), ensure_ascii=False).encode()
    js += b' ' * (-len(js) % 4)
    body_b = struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(data), 0x004E4942) + bytes(data)
    out = struct.pack('<III', 0x46546C67, 2, 12 + len(body_b)) + body_b
    glb.measure(*glb.read_bytes(out))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    open(out_path, 'wb').write(out)
    print('RIG', out_path, json.dumps(report))


main()
