"""owner.py : puts the owner's colour on a model, as its roster entry's `owner` says, for civ.one's 3D map.

Args (after --): GLB RULE.json. Rewrites GLB in place; Blender is used only to read its JPEG.

The rule picks where the owner's colour goes on one of the model's parts (`part`, counted through its meshes'
primitives in the scene's order, default 0):
- `colours`: by the colour of its texture, each a range of hue (degrees, wrapping round where the first is the
  bigger), saturation and value (0 to 1), any left out being any. With no `colours`, any colour.
- `within` and `without`: by where it is, as boxes in metres in the file's axes (x across, y up, z along, front at
  +z), each side a range [low, high] and any left out being any: in one of the `within` boxes (if there are any) and
  in none of the `without` ones.
- `sides`: by which way it faces: only faces facing sideways, whose normal rises or falls no more than this (its
  upright part, from 0 to 1), as a hull's sides do and its deck doesn't.

By default it picks whole faces: those where at least `share` (default 0.5) of the points sampled over each are in
the colours, whose middles are where the rule says; then, `smooth` times (default 2), any face whose neighbours all
differ from it changes to match them, so no specks are left. With `cut`, it goes texel by texel instead: each texel
of the texture is in the owner's colour where it's in the colours and the place it's drawn at is where the rule
says, which follows a line across big faces, such as a band along a hull.

The faces with any of the owner's colour move to a primitive of their own, sharing the part's points, drawn with a
copy of its material that says `extras.playerColour` and has a PNG of its own, at half the texture's size. Where the
owner's colour goes it's grey, as light as the texture there (its middle `light`, default 0.8, its shading kept), and
its alpha is 0; cut texel by texel, it's the texture as it is, solid, where it doesn't. civ.one draws it as
rgb × mix(owner, white, alpha), so the owner's colour goes where the rule says, shaded as before. The rest of the
model, its texture and its JPEG are left as they are.

It fails, writing nothing, where the rule picks no face or every face of the part (whose JPEG is kept for the
rest), or the file already has an owner's colour.
"""
import json
import math
import os
import struct
import sys
import tempfile
import zlib

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glb  # noqa: E402

RULE = {'part', 'colours', 'within', 'without', 'sides', 'cut', 'share', 'smooth', 'light'}
SAMPLES = ((1 / 3, 1 / 3, 1 / 3), (2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3),
           (0.4, 0.4, 0.2), (0.4, 0.2, 0.4), (0.2, 0.4, 0.4))


def fail(text):
    raise RuntimeError(f'Error: {text}')


def read_jpeg(data):
    """The JPEG's pixels as an array of rows from the top, RGB from 0 to 1 as stored (sRGB)."""
    with tempfile.TemporaryDirectory(prefix='owner-texture.') as folder:
        path = os.path.join(folder, 'texture.jpg')
        with open(path, 'wb') as f:
            f.write(data)
        img = bpy.data.images.load(path)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3].copy()


def hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(axis=-1)
    c = v - rgb.min(axis=-1)
    s = np.where(v > 0, c / np.maximum(v, 1e-9), 0)
    safe = np.maximum(c, 1e-9)
    h = np.where(v == r, ((g - b) / safe) % 6, np.where(v == g, (b - r) / safe + 2, (r - g) / safe + 4)) * 60
    return np.where(c > 0, h, 0), s, v


def in_range(values, span):
    if span is None:
        return np.ones_like(values, dtype=bool)
    lo, hi = span
    return (values >= lo) & (values <= hi)


def keyed(rgb, colours):
    h, s, v = hsv(rgb)
    out = np.zeros(rgb.shape[:2], dtype=bool)
    for c in colours:
        hue = c.get('h')
        if hue is not None and hue[0] > hue[1]:
            hm = (h >= hue[0]) | (h <= hue[1])
        else:
            hm = in_range(h, hue)
        if hue is not None:  # a grey has no hue, so is in no range of hues
            hm &= s > 0
        out |= hm & in_range(s, c.get('s')) & in_range(v, c.get('v'))
    return out


