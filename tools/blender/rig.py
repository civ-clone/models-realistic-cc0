"""rig.py : rigs a posed figure for civ.one's 3D map, as its roster entry's `rig` says: binds it to the skeleton
stance.py posed it with, and gives it clips (idle, move, fight, die and the like) made from key poses.

Args (after --): POSED.glb WEIGHTS.json STANCE.json RIG.json OUT.glb. POSED is the figure as stance.py left it, and
WEIGHTS what it wrote of its points' weights then. OUT is POSED with a skin and the clips; its mesh, materials and
textures are POSED's, untouched, so it stands as POSED does until a clip moves it.

- **The skeleton** is stance.py's, bound where the stance put it: each bone a joint (named as the bone), under a root
  node `skeleton`. Each point keeps the four weights stance.py gave it that are biggest, shared again to add up to one,
  but for a leg's above its hip, which fade out (see LEG_REACH).
- **`prop`:** a part (`part`, counted as stance.py counts them) on a joint of its own, `prop`, a child of the bone
  that holds it (`bone`), with its origin at the middle of the part as it stands (so a shot from it leaves from
  there). Unless a key holds it otherwise (`hold`, below) it stays in the hand as the stance holds it: only its size
  changes, as a shot throws it. Its long way and ends are its own: the line its surface lies along most, its top the
  end towards `muzzle` (a way [x, y, z], within 45 degrees of its length), and its back, across that, the side facing
  `back` (a way, as the stance holds it, nearer across it than along it: a rifle's sights; its shape can't say). A prop
  a key holds or grips needs both. With `muzzle`, a
  node of that name (not a joint) sits at the middle of its top, a child of the prop's joint, for shots to leave
  from. With `grounded` false, it's left out of standing the figure on the ground (a rifle's butt by a foot would
  lift him as the hand moves), and the report says how far it went below. With `slides` false, the hand that holds
  it can't slide along it (a pistol grip): as a hold eases, the prop moves with the hand instead (below). (A hold's
  `hand` still moves the hand along it.)
- **`muzzle`:** for a figure whose weapon isn't a prop of its own but part of him, held whole by a bone as its stance
  says (a slung gun his chest carries, say): a node of that name (not a joint), a child of that bone's joint
  (`bone`), at `at` ([x, y, z], as the posed figure stands in the file), for shots to leave from. A rig has one
  muzzle at most: this, or its prop's.
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
    a foot is put down and lifted smoothly: its ankle goes straight from where the keys put it to where it's planted,
    and the leg is turned partly as the keys turn it, so a step is clean only if the keys hold the foot clear of the
    ground before it's put down and after it's lifted, and keep a planted leg about where it's planted. The figure
    is still stood on its lowest point, so nothing else should go lower than a planted foot (the report's `planted`
    says how far a planted ankle ends up from its place: a few millimetres either way as the legs bend, more if
    something else went below the ground);
  - `ease`: how the key is met: `stop` (easing to it where the movement turns back, on through it where it doesn't),
    `through` (on at speed, as an arm at a throw's release, which may overshoot), `hit` (arriving at twice the speed
    of a straight line from the key before, as a body hitting the ground, and leaving from rest), or `snap` (leaving
    the key before at twice that speed, even one hit, as a body a shot strikes, and met as `stop` meets a key). Feet
    are put down and lifted as `stop` whatever the key's ease;
  - `late`: bones that meet the key after the rest of the figure, by a time in seconds, as arms and a head reach the
    ground after the body they hang from;
  - `hold`: the prop held as the key says rather than as the hand holds it: its top pointing `aim`, its back facing
    `up` (as near as it can, across its length), and its foot (the end away from its top) at `butt`, [x, y, z], as the
    posed figure stands in the file; all carried by the chest as it turns and leans (a rifle at the shoulder). The
    hand that holds it (the prop's `bone`, a hand) holds it at `hand`, a share of the way from its foot to its top (0
    to 1; where it holds it in the stance, without one), its arm bent to reach it. How much a key holds it is eased
    on and off as `plant` eases a foot, and where it holds it goes from key to key as the keys' eases say;
  - `grip`: the other hand on the prop (`L` or `R`), at a share of the way from its foot to its top, its arm bent to
    reach it. Eased on and off as `plant` is.
  At a key that holds or grips the prop (at the frame nearest it), a hand on it is turned as its forearm carries it
  (as the stance turns it on the forearm), then the least that lays it along the prop (towards its top or its foot,
  whichever is nearer; but at a hold next to a key that doesn't hold, the way the stance lays the hand that holds
  it). Between keys, it turns from one key's turn to the next's as the chest carries it, easing out of one and into
  the next, as an arm brings a hand up (where the two lay it opposite ways, it turns end for end on the prop over
  those frames, as a hand changes its grip), and the prop passes it as it does the hand that holds it in the stance
  (the other: through its middle). The hand that holds the prop eases from as the stance holds it as the hold eases
  on, and back as it eases off (off the prop's line by a little as it does), its elbow's bend eased with it from as
  the keys bend it to as the full hold would (a full hold out of the arm's reach eased to all the same): the hand
  slides along the prop (by up to SLIDE, and never past its ends) to where the wrist is as far from the shoulder as
  that bend puts it, or where the prop's line doesn't come that near, to where it comes nearest; so a nearly
  straight arm bends steadily rather than snapping. A prop whose `slides` is false moves with the hand instead,
  straight towards or away from the shoulder (by up to SLIDE), the hand staying where the keys' holds put it on the
  prop. Where that slide or move would change by more than SLIDE_STEP from one frame to the next (a hold eased on
  or off in too few frames, or the prop passing the shoulder fast as it eases), or the slide would jump by more than
  GRIP from one side of where the shoulder comes nearest the prop's line to the other, the build fails. An arm's
  elbow points the way the keys point it.
  Each clip may give bones a `lag` in seconds: they turn as they would that much earlier (in a clip that plays once,
  less and less towards its end, so it ends as it would without), so a movement passes from the body out to the limbs
  and head.

  Between keys each bone turns smoothly, on a curve through them that doesn't overshoot them (but for a key met
  `through`): it eases to a stop at a key where it turns back, where two keys are the same, and at the ends of a clip
  that plays once, but for a last key hit, a second key snapped to, and `through` there, which is `stop`. A clip that
  plays once starts at the stance, as the key at 0 must be (it may plant feet, but only where they stand, so they
  don't slide as the clip starts); a loop's last frame is its first, and its first key has no late bones. The figure
  is stood on the ground in every frame, by its lowest point (the prop's included, at its size, unless it isn't
  `grounded`), as stance.py stands it.
  - `shots`, in a clip: where a shot leaves the figure, for the map to draw: each a time (`at`), the joint it
    leaves from (`joint`: the prop, or the `muzzle`; three.js renames joints whose names have a dot, so the bones'
    can't be found by name) and what flies (`kind`: bottle, the default, arrow, bullet or shell). The map reads the
    joint's place then, and draws it. A bottle is the prop, thrown: it leaves from the prop, which is gone from 1 ms
    after `at` until 0.2 s before `back` (at least 0.25 s after `at`), growing back in the hand over those 0.2 s.
    The rest leave the prop (or the figure) where it is.
  - `strike`, in a clip played once with no shots (a melee fight's, for one): the time its blow lands, for the map
    to time the blow and the attacker's lunge by. Nothing in the figure changes with it.

Every clip keys every joint's turn, the root's place, and the prop's size (and, where any key holds or grips it, the
prop's place on the hand), so none leaves a joint as another left it. Clips are sampled at about FPS frames a second
(a whole number of frames over each clip, and keys at least a frame apart, so each shows), played
between frames by turning each joint linearly. It prints a report: for each clip, its frames, how far its first frame
is from the bind, the most any edge of the figure grows and when, how many faces grow over 1.4 times, the most weight
any point lost to the four kept, the furthest a fully planted ankle ends up from its place (`planted`), and where they
apply, how far an ungrounded prop went below the ground (`below`) and the furthest each hand ends up from where it
holds the prop (`grip`, by hand: where it fully holds or grips it, from its place there; where the hand that holds it
eases on or off, from the prop's line; more than a centimetre or so says the prop was out of the arm's reach, and over
GRIP fails the build), the most each hand on it bends off the line of its forearm (`wrist`, in degrees), and the least its elbow
bends there (`elbow`: near 0, the arm is at full reach, and whips as it bends). Where a hold eases, it gives `slide`:
the most the hand that holds the prop slid along it (or moved it, if it doesn't slide), its largest change from one
frame to the next, how many frames it was `capped` (held back at SLIDE or the prop's ends, or the prop's line not
coming as near the shoulder as the eased bend needs), where the elbow falls short of the eased bend (as far as it
would without the slide, at worst), and how many times it `flips` from one side of where the shoulder comes nearest
the prop's line to the other (over GRIP in a frame fails the build).
With RIG_FRAMES set to a folder, it also writes each clip's points frame by frame (`<clip>.npy`) and its feet
(`<clip>-feet.npz`: their plant weights and places, the joints, and how far each frame was lowered to the ground),
to check a player or a clip against.
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
KEY = {'at', 'aim', 'twist', 'turn', 'slide', 'ease', 'hips', 'plant', 'late', 'hold', 'grip'}
KINDS = ('bottle', 'arrow', 'bullet', 'shell')  # what a shot is, for the map to draw
END = 0.015  # how near its end a prop's points are taken to find the middle of the end
GRIP = 0.02  # the furthest a hand may end up from where it holds a prop, in metres
SLIDE = 0.1  # the furthest a hand slides along a prop (or moves one that doesn't slide), as a hold eases on or off, to
#  ease its elbow's bend, in metres
SLIDE_STEP = 0.05  # the furthest that slide (or move) may change from one frame to the next, in metres
FULL = 0.999  # a hold or grip this near 1 counts as full: the hand on the prop where the key puts it


def number(v, lo=-math.inf):
    return finite([v]) and v > lo


def way(v):
    return finite(v, 3) and 1e-6 < np.linalg.norm(v) < 1e6


def shot_ok(x, rig, length):
    """Whether a shot is a time in the clip, the joint it leaves from, what flies, and (a bottle) when it's back."""
    prop, muzzle = rig.get('prop'), 'muzzle' in rig or 'muzzle' in (rig.get('prop') or {})
    if not (isinstance(x, dict) and (prop or muzzle) and number(x.get('at'), 0) and x['at'] < length):
        return False
    kind = x.get('kind', 'bottle')
    if kind == 'bottle':
        return bool(prop) and x.get('joint') == 'prop' and {'at', 'joint', 'back'} <= set(x) <= {'at', 'joint', 'back', 'kind'}
    joints = (('prop',) if prop else ()) + (('muzzle',) if muzzle else ())
    return kind in KINDS and x.get('joint') in joints and {'at', 'joint'} <= set(x) <= {'at', 'joint', 'kind'}


