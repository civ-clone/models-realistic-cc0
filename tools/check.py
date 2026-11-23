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
- **Each file** in `models/` is a model in the manifest or an extra in the roster, and nothing else is there. Each is
  a glTF 2 binary that reads nothing from outside itself (no `uri` anywhere in it, as civ.one's loader asks) and needs
  no extension:
  - one JSON chunk and at most one binary chunk, each whole; every index in range (textures, animations and skins
    too);
  - triangles only, with positions, normals and one set of texture coordinates (and joints and weights where an extra
    keeps its skeleton): positions finite, normals a unit long, texture coordinates within 0 to 1;
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
- **Each stance** names every joint of the skeleton blender/stance.py fits, and only its bones; a model with one says
  "posed" in its `made`, and only then.
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
MODEL = {'units', 'source', 'drop', 'cut', 'stage', 'prop', 'owner', 'stance', 'scale', 'budget', 'made'}
EXTRA = {'source', 'drop', 'cut', 'stage', 'prop', 'owner', 'stance', 'made'}
CUT = {'mode', 'tris', 'texture', 'depth', 'solidify'}
STAGE = {'measure', 'size', 'turn', 'draught', 'pose', 'keep'}
PROP = {'mode', 'source', 'options', 'cut'}
OWNER = {'part', 'colours', 'within', 'without', 'sides', 'cut', 'share', 'smooth', 'light'}
STANCE = {'joints', 'aim', 'twist', 'whole'}
# A figure's joints and bones, as blender/stance.py names them.
JOINTS = {'pelvis', 'chest', 'neck', 'head', 'top'} | {f'{j}.{s}' for s in 'LR' for j in (
    'shoulder', 'elbow', 'wrist', 'hand', 'hip', 'knee', 'ankle', 'toe')}
BONES = {'hips', 'spine', 'chest', 'neck', 'head'} | {f'{b}.{s}' for s in 'LR' for b in (
    'shoulder', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot')}
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
    aim = rule.get('aim', {})
    if not isinstance(aim, dict) or set(aim) - BONES or not all(
            isinstance(d, list) and len(d) == 3 and all(number(v) for v in d) and any(d) for d in aim.values()):
        problem(f'{where}: aim should give bones a way to point [x, y, z]')
    twist = rule.get('twist', {})
    if not isinstance(twist, dict) or set(twist) - BONES or not all(number(v) for v in twist.values()):
        problem(f'{where}: twist should give bones a number of degrees')
    whole_ = rule.get('whole', [])
    if not isinstance(whole_, list) or not all(
            isinstance(b, dict) and b.get('bone') in BONES and (
                (set(b) == {'bone', 'part'} and whole(b['part'], -1)) or
                (len(b) > 1 and set(b) <= {'bone', 'x', 'y', 'z'} and all(
                    span(b[k], -math.inf, math.inf) and b[k][0] <= b[k][1] for k in 'xyz' if k in b)))
            for b in whole_):
        problem(f'{where}: whole should be a list, each a bone with a part or a box of x, y or z ranges')


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
    if 'prop' in e and keys_ok(f'{where}.prop', e['prop'], PROP):
        p = e['prop']
        if p.get('mode') not in ('hand', 'chute', 'hat', 'bonehat') or p.get('source') not in sources:
            problem(f'{where}.prop: needs a mode (hand, chute, hat or bonehat) and a source in the roster')
        if not isinstance(p.get('options'), dict):
            problem(f'{where}.prop: options should be an object')
        if 'cut' in p:
            check_cut(f'{where}.prop.cut', p['cut'])
    if 'owner' in e:
        check_owner(f'{where}.owner', e['owner'])
    if 'stance' in e:
        check_stance(f'{where}.stance', e['stance'])
    if not isinstance(e.get('made'), str) or not e['made']:
        problem(f'{where}: made should say what was done')
    elif isinstance(e.get('cut'), dict) and (e['cut'].get('mode') == 'rewrap') != ('rewrap' in e['made']):
        problem(f'{where}: made should say "rewrapped" where, and only where, the model was rewrapped')
    elif ('owner' in e) != ("the owner's colour" in e['made']):
        problem(f'{where}: made should mention "the owner\'s colour" exactly when there is an owner rule')
    elif ('stance' in e) != ('posed' in e['made']):
        problem(f'{where}: made should say "posed" exactly when there is a stance')


def credit_of(roster, key):
    s = roster['sources'][key]
    c = roster['generated'] if s.get('generated') else s
    return {k: c[k] for k in ('work', 'author', 'url', 'licence')}


def credit_line(c):
    return f'"{c["work"]}" by {c["author"]} ({c["url"]}), {c["licence"]["name"]} ({c["licence"]["url"]})'


def keys_of(entry):
    return [entry['source']] + ([entry['prop']['source']] if 'prop' in entry else [])


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


def check_file(rel, skinned_ok, texture, owner):
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
    listed = {f'{mid}.glb' for mid in models} | set(roster.get('extras', {}))
    present = set()
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'models')):
        for f in files:
            present.add(os.path.relpath(os.path.join(dirpath, f), os.path.join(ROOT, 'models')).replace(os.sep, '/'))
    for rel in sorted(present - listed):
        problem(f'models/{rel}: is neither a model in the manifest nor an extra in the roster')
    for rel in sorted(listed - present):
        problem(f'models/{rel}: is missing')
    for rel in sorted(listed & present):
        mid = rel[:-4] if rel in {f'{m}.glb' for m in models} else None
        entry = models[mid] if mid else roster['extras'][rel]
        got = check_file(rel, skinned_ok=mid is None, texture=entry['cut']['texture'], owner='owner' in entry)
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
