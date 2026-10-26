"""Minimal PNG reader and writers (RGBA and indexed)."""
import struct
import zlib


def png_write(w, h, rgba):
    raw = b''.join(b'\0' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c))

    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def png_read(data):
    data = bytes(data)
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG file')
    p, idat, pal, trns, head = 8, b'', None, None, None
    while p < len(data):
        n, tag = struct.unpack_from('>I4s', data, p)
        body = data[p + 8:p + 8 + n]
        if tag == b'IHDR':
            head = struct.unpack('>IIBBBBB', body)
        elif tag == b'PLTE':
            pal = body
        elif tag == b'tRNS':
            trns = body
        elif tag == b'IDAT':
            idat += body
        p += 12 + n
    w, h, depth, ctype, _, _, inter = head
    if inter:
        raise ValueError('Interlaced PNG not supported: save it without interlacing')
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, chans * depth // 8)
    stride = (w * chans * depth + 7) // 8
    raw = zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        cur = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = cur[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                cur[i] = (cur[i] + a) & 255
            elif f == 2:
                cur[i] = (cur[i] + b) & 255
            elif f == 3:
                cur[i] = (cur[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(cur)
        prev = cur
    out = bytearray(w * h * 4)
    for y, row in enumerate(rows):
        for x in range(w):
            if depth == 16:
                v = [row[(x * chans + c) * 2] for c in range(chans)]
            elif depth == 8:
                v = [row[x * chans + c] for c in range(chans)]
            else:
                per = 8 // depth
                v = [(row[x // per] >> (8 - depth * (x % per + 1))) & ((1 << depth) - 1)]
            o = (y * w + x) * 4
            if ctype == 3:
                i = v[0]
                out[o:o + 3] = pal[i * 3:i * 3 + 3]
                out[o + 3] = trns[i] if trns and i < len(trns) else 255
            elif ctype == 0:
                g = v[0] * 255 // ((1 << depth) - 1) if depth < 8 else v[0]
                out[o:o + 4] = bytes((g, g, g, 255))
            elif ctype == 4:
                out[o:o + 4] = bytes((v[0], v[0], v[0], v[1]))
            elif ctype == 2:
                out[o:o + 4] = bytes((*v, 255))
            else:
                out[o:o + 4] = bytes(v)
    return w, h, bytes(out)


def png_write_indexed(w, h, idx, pal, depth):
    raw = b''.join(b'\0' + (bytes(idx[y * w:(y + 1) * w]) if depth == 8 else bytes(idx[y * w + x] << 4 | idx[y * w + x + 1] for x in range(0, w, 2))) for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c))

    plte = b''.join(bytes(c) for c in pal)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, 3, 0, 0, 0)) + chunk(b'PLTE', plte) + chunk(b'tRNS', b'\0') + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
