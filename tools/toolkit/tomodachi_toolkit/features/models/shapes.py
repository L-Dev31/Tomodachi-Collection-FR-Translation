"""Shapes of a model as world space meshes (used by the OBJ export and import)."""
import math

from .geometry import gx_draw, mdl_walk
from .matrix import m_inv, m_pt, m_vec, unit


def slot_matrix(draw, slot):
    return draw['matrix'] if slot == -1 else draw['stack'][slot]


def draw_alias(draw):
    """Index of the matrix stack slot that holds the matrix of the draw call, or None."""
    for k, mx in enumerate(draw['stack']):
        if all(abs(x - y) < 1e-9 for x, y in zip(mx, draw['matrix'])):
            return k
    return None


def canon_polys(polys, alias):
    """Corner tuples (x, y, z, s, t, nx, ny, nz, slot); slot None (the matrix of the draw call) becomes the alias slot or -1."""
    none = -1 if alias is None else alias
    return [tuple(v[:8] + (none if v[8] is None else v[8],) for v in poly) for poly in polys]


def poly_key(poly):
    return min(tuple(poly[i:]) + tuple(poly[:i]) for i in range(len(poly)))


def poly_flat(poly):
    """True when two corners are the same vertex (zero area whatever the animation)."""
    return len({v[:3] + v[8:] for v in poly}) < len(poly)


class ShapeRef:
    """The original geometry of one drawn shape in model space, used to export it and to match an imported mesh."""

    def __init__(self, b, model, draw):
        self.model, self.draw = model, draw
        self.shape = model['shapes'][draw['shape']]
        self.alias = draw_alias(draw)
        self.tex = bool(self.shape['flags'] & 4)
        self.polys = canon_polys(gx_draw(b, self.shape, draw), self.alias)
        self.mats = {}
        self.corners, self.cent, self.grid, self.wp = [], [], {}, []
        slots = {v[8] for poly in self.polys for v in poly} or {-1}
        for s in slots:
            self.mat(s)
        self.multi = len(slots) > 1
        scale = max(1e-9, max(max(abs(x) for x in mx[:3] + mx[4:7] + mx[8:11]) for mx, _ in self.mats.values()))
        self.tol = 3.0 * scale / 4096
        for pi, poly in enumerate(self.polys):
            wp = [self.world(v) for v in poly]
            self.wp.append(wp)
            self.cent.append(tuple(sum(p[0][a] for p in wp) / len(wp) for a in range(3)))
            for v, (p, n) in zip(poly, wp):
                self.corners.append((v, p, n, pi))
        pts = [c[1] for c in self.corners]
        if pts:
            ext = max(max(p[a] for p in pts) - min(p[a] for p in pts) for a in range(3))
            self.cell = max(ext / 24, self.tol, 1e-6)
        else:
            self.cell = 1.0
        for i, c in enumerate(self.corners):
            self.grid.setdefault(self.cellof(c[1]), []).append(i)

    def mat(self, slot):
        """(matrix, inverse) of a matrix stack slot (-1: the matrix of the draw call)."""
        if slot not in self.mats:
            mx = slot_matrix(self.draw, slot)
            self.mats[slot] = (mx, m_inv(mx))
        return self.mats[slot]

    def cellof(self, p):
        return (math.floor(p[0] / self.cell), math.floor(p[1] / self.cell), math.floor(p[2] / self.cell))

    def world(self, v):
        mx = self.mat(v[8])[0]
        n = m_vec(mx, (v[5] / 512, v[6] / 512, v[7] / 512))
        return m_pt(mx, (v[0] / 4096, v[1] / 4096, v[2] / 4096)), unit(n)

    def near(self, p, radius):
        """Indices of the original corners within radius of the model space point p."""
        r = int(radius / self.cell) + 1
        cx, cy, cz = self.cellof(p)
        out = []
        for ix in range(cx - r, cx + r + 1):
            for iy in range(cy - r, cy + r + 1):
                for iz in range(cz - r, cz + r + 1):
                    for i in self.grid.get((ix, iy, iz), ()):
                        q = self.corners[i][1]
                        if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2 <= radius * radius:
                            out.append(i)
        return out

    def nearest(self, p):
        """Indices of the original corners closest to the model space point p (several when they tie)."""
        if not self.corners:
            return []
        cx, cy, cz = self.cellof(p)
        best, bd, r = [], 1e300, 0
        while r <= 6:
            for ix in range(cx - r, cx + r + 1):
                for iy in range(cy - r, cy + r + 1):
                    for iz in range(cz - r, cz + r + 1):
                        if max(abs(ix - cx), abs(iy - cy), abs(iz - cz)) != r:
                            continue
                        for i in self.grid.get((ix, iy, iz), ()):
                            q = self.corners[i][1]
                            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
                            if d < bd - 1e-15:
                                best, bd = [i], d
                            elif d <= bd + 1e-15:
                                best.append(i)
            if best and (r * self.cell) ** 2 >= bd:
                return best
            r += 1
        best, bd = [], 1e300
        for i, c in enumerate(self.corners):
            q = c[1]
            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
            if d < bd - 1e-15:
                best, bd = [i], d
            elif d <= bd + 1e-15:
                best.append(i)
        return best


def mdl_draws(model):
    """One draw call per shape (the first one); every model of the game draws each shape once."""
    seen, out = set(), []
    for d in mdl_walk(model):
        if d['shape'] not in seen:
            seen.add(d['shape'])
            out.append(d)
    return out
