"""Software render of a model: textured, lit, back faces culled. Pure Python, made for the small models of the game."""
import math

from .bmd import bmd_textures
from .geometry import gx_draw, mdl_models, mdl_walk
from .matrix import cross, m_mul, m_pt, unit
from .textures import tex_render

LEVELS = 16                                   # brightness steps of the lighting
AMBIENT = 0.42                                # brightness of a face that looks away from the light
LIGHT = unit((-0.35, 0.5, 0.8))               # direction to the light in view space (+z points to the viewer)
NEAR = 0.02                                   # near plane, in model radii
FOV = math.radians(38)
WRAP = 1 << 20                                # keeps repeating texture coordinates positive (a multiple of every texture size)
CHUNK = 8                                     # pixels between two exact perspective corrections
SHOW_BACK, SHOW_FRONT = 1, 2                  # polygon attribute bits 6 and 7: which sides of a polygon are drawn


def packed(c):
    return (c & 31) * 255 // 31 << 16 | (c >> 5 & 31) * 255 // 31 << 8 | (c >> 10 & 31) * 255 // 31


def shade_color(c, level):
    m = int((AMBIENT + (1 - AMBIENT) * level / (LEVELS - 1)) * 256)
    return ((c >> 16) * m >> 8) << 16 | ((c >> 8 & 255) * m >> 8) << 8 | (c & 255) * m >> 8


class Tile:
    """The pixels of a texture for the rasteriser: packed 0xRRGGBB, -1 where see through. Mirrored repeats are drawn out in advance."""

    def __init__(self, w, h, rgba, tparam):
        rep_s, rep_t, flip_s, flip_t = tparam >> 16 & 1, tparam >> 17 & 1, tparam >> 18 & 1, tparam >> 19 & 1
        r, g, b, a = rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4]
        px = [(r_ << 16 | g_ << 8 | b_) if a_ >= 128 else -1 for r_, g_, b_, a_ in zip(r, g, b, a)]
        rows = [px[y * w:(y + 1) * w] for y in range(h)]
        if flip_s and rep_s:
            rows = [row + row[::-1] for row in rows]
        if flip_t and rep_t:
            rows = rows + rows[::-1]
        self.px = [c for row in rows for c in row]
        self.w, self.h = w, h
        self.tw, self.th = len(rows[0]), len(rows)
        self.repeat = (bool(rep_s), bool(rep_t))
        self.cutout = -1 in self.px
        self.levels = {}

    def shaded(self, level):
        px = self.levels.get(level)
        if px is None:
            m = int((AMBIENT + (1 - AMBIENT) * level / (LEVELS - 1)) * 256)
            if m >= 256:
                px = self.px
            else:
                px = [c if c < 0 else ((c >> 16) * m >> 8) << 16 | ((c >> 8 & 255) * m >> 8) << 8 | (c & 255) * m >> 8 for c in self.px]
            self.levels[level] = px
        return px


class Part:
    """One drawn shape: its triangles with the vertices shared, ready to be moved by a pose of the model."""

    def __init__(self, b, model, draw):
        self.shape = draw['shape']
        self.mat = draw['mat']
        self.vx, self.vy, self.vz, self.vslot = [], [], [], []
        index, self.tris = {}, []
        for poly in gx_draw(b, model['shapes'][draw['shape']], draw):
            ids = []
            for v in poly:
                slot = -1 if v[8] is None else v[8]
                key = (v[0], v[1], v[2], slot)
                i = index.get(key)
                if i is None:
                    i = index[key] = len(self.vx)
                    self.vx.append(v[0] / 4096)
                    self.vy.append(v[1] / 4096)
                    self.vz.append(v[2] / 4096)
                    self.vslot.append(slot)
                ids.append(i)
            corners = [(ids[k], v[3] / 16, v[4] / 16, v[5], v[6], v[7], -1 if v[8] is None else v[8]) for k, v in enumerate(poly)]
            for k in range(1, len(poly) - 1):
                a, b_, c = corners[0], corners[k], corners[k + 1]
                if len({a[0], b_[0], c[0]}) < 3:
                    continue
                n = (a[3] + b_[3] + c[3], a[4] + b_[4] + c[4], a[5] + b_[5] + c[5])
                self.tris.append((a[0], b_[0], c[0], a[1], a[2], b_[1], b_[2], c[1], c[2], n, a[6]))
        groups = {}
        for i, s in enumerate(self.vslot):
            groups.setdefault(s, []).append(i)
        self.groups = list(groups.items())


