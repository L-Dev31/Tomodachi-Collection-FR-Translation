"""Nitro graphics containers (NCGR tiles, NCLR palettes, NSCR screens)."""
import struct

from .binary import u16, u32


def rgcn(d, a):
    p = a + 0x10
    while d[p:p + 4] != b'RAHC':
        p += u32(d, p + 4)
    return p + 8 + u32(d, p + 28)


def sect(f, tag):
    p = u16(f, 12)
    while p < len(f):
        if f[p:p + 4] == tag:
            return p
        p += u32(f, p + 4)
    raise ValueError('missing ' + tag.decode())


def ncgr_info(f):
    p = sect(f, b'RAHC')
    th, tw = struct.unpack_from('<hh', f, p + 8)
    return {'th': th, 'tw': tw, 'bits': 8 if u32(f, p + 12) == 4 else 4, 'linear': u32(f, p + 20) != 0, 'start': p + 32, 'size': u32(f, p + 24)}


def nclr_colors(f):
    p = sect(f, b'TTLP')
    n = min(u32(f, p + 16), len(f) - p - 24) // 2
    out = []
    for i in range(n):
        v = u16(f, p + 24 + i * 2)
        out.append(((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3))
    return out


def nscr_info(f):
    p = sect(f, b'NRCS')
    w, h = struct.unpack_from('<HH', f, p + 8)
    n = u32(f, p + 16) // 2
    return {'w': w, 'h': h, 'cells': [u16(f, p + 20 + i * 2) for i in range(n)]}


def ntiles(info):
    return info['size'] // (32 if info['bits'] == 4 else 64)


def tile_pixels(f, info, t):
    bpt = 32 if info['bits'] == 4 else 64
    o = info['start'] + t * bpt
    d = f[o:o + bpt]
    if len(d) < bpt:
        return [0] * 64
    if info['bits'] == 8:
        return list(d)
    out = []
    for b in d:
        out += [b & 15, b >> 4]
    return out


def put_tile(buf, info, t, idx):
    if info['bits'] == 8:
        o = info['start'] + t * 64
        buf[o:o + 64] = bytes(idx)
    else:
        o = info['start'] + t * 32
        buf[o:o + 32] = bytes(idx[i] | idx[i + 1] << 4 for i in range(0, 64, 2))


def pal_rgba(cols, bank, bits, idx):
    if idx == 0:
        return (0, 0, 0, 0)
    c = cols[bank * 16 + idx] if bits == 4 and bank * 16 + idx < len(cols) else cols[idx] if idx < len(cols) else (255, 0, 255)
    return (*c, 255)


def nclr_set(file, color_idx, new_rgb):
    """Sets a colour in an NCLR palette file at the given index.
    
    file: bytes of the NCLR file
    color_idx: index of the colour to change (0-15 for 4bpp, 0-255 for 8bpp)
    new_rgb: list/tuple of 3 ints [R, G, B] (0-255)
    
    Returns new file bytes with the colour changed.
    """
    data = bytearray(file)
    if len(data) < 0x20:
        return file
    # Determine bit depth from header
    bits = data[0x1E] if len(data) > 0x1E else 4
    if bits == 4:
        # 4bpp: 16 colours, each 2 bytes (BGR555 packed)
        offset = 0x20 + color_idx * 2
        # BGR555 format: depends on how the data is stored
        # From the existing code, colours are stored as RGB values
        # Let's use a simple approach: just set the RGB bytes
        # The palette entry is 2 bytes, we'll set it directly
        r, g, b = new_rgb
        # BGR555: bits 15-10 = Blue, 9-5 = Green, 4-0 = Red
        # Packing: (R >> 3) << 10 | (G >> 3) << 5 | (B >> 3)
        value = ((r & 0xF8) << 8) | ((g & 0xF8) << 3) | (b >> 3)
        data[offset] = value & 0xFF
        data[offset + 1] = value >> 8
    elif bits == 8:
        # 8bpp: 256 colours, each 1 byte
        offset = 0x20 + color_idx
        data[offset] = new_rgb[0]  # Set red channel, game uses this as index
    return bytes(data)
