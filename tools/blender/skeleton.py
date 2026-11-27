"""skeleton.py : the skeleton stance.py fits to a figure and rig.py binds it to, and how its bones are turned.

A stance's `joints` give each joint's place as the figure stands in the file; `bones()` makes the skeleton from them
(a rider's with his mount's bones first, his hips riding on its back), and `forward()` turns its bones as an `aim`
and a `twist` say (see stance.py), from the root out. `read_fingers()` reads a stance's `fingers`, each hand's frame
as the figure stands in the file, and `curl()` bends a hand's fingers so.
"""
import math

import numpy as np

from check import BONES, FINGERS, MOUNT_LEG_BONES, MOUNT_LEGS, STANCE, figure

SIDES = ('L', 'R')


def fail(text):
    raise RuntimeError(f'Error: {text}')


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
    if 'mount_pelvis' not in J:
        return out
    # A rider: his mount's bones first, from its hips (the root, from its pelvis down) along its back to its withers,
    #  its neck to its poll and its head to its nose, its tail from its dock, and each leg from its top to the front of
    #  its hoof (the forelegs hung from its back, the hind legs from its hips); and his hips riding on its back.
    mount = {'mount_hips': (J['mount_pelvis'], J['mount_pelvis'] - np.array([0, 0.12, 0]), None),
             'mount_back': (J['mount_pelvis'], J['mount_withers'], 'mount_hips'),
             'mount_neck': (J['mount_withers'], J['mount_poll'], 'mount_back'),
             'mount_head': (J['mount_poll'], J['mount_nose'], 'mount_neck'),
             'mount_tail': (J['mount_dock'], J['mount_tail'], 'mount_hips')}
    for s in SIDES:
        for leg, parent in (('fore', 'mount_back'), ('hind', 'mount_hips')):
            js = MOUNT_LEGS[leg]
            for i, b in enumerate(MOUNT_LEG_BONES):
                name = f'mount_{leg}_{b}.{s}'
                mount[name] = (J[f'mount_{leg}_{js[i]}.{s}'], J[f'mount_{leg}_{js[i + 1]}.{s}'], parent)
                parent = name
    head, tail, _ = out['hips']
    out['hips'] = (head, tail, 'mount_back')
    return {**mount, **out}


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


def forward(skeleton, aim, twist):
    """Each bone's turn, from the root out: aimed where `aim` says, else carried by its parent, then turned about its
    own length as `twist` says. Returns name -> rotation, and name -> where its head is then."""
    rot, moved = {}, {}
    for name, (head, tail, parent) in skeleton.items():
        r_parent = rot[parent] if parent else np.eye(3)
        r = r_parent
        if name in aim:
            r = turn(r_parent @ (tail - head), np.array(aim[name], dtype=float)) @ r_parent
        if name in twist:
            r = about(r @ (tail - head), math.radians(twist[name])) @ r
        rot[name] = r
        moved[name] = head if not parent else rot[parent] @ (head - skeleton[parent][0]) + moved[parent]
    return rot, moved


def finite(v, n=None):
    ok = (isinstance(v, list) and (n is None or len(v) == n) and
          all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v))
    return ok


def read_aim(aim, twist, where='the rule', bones=BONES):
    """An aim and a twist, checked: for `bones` (the figure's) only."""
    if not isinstance(aim, dict) or set(aim) - bones or not all(finite(d, 3) and 1e-6 < np.linalg.norm(d) < 1e6 for d in aim.values()):
        fail(f'{where}: aim should give bones (by name) a way to point [x, y, z], not [0, 0, 0]')
    if not isinstance(twist, dict) or set(twist) - bones or not all(finite([v]) for v in twist.values()):
        fail(f'{where}: twist should give bones (by name) a number of degrees')


def read_rule(rule):
    """The rule, checked: its joints as arrays, and the skeleton they make."""
    if not isinstance(rule, dict) or set(rule) - STANCE:
        fail(f'the rule should be an object of {sorted(STANCE)}')
    joints = rule.get('joints')
    shape = figure(joints)
    if shape is None or not all(finite(p, 3) for p in joints.values()):
        fail('the joints should be exactly a person\'s or a rider\'s (his and his mount\'s), as check.py names them, '
             'each a place [x, y, z]')
    J = {k: np.array(v, dtype=float) for k, v in joints.items()}
    skeleton = bones(J)
    if set(skeleton) != shape[1]:
        fail('the skeleton\'s bones are not those check.py knows')
    short = [n for n, (head, tail, _) in skeleton.items() if np.linalg.norm(tail - head) < 0.005]
    if short:
        fail(f'bones shorter than 5 mm, their joints too close: {short}')
    read_aim(rule.get('aim', {}), rule.get('twist', {}), bones=shape[1])
    whole = rule.get('whole', [])
    if not isinstance(whole, list):
        fail('whole should be a list')
    for b in whole:
        ok = isinstance(b, dict) and b.get('bone') in shape[1]
        if ok and 'part' in b:
            ok = set(b) == {'bone', 'part'} and isinstance(b['part'], int) and not isinstance(b['part'], bool)
        elif ok and 'line' in b:
            ok = (set(b) == {'bone', 'line', 'radius'} and isinstance(b['line'], list) and len(b['line']) == 2 and
                  all(finite(e, 3) for e in b['line']) and finite([b['radius']]) and b['radius'] > 0)
        elif ok:
            ok = len(b) > 1 and set(b) <= {'bone', 'x', 'y', 'z'} and all(
                finite(b[k], 2) and b[k][0] <= b[k][1] for k in 'xyz' if k in b)
        if not ok:
            fail(f'whole: {b!r} should be a bone with a part, a line and radius, or a box of x, y or z ranges')
    return J, skeleton