class Camera:
    """An orbit camera around a point of the model."""

    def __init__(self, center=(0.0, 0.0, 0.0), radius=1.0):
        self.center, self.radius = center, radius
        self.reset()

    def reset(self):
        self.yaw, self.pitch = math.radians(28), math.radians(14)
        self.dist = self.radius / math.sin(FOV / 2) * 1.05
        self.target = self.center

    def orbit(self, dyaw, dpitch):
        self.yaw += dyaw
        self.pitch = max(-1.5, min(1.5, self.pitch + dpitch))

    def zoom(self, factor):
        self.dist = max(self.radius * 0.15, min(self.radius * 40, self.dist * factor))

    def pan(self, dx, dy):
        """Moves the target by fractions of the view height."""
        right, up, _ = self.axes()
        k = self.dist * math.tan(FOV / 2) * 2
        self.target = tuple(self.target[i] - right[i] * dx * k + up[i] * dy * k for i in range(3))

    def axes(self):
        cp = math.cos(self.pitch)
        back = (cp * math.sin(self.yaw), math.sin(self.pitch), cp * math.cos(self.yaw))
        right = unit(cross((0.0, 1.0, 0.0), back))
        return right, cross(back, right), back

    def matrix(self):
        """World to view (3 rows of 4): the camera looks down -z."""
        right, up, back = self.axes()
        pos = tuple(self.target[i] + back[i] * self.dist for i in range(3))
        return (right[0], right[1], right[2], -sum(right[i] * pos[i] for i in range(3)),
                up[0], up[1], up[2], -sum(up[i] * pos[i] for i in range(3)),
                back[0], back[1], back[2], -sum(back[i] * pos[i] for i in range(3)))


class Scene:
    """The models of a BMD0 file ready to draw. `which` is the index of the only model to show, or None for all of them."""

    def __init__(self, b, which=None):
        self.models = mdl_models(b)
        if not self.models:
            raise ValueError('no model in this file')
        self.shown = [which] if which is not None else list(range(len(self.models)))
        try:
            texs, pals = bmd_textures(b)
        except Exception:
            texs, pals = [], []
        self.texs = {t['name']: t for t in texs}
        self.pals = pals
        self.b = b
        self.tiles = {}
        self.parts = {}
        for mi in self.shown:
            model = self.models[mi]
            self.parts[mi] = [Part(b, model, d) for d in mdl_walk(model)]
        self.bounds()

    def tile(self, model, mat):
        """The Tile of a material of a model, or None when it has no texture."""
        key = (id(model), mat['name'])
        if key not in self.tiles:
            tile = None
            t = self.texs.get(mat['tex'])
            if t is not None:
                try:
                    if mat['pal'] is not None:
                        pi = next((i for i, p in enumerate(self.pals) if p['name'] == mat['pal']), None)
                        if pi is not None:
                            t = dict(t, pal=pi)
                    w, h, rgba = tex_render(self.b, t, self.pals)
                    tile = Tile(w, h, rgba, mat['tparam'])
                except Exception:
                    tile = None
            self.tiles[key] = tile
        return self.tiles[key]

    def bounds(self):
        lo, hi = [1e30] * 3, [-1e30] * 3
        for mi in self.shown:
            model = self.models[mi]
            for part, draw in zip(self.parts[mi], mdl_walk(model)):
                mats = {-1: draw['matrix']}
                for slot, ids in part.groups:
                    mx = mats.get(slot) or draw['stack'][slot]
                    for i in ids:
                        p = m_pt(mx, (part.vx[i], part.vy[i], part.vz[i]))
                        for a in range(3):
                            lo[a], hi[a] = min(lo[a], p[a]), max(hi[a], p[a])
        if lo[0] > hi[0]:
            lo, hi = [-1.0] * 3, [1.0] * 3
        self.center = tuple((lo[a] + hi[a]) / 2 for a in range(3))
        self.radius = max(1e-6, math.sqrt(sum((hi[a] - lo[a]) ** 2 for a in range(3))) / 2)
        self.lo, self.hi = tuple(lo), tuple(hi)

    def camera(self):
        return Camera(self.center, self.radius)


def clip_near(pts, near):
    """Keeps the part of a polygon in front of the near plane. Points are (x, y, z, s, t) in view space."""
    out = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        da, db = -a[2] - near, -b[2] - near
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append(tuple(p + (q - p) * t for p, q in zip(a, b)))
    return out


