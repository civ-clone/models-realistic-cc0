"""build.py : builds the set's models from their originals, as roster.json says, then writes the manifest.

    python3 -I tools/build.py --blender BLENDER --originals DIR [--work DIR] [NAME ...]
    python3 -I tools/build.py

With --originals, it builds each model the roster lists (or only those NAMEd, by model id or extra path) in Blender:
it finds each original in DIR by its SHA-256, leaves out any parts the roster drops, splits off a piece fused to a
figure where the roster says (blender/split.py), cuts it to its budget and bakes its colour into one texture
(blender/cut.py), turns, sizes and grounds it, or floats it at its draught (blender/normalise.py), puts in its prop,
which may be the piece split off (blender/assemble.py), puts its owner's colour where the roster says
(blender/owner.py), stands a figure in a natural pose (blender/stance.py), and rigs it with its clips into
models/rigged/ where the roster gives it a rig (blender/rig.py). Blender runs with factory settings and with scripts in
files turned off (-b --factory-startup -Y), and reads the originals only as data.

Then, with or without --originals, it writes each model (and its rigged figure) into models/ with its credit,
licence and changes in its `asset.extras`, and writes manifest.json and CREDITS.md from the files and the roster. That last step needs only
Python 3.10 or later.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import glb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER_SCRIPTS = os.path.join(ROOT, 'tools', 'blender')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def stamp(path, extras, copyright):
    """Puts extras in the file's asset.extras and its credit in asset.copyright, keeping the rest of it as it is."""
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n])
    rest = b[20 + n:]
    j.setdefault('asset', {})['extras'] = extras
    j['asset']['copyright'] = copyright
    js = json.dumps(j, separators=(',', ':'), ensure_ascii=False).encode()
    js += b' ' * (-len(js) % 4)
    body = struct.pack('<II', len(js), 0x4E4F534A) + js + rest
    open(path, 'wb').write(struct.pack('<III', 0x46546C67, 2, 12 + len(body)) + body)


