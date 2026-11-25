"""skeleton.py : the skeleton stance.py fits to a figure and rig.py binds it to, and how its bones are turned.

A stance's `joints` give each joint's place as the figure stands in the file; `bones()` makes the skeleton from them,
and `forward()` turns its bones as an `aim` and a `twist` say (see stance.py), from the root out. `read_fingers()` reads
a stance's `fingers`, each hand's frame as the figure stands in the file, and `curl()` bends a hand's fingers so.
"""
import math

import numpy as np

from check import BONES, FINGERS, JOINTS, STANCE

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
    return out


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


def read_aim(aim, twist, where='the rule'):
    """An aim and a twist, checked."""
    if not isinstance(aim, dict) or set(aim) - BONES or not all(finite(d, 3) and 1e-6 < np.linalg.norm(d) < 1e6 for d in aim.values()):
        fail(f'{where}: aim should give bones (by name) a way to point [x, y, z], not [0, 0, 0]')
    if not isinstance(twist, dict) or set(twist) - BONES or not all(finite([v]) for v in twist.values()):
        fail(f'{where}: twist should give bones (by name) a number of degrees')


def read_rule(rule):
    """The rule, checked: its joints as arrays, and the skeleton they make."""
    if not isinstance(rule, dict) or set(rule) - STANCE:
        fail(f'the rule should be an object of {sorted(STANCE)}')
    joints = rule.get('joints')
    if not isinstance(joints, dict) or set(joints) != JOINTS or not all(finite(p, 3) for p in joints.values()):
        fail(f'the joints should be exactly {sorted(JOINTS)}, each a place [x, y, z]')
    J = {k: np.array(v, dtype=float) for k, v in joints.items()}
    skeleton = bones(J)
    if set(skeleton) != BONES:
        fail('the skeleton\'s bones are not those check.py knows')
    short = [n for n, (head, tail, _) in skeleton.items() if np.linalg.norm(tail - head) < 0.005]
    if short:
        fail(f'bones shorter than 5 mm, their joints too close: {short}')
    read_aim(rule.get('aim', {}), rule.get('twist', {}))
    whole = rule.get('whole', [])
    if not isinstance(whole, list):
        fail('whole should be a list')
    for b in whole:
        ok = isinstance(b, dict) and b.get('bone') in BONES
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
    by up to `curl`, and drawn `together` towards the hand's middle, by that share at their tips."""
    fingers = rule.get('fingers', {})
    if not isinstance(fingers, dict) or set(fingers) - set(SIDES):
        fail('fingers should name hands, L or R')
    out = {}
    for side, f in fingers.items():
        if not (isinstance(f, dict) and FINGERS <= set(f) <= FINGERS | {'together'} and finite(f['palm'], 3) and
                finite([f['knuckles'], f['radius'], f['curl'], f.get('together', 0)]) and 0 < f['knuckles'] < 1 and
                0 < f['radius'] <= 0.2 and 0 < f['curl'] <= 360 and 0 <= f.get('together', 0) < 1):
            fail(f'fingers.{side} should give the way its palm faces [x, y, z], where its knuckles are (a share of '
                 'the way from the wrist to the fingertips, between 0 and 1), and how its fingers curl: a radius '
                 '(metres, over 0 and up to 0.2) and degrees (over 0 and up to 360), and may draw them `together` '
                 '(from 0 to under 1)')
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
                     'centre': wrist + along * knuckles + palm * radius}
    return out


def curl(hand, points, normals, mine, faces=(), weld=None):
    """A hand's points past its knuckles (and their normals) with the fingers curled, as read_fingers() reads the
    hand: each bent round the curl's axis, as a finger's length wraps it (a point that far past the knuckles turned by
    that far over the radius, keeping its height above the finger's middle), up to the curl, and straight on past
    that; and first, with `together`, splayed fingers closed: each finger (a piece of the mesh, by `faces`, past the
    first part of its length, points at one place, by `weld`, kept together) has that share taken off how far it
    runs across the hand as it goes (beyond the fingers' usual), so it keeps its width. The points, the normals, and
    which points moved (of `mine`, the points that are the hand's)."""
    rel = points - hand['wrist']
    past = rel @ hand['along'] - hand['knuckles']
    up = rel @ hand['palm']
    radius = hand['radius']
    phi = np.clip(past / radius, 0, hand['curl'])
    on = np.maximum(past - hand['curl'] * radius, 0)
    c, s = np.cos(phi), np.sin(phi)
    along = hand['knuckles'] + (radius - up) * s + on * c
    palm = radius - (radius - up) * c + on * s
    moved = (past > 0) & mine
    across = rel @ hand['across']
    if hand['together'] and len(faces) and moved.any():
        finger = moved & (past > 0.15 * (hand['length'] - hand['knuckles']))  # past where the fingers part
        parent = np.arange(len(points))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for f in faces:
            if finger[f].all():
                for j in f[1:]:
                    parent[root(j)] = root(f[0])
        if weld is not None:  # points at one place (split along a texture's seams) are one finger's
            first = {}
            for i in np.where(finger)[0]:
                parent[root(i)] = root(first.setdefault(int(weld[i]), i))
        idx = np.where(finger)[0]
        roots = np.array([root(i) for i in idx])
        drift = {}  # each finger's run across the hand per metre along it
        for r in np.unique(roots):
            m = idx[roots == r]
            if len(m) >= 3 and np.ptp(past[m]) > 1e-3:
                drift[r] = np.polyfit(past[m], across[m], 1)[0]
        if drift:
            usual = float(np.median(list(drift.values())))
            for r, k in drift.items():
                m = idx[roots == r]
                across[m] -= hand['together'] * (k - usual) * past[m]
    new = points.copy()
    new[moved] = (hand['wrist'] + np.outer(along, hand['along']) + np.outer(palm, hand['palm']) +
                  np.outer(across, hand['across']))[moved]
    na, npl = normals @ hand['along'], normals @ hand['palm']
    turned = (np.outer(na * c - npl * s, hand['along']) + np.outer(na * s + npl * c, hand['palm']) +
              np.outer(normals @ hand['across'], hand['across']))
    new_normals = normals.copy()
    new_normals[moved] = turned[moved]
    return new, new_normals, moved
