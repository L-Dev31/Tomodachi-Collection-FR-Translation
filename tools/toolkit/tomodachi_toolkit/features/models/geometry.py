"""MDL0 parser: nodes, render commands, GX display lists."""
import struct

from ...core.binary import u16, u32
from .matrix import m_mul, m_scale, pivot_rot, s16, s32
from .bmd import bmd_blocks, dict_entries


GX_PARAMS = {
    0x00: 0, 0x10: 1, 0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 16, 0x17: 12, 0x18: 16, 0x19: 12, 0x1A: 9, 0x1B: 3, 0x1C: 3,
    0x20: 1, 0x21: 1, 0x22: 1, 0x23: 2, 0x24: 1, 0x25: 1, 0x26: 1, 0x27: 1, 0x28: 1, 0x29: 1, 0x2A: 1, 0x2B: 1,
    0x30: 1, 0x31: 1, 0x32: 1, 0x33: 1, 0x34: 32, 0x40: 1, 0x41: 0, 0x50: 1, 0x60: 1, 0x70: 3, 0x71: 2, 0x72: 1}


SBC_PARAMS = {0x00: 0, 0x01: 0, 0x02: 2, 0x03: 1, 0x04: 1, 0x05: 1, 0x06: 3, 0x07: 1, 0x08: 1, 0x0B: 0, 0x0C: 2, 0x0D: 2,
              0x24: 1, 0x26: 4, 0x2B: 0, 0x40: 0, 0x44: 1, 0x46: 4, 0x47: 2, 0x66: 5, 0x80: 0}


MDL_IDENT = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def mdl_info(b, o):
    """Parses a Nitro dictionary at o: list of (entry bytes, name)."""
    ents, names = dict_entries(b, o, 0)
    return list(zip(ents, names))


def mdl_node(b, p):
    flags = u16(b, p)
    m0 = s16(b, p + 2)
    p += 4
    t, s, rot = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if not flags & 1:
        t = tuple(s32(b, p + 4 * i) / 4096 for i in range(3))
        p += 12
    if flags & 8:
        a, bb = s16(b, p) / 4096, s16(b, p + 2) / 4096
        p += 4
        sel = flags >> 4 & 15
        if sel >= 9:
            raise ValueError('pivot form not understood')
        rot = pivot_rot(sel, flags >> 8 & 15, a, bb)
    elif not flags & 2:
        v = [m0] + [s16(b, p + 2 * i) for i in range(8)]
        p += 16
        rot = tuple(tuple(v[3 * j + i] / 4096 for j in range(3)) for i in range(3))
    if not flags & 4:
        s = tuple(s32(b, p + 4 * i) / 4096 for i in range(3))
    m = []
    for i in range(3):
        for j in range(3):
            m.append(rot[i][j] * s[j])
        m.append(t[i])
    return {'flags': flags, 't': t, 's': s, 'rot': rot, 'matrix': tuple(m)}


def sbc_parse(b, p):
    """Render commands at p: list of (offset, opcode, params bytes)."""
    out = []
    while True:
        o = p
        op = b[p]
        p += 1
        if op == 0x09:
            n = b[p + 1]
            k = 2 + 3 * n
        elif op in SBC_PARAMS:
            k = SBC_PARAMS[op]
        else:
            raise ValueError(f'unknown render command {op:#x}')
        out.append((o, op, bytes(b[p:p + k])))
        p += k
        if op == 0x01:
            return out


def mat_srt(b, p, flags):
    """Scale, rotation (sine, cosine or None) and translation of the texture matrix of a material; the translation counts in textures."""
    scale, rot, trans = (1.0, 1.0), None, (0.0, 0.0)
    if flags & 1:
        if not flags & 2:
            scale = (s32(b, p) / 4096, s32(b, p + 4) / 4096)
            p += 8
        if not flags & 4:
            rot = (s16(b, p) / 4096, s16(b, p + 2) / 4096)
            p += 4
        if not flags & 8:
            trans = (s32(b, p) / 4096, s32(b, p + 4) / 4096)
    return scale, rot, trans


