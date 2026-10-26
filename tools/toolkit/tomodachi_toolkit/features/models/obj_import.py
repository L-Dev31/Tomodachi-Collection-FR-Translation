"""OBJ back into a model: snaps to the original data where nothing changed."""
import collections
import math
import re

from .obj_export import obj_ident, obj_shape_name, shape_uv_size
from .bmd_edit import bmd_set_model, mdl_assemble
from .dlencode import dl_encode, dl_stats
from .geometry import gx_draw, mdl_models
from .matrix import cross, dot3, m_pt, m_vec, sub3, unit
from .shapes import ShapeRef, canon_polys, mdl_draws, poly_flat, poly_key
from .bmd import bmd_textures


def obj_index(i, n):
    if i > 0:
        return i - 1
    if i < 0:
        return n + i
    raise ValueError('index 0 in a face')


def obj_parse(text):
    """OBJ text -> (positions, texture coordinates, normals, {object name: faces}); a face is a list of (v, vt, vn) indices."""
    V, VT, VN, objs = [], [], [], {}
    has_o = re.search(r'^o\s', text, re.M) is not None
    cur = ''
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0][0] == '#':
            continue
        k = parts[0]
        try:
            if k == 'v':
                V.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif k == 'vt':
                VT.append((float(parts[1]), float(parts[2]) if len(parts) > 2 else 0.0))
            elif k == 'vn':
                VN.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif k == 'o' or (k == 'g' and not has_o):
                cur = line.split(None, 1)[1].strip() if len(parts) > 1 else ''
            elif k == 'f':
                face = []
                for tok in parts[1:]:
                    f = tok.split('/')
                    face.append((obj_index(int(f[0]), len(V)),
                                 obj_index(int(f[1]), len(VT)) if len(f) > 1 and f[1] else None,
                                 obj_index(int(f[2]), len(VN)) if len(f) > 2 and f[2] else None))
                objs.setdefault(cur, []).append(face)
        except (ValueError, IndexError):
            raise ValueError('Cannot read this line of the OBJ file: ' + line[:60])
    return V, VT, VN, objs


def newell(P):
    nx = ny = nz = 0.0
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def pos_key(P):
    """A polygon as a loop of rounded positions that does not depend on the corner it starts at."""
    q = [(round(p[0], 5) + 0.0, round(p[1], 5) + 0.0, round(p[2], 5) + 0.0) for p in P]
    return min(tuple(q[i:] + q[:i]) for i in range(len(q)))


def face_split(P, keep=False):
    """Corner index tuples (3 or 4 corners) that tile a polygon; a quad stays a quad when it is convex (or when keep is set)."""
    n = len(P)
    if n == 3:
        return [(0, 1, 2)]
    nrm = newell(P)
    tol = 1e-6 * dot3(nrm, nrm)

    def turn(a, b, c):
        return dot3(cross(sub3(P[b], P[a]), sub3(P[c], P[b])), nrm)

    if n == 4:
        if keep or all(turn(i, (i + 1) % 4, (i + 2) % 4) >= -tol for i in range(4)):
            return [(0, 1, 2, 3)]
        for a, b in (((0, 1, 2), (0, 2, 3)), ((0, 1, 3), (1, 2, 3))):
            if turn(*a) > 0 and turn(*b) > 0:
                return [a, b]
        return [(0, 1, 2), (0, 2, 3)]
    idx, out = list(range(n)), []
    while len(idx) > 3:
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if turn(a, b, c) <= 0:
                continue
            if any(o not in (a, b, c) and all(dot3(cross(sub3(P[y], P[x]), sub3(P[o], P[x])), nrm) >= 0 for x, y in ((a, b), (b, c), (c, a))) for o in idx):
                continue
            out.append((a, b, c))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        out.append(tuple(idx))
    else:
        out += [(idx[0], idx[i], idx[i + 1]) for i in range(1, len(idx) - 1)]
    return out


def local_normal(ref, slot, n):
    inv = ref.mat(slot)[1]
    ln = unit(m_vec(inv, n)) if inv else None
    if ln is None:
        return (0, 511, 0)
    return tuple(max(-512, min(511, round(q * 512))) for q in ln)


