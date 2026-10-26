"""Joint animations (BCA0 files): where every node of a skeleton is, frame by frame."""
import math
import struct

from ...core.binary import u16, u32
from .bmd import dict_entries
from .matrix import cross, pivot_rot, unit

# What the tag of a node says about its translation, rotation and scale (the node index is in the top byte).
ALL_NONE = 0x1
T_NONE, T_BASE = 0x2, 0x4
R_NONE, R_BASE, R_CONST = 0x40, 0x80, 0x100
S_NONE, S_BASE = 0x200, 0x400

# A 16 bit translation or scale is stored with 12 fractional bits like the rest of the format.
FIX = 4096.0


class Track:
    """The samples of one number (or of the rotation indices) over the frames of an animation.

    The samples are stored every `1 << shift` frames up to the frame `last`; after it every frame has its own sample."""
    __slots__ = ('data', 'shift', 'last')

    def __init__(self, data, shift=0, last=0):
        self.data, self.shift, self.last = data, shift, last

    def span(self, frame):
        """(first sample, second sample, weight of the second) that make the value at a frame."""
        n = len(self.data)
        if not self.shift:
            i = min(n - 1, frame)
            return i, i, 0.0
        if frame >= self.last:
            i = min(n - 1, (self.last >> self.shift) + frame - self.last)
            return i, i, 0.0
        i, r = divmod(frame, 1 << self.shift)
        return i, min(n - 1, i + 1), r / (1 << self.shift)

    def value(self, frame):
        i, j, w = self.span(frame)
        a = self.data[i]
        return a if not w else a + (self.data[j] - a) * w


def track_size(info, frames):
    """(shift, 16 bit samples, last interpolated frame, number of samples) of a track from its info word."""
    shift = info >> 30
    last = info >> 16 & 0xFFF
    if not shift:
        return 0, bool(info >> 29 & 1), last, frames
    return shift, bool(info >> 29 & 1), last, (last >> shift) + 1 + max(0, frames - 1 - last)


