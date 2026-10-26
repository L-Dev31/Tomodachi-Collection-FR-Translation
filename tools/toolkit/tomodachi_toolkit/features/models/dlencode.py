"""Encodes polygons back to GX display lists (strips, shortest vertex commands)."""
import struct

from .geometry import gx_draw, gx_parse


def gx_pos(p, prev):
    """The shortest command that moves the vertex position register from prev to p."""
    x, y, z = p
    if prev is not None:
        dx, dy, dz = x - prev[0], y - prev[1], z - prev[2]
        if -512 <= dx <= 511 and -512 <= dy <= 511 and -512 <= dz <= 511:
            return 0x28, [dx & 0x3FF | (dy & 0x3FF) << 10 | (dz & 0x3FF) << 20]
        if dz == 0:
            return 0x25, [x & 0xFFFF | (y & 0xFFFF) << 16]
        if dy == 0:
            return 0x26, [x & 0xFFFF | (z & 0xFFFF) << 16]
        if dx == 0:
            return 0x27, [y & 0xFFFF | (z & 0xFFFF) << 16]
    if x % 64 == 0 and y % 64 == 0 and z % 64 == 0 and min(p) >= -32768 and max(p) <= 32704:
        return 0x24, [x >> 6 & 0x3FF | (y >> 6 & 0x3FF) << 10 | (z >> 6 & 0x3FF) << 20]
    return 0x23, [x & 0xFFFF | (y & 0xFFFF) << 16, z & 0xFFFF]


def gx_pack(cmds):
    out = bytearray()
    for i in range(0, len(cmds), 4):
        grp = cmds[i:i + 4]
        out += bytes([c[0] for c in grp] + [0] * (4 - len(grp)))
        for _, params in grp:
            for q in params:
                out += struct.pack('<I', q & 0xFFFFFFFF)
    return bytes(out) or bytes(4)


def dl_batches(polys):
    """Groups the polygons, in order, into independent triangles, independent quads, triangle strips and quad strips.
    Returns [(primitive type, vertices)]. Two corners are the same hardware vertex when the tuples are equal."""
    out, run, kind = [], [], 0

    def flush():
        nonlocal run
        if run:
            out.append((0 if kind == 3 else 1, [c for p in run for c in p]))
        run = []

    n, i = len(polys), 0
    while i < n:
        p = polys[i]
        best = None
        if len(p) == 3:
            for r in range(3):
                verts = [p[r], p[(r + 1) % 3], p[(r + 2) % 3]]
                j = i + 1
                while j < n and len(polys[j]) == 3:
                    q = polys[j]
                    x, y, t = verts[-2], verts[-1], len(verts) - 2
                    w = None
                    for s in range(3):
                        if t % 2 == 0:
                            if q[s] == x and q[(s + 1) % 3] == y:
                                w = q[(s + 2) % 3]
                        elif q[s] == x and q[(s + 2) % 3] == y:
                            w = q[(s + 1) % 3]
                    if w is None:
                        break
                    verts.append(w)
                    j += 1
                if best is None or j > best[0]:
                    best = (j, verts)
            typ = 2
        else:
            for r in range(4):
                verts = [p[r], p[(r + 1) % 4], p[(r + 3) % 4], p[(r + 2) % 4]]
                j = i + 1
                while j < n and len(polys[j]) == 4:
                    q = polys[j]
                    w = None
                    for s in range(4):
                        if q[s] == verts[-2] and q[(s + 1) % 4] == verts[-1]:
                            w = [q[(s + 3) % 4], q[(s + 2) % 4]]
                    if w is None:
                        break
                    verts += w
                    j += 1
                if best is None or j > best[0]:
                    best = (j, verts)
            typ = 3
        if best[0] - i >= 2:
            flush()
            out.append((typ, best[1]))
            i = best[0]
        else:
            if kind != len(p):
                flush()
                kind = len(p)
            run.append(p)
            i += 1
    flush()
    return out


def dl_encode(polys, tex, alias):
    """Polygons (tuples of 3 or 4 corners (x, y, z, s, t, nx, ny, nz, slot)) -> (display list bytes, number of MTX_RESTORE)."""
    cmds, cur, pos, st, nrm, restores = [], -1, None, None, None, 0
    for prim, verts in dl_batches(polys):
        cmds.append((0x40, [prim]))
        for c in verts:
            slot = c[8]
            if slot != cur and not (cur == -1 and slot == alias):
                if slot == -1:
                    raise ValueError('a vertex needs the matrix of the draw call after another matrix was loaded')
                cmds.append((0x14, [slot]))
                restores += 1
            cur = slot
            if (c[5], c[6], c[7]) != nrm:
                nrm = (c[5], c[6], c[7])
                cmds.append((0x21, [nrm[0] & 0x3FF | (nrm[1] & 0x3FF) << 10 | (nrm[2] & 0x3FF) << 20]))
            if tex and (c[3], c[4]) != st:
                st = (c[3], c[4])
                cmds.append((0x22, [st[0] & 0xFFFF | (st[1] & 0xFFFF) << 16]))
            p = (c[0], c[1], c[2])
            cmds.append(gx_pos(p, pos))
            pos = p
        cmds.append((0x41, []))
    return gx_pack(cmds), restores


def dl_stats(dl):
    """(vertex commands, polygons, triangles, quads) of a display list."""
    nv = sum(1 for op, _ in gx_parse(dl, 0, len(dl)) if 0x23 <= op <= 0x28)
    polys = gx_draw(dl, {'dl': 0, 'dlen': len(dl)}, None)
    nt = sum(1 for p in polys if len(p) == 3)
    return nv, len(polys), nt, len(polys) - nt