def resolve_corner(ref, P, st, n, cent):
    """Display list corner (x, y, z, s, t, nx, ny, nz, slot) for the model space point P.
    A point that is still an original vertex gets the original values back, so untouched geometry is kept bit for bit."""
    best = None
    for i in ref.near(P, ref.tol):
        v, _, vn, pi = ref.corners[i]
        L = m_pt(ref.mat(v[8])[1], P)
        if abs(L[0] * 4096 - v[0]) > 0.6 or abs(L[1] * 4096 - v[1]) > 0.6 or abs(L[2] * 4096 - v[2]) > 0.6:
            continue
        ubad = st is not None and (abs(st[0] - v[3]) > 1 or abs(st[1] - v[4]) > 1)
        nbad = n is not None and vn is not None and dot3(n, vn) < 0.9986
        c = ref.cent[pi]
        key = (ubad + nbad, (c[0] - cent[0]) ** 2 + (c[1] - cent[1]) ** 2 + (c[2] - cent[2]) ** 2)
        if best is None or key < best[0]:
            best = (key, v, ubad, nbad)
    if best:
        _, v, ubad, nbad = best
        s, t = st if ubad else (v[3], v[4])
        ln = local_normal(ref, v[8], n) if nbad else v[5:8]
        return v[:3] + (s, t) + tuple(ln) + (v[8],)
    near = ref.nearest(P)
    if near:
        c = min(near, key=lambda i: sum((ref.cent[ref.corners[i][3]][a] - cent[a]) ** 2 for a in range(3)))
        slot, fallback = ref.corners[c][0][8], ref.corners[c][0][5:8]
    else:
        slot, fallback = (ref.alias if ref.alias is not None else -1), (0, 511, 0)
    inv = ref.mat(slot)[1]
    if inv is None:
        raise ValueError('The matrix of this shape cannot be inverted')
    x, y, z = (round(q * 4096) for q in m_pt(inv, P))
    if min(x, y, z) < -32768 or max(x, y, z) > 32767:
        raise ValueError('A vertex is too far from the part it belongs to (the game stores positions within +-8 units of the part): scale it down or move it closer')
    ln = local_normal(ref, slot, n) if n is not None else fallback
    s, t = st if st is not None else (0, 0)
    return (x, y, z, s, t, ln[0], ln[1], ln[2], slot)


def shape_import(ref, faces, V, VT, VN, dims, warn):
    """Polygons (tuples of display list corners) for the faces of one OBJ object."""
    tw, th = dims
    polys = []
    quads = {pos_key([w[0] for w in ref.wp[pi]]) for pi, q in enumerate(ref.polys) if len(q) == 4}
    for face in faces:
        if len(face) < 3:
            continue
        for vi, ti, ni in face:
            if vi >= len(V) or (ti is not None and ti >= len(VT)) or (ni is not None and ni >= len(VN)):
                raise ValueError('A face uses a vertex that does not exist')
        P = [V[c[0]] for c in face]
        for t in face_split(P, len(face) == 4 and pos_key(P) in quads):
            polys.append([face[i] for i in t])
    gen = {}
    if any(c[2] is None or unit(VN[c[2]]) is None for p in polys for c in p):
        acc = {}
        for p in polys:
            fn = newell([V[c[0]] for c in p])
            for c in p:
                a = acc.get(c[0], (0.0, 0.0, 0.0))
                acc[c[0]] = (a[0] + fn[0], a[1] + fn[1], a[2] + fn[2])
        gen = {k: unit(v) for k, v in acc.items()}
    out, nouv = [], 0
    for p in polys:
        Ps = [V[c[0]] for c in p]
        cent = tuple(sum(q[a] for q in Ps) / len(Ps) for a in range(3))
        poly = []
        for (vi, ti, ni), P in zip(p, Ps):
            n = unit(VN[ni]) if ni is not None else None
            if n is None:
                n = gen.get(vi)
            st = None
            if ref.tex:
                if ti is None:
                    nouv += 1
                else:
                    st = (round(VT[ti][0] * 16 * tw), round((1 - VT[ti][1]) * 16 * th))
                    if min(st) < -32768 or max(st) > 32767:
                        raise ValueError('Texture coordinates go too far outside the picture (the limit is 2048 pixels)')
            poly.append(resolve_corner(ref, P, st, n, cent))
        out.append(tuple(poly))
    if nouv:
        warn('%d corner(s) without texture coordinates kept the original ones or got 0.' % nouv)
    return out


def obj_target(name, models):
    mm = re.match(r'^(?:m(\d+)_)?(\d+)_', name)
    if mm:
        mi, si = int(mm.group(1) or 0), int(mm.group(2))
        if mi < len(models) and si < len(models[mi]['shapes']):
            return mi, si
    base = obj_ident(re.sub(r'\.\d+$', '', name))
    hits = [(mi, si) for mi, m in enumerate(models) for si, s in enumerate(m['shapes']) if obj_ident(s['name']) == base]
    return hits[0] if len(hits) == 1 else None