def read_fingers(rule, J):
    """A stance's `fingers`, checked: for each hand it names, the hand as the figure stands in the file (its wrist, its
    length to the fingertips, the ways along it, towards its palm and across it) and how its fingers curl: from the
    knuckles, round an axis across the hand `radius` towards the palm from them (where a fist holds a prop's middle),
    by up to `curl`, with `together`, each finger's run across the hand cut by that share, and with `grip`, each
    finger closing on the axis until its side nearest the palm is that far from it (see curl())."""
    fingers = rule.get('fingers', {})
    if not isinstance(fingers, dict) or set(fingers) - set(SIDES):
        fail('fingers should name hands, L or R')
    out = {}
    for side, f in fingers.items():
        if not (isinstance(f, dict) and FINGERS <= set(f) <= FINGERS | {'together', 'grip'} and
                finite(f['palm'], 3) and 1e-6 < np.linalg.norm(f['palm']) < 1e6 and
                finite([f['knuckles'], f['radius'], f['curl'], f.get('together', 0), f.get('grip', 0)]) and
                0 < f['knuckles'] < 1 and 0 < f['radius'] <= 0.2 and 0 < f['curl'] <= 360 and
                0 <= f.get('together', 0) < 1 and ('grip' not in f or 0 < f['grip'] < f['radius'])):
            fail(f'fingers.{side} should give the way its palm faces [x, y, z], where its knuckles are (a share of '
                 'the way from the wrist to the fingertips, between 0 and 1), and how its fingers curl: a radius '
                 '(metres, over 0 and up to 0.2) and degrees (over 0 and up to 360), and may draw them `together` '
                 '(from 0 to under 1) and `grip` (metres, over 0 and under the radius)')
        wrist, tip = J[f'wrist.{side}'], J[f'hand.{side}']
        length = float(np.linalg.norm(tip - wrist))
        along = (tip - wrist) / length
        palm = np.array(f['palm'], dtype=float)
        palm -= along * (palm @ along)
        if np.linalg.norm(palm) < 1e-6:
            fail(f'fingers.{side}.palm should be a way across the hand, not along it')
        palm /= np.linalg.norm(palm)
        knuckles, radius = f['knuckles'] * length, float(f['radius'])
        out[side] = {'wrist': wrist, 'along': along, 'palm': palm, 'across': np.cross(along, palm),
                     'knuckles': knuckles, 'radius': radius, 'curl': math.radians(f['curl']), 'length': length,
                     'together': float(f.get('together', 0)),
                     'grip': float(f['grip']) if 'grip' in f else None,
                     'centre': wrist + along * knuckles + palm * radius}
    return out


def pieces(of, faces, weld):
    """The pieces of a mesh among the points `of`: points joined by `faces` all of whose points are `of`, and points at
    one place (by `weld`: a mesh split along a texture's seams) kept together. Each, as an array of its points."""
    parent = np.arange(len(of))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        if of[f].all():
            for j in f[1:]:
                parent[root(j)] = root(f[0])
    first = {}
    for i in np.where(of)[0]:
        parent[root(i)] = root(first.setdefault(int(weld[i]), i))
    idx = np.where(of)[0]
    roots = np.array([root(i) for i in idx])
    return [idx[roots == r] for r in np.unique(roots)]


