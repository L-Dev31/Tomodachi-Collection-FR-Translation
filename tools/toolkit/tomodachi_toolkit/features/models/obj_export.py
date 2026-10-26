"""Model to OBJ, MTL and PNG files (for Blender and other 3D software)."""
import re

from .geometry import mdl_models
from .textures import tex_render
from .shapes import ShapeRef, mdl_draws, poly_flat
from ...core.png import png_write
from .bmd import bmd_textures


def obj_ident(s):
    return re.sub(r'[^A-Za-z0-9_-]', '_', s) or 'x'


def obj_shape_name(multi, mi, si, name):
    return ('m%d_' % mi if multi else '') + '%02d_%s' % (si, obj_ident(name))


def shape_uv_size(model, draw, by_tex):
    mat = model['materials'][draw['mat']] if draw['mat'] < len(model['materials']) else None
    t = by_tex.get(mat['tex']) if mat else None
    if t is not None:
        return t['w'], t['h']
    return (mat['w'] or 1, mat['h'] or 1) if mat else (1, 1)


def obj_export(b, stem):
    """Model file -> (obj text, mtl text, {png file name: bytes}, info). Positions are in model space (Y up)."""
    models = mdl_models(b)
    try:
        texs, pals = bmd_textures(b)
    except Exception:
        texs, pals = [], []
    by_tex = {t['name']: t for t in texs}
    multi = len(models) > 1
    obj = ['# Tomodachi Location Toolkit model export. Keep the object names; do not join or rename objects.', 'mtllib %s.mtl' % stem]
    mtl, pngs, png_of, info = [], {}, {}, {'shapes': 0, 'polys': 0, 'flat': 0, 'notes': []}
    vb = tb = nb = 0
    for mi, m in enumerate(models):
        pre = 'm%d_' % mi if multi else ''
        for mat in m['materials']:
            mtl.append('newmtl ' + pre + obj_ident(mat['name']))
            mtl.append('Ka 0 0 0')
            mtl.append('Ks 0 0 0')
            t = by_tex.get(mat['tex'])
            if t is not None and t['name'] not in png_of:
                try:
                    w, h, rgba = tex_render(b, t, pals)
                    fn = '%s_%s.png' % (stem, obj_ident(t['name']))
                    pngs[fn] = png_write(w, h, rgba)
                    png_of[t['name']] = (fn, any(rgba[i] < 255 for i in range(3, len(rgba), 4)))
                except Exception as e:
                    png_of[t['name']] = None
                    info['notes'].append('Texture %s could not be drawn (%s).' % (t['name'], e))
            pic = png_of.get(t['name']) if t is not None else None
            if pic:
                mtl.append('Kd 1 1 1')
                mtl.append('map_Kd ' + pic[0])
                if pic[1]:
                    mtl.append('map_d ' + pic[0])
            else:
                c = mat['dif_amb'] & 0x7FFF
                mtl.append('Kd %.4f %.4f %.4f' % ((c & 31) / 31, (c >> 5 & 31) / 31, (c >> 10 & 31) / 31))
            mtl.append('')
        draws = mdl_draws(m)
        if len(draws) < len(m['shapes']):
            info['notes'].append('%d shape(s) of model %s are never drawn and were left out.' % (len(m['shapes']) - len(draws), m['name']))
        if any(op in (0x07, 0x08) for _, op, _ in m['sbc']):
            info['notes'].append('Model %s has billboard nodes: they are shown as they are stored, without the camera rotation.' % m['name'])
        for d in draws:
            ref = ShapeRef(b, m, d)
            tw, th = shape_uv_size(m, d, by_tex)
            vmap, vl, tmap, tl, nmap, nl, faces = {}, [], {}, [], {}, [], []
            for pi, poly in enumerate(ref.polys):
                if poly_flat(poly):
                    info['flat'] += 1
                    continue
                used, f = set(), []
                for v, (p, n) in zip(poly, ref.wp[pi]):
                    key = (round(p[0], 6) + 0.0, round(p[1], 6) + 0.0, round(p[2], 6) + 0.0)
                    vi = vmap.get(key)
                    if vi is None or vi in used:
                        vi = len(vl)
                        vl.append(p)
                        vmap.setdefault(key, vi)
                    used.add(vi)
                    ti = ni = None
                    if ref.tex:
                        tk_ = (v[3], v[4])
                        ti = tmap.get(tk_)
                        if ti is None:
                            ti = tmap[tk_] = len(tl)
                            tl.append(tk_)
                    if n is not None:
                        nk = (round(n[0], 6) + 0.0, round(n[1], 6) + 0.0, round(n[2], 6) + 0.0)
                        ni = nmap.get(nk)
                        if ni is None:
                            ni = nmap[nk] = len(nl)
                            nl.append(nk)
                    f.append((vi, ti, ni))
                faces.append(f)
            if not faces:
                continue
            mat = m['materials'][d['mat']] if d['mat'] < len(m['materials']) else None
            obj.append('o ' + obj_shape_name(multi, mi, d['shape'], ref.shape['name']))
            obj += ['v %.7f %.7f %.7f' % p for p in vl]
            obj += ['vt %.6f %.6f' % (s / (16 * tw), 1 - t / (16 * th)) for s, t in tl]
            obj += ['vn %.6f %.6f %.6f' % n for n in nl]
            if mat:
                obj.append('usemtl ' + pre + obj_ident(mat['name']))
            for f in faces:
                obj.append('f ' + ' '.join('%d/%s/%s' % (vi + vb + 1, '' if ti is None else ti + tb + 1, '' if ni is None else ni + nb + 1) for vi, ti, ni in f))
            vb, tb, nb = vb + len(vl), tb + len(tl), nb + len(nl)
            info['shapes'] += 1
            info['polys'] += len(faces)
    return '\n'.join(obj) + '\n', '\n'.join(mtl) + '\n', pngs, info