def png_image(pixels):
    """An 8-bit PNG of rows from the top, grey and alpha or RGBA, each row filtered as makes it smallest."""
    h, w, c = pixels.shape
    raw = pixels.reshape(h, w * c).astype(np.int16)
    rows = []
    prev = np.zeros(w * c, dtype=np.int16)
    for y in range(h):
        line = raw[y]
        left = np.concatenate([np.zeros(c, dtype=np.int16), line[:-c]])
        upleft = np.concatenate([np.zeros(c, dtype=np.int16), prev[:-c]])
        p = left + prev - upleft
        pa, pb, pc = np.abs(p - left), np.abs(p - prev), np.abs(p - upleft)
        paeth = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, prev, upleft))
        options = [(0, line), (1, line - left), (2, line - prev), (3, line - (left + prev) // 2), (4, line - paeth)]
        kind, best = min(options, key=lambda o: int(np.abs(((o[1] + 128) % 256) - 128).sum()))
        rows.append(bytes([kind]) + (best % 256).astype(np.uint8).tobytes())
        prev = line

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, {2: 4, 4: 6}[c], 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    path, rule = a[0], json.load(open(a[1], encoding='utf-8'))
    if set(rule) - RULE:
        fail(f'the rule says {sorted(set(rule) - RULE)}, which this does not read')
    gltf, binary = glb.read(path)
    n_views = len(gltf['bufferViews'])
    if any(m.get('extras', {}).get('playerColour') for m in gltf.get('materials', [])):
        fail(f'{path} already has an owner\'s colour')

    parts = [(mi, pi, world) for mi, world in glb.placed_meshes(gltf) for pi in range(len(gltf['meshes'][mi]['primitives']))]
    part = rule.get('part', 0)
    if not isinstance(part, int) or not 0 <= part < len(parts):
        fail(f'there is no part {part}: the file\'s parts are numbered from 0 to {len(parts) - 1}')
    if [mi for mi, _ in glb.placed_meshes(gltf)].count(parts[part][0]) > 1:
        fail('the part\'s mesh is placed more than once')
    mi, pi, world = parts[part]
    prim = gltf['meshes'][mi]['primitives'][pi]
    if 'indices' not in prim:
        fail('the part has no indices')
    if sum(p.get('indices') == prim['indices'] for m in gltf['meshes'] for p in m['primitives']) > 1:
        fail('the part\'s indices are shared with another primitive')
    material = gltf['materials'][prim['material']]
    tex = gltf['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']]
    image = gltf['images'][tex['source']]
    view = gltf['bufferViews'][image['bufferView']]
    if image.get('mimeType') != 'image/jpeg':
        fail('the part\'s texture is not a JPEG')
    rgb = read_jpeg(binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']])
    h, w = rgb.shape[:2]

    pos = [tuple(world[r][0] * x + world[r][1] * y + world[r][2] * z + world[r][3] for r in range(3))
           for x, y, z in glb.accessor(gltf, binary, prim['attributes']['POSITION'])]
    uv = np.array(glb.accessor(gltf, binary, prim['attributes']['TEXCOORD_0']), dtype=np.float64)
    faces = glb.triangles(gltf, binary, prim)
    tri = np.array(faces, dtype=np.int64)

    # Where each face lies in the texture: the texels whose middles it covers, and where on it each one is; then, for
    #  texels no face covers, the face whose edge is within a twentieth of them, for the margin round each island.
    #  Where faces share texels (their UVs overlap), the last one drawn has them.
    face_at = np.full((h, w), -1, dtype=np.int64)
    bary_at = np.zeros((h, w, 3))
    edge_at = np.full((h, w), -1, dtype=np.int64)
    edge_bary = np.zeros((h, w, 3))
    for f in range(len(faces)):
        t = uv[tri[f]] * (w, h)
        x0, y0 = np.floor(t.min(axis=0)).astype(int)
        x1, y1 = np.ceil(t.max(axis=0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = t
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
        l3 = 1 - l1 - l2
        bary = np.stack([l1, l2, l3], axis=-1)
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        near = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05) & ~inside
        face_at[y0:y1 + 1, x0:x1 + 1][inside] = f
        bary_at[y0:y1 + 1, x0:x1 + 1][inside] = bary[inside]
        edge_at[y0:y1 + 1, x0:x1 + 1][near] = f
        edge_bary[y0:y1 + 1, x0:x1 + 1][near] = bary[near]
    unclaimed = (face_at < 0) & (edge_at >= 0)
    face_at[unclaimed] = edge_at[unclaimed]
    bary_at[unclaimed] = edge_bary[unclaimed]
    strict = np.zeros((h, w), dtype=bool)
    strict[face_at >= 0] = True
    strict[unclaimed] = False
    P = np.array(pos)
    normal = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    length = np.linalg.norm(normal, axis=1)
    sideways = (length > 0) & (np.abs(normal[:, 1]) <= rule.get('sides', 1) * np.maximum(length, 1e-30))

    def placed(points):
        """Whether each point is where the rule wants: in a `within` box, if any, and in no `without` one."""
        ok = np.ones(len(points), dtype=bool)
        if rule.get('within'):
            ok &= np.any([np.all([(points[:, k] >= b[a][0]) & (points[:, k] <= b[a][1]) for k, a in enumerate('xyz')
                                  if b.get(a) is not None] or [np.ones(len(points), dtype=bool)], axis=0)
                          for b in rule['within']], axis=0)
        for b in rule.get('without', []):
            ok &= ~np.all([(points[:, k] >= b[a][0]) & (points[:, k] <= b[a][1]) for k, a in enumerate('xyz')
                           if b.get(a) is not None] or [np.ones(len(points), dtype=bool)], axis=0)
        return ok

    key = keyed(rgb, rule['colours']) if rule.get('colours') else np.ones((h, w), dtype=bool)
    on = face_at >= 0
    if rule.get('cut'):
        # Texel by texel: each texel is in the owner's colour where it, and the place on the model it's drawn at, are
        #  as the rule says; a face is picked where any of its texels are.
        where = np.zeros((h, w, 3))
        f_on = face_at[on]
        where[on] = np.einsum('nk,nkc->nc', bary_at[on], P[tri[f_on]])
        texel = np.zeros((h, w), dtype=bool)
        texel[on] = key[on] & placed(where[on]) & sideways[f_on]
        picked = np.bincount(face_at[texel & strict], minlength=len(faces)) > 0
        # A face too small to cover a texel's middle is picked as its middle is.
        tiny = np.bincount(face_at[strict], minlength=len(faces)) == 0
        q = uv[tri].mean(axis=1)
        keyed_middle = key[np.clip((q[:, 1] * h).astype(int), 0, h - 1), np.clip((q[:, 0] * w).astype(int), 0, w - 1)]
        picked |= tiny & keyed_middle & placed(P[tri].mean(axis=1)) & sideways
    else:
        # Face by face: a face is picked where enough of its texture is in the rule's colours and its middle where
        #  the rule says, and then all of it is in the owner's colour.
        hits = np.zeros(len(faces))
        for bary in SAMPLES:
            q = bary[0] * uv[tri[:, 0]] + bary[1] * uv[tri[:, 1]] + bary[2] * uv[tri[:, 2]]
            hits += key[np.clip((q[:, 1] * h).astype(int), 0, h - 1), np.clip((q[:, 0] * w).astype(int), 0, w - 1)]
        picked = (hits / len(SAMPLES) >= rule.get('share', 0.5)) & placed(P[tri].mean(axis=1)) & sideways

        # Specks: faces whose neighbours (across an edge, where the points meet, seams or not) all differ.
        weld = {}
        ids = [weld.setdefault(tuple(round(c, 4) for c in p), len(weld)) for p in pos]
        edges = {}
        for f, (i, j, k) in enumerate(faces):
            for e in ((ids[i], ids[j]), (ids[j], ids[k]), (ids[k], ids[i])):
                edges.setdefault(tuple(sorted(e)), []).append(f)
        near = [set() for _ in faces]
        for fs in edges.values():
            for f in fs:
                near[f].update(g for g in fs if g != f)
        for _ in range(rule.get('smooth', 2)):
            flip = [f for f in range(len(faces)) if near[f] and all(picked[g] != picked[f] for g in near[f])]
            if not flip:
                break
            picked[flip] = ~picked[flip]
        texel = on & picked[np.maximum(face_at, 0)]
    if not picked.any() or not texel.any():
        fail('the rule picks no faces, or none big enough to cover a texel')

    # The owner's texture, over the picked faces: grey and alpha 0 where the owner's colour goes, as light as the
    #  texture there; and, cut texel by texel, the texture as it is, solid, where it doesn't. Round them, a margin
    #  carried on from their edges; elsewhere, flat.
    covered = on & picked[np.maximum(face_at, 0)]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    middle = float(np.median(lum[texel]))
    light = rule.get('light', 0.8)
    grey = np.clip(light * (np.maximum(lum, 1e-4) / max(middle, 1e-4)) ** 0.75, 0.3, 1.0)
    if rule.get('cut'):
        img = np.where(texel[..., None], np.concatenate([np.repeat(grey[..., None], 3, -1), np.zeros((h, w, 1))], -1),
                       np.concatenate([rgb, np.ones((h, w, 1))], -1))
    else:
        img = np.stack([grey, np.zeros((h, w))], axis=-1)
    filled = covered.copy()
    for _ in range(max(4, w // 64)):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(filled, (dy, dx), axis=(0, 1))
            if dy == 1: src[0, :] = False
            if dy == -1: src[-1, :] = False
            if dx == 1: src[:, 0] = False
            if dx == -1: src[:, -1] = False
            take = src & ~filled
            img[take] = np.roll(img, (dy, dx), axis=(0, 1))[take]
            filled |= take
    # Flat beyond the margin: grey for the owner's colour, or, cut texel by texel, the texture's mean colour, solid,
    #  so small copies' mipmaps don't carry the owner's colour onto faces that don't have it.
    flat = np.concatenate([rgb[on].mean(axis=0), [1.0]]) if rule.get('cut') else np.array([light, 0.0])
    img = np.where(filled[..., None], img, flat)
    if h % 2 == 0 and w % 2 == 0:  # at half the texture's size: mostly it holds shading, the colour being the owner's
        img = img.reshape(h // 2, 2, w // 2, 2, img.shape[-1]).mean(axis=(1, 3))
    png = png_image(np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))

    # The file: the part's faces reordered, the rest first, then the picked; the picked as a primitive of their own.
    picked_n = int(picked.sum())
    rest = len(faces) - picked_n
    views = {}
    if rest == 0:
        fail('the rule picks every face of the part: give the owner\'s colour to part of it, as its JPEG is kept')
    acc = gltf['accessors'][prim['indices']]
    iview = gltf['bufferViews'][acc['bufferView']]
    size = {5121: 1, 5123: 2, 5125: 4}[acc['componentType']]
    if iview.get('byteStride') not in (None, size):
        fail('the part\'s indices are strided')
    fmt = '<' + {1: 'B', 2: 'H', 4: 'I'}[size] * 3
    order = [f for f in range(len(faces)) if not picked[f]] + [f for f in range(len(faces)) if picked[f]]
    data = bytearray(binary[iview.get('byteOffset', 0):iview.get('byteOffset', 0) + iview['byteLength']])
    for n, f in enumerate(order):
        struct.pack_into(fmt, data, acc.get('byteOffset', 0) + n * 3 * size, *faces[f])
    views[acc['bufferView']] = bytes(data)
    acc['count'] = rest * 3
    acc.pop('min', None)
    acc.pop('max', None)
    owner_acc = {k: v for k, v in acc.items() if k not in ('count', 'byteOffset', 'name')}
    owner_acc.update({'byteOffset': acc.get('byteOffset', 0) + rest * 3 * size, 'count': picked_n * 3})
    gltf['accessors'].append(owner_acc)
    gltf['bufferViews'].append({'buffer': 0, 'byteOffset': 0, 'byteLength': len(png)})
    views[len(gltf['bufferViews']) - 1] = png
    gltf['images'].append({'bufferView': len(gltf['bufferViews']) - 1, 'mimeType': 'image/png',
                           'name': f'{image.get("name", "texture")}-owner'})
    new_tex = {'source': len(gltf['images']) - 1}
    if 'sampler' in tex:
        new_tex['sampler'] = tex['sampler']
    gltf['textures'].append(new_tex)
    owner_mat = json.loads(json.dumps(material))
    owner_mat['name'] = f'{material.get("name", "material")}-owner'
    owner_mat['pbrMetallicRoughness']['baseColorTexture'] = {'index': len(gltf['textures']) - 1}
    owner_mat['extras'] = {'playerColour': True}
    gltf['materials'].append(owner_mat)
    owner_prim = {k: v for k, v in prim.items() if k not in ('indices', 'material')}
    owner_prim.update({'indices': len(gltf['accessors']) - 1, 'material': len(gltf['materials']) - 1})
    gltf['meshes'][mi]['primitives'].insert(pi + 1, owner_prim)

    # The binary chunk laid out again, each view in its old order, those changed with their new bytes.
    out = bytearray()
    order = sorted(range(len(gltf['bufferViews'])),
                   key=lambda v: (gltf['bufferViews'][v].get('byteOffset', 0) if v < n_views else math.inf, v))
    for v in order:
        bv = gltf['bufferViews'][v]
        chunk = views.get(v)
        if chunk is None:
            chunk = binary[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
        out += b'\x00' * (-len(out) % 4)
        bv['byteOffset'] = len(out)
        bv['byteLength'] = len(chunk)
        out += chunk
    out += b'\x00' * (-len(out) % 4)
    gltf['buffers'][0]['byteLength'] = len(out)

    js = json.dumps(gltf, separators=(',', ':'), ensure_ascii=False).encode()
    js += b' ' * (-len(js) % 4)
    body = struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out)
    data = struct.pack('<III', 0x46546C67, 2, 12 + len(body)) + body
    glb.measure(*glb.read_bytes(data))
    open(path, 'wb').write(data)
    print('OWNER', path, json.dumps({'faces': picked_n, 'of': len(faces), 'png': len(png),
                                     'middle': round(middle, 3)}))


main()