def read_rig(rig):
    """The rig rule, checked."""
    if not isinstance(rig, dict) or set(rig) - {'prop', 'muzzle', 'clips'} or not isinstance(rig.get('clips'), dict) or not rig['clips']:
        fail('the rig should have clips, and may have a prop or a muzzle')
    prop = rig.get('prop')
    muzzle = rig.get('muzzle')
    if muzzle is not None and not (isinstance(muzzle, dict) and set(muzzle) == {'bone', 'at'} and muzzle['bone'] in BONES
                                   and finite(muzzle['at'], 3)):
        fail('muzzle should be the bone that carries it and where it is (at, [x, y, z], as the posed figure stands)')
    if muzzle is not None and prop is not None and 'muzzle' in prop:
        fail('the rig has a muzzle of its own and its prop has one too: shots leave from one')
    if prop is not None and not (isinstance(prop, dict) and {'part', 'bone'} <= set(prop) <= {'part', 'bone', 'muzzle', 'back', 'grounded', 'slides'}
                                 and prop['bone'] in BONES and isinstance(prop['part'], int) and not isinstance(prop['part'], bool)
                                 and all(way(prop[k]) for k in ('muzzle', 'back') if k in prop)
                                 and all(isinstance(prop.get(k, True), bool) for k in ('grounded', 'slides'))):
        fail('prop should be a part and the bone it follows, and may have a muzzle and a back (ways [x, y, z]) and '
             'grounded (true or false) and slides (true or false)')
    hand = prop['bone'][-1] if prop and prop['bone'] in ('hand.L', 'hand.R') else None
    for role, clip in rig['clips'].items():
        where = f'clip {role}'
        if role not in LOOPS | ONCE:
            fail(f'{where}: a clip is one of {sorted(LOOPS | ONCE)}')
        if not isinstance(clip, dict) or set(clip) - {'length', 'keys', 'shots', 'strike', 'lag'} or \
                not number(clip.get('length'), 0):
            fail(f'{where}: a clip has a length over 0 and keys, and may have shots, a strike and lag')
        if 'strike' in clip and not (number(clip['strike'], 0) and clip['strike'] <= clip['length'] and role in ONCE
                                     and not clip.get('shots')):
            fail(f'{where}: strike should be the time a blow lands, over 0 and up to its length, in a clip played once '
                 'with no shots (a melee fight)')
        keys = clip.get('keys')
        if not isinstance(keys, list) or not keys:
            fail(f'{where}: keys should be a list of poses')
        lag = clip.get('lag', {})
        if not isinstance(lag, dict) or set(lag) - BONES or not all(number(v) and 0 <= v < clip['length'] for v in lag.values()):
            fail(f'{where}: lag should give bones a time from 0 to under the clip\'s length, in seconds')
        turns = []
        for k in keys:
            if not isinstance(k, dict) or set(k) - KEY or not (number(k.get('at')) and k['at'] >= 0):
                fail(f'{where}: each key has a time (at, from 0), and may have aim, twist, turn, slide, ease, hips, plant, '
                     'late, hold and grip')
            if 'hold' in k:
                h = k['hold']
                if not (hand and 'back' in prop and 'muzzle' in prop and isinstance(h, dict) and {'aim', 'up', 'butt'} <= set(h) <= {'aim', 'up', 'butt', 'hand'} and
                        way(h['aim']) and way(h['up']) and finite(h['butt'], 3) and
                        np.linalg.norm(np.cross(h['aim'], h['up'])) > 1e-6 * np.linalg.norm(h['aim']) * np.linalg.norm(h['up']) and
                        ('hand' not in h or (number(h['hand']) and 0 <= h['hand'] <= 1))):
                    fail(f'{where}: hold is for a prop a hand holds, with a muzzle and a back: its aim and up (ways, not the '
                         'same), its butt [x, y, z], and where the hand holds it (hand, 0 to 1)')
            grip = k.get('grip')
            if 'grip' in k and (not (isinstance(grip, dict) and grip and hand and 'muzzle' in prop and 'back' in prop) or set(grip) - ({'L', 'R'} - {hand}) or not all(
                    number(v) and 0 <= v <= 1 for v in grip.values())):
                fail(f'{where}: grip is for a prop a hand holds, with a muzzle and a back: it gives the other hand (L or R) a '
                     'share of the way along it, 0 to 1')
            late = k.get('late', {})
            if not isinstance(late, dict) or set(late) - BONES or not all(number(v) and v >= 0 for v in late.values()):
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
        step = clip['length'] / max(2, int(round(clip['length'] * FPS)))
        if any(b - a < step - 1e-6 for a, b in zip(times, times[1:] + ([times[0] + clip['length']] if role in LOOPS else []))):
            fail(f'{where}: its keys should be at least a frame ({step:.4f} s) apart (in a loop, round from its last to its '
                 'first), so each is played')
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
            if set(keys[0]) - {'at', 'plant'} or not all(v is True for v in keys[0].get('plant', {}).values()):
                fail(f'{where}: a clip that plays once starts at the stance, its first key only a time, and feet planted '
                     'where they stand (true)')
        shots = clip.get('shots', [])
        if not isinstance(shots, list) or not all(shot_ok(x, rig, clip['length']) for x in shots):
            fail(f'{where}: shots should each be a time in the clip (at), the joint they leave from (prop, or a muzzle: '
                 'three.js renames the bones) and what flies (kind: bottle, the default, arrow, bullet or shell); a bottle '
                 'is the prop, thrown, so leaves from it, and says when the prop is back (back)')
        if any(b['at'] <= a['at'] for a, b in zip(shots, shots[1:])):
            fail(f'{where}: its shots should come in order of time')
        thrown = [x for x in shots if x.get('kind', 'bottle') == 'bottle']
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


