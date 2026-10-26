"""Texture decode and encode (all NDS texture formats)."""
import struct

from ...core.binary import u16, u32
from .bmd import TEX_COLORS


def _col(v):
    return ((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3)


def tex_palette(b, t, pals):
    if t['pal'] is None:
        n = TEX_COLORS.get(t['fmt'], 16)
        return [(i * 255 // max(1, n - 1),) * 3 for i in range(n)]
    p = pals[t['pal']]
    return [_col(u16(b, p['off'] + 2 * i)) for i in range((min(p['size'], len(b) - p['off'])) // 2)]


def tex_render(b, t, pals):
    w, h, fmt = t['w'], t['h'], t['fmt']
    pal = tex_palette(b, t, pals)
    d = b[t['off']:t['off'] + t['size']]
    out = bytearray(w * h * 4)

    def put(i, c, a):
        out[i * 4:i * 4 + 4] = bytes((c[0], c[1], c[2], a))

    def pc(i):
        return pal[i] if i < len(pal) else (0, 0, 0)

    if fmt in (2, 3, 4):
        bits = {2: 2, 3: 4, 4: 8}[fmt]
        for i in range(w * h):
            v = d[i * bits // 8]
            idx = v if bits == 8 else (v >> (i * bits % 8)) & ((1 << bits) - 1)
            put(i, pc(idx), 0 if (idx == 0 and t['tr0']) else 255)
    elif fmt == 1:
        for i in range(w * h):
            v = d[i]
            put(i, pc(v & 31), (v >> 5) * 255 // 7)
    elif fmt == 6:
        for i in range(w * h):
            v = d[i]
            put(i, pc(v & 7), (v >> 3) * 255 // 31)
    elif fmt == 7:
        for i in range(w * h):
            v = u16(d, i * 2)
            put(i, _col(v), 255 if v & 0x8000 else 0)
    elif fmt == 5:
        for by in range(h // 4):
            for bx in range(w // 4):
                k = by * (w // 4) + bx
                tex = u32(b, t['off'] + 4 * k)
                inf = u16(b, t['info'] + 2 * k)
                po, mode = (inf & 0x3FFF) * 2, inf >> 14
                c = [pc(po), pc(po + 1)]
                if mode == 0:
                    cols = [c[0], c[1], c[0], c[0]]
                    alpha = [255, 255, 255, 0]
                    cols[2] = c[0]
                elif mode == 1:
                    cols = [c[0], c[1], tuple((x + y) // 2 for x, y in zip(c[0], c[1])), (0, 0, 0)]
                    alpha = [255, 255, 255, 0]
                elif mode == 2:
                    cols = [c[0], c[1], pc(po + 2), pc(po + 3)]
                    alpha = [255] * 4
                else:
                    cols = [c[0], c[1], tuple((5 * x + 3 * y) // 8 for x, y in zip(c[0], c[1])), tuple((3 * x + 5 * y) // 8 for x, y in zip(c[0], c[1]))]
                    alpha = [255] * 4
                for j in range(16):
                    ix = tex >> (2 * j) & 3
                    put((by * 4 + j // 4) * w + bx * 4 + j % 4, cols[ix], alpha[ix])
    else:
        raise ValueError('Unknown texture format')
    return w, h, bytes(out)


def tex_encode(b, t, pals, w, h, rgba):
    """Returns new file bytes with texture t replaced by the RGBA picture (same size)."""
    fmt = t['fmt']
    if fmt == 5:
        raise ValueError('4x4 compressed textures can be exported but not imported yet')
    if (w, h) != (t['w'], t['h']):
        raise ValueError(f"Picture must be {t['w']} x {t['h']} pixels (it is {w} x {h})")
    pal = tex_palette(b, t, pals)
    buf = bytearray(b)
    cache, snapped = {}, 0

    def best(px, lo):
        nonlocal snapped
        key = (px, lo)
        if key not in cache:
            bi, bd = 0, 1 << 30
            for i in range(lo, min(len(pal), TEX_COLORS.get(fmt, 0))):
                c = pal[i]
                dd = (c[0] - px[0]) ** 2 + (c[1] - px[1]) ** 2 + (c[2] - px[2]) ** 2
                if dd < bd:
                    bi, bd = i, dd
            cache[key] = (bi, bd)
        snapped += cache[key][1] > 64
        return cache[key][0]

    o = t['off']
    if fmt in (2, 3, 4):
        bits = {2: 2, 3: 4, 4: 8}[fmt]
        for i in range(w * h):
            px = tuple(rgba[i * 4:i * 4 + 4])
            if t['tr0'] and px[3] < 128:
                idx = 0
            else:
                idx = best(px[:3], 1 if t['tr0'] else 0)
            if bits == 8:
                buf[o + i] = idx
            else:
                sh = i * bits % 8
                j = o + i * bits // 8
                buf[j] = (buf[j] & ~(((1 << bits) - 1) << sh)) | idx << sh
    elif fmt in (1, 6):
        amax = 7 if fmt == 1 else 31
        mask = 31 if fmt == 1 else 7
        sh = 5 if fmt == 1 else 3
        for i in range(w * h):
            px = tuple(rgba[i * 4:i * 4 + 4])
            buf[o + i] = best(px[:3], 0) & mask | (px[3] * amax + 127) // 255 << sh
    else:
        for i in range(w * h):
            r, g, bb, a = rgba[i * 4:i * 4 + 4]
            struct.pack_into('<H', buf, o + i * 2, (r >> 3) | (g >> 3) << 5 | (bb >> 3) << 10 | (0x8000 if a >= 128 else 0))
    return bytes(buf), snapped