def mdl_model(b, m, name):
    size, o_sbc, o_mat, o_shp, o_evp = struct.unpack_from('<5I', b, m)
    sbc_type, scaling, texmtx, n_node, n_mat, n_shp, first_unused, _ = b[m + 0x14:m + 0x1C]
    up, down = s32(b, m + 0x1C) / 4096, s32(b, m + 0x20) / 4096
    n_vert, n_poly, n_tri, n_quad = struct.unpack_from('<4H', b, m + 0x24)
    box = struct.unpack_from('<6h', b, m + 0x2C)
    box_scale, box_inv = s32(b, m + 0x38) / 4096, s32(b, m + 0x3C) / 4096
    nd = m + 0x40
    nodes = []
    for e, nm in mdl_info(b, nd):
        n = mdl_node(b, nd + u32(e, 0))
        n['name'] = nm
        nodes.append(n)
    mat0 = m + o_mat
    tex_pair, pal_pair = u16(b, mat0), u16(b, mat0 + 2)
    mats = []
    for e, nm in mdl_info(b, mat0 + 4):
        q = mat0 + u32(e, 0)
        dif_amb, spe_emi, pattr, pmask, tparam, unk3, pbase, misc = struct.unpack_from('<IIIIIIHH', b, q + 4)
        w, h = u16(b, q + 0x20), u16(b, q + 0x22)
        mats.append({'name': nm, 'off': q, 'dif_amb': dif_amb, 'spe_emi': spe_emi, 'attr': pattr, 'mask': pmask, 'tparam': tparam,
                     'misc': misc, 'w': w, 'h': h, 'tex': None, 'pal': None, 'srt': mat_srt(b, q + 0x2C, misc)})
    for key, o in (('tex', tex_pair), ('pal', pal_pair)):
        for e, nm in mdl_info(b, mat0 + o):
            off, num = u16(e, 0), e[2]
            for mi in b[mat0 + off:mat0 + off + num]:
                mats[mi][key] = nm
    shp0 = m + o_shp
    shapes = []
    for e, nm in mdl_info(b, shp0):
        q = shp0 + u32(e, 0)
        _, ssize, flags, dloff, dlen = struct.unpack_from('<HHIII', b, q)
        shapes.append({'name': nm, 'off': q, 'size': ssize, 'flags': flags, 'dl': q + dloff, 'dlen': dlen})
    return {'name': name, 'off': m, 'size': size, 'sbc_off': m + o_sbc, 'mat_off': mat0, 'shp_off': shp0, 'evp_off': m + o_evp,
            'sbc_type': sbc_type, 'scaling': scaling, 'texmtx': texmtx, 'first_unused': first_unused,
            'up': up, 'down': down, 'counts': (n_vert, n_poly, n_tri, n_quad), 'box': box, 'box_scale': box_scale, 'box_inv': box_inv,
            'nodes': nodes, 'materials': mats, 'shapes': shapes, 'n_node': n_node, 'n_mat': n_mat, 'n_shp': n_shp,
            'sbc': sbc_parse(b, m + o_sbc), 'node_dict': nd}


def mdl_models(b):
    blocks = bmd_blocks(b)
    mo = blocks.get(b'MDL0')
    if mo is None:
        return []
    return [mdl_model(b, mo + u32(e, 0), nm) for e, nm in mdl_info(b, mo + 8)]


def gx_parse(b, o, n):
    """Display list bytes -> list of (opcode, params tuple); NOPs are dropped."""
    out, end = [], o + n
    while o < end:
        ops = b[o:o + 4]
        o += 4
        for op in ops:
            if op not in GX_PARAMS:
                raise ValueError(f'unknown GX command {op:#x}')
            k = GX_PARAMS[op]
            if o + 4 * k > end + 0:
                if op == 0:
                    continue
                raise ValueError('display list is cut')
            if op:
                out.append((op, struct.unpack_from('<%dI' % k, b, o)))
            o += 4 * k
    return out