def whole_at(axis, place, degrees, slide):
    """The whole figure's turn (by degrees about the axis, through the place) and slide ([x, z]), as a 4x4 matrix."""
    out = np.eye(4)
    if axis is not None and degrees:
        r = about(axis, math.radians(degrees))
        out[:3, :3], out[:3, 3] = r, place - r @ place
    out[0, 3] += slide[0]
    out[2, 3] += slide[1]
    return out


def prop_size(clip, length):
    """The prop's size through a clip, as times and sizes: 1 but where a shot throws it, when it's 0 from 1 ms after
    the shot to 0.2 s before it's back, then grows back."""
    times, sizes = [0.0], [1.0]
    for x in clip.get('shots', []):
        if x.get('kind', 'bottle') == 'bottle':
            times += [x['at'], x['at'] + 0.001, x['back'] - 0.2, x['back']]
            sizes += [1.0, 0.0, 0.0, 1.0]
    if times[-1] < length:
        times.append(float(length))
        sizes.append(1.0)
    return times, sizes


def prop_frame(pos, tri, top_way, back_way):
    """A prop's own long way and ends, from its faces (tri, into pos): the line its surface lies along most, its top
    the end towards top_way; across that, its back, the side facing back_way (or any way across, without one); and the
    middles of its ends (its foot and top), each at the very end."""
    a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    d = (a + b + c) / 3
    centre = (area[:, None] * d).sum(axis=0) / area.sum()
    d -= centre
    vecs = np.linalg.eigh((d * area[:, None]).T @ d)[1]
    along = vecs[:, 2] if vecs[:, 2] @ top_way >= 0 else -vecs[:, 2]
    if abs(along @ top_way) < math.sqrt(0.5) * np.linalg.norm(top_way):
        fail('prop: its muzzle should point along it, nearer its length than across it')
    if back_way is not None and abs(back_way @ along) > math.sqrt(0.5) * np.linalg.norm(back_way):
        fail('prop: its back should lie across its length, nearer across it than along it')
    back = vecs[:, 1] if back_way is None else back_way - (back_way @ along) * along
    back = back / np.linalg.norm(back)
    points = pos[np.unique(tri)]
    t = (points - centre) @ along
    ends = []
    for end, near in ((t.min(), t < t.min() + END), (t.max(), t > t.max() - END)):
        ring = points[near].mean(axis=0)
        ends.append(ring + along * (end - (ring - centre) @ along))
    return along, back, ends[0], ends[1]