class Blender:
    def __init__(self, exe, originals, work):
        self.exe, self.work = exe, work
        self.by_sha = {}
        for dirpath, _, files in os.walk(originals):
            for f in files:
                p = os.path.join(dirpath, f)
                self.by_sha.setdefault(sha256(p), p)

    def run(self, script, *args, env=None):
        cmd = [self.exe, '-b', '--factory-startup', '-Y', '--python-exit-code', '1', '--python',
               os.path.join(BLENDER_SCRIPTS, script), '--', *map(str, args)]
        p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **(env or {})})
        bad = [line for line in (p.stdout + p.stderr).splitlines() if 'Traceback' in line or 'Error' in line]
        if p.returncode or bad:
            sys.exit(f'{script} failed on {args[:2]}:\n' + '\n'.join(bad[:10] or (p.stdout + p.stderr).splitlines()[-10:]))
        for line in p.stdout.splitlines():
            if line.startswith(('SPLIT ', 'CLOSE ', 'OWNER ', 'POSE ', 'RIG ')):
                print('  ' + line, flush=True)

    def original(self, roster, key):
        src = roster['sources'][key]
        path = self.by_sha.get(src['sha256'])
        if path is None:
            sys.exit(f'No file in the originals has the SHA-256 of {key!r} ({src["work"]}): {src["file"]}')
        return path

    def cut(self, src, out, cut):
        args = [src, out, cut['tris'], cut['texture'], cut['mode']] + ([cut['depth']] if cut['mode'] == 'rewrap' else [])
        env = {'REWRAP_' + k.upper(): str(cut[k]) for k in ('solidify', 'close') if k in cut} or None
        self.run('cut.py', *args, env=env)
        return os.path.join(out, 'cut.glb')

    def build(self, roster, name, entry, out):
        """Builds one model or extra into the file out (and, where it has a rig, its rigged figure into rigged/ beside
        out)."""
        slug = name.replace('/', '-').removesuffix('.glb')
        src = self.original(roster, entry['source'])
        if entry.get('drop'):
            fixed = os.path.join(self.work, 'fixed', slug + '.glb')
            os.makedirs(os.path.dirname(fixed), exist_ok=True)
            self.run('drop_parts.py', src, fixed, *entry['drop'])
            src = fixed
        piece = None
        if entry.get('split'):  # a piece fused to the figure, split off to be put back as its prop
            body = os.path.join(self.work, 'split', slug + '-body.glb')
            piece = os.path.join(self.work, 'split', slug + '-piece.glb')
            rule = os.path.join(self.work, 'split', slug + '.json')
            os.makedirs(os.path.dirname(rule), exist_ok=True)
            with open(rule, 'w', encoding='utf-8') as f:
                json.dump({'stage': entry['stage'], **entry['split']}, f)
            self.run('split.py', src, body, piece, rule)
            src = body
        cut = self.cut(src, os.path.join(self.work, 'cut', slug), entry['cut'])
        prop = entry.get('prop')
        staged = os.path.join(self.work, 'parts' if prop else 'staged', slug + '.glb')
        stage = {slug: {'src': cut, **entry['stage'], 'out': os.path.basename(staged)}}
        stage_path = os.path.join(self.work, 'stage', slug + '.json')
        os.makedirs(os.path.dirname(stage_path), exist_ok=True)
        json.dump(stage, open(stage_path, 'w', encoding='utf-8'), indent=1)
        self.run('normalise.py', stage_path, os.path.dirname(staged), slug)
        if prop:
            options = dict(prop['options'])
            if prop['source'] == 'molotov':  # the molotov comes as a zip: its FBX and its texture
                d = os.path.join(self.work, 'props', 'molotov')
                with zipfile.ZipFile(self.original(roster, 'molotov')) as z:
                    for member in ('Molotov.fbx', 'Molotov.png'):
                        os.makedirs(d, exist_ok=True)
                        open(os.path.join(d, member), 'wb').write(z.read(member))
                prop_file = os.path.join(d, 'Molotov.fbx')
                options['texture'] = os.path.join(d, 'Molotov.png')
            else:
                prop_file = piece if prop['source'] == 'split' else self.original(roster, prop['source'])
                if 'cut' in prop:
                    prop_file = self.cut(prop_file, os.path.join(self.work, 'cut', slug + '-prop'), prop['cut'])
            if 'posed' in options:  # turned to point that way once posed: assemble.py reads the stance
                rule = os.path.join(self.work, 'stance', slug + '.json')
                os.makedirs(os.path.dirname(rule), exist_ok=True)
                with open(rule, 'w', encoding='utf-8') as f:
                    json.dump(entry['stance'], f)
                options['stance'] = rule
            self.run('assemble.py', prop['mode'], staged, prop_file, out,
                     *[f'{k}={",".join(map(str, v)) if isinstance(v, list) else v}' for k, v in options.items()])
        else:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(staged, out)
        if 'owner' in entry:
            rule = os.path.join(self.work, 'owner', slug + '.json')
            os.makedirs(os.path.dirname(rule), exist_ok=True)
            with open(rule, 'w', encoding='utf-8') as f:
                json.dump(entry['owner'], f)
            self.run('owner.py', out, rule)
        if 'stance' in entry:
            check.problems.clear()
            check.check_stance(f'{name}.stance', entry['stance'])
            if 'rig' in entry:
                check.check_rig(f'{name}.rig', entry['rig'], entry['stance'])
            if check.problems:
                sys.exit('\n'.join(check.problems))
            rule = os.path.join(self.work, 'stance', slug + '.json')
            weights = os.path.join(self.work, 'stance', slug + '-weights.json')
            os.makedirs(os.path.dirname(rule), exist_ok=True)
            with open(rule, 'w', encoding='utf-8') as f:
                json.dump(entry['stance'], f)
            self.run('stance.py', out, rule, *([weights] if 'rig' in entry else []))
            if 'rig' in entry:
                rig = os.path.join(self.work, 'rig', slug + '.json')
                os.makedirs(os.path.dirname(rig), exist_ok=True)
                with open(rig, 'w', encoding='utf-8') as f:
                    json.dump(entry['rig'], f)
                self.run('rig.py', out, weights, rule, rig, rigged_path(out))


def rigged_path(out):
    """Where a model's rigged figure is, beside the model."""
    return os.path.join(os.path.dirname(out), 'rigged', os.path.basename(out))