def mdl_walk(model, matrices=None, world=None):
    """Runs the render commands. Returns the draw calls: dict(op, shape, mat, matrix, stack).
    matrices replaces the local matrices of the nodes (a pose of an animation); world, a dict, receives the matrix of every node."""
    cur, stack, mat, draws = MDL_IDENT, [MDL_IDENT] * 32, 0, []
    nodes = model['nodes']
    local = matrices if matrices is not None else [n['matrix'] for n in nodes]
    for k, (off, op, pr) in enumerate(model['sbc']):
        if op == 0x03:
            cur = stack[pr[0]]
        elif op in (0x04, 0x24, 0x44):
            mat = pr[0]
        elif op == 0x05:
            draws.append({'op': k, 'shape': pr[0], 'mat': mat, 'matrix': cur, 'stack': tuple(stack)})
        elif op in (0x06, 0x26, 0x46, 0x66):
            if op in (0x46, 0x66):
                cur = stack[pr[4] if op == 0x66 else pr[3]]
            cur = m_mul(cur, local[pr[0]])
            if world is not None:
                world[pr[0]] = cur
            if op in (0x26, 0x66):
                stack[pr[3]] = cur
        elif op == 0x0B:
            cur = m_mul(cur, m_scale(model['up']))
        elif op == 0x2B:
            cur = m_mul(cur, m_scale(model['down']))
    return draws


def gx_draw(b, shape, draw):
    """Executes a shape's display list. Returns the polygons: lists of vertex tuples
    (x, y, z, s, t, nx, ny, nz, slot) in raw fixed point (positions 1/4096, texcoords 1/16, normals 1/512);
    slot is the matrix stack slot that was current when the vertex was sent (None: the matrix of the draw call)."""
    cmds = gx_parse(b, shape['dl'], shape['dlen'])
    polys = []
    pos, st, nrm, slot = [0, 0, 0], [0, 0], [0, 0, 0], None
    prim, verts = None, []

    def flush():
        nonlocal prim, verts
        v = verts
        if prim == 0:
            for i in range(0, len(v) - 2, 3):
                polys.append([v[i], v[i + 1], v[i + 2]])
        elif prim == 1:
            for i in range(0, len(v) - 3, 4):
                polys.append([v[i], v[i + 1], v[i + 2], v[i + 3]])
        elif prim == 2:
            for i in range(len(v) - 2):
                polys.append([v[i], v[i + 1], v[i + 2]] if i % 2 == 0 else [v[i], v[i + 2], v[i + 1]])
        elif prim == 3:
            for i in range(0, len(v) - 3, 2):
                polys.append([v[i], v[i + 1], v[i + 3], v[i + 2]])
        prim, verts = None, []

    def sgn(x, bits):
        return x - (1 << bits) if x & (1 << (bits - 1)) else x

    for op, pr in cmds:
        if op == 0x14:
            slot = pr[0] & 31
        elif op == 0x40:
            flush()
            prim = pr[0] & 3
        elif op == 0x41:
            flush()
        elif op == 0x22:
            st = [sgn(pr[0] & 0xFFFF, 16), sgn(pr[0] >> 16, 16)]
        elif op == 0x21:
            nrm = [sgn(pr[0] & 0x3FF, 10), sgn(pr[0] >> 10 & 0x3FF, 10), sgn(pr[0] >> 20 & 0x3FF, 10)]
        elif op in (0x23, 0x24, 0x25, 0x26, 0x27, 0x28):
            if op == 0x23:
                pos = [sgn(pr[0] & 0xFFFF, 16), sgn(pr[0] >> 16, 16), sgn(pr[1] & 0xFFFF, 16)]
            elif op == 0x24:
                pos = [sgn(pr[0] & 0x3FF, 10) << 6, sgn(pr[0] >> 10 & 0x3FF, 10) << 6, sgn(pr[0] >> 20 & 0x3FF, 10) << 6]
            elif op == 0x25:
                pos = [sgn(pr[0] & 0xFFFF, 16), sgn(pr[0] >> 16, 16), pos[2]]
            elif op == 0x26:
                pos = [sgn(pr[0] & 0xFFFF, 16), pos[1], sgn(pr[0] >> 16, 16)]
            elif op == 0x27:
                pos = [pos[0], sgn(pr[0] & 0xFFFF, 16), sgn(pr[0] >> 16, 16)]
            else:
                pos = [pos[0] + sgn(pr[0] & 0x3FF, 10), pos[1] + sgn(pr[0] >> 10 & 0x3FF, 10), pos[2] + sgn(pr[0] >> 20 & 0x3FF, 10)]
            verts.append((pos[0], pos[1], pos[2], st[0], st[1], nrm[0], nrm[1], nrm[2], slot))
    flush()
    return polys