def frame_of(along, back):
    """The turn whose columns are along, back and the way across both."""
    return np.stack([along, back, np.cross(along, back)], axis=1)


def held_frame(h):
    """The turn a hold puts a prop's own frame (its long way and back) at: along its aim, its back as near up as it
    can be."""
    a = np.array(h['aim'], dtype=float)
    a /= np.linalg.norm(a)
    u = np.array(h['up'], dtype=float)
    u -= (u @ a) * a
    return frame_of(a, u / np.linalg.norm(u))


def bend_arm(skeleton, rot, moved, shift, side, wrist, hand, weight):
    """Bends an arm (side L or R) so its wrist is at wrist (as the file stands, before the whole figure's turn), its
    elbow the way the keys bend it, its hand turned to hand (world); blended with the arm as it was by weight. Returns
    how far the wrist ends up from wrist."""
    ua, fa, hd = (f'{b}.{side}' for b in ('upper_arm', 'forearm', 'hand'))
    a, b = (np.linalg.norm(skeleton[x][1] - skeleton[x][0]) for x in (ua, fa))
    shoulder, elbow_k = moved[ua] - shift, moved[fa] - shift
    pole = elbow_k - shoulder
    u = wrist - shoulder
    u = u / max(float(np.linalg.norm(u)), 1e-9)
    if np.linalg.norm(pole - (pole @ u) * u) < 0.01:  # a straight arm gives no way to bend it: down and out, then
        pole = rot['chest'] @ np.array([0.5 if side == 'L' else -0.5, -1.0, 0.0])
    elbow, reached = reach(shoulder, wrist, a, b, pole)
    r_ua = turn(rot[ua] @ (skeleton[ua][1] - skeleton[ua][0]), elbow - shoulder) @ rot[ua]
    carried = r_ua @ rot[ua].T @ rot[fa]
    r_fa = turn(carried @ (skeleton[fa][1] - skeleton[fa][0]), reached - elbow) @ carried
    for n, r in ((ua, r_ua), (fa, r_fa), (hd, hand)):
        rot[n] = blend(rot[n], r, weight) if weight < 1 else r
    for n, p in ((fa, ua), (hd, fa)):
        moved[n] = rot[p] @ (skeleton[n][0] - skeleton[p][0]) + moved[p]
    return float(np.linalg.norm(moved[hd] - shift - wrist))


