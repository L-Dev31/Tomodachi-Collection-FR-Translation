"""Animations that are not skeletons: BTA0 (a texture slides or stretches), BTP0 (a material changes its picture)
and BVA0 (parts of the model show up and disappear). The files hold one or several named animations like BCA0 files do."""
import struct

from ...core.binary import u16, u32
from .anim import FIX, Track, read_numbers
from .bmd import dict_entries, dict_offsets
from .cells import Cell


def animation_list(b, magic, block):
    """[(name, offset of the animation)] of an animation file whose first block is `block`."""
    if b[:4] != magic:
        raise ValueError('not a %s file' % magic.decode('latin1'))
    o = u32(b, 16)
    if b[o:o + 4] != block:
        raise ValueError('no %s block' % block.decode('latin1'))
    ents, names = dict_entries(b, o + 8, 0)
    return [(nm, o + u32(e, 0)) for e, nm in zip(ents, names)]


# ----- BTA0: the matrix of the texture (scale, rotation, translation) of materials

def srt_samples(info, frames):
    """(sample every 1 << shift frames, constant, 16 bit samples, last interpolated frame, number of samples) from the info word
    of a channel. Past the last interpolated frame, every frame has its own sample."""
    shift, const, short, last = info >> 30, info >> 29 & 1, info >> 28 & 1, info & 0xFFFF
    n = frames if not shift else (last >> shift) + 1 + max(0, frames - 1 - last)
    return shift, bool(const), bool(short), last, n


def srt_channel(b, a, info, value, frames, where):
    """The Track of one number of a texture matrix; `a` is where the animation starts, the offsets count from there; `where` is where
    the word `value` is in the file."""
    shift, const, short, last, n = srt_samples(info, frames)
    size, fmt = (2, 'h') if short else (4, 'i')
    if const:                                   # the number itself is where the offset would be
        if short:
            v = value & 0xFFFF
            v -= 0x10000 if v & 0x8000 else 0
        else:
            v = value - (1 << 32) if value & 0x80000000 else value
        return Track([v / FIX], cells=[Cell(where, fmt, FIX)])
    data = read_numbers(b, a + value, n, size, fmt)
    return Track([x / FIX for x in data], shift, last,
                 [Cell(a + value + k * size, fmt, FIX) if a + value + (k + 1) * size <= len(b) else None for k in range(len(data))])


class SrtTrack:
    """How the texture matrix of one material changes: scale (s, t) and translation (s, t) in textures. The rotation, that every
    animation of the game keeps still, is not read."""
    __slots__ = ('scale', 'trans')

    def __init__(self, b, a, entry, frames, where):
        ch = [srt_channel(b, a, *struct.unpack_from('<II', entry, 8 * k), frames, where + 8 * k + 4) for k in (0, 1, 3, 4)]
        self.scale, self.trans = ch[0:2], ch[2:4]

    def at(self, frame):
        """((scale s, scale t), (translation s, translation t)) at a frame."""
        return (tuple(c.value(frame) for c in self.scale), tuple(c.value(frame) for c in self.trans))


class SrtAnimation:
    """One animation of a BTA0 file: `tracks` {material name: SrtTrack}."""
    kind = 'srt'

    def __init__(self, b, name, a):
        self.name, self.frames = name, u16(b, a + 4)
        ents, names = dict_entries(b, a + 8, 0)
        self.tracks = {nm: SrtTrack(b, a, e, self.frames, where) for e, nm, where in zip(ents, names, dict_offsets(b, a + 8))}


def srt_animations(b):
    """The animations of a BTA0 file."""
    return [SrtAnimation(b, nm, a) for nm, a in animation_list(b, b'BTA0', b'SRT0')]


# ----- BTP0: the picture (texture and palette) of materials

class PatAnimation:
    """One animation of a BTP0 file: `textures` and `palettes` are the names it picks from, `tracks` {material name: [(frame,
    texture index, palette index)]} the pictures a material shows from a frame on."""
    kind = 'pat'

    def __init__(self, b, name, a):
        self.name, self.frames = name, u16(b, a + 4)
        n_tex, n_pal, o_tex, o_pal = b[a + 6], b[a + 7], u16(b, a + 8), u16(b, a + 10)

        def names(o, n):
            return [bytes(b[a + o + 16 * i:a + o + 16 * i + 16]).split(b'\0')[0].decode('latin1') for i in range(n)]
        self.textures, self.palettes = names(o_tex, n_tex), names(o_pal, n_pal)
        ents, mats = dict_entries(b, a + 12, 0)
        self.tracks, self.cells = {}, {}
        for e, nm in zip(ents, mats):
            count, off = u16(e, 0), u16(e, 6)
            keys = [(i, struct.unpack_from('<HBB', b, a + off + 4 * i)) for i in range(count) if a + off + 4 * i + 4 <= len(b)]
            keys = [(i, k) for i, k in keys if k[1] < n_tex and k[2] < n_pal]
            self.tracks[nm] = [k for i, k in keys]
            self.cells[nm] = [(Cell(a + off + 4 * i, 'H'), Cell(a + off + 4 * i + 2, 'B'), Cell(a + off + 4 * i + 3, 'B')) for i, k in keys]

    def at(self, material, frame):
        """(texture name, palette name) a material shows at a frame, or None when the animation does not know the material."""
        keys = self.tracks.get(material)
        if not keys:
            return None
        key = keys[0]
        for k in keys:
            if k[0] > frame:
                break
            key = k
        return self.textures[key[1]], self.palettes[key[2]]


def pat_animations(b):
    """The animations of a BTP0 file."""
    return [PatAnimation(b, nm, a) for nm, a in animation_list(b, b'BTP0', b'PAT0')]


# ----- BVA0: which nodes of the model are shown

class VisAnimation:
    """One animation of a BVA0 file: for every frame, one bit per node of the model (set: the node is shown)."""
    kind = 'vis'

    def __init__(self, b, name, a):
        self.name, self.frames, self.count, self.a = name, u16(b, a + 4), u16(b, a + 6), a
        size = (self.frames * self.count + 7) // 8
        self.bits = bytes(b[a + 12:a + 12 + size])
        self.bits += bytes(size - len(self.bits))

    def at(self, frame):
        """[shown or not] for every node at a frame."""
        base = min(frame, max(0, self.frames - 1)) * self.count
        return [bool(self.bits[(base + n) >> 3] >> ((base + n) & 7) & 1) for n in range(self.count)]


def vis_animations(b):
    """The animations of a BVA0 file."""
    return [VisAnimation(b, nm, a) for nm, a in animation_list(b, b'BVA0', b'VIS0')]
