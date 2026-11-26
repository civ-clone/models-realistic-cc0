"""check.py : checks the set against roster.json, as CI runs it. Standard library only.

- **The roster** says only what build.py reads, with values of the right kind. Each model is named as civ.one's build
  takes it (lowercase letters, digits and dashes), draws unit types the engine has, and is built from sources the
  roster lists, each with its page, licence, where its file came from and that file's SHA-256. Every source's
  licence is one this set's licence allows.
- **The manifest** is the set as civ.one's library reads it: schema 1, kind `models`, the roster's id, name, licence
  (with the credit to show, `licence.attribution`) and scale, and its credits as build.py writes them. Its models are
  the roster's, no more and no fewer, and each unit type is drawn by one model, the one the roster says.
- **Each model's entry** names its file, that file's SHA-256, its triangles (no more than the roster's budget), how far
  it reaches (`extent`), its animations, its sources' pages and what was done to it, all as the file and the roster
  say.
- **Each file** in `models/` is a model in the manifest, a rigged model's figure or an extra in the roster, and
  nothing else is there. Each is a glTF 2 binary that reads nothing from outside itself (no `uri` anywhere in it, as
  civ.one's loader asks) and needs no extension:
  - one JSON chunk and at most one binary chunk, each whole; every index in range (textures, animations and skins
    too);
  - triangles only, with positions, normals and one set of texture coordinates (and joints and weights where an extra
    keeps its skeleton, or a figure is rigged): positions finite, normals a unit long, texture coordinates within 0
    to 1;
  - images as JPEG, saying so: the first the baked texture, as big as the roster says, and none bigger;
  - each primitive drawn opaque, with a material that has a colour texture;
  - where the roster gives a model an `owner` rule, and only there, its owner's colour: materials saying
    `extras.playerColour` (and nothing else in their extras), each with a texture of its own that's a PNG (8-bit,
    grey and alpha or RGBA), no bigger than the baked texture, whose alpha is 0 somewhere, and where it is, its colour
    no darker than a grey of 70 in 255, so the owner's colour isn't drawn dark; and no other PNG;
  - its credit, licence and changes in `asset.extras`, and its credit in `asset.copyright`, as build.py writes them,
    saying where it was made with AI.
- **Each model stands as its roster says:** on the ground (or floating at its draught), centred across and along, and
  as tall or long as its size. A model with a prop is checked for its draught and grounding only, as its prop reaches
  past it.
- **The credits** in CREDITS.md are as build.py writes them.
- **Each stance** names every joint of the skeleton blender/stance.py fits, none of its bones shorter than 5 mm, and
  only its bones, and any hand's `fingers` (its palm a way across the hand, its knuckles a share between 0 and 1,
  a radius over 0 and up to 0.2 m, a curl over 0 and up to 360°, `together` from 0 to under 1, and a `grip` over 0
  and under the radius); a model with one says "posed" in its `made`, and its mesh says `extras.posed`, and only
  then.
- **Each rig** is on a figure with a stance, and says only what blender/rig.py reads: its clips by role (idle, move
  and work loop; fight, die and settle play once), each with a length and keys in order (a loop's from 0 to before its
  length; a clip played once from the stance at 0 to a key at its length), any prop a part the stance holds whole, any
  muzzle of its own a bone and a place (for a weapon held whole, not a prop: one muzzle at most, its own or its
  prop's), any shots within its clip, each from the prop (back in the hand by the clip's end) or the muzzle, and any
  strike (when a blow lands) within it, in a clip played once with no shots. A clip's `lag` gives bones a time under
  its length; a key's `ease` is one of EASES, its `hips` [x, y, z], its `plant` feet each at [x, z] or `true`, and its
  `late` bones a time from 0, each bone's keys still in order once late (a loop's before its length, none late on its
  first key; a clip played once none late on its last). A clip played once has nothing on its first key but its time
  and feet planted where they stand (`true`).
- **Each rigged figure,** `models/rigged/<model>.glb`, is its model bound to its stance's skeleton:
  - one skin whose joints are the stance's bones (and the prop), each where its inverse bind matrix undoes, so it
    stands as its model does; its mesh, materials and images are its model's, with no morph targets, and four joints
    and weights to each point, the weights adding up to one, no joint twice;
  - its clips are the rig's, each running from 0 to its length (its times' min and max given), keying the same
    joints (every joint's turn and the root's place) linearly, with values that are numbers and turns that are unit
    quaternions. A clip played once starts where the figure stands, and a loop ends where it starts. Clips play in
    place: only the root's place is keyed (and the prop's size), and the root stays within 0.25 m of where it starts
    across the ground in a loop, and 2.5 m in a clip played once. Each joint's property is keyed once. The prop's
    part moves with the prop's joint alone, which is a child of its bone, kept as it is held: its size is 1 but
    while it's thrown, and 0 from just after each shot until it grows back. A muzzle of the rig's own is one node, a
    child of its bone's joint, with only its place, where the rig says as the figure stands;
  - the manifest gives its file, SHA-256, clips, and any shots and strikes by clip (`rigged`).
"""
import hashlib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb  # noqa: E402
import imgsize  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems = []

# The engine's unit types, by their class names (Civilization and Civilization II).
UNITS = {
    'Artillery', 'Battleship', 'Bomber', 'Cannon', 'Caravan', 'Carrier', 'Catapult', 'Chariot', 'Cruiser', 'Diplomat',
    'Fighter', 'Frigate', 'Horseman', 'Ironclad', 'Knight', 'MechanizedInfantry', 'Musketman', 'Nuclear', 'Rifleman',
    'Sail', 'Settlers', 'Spearman', 'Submarine', 'Swordman', 'Tank', 'Transport', 'Trireme', 'Warrior',
    'AlpineTrooper', 'Archer', 'Cavalry', 'CruiseMissile', 'Crusader', 'Destroyer', 'Dragoon', 'Elephant', 'Engineer',
    'Explorer', 'Fanatic', 'Freight', 'Galleon', 'Helicopter', 'Howitzer', 'Marine', 'MissileCruiser', 'Paratrooper',
    'Partisan', 'Pikeman', 'Spy', 'StealthBomber', 'StealthFighter',
}
LICENCES = {
    'CC0 1.0': 'https://creativecommons.org/publicdomain/zero/1.0/',
    'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/',
}
ALLOWED = {'CC0 1.0': {'CC0 1.0'}, 'CC BY 4.0': {'CC0 1.0', 'CC BY 4.0'}}
NAME = re.compile(r'[a-z0-9][a-z0-9-]*\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
TOP = {'set', 'date', 'scale', 'generated', 'sources', 'models', 'extras'}
SOURCE = {'work', 'author', 'url', 'licence', 'note', 'ai', 'generated', 'made', 'prompt', 'file', 'sha256'}
MODEL = {'units', 'source', 'drop', 'split', 'cut', 'stage', 'prop', 'owner', 'stance', 'rig', 'scale', 'budget', 'made'}
EXTRA = {'source', 'drop', 'split', 'cut', 'stage', 'prop', 'owner', 'stance', 'made'}
SPLIT = {'chains', 'drop', 'depth', 'mirror'}
CUT = {'mode', 'tris', 'texture', 'depth', 'solidify', 'close'}
STAGE = {'measure', 'size', 'turn', 'draught', 'pose', 'keep'}
PROP = {'mode', 'source', 'options', 'cut'}
OWNER = {'part', 'colours', 'within', 'without', 'sides', 'cut', 'share', 'smooth', 'light'}
STANCE = {'joints', 'aim', 'twist', 'whole', 'fingers'}
FINGERS = {'palm', 'knuckles', 'radius', 'curl'}  # a hand's, in a stance's `fingers`
# A rig, as blender/rig.py reads it, and its clips by role: those that loop, and those that play once.
RIG = {'prop', 'muzzle', 'clips'}
CLIP = {'length', 'keys', 'shots', 'strike', 'lag'}
KEY = {'at', 'aim', 'twist', 'turn', 'slide', 'ease', 'hips', 'plant', 'late', 'hold', 'grip'}
KINDS = ('bottle', 'arrow', 'bullet', 'shell')  # what a shot is, for the map to draw
FPS = 24  # as blender/rig.py samples clips
EASES = ('stop', 'through', 'hit', 'snap')
LOOPS = {'idle', 'move', 'work'}
ONCE = {'fight', 'die', 'settle'}
# A figure's joints and bones, as blender/stance.py names them.
JOINTS = {'pelvis', 'chest', 'neck', 'head', 'top'} | {f'{j}.{s}' for s in 'LR' for j in (
    'shoulder', 'elbow', 'wrist', 'hand', 'hip', 'knee', 'ankle', 'toe')}
BONES = {'hips', 'spine', 'chest', 'neck', 'head'} | {f'{b}.{s}' for s in 'LR' for b in (
    'shoulder', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot')}
# The joints at each end of a bone (the hips and shoulder bones start where stance.py works out, so are checked apart).
BONE_ENDS = {'spine': ('pelvis', 'chest'), 'chest': ('chest', 'neck'), 'neck': ('neck', 'head'),
             'head': ('head', 'top')}
BONE_ENDS |= {f'{b}.{s}': (f'{h}.{s}', f'{t}.{s}') for s in 'LR' for b, h, t in (
    ('upper_arm', 'shoulder', 'elbow'), ('forearm', 'elbow', 'wrist'), ('hand', 'wrist', 'hand'),
    ('thigh', 'hip', 'knee'), ('shin', 'knee', 'ankle'), ('foot', 'ankle', 'toe'))}
ATTRIBUTES = {'POSITION', 'NORMAL', 'TEXCOORD_0'}
SKIN_ATTRIBUTES = {'JOINTS_0', 'WEIGHTS_0'}
# Points over a face, where it's sampled to find its owner's colour (as blender/owner.py samples it).
SAMPLES = ((1 / 3, 1 / 3, 1 / 3), (2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3),
           (0.4, 0.4, 0.2), (0.4, 0.2, 0.4), (0.2, 0.4, 0.4))


def problem(text):
    problems.append(text)


def number(value, above=None):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return ok and (above is None or value > above)


def whole(value, above=0):
    return isinstance(value, int) and not isinstance(value, bool) and value > above


def keys_ok(where, entry, allowed):
    if not isinstance(entry, dict):
        problem(f'{where}: should be an object')
        return False
    for k in sorted(set(entry) - allowed):
        problem(f'{where}: says {k!r}, which build.py does not read')
    return True


def check_licence(where, lic):
    if not isinstance(lic, dict) or lic.get('name') not in LICENCES or LICENCES[lic['name']] != lic.get('url'):
        problem(f'{where}: licence should be one of {sorted(LICENCES)}, with its url')
        return None
    return lic['name']


def finite_vec(value, n):
    return isinstance(value, list) and len(value) == n and all(number(x) for x in value)


def check_split(where, split):
    """A split rule, as blender/split.py reads it: chains of at least two stations [place, across, deep, gap] (the
    piece's, and what to `drop`; a rule may only drop, with no chains)."""
    if not keys_ok(where, split, SPLIT):
        return
    chains = split.get('chains', [])
    if not (isinstance(chains, list) and all(isinstance(c, list) and len(c) >= 2 for c in chains)):
        problem(f'{where}: chains should be a list of chains, each of two or more stations')
        return
    drop = split.get('drop', [])
    if not (isinstance(drop, list) and all(isinstance(c, list) and len(c) >= 2 for c in drop)):
        problem(f'{where}: drop should be a list of chains, each of two or more stations')
        return
    if not chains and not drop:
        problem(f'{where}: should have chains (a piece to split off), or drop, or both')
        return
    depth = split.get('depth', [0, 0, 1])
    if 'depth' in split and not (finite_vec(depth, 3) and any(depth)):
        problem(f'{where}.depth: should be a way [x, y, z], not [0, 0, 0]')
        depth = [0, 0, 1]
    for name, group in (('chains', chains), ('drop', drop)):
        for i, chain in enumerate(group):
            for j, st in enumerate(chain):
                if not (isinstance(st, list) and len(st) == 4 and finite_vec(st[0], 3) and number(st[1], 0) and
                        number(st[2], 0) and number(st[3]) and st[3] >= 0):
                    problem(f'{where}.{name}[{i}][{j}]: should be [place [x, y, z], across, deep (over 0), gap (0 or '
                            f'more)]')
            if not all(isinstance(st, list) and st and finite_vec(st[0], 3) for st in chain):
                continue
            for a, b in zip(chain, chain[1:]):
                length = math.dist(a[0], b[0])
                if length < 1e-3:
                    problem(f'{where}.{name}[{i}]: stations next to each other should be apart')
                elif abs(sum((q - p) * d for p, q, d in zip(a[0], b[0], depth))) > (
                        math.cos(math.radians(10)) * length * math.hypot(*depth)):
                    problem(f'{where}.{name}[{i}]: a stretch between stations shouldn\'t run within 10° of depth, '
                            f'whose way its ellipses are measured across')
            for j in range(1, len(chain) - 1):  # each stretch reaches 1 cm past its ends: a bend's outside must fit
                u = [q - p for p, q in zip(chain[j - 1][0], chain[j][0])]
                v = [q - p for p, q in zip(chain[j][0], chain[j + 1][0])]
                nu, nv = math.hypot(*u), math.hypot(*v)
                if not (nu and nv and isinstance(chain[j], list) and len(chain[j]) == 4 and number(chain[j][1]) and
                        number(chain[j][2])):
                    continue
                bend = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v)) / (nu * nv))))
                if max(chain[j][1], chain[j][2]) * math.sin(bend / 2) > 0.01:
                    problem(f'{where}.{name}[{i}][{j}]: its bend ({math.degrees(bend):.0f}°) leaves the outside of it '
                            f'uncovered past the 1 cm its stretches reach: add a station, or narrow it')
    if 'mirror' in split and not (isinstance(split['mirror'], bool) and (chains or not split['mirror'])):
        problem(f'{where}.mirror: should be true or false (and only true with chains, a piece to mirror)')


def check_cut(where, cut):
    if not keys_ok(where, cut, CUT):
        return
    if cut.get('mode') not in ('parts', 'rewrap'):
        problem(f'{where}: mode should be parts or rewrap')
    if not whole(cut.get('tris')):
        problem(f'{where}: tris should be a whole number over 0')
    if not whole(cut.get('texture')) or cut['texture'] not in (256, 512, 1024, 2048):
        problem(f'{where}: texture should be 256, 512, 1024 or 2048')
    if cut.get('mode') == 'rewrap' and not (whole(cut.get('depth')) and 6 <= cut['depth'] <= 10):
        problem(f'{where}: a rewrap needs a whole-number depth from 6 to 10')
    if 'solidify' in cut and not number(cut['solidify'], 0):
        problem(f'{where}: solidify should be a number over 0')
    if 'close' in cut and not (cut.get('mode') == 'rewrap' and number(cut['close'], 0) and cut['close'] < 0.2):
        problem(f'{where}: close is for a rewrap, a number over 0 and under 0.2 (a fraction of its size)')
    elif 'close' in cut and whole(cut.get('depth')) and not (cut['depth'] <= 8 and cut['close'] * 2 ** cut['depth'] >= 1.5):
        problem(f'{where}: a closing works in a box of voxels, so its depth should be 8 or under, and its reach (close) '
                f'at least one and a half voxels (1.5 / 2^depth)')
    if 'close' in cut and 'solidify' in cut:
        problem(f'{where}: a rewrap closes or solidifies, not both')


def span(value, low, high):
    return (isinstance(value, list) and len(value) == 2 and all(number(v) for v in value)
            and low <= value[0] <= high and low <= value[1] <= high)


def check_owner(where, rule):
    """An owner rule says only what blender/owner.py reads, with values of the right kind."""
    if not keys_ok(where, rule, OWNER):
        return
    if 'part' in rule and not whole(rule['part'], -1):
        problem(f'{where}: part should be a whole number from 0')
    colours = rule.get('colours', [])
    if not isinstance(colours, list) or not all(isinstance(c, dict) and set(c) <= {'h', 's', 'v'} for c in colours):
        problem(f'{where}: colours should be a list of ranges of h, s and v')
    else:
        for c in colours:
            if ('h' in c and not span(c['h'], 0, 360)) or any(k in c and not (span(c[k], 0, 1) and c[k][0] <= c[k][1]) for k in 'sv'):
                problem(f'{where}: colours: h is two angles from 0 to 360, s and v each a range from 0 to 1')
    for k in ('within', 'without'):
        boxes = rule.get(k, [])
        if not isinstance(boxes, list) or not all(isinstance(b, dict) and b and set(b) <= {'x', 'y', 'z'}
                                                  and all(span(r, -math.inf, math.inf) and r[0] <= r[1] for r in b.values())
                                                  for b in boxes):
            problem(f'{where}: {k} should be a list of boxes, each with ranges of x, y or z, low to high')
    for k in ('sides', 'share', 'light'):
        if k in rule and not (number(rule[k]) and 0 <= rule[k] <= 1):
            problem(f'{where}: {k} should be a number from 0 to 1')
    if 'smooth' in rule and not whole(rule['smooth'], -1):
        problem(f'{where}: smooth should be a whole number from 0')
    if 'cut' in rule and not isinstance(rule['cut'], bool):
        problem(f'{where}: cut should be true or false')


