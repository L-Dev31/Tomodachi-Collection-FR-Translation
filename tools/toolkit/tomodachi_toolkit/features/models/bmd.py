"""BMD0 container: blocks, dictionaries and textures list."""
import struct

from ...core.binary import u16, u32


TEX_FORMATS = {1: 'A3I5', 2: '4 colours', 3: '16 colours', 4: '256 colours', 5: '4x4 compressed', 6: 'A5I3', 7: '16 bit'}


TEX_COLORS = {1: 32, 2: 4, 3: 16, 4: 256, 6: 8}


def bmd_blocks(b):
    if b[:4] not in (b'BMD0', b'BTX0') or len(b) < 20:
        raise ValueError('not a model file')
    n = u16(b, 14)
    return {b[o:o + 4]: o for o in (u32(b, 16 + 4 * i) for i in range(n)) if o + 4 <= len(b)}


def dict_entries(b, o, size):
    """Nitro dictionary: returns (entries bytes list, names list)."""
    n = b[o + 1]
    p = o + 4 + 4 + (n + 1) * 4
    unit, total = struct.unpack_from('<HH', b, p)
    p += 4
    ents = [bytes(b[p + i * unit:p + (i + 1) * unit]) for i in range(n)]
    q = p + n * unit
    names = [bytes(b[q + i * 16:q + (i + 1) * 16]).split(b'\0')[0].decode('latin1') for i in range(n)]
    return ents, names


def bmd_textures(b):
    """List of dicts: name, fmt, w, h, tr0, off (absolute data offset), size, pal (index or None), plus palette list."""
    blocks = bmd_blocks(b)
    if b'TEX0' not in blocks:
        return [], []
    tx = blocks[b'TEX0']
    tdata, cdata, cinfo, pdata = u32(b, tx + 0x14), u32(b, tx + 0x24), u32(b, tx + 0x28), u32(b, tx + 0x38)
    ents, names = dict_entries(b, tx + u16(b, tx + 0xE), 0)
    pents, pnames = ([], [])
    if u32(b, tx + 0x34):
        pents, pnames = dict_entries(b, tx + u32(b, tx + 0x34), 0)
    pals = []
    offs = sorted(u16(e, 0) << 3 for e in pents)
    for e, nm in zip(pents, pnames):
        o = u16(e, 0) << 3
        nxt = next((x for x in offs if x > o), None)
        end = (nxt if nxt is not None else (u32(b, tx + 0x30) << 3)) 
        pals.append({'name': nm, 'off': tx + pdata + o, 'size': max(0, end - o)})
    out = []
    for e, nm in zip(ents, names):
        off, param = u16(e, 0), u16(e, 2)
        fmt, w, h = param >> 10 & 7, 8 << (param >> 4 & 7), 8 << (param >> 7 & 7)
        bits = {1: 8, 2: 2, 3: 4, 4: 8, 5: 2, 6: 8, 7: 16}.get(fmt, 0)
        t = {'name': nm, 'fmt': fmt, 'w': w, 'h': h, 'tr0': param >> 13 & 1, 'size': w * h * bits // 8}
        if fmt == 5:
            t['off'] = tx + cdata + (off << 3)
            t['info'] = tx + cinfo + (off << 2)
        else:
            t['off'] = tx + tdata + (off << 3)
        t['pal'] = next((i for i, p in enumerate(pals) if p['name'] in (nm + '_pl', nm)), None)
        out.append(t)
    return out, pals
