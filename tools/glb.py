"""glb.py : reads a glTF 2 binary as data, for build.py and check.py. Standard library only.

read(path) returns the file's JSON and binary chunks, or raises Bad saying what's wrong with its framing;
read_bytes(data) does the same for a file's bytes.
measure(gltf, binary) returns what the manifest says of a model: its triangles, how far it reaches (extent, in glTF's
axes: x across, z along with the front at +z, y up) and its animations' names, and its lowest point. Points are
placed as their nodes place them in the scene, as the file stands (not as an animation moves them); a skinned mesh is
measured as it's bound.
"""
import json
import math
import struct

GLB_MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
FORMATS = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}


class Bad(Exception):
    """What's wrong with a file."""


def read(path):
    return read_bytes(open(path, 'rb').read())


def read_bytes(data):
    if len(data) < 20:
        raise Bad('too short for a glTF binary')
    magic, version, length = struct.unpack_from('<III', data, 0)
    if magic != GLB_MAGIC or version != 2:
        raise Bad('not a glTF 2 binary')
    if length != len(data):
        raise Bad(f'says it is {length} bytes long, but is {len(data)}')
    chunks, at = [], 12
    while at < len(data):
        if at + 8 > len(data):
            raise Bad('a chunk header runs past the end')
        size, kind = struct.unpack_from('<II', data, at)
        if at + 8 + size > len(data) or size % 4:
            raise Bad('a chunk runs past the end, or is not padded to 4 bytes')
        chunks.append((kind, data[at + 8:at + 8 + size]))
        at += 8 + size
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise Bad('the first chunk is not JSON')
    if len(chunks) > 2 or (len(chunks) == 2 and chunks[1][0] != BIN_CHUNK):
        raise Bad('more than one JSON chunk and one binary chunk')
    try:
        gltf = json.loads(chunks[0][1].decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Bad(f'its JSON chunk does not parse: {e}')
    return gltf, (chunks[1][1] if len(chunks) == 2 else b'')


def item(gltf, kind, index):
    items = gltf.get(kind, [])
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(items):
        raise Bad(f'{kind} {index!r} is out of range')
    return items[index]


def accessor(gltf, binary, index):
    """An accessor's values, as a list of tuples."""
    a = item(gltf, 'accessors', index)
    if 'sparse' in a:
        raise Bad(f'accessor {index} is sparse')
    if a.get('componentType') not in FORMATS or a.get('type') not in COMPONENTS:
        raise Bad(f'accessor {index} has an unknown component type or type')
    n, comps, fmt = a.get('count', 0), COMPONENTS[a['type']], FORMATS[a['componentType']]
    if 'bufferView' not in a:
        return [tuple([0] * comps)] * n
    view = item(gltf, 'bufferViews', a['bufferView'])
    if view.get('buffer') != 0:
        raise Bad(f'buffer view {a["bufferView"]} is not in the file\'s own buffer')
    size = struct.calcsize('<' + fmt)
    stride = view.get('byteStride') or size * comps
    start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
    end = view.get('byteOffset', 0) + view.get('byteLength', 0)
    if end > len(binary) or (n and start + stride * (n - 1) + size * comps > end):
        raise Bad(f'accessor {index} runs past its buffer view or the binary chunk')
    one = struct.Struct('<' + fmt * comps)
    return [one.unpack_from(binary, start + stride * i) for i in range(n)]


def multiply(a, b):
    """a × b, adding in order (not with sum(), whose float rounding changed in Python 3.12)."""
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            total = 0.0
            for k in range(4):
                total += a[i][k] * b[k][j]
            out[i][j] = total
    return out


def local_matrix(node):
    if 'matrix' in node:
        m = node['matrix']  # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get('translation', [0, 0, 0])
    qx, qy, qz, qw = node.get('rotation', [0, 0, 0, 1])
    sx, sy, sz = node.get('scale', [1, 1, 1])
    r = [[1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
         [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
         [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
            [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
            [0, 0, 0, 1]]


def placed_meshes(gltf):
    """(mesh index, world matrix) for each node with a mesh in the default scene."""
    scene = item(gltf, 'scenes', gltf.get('scene', 0))
    out, seen = [], set()

    def walk(index, parent):
        if index in seen:
            raise Bad(f'node {index} appears twice in the scene')
        seen.add(index)
        node = item(gltf, 'nodes', index)
        world = multiply(parent, local_matrix(node))
        if 'mesh' in node:
            item(gltf, 'meshes', node['mesh'])
            out.append((node['mesh'], world))
        for child in node.get('children', []):
            walk(child, world)

    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    for root in scene.get('nodes', []):
        walk(root, identity)
    return out


def triangles(gltf, binary, prim):
    """A triangle primitive's corners, as index triples."""
    if prim.get('mode', 4) != 4:
        raise Bad('a primitive is not triangles')
    n = item(gltf, 'accessors', prim['attributes']['POSITION'])['count']
    if 'indices' in prim:
        a = item(gltf, 'accessors', prim['indices'])
        if a.get('componentType') not in (5121, 5123, 5125) or a.get('type') != 'SCALAR':
            raise Bad('a primitive\'s indices are not unsigned whole numbers')
        idx = [v[0] for v in accessor(gltf, binary, prim['indices'])]
    else:
        idx = list(range(n))
    if len(idx) % 3:
        raise Bad('a primitive has indices for part of a triangle')
    if any(not 0 <= i < n for i in idx):
        raise Bad('a primitive has an index past its points')
    return [tuple(idx[i:i + 3]) for i in range(0, len(idx), 3)]


def measure(gltf, binary):
    tris, lo, hi = 0, [math.inf] * 3, [-math.inf] * 3
    for mesh_index, world in placed_meshes(gltf):
        for prim in gltf['meshes'][mesh_index].get('primitives', []):
            if 'POSITION' not in prim.get('attributes', {}):
                raise Bad('a primitive has no positions')
            tris += len(triangles(gltf, binary, prim))
            for x, y, z in accessor(gltf, binary, prim['attributes']['POSITION']):
                p = [world[r][0] * x + world[r][1] * y + world[r][2] * z + world[r][3] for r in range(3)]
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
    if tris == 0:
        raise Bad('it draws no triangles')
    extent = {'across': [round(lo[0], 3), round(hi[0], 3)], 'along': [round(lo[2], 3), round(hi[2], 3)],
              'height': round(hi[1], 3)}
    if round(-lo[1], 3) > 0:
        extent['draught'] = round(-lo[1], 3)
    return {'triangles': tris, 'extent': extent, 'lowest': round(lo[1], 3),
            'animations': sorted(a.get('name', '') for a in gltf.get('animations', []))}