def curl(hand, points, normals, mine, faces, weld):
    """A hand's points past its knuckles (and their normals) with the fingers curled, as read_fingers() reads the
    hand: each bent round the curl's axis, as a finger's length wraps it (a point that far past the knuckles turned by
    that far over the radius, keeping its height above the line from the wrist to the fingertips, towards the palm),
    up to the curl, and straight on past that. A point that would come nearer the axis than a fifth of the radius is
    held that far from it (and counted): one further towards the palm than the axis would otherwise be turned through
    it, inside out.

    With `grip`, each finger also closes on the axis as it wraps it, as on a held prop's handle. Its middle, a line
    fitted to its points' heights along it, comes in (or goes out), over the stretch from where the fingers part to as
    far again, until the side of it nearest the palm lies `grip` from the axis. It turns as the line halfway between
    its middle and that side keeps its length, so its palm side is pressed a little and its back stretched, as a
    finger's is round a handle, and a finger that has come in turns further. Every curled point of the hand is then
    held a fifth of the grip from the axis, rather than a fifth of the radius. A curl that ends before the fingers
    part leaves the grip nothing to do.

    And first, with `together`, splayed fingers closed: each finger, a piece of the mesh (by `faces`, points at one
    place, by `weld`, kept together) past the first part of its length, has that share taken off how far it runs
    across the hand as it goes, beyond the pieces' middle run, so it runs nearer parallel to the others and keeps its
    width; the share grows from where the fingers part, so nothing jumps there. A thumb that reaches past the knuckles
    is such a piece too. A run is taken as at most 45 degrees across.

    `mine` are the points that are the hand's. Returns the points, the normals, which points moved, and what was done:
    how many moved, how many were held short of the axis, how many faces were folded (turned over, as a long face that
    a bent finger runs along can be, since it can't bend itself), with `grip`, the most a finger turned, and, with
    `together`, how many pieces were found and the most a point was moved across."""
    rel = points - hand['wrist']
    past = rel @ hand['along'] - hand['knuckles']
    up = rel @ hand['palm']
    radius, grip = hand['radius'], hand['grip']
    moved = (past > 0) & mine
    start = 0.15 * (hand['length'] - hand['knuckles'])  # where the fingers part
    fingers = ([q for q in pieces(moved & (past > start), faces, weld) if len(q) >= 3 and np.ptp(past[q]) > 1e-3]
               if (hand['together'] or grip) and moved.any() else [])
    reach = radius - up  # from the axis, once turned
    phi = np.clip(past / radius, 0, hand['curl'])
    on = np.maximum(past - hand['curl'] * radius, 0)
    least = 0.2 * radius
    info = {'points': int(moved.sum())}
    if grip is not None:
        least = 0.2 * grip
        if start / radius < hand['curl']:
            for q in fingers:
                slope, height = np.polyfit(past[q], up[q], 1)
                slope = float(np.clip(slope, -1, 1))
                height = float(np.mean(up[q] - slope * past[q]))
                inner = float((up[q] - height - slope * past[q]).max())  # its side nearest the palm, from its middle

                def closer(s):  # how far its middle has come in, that far past the knuckles
                    return (radius - height - slope * s - inner - grip) * np.clip((s - start) / start, 0, 1)
                s = np.linspace(start, past[q].max(), max(2, int(np.ceil((past[q].max() - start) / 5e-4)) + 1))
                bend = np.maximum(radius - height - slope * s - closer(s) - inner / 2, least)  # keeps its length
                gone = np.cumsum(np.diff(s) * (1 / bend[:-1] + 1 / bend[1:]) / 2)  # its turn, from where they part
                turn = start / radius + np.concatenate([[0], gone])
                phi[q] = np.minimum(np.interp(past[q], s, turn), hand['curl'])
                last = np.interp(hand['curl'], turn, s) if turn[-1] > hand['curl'] else np.inf  # where it's turned all
                on[q] = np.maximum(past[q] - last, 0)
                reach[q] -= closer(past[q])
        info['most turned (deg)'] = round(math.degrees(float(phi[moved].max())), 1) if moved.any() else 0
    held = moved & (reach < least)
    reach = np.maximum(reach, least)
    info['held'] = int(held.sum())
    c, s = np.cos(phi), np.sin(phi)
    along = hand['knuckles'] + reach * s + on * c
    palm = radius - reach * c + on * s
    across = rel @ hand['across']
    if hand['together'] and moved.any():
        drift = []  # each finger's run across the hand per metre along it
        for q in fingers:
            drift.append((q, float(np.clip(np.polyfit(past[q], across[q], 1)[0], -1, 1))))
        shift = np.zeros(len(points))
        if drift:
            usual = float(np.median([k for _, k in drift]))
            for q, k in drift:
                shift[q] = hand['together'] * (k - usual) * (past[q] - start)  # from where they part, so none jumps
        across = across - shift
        info.update({'pieces': len(drift), 'most across (mm)': round(float(np.abs(shift).max()) * 1000, 1)})
    new = points.copy()
    new[moved] = (hand['wrist'] + np.outer(along, hand['along']) + np.outer(palm, hand['palm']) +
                  np.outer(across, hand['across']))[moved]
    na, npl = normals @ hand['along'], normals @ hand['palm']
    turned = (np.outer(na * c - npl * s, hand['along']) + np.outer(na * s + npl * c, hand['palm']) +
              np.outer(normals @ hand['across'], hand['across']))
    new_normals = normals.copy()
    new_normals[moved] = turned[moved]
    f = faces[moved[faces].any(1)]
    if len(f):  # a face's normal, turned as its points are, against the face's own once they're moved
        n0, n1 = (np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]]) for p in (points, new))
        ph = np.where(moved, phi, 0)[f].mean(1)
        na, npl = n0 @ hand['along'], n0 @ hand['palm']
        n0 = (np.outer(na * np.cos(ph) - npl * np.sin(ph), hand['along']) +
              np.outer(na * np.sin(ph) + npl * np.cos(ph), hand['palm']) + np.outer(n0 @ hand['across'], hand['across']))
        info['folded'] = int(((n0 * n1).sum(1) < 0).sum())
    return new, new_normals, moved, info