def fill(fb, zb, width, height, p0, p1, p2, tile, px, flat):
    """Draws a triangle of screen points (x, y, 1/w, s/w, t/w). px are the pixels of the tile, flat the colour without a tile."""
    x0, y0, i0, u0, v0 = p0
    x1, y1, i1, u1, v1 = p1
    x2, y2, i2, u2, v2 = p2
    if y1 < y0:
        x0, y0, i0, u0, v0, x1, y1, i1, u1, v1 = x1, y1, i1, u1, v1, x0, y0, i0, u0, v0
    if y2 < y0:
        x0, y0, i0, u0, v0, x2, y2, i2, u2, v2 = x2, y2, i2, u2, v2, x0, y0, i0, u0, v0
    if y2 < y1:
        x1, y1, i1, u1, v1, x2, y2, i2, u2, v2 = x2, y2, i2, u2, v2, x1, y1, i1, u1, v1
    ys = max(0, math.ceil(y0 - 0.5))
    ye = min(height - 1, math.ceil(y2 - 0.5) - 1)
    if ys > ye or y2 - y0 < 1e-9:
        return
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return
    inv = 1.0 / area
    gi_x = ((i1 - i0) * (y2 - y0) - (i2 - i0) * (y1 - y0)) * inv
    gi_y = ((i2 - i0) * (x1 - x0) - (i1 - i0) * (x2 - x0)) * inv
    long_dx = (x2 - x0) / (y2 - y0)
    top_dx = (x1 - x0) / (y1 - y0) if y1 - y0 > 1e-9 else 0.0
    low_dx = (x2 - x1) / (y2 - y1) if y2 - y1 > 1e-9 else 0.0
    if tile is not None:
        gu_x = ((u1 - u0) * (y2 - y0) - (u2 - u0) * (y1 - y0)) * inv
        gu_y = ((u2 - u0) * (x1 - x0) - (u1 - u0) * (x2 - x0)) * inv
        gv_x = ((v1 - v0) * (y2 - y0) - (v2 - v0) * (y1 - y0)) * inv
        gv_y = ((v2 - v0) * (x1 - x0) - (v1 - v0) * (x2 - x0)) * inv
        tw, th, w, h = tile.tw, tile.th, tile.w, tile.h
        um, vm = tw - 1, th - 1
        rep_s, rep_t = tile.repeat
        fast = rep_s and rep_t
        cutout = tile.cutout
        off_u = WRAP if rep_s else 0
        off_v = WRAP if rep_t else 0
        w1, h1 = w - 1, h - 1
    ceil = math.ceil
    for y in range(ys, ye + 1):
        yc = y + 0.5
        xa = x0 + (yc - y0) * long_dx
        xb = x0 + (yc - y0) * top_dx if yc < y1 else x1 + (yc - y1) * low_dx
        if xa > xb:
            xa, xb = xb, xa
        xl = max(0, ceil(xa - 0.5))
        xr = min(width, ceil(xb - 0.5))
        if xl >= xr:
            continue
        dx = xl + 0.5 - x0
        dy = yc - y0
        iz = i0 + dx * gi_x + dy * gi_y
        row = y * width
        if tile is None:
            idx = row + xl
            for _ in range(xr - xl):
                if iz > zb[idx]:
                    zb[idx] = iz
                    fb[idx] = flat
                iz += gi_x
                idx += 1
            continue
        uw = u0 + dx * gu_x + dy * gu_y
        vw = v0 + dx * gv_x + dy * gv_y
        x = xl
        while x < xr:
            n = min(CHUNK, xr - x)
            if iz < 1e-12:
                break
            u = uw / iz + off_u
            v = vw / iz + off_v
            if n > 1:
                k = n - 1
                iz_e = iz + gi_x * k
                if iz_e < 1e-12:
                    iz_e = iz
                du = ((uw + gu_x * k) / iz_e + off_u - u) / k
                dv = ((vw + gv_x * k) / iz_e + off_v - v) / k
            else:
                du = dv = 0.0
            idx = row + x
            z = iz
            if fast and not cutout:
                for _ in range(n):
                    if z > zb[idx]:
                        zb[idx] = z
                        fb[idx] = px[(int(v) & vm) * tw + (int(u) & um)]
                    u += du
                    v += dv
                    z += gi_x
                    idx += 1
            elif fast:
                for _ in range(n):
                    if z > zb[idx]:
                        c = px[(int(v) & vm) * tw + (int(u) & um)]
                        if c >= 0:
                            zb[idx] = z
                            fb[idx] = c
                    u += du
                    v += dv
                    z += gi_x
                    idx += 1
            else:
                for _ in range(n):
                    if z > zb[idx]:
                        ui, vi = int(u), int(v)
                        ui = ui & um if rep_s else (0 if ui < 0 else w1 if ui > w1 else ui)
                        vi = vi & vm if rep_t else (0 if vi < 0 else h1 if vi > h1 else vi)
                        c = px[vi * tw + ui]
                        if c >= 0:
                            zb[idx] = z
                            fb[idx] = c
                    u += du
                    v += dv
                    z += gi_x
                    idx += 1
            x += n
            iz += gi_x * n
            uw += gu_x * n
            vw += gv_x * n


def material_texture_matrix(mat, tile, override):
    """(scale s, scale t, translation s, translation t in texels) that turn the texture coordinates of a material into texels."""
    if override is not None:
        scale, trans = override
    elif mat is not None and mat['tparam'] >> 30 & 3 == 1:
        scale, trans = mat['srt'][0], mat['srt'][2]
    else:
        scale, trans = (1.0, 1.0), (0.0, 0.0)
    w, h = (tile.w, tile.h) if tile is not None else (1, 1)
    return scale[0], scale[1], trans[0] * w, trans[1] * h


