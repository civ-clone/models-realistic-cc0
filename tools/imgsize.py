"""Width and height of a PNG or JPEG, from its bytes; and an 8-bit PNG's pixels."""
import struct
import zlib


def size(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF or data[i + 1] == 0xFF:  # not a marker, or a fill byte before one
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


def png_pixels(data):
    """An 8-bit PNG's width, height, channels (2, grey and alpha; or 4, RGBA) and rows of bytes from the top, or None
    where it isn't such a PNG, or doesn't read."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    at, idat, head = 8, b'', None
    while at + 8 <= len(data):
        n, kind = struct.unpack('>I4s', data[at:at + 8])
        chunk = data[at + 8:at + 8 + n]
        if len(chunk) != n or at + 12 + n > len(data) or zlib.crc32(kind + chunk) & 0xFFFFFFFF != struct.unpack('>I', data[at + 8 + n:at + 12 + n])[0]:
            return None
        if kind == b'IHDR':
            head = struct.unpack('>IIBBBBB', chunk)
        elif kind == b'IDAT':
            idat += chunk
        elif kind == b'IEND':
            break
        at += 12 + n
    if head is None or head[2] != 8 or head[3] not in (4, 6) or head[4:] != (0, 0, 0):
        return None
    w, h, c = head[0], head[1], {4: 2, 6: 4}[head[3]]
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return None
    stride = w * c
    if len(raw) != h * (stride + 1):
        return None
    rows, prev = [], bytearray(stride)
    for y in range(h):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if kind == 1:
            for i in range(c, stride):
                line[i] = (line[i] + line[i - c]) & 255
        elif kind == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif kind == 3:
            for i in range(stride):
                line[i] = (line[i] + ((line[i - c] if i >= c else 0) + prev[i]) // 2) & 255
        elif kind == 4:
            for i in range(stride):
                a, b, d = (line[i - c] if i >= c else 0), prev[i], (prev[i - c] if i >= c else 0)
                p = a + b - d
                pa, pb, pd = abs(p - a), abs(p - b), abs(p - d)
                line[i] = (line[i] + (a if pa <= pb and pa <= pd else b if pb <= pd else d)) & 255
        elif kind != 0:
            return None
        rows.append(bytes(line))
        prev = line
    return w, h, c, rows