def finish(roster, built):
    """Writes models/ (from built where a model was built now), manifest.json and CREDITS.md."""
    s = roster['set']
    clash = sorted(f'rigged/{mid}.glb' for mid, e in roster['models'].items() if 'rig' in e and f'rigged/{mid}.glb' in roster['extras'])
    if clash:
        sys.exit(f'models/{clash[0]} would be both an extra and a rigged model\'s figure')
    models, names = {}, {}
    entries = [(f'{mid}.glb', mid, e) for mid, e in roster['models'].items()]
    entries += [(rel, None, e) for rel, e in roster['extras'].items()]
    for rel, mid, e in entries:
        files = [rel] + ([f'rigged/{rel}'] if mid is not None and 'rig' in e else [])
        for f in files:
            dst = os.path.join(ROOT, 'models', f)
            if f in built:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(built[f], dst)
            if not os.path.exists(dst):
                sys.exit(f'models/{f} is missing: build it with --originals')
            stamp(dst, check.expected_extras(roster, e), check.expected_copyright(roster, e))
        dst = os.path.join(ROOT, 'models', rel)
        if mid is None:
            continue
        measured = glb.measure(*glb.read(dst))
        m = {'file': f'models/{rel}'}
        if 'scale' in e:
            m['scale'] = e['scale']
        m.update({'sha256': sha256(dst), 'extent': measured['extent'], 'triangles': measured['triangles'],
                  'from': [check.credit_of(roster, k)['url'] for k in check.keys_of(e)], 'made': e['made']})
        if measured['animations']:
            m['animations'] = measured['animations']
        if 'rig' in e:
            rigged = os.path.join(ROOT, 'models', 'rigged', rel)
            m['rigged'] = {'file': f'models/rigged/{rel}', 'sha256': sha256(rigged),
                           'clips': {role: role for role in e['rig']['clips']}}
            if check.shots_of(e['rig']):
                m['rigged']['shots'] = check.shots_of(e['rig'])
        models[mid] = m
        for u in e['units']:
            names[u] = mid
    credits = check.expected_credits(roster)
    manifest = {'schema': 1, 'kind': 'models', 'id': s['id'], 'name': s['name'], 'source': 'hosted',
                'licence': s['licence'], 'credits': credits, 'scale': roster['scale'], 'models': models,
                'names': {'unit': names}}
    with open(os.path.join(ROOT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write('\n')
    with open(os.path.join(ROOT, 'CREDITS.md'), 'w', encoding='utf-8', newline='') as f:
        f.write(check.credits_md(roster, credits))
    print(f'{s["id"]}: {len(models)} models, {len(names)} unit types, {len(credits)} credits')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--blender', help="Blender's executable (4.5 was used)")
    ap.add_argument('--originals', help='a folder holding the original files the roster names')
    ap.add_argument('--work', help='a folder for the steps in between (default: a new temporary one)')
    ap.add_argument('names', nargs='*', help='only these models (by id) or extras (by path in models/)')
    a = ap.parse_args()
    roster = json.load(open(os.path.join(ROOT, 'roster.json'), encoding='utf-8'))
    unknown = set(a.names) - set(roster['models']) - set(roster['extras'])
    if unknown:
        sys.exit(f'Not in the roster: {", ".join(sorted(unknown))}')
    if (a.names or a.blender) and not a.originals:
        sys.exit('Building models needs --blender and --originals')
    built = {}
    if a.originals:
        if not a.blender:
            sys.exit('--originals needs --blender')
        work = a.work or tempfile.mkdtemp(prefix='models-build.')
        b = Blender(a.blender, a.originals, work)
        todo = [(f'{mid}.glb', e) for mid, e in roster['models'].items() if not a.names or mid in a.names]
        todo += [(rel, e) for rel, e in roster['extras'].items() if not a.names or rel in a.names]
        for rel, e in todo:
            out = os.path.join(work, 'models', rel)
            print('building', rel, flush=True)
            b.build(roster, rel, e, out)
            built[rel] = out
            if 'rig' in e and rel.removesuffix('.glb') in roster['models']:
                built[f'rigged/{rel}'] = rigged_path(out)
        print('steps in between are in', work)
    finish(roster, built)


if __name__ == '__main__':
    main()