def render(scene, cam, width, height, poses=None, srts=None, background=0xE8E4DC):
    """Draws the scene and returns the picture as a list of width * height packed 0xRRGGBB pixels.
    poses {model index: node matrices} moves the skeleton of a model, srts {(model index, material index): (scale, translation)} the texture of a material."""
    fb = [background] * (width * height)
    zb = [0.0] * (width * height)
    view = cam.matrix()
    near = NEAR * scene.radius
    f = height / 2 / math.tan(FOV / 2)
    cx, cy = width / 2, height / 2
    poses = poses or {}
    srts = srts or {}
    for mi in scene.shown:
        model = scene.models[mi]
        for part, draw in zip(scene.parts[mi], mdl_walk(model, poses.get(mi))):
            mat = model['materials'][part.mat] if part.mat < len(model['materials']) else None
            sides = mat['attr'] >> 6 & 3 if mat else SHOW_FRONT
            if sides == 0 or not part.tris:
                continue
            tile = scene.tile(model, mat) if mat else None
            lit = bool(mat['attr'] & 15) if mat else True
            color = packed(mat['dif_amb'] & 0x7FFF) if mat else 0xB0B0B0
            if tile is None and mat and mat['tex'] is not None:
                color = 0xC8C8C8
            sx, sy, tx, ty = material_texture_matrix(mat, tile, srts.get((mi, part.mat)))
            n = len(part.vx)
            X, Y, Z = [0.0] * n, [0.0] * n, [0.0] * n
            mats = {}
            vx, vy, vz = part.vx, part.vy, part.vz
            for slot, ids in part.groups:
                mx = mats[slot] = m_mul(view, draw['matrix'] if slot == -1 else draw['stack'][slot])
                m0, m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11 = mx
                for q in ids:
                    x, y, z = vx[q], vy[q], vz[q]
                    X[q] = m0 * x + m1 * y + m2 * z + m3
                    Y[q] = m4 * x + m5 * y + m6 * z + m7
                    Z[q] = m8 * x + m9 * y + m10 * z + m11
            for ia, ib, ic, s0, t0, s1, t1, s2, t2, nrm, nslot in part.tris:
                z0, z1, z2 = Z[ia], Z[ib], Z[ic]
                pts = [(X[ia], Y[ia], z0, s0 * sx + tx, t0 * sy + ty), (X[ib], Y[ib], z1, s1 * sx + tx, t1 * sy + ty),
                       (X[ic], Y[ic], z2, s2 * sx + tx, t2 * sy + ty)]
                if z0 > -near or z1 > -near or z2 > -near:
                    pts = clip_near(pts, near)
                    if len(pts) < 3:
                        continue
                scr = []
                for px_, py_, pz_, ps_, pt_ in pts:
                    iw = -1.0 / pz_
                    scr.append((cx + px_ * f * iw, cy - py_ * f * iw, iw, ps_ * iw, pt_ * iw))
                a0, a1, a2 = scr[0], scr[1], scr[2]
                area = (a1[0] - a0[0]) * (a2[1] - a0[1]) - (a2[0] - a0[0]) * (a1[1] - a0[1])
                if abs(area) < 1e-6:
                    continue
                front = area < 0
                if not sides & (SHOW_FRONT if front else SHOW_BACK):
                    continue
                if lit:
                    mx = mats[nslot]
                    nx = mx[0] * nrm[0] + mx[1] * nrm[1] + mx[2] * nrm[2]
                    ny = mx[4] * nrm[0] + mx[5] * nrm[1] + mx[6] * nrm[2]
                    nz = mx[8] * nrm[0] + mx[9] * nrm[1] + mx[10] * nrm[2]
                    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
                    d = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / ln if ln > 1e-9 else 1.0
                    level = int(max(0.0, d if front else -d) * (LEVELS - 1) + 0.5)
                else:
                    level = LEVELS - 1
                if tile is not None:
                    pix, flat = tile.shaded(level), 0
                else:
                    pix, flat = None, shade_color(color, level)
                for k in range(1, len(scr) - 1):
                    fill(fb, zb, width, height, scr[0], scr[k], scr[k + 1], tile, pix, flat)
    return fb


def to_ppm(width, height, fb):
    """The picture as a binary PPM file (what a Tk PhotoImage reads)."""
    out = bytearray(len(fb) * 3)
    out[0::3] = bytes([c >> 16 for c in fb])
    out[1::3] = bytes([c >> 8 & 255 for c in fb])
    out[2::3] = bytes([c & 255 for c in fb])
    return b'P6 %d %d 255\n' % (width, height) + bytes(out)