def check_stance(where, rule):
    """A stance says only what blender/stance.py reads, with values of the right kind."""
    if not keys_ok(where, rule, STANCE):
        return
    joints = rule.get('joints')
    if not isinstance(joints, dict) or set(joints) != JOINTS or not all(
            isinstance(p, list) and len(p) == 3 and all(number(v) for v in p) for p in joints.values()):
        problem(f'{where}: joints should give each of {len(JOINTS)} joints a place [x, y, z]')
    else:
        short = [b for b, (h, t) in BONE_ENDS.items() if math.dist(joints[h], joints[t]) < 0.005]
        for s, sgn in (('L', 1), ('R', -1)):
            # the shoulder bone runs from a point between the chest and neck, out to the shoulder joint
            root = [c + 0.7 * (n - c) + (sgn * 0.03 if k == 0 else 0)
                    for k, (c, n) in enumerate(zip(joints['chest'], joints['neck']))]
            if math.dist(root, joints[f'shoulder.{s}']) < 0.005:
                short.append(f'shoulder.{s}')
        if short:
            problem(f'{where}: bones shorter than 5 mm, their joints too close: {sorted(short)}')
    aim = rule.get('aim', {})
    if not isinstance(aim, dict) or set(aim) - BONES or not all(
            isinstance(d, list) and len(d) == 3 and all(number(v) for v in d) and 1e-6 < math.hypot(*d) < 1e6
            for d in aim.values()):
        problem(f'{where}: aim should give bones a way to point [x, y, z]')
    twist = rule.get('twist', {})
    if not isinstance(twist, dict) or set(twist) - BONES or not all(number(v) for v in twist.values()):
        problem(f'{where}: twist should give bones a number of degrees')
    whole_ = rule.get('whole', [])
    if not isinstance(whole_, list) or not all(
            isinstance(b, dict) and b.get('bone') in BONES and (
                (set(b) == {'bone', 'part'} and whole(b['part'], -1)) or
                (set(b) == {'bone', 'line', 'radius'} and isinstance(b['line'], list) and len(b['line']) == 2 and all(
                    isinstance(e, list) and len(e) == 3 and all(number(v) for v in e) for e in b['line'])
                 and number(b['radius'], 0)) or
                (len(b) > 1 and set(b) <= {'bone', 'x', 'y', 'z'} and all(
                    span(b[k], -math.inf, math.inf) and b[k][0] <= b[k][1] for k in 'xyz' if k in b)))
            for b in whole_):
        problem(f'{where}: whole should be a list, each a bone with a part, a line and radius, or a box of x, y or z ranges')
    fingers = rule.get('fingers', {})
    if not isinstance(fingers, dict) or set(fingers) - {'L', 'R'} or not all(
            isinstance(f, dict) and FINGERS <= set(f) <= FINGERS | {'together', 'grip'} and direction(f['palm']) and
            number(f['knuckles']) and 0 < f['knuckles'] < 1 and number(f['radius']) and 0 < f['radius'] <= 0.2 and
            number(f['curl']) and 0 < f['curl'] <= 360 and number(f.get('together', 0)) and
            0 <= f.get('together', 0) < 1 and ('grip' not in f or (number(f['grip'], 0) and f['grip'] < f['radius']))
            for f in fingers.values()):
        problem(f'{where}: fingers should give a hand (L or R) the way its palm faces [x, y, z], where its '
                'knuckles are (a share of the way from the wrist to the fingertips, between 0 and 1), and how its '
                'fingers curl: a radius (metres, over 0 and up to 0.2) and degrees (over 0 and up to 360), and may '
                'draw them together (a share, from 0 to under 1) and close them on a grip (metres, over 0 and under '
                'the radius)')
    elif isinstance(joints, dict) and set(joints) == JOINTS and all(
            isinstance(p, list) and len(p) == 3 and all(number(v) for v in p) for p in joints.values()):
        for side, f in fingers.items():
            along = [t - w for w, t in zip(joints[f'wrist.{side}'], joints[f'hand.{side}'])]
            n = math.hypot(*along)
            if n > 0:
                d = sum(p * a / n for p, a in zip(f['palm'], along))
                if math.hypot(*(p - d * a / n for p, a in zip(f['palm'], along))) < 1e-6:
                    problem(f'{where}: fingers.{side}.palm should be a way across the hand, not along it')


def direction(d):
    return isinstance(d, list) and len(d) == 3 and all(number(v) for v in d) and 1e-6 < math.hypot(*d) < 1e6


def shot_ok(x, prop, length, muzzle=False):
    """Whether a shot is a time in the clip, the joint it leaves from, what flies, and (a bottle) when it's back.
    `muzzle`: whether the rig has a muzzle of its own (on a bone, not its prop)."""
    muzzle = muzzle or bool(prop and 'muzzle' in prop)
    if not (isinstance(x, dict) and (prop or muzzle) and number(x.get('at')) and 0 < x['at'] < length):
        return False
    kind = x.get('kind', 'bottle')
    if kind == 'bottle':
        return bool(prop) and x.get('joint') == 'prop' and {'at', 'joint', 'back'} <= set(x) <= {'at', 'joint', 'back', 'kind'}
    joints = (('prop',) if prop else ()) + (('muzzle',) if muzzle else ())
    return kind in KINDS and x.get('joint') in joints and {'at', 'joint'} <= set(x) <= {'at', 'joint', 'kind'}


def posing(rig):
    """Whether any key holds the rig's prop or grips it, so every clip keys its place on the hand."""
    return any('hold' in k or 'grip' in k for c in rig['clips'].values() for k in c['keys'])


def check_rig(where, rig, stance):
    """A rig says only what blender/rig.py reads, with values of the right kind, on a figure with a stance."""
    if not keys_ok(where, rig, RIG):
        return
    if not isinstance(stance, dict):
        problem(f'{where}: a rig binds the skeleton a stance fits, so needs a stance')
        return
    prop = rig.get('prop')
    if prop is not None and not (isinstance(prop, dict) and {'part', 'bone'} <= set(prop) <= {'part', 'bone', 'muzzle', 'back', 'grounded', 'slides'}
                                 and {'part': prop.get('part'), 'bone': prop.get('bone')} in stance.get('whole', []) and
                                 all(direction(prop[k]) for k in ('muzzle', 'back') if k in prop) and
                                 all(isinstance(prop.get(k, True), bool) for k in ('grounded', 'slides'))):
        problem(f'{where}.prop: should be a part and its bone, as the stance holds it whole, and may have a muzzle and a '
                'back (ways [x, y, z]) and grounded (true or false) and slides (true or false)')
        prop = None
    muzzle = rig.get('muzzle')
    if muzzle is not None and not (isinstance(muzzle, dict) and set(muzzle) == {'bone', 'at'} and muzzle['bone'] in BONES
                                   and isinstance(muzzle['at'], list) and len(muzzle['at']) == 3
                                   and all(number(v) for v in muzzle['at'])):
        problem(f'{where}.muzzle: should be the bone that carries it and where it is (at, [x, y, z], as the posed figure '
                'stands)')
        muzzle = None
    if muzzle is not None and prop is not None and 'muzzle' in prop:
        problem(f'{where}: has a muzzle of its own and its prop has one too: shots leave from one')
    hand = prop['bone'][-1] if prop and prop['bone'] in ('hand.L', 'hand.R') else None
    clips = rig.get('clips')
    if not isinstance(clips, dict) or not clips:
        problem(f'{where}: needs clips')
        return
    for role, clip in clips.items():
        at = f'{where}.clips.{role}'
        if role not in LOOPS | ONCE:
            problem(f'{at}: a clip is one of {sorted(LOOPS | ONCE)}')
        if not keys_ok(at, clip, CLIP):
            continue
        length, keys = clip.get('length'), clip.get('keys')
        if not number(length, 0) or not isinstance(keys, list) or not keys or not all(isinstance(k, dict) for k in keys):
            problem(f'{at}: needs a length over 0 and a list of keys')
            continue
        lag = clip.get('lag', {})
        if not isinstance(lag, dict) or set(lag) - BONES or not all(number(v) and 0 <= v < length for v in lag.values()):
            problem(f'{at}: lag should give bones a time from 0 to under the clip\'s length, in seconds')
        turns = []
        for k in keys:
            for f in sorted(set(k) - KEY):
                problem(f'{at}: a key says {f!r}, which blender/rig.py does not read')
            aim, twist = k.get('aim', {}), k.get('twist', {})
            if not number(k.get('at')) or k['at'] < 0:
                problem(f'{at}: each key needs a time (at), from 0')
            if not isinstance(aim, dict) or set(aim) - BONES or not all(d is None or direction(d) for d in aim.values()):
                problem(f'{at}: aim should give bones a way to point [x, y, z], or null')
            if not isinstance(twist, dict) or set(twist) - BONES or not all(number(v) for v in twist.values()):
                problem(f'{at}: twist should give bones a number of degrees')
            if 'turn' in k:
                t = k['turn']
                if not (isinstance(t, dict) and set(t) == {'axis', 'degrees', 'about'} and direction(t['axis']) and
                        number(t['degrees']) and isinstance(t['about'], list) and len(t['about']) == 3 and
                        all(number(v) for v in t['about'])):
                    problem(f'{at}: a turn has an axis, degrees and a place to turn about')
                else:
                    turns.append(t)
            if 'slide' in k and not (isinstance(k['slide'], list) and len(k['slide']) == 2 and all(number(v) for v in k['slide'])):
                problem(f'{at}: slide should be [x, z]')
            if k.get('ease', 'stop') not in EASES:
                problem(f'{at}: a key\'s ease is one of {", ".join(EASES)}')
            if 'hips' in k and not (isinstance(k['hips'], list) and len(k['hips']) == 3 and all(number(v) for v in k['hips'])):
                problem(f'{at}: hips should be [x, y, z], how far the hips move from where they stand')
            plant = k.get('plant', {})
            if not isinstance(plant, dict) or set(plant) - {'L', 'R'} or not all(
                    v is True or (isinstance(v, list) and len(v) == 2 and all(number(x) for x in v)) for v in plant.values()):
                problem(f'{at}: plant should give feet (L, R) a place on the ground [x, z], or true to keep them where they stand')
            late = k.get('late', {})
            if not isinstance(late, dict) or set(late) - BONES or not all(number(v) and v >= 0 for v in late.values()):
                problem(f'{at}: late should give bones a time from 0, in seconds')
            if 'hold' in k:
                h = k['hold']
                if not (hand and 'back' in prop and 'muzzle' in prop and isinstance(h, dict) and {'aim', 'up', 'butt'} <= set(h) <= {'aim', 'up', 'butt', 'hand'} and
                        direction(h['aim']) and direction(h['up']) and isinstance(h['butt'], list) and
                        len(h['butt']) == 3 and all(number(v) for v in h['butt']) and
                        ('hand' not in h or (number(h['hand']) and 0 <= h['hand'] <= 1))):
                    problem(f'{at}: hold is for a prop a hand holds, with a muzzle and a back: its aim and up (ways), its '
                            'butt [x, y, z], and where the hand holds it (hand, 0 to 1)')
                else:
                    a, u = h['aim'], h['up']
                    cross = math.hypot(a[1] * u[2] - a[2] * u[1], a[2] * u[0] - a[0] * u[2], a[0] * u[1] - a[1] * u[0])
                    if cross <= 1e-6 * math.hypot(*a) * math.hypot(*u):
                        problem(f'{at}: a hold\'s up should lie across its aim, not along it')
            grip = k.get('grip')
            if 'grip' in k and (not (isinstance(grip, dict) and grip and hand and 'muzzle' in prop and 'back' in prop) or set(grip) - ({'L', 'R'} - {hand}) or not all(
                    number(v) and 0 <= v <= 1 for v in grip.values())):
                problem(f'{at}: grip is for a prop a hand holds, with a muzzle and a back: it gives the other hand (L or R) '
                        'a share of the way along it, 0 to 1')
        if any(t['axis'] != turns[0]['axis'] or t['about'] != turns[0]['about'] for t in turns):
            problem(f'{at}: its turns should share their axis and the place they turn about')
        times = [k.get('at') for k in keys]
        if not all(number(t) for t in times):
            continue
        if any(b <= a for a, b in zip(times, times[1:])):
            problem(f'{at}: its keys should come in order of time, none at the same time')
        if number(length, 0):
            step = length / max(2, int(round(length * FPS)))
            if any(b - a < step - 1e-6 for a, b in zip(times, times[1:] + ([times[0] + length] if role in LOOPS else []))):
                problem(f'{at}: its keys should be at least a frame ({step:.4f} s) apart (in a loop, round from its last to '
                        'its first), so each is played')
        if role in LOOPS and not (times[0] == 0 and times[-1] < length):
            problem(f'{at}: a loop\'s keys run from 0 to before its length')
        first = keys[0]
        if role in ONCE and not (times[0] == 0 and times[-1] == length and not set(first) - {'at', 'plant'} and (
                not isinstance(first.get('plant', {}), dict) or all(v is True for v in first.get('plant', {}).values()))):
            problem(f'{at}: a clip that plays once starts at the stance (its first key only at 0, and feet planted where '
                    'they stand, true) and has a key at its length')
        lates = [k['late'] for k in keys if isinstance(k.get('late'), dict)]
        for b in sorted({b for d in lates for b in d if b in BONES and number(d[b])}):
            bt = [k['at'] + (k['late'][b] if isinstance(k.get('late'), dict) and number(k['late'].get(b)) else 0) for k in keys]
            if any(y <= x for x, y in zip(bt, bt[1:])) or not (bt[-1] < length if role in LOOPS else bt[-1] <= length):
                problem(f'{at}: late keys of {b} should still come in order of time, '
                        + ('before the loop\'s length' if role in LOOPS else 'none late at its last key'))
        if role in LOOPS and isinstance(keys[0].get('late'), dict) and keys[0]['late']:
            problem(f'{at}: a loop\'s first key has no late bones (they would jump where the loop starts again)')
        if 'strike' in clip and not (number(clip['strike'], 0) and clip['strike'] <= length and role in ONCE and
                                     not clip.get('shots')):
            problem(f'{at}: strike should be the time a blow lands, over 0 and up to its length, in a clip played once '
                    'with no shots (a melee fight)')
        shots = clip.get('shots', [])
        if not isinstance(shots, list) or not all(shot_ok(x, prop, length, muzzle is not None) for x in shots):
            problem(f'{at}: shots should each be a time in the clip (at), the joint they leave from (prop, or a '
                    'muzzle: three.js renames the bones) and what flies (kind: bottle, the default, arrow, bullet or '
                    'shell); a bottle is the prop, thrown, so leaves from it, and says when the prop is back (back)')
            continue
        if any(b['at'] <= a['at'] for a, b in zip(shots, shots[1:])):
            problem(f'{at}: its shots should come in order of time')
        thrown = [x for x in shots if x.get('kind', 'bottle') == 'bottle']
        if not all(number(x['back']) and x['back'] - x['at'] >= 0.25 - 1e-9 and x['back'] <= length for x in thrown) or any(
                b['at'] <= a['back'] for a, b in zip(thrown, thrown[1:])):
            problem(f'{at}: a thrown prop is back (back) no sooner than at + 0.25, no later than the clip\'s length, and '
                    'before it is thrown again')


