"""Nitro fonts (NFTR): the characters a font can draw and the picture of each glyph."""
import struct

from .binary import u16, u32


class FontError(ValueError):
    pass


class Font:
    """A parsed NFTR font.

    height, width: size of a glyph cell in pixels. depth: bits per pixel (1 or 2).
    encoding: 0 UTF-8, 1 UTF-16, 2 Shift-JIS, 3 CP1252.
    codes: {character code: glyph number}. widths: {glyph number: (left, glyph width, advance)}.
    """

    def __init__(self, data):
        d = bytes(data)
        if d[:4] not in (b'RTFN', b'NFTR'):
            raise FontError('not a font file')
        try:
            self._parse(d)
        except (IndexError, struct.error) as e:
            raise FontError('damaged font file') from e

    def _parse(self, d):
        count = u16(d, 14)
        p = u16(d, 12)
        blocks = {}
        for _ in range(count):
            blocks.setdefault(bytes(d[p:p + 4]), []).append(p)
            p += u32(d, p + 4)
        info = blocks[b'FNIF'][0]
        self.line_height = d[info + 9]
        self.default_glyph = u16(d, info + 10)
        self.default_widths = (struct.unpack_from('<b', d, info + 12)[0], d[info + 13], d[info + 14])
        self.encoding = d[info + 15]
        glp = blocks[b'PLGC'][0]
        self.width, self.height = d[glp + 8], d[glp + 9]
        self.cell_size = u16(d, glp + 10)
        self.baseline = struct.unpack_from('<b', d, glp + 12)[0]
        self.depth = d[glp + 14]
        if self.depth not in (1, 2, 4, 8) or self.cell_size == 0:
            raise FontError('unsupported glyph format')
        self.glyph_data = glp + 16
        self.glyph_count = (u32(d, glp + 4) - 16) // self.cell_size
        self.widths = {}
        for p in blocks.get(b'HDWC', []):
            first, last = u16(d, p + 8), u16(d, p + 10)
            for g in range(first, last + 1):
                o = p + 16 + (g - first) * 3
                self.widths[g] = (struct.unpack_from('<b', d, o)[0], d[o + 1], d[o + 2])
        self.codes = {}
        for p in blocks.get(b'PAMC', []):
            first, last, kind = u16(d, p + 8), u16(d, p + 10), u16(d, p + 12)
            if kind == 0:
                start = u16(d, p + 20)
                for c in range(first, last + 1):
                    self.codes[c] = start + c - first
            elif kind == 1:
                for c in range(first, last + 1):
                    g = u16(d, p + 20 + (c - first) * 2)
                    if g != 0xFFFF:
                        self.codes[c] = g
            elif kind == 2:
                for i in range(u16(d, p + 20)):
                    self.codes[u16(d, p + 22 + i * 4)] = u16(d, p + 24 + i * 4)
        self.data = d

    def has(self, ch):
        """True when the font draws the character (a string of one character)."""
        return ord(ch) in self.codes

    def glyph(self, code):
        """The pixels of a character: a list of rows, each a list of intensities 0..(2**depth - 1), or None when the
        font has no glyph for it."""
        g = self.codes.get(code if isinstance(code, int) else ord(code))
        if g is None or g >= self.glyph_count:
            return None
        o = self.glyph_data + g * self.cell_size
        bits = self.depth
        per = 8 // bits
        mask = (1 << bits) - 1
        pixels = []
        for i in range(self.width * self.height):
            byte = self.data[o + i // per]
            pixels.append(byte >> (8 - bits * (i % per + 1)) & mask)
        return [pixels[y * self.width:(y + 1) * self.width] for y in range(self.height)]

    def box(self, code):
        """(left, glyph width, advance) of a character in pixels: where its picture starts, how wide it is and how far
        the pen moves after it. The default widths of the font when the character has none."""
        g = self.codes.get(code if isinstance(code, int) else ord(code))
        return self.widths.get(g, self.default_widths)

    def advance(self, code):
        """How far the pen moves after the character (pixels)."""
        return self.box(code)[2]