def obj_import(b, text):
    """Model file b + OBJ text -> (new model file or None when nothing changed, report).
    report: shapes (changed shape names), warnings, polys/verts (new totals), size (old, new model data bytes)."""
    models = mdl_models(b)
    try:
        texs, _ = bmd_textures(b)
    except Exception:
        texs = []
    by_tex = {t['name']: t for t in texs}
    V, VT, VN, objs = obj_parse(text)
    rep = {'shapes': [], 'warnings': [], 'unchanged': 0, 'size': (0, 0), 'polys': (0, 0), 'verts': (0, 0)}
    groups = {}
    for name, faces in objs.items():
        tg = obj_target(name, models)
        if tg is None:
            rep['warnings'].append('Object "%s" does not match any shape and was ignored.' % name)
        else:
            groups.setdefault(tg, []).extend(faces)
    if not groups:
        raise ValueError('No object of this file is named like the exported shapes (00_name, 01_name, ...).')
    new_models, size_old, size_new, pv_old, pv_new = {}, 0, 0, [0, 0], [0, 0]
    for mi in sorted({k[0] for k in groups}):
        m = models[mi]
        draws = {d['shape']: d for d in mdl_draws(m)}
        refs = {k: ShapeRef(b, m, d) for k, d in draws.items()}
        dls = [bytes(b[s['dl']:s['dl'] + s['dlen']]) for s in m['shapes']]
        flags = [s['flags'] for s in m['shapes']]
        final = {k: r.polys for k, r in refs.items()}
        changed = []
        for (gm_, si), faces in sorted(groups.items()):
            if gm_ != mi:
                continue
            nm = obj_shape_name(len(models) > 1, mi, si, m['shapes'][si]['name'])
            if si not in refs:
                rep['warnings'].append('Shape %s is never drawn: ignored.' % nm)
                continue
            ref = refs[si]
            wl = []
            try:
                polys = shape_import(ref, faces, V, VT, VN, shape_uv_size(m, draws[si], by_tex), wl.append)
            except ValueError as e:
                raise ValueError('%s: %s' % (nm, e))
            rep['warnings'] += ['%s: %s' % (nm, w) for w in wl]
            enc = [p for p in polys if not poly_flat(p)]
            if collections.Counter(map(poly_key, enc)) == collections.Counter(poly_key(p) for p in ref.polys if not poly_flat(p)):
                rep['unchanged'] += 1
                continue
            dl, restores = dl_encode(enc, ref.tex, ref.alias)
            back = canon_polys(gx_draw(dl, {'dl': 0, 'dlen': len(dl)}, None), ref.alias)
            if collections.Counter(map(poly_key, back)) != collections.Counter(map(poly_key, enc)):
                raise ValueError('%s: internal error, the display list does not read back as the mesh' % nm)
            dls[si], final[si] = dl, enc
            flags[si] = flags[si] & ~8 | (8 if restores else 0)
            changed.append((nm, len(ref.polys), len(enc)))
        if not changed:
            continue
        counts = [0, 0, 0, 0]
        for dl in dls:
            for k, v in enumerate(dl_stats(dl)):
                counts[k] += v
        if max(counts) > 65535:
            raise ValueError('Too many vertices or polygons for one model')
        lo, hi = [1e300] * 3, [-1e300] * 3
        for si, polys in final.items():
            for poly in polys:
                for v in poly:
                    p = m_pt(refs[si].mat(v[8])[0], (v[0] / 4096, v[1] / 4096, v[2] / 4096))
                    for a in range(3):
                        lo[a], hi[a] = min(lo[a], p[a]), max(hi[a], p[a])
        bs = m['box_scale'] or 1.0
        mn = [max(-32768, min(32767, math.floor(x * 4096 / bs))) for x in lo]
        sz = [max(0, min(32767, math.ceil(h * 4096 / bs) - a)) for h, a in zip(hi, mn)]
        new_models[mi] = mdl_assemble(b, m, dls, flags, counts, mn + sz)
        rep['shapes'] += changed
        size_old, size_new = size_old + m['size'], size_new + len(new_models[mi])
        pv_old[0] += m['counts'][1]
        pv_old[1] += m['counts'][0]
        pv_new[0] += counts[1]
        pv_new[1] += counts[0]
    rep['size'], rep['polys'], rep['verts'] = (size_old, size_new), tuple(pv_old[:1] + pv_new[:1]), (pv_old[1], pv_new[1])
    if not new_models:
        return None, rep
    out = b
    for mi in sorted(new_models, key=lambda k: -models[k]['off']):
        out = bmd_set_model(out, mi, new_models[mi])
    chk = mdl_models(out)
    if len(chk) != len(models):
        raise ValueError('internal error: the rebuilt file lost a model')
    try:
        t2, _ = bmd_textures(out)
        if [out[t['off']:t['off'] + t['size']] for t in t2] != [b[t['off']:t['off'] + t['size']] for t in texs]:
            raise ValueError('internal error: the textures moved')
    except ValueError:
        raise
    return out, rep
