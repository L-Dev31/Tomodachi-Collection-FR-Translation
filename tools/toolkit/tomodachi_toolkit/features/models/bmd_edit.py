"""Rebuilds a model and a BMD0 file around new display lists."""
import struct

from ...core.binary import u16, u32
from .bmd import bmd_blocks


def mdl_assemble(b, model, dls, flags, counts, box):
    """New model data: the old data up to the first display list, then the new display lists in shape order."""
    m0 = model['off']
    if model['evp_off'] != m0 + model['size']:
        raise ValueError('This model has envelope data after the shapes: not supported')
    old = sorted((s['dl'], s['dlen']) for s in model['shapes'])
    if [d for d, _ in old] != [s['dl'] for s in model['shapes']] or any(a + n != c for (a, n), (c, _) in zip(old, old[1:])) or old[-1][0] + old[-1][1] != m0 + model['size']:
        raise ValueError('The display lists of this model are not stored one after another at the end: not supported')
    first = old[0][0] - m0
    head, body, pos = bytearray(b[m0:m0 + first]), bytearray(), first
    for k, sh in enumerate(model['shapes']):
        so = sh['off'] - m0
        struct.pack_into('<III', head, so + 4, flags[k], pos - so, len(dls[k]))
        body += dls[k]
        pos += len(dls[k])
    out = head + body
    struct.pack_into('<II', out, 0, len(out), model['sbc_off'] - m0)
    struct.pack_into('<I', out, 0x10, len(out))
    struct.pack_into('<4H', out, 0x24, *counts)
    if box:
        struct.pack_into('<6h', out, 0x2C, *box)
    return bytes(out)


def bmd_set_model(b, mi, new):
    """The model file b with model number mi replaced by the model data new (the size may change)."""
    b = bytearray(b)
    mo = bmd_blocks(bytes(b))[b'MDL0']
    o = mo + 8
    n = b[o + 1]
    p = o + 8 + (n + 1) * 4
    unit_ = u16(b, p)
    ep = p + 4
    offs = [u32(b, ep + j * unit_) for j in range(n)]
    m = mo + offs[mi]
    old = u32(b, m)
    delta = len(new) - old
    b[m:m + old] = new
    for j in range(n):
        if offs[j] > offs[mi]:
            struct.pack_into('<I', b, ep + j * unit_, offs[j] + delta)
    struct.pack_into('<I', b, mo + 4, u32(b, mo + 4) + delta)
    struct.pack_into('<I', b, 8, u32(b, 8) + delta)
    for i in range(u16(b, 14)):
        q = u32(b, 16 + 4 * i)
        if q > mo:
            struct.pack_into('<I', b, 16 + 4 * i, q + delta)
    return bytes(b)
