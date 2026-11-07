"""Adds characters to the fonts of the game (NFTR, one bit per pixel).

The game draws a character with the glyph its code is mapped to. A new character gets a new glyph cell at the end of the glyph block,
its width in a new width block and its code in a new code map (a list of code and glyph pairs). Nothing that exists is changed, so
the characters of the game keep their pictures and their numbers.

A glyph picture is a list of rows of 0 (no ink) and 1 (ink), height rows of width pixels. It comes from a TrueType font (render_rows)
or from a dark picture on a transparent background (picture_rows).
"""
import glob
import os
import struct

from ...core.binary import u16
from ...core.compression import lz10
from ...core.nftr import Font, FontError
from ...core.narc import narc_files

FONT_FILES = ('/Cmn/Font/FontLD12x_LZ.bin', '/Cmn/Font/FontLD10x_LZ.bin')     # the messages font, the keys font
ALL_FONTS = FONT_FILES + ('/Cmn/Font/FontLD08x_LZ.bin',)                        # every font the Fonts tab shows
TTF_CANDIDATES = ('DejaVuSans.ttf', 'NotoSans-Regular.ttf', 'LiberationSans-Regular.ttf', 'FreeSans.ttf')


def font_bytes(rom, path):
    """The NFTR bytes of a font file of the ROM (the archive holds one font)."""
    s, e = rom.fat(rom.files()[path])
    raw = bytes(rom.d[s:e])
    return narc_files(lz10(raw) if raw[:1] == b'\x10' else raw)[0]


def blocks_of(d):
    """[(magic, offset, size)] of the blocks of an NFTR file, in the order the file holds them."""
    count, p = u16(d, 14), u16(d, 12)
    out = []
    for _ in range(count):
        size = struct.unpack_from('<I', d, p + 4)[0]
        out.append((bytes(d[p:p + 4]), p, size))
        p += size
    return out


