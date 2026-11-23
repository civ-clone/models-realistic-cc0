"""rig.py : rigs a posed figure for civ.one's 3D map, as its roster entry's `rig` says: binds it to the skeleton
stance.py posed it with, and gives it clips (idle, move, fight, die and the like) made from key poses.

Args (after --): POSED.glb WEIGHTS.json STANCE.json RIG.json OUT.glb. POSED is the figure as stance.py left it, and
WEIGHTS what it wrote of its points' weights then. OUT is POSED with a skin and the clips; its mesh, materials and
textures are POSED's, untouched, so it stands as POSED does until a clip moves it.

- **The skeleton** is stance.py's, bound where the stance put it: each bone a joint (named as the bone), under a root
  node `skeleton`. Each point keeps the four weights stance.py gave it that are biggest, shared again to add up to one.
- **`prop`:** a part (`part`, counted as stance.py counts them) on a joint of its own, `prop`, a child of the bone
  that holds it (`bone`), with its origin at the middle of the part as it stands (so a shot from it leaves from
  there). It never leaves the hand: only its size changes (its turn on the hand is keyed too, but stays the same).
- **`clips`:** by role: `idle`, `move` and `work` loop; `fight`, `die` and `settle` play once. Each has a `length` in
  seconds and its `keys`, each a pose at a time (`at`):
  - `aim` and `twist`, as a stance's, laid over the stance's own: a bone a key names is aimed (or twisted) as the key
    says, and a bone it aims at null keeps the turn on its parent that the stance gave it (a hand keeps its grip as
    the arm swings);
  - `turn`: the whole figure turned about a place (`about`), about an axis (`axis`), by `degrees`. A clip's turns
    share their axis and place;
  - `slide`: the whole figure moved across and along, [x, z], in metres;
  - `hips`: the hips moved from where they stand, [x, y, z], in metres, and `plant`: feet (`L`, `R`) kept on the
    ground, the ankle at a place [x, z] (as the posed figure stands in the file; or `true`: where it stands), the
    legs bent to reach them (the knees bending forward from where the keys put them), so the hips can drop, lean and
    shift their weight, and a foot can step, without the feet sliding, even as the whole figure turns. Between keys
    a foot is put down and lifted smoothly. The figure is still stood on its lowest point, so nothing else should go
    lower than a planted foot (the report's `planted` says how far one was lifted off);
  - `ease`: how the key is met: `stop` (easing to it where the movement turns back, on through it where it doesn't),
    `through` (on at speed, as an arm at a throw's release, which may overshoot), `hit` (arriving at twice the speed
    of a straight line from the key before, as a body hitting the ground, and leaving from rest), or `snap` (leaving
    the key before at twice that speed, even one hit, as a body a shot strikes, and met as `stop` meets a key). Feet
    are put down and lifted as `stop` whatever the key's ease;
  - `late`: bones that meet the key after the rest of the figure, by a time in seconds, as arms and a head reach the
    ground after the body they hang from.
  Each clip may give bones a `lag` in seconds: they turn as they would that much earlier (in a clip that plays once,
  less and less towards its end, so it ends as it would without), so a movement passes from the body out to the limbs
  and head.

  Between keys each bone turns smoothly, on a curve through them that doesn't overshoot them (but for a key met
  `through`): it eases to a stop at a key where it turns back, where two keys are the same, and at the ends of a clip
  that plays once, but for a last key hit, a second key snapped to, and `through` there, which is `stop`. A clip that
  plays once starts at the stance, as the key at 0 must be; a loop's last frame is its first, and its first key has
  no late bones. The figure is stood on
  the ground in every frame, by its lowest point (the prop's included, at its size), as stance.py stands it.
  - `shots`, in a clip: where a shot leaves the figure, for the map to draw: each a time (`at`) and the joint it
    leaves from (`joint`). The map reads the joint's place then, and draws what flies. For now a shot leaves from the
    prop (three.js renames joints whose names have a dot, so the bones' can't be found by name): it throws the prop,
    which is gone from 1 ms after `at` until 0.2 s before `back` (at least 0.25 s after `at`), growing back in the hand
    over those 0.2 s.

Every clip keys every joint's turn, the root's place, and the prop's size, so none leaves a joint as another left
it. Clips are sampled at about FPS frames a second (a whole number of frames over each clip), played
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
from skeleton import SIDES, about, fail, finite, forward, read_aim, read_rule, turn  # noqa: E402

FPS = 24
LOOPS = {'idle', 'move', 'work'}
ONCE = {'fight', 'die', 'settle'}
INFLUENCES = 4
LEG_REACH = (0.08, 0.18)  # a leg's weight fades out from this far above its hip to this far


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
        if not isinstance(clip, dict) or set(clip) - {'length', 'keys', 'shots', 'lag'} or not number(clip.get('length'), 0):
            fail(f'{where}: a clip has a length over 0 and keys, and may have shots and lag')
        keys = clip.get('keys')
        if not isinstance(keys, list) or not keys:
            fail(f'{where}: keys should be a list of poses')
        lag = clip.get('lag', {})
        if not isinstance(lag, dict) or set(lag) - BONES or not all(number(v, -1e-9) and v < clip['length'] for v in lag.values()):
            fail(f'{where}: lag should give bones a time from 0 to under the clip\'s length, in seconds')
        turns = []
        for k in keys:
            if not isinstance(k, dict) or set(k) - {'at', 'aim', 'twist', 'turn', 'slide', 'ease', 'hips', 'plant', 'late'} or not number(k.get('at'), -1e-9):
                fail(f'{where}: each key has a time (at, from 0), and may have aim, twist, turn, slide, ease, hips, plant and late')
            late = k.get('late', {})
            if not isinstance(late, dict) or set(late) - BONES or not all(number(v, -1e-9) for v in late.values()):
                fail(f'{where}: late should give bones (by name) a time from 0, in seconds')
            if 'hips' in k and not finite(k['hips'], 3):
                fail(f'{where}: hips should be [x, y, z], how far the hips move from where they stand')
            plant = k.get('plant', {})
            if not isinstance(plant, dict) or set(plant) - {'L', 'R'} or not all(v is True or finite(v, 2) for v in plant.values()):
                fail(f'{where}: plant should give feet (L, R) a place on the ground [x, z], or true to keep them where they stand')
            if k.get('ease', 'stop') not in ('stop', 'through', 'hit', 'snap'):
                fail(f'{where}: a key\'s ease is stop, through, hit or snap')
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
        if role in LOOPS and keys[0].get('late'):
            fail(f'{where}: a loop\'s first key has no late bones (they would jump where the loop starts again)')
        for b in sorted({b for k in keys for b in k.get('late', {})}):
            bt = [k['at'] + k.get('late', {}).get(b, 0) for k in keys]
            if any(y <= x for x, y in zip(bt, bt[1:])) or not (bt[-1] < clip['length'] if role in LOOPS else bt[-1] <= clip['length']):
                fail(f'{where}: late keys of {b} should still come in order of time, '
                     + ('before the loop\'s length' if role in LOOPS else 'none late at its last key'))
        if role in ONCE:
            if not (times[0] == 0 and times[-1] == clip['length']):
                fail(f'{where}: a clip that plays once has keys at 0 and at its length')
            if set(keys[0]) != {'at'}:
                fail(f'{where}: a clip that plays once starts at the stance, its first key only a time')
        shots = clip.get('shots', [])
        if not isinstance(shots, list) or not all(
                isinstance(x, dict) and prop and x.get('joint') == 'prop' and
                set(x) == ({'at', 'joint', 'back'} if x.get('joint') == 'prop' else {'at', 'joint'}) and
                number(x['at'], 0) and x['at'] < clip['length'] for x in shots):
            fail(f'{where}: shots should each be a time in the clip (at), the joint they leave from (prop, for now: '
                 'three.js renames the bones), and when the prop is back (back)')
        if any(b['at'] <= a['at'] for a, b in zip(shots, shots[1:])):
            fail(f'{where}: its shots should come in order of time')
        thrown = [x for x in shots if x['joint'] == 'prop']
        if not all(number(x['back']) and x['back'] - x['at'] >= 0.25 - 1e-9 and x['back'] <= clip['length'] for x in thrown) or any(
                b['at'] <= a['back'] for a, b in zip(thrown, thrown[1:])):
            fail(f'{where}: a thrown prop is back (back) no sooner than at + 0.25, no later than the clip\'s length, and '
                 'before it is thrown again')
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


def blend(a, b, w):
    """The rotation w of the way from a to b."""
    qa, qb = quat(a), quat(b)
    if qa @ qb < 0:
        qb = -qb
    c = float(np.clip(qa @ qb, -1, 1))
    if c > 0.9995:
        return matrix(qa + w * (qb - qa))
    th = math.acos(c)
    return matrix((math.sin((1 - w) * th) * qa + math.sin(w * th) * qb) / math.sin(th))


def reach(hip, target, a, b, pole):
    """Where the knee goes for an ankle at target, the thigh a long and the shin b, the knee bent towards pole."""
    d = target - hip
    n = max(float(np.linalg.norm(d)), 1e-9)
    u = d / n
    n = min(max(n, abs(a - b) + 1e-4), a + b - 1e-4)
    cos = (a * a + n * n - b * b) / (2 * a * n)
    side = pole - (pole @ u) * u
    if np.linalg.norm(side) < 1e-9:  # a pole along the leg gives no way to bend it: any way across will do
        side = np.cross(u, [1.0, 0, 0] if abs(u[0]) < 0.9 else [0, 0, 1.0])
    side /= float(np.linalg.norm(side))
    return hip + a * (cos * u + math.sqrt(max(0.0, 1 - cos * cos)) * side), hip + n * u


def curve(times, values, t, loop, length, wrap=None, eases=None):
    """values (keys x n) at times, at each time in t, on a cubic curve through them that doesn't overshoot them: a loop
    wraps round (its keys after the end taken times `wrap`, and its last before the start the same, as for a
    quaternion that goes on round rather than back); a clip played once stops at its ends. Each key's ease (`eases`)
    is how it's met: `stop` (as above), `through` (on at speed: the slope from the keys either side, unlimited, so it
    may overshoot), `hit` (arriving at speed, as a fall reaches the ground, and leaving from rest) or `snap` (thrown
    to it: leaving the key before at speed, as a body a shot strikes, and easing to it)."""
    times, values = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    if len(times) == 1:  # one key: it holds
        return np.repeat(values, len(t), axis=0)
    if loop:
        w = np.ones(values.shape[1]) if wrap is None else np.asarray(wrap, dtype=float)
        times = np.concatenate([[times[-1] - length], times, [times[0] + length, times[1 % len(times)] + length]])
        values = np.concatenate([values[-1:] * w, values, values[:1] * w, values[1 % len(values):][:1] * w])
        if eases is not None:
            eases = [eases[-1]] + list(eases) + [eases[0], eases[1 % len(eases)]]
    elif eases is not None:
        eases = list(eases)
    n = len(times)
    tangent = np.zeros_like(values)
    for k in range(1, n - 1):
        # From the keys either side, but none where the curve turns back or is flat at the key, and no steeper than
        #  three times the slope either side, so it never overshoots a key (Fritsch and Carlson's limits).
        before = (values[k] - values[k - 1]) / (times[k] - times[k - 1])
        after = (values[k + 1] - values[k]) / (times[k + 1] - times[k])
        m = (values[k + 1] - values[k - 1]) / (times[k + 1] - times[k - 1])
        m = np.clip(m, -3 * np.minimum(np.abs(before), np.abs(after)), 3 * np.minimum(np.abs(before), np.abs(after)))
        tangent[k] = np.where(before * after > 0, m, 0)
    arrive = tangent.copy()  # the slope as each key is reached, and (tangent) as it's left
    ease = list(eases) if eases is not None else ['stop'] * n
    for k in range(n):
        if ease[k] == 'through' and 0 < k < n - 1:
            arrive[k] = tangent[k] = (values[k + 1] - values[k - 1]) / (times[k + 1] - times[k - 1])
        elif ease[k] in ('hit', 'snap') and k > 0:
            slope = (values[k] - values[k - 1]) / (times[k] - times[k - 1])
            # Twice the slope at one end of the way, and at the other no more than root 5 times it, so the two stay
            #  inside Fritsch and Carlson's circle and the way doesn't overshoot either key.
            most = math.sqrt(5) * np.abs(slope)
            if ease[k] == 'hit':  # arriving at speed, leaving from rest
                arrive[k], tangent[k] = 2 * slope, 0
                if ease[k - 1] in ('stop', 'snap'):
                    arrive[k - 1] = tangent[k - 1] = np.clip(tangent[k - 1], -most, most)
            else:  # leaving the key before at speed, easing to this one
                tangent[k - 1] = 2 * slope
                arrive[k] = tangent[k] = np.clip(tangent[k], -most, most)
    out = np.empty((len(t), values.shape[1]))
    for i, x in enumerate(t):
        k = int(np.clip(np.searchsorted(times, x, side='right') - 1, 0, n - 2))
        dt = times[k + 1] - times[k]
        u = (x - times[k]) / dt
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        out[i] = h00 * values[k] + h10 * dt * tangent[k] + h01 * values[k + 1] + h11 * dt * arrive[k + 1]
    return out


def prop_size(clip, length):
    """The prop's size through a clip, as times and sizes: 1 but where a shot throws it, when it's 0 from 1 ms after
    the shot to 0.2 s before it's back, then grows back."""
    times, sizes = [0.0], [1.0]
    for x in clip.get('shots', []):
        if x['joint'] == 'prop':
            times += [x['at'], x['at'] + 0.001, x['back'] - 0.2, x['back']]
            sizes += [1.0, 0.0, 0.0, 1.0]
    if times[-1] < length:
        times.append(float(length))
        sizes.append(1.0)
    return times, sizes


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
    # The bone heat can reach a leg's weight up into the body (the Partisan's armpit and satchel). A leg moves less and
    #  less of what's above its hip, and nothing LEG_REACH above it, so a step or a crouch doesn't drag the chest.
    #  (The bind is the same whatever the weights, so the figure stands as before.)
    hip_y = max(skeleton[f'thigh.{s}'][0][1] for s in SIDES) - side['shift'][1]
    fade = np.clip((pos[:, 1] - hip_y - LEG_REACH[0]) / (LEG_REACH[1] - LEG_REACH[0]), 0, 1)
    legs = [names.index(f'{b}.{s}') for b in ('thigh', 'shin', 'foot') for s in SIDES]
    kept = w.copy()
    kept[:, legs] *= (1 - fade)[:, None]
    ok = kept.sum(axis=1) > 1e-6
    w[ok] = kept[ok] / kept[ok].sum(axis=1, keepdims=True)
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
    parents = {n: skeleton[n][2] for n in names}  # (and the prop's, below)
    rot_s, moved_s = forward(skeleton, stance.get('aim', {}), stance.get('twist', {}))

    def world(rot, moved):
        """4x4 world matrices of the bones, as turned (rot) and placed (moved, before the stance's shift)."""
        out = np.zeros((nb, 4, 4))
        for i, n in enumerate(names):
            out[i, :3, :3], out[i, :3, 3], out[i, 3, 3] = rot[n], moved[n] - shift, 1
        return out

    bind = world(rot_s, moved_s)
    if rig.get('prop'):  # the prop's joint turned as its bone is, at the middle of the part
        held = bind[names.index(rig['prop']['bone'])].copy()
        mid = held.copy()
        mid[:3, 3] = (pos[used].min(axis=0) + pos[used].max(axis=0)) / 2
        bind = np.concatenate([bind, mid[None]])
        carry = np.linalg.inv(held) @ mid  # the prop's place on its bone
        parents['prop'] = rig['prop']['bone']
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
        hips_off, weights, targets = [], [], []
        axis = place = None
        for k in keys:
            rot = key_pose(k)
            local_q.append([quat(rot[n] if parents[n] is None else rot[parents[n]].T @ rot[n]) for n in names])
            hips_off.append(k.get('hips', [0, 0, 0]))
            moved = {}
            for n in names:
                p = parents[n]
                moved[n] = heads[n] + np.array(hips_off[-1]) if p is None else rot[p] @ (heads[n] - heads[p]) + moved[p]
            weights.append([1.0 if s in k.get('plant', {}) else 0.0 for s in SIDES])
            row = []
            for s in SIDES:
                v = k.get('plant', {}).get(s)
                stand = moved_s[f'foot.{s}']  # the ankle as it stands
                row += list(moved[f'foot.{s}'] if v is None else stand if v is True else [v[0] + shift[0], stand[1], v[1] + shift[2]])
            targets.append(row)
            if 'turn' in k:
                axis, place = np.array(k['turn']['axis'], dtype=float), np.array(k['turn']['about'], dtype=float)
            turns.append(float(k.get('turn', {}).get('degrees', 0)))
            slides.append(k.get('slide', [0, 0]))
        local_q = np.array(local_q)  # keys x bones x 4
        for k in range(1, len(keys)):  # each the nearer of q and -q to the key before it
            flip = np.einsum('bq,bq->b', local_q[k], local_q[k - 1]) < 0
            local_q[k, flip] *= -1
        # A loop goes on from its last key to its first the short way round (a joint turning on and on keeps turning).
        wrap = np.where(np.einsum('bq,bq->b', local_q[-1], local_q[0]) < 0, -1.0, 1.0)
        eases = [k.get('ease', 'stop') for k in keys]
        q = np.zeros((len(t), nb, 4))
        for i, n in enumerate(names):
            # A bone that lags turns as it would that much earlier: a loop's all through, a clip played once's less
            #  and less towards its end, so it starts and ends as without.
            lag = clip.get('lag', {}).get(n, 0)
            tb = (t - lag) % length if loop else np.maximum(0, t - lag * (1 - t / length))
            if loop:
                tb[-1] = tb[0]
            kb = [k['at'] + k.get('late', {}).get(n, 0) for k in keys]  # a bone late to a key meets it after the rest
            q[:, i] = curve(kb, local_q[:, i], tb, loop, length, np.repeat(wrap[i], 4), eases)
        q /= np.linalg.norm(q, axis=2, keepdims=True)
        deg = curve(kt, np.array(turns)[:, None], t, loop, length, None, eases)[:, 0]
        off = curve(kt, np.array(hips_off, dtype=float), t, loop, length, None, eases)
        held_w = np.clip(curve(kt, np.array(weights), t, loop, length), 0, 1)  # feet go down and up as `stop`
        held_at = curve(kt, np.array(targets), t, loop, length).reshape(len(t), 2, 3)
        if loop:
            off[-1], held_w[-1], held_at[-1] = off[0], held_w[0], held_at[0]
        sl = curve(kt, np.array(slides, dtype=float), t, loop, length, None, eases)
        if loop:  # the last frame is the first
            q[-1], deg[-1], sl[-1] = q[0], deg[0], sl[0]
        frames = np.zeros((len(t), len(joints), 4, 4))
        for f in range(len(t)):
            rot, moved = {}, {}
            for i, n in enumerate(names):
                p = parents[n]
                rot[n] = matrix(q[f, i]) if p is None else rot[p] @ matrix(q[f, i])
                moved[n] = heads[n] + off[f] if p is None else rot[p] @ (heads[n] - heads[p]) + moved[p]
            # The whole figure's turn and slide, which a planted foot's leg reaches through.
            whole = np.eye(4)
            if axis is not None and deg[f]:
                r = about(axis, math.radians(deg[f]))
                whole[:3, :3], whole[:3, 3] = r, place - r @ place
            whole[0, 3] += sl[f, 0]
            whole[2, 3] += sl[f, 1]
            back = np.linalg.inv(whole)
            for j, s in enumerate(SIDES):
                if held_w[f, j] <= 0:
                    continue
                # A planted foot: the leg bent to put the ankle where it's planted once the figure is turned, the
                #  foot as it stands; blended with the leg as the keys turn it while the foot is put down or lifted.
                th, sh, ft = f'thigh.{s}', f'shin.{s}', f'foot.{s}'
                a, b = (np.linalg.norm(skeleton[x][1] - skeleton[x][0]) for x in (th, sh))
                hip, knee_k, ankle_k = moved[th], moved[sh], moved[ft]  # the leg as the keys turn it
                target = back[:3, :3] @ (held_at[f, j] - shift) + back[:3, 3] + shift
                # The knee bends forward, but from where the keys put it: as far from where a leg bent forward would
                #  put it for the keys' ankle as it is, so a foot planted where the keys put it leaves the leg be.
                fwd = rot['hips'] @ np.array([0.0, 0.0, 1.0])
                ideal_k, _ = reach(hip, ankle_k, a, b, fwd)
                ideal_t, _ = reach(hip, target, a, b, fwd)
                swing = turn(ankle_k - hip, target - hip)
                knee, ankle = reach(hip, target, a, b, ideal_t + swing @ (knee_k - ideal_k) - hip)
                r_th = turn(rot[th] @ (skeleton[th][1] - skeleton[th][0]), knee - hip) @ rot[th]
                carried = r_th @ rot[th].T @ rot[sh]
                r_sh = turn(carried @ (skeleton[sh][1] - skeleton[sh][0]), ankle - knee) @ carried
                for n, r in ((th, r_th), (sh, r_sh), (ft, whole[:3, :3].T @ rot_s[ft])):
                    rot[n] = blend(rot[n], r, held_w[f, j])
                for n in (sh, ft):
                    p = parents[n]
                    moved[n] = rot[p] @ (heads[n] - heads[p]) + moved[p]
            m = world(rot, moved)
            frames[f, :nb] = np.einsum('ab,jbc->jac', whole, m)
            if rig.get('prop'):
                frames[f, nb] = frames[f, names.index(rig['prop']['bone'])] @ carry
        # The prop's size: gone 1 ms after each shot that throws it, and grown back in the hand by its `back`.
        size_t, size_v = prop_size(clip, length)
        scale = np.interp(t, size_t, size_v)
        # Stood on the ground: each frame lifted or lowered so its lowest point (the prop's included, at its size) is on
        #  it, as stance.py stood the figure.
        shown = frames.copy()
        if rig.get('prop'):
            shown[:, nb, :3, :3] *= scale[:, None, None]
        low = skinned(shown)[:, :, 1].min(axis=1)
        frames[:, :, 1, 3] -= low[:, None]
        shown[:, :, 1, 3] -= low[:, None]
        # Joints' local turns (and the root's place) for the file.
        rots = np.zeros((len(t), len(joints), 4))
        for f in range(len(t)):
            for i, n in enumerate(joints):
                p = parents[n]
                lm = frames[f, i] if p is None else np.linalg.inv(frames[f, joints.index(p)]) @ frames[f, i]
                rots[f, i] = quat(lm[:3, :3])
        for j in range(len(joints)):  # each the nearer of q and -q to the frame before
            for f in range(1, len(t)):
                if rots[f, j] @ rots[f - 1, j] < 0:
                    rots[f, j] *= -1
        root_t = frames[:, 0, :3, 3]
        animations.append((role, t, rots, root_t, (size_t, size_v)))
        # What it does to the figure, for the report: how far the first frame is from the bind, and how far the
        #  figure's edges grow (the prop's left out), frame by frame.
        final = skinned(shown)  # as the file plays: the prop at its size
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
        # How far a planted foot's ankle is from where it's planted, once the figure is stood on the ground: more
        #  than a few millimetres says something else (the other foot, the hem of a coat) went below the ground.
        off_plant = [np.linalg.norm(frames[f, names.index(f'foot.{s}'), :3, 3] - (held_at[f, j] - shift))
                     for j, s in enumerate(SIDES) for f in range(len(t)) if held_w[f, j] > 0.999]
        report[role] = {'from bind': round(start_off, 6), 'frames': len(t), 'grown': round(float(grown.max()), 2), 'at': round(float(t[worst]), 3),
                        'over 1.4x': int((grown > 1.4).any(axis=0).sum()), 'dropped': round(float(dropped.max()), 3),
                        'planted': round(float(max(off_plant, default=0)), 3)}
        if os.environ.get('RIG_FRAMES'):  # each frame's points, to check a player against
            np.save(os.path.join(os.environ['RIG_FRAMES'], f'{role}.npy'), final.astype(np.float32))
            np.savez(os.path.join(os.environ['RIG_FRAMES'], f'{role}-feet.npz'), weight=held_w, target=held_at - shift,
                     joints=frames[:, :, :3, 3], names=np.array(joints), low=low)

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
    root = {'name': 'skeleton', 'children': [index[n] for n in names if parents[n] is None]}
    nodes.append(root)
    for i, n in enumerate(joints):
        p = parents[n]
        lm = bind[i] if p is None else np.linalg.inv(bind[joints.index(p)]) @ bind[i]
        node = {'name': n, 'rotation': [float(v) for v in quat(lm[:3, :3]).astype(np.float32)],
                'translation': [float(v) for v in lm[:3, 3].astype(np.float32)]}
        kids = [index[c] for c in joints if parents[c] == n]
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
    for role, t, rots, root_t, (size_t, size_v) in animations:
        anim = {'name': role, 'samplers': [], 'channels': []}
        frame_times = add(t.astype(np.float32), 'SCALAR', 5126, minmax=True)

        def channel(node, path, values, kind, times=frame_times):
            anim['samplers'].append({'input': times, 'output': add(values.astype(np.float32), kind, 5126),
                                     'interpolation': 'LINEAR'})
            anim['channels'].append({'sampler': len(anim['samplers']) - 1, 'target': {'node': node, 'path': path}})

        for j, n in enumerate(joints):
            channel(index[n], 'rotation', rots[:, j], 'VEC4')
        channel(index[names[0]], 'translation', root_t, 'VEC3')
        if 'prop' in index:  # its size, on times of its own, so it's gone just after a shot
            channel(index['prop'], 'scale', np.repeat(np.array(size_v)[:, None], 3, axis=1), 'VEC3',
                    add(np.array(size_t, dtype=np.float32), 'SCALAR', 5126, minmax=True))
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