def check_build_entry(where, e, allowed, sources):
    if not keys_ok(where, e, allowed):
        return
    if e.get('source') not in sources:
        problem(f'{where}: source {e.get("source")!r} is not in the roster\'s sources')
    if 'drop' in e and not (isinstance(e['drop'], list) and all(isinstance(n, str) for n in e['drop'])):
        problem(f'{where}: drop should be a list of part names')
    check_cut(f'{where}.cut', e.get('cut'))
    st = e.get('stage')
    if keys_ok(f'{where}.stage', st, STAGE):
        if st.get('measure') not in ('height', 'along') or not number(st.get('size'), 0):
            problem(f'{where}.stage: needs measure (height or along) and a size over 0')
        if not number(st.get('turn', 0)) or ('draught' in st and not number(st['draught'], 0)):
            problem(f'{where}.stage: turn and draught should be numbers (draught over 0)')
    # whether it splits a piece off (not only dropping): None where check_split finds its rule malformed (said there)
    chains = e['split'].get('chains', []) if isinstance(e.get('split'), dict) else None
    splits = (bool(chains) if isinstance(chains, list) else None) if 'split' in e else False
    if 'split' in e:
        check_split(f'{where}.split', e['split'])
        if splits and 'prop' not in e:
            problem(f'{where}: a piece split off should be put back as its prop')
        if isinstance(st, dict) and set(st) & {'draught', 'keep', 'pose'}:
            problem(f'{where}: split.py stages a figure as it stands, so its stage can\'t have draught, keep or pose')
    if 'prop' in e and keys_ok(f'{where}.prop', e['prop'], PROP):
        p = e['prop']
        if p.get('mode') not in ('hand', 'chute', 'hat', 'bonehat') or p.get('source') not in set(sources) | {'split'}:
            problem(f'{where}.prop: needs a mode (hand, chute, hat or bonehat) and a source in the roster (or split)')
        if splits is not None and (p.get('source') == 'split') != splits:
            problem(f'{where}.prop: its source should be split exactly when the model splits a piece off')
        opts = p.get('options')
        if not isinstance(opts, dict):
            problem(f'{where}.prop: options should be an object')
            opts = {}
        for k in ('top', 'ground', 'roll', 'end'):
            if k in opts and 'posed' not in opts:
                problem(f'{where}.prop: {k} is only for a prop that is posed (with posed)')
        if 'top' in opts and not finite_vec(opts['top'], 3):
            problem(f'{where}.prop: top should be a place [x, y, z]')
        if 'roll' in opts and not number(opts['roll']):
            problem(f'{where}.prop: roll should be a number of degrees')
        if 'end' in opts and opts['end'] not in ('narrow', 'wide'):
            problem(f'{where}.prop: end should be narrow or wide')
        if 'ground' in opts and (type(opts['ground']) is not int or opts['ground'] != 1):
            problem(f'{where}.prop: ground should be 1')
        if 'top' in opts and 'end' in opts:
            problem(f'{where}.prop: top or end names its top, not both')
        if 'posed' in opts and not number(opts.get('height'), 0):
            problem(f'{where}.prop: a posed prop needs its height (m)')
        if 'ground' in opts and 'grip' in opts:
            problem(f'{where}.prop: ground sets where it\'s held, so grip goes with it')
        if 'posed' in opts and 'upright' in opts:
            problem(f'{where}.prop: posed turns the prop along its own length, so upright goes')
        if 'posed' in opts:
            stance = e.get('stance') if isinstance(e.get('stance'), dict) else {}
            posed = opts['posed']
            if not (finite_vec(posed, 3) and any(posed) and p.get('mode') == 'hand' and stance):
                problem(f'{where}.prop: posed should be a way [x, y, z], for a prop in the hand of a figure with a '
                        f'stance')
            whole = stance.get('whole') if isinstance(stance.get('whole'), list) else []
            prop_part = 2 if 'owner' in e else 1  # the body, its owner's colour, then the prop
            if stance and not any(isinstance(b, dict) and b.get('bone') == 'hand.R' and b.get('part') == prop_part
                                  for b in whole):
                problem(f'{where}.prop: a posed prop is turned as the right hand is, so the stance should hold it '
                        f'(part {prop_part}) whole on hand.R')
            if 'ground' in opts and finite_vec(posed, 3) and posed[1] <= 0:
                problem(f'{where}.prop: a prop stood on the ground should point up (posed y over 0)')
            legs = {'hips', 'thigh.L', 'thigh.R', 'shin.L', 'shin.R', 'foot.L', 'foot.R'}
            turned = set(stance.get('aim', {}) if isinstance(stance.get('aim'), dict) else {}) | set(
                stance.get('twist', {}) if isinstance(stance.get('twist'), dict) else {})
            if 'ground' in opts and turned & legs:
                problem(f'{where}.prop: ground stands the prop where the figure stands as it is, so the stance '
                        f'shouldn\'t move the legs ({sorted(turned & legs)})')
        if 'cut' in p:
            check_cut(f'{where}.prop.cut', p['cut'])
        if isinstance(e.get('split'), dict) and e['split'].get('mirror') and not (
                isinstance(p.get('cut'), dict) and p['cut'].get('mode') == 'rewrap' and 'close' in p['cut']):
            problem(f'{where}.prop: a mirrored piece wants a cut that rewraps and closes it')
    if 'owner' in e:
        check_owner(f'{where}.owner', e['owner'])
    if 'stance' in e:
        check_stance(f'{where}.stance', e['stance'])
    if 'rig' in e:
        check_rig(f'{where}.rig', e['rig'], e.get('stance'))
    if not isinstance(e.get('made'), str) or not e['made']:
        problem(f'{where}: made should say what was done')
    elif splits is not None and splits != ('split off' in e['made']):
        problem(f'{where}: made should say "split off" exactly when a piece is split off')
    elif 'split' in e and splits is False and 'dropped' not in e['made']:
        problem(f'{where}: made should say what was dropped where the split rule only drops')
    elif isinstance(e.get('cut'), dict) and (e['cut'].get('mode') == 'rewrap') != ('rewrap' in e['made']):
        problem(f'{where}: made should say "rewrapped" where, and only where, the model was rewrapped')
    elif ('owner' in e) != ("the owner's colour" in e['made']):
        problem(f'{where}: made should mention "the owner\'s colour" exactly when there is an owner rule')
    elif ('stance' in e) != bool(re.search(r'\bposed\b', e['made'])):
        problem(f'{where}: made should say "posed" exactly when there is a stance')


