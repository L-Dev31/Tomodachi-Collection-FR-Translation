"""Fixed point readers and small matrix and vector helpers."""
import math
import struct


def s16(b, o):
    return struct.unpack_from('<h', b, o)[0]


def s32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def m_mul(a, b):
    out = []
    for i in range(3):
        for j in range(3):
            out.append(a[4 * i] * b[j] + a[4 * i + 1] * b[4 + j] + a[4 * i + 2] * b[8 + j])
        out.append(a[4 * i] * b[3] + a[4 * i + 1] * b[7] + a[4 * i + 2] * b[11] + a[4 * i + 3])
    return tuple(out)


def m_pt(m, p):
    x, y, z = p
    return (m[0] * x + m[1] * y + m[2] * z + m[3], m[4] * x + m[5] * y + m[6] * z + m[7], m[8] * x + m[9] * y + m[10] * z + m[11])


def m_vec(m, p):
    x, y, z = p
    return (m[0] * x + m[1] * y + m[2] * z, m[4] * x + m[5] * y + m[6] * z, m[8] * x + m[9] * y + m[10] * z)


def m_inv(m):
    a, b, c, d, e, f, g, h, i = m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return None
    r = ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
         (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
         (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det)
    tx, ty, tz = m[3], m[7], m[11]
    return (r[0], r[1], r[2], -(r[0] * tx + r[1] * ty + r[2] * tz),
            r[3], r[4], r[5], -(r[3] * tx + r[4] * ty + r[5] * tz),
            r[6], r[7], r[8], -(r[6] * tx + r[7] * ty + r[8] * tz))


def m_scale(s):
    return (s, 0.0, 0.0, 0.0, 0.0, s, 0.0, 0.0, 0.0, 0.0, s, 0.0)


def pivot_rot(select, neg, a, b):
    o = -1.0 if neg & 1 else 1.0
    c = -b if neg & 2 else b
    d = -a if neg & 4 else a
    cols = {0: ((o, 0, 0), (0, a, b), (0, c, d)), 1: ((0, o, 0), (a, 0, b), (c, 0, d)), 2: ((0, 0, o), (a, b, 0), (c, d, 0)),
            3: ((0, a, b), (o, 0, 0), (0, c, d)), 4: ((a, 0, b), (0, o, 0), (c, 0, d)), 5: ((a, b, 0), (0, 0, o), (c, d, 0)),
            6: ((0, a, b), (0, c, d), (o, 0, 0)), 7: ((a, 0, b), (c, 0, d), (0, o, 0)), 8: ((a, b, 0), (c, d, 0), (0, 0, o))}[select]
    return tuple(tuple(float(cols[j][i]) for j in range(3)) for i in range(3))


def unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else None


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