def _read(b, o, n, size, fmt):
    """n numbers of the given struct format at o (the missing ones at the end of a short file repeat the last one)."""
    n = max(0, min(n, (len(b) - o) // size))
    out = list(struct.unpack_from('<%d%s' % (n, fmt), b, o)) if n else []
    return out or [0]


def rot5_matrix(v):
    """3x3 rotation (rows) from the five numbers of a compressed rotation: two columns, the third one follows."""
    c0 = unit((v[0] / 32768, v[1] / 32768, v[2] / 32768)) or (1.0, 0.0, 0.0)
    d, e = v[3] / 32768, (v[4] & ~7) / 32768
    f = math.sqrt(max(0.0, 1.0 - d * d - e * e))
    if abs(c0[2]) > f:
        f = -(c0[0] * d + c0[1] * e) / c0[2]
    elif v[4] & 1:
        f = -f
    c1 = (d, e, f)
    k = sum(a * b for a, b in zip(c0, c1))
    c1 = unit(tuple(a - k * b for a, b in zip(c1, c0))) or (0.0, 1.0, 0.0)
    c2 = cross(c0, c1)
    return tuple(tuple((c0, c1, c2)[j][i] for j in range(3)) for i in range(3))


def rot_blend(a, b, w):
    """Rotation between two rotations (rows), by a weight of the second one."""
    if a is b or not w:
        return a
    c0 = unit(tuple(a[i][0] + (b[i][0] - a[i][0]) * w for i in range(3))) or (1.0, 0.0, 0.0)
    c1 = tuple(a[i][1] + (b[i][1] - a[i][1]) * w for i in range(3))
    k = sum(x * y for x, y in zip(c0, c1))
    c1 = unit(tuple(x - k * y for x, y in zip(c1, c0))) or (0.0, 1.0, 0.0)
    c2 = cross(c0, c1)
    return tuple(tuple((c0, c1, c2)[j][i] for j in range(3)) for i in range(3))


class JointAnimation:
    """One animation of a BCA0 file: for every node, how its translation, rotation and scale change."""

    def __init__(self, b, name, o):
        self.name, self.b, self.o = name, b, o
        self.frames, count = u16(b, o + 4), u16(b, o + 6)
        self.rot3 = o + struct.unpack_from('<i', b, o + 12)[0]
        self.rot5 = o + struct.unpack_from('<i', b, o + 16)[0]
        self.rot_cache = {}
        self.nodes = [self._node(o + u16(b, o + 20 + 2 * i)) for i in range(count)]

    def _channel(self, p, const, scale=False):
        """Reads the description of a number at p: ('const', value) or a track. Returns (channel, new p)."""
        b = self.b
        if const:
            v = struct.unpack_from('<i', b, p)[0] / FIX
            return Track([v]), p + (8 if scale else 4)
        info, off = u32(b, p), u32(b, p + 4)
        shift, short, last, n = track_size(info, self.frames)
        o = self.o + off
        mult = 2 if scale else 1
        data = _read(b, o, n * mult, 2 if short else 4, 'h' if short else 'i')
        data = [x / FIX for x in data[::mult]]
        return Track(data, shift, last), p + 8

    def _node(self, p):
        b = self.b
        tag = u32(b, p)
        p += 4
        node = {'index': tag >> 24, 'tag': tag & 0xFFFFFF, 't': None, 'r': None, 's': None}
        if tag & ALL_NONE:
            return node
        if not tag & (T_NONE | T_BASE):
            node['t'] = []
            for k in range(3):
                ch, p = self._channel(p, tag >> (3 + k) & 1)
                node['t'].append(ch)
        elif tag & T_BASE:
            node['t'] = 'base'
        if not tag & (R_NONE | R_BASE):
            if tag & R_CONST:
                node['r'] = Track([u32(b, p) & 0xFFFF])
                p += 4
            else:
                info, off = u32(b, p), u32(b, p + 4)
                p += 8
                shift, _, last, n = track_size(info, self.frames)
                node['r'] = Track(_read(b, self.o + off, n, 2, 'H'), shift, last)
        elif tag & R_BASE:
            node['r'] = 'base'
        if not tag & (S_NONE | S_BASE):
            node['s'] = []
            for k in range(3):
                ch, p = self._channel(p, tag >> (11 + k) & 1, True)
                node['s'].append(ch)
        elif tag & S_BASE:
            node['s'] = 'base'
        return node

    def rotation(self, index):
        """3x3 rotation (rows) of an entry of the rotation tables."""
        m = self.rot_cache.get(index)
        if m is None:
            b = self.b
            if index & 0x8000:
                info, a, c = struct.unpack_from('<Hhh', b, self.rot3 + 6 * (index & 0x7FFF))
                m = pivot_rot(info & 15, info >> 4 & 15, a / FIX, c / FIX)
            else:
                m = rot5_matrix(struct.unpack_from('<5h', b, self.rot5 + 10 * index))
            self.rot_cache[index] = m
        return m

    def node_matrix(self, node, base, frame):
        """12 numbers (3 rows of rotation times scale, then translation) of a node at a frame; base is the node of the model."""
        t, r, s = node['t'], node['r'], node['s']
        if t == 'base':
            t = base['t']
        elif t is None:
            t = (0.0, 0.0, 0.0)
        else:
            t = tuple(ch.value(frame) for ch in t)
        if r == 'base':
            r = base['rot']
        elif r is None:
            r = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        else:
            i, j, w = r.span(frame)
            r = rot_blend(self.rotation(r.data[i]), self.rotation(r.data[j]), w)
        if s == 'base':
            s = base['s']
        elif s is None:
            s = (1.0, 1.0, 1.0)
        else:
            s = tuple(ch.value(frame) for ch in s)
        out = []
        for i in range(3):
            out += [r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]]
        return tuple(out)

    def pose(self, nodes, frame):
        """The matrices of the nodes of a model (its 'nodes' list) at a frame; the nodes this animation does not move stay as they are."""
        out = [n['matrix'] for n in nodes]
        for node in self.nodes:
            k = node['index']
            if k < len(nodes):
                out[k] = self.node_matrix(node, nodes[k], frame)
        return out


def bca_animations(b):
    """The animations of a BCA0 file."""
    if b[:4] != b'BCA0':
        raise ValueError('not a joint animation file')
    o = u32(b, 16)
    if b[o:o + 4] != b'JNT0':
        raise ValueError('no joint animation block')
    ents, names = dict_entries(b, o + 8, 0)
    return [JointAnimation(b, nm, o + u32(e, 0)) for e, nm in zip(ents, names)]