def credit_of(roster, key):
    s = roster['sources'][key]
    c = roster['generated'] if s.get('generated') else s
    return {k: c[k] for k in ('work', 'author', 'url', 'licence')}


def credit_line(c):
    return f'"{c["work"]}" by {c["author"]} ({c["url"]}), {c["licence"]["name"]} ({c["licence"]["url"]})'


def keys_of(entry):
    return [entry['source']] + ([entry['prop']['source']] if 'prop' in entry and entry['prop']['source'] != 'split' else [])


def expected_extras(roster, entry):
    keys = keys_of(entry)
    out = {'credits': [credit_line(credit_of(roster, k)) for k in keys],
           'licence': roster['set']['licence']['name'],
           'modifications': f'{entry["made"]}; by dom111 for civ.one, {roster["date"]}'}
    if any(roster['sources'][k].get('ai') for k in keys):
        out['ai'] = 'Made with AI (Meshy)'
    return out


def expected_copyright(roster, entry):
    credits = '; '.join(credit_line(credit_of(roster, k)) for k in keys_of(entry))
    return f'{credits}. Changed by dom111 for civ.one: {entry["made"]}.'


def has_uri(value):
    if isinstance(value, dict):
        return 'uri' in value or any(has_uri(v) for v in value.values())
    if isinstance(value, list):
        return any(has_uri(v) for v in value)
    return False


def expected_credits(roster):
    credits, seen = [], set()
    for entry in list(roster['models'].values()) + list(roster['extras'].values()):
        for k in keys_of(entry):
            c = credit_of(roster, k)
            if c['url'] not in seen:
                seen.add(c['url'])
                credits.append(c)
    return credits


def credits_md(roster, credits):
    s = roster['set']
    lines = [f'# Credits for {s["name"]}', '', s['licence']['attribution'], '']
    lines += [f'- {credit_line(c)}' for c in credits]
    lines += ['', "Each model's own credit is also in its file's `asset.extras`."]
    return '\n'.join(lines) + '\n'