def encode_cell(rows, width, height, cell_size):
    """The bytes of one glyph cell (one bit a pixel, the first pixel in the top bit, rows one after the other)."""
    if len(rows) != height or any(len(r) != width for r in rows):
        raise ValueError(f'a glyph is {width} x {height} pixels')
    bits = [1 if px else 0 for r in rows for px in r]
    if (len(bits) + 7) // 8 > cell_size:
        raise ValueError('the glyph does not fit its cell')
    out = bytearray(cell_size)
    for i, bit in enumerate(bits):
        if bit:
            out[i // 8] |= 0x80 >> (i % 8)
    return bytes(out)


def add_glyphs(data, glyphs):
    """The NFTR bytes `data` with the characters of `glyphs` ({code: rows}) added. A code the font already draws is refused."""
    font = Font(data)
    d = bytes(data)
    if font.depth != 1:
        raise FontError('only fonts of one bit a pixel can get new characters')
    if not glyphs:
        return d
    taken = sorted(c for c in glyphs if c in font.codes)
    if taken:
        raise ValueError('the font already draws ' + ', '.join(f'U+{c:04X}' for c in taken[:6]))
    plgc = [b for b in blocks_of(d) if b[0] == b'PLGC'][0]
    if (plgc[2] - 16) // font.cell_size != font.glyph_count or (plgc[2] - 16) % font.cell_size >= font.cell_size:
        raise FontError('the glyph block does not hold whole cells: not changed')
    codes = sorted(glyphs)
    first = font.glyph_count
    cells = b''.join(encode_cell(glyphs[c], font.width, font.height, font.cell_size) for c in codes)
    glyph_block = bytearray(d[plgc[1]:plgc[1] + 16 + first * font.cell_size]) + cells
    glyph_block += b'\0' * (-len(glyph_block) % 4)                  # less than a cell: the count of cells does not change
    struct.pack_into('<I', glyph_block, 4, len(glyph_block))
    last = first + len(codes) - 1
    widths = bytearray(b'HDWC' + struct.pack('<I', 0) + struct.pack('<HH', first, last) + b'\0' * 4)
    for _ in codes:
        widths += bytes(struct.pack('<bBB', *font.default_widths))
    widths += b'\0' * (-len(widths) % 4)
    struct.pack_into('<I', widths, 4, len(widths))
    pairs = b''.join(struct.pack('<HH', c, first + i) for i, c in enumerate(codes))
    code_map = bytearray(b'PAMC' + struct.pack('<I', 0) + struct.pack('<HH', codes[0], codes[-1]) + struct.pack('<H', 2) + b'\0' * 6)
    code_map += struct.pack('<H', len(codes)) + pairs
    code_map += b'\0' * (-len(code_map) % 4)
    struct.pack_into('<I', code_map, 4, len(code_map))
    head = bytearray(d[:u16(d, 12)])
    out = bytearray()
    for magic, p, size in blocks_of(d):
        out += glyph_block if magic == b'PLGC' else d[p:p + size]
    out += widths + code_map
    struct.pack_into('<H', head, 14, u16(d, 14) + 2)
    struct.pack_into('<I', head, 8, len(head) + len(out))
    return bytes(head + out)


def render_rows(ch, width, height, ttf):
    """The picture of a character drawn by a TrueType font, as large as the cell allows, centred in it."""
    from PIL import Image, ImageDraw, ImageFont
    size = height
    while True:
        font = ImageFont.truetype(ttf, size)
        left, top, right, bottom = font.getbbox(ch)
        if (bottom - top <= height and right - left <= width) or size <= 4:
            break
        size -= 1
    img = Image.new('L', (width, height), 0)
    ImageDraw.Draw(img).text(((width - (right - left)) // 2 - left, (height - (bottom - top)) // 2 - top), ch, font=font, fill=255)
    px = img.load()
    return [[1 if px[x, y] >= 128 else 0 for x in range(width)] for y in range(height)]


def picture_rows(rgba, width, height):
    """The rows of a picture (RGBA bytes, width x height): dark opaque pixels are ink."""
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            i = 4 * (y * width + x)
            r, g, b, a = rgba[i:i + 4]
            row.append(1 if a >= 128 and (r + g + b) / 3 < 128 else 0)
        rows.append(row)
    return rows


def default_ttf():
    """A TrueType font of the system that has Latin, Greek and Cyrillic letters, or None when none is found."""
    for name in TTF_CANDIDATES:
        for folder in ('/usr/share/fonts', os.path.expanduser('~/.local/share/fonts'), os.path.expanduser('~/.fonts')):
            found = glob.glob(os.path.join(folder, '**', name), recursive=True)
            if found:
                return found[0]
    return None


def replace_glyph(data, code, rows):
    """The NFTR bytes `data` with the picture of a character the font draws replaced in its own cell (the size does not change)."""
    font = Font(data)
    if code not in font.codes:
        raise ValueError(f'the font does not draw U+{code:04X}')
    cell = encode_cell(rows, font.width, font.height, font.cell_size)
    out = bytearray(data)
    o = font.glyph_data + font.codes[code] * font.cell_size
    out[o:o + font.cell_size] = cell
    return bytes(out)


def apply_changes(data, glyphs):
    """The NFTR bytes `data` with the pictures of `glyphs` ({code: rows}): a character the font draws gets its new picture in its
    cell, any other character is added at the end of the font."""
    if not glyphs:
        return bytes(data)
    font = Font(data)
    out = bytes(data)
    for code in sorted(c for c in glyphs if c in font.codes):
        out = replace_glyph(out, code, glyphs[code])
    outside = {c: rows for c, rows in glyphs.items() if c not in font.codes}
    return add_glyphs(out, outside) if outside else out


def patched_font(rom, path, glyphs):
    """The Font of a font file of the ROM with `glyphs` applied (the font of the ROM when there are none)."""
    return Font(apply_changes(font_bytes(rom, path), glyphs))


def ttf_draws(ch, ttf):
    """Whether a TrueType font has the character: a font that lacks it draws its empty box for it, the same picture as a code that
    no font has."""
    if ch.isspace():
        return True
    width, height = 16, 20
    rows = render_rows(ch, width, height, ttf)
    box = render_rows('\U000F0000', width, height, ttf)
    return any(any(r) for r in rows) and rows != box


FONT_FOLDERS = ('/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.local/share/fonts'), os.path.expanduser('~/.fonts'),
                '/Library/Fonts', os.path.expanduser('~/Library/Fonts'), 'C:\\Windows\\Fonts')


def installed_fonts():
    """{name: path} of the TrueType and OpenType fonts installed on this computer, by name, sorted by name."""
    found = {}
    for folder in FONT_FOLDERS:
        for path in glob.glob(os.path.join(folder, '**', '*.[ot]tf'), recursive=True):
            found.setdefault(os.path.splitext(os.path.basename(path))[0], path)
    return dict(sorted(found.items(), key=lambda kv: kv[0].lower()))