def filled(values, loop):
    """Each key's value, or where it has none, the one before's that has (round from the end, in a loop), else the
    next's: so a hold or grip eases off as it was, and on as it will be."""
    have = [i for i, v in enumerate(values) if v is not None]
    out = []
    for i, v in enumerate(values):
        if v is None and have:
            before = [j for j in have if j < i]
            v = values[before[-1] if before else have[-1] if loop else have[0]]
        out.append(v)
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
    # Whether any key holds the prop or grips it: if so, every clip keys its place on the hand.
    posing = any('hold' in k or 'grip' in k for c in rig['clips'].values() for k in c['keys'])
    if rig.get('prop') and (posing or 'muzzle' in rig['prop']):  # its own frame, where it's held or shot from
        tri = start[p['attributes']['POSITION']] + np.array(glb.triangles(gltf, binary, p), dtype=np.int64)
        along, back, foot, top = prop_frame(pos, tri, np.array(rig['prop'].get('muzzle', [0, 1, 0]), dtype=float),
                                            np.array(rig['prop']['back'], dtype=float) if 'back' in rig['prop'] else None)
        span = float((top - foot) @ along)
        own_frame = frame_of(along, back)
    if posing:
        bone = rig['prop']['bone']
        hand_side = bone[-1]
        prop_slides = rig['prop'].get('slides', True)  # whether the hand that holds it may slide along it, or moves it
        hi = names.index(bone)
        tip = rot_s[bone] @ (skeleton[bone][1] - skeleton[bone][0])
        holds_at = float((bind[hi, :3, 3] + tip / 2 - foot) @ along) / span  # where the hand holds it, its middle
        prop_inv = np.linalg.inv(bind[nb])
        stance_lay = 1.0 if tip @ along >= 0 else -1.0  # the way the stance lays its hand along the prop
        chest_bind = np.linalg.inv(bind[names.index('chest')])
        # Where the prop's line passes each hand, from its wrist, as the skeleton stands unposed: the hand that holds
        #  it as the stance holds it; the other at its middle.
        near = {hand_side: rot_s[bone].T @ (foot + holds_at * span * along - bind[hi, :3, 3])}
        near['L' if hand_side == 'R' else 'R'] = (lambda b: (skeleton[b][1] - skeleton[b][0]) / 2)(
            f'hand.{"L" if hand_side == "R" else "R"}')

    def hold_hand(rot, moved, side, prop_m, share, weight, lay=None):
        """Bends an arm so its hand holds the prop share of the way along it: the hand turned as its forearm carries
        it (as the stance turns it on the forearm), then the least that lays it along the prop, towards its top (lay
        1) or its foot (-1; without a lay, whichever is nearer), and placed so the prop's line passes it as `near`
        says; the arm blended in by weight. Returns the hand's place and turn (4x4)."""
        fa, hd = f'forearm.{side}', f'hand.{side}'
        on = rot_s[fa].T @ rot_s[hd]
        bone_v = skeleton[hd][1] - skeleton[hd][0]
        way = prop_m[:3, :3] @ bind[nb, :3, :3].T @ along
        at = (prop_m @ prop_inv @ np.append(foot + share * span * along, 1))[:3]
        trial = dict(rot)  # a first try, to see where the forearm goes
        for r_, m_, w_ in ((trial, dict(moved), 1.0), (rot, moved, weight)):
            nat = trial[fa] @ on
            d = nat @ bone_v
            hand_r = turn(d, way if (d @ way >= 0 if lay is None else lay > 0) else -way) @ nat
            wrist = at - hand_r @ near[side]
            bend_arm(skeleton, r_, m_, shift, side, wrist, hand_r, w_)
        there = np.eye(4)
        there[:3, :3], there[:3, 3] = hand_r, wrist
        return there

    def mix(a, b, w):
        """The place and turn (4x4) w of the way from a to b."""
        out = np.eye(4)
        out[:3, :3] = blend(a[:3, :3], b[:3, :3], w) if 0 < w < 1 else (a if w <= 0 else b)[:3, :3]
        out[:3, 3] = a[:3, 3] + w * (b[:3, 3] - a[:3, 3])
        return out
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
        turned = [k['turn'] for k in keys if 'turn' in k]
        axis, place = ((np.array(turned[0]['axis'], dtype=float), np.array(turned[0]['about'], dtype=float)) if turned
                       else (None, None))
        for k in keys:
            rot = key_pose(k)
            local_q.append([quat(rot[n] if parents[n] is None else rot[parents[n]].T @ rot[n]) for n in names])
            hips_off.append(k.get('hips', [0, 0, 0]))
            moved = {}
            for n in names:
                p = parents[n]
                moved[n] = heads[n] + np.array(hips_off[-1]) if p is None else rot[p] @ (heads[n] - heads[p]) + moved[p]
            weights.append([1.0 if s in k.get('plant', {}) else 0.0 for s in SIDES])
            # Where each ankle is at the key, as the ground sees it: where it's planted, or (a foot the key doesn't
            #  plant) where the keys put it, the whole figure turned and slid as the key says.
            whole = whole_at(axis, place, float(k.get('turn', {}).get('degrees', 0)), k.get('slide', [0, 0]))
            row = []
            for s in SIDES:
                v = k.get('plant', {}).get(s)
                stand = moved_s[f'foot.{s}']  # the ankle as it stands
                free = whole[:3, :3] @ (moved[f'foot.{s}'] - shift) + whole[:3, 3] + shift
                row += list(free if v is None else stand if v is True else [v[0] + shift[0], stand[1], v[1] + shift[2]])
            targets.append(row)
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
        if posing:
            # The holds: each key's turn of the prop from as the stance holds it, its butt, and where the hand holds
            #  it, eased from key to key (a key without a hold as the hold before it, so it eases off as it was); and
            #  how much each key holds it, eased as feet are put down. The grips likewise.
            hold = filled([k.get('hold') for k in keys], loop)
            hq = np.array([quat(held_frame(h) @ own_frame.T) if h else np.array([0.0, 0, 0, 1]) for h in hold])
            for k in range(1, len(hq)):
                if hq[k] @ hq[k - 1] < 0:
                    hq[k] *= -1
            hq = curve(kt, hq, t, loop, length, np.repeat(-1.0 if hq[-1] @ hq[0] < 0 else 1.0, 4), eases)
            hq /= np.linalg.norm(hq, axis=1, keepdims=True)
            hb = curve(kt, np.array([h['butt'] if h else foot for h in hold], dtype=float), t, loop, length, None, eases)
            hs = curve(kt, np.array([[h.get('hand', holds_at)] if h else [holds_at] for h in hold]), t, loop, length,
                       None, eases)[:, 0]
            hw = np.clip(curve(kt, np.array([[1.0 if 'hold' in k else 0.0] for k in keys]), t, loop, length), 0, 1)[:, 0]
            other = 'L' if hand_side == 'R' else 'R'
            grip = filled([k.get('grip', {}).get(other) for k in keys], loop)
            gs = curve(kt, np.array([[v if v is not None else 0.5] for v in grip]), t, loop, length, None, eases)[:, 0]
            gw = np.clip(curve(kt, np.array([[1.0 if other in k.get('grip', {}) else 0.0] for k in keys]), t, loop,
                               length), 0, 1)[:, 0]
            if loop:
                hq[-1], hb[-1], hs[-1], hw[-1], gs[-1], gw[-1] = hq[0], hb[0], hs[0], hw[0], gs[0], gw[0]
            gaps = {hand_side: [], other: []}
        frames = np.zeros((len(t), len(joints), 4, 4))
        # Where a key holds or grips the prop, a hand's place on it is found first at the keys (the frames nearest
        #  them) that hold or grip it, lying along it as its forearm carries it; then between, it goes from one key's
        #  place to the next's (the hand that holds the prop eased from as the stance holds it), so a hand never turns
        #  over from one frame to the next.
        if posing:
            span_n = len(t) - 1 if loop else len(t)  # a loop's last frame is its first

            def at_keys(has):
                return {int(math.floor(k['at'] / length * (len(t) - 1) + 0.5)) % span_n for k in keys if has(k)}

            def between(rels, full, f):
                """A hand's turn at frame f, as the chest carries it, from the keys' either side of it."""
                order = sorted(full)
                f %= span_n
                if f in rels:  # at a key
                    return rels[f]
                before, after = [g for g in order if g < f], [g for g in order if g > f]
                if loop:
                    p, n = (before or order)[-1], (after or order)[0]
                    dp, dn = (f - p) % span_n, (n - f) % span_n
                else:
                    p, n = (before or [None])[-1], (after or [None])[0]
                    if p is None or n is None:
                        return rels[n if p is None else p]
                    dp, dn = f - p, n - f
                u = dp / (dp + dn)
                return rels[p] if p == n else blend(rels[p], rels[n], u * u * (3 - 2 * u))  # eased in and out

            full = {hand_side: at_keys(lambda k: 'hold' in k), other: at_keys(lambda k: other in k.get('grip', {}))}
            # A hold next to a key that doesn't hold (where it eases on or off) lays the hand as the stance does, so
            #  it eases from and to the stance's grip without turning over.
            edge = set()
            for i, k in enumerate(keys):
                near_keys = [(i - 1) % len(keys), (i + 1) % len(keys)] if loop else [j for j in (i - 1, i + 1) if 0 <= j < len(keys)]
                if 'hold' in k and any('hold' not in keys[j] for j in near_keys):
                    edge |= at_keys(lambda x: x is k)
            turned = {hand_side: {}, other: {}}  # each hand's turn at the keys, as the chest carries it
            wrists = {hand_side: [], other: []}  # how far each hand bends off its forearm, in degrees
            elbows = {hand_side: [], other: []}  # how far each arm on the prop bends at the elbow, in degrees
        for pass_ in ((0, 1) if posing else (1,)):
            if posing:
                gaps = {hand_side: [], other: []}
                slid = {}  # how far the hand that holds the prop slid along it (or moved it), by frame (where it did)
                capped = set()  # frames where it couldn't slide (or move) as far as the eased bend needed
                sides = {}  # frames where it slid out from the shoulder, and which way along the prop (+1 or -1)
            for f in range(len(t)):
                rot, moved = {}, {}
                for i, n in enumerate(names):
                    p = parents[n]
                    rot[n] = matrix(q[f, i]) if p is None else rot[p] @ matrix(q[f, i])
                    moved[n] = heads[n] + off[f] if p is None else rot[p] @ (heads[n] - heads[p]) + moved[p]
                # The whole figure's turn and slide, which a planted foot's leg reaches through.
                whole = whole_at(axis, place, deg[f], sl[f])
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
                if posing:
                    # The prop: as the hand holds it, eased to as the key holds it (carried by the chest), all before the
                    #  whole figure's turn; then the hand that holds it bent to it, and the other to its grip.
                    own = m[hi] @ carry
                    set_ = np.eye(4)
                    set_[:3, :3] = matrix(hq[f]) @ bind[nb, :3, :3]
                    set_[:3, 3] = hb[f] + matrix(hq[f]) @ (bind[nb, :3, 3] - foot)
                    kept = m[names.index('chest')] @ chest_bind @ set_
                    prop_m = np.eye(4)
                    prop_m[:3, :3] = blend(own[:3, :3], kept[:3, :3], hw[f]) if hw[f] > 0 else own[:3, :3]
                    prop_m[:3, 3] = own[:3, 3] + hw[f] * (kept[:3, 3] - own[:3, 3])
                    fm = f % span_n
                    chest_r = m[names.index('chest')][:3, :3]
                    for side, weight, share in ((hand_side, hw, hs), (other, gw, gs)):
                        if weight[f] <= 0:
                            continue
                        if pass_ == 0:  # at a key: lying along it as its forearm carries it
                            if fm in full[side]:
                                lay = stance_lay if side == hand_side and fm in edge else None
                                turned[side][fm] = chest_r.T @ hold_hand(rot, moved, side, prop_m, share[f], 1.0, lay)[:3, :3]
                            continue
                        wt = float(weight[f]) if side == other else 1.0  # the hand that holds it is always on it
                        # Turned as the keys either side turn it, as the chest carries it, and placed so the prop
                        #  passes it as at a key; the hand that holds the prop eased from as the stance holds it.
                        hand_r = chest_r @ between(turned[side], full[side], f)
                        at = (prop_m @ prop_inv @ np.append(foot + share[f] * span * along, 1))[:3]
                        there = np.eye(4)
                        there[:3, :3], there[:3, 3] = hand_r, at - hand_r @ near[side]
                        if side == hand_side and weight[f] < FULL:
                            # Its elbow eased from as the keys bend it to as the full hold would (the hand on the
                            #  prop as the key holds it), so a nearly straight arm bends steadily rather than in a
                            #  snap: the hand slid along the prop to where its wrist is that far from the shoulder.
                            full_at = (kept @ prop_inv @ np.append(foot + share[f] * span * along, 1))[:3]
                            ua_n, fa_n = f'upper_arm.{side}', f'forearm.{side}'
                            a_, b_ = (float(np.linalg.norm(skeleton[x][1] - skeleton[x][0])) for x in (ua_n, fa_n))
                            ua_v, fa_v = (rot[x] @ (skeleton[x][1] - skeleton[x][0]) for x in (ua_n, fa_n))
                            bend_keyed = math.acos(np.clip(ua_v @ fa_v / a_ / b_, -1, 1))
                            r_full = float(np.linalg.norm(full_at - there[:3, :3] @ near[side] - (moved[ua_n] - shift)))
                            cos_held = (r_full ** 2 - a_ * a_ - b_ * b_) / (2 * a_ * b_)
                            bend_held = math.acos(np.clip(cos_held, -1, 1))
                            bend_now = bend_keyed + (bend_held - bend_keyed) * weight[f]
                            stretch = math.sqrt(a_ * a_ + b_ * b_ + 2 * a_ * b_ * math.cos(bend_now))
                            if abs(cos_held) > 1:  # the full hold out of the arm's reach (or nearer than it folds):
                                #  eased to all the same, so the hand comes to rest on the prop where the key holds it
                                stretch += weight[f] * (r_full - (a_ + b_ if cos_held > 1 else abs(a_ - b_)))
                            there = mix(prop_m @ np.linalg.inv(carry), there, weight[f])
                            way = prop_m[:3, :3] @ bind[nb, :3, :3].T @ along
                            from_ = there[:3, 3] - (moved[ua_n] - shift)  # the wrist, from the shoulder
                            if not prop_slides:
                                # The hand stays where it holds the prop, and the prop moves with it, straight
                                #  towards or away from the shoulder.
                                far = float(np.linalg.norm(from_))
                                if abs(stretch - far) > SLIDE:
                                    capped.add(f)
                                shove = min(max(stretch - far, -SLIDE), SLIDE) * from_ / far
                                slid[f] = shove  # (as a move, as its way turns from frame to frame too)
                                there[:3, 3] += shove
                                at = at + shove
                                prop_m[:3, 3] += shove
                            else:
                                b2, c2 = float(way @ from_), float(from_ @ from_) - stretch * stretch
                                slide = -b2 if b2 * b2 < c2 else min((-b2 - math.sqrt(b2 * b2 - c2), -b2 + math.sqrt(b2 * b2 - c2)), key=abs)
                                # Never past the prop's ends (whatever SLIDE allows), from where the hand is on it,
                                #  eased from the stance's grip.
                                place = share[f] * span + float((there[:3, 3] + there[:3, :3] @ near[side] - at) @ way)
                                wanted = slide
                                slide = min(max(min(max(slide, -SLIDE), SLIDE), -place), span - place)
                                if b2 * b2 < c2 or abs(slide - wanted) > 1e-9:  # the line not that near, or held back
                                    capped.add(f)
                                if c2 < 0 and wanted:  # (its side as it would be, whatever holds it back)
                                    sides[f] = math.copysign(1.0, wanted)
                                slid[f] = slide
                                there[:3, 3] += slide * way
                                at = at + slide * way  # the hold's place, slid as the hand was (not where the hand is)
                        short = bend_arm(skeleton, rot, moved, shift, side, there[:3, 3], there[:3, :3], wt)
                        fa, hd = f'forearm.{side}', f'hand.{side}'
                        if side == hand_side or weight[f] >= FULL:
                            # How far the hand ends up from where it holds the prop: fully holding it, from its place
                            #  (short of it, out of reach); easing on or off, from the prop's line.
                            way = prop_m[:3, :3] @ bind[nb, :3, :3].T @ along
                            miss = moved[hd] - shift + rot[hd] @ near[side] - at
                            gaps[side].append(short if weight[f] >= FULL else float(np.linalg.norm(miss - (miss @ way) * way)))
                            ua = rot[f'upper_arm.{side}'] @ (skeleton[f'upper_arm.{side}'][1] - skeleton[f'upper_arm.{side}'][0])
                            fv = rot[fa] @ (skeleton[fa][1] - skeleton[fa][0])
                            elbows[side].append(math.degrees(math.acos(np.clip(ua @ fv / np.linalg.norm(ua) / np.linalg.norm(fv), -1, 1))))
                        a_, b_ = (rot[x] @ (skeleton[x][1] - skeleton[x][0]) for x in (fa, hd))
                        wrists[side].append(math.degrees(math.acos(np.clip(a_ @ b_ / np.linalg.norm(a_) / np.linalg.norm(b_), -1, 1))))
                    m = world(rot, moved)
                    frames[f, :nb] = np.einsum('ab,jbc->jac', whole, m)
                    frames[f, nb] = whole @ prop_m
                    continue
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
        standing = np.ones(len(pos), dtype=bool)
        if rig.get('prop') and rig['prop'].get('grounded', True) is False:
            standing[used] = False  # the figure stands on its feet, wherever the prop goes
        low = skinned(shown)[:, standing, 1].min(axis=1)
        frames[:, :, 1, 3] -= low[:, None]
        shown[:, :, 1, 3] -= low[:, None]
        # Joints' local turns (and the root's place) for the file.
        rots = np.zeros((len(t), len(joints), 4))
        prop_t = np.zeros((len(t), 3))
        for f in range(len(t)):
            for i, n in enumerate(joints):
                p = parents[n]
                lm = frames[f, i] if p is None else np.linalg.inv(frames[f, joints.index(p)]) @ frames[f, i]
                rots[f, i] = quat(lm[:3, :3])
                if n == 'prop':
                    prop_t[f] = lm[:3, 3]
        for j in range(len(joints)):  # each the nearer of q and -q to the frame before
            for f in range(1, len(t)):
                if rots[f, j] @ rots[f - 1, j] < 0:
                    rots[f, j] *= -1
        root_t = frames[:, 0, :3, 3]
        animations.append((role, t, rots, root_t, (size_t, size_v), prop_t if posing else None))
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
        if not standing.all():
            report[role]['below'] = round(max(0.0, -float(final[:, used, 1].min())), 3)
        if posing:
            # The slide follows the eased bend and where the shoulder comes nearest the prop's line, so a hold eased
            #  on or off in too few frames, or a prop passing the shoulder fast (or the wrist passing that point, where
            #  the slide turns from one side to the other), would jerk the hand along it; likewise a prop that moves
            #  with the hand would jerk.
            steps = [float(np.linalg.norm(np.asarray(slid.get(f, 0.0)) - np.asarray(slid.get(f - 1, 0.0))))
                     for f in range(len(t))]
            flips = 0
            for f in range(1, len(t)):
                step = steps[f]
                flips += sides.get(f, 0) * sides.get(f - 1, 0) < 0
                # Slid out from the shoulder one way along the prop and then the other: the wrist passed where the
                #  shoulder comes nearest the prop's line, and the hand jumps from one side to the other.
                if sides.get(f, 0) * sides.get(f - 1, 0) < 0 and step > GRIP:
                    fail(f'clip {role}: the hand that holds the prop would jump {step:.3f} m along it at {t[f]:.3f} s, '
                         'from one side of where the shoulder comes nearest its line to the other, as the hold eases; '
                         'key the prop so the hand passes the shoulder once the hold is full (as a port arms key does)')
                if step > SLIDE_STEP:
                    fail(f'clip {role}: the hand that holds the prop would change how far it slides along it (or moves '
                         f'it) by {step:.3f} m from one frame to the next at {t[f]:.3f} s, as the hold eases (too fast, or '
                         'with the prop passing its shoulder); ease the hold over more frames, or key the prop to pass '
                         'the shoulder once the hold is full (as a port arms key does)')
            report[role]['grip'] = {s_: round(float(max(g, default=0)), 3) for s_, g in sorted(gaps.items())}
            if slid:
                report[role]['slide'] = {'most': round(max(float(np.linalg.norm(v)) for v in slid.values()), 3),
                                         'step': round(max(steps[1:], default=0.0), 3), 'capped': len(capped),
                                         'flips': int(flips)}
            if max(report[role]['grip'].values()) > GRIP:
                fail(f'clip {role}: a hand ends up {max(report[role]["grip"].values())} m from where it holds the prop, '
                     'out of its arm\'s reach')
            report[role]['wrist'] = {s_: round(max(g, default=0)) for s_, g in sorted(wrists.items())}
            report[role]['elbow'] = {s_: round(min(g, default=180)) for s_, g in sorted(elbows.items())}
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
        if n == 'prop' and 'muzzle' in rig['prop']:  # where its shots leave from: the middle of its top
            kids.append(first + 1 + len(joints))
        if rig.get('muzzle') and n == rig['muzzle']['bone']:  # or on the bone that carries the weapon, where it says
            kids.append(first + 1 + len(joints))
        if kids:
            node['children'] = kids
        nodes.append(node)
    if rig.get('prop') and 'muzzle' in rig['prop']:
        nodes.append({'name': 'muzzle', 'translation': [
            float(v) for v in (np.linalg.inv(bind[nb]) @ np.append(top, 1))[:3].astype(np.float32)]})
    if rig.get('muzzle'):
        nodes.append({'name': 'muzzle', 'translation': [float(v) for v in (
            np.linalg.inv(bind[joints.index(rig['muzzle']['bone'])]) @ np.append(rig['muzzle']['at'], 1))[:3].astype(np.float32)]})
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
    for role, t, rots, root_t, (size_t, size_v), prop_t in animations:
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
        if prop_t is not None:  # and its place on the hand, where a key holds or grips it
            channel(index['prop'], 'translation', prop_t, 'VEC3')
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