def check_file(rel, skinned_ok, texture, owner, posed):
    """Checks one GLB; returns its gltf and measurements, or None."""
    path = os.path.join(ROOT, 'models', rel)
    try:
        gltf, binary = glb.read(path)
        if any(k in gltf for k in ('extensionsUsed', 'extensionsRequired', 'extensions')):
            raise glb.Bad('it uses an extension')
        if has_uri(gltf):
            raise glb.Bad('it names a uri, so it would read from outside the file')
        if len(gltf.get('buffers', [])) > 1 or (gltf.get('buffers') and gltf['buffers'][0].get('byteLength', 0) > len(binary)):
            raise glb.Bad('its buffer is not the binary chunk')
        for kind in ('meshes', 'materials', 'textures', 'images', 'nodes', 'accessors', 'animations', 'skins'):
            for x in gltf.get(kind, []):
                if 'extensions' in x:
                    raise glb.Bad(f'one of its {kind} uses an extension')
        # Posed (blender/stance.py marks the mesh) exactly where the roster gives a stance.
        marks = [m.get('extras') for m in gltf.get('meshes', [])]
        if any(x is not None and x != {'posed': True} for x in marks):
            raise glb.Bad('a mesh has extras other than posed: true')
        if any(x == {'posed': True} for x in marks) != posed:
            raise glb.Bad('it is posed where the roster has no stance' if not posed else
                          'it is not posed, though the roster gives a stance')
        # The owner's colour: which images its materials draw with, and which others do.
        used = {p.get('material') for mesh in gltf.get('meshes', []) for p in mesh.get('primitives', [])}
        tinted, plain, masks = set(), set(), {}
        for mi, m in enumerate(gltf.get('materials', [])):
            if mi not in used:
                raise glb.Bad(f'material {mi} is drawn by no primitive')
            extras = m.get('extras')
            if extras is not None and not (len(extras) == 1 and extras.get('playerColour') is True):
                raise glb.Bad(f'material {mi} has extras other than playerColour: true')
            base = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
            if base is not None:
                source = glb.item(gltf, 'textures', base.get('index')).get('source')
                (tinted if extras else plain).add(source)
        if tinted & plain:
            raise glb.Bad('an image is drawn both in the owner\'s colour and not')
        if bool(tinted) != owner:
            raise glb.Bad('it has an owner\'s colour where the roster has no owner rule' if tinted else
                          'it has no owner\'s colour, though the roster has an owner rule')
        for i, img in enumerate(gltf.get('images', [])):
            view = glb.item(gltf, 'bufferViews', img.get('bufferView'))
            data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view.get('byteLength', 0)]
            if i in tinted:
                if i == 0:
                    raise glb.Bad('image 0, the baked texture, is drawn in the owner\'s colour, not kept as a JPEG')
                read = imgsize.png_pixels(data)
                if read is None or img.get('mimeType') != 'image/png':
                    raise glb.Bad(f'image {i}, for the owner\'s colour, is not an 8-bit PNG of grey and alpha or RGBA, saying so')
                w, h, c, rows = read
                if max(w, h) > texture:
                    raise glb.Bad(f'image {i}, for the owner\'s colour, is {w} x {h}, bigger than the baked texture')
                clear = [row[x:x + c - 1] for row in rows for x in range(0, w * c, c) if row[x + c - 1] == 0]
                if not clear:
                    raise glb.Bad(f'image {i}, for the owner\'s colour, has no alpha of 0, so shows no owner\'s colour')
                if min(min(p) for p in clear) < 70:
                    raise glb.Bad(f'image {i}, for the owner\'s colour, is darker than a grey of 70 under its mask')
                masks[i] = (w, h, c, rows)
                continue
            if data[:3] != b'\xff\xd8\xff' or img.get('mimeType') != 'image/jpeg':
                raise glb.Bad(f'image {i} is not a JPEG, or says it is something else')
            sides = imgsize.size(data)
            if sides is None or max(sides) > texture or (i == 0 and max(sides) != texture):
                raise glb.Bad(f'image {i} is {sides}: the baked texture should be {texture} px, and no other bigger')
        for t in gltf.get('textures', []):
            glb.item(gltf, 'images', t.get('source'))
        for m in gltf.get('materials', []):
            pbr = m.get('pbrMetallicRoughness', {})
            for tex in (pbr.get('baseColorTexture'), pbr.get('metallicRoughnessTexture'), m.get('normalTexture'),
                        m.get('occlusionTexture'), m.get('emissiveTexture')):
                if tex is not None:
                    glb.item(gltf, 'textures', tex.get('index'))
        for t in gltf.get('textures', []):
            if 'sampler' in t:
                glb.item(gltf, 'samplers', t['sampler'])
        for ai, anim in enumerate(gltf.get('animations', [])):
            samplers = anim.get('samplers', [])
            for s in samplers:
                if len(glb.accessor(gltf, binary, s.get('input'))) != len(glb.accessor(gltf, binary, s.get('output'))) and s.get('interpolation', 'LINEAR') != 'CUBICSPLINE':
                    raise glb.Bad(f'animation {ai} has a sampler whose times and values differ in number')
            for ch in anim.get('channels', []):
                if not isinstance(ch.get('sampler'), int) or not 0 <= ch['sampler'] < len(samplers):
                    raise glb.Bad(f'animation {ai} has a channel whose sampler is out of range')
                glb.item(gltf, 'nodes', ch.get('target', {}).get('node'))
        for si, skin in enumerate(gltf.get('skins', [])):
            joints = skin.get('joints', [])
            for j in joints:
                glb.item(gltf, 'nodes', j)
            if 'inverseBindMatrices' in skin and len(glb.accessor(gltf, binary, skin['inverseBindMatrices'])) != len(joints):
                raise glb.Bad(f'skin {si} has a matrix for each of a different number of joints')
        allowed = ATTRIBUTES | (SKIN_ATTRIBUTES if skinned_ok else set())
        if gltf.get('skins') and not skinned_ok:
            raise glb.Bad('it has a skeleton, which only an extra may keep')
        for mi, mesh in enumerate(gltf.get('meshes', [])):
            for prim in mesh.get('primitives', []):
                attrs = prim.get('attributes', {})
                if not {'POSITION', 'NORMAL', 'TEXCOORD_0'} <= set(attrs) or set(attrs) - allowed:
                    raise glb.Bad(f'mesh {mi} has attributes {sorted(attrs)}')
                mat = glb.item(gltf, 'materials', prim.get('material'))
                if 'baseColorTexture' not in mat.get('pbrMetallicRoughness', {}):
                    raise glb.Bad(f'mesh {mi} is not drawn with a colour texture')
                if mat.get('alphaMode', 'OPAQUE') != 'OPAQUE':
                    raise glb.Bad(f'mesh {mi} is drawn see-through ({mat["alphaMode"]})')
                glb.triangles(gltf, binary, prim)
                pos = glb.accessor(gltf, binary, attrs['POSITION'])
                if any(not all(math.isfinite(c) for c in p) for p in pos):
                    raise glb.Bad(f'mesh {mi} has a point that is not a finite number')
                nor = glb.accessor(gltf, binary, attrs['NORMAL'])
                if len(nor) != len(pos) or any(not all(math.isfinite(c) for c in n) or abs(math.sqrt(sum(c * c for c in n)) - 1) > 0.01 for n in nor):
                    raise glb.Bad(f'mesh {mi} has a normal that is not a unit long')
                uv = glb.accessor(gltf, binary, attrs['TEXCOORD_0'])
                if len(uv) != len(pos) or any(not -1e-4 <= c <= 1 + 1e-4 for t in uv for c in t):
                    raise glb.Bad(f'mesh {mi} has texture coordinates outside 0 to 1')
                source = glb.item(gltf, 'textures', mat['pbrMetallicRoughness']['baseColorTexture'].get('index')).get('source')
                if source in masks:  # the owner's colour shows on some of its faces, not only somewhere in its PNG
                    w, h, c, rows = masks[source]
                    points = [tuple(wa * uv[a][k] + wb * uv[b][k] + wd * uv[d][k] for k in (0, 1))
                              for a, b, d in glb.triangles(gltf, binary, prim) for wa, wb, wd in SAMPLES]
                    if not any(rows[min(int(v * h), h - 1)][min(int(u * w), w - 1) * c + c - 1] < 128 for u, v in points):
                        raise glb.Bad(f'mesh {mi}, in the owner\'s colour, has it under none of its faces')
        return gltf, glb.measure(gltf, binary)
    except (glb.Bad, KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        problem(f'models/{rel}: {e}')
        return None


def strikes_of(rig):
    """The manifest's strikes for a rig: by clip, the time its blow lands."""
    return {role: clip['strike'] for role, clip in rig['clips'].items() if 'strike' in clip}


def shots_of(rig):
    """The manifest's shots for a rig: by clip, each a time, the joint the shot leaves from, and what flies (where
    it's not a bottle, the default)."""
    return {role: [{'at': x['at'], 'joint': x['joint'], **({'kind': x['kind']} if 'kind' in x else {})}
                   for x in clip['shots']]
            for role, clip in rig['clips'].items() if clip.get('shots')}


def same(a, b, path, tolerance):
    """Whether two keyed values are the same, a turn's quaternion either way round."""
    if len(a) != len(b):
        return False
    close = all(abs(x - y) <= tolerance for x, y in zip(a, b))
    return close or (path == 'rotation' and all(abs(x + y) <= tolerance for x, y in zip(a, b)))


def check_rigged(rel, entry):
    """A rigged figure is its model bound to the stance's skeleton, with the rig's clips: checks what civ.one's player
    and the static model need of it, adding any problem."""
    path = os.path.join(ROOT, 'models', rel)
    static_rel = rel.split('/', 1)[1]
    try:
        gltf, binary = glb.read(path)
        static, static_bin = glb.read(os.path.join(ROOT, 'models', static_rel))
        rig = entry['rig']
        skins = gltf.get('skins', [])
        if len(skins) != 1:
            raise glb.Bad('it should have one skin')
        nodes = gltf['nodes']
        joints = skins[0]['joints']
        names = [nodes[j].get('name') for j in joints]
        parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
        want = BONES | ({'prop'} if 'prop' in rig else set())
        if len(set(names)) != len(names) or set(names) != want:
            raise glb.Bad(f'its joints should be the stance\'s bones{" and the prop" if "prop" in rig else ""}, each once')
        placed = glb.placed_meshes(gltf)
        meshed = [n for n in nodes if 'mesh' in n]
        if len(placed) != 1 or len(meshed) != 1 or meshed[0].get('skin') != 0 or any(
                k in meshed[0] for k in ('matrix', 'translation', 'rotation', 'scale')):
            raise glb.Bad('it should be one mesh, on a node of its own with the skin and no transform')
        # Bound where the model stands: the same points, normals, texture coordinates, faces and materials.
        prims, static_prims = gltf['meshes'][placed[0][0]]['primitives'], static['meshes'][glb.placed_meshes(static)[0][0]]['primitives']
        if len(prims) != len(static_prims) or gltf.get('materials') != static.get('materials') or \
                gltf.get('textures') != static.get('textures'):
            raise glb.Bad(f'its parts and materials should be models/{static_rel}\'s')
        for (img, simg) in zip(gltf.get('images', []), static.get('images', [])):
            def data(g, b, i):
                v = g['bufferViews'][i['bufferView']]
                return b[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
            if data(gltf, binary, img) != data(static, static_bin, simg):
                raise glb.Bad(f'its images should be models/{static_rel}\'s')
        if len(gltf.get('images', [])) != len(static.get('images', [])):
            raise glb.Bad(f'its images should be models/{static_rel}\'s')
        if any('targets' in p for p in prims) or any('weights' in m for m in gltf.get('meshes', [])):
            raise glb.Bad('it has morph targets, which civ.one\'s map doesn\'t play')
        for p, sp in zip(prims, static_prims):
            if p.get('material') != sp.get('material') or set(p['attributes']) != ATTRIBUTES | SKIN_ATTRIBUTES or \
                    glb.triangles(gltf, binary, p) != glb.triangles(static, static_bin, sp) or any(
                    glb.accessor(gltf, binary, p['attributes'][a]) != glb.accessor(static, static_bin, sp['attributes'][a])
                    for a in ATTRIBUTES):
                raise glb.Bad(f'its mesh should be models/{static_rel}\'s as it stands, with joints and weights')
            ja, wa = (gltf['accessors'][p['attributes'][a]] for a in ('JOINTS_0', 'WEIGHTS_0'))
            if ja.get('count') != gltf['accessors'][p['attributes']['POSITION']].get('count') or wa.get('count') != ja.get('count'):
                raise glb.Bad('its joints and weights should be one to a point')
            if ja.get('type') != 'VEC4' or ja.get('componentType') not in (5121, 5123) or wa.get('type') != 'VEC4' or \
                    wa.get('componentType') != 5126 or ja.get('normalized') or wa.get('normalized'):
                raise glb.Bad('its joints should be whole numbers and its weights floats, four to a point')
            for js, ws in zip(glb.accessor(gltf, binary, p['attributes']['JOINTS_0']),
                              glb.accessor(gltf, binary, p['attributes']['WEIGHTS_0'])):
                if any(j >= len(joints) for j in js) or any(not 0 <= w <= 1 for w in ws) or abs(sum(ws) - 1) > 1e-3:
                    raise glb.Bad('a point\'s joints are out of range, or its weights don\'t add up to one')
                used = [j for j, w in zip(js, ws) if w > 0]
                if len(set(used)) != len(used):
                    raise glb.Bad('a point has two weights on one joint')
        if 'prop' in rig:
            # The prop's part on the prop's joint alone, and no other point on it; the joint a child of its bone.
            prop_j = names.index('prop')
            held = {(p['attributes']['POSITION'], i) for p in [prims[rig['prop']['part']]]
                    for f in glb.triangles(gltf, binary, p) for i in f}
            for p in prims:
                pa = p['attributes']['POSITION']
                for i, (js, ws) in enumerate(zip(glb.accessor(gltf, binary, p['attributes']['JOINTS_0']),
                                                 glb.accessor(gltf, binary, p['attributes']['WEIGHTS_0']))):
                    on = sum(w for j, w in zip(js, ws) if j == prop_j)
                    if ((pa, i) in held and abs(on - 1) > 1e-6) or ((pa, i) not in held and on > 0):
                        raise glb.Bad('the prop\'s part should move with the prop\'s joint alone, and nothing else with it')
            if parent.get(joints[prop_j]) != joints[names.index(rig['prop']['bone'])]:
                raise glb.Bad(f'the prop\'s joint should be a child of {rig["prop"]["bone"]}, which holds it')
            # Its muzzle, where it has one: a node of that name on the prop's joint, placed, with nothing on it.
            muzzles = [i for i, n in enumerate(nodes) if n.get('name') == 'muzzle']
            if 'muzzle' in rig['prop'] and (len(muzzles) != 1 or parent.get(muzzles[0]) != joints[prop_j] or
                                            set(nodes[muzzles[0]]) != {'name', 'translation'}):
                raise glb.Bad('the prop\'s muzzle should be one node, a child of the prop\'s joint, with only its place')
            if 'muzzle' not in rig['prop'] and 'muzzle' not in rig and muzzles:
                raise glb.Bad('it has a muzzle, but its prop has none')
            if muzzles and 'muzzle' in rig['prop']:  # at the end of the prop: as far as it reaches that way from its joint, and on it
                ibm_p = glb.accessor(gltf, binary, skins[0]['inverseBindMatrices'])[prop_j]
                inv_p = [[ibm_p[c * 4 + r] for c in range(4)] for r in range(4)]
                pp = prims[rig['prop']['part']]
                points = glb.accessor(gltf, binary, pp['attributes']['POSITION'])
                pts = [[sum(inv_p[r][c] * v for c, v in enumerate([*points[i], 1])) for r in range(3)]
                       for i in sorted({i for f in glb.triangles(gltf, binary, pp) for i in f})]
                m = nodes[muzzles[0]]['translation']
                length = math.hypot(*m)
                reach = max(sum(a * b for a, b in zip(x, m)) for x in pts) / max(length, 1e-9)
                bound = [[inv_p[c][r] for c in range(3)] for r in range(3)]  # the joint's turn as bound: inv_p's, undone
                way_m = [sum(bound[r][c] * m[c] for c in range(3)) for r in range(3)]
                if abs(reach - length) > 0.02 or min(math.dist(x, m) for x in pts) > 0.08 or \
                        sum(a * b for a, b in zip(way_m, rig['prop']['muzzle'])) <= 0:
                    raise glb.Bad('the prop\'s muzzle should be at its end, as far as the prop reaches that way, the '
                                  'end its muzzle way points to')
        muzzles = [i for i, n in enumerate(nodes) if n.get('name') == 'muzzle']
        if 'muzzle' in rig:  # the rig's own: one node on the joint of the bone that carries it, placed, nothing on it
            if len(muzzles) != 1 or parent.get(muzzles[0]) != joints[names.index(rig['muzzle']['bone'])] or \
                    set(nodes[muzzles[0]]) != {'name', 'translation'}:
                raise glb.Bad(f'its muzzle should be one node, a child of {rig["muzzle"]["bone"]}\'s joint, with only its '
                              'place')
        elif 'prop' not in rig and muzzles:
            raise glb.Bad('it has a muzzle, but its rig gives none')
        # Standing as bound: each joint where its inverse bind matrix undoes.

        def world(i, local=None):
            m = (local or {}).get(i) or glb.local_matrix(nodes[i])
            return m if i not in parent else glb.multiply(world(parent[i], local), m)

        ibm = glb.accessor(gltf, binary, skins[0]['inverseBindMatrices'])
        for j, inv in zip(joints, ibm):
            m = glb.multiply(world(j), [[inv[c * 4 + r] for c in range(4)] for r in range(4)])
            if any(abs(m[r][c] - (r == c)) > 1e-4 for r in range(4) for c in range(4)):
                raise glb.Bad(f'joint {nodes[j].get("name")} is not where it is bound, so the figure would not stand as models/{static_rel} does')
        if 'muzzle' in rig and math.dist([world(muzzles[0])[r][3] for r in range(3)], rig['muzzle']['at']) > 1e-3:
            raise glb.Bad('its muzzle should be where the rig says, as the figure stands')
        # The clips: by role, each keying the same joints' turns and places, from 0 to its length.
        anims = {a.get('name'): a for a in gltf.get('animations', [])}
        posed = posing(rig)
        if set(anims) != set(rig['clips']) or len(anims) != len(gltf.get('animations', [])):
            raise glb.Bad(f'its clips should be {sorted(rig["clips"])}, each once')
        keyed = None
        for role, anim in anims.items():
            length = rig['clips'][role]['length']
            got = set()
            targets = [(c['target'].get('node'), c['target'].get('path')) for c in anim['channels']]
            if len(set(targets)) != len(targets):
                raise glb.Bad(f'clip {role} keys one joint\'s one property twice')
            for ch in anim['channels']:
                sampler = anim['samplers'][ch['sampler']]
                node, path_ = ch['target'].get('node'), ch['target'].get('path')
                if node not in joints or sampler.get('interpolation', 'LINEAR') != 'LINEAR':
                    raise glb.Bad(f'clip {role} moves a node that is not a joint, or not linearly')
                times = [t[0] for t in glb.accessor(gltf, binary, sampler['input'])]
                if times[0] != 0 or abs(times[-1] - length) > 1e-4 or any(b <= a for a, b in zip(times, times[1:])):
                    raise glb.Bad(f'clip {role} should run from 0 to its length, {length} s')
                ia = gltf['accessors'][sampler['input']]
                if ia.get('min') != [times[0]] or ia.get('max') != [times[-1]]:
                    raise glb.Bad(f'clip {role} has times without their least and most (min and max), as glTF asks')
                values = glb.accessor(gltf, binary, sampler['output'])
                if any(not math.isfinite(v) for value in values for v in value) or (path_ == 'rotation' and any(
                        abs(math.sqrt(sum(v * v for v in q)) - 1) > 1e-3 for q in values)):
                    raise glb.Bad(f'clip {role} has a value that is not a number, or a turn that is not a unit quaternion')
                if path_ == 'translation' and nodes[node].get('name') not in ('hips', *(('prop',) if posed else ())) or \
                        path_ == 'scale' and nodes[node].get('name') != 'prop':
                    raise glb.Bad(f'clip {role} moves {nodes[node].get("name")} ({path_}); only the root\'s place, and the '
                                  'prop\'s size (and its place, where a key holds or grips it), are keyed beside the turns')
                held = any(k.get('hold') or k.get('grip') for k in rig['clips'][role]['keys'])
                if path_ == 'translation' and nodes[node].get('name') == 'prop' and not held and not all(
                        same(v, nodes[node].get('translation', (0, 0, 0)), path_, 1e-5) for v in values):
                    raise glb.Bad(f'clip {role} moves the prop on the hand, though none of its keys holds or grips it')
                if path_ == 'rotation' and any(
                        abs(sum(x * y for x, y in zip(a, b))) < math.cos(math.radians(45)) for a, b in zip(values, values[1:])):
                    raise glb.Bad(f'clip {role} turns {nodes[node].get("name")} by over 90° from one frame to the next, '
                                  'which a player may play the long way round')
                if path_ == 'rotation' and nodes[node].get('name') == 'prop' and not held and not all(
                        same(v, nodes[node].get('rotation', (0, 0, 0, 1)), path_, 1e-5) for v in values):
                    raise glb.Bad(f'clip {role} turns the prop in the hand, where it should stay as it is held')
                if path_ == 'scale':
                    out = [x for x in rig['clips'][role].get('shots', []) if x.get('kind', 'bottle') == 'bottle']
                    if any(not same(v, (1, 1, 1), path_, 1e-6) for t, v in zip(times, values)
                           if not any(x['at'] + 1e-4 < t < x['back'] - 1e-4 for x in out)):
                        raise glb.Bad(f'clip {role} should keep the prop in the hand, its size 1, but while it is thrown')
                if path_ == 'translation' and nodes[node].get('name') == 'hips':
                    reach = max(math.hypot(v[0] - values[0][0], v[2] - values[0][2]) for v in values)
                    if reach > (0.25 if role in LOOPS else 2.5):
                        raise glb.Bad(f'clip {role} moves the figure {reach:.2f} m across the ground; clips play in '
                                      'place (a loop within 0.25 m, a clip played once within 2.5 m)')
                if path_ == 'scale' and nodes[node].get('name') == 'prop' and not (
                        same(values[0], (1, 1, 1), path_, 1e-6) and same(values[-1], (1, 1, 1), path_, 1e-6)):
                    raise glb.Bad(f'clip {role} should start and end with the prop in the hand, its size 1')
                rest = nodes[node].get(path_, {'rotation': (0, 0, 0, 1), 'scale': (1, 1, 1)}.get(path_, (0, 0, 0)))
                if role in ONCE and not same(values[0], rest, path_, 1e-4):
                    raise glb.Bad(f'clip {role} should start where the figure stands')
                if role in LOOPS and not same(values[0], values[-1], path_, 1e-5):
                    raise glb.Bad(f'clip {role} should end where it starts, as it loops')
                got.add((nodes[node]['name'], path_))
            for x in rig['clips'][role].get('shots', []):
                if x['joint'] not in names and not (x['joint'] == 'muzzle' and ('muzzle' in rig or 'muzzle' in rig.get('prop', {}))):
                    raise glb.Bad(f'clip {role} has a shot from {x["joint"]}, which is not a joint or a muzzle')
                if x.get('kind', 'bottle') == 'bottle':
                    ch = next((c for c in anim['channels'] if nodes[c['target']['node']].get('name') == 'prop' and
                               c['target'].get('path') == 'scale'), None)
                    sampler = anim['samplers'][ch['sampler']] if ch else None
                    times = [t[0] for t in glb.accessor(gltf, binary, sampler['input'])] if sampler else []
                    sizes = glb.accessor(gltf, binary, sampler['output']) if sampler else []
                    def size_at(when):
                        k = max(i for i, t in enumerate(times) if t <= when)
                        if k == len(times) - 1:
                            return sizes[k]
                        u = (when - times[k]) / (times[k + 1] - times[k])
                        return [a + u * (b - a) for a, b in zip(sizes[k], sizes[k + 1])]
                    steps = int((x['back'] - 0.21 - x['at'] - 0.01) / 0.005)
                    if not sizes or any(abs(v) > 1e-4 for i in range(steps + 1) for v in size_at(x['at'] + 0.01 + 0.005 * i)):
                        raise glb.Bad(f'clip {role} should hide the prop (its size 0) after it is thrown at {x["at"]} s')
                    if any(abs(v - 1) > 1e-4 for when in (x['at'], x['back']) for v in size_at(when)):
                        raise glb.Bad(f'clip {role} should have the prop whole in the hand as it\'s thrown at {x["at"]} s, '
                                      f'and again by {x["back"]} s')
            if keyed is None:
                keyed = got
            if got != keyed or not {(n, 'rotation') for n in want} | {('hips', 'translation')} | (
                    {('prop', 'translation')} if posed else set()) <= got:
                raise glb.Bad(f'clip {role} should key every joint\'s turn and the root\'s place (and the prop\'s, where a '
                              'key holds or grips it), as every clip does')
    except (glb.Bad, KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        problem(f'models/{rel}: {e}')


def main():
    roster = json.load(open(os.path.join(ROOT, 'roster.json'), encoding='utf-8'))
    manifest = json.load(open(os.path.join(ROOT, 'manifest.json'), encoding='utf-8'))

    # The roster.
    keys_ok('roster', roster, TOP)
    s = roster.get('set', {})
    set_licence = check_licence('roster.set', s.get('licence'))
    if not (isinstance(s.get('id'), str) and NAME.match(s['id']) and s.get('name') and s.get('licence', {}).get('attribution')):
        problem('roster.set: needs an id, a name and a licence with its attribution')
    if not number(roster.get('scale'), 0) or not isinstance(roster.get('date'), str):
        problem('roster: needs a scale over 0 and a date')
    gen = roster.get('generated', {})
    if check_licence('roster.generated', gen.get('licence')) != 'CC0 1.0' or gen.get('author') != 'dom111':
        problem('roster.generated: the generated models\' credit is dom111\'s, CC0 1.0')
    for f in ('work', 'url'):
        if not isinstance(gen.get(f), str) or not gen[f]:
            problem(f'roster.generated: needs {f}, as the manifest\'s credits need it')
    sources = roster.get('sources', {})
    for k, src in sources.items():
        where = f'roster.sources.{k}'
        if k == 'split':
            problem(f'{where}: split names the piece a model splits off, so it can\'t name a source')
        if not keys_ok(where, src, SOURCE):
            continue
        lic = check_licence(where, src.get('licence'))
        if set_licence and lic and lic not in ALLOWED[set_licence]:
            problem(f'{where}: {lic} is not allowed in a {set_licence} set')
        for f in ('work', 'author', 'url', 'file'):
            if not isinstance(src.get(f), str) or not src[f]:
                problem(f'{where}: needs {f}')
        if not isinstance(src.get('sha256'), str) or not SHA.match(src['sha256']):
            problem(f'{where}: needs the SHA-256 of the file it was built from')
        if src.get('generated') and (lic != 'CC0 1.0' or not src.get('prompt') or src.get('ai') is not True):
            problem(f'{where}: a generated source is CC0 1.0, gives its prompt and says it is made with AI ("ai": true)')
        if 'ai' in src and not isinstance(src['ai'], bool):
            problem(f'{where}: ai should be true or false')
    models = roster.get('models', {})
    drawn = {}
    for mid, e in models.items():
        where = f'roster.models.{mid}'
        if not NAME.match(mid):
            problem(f'{where}: a model is named with lowercase letters, digits and dashes')
        check_build_entry(where, e, MODEL, sources)
        if not (isinstance(e.get('units'), list) and e['units']):
            problem(f'{where}: units should be a list of unit types')
        for u in e.get('units', []):
            if u not in UNITS:
                problem(f'{where}: {u!r} is not one of the engine\'s unit types')
            if u in drawn:
                problem(f'{where}: {u} is already drawn by {drawn[u]}')
            drawn[u] = mid
        if not whole(e.get('budget')) or ('scale' in e and not number(e['scale'], 0)):
            problem(f'{where}: needs a budget (a whole number) and any scale over 0')
    for rel, e in roster.get('extras', {}).items():
        check_build_entry(f'roster.extras.{rel}', e, EXTRA, sources)
    rigged = {f'rigged/{mid}.glb': mid for mid, e in models.items() if 'rig' in e}
    for rel in sorted(set(rigged) & set(roster.get('extras', {}))):
        problem(f'models/{rel}: is both an extra and a rigged model\'s figure')
    if problems:
        return

    # The manifest.
    credits = expected_credits(roster)
    head = {'schema': 1, 'kind': 'models', 'id': s['id'], 'name': s['name'], 'source': 'hosted', 'licence': s['licence'],
            'credits': credits, 'scale': roster['scale']}
    for k, v in head.items():
        if manifest.get(k) != v:
            problem(f'manifest: {k} should be {json.dumps(v)[:120]}')
    for k in sorted(set(manifest) - set(head) - {'models', 'names'}):
        problem(f'manifest: says {k!r}, which build.py does not write')
    names = {u: mid for mid, e in models.items() for u in e['units']}
    if manifest.get('names') != {'unit': names}:
        problem('manifest: names.unit should map each unit type to the model the roster says')
    mm = manifest.get('models', {})
    for mid in sorted(set(mm) ^ set(models)):
        problem(f'manifest: model {mid} is in only one of the manifest and the roster')

    # The files.
    listed = {f'{mid}.glb' for mid in models} | set(roster.get('extras', {})) | set(rigged)
    present = set()
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'models')):
        for f in files:
            present.add(os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, 'models')).replace(os.sep, '/'))
    for rel in sorted(present - listed):
        problem(f'models/{rel}: is neither a model in the manifest nor an extra in the roster')
    for rel in sorted(listed - present):
        problem(f'models/{rel}: is missing')
    for rel in sorted(listed & present):
        if rel in rigged:
            entry = models[rigged[rel]]
            got = check_file(rel, skinned_ok=True, texture=entry['cut']['texture'], owner='owner' in entry, posed=True)
            if got is None:
                continue
            if got[0].get('asset', {}).get('extras') != expected_extras(roster, entry) or \
                    got[0].get('asset', {}).get('copyright') != expected_copyright(roster, entry):
                problem(f'models/{rel}: its asset.extras and asset.copyright should be its model\'s, as build.py writes them')
            if f'{rigged[rel]}.glb' in present:
                check_rigged(rel, entry)
            continue
        mid = rel[:-4] if rel in {f'{m}.glb' for m in models} else None
        entry = models[mid] if mid else roster['extras'][rel]
        got = check_file(rel, skinned_ok=mid is None, texture=entry['cut']['texture'], owner='owner' in entry,
                         posed='stance' in entry)
        if got is None:
            continue
        gltf, measured = got
        if gltf.get('asset', {}).get('extras') != expected_extras(roster, entry):
            problem(f'models/{rel}: its asset.extras should hold its credit, licence and changes as build.py writes them')
        if gltf.get('asset', {}).get('copyright') != expected_copyright(roster, entry):
            problem(f'models/{rel}: its asset.copyright should hold its credit as build.py writes it')
        if mid is None:
            continue
        m = mm.get(mid, {})
        want = {'file': f'models/{rel}', 'sha256': hashlib.sha256(open(os.path.join(ROOT, 'models', rel), 'rb').read()).hexdigest(),
                'extent': measured['extent'], 'triangles': measured['triangles'],
                'from': [credit_of(roster, k)['url'] for k in keys_of(entry)], 'made': entry['made']}
        if 'scale' in entry:
            want['scale'] = entry['scale']
        if measured['animations']:
            want['animations'] = measured['animations']
        if 'rig' in entry:
            rp = os.path.join(ROOT, 'models', 'rigged', rel)
            want['rigged'] = {'file': f'models/rigged/{rel}',
                              'sha256': hashlib.sha256(open(rp, 'rb').read()).hexdigest() if os.path.exists(rp) else None,
                              'clips': {r: r for r in entry['rig']['clips']}}
            shots = shots_of(entry['rig'])
            if shots:
                want['rigged']['shots'] = shots
            strikes = strikes_of(entry['rig'])
            if strikes:
                want['rigged']['strikes'] = strikes
        for k in sorted(set(want) | set(m)):
            if m.get(k) != want.get(k):
                problem(f'manifest: {mid}.{k} should be {json.dumps(want.get(k))[:100]}, as its file and the roster say')
        if measured['triangles'] > entry['budget']:
            problem(f'models/{rel}: {measured["triangles"]} triangles, over its budget of {entry["budget"]}')
        stage, ext = entry['stage'], measured['extent']
        if abs(measured['lowest'] + stage.get('draught', 0)) > 0.002:
            where = f'floats {-measured["lowest"]} deep' if measured['lowest'] < 0 else f'stands {measured["lowest"]} above the ground'
            problem(f'models/{rel}: {where}, not ' + (f'{stage["draught"]} deep' if 'draught' in stage else 'on it'))
        if 'prop' not in entry:
            reach = ext['height'] - measured['lowest'] if stage['measure'] == 'height' else ext['along'][1] - ext['along'][0]
            if abs(reach - stage['size']) > 0.005 * stage['size'] + 0.002:
                problem(f'models/{rel}: is {reach:.3f} {"tall" if stage["measure"] == "height" else "long"}, not {stage["size"]}')
            for axis in ('across', 'along'):
                if abs(ext[axis][0] + ext[axis][1]) > 0.004:
                    problem(f'models/{rel}: is not centred {axis} ({ext[axis]})')

    # The credits.
    path = os.path.join(ROOT, 'CREDITS.md')
    if not os.path.exists(path) or open(path, encoding='utf-8', newline='').read() != credits_md(roster, credits):
        problem('CREDITS.md: should list the credits as build.py writes them')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:  # a roster or manifest too broken to check further
        problem(f'stopped: {e!r}')
    for p in problems:
        print(p)
    print(f'{len(problems)} problem(s)' if problems else 'All well.')
    sys.exit(1 if problems else 0)
