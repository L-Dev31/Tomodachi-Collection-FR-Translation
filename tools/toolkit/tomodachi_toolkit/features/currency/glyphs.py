"""The yen sign: font glyphs and the pictures that contain it."""

from ...core.binary import u16, u32
from ...core.nitro import rgcn
from ...core.narc import narc_offsets


YEN_CODE = 0xFFE5                  # the character the game writes after a price: its glyph is the one that becomes the symbol of the money
YEN = ['#######', '#..#..#', '#..#..#', '#######', '#.....#', '#.....#', '#....##']


LIST_YEN = [(2, 32, 38, 97), (2, 32, 226, 59), (2, 32, 176, 87), (2, 32, 193, 132)]


GLYPHS = {
    '/Scn/List/List_AlbumList_LZ.bin': LIST_YEN,
    '/Scn/List/List_ChangeRoomList_LZ.bin': LIST_YEN,
    '/Scn/List/List_MiiList_LZ.bin': LIST_YEN,
    '/Scn/List/List_NewsList_LZ.bin': LIST_YEN,
    '/Scn/List/List_RightJobList_LZ.bin': LIST_YEN,
    '/Scn/List/List_ShopList_LZ.bin': LIST_YEN + [(3, 1, 1, 3521), (3, 8, 12, 501)],
    '/Scn/List/List_TouchList_LZ.bin': LIST_YEN,
    '/Scn/List/List_TushinItemList_LZ.bin': LIST_YEN,
    '/Scn/List/List_TushinList_LZ.bin': LIST_YEN,
    '/Scn/List/List_WriteSongList_LZ.bin': LIST_YEN,
    '/Scn/Scene/SceneMap2_LZ.bin': [(4, 8, 12, 333)],
    '/Scn/Scene/SceneMiiTouch_LZ.bin': [(7, 8, 44, 317)],
    '/Scn/Scene/SceneShop_LZ.bin': [(5, 32, 206, 65), (5, 32, 206, 169), (5, 32, 201, 4), (5, 32, 242, 11),
                                    (5, 32, 201, 108), (5, 32, 242, 115), (8, 1, 1, 65), (8, 1, 1, 1)],
    '/Scn/Scene/SceneTestNg136_LZ.bin': [(1, 32, 176, 87)],
    '/Scn/Scene/SceneWriteSong_LZ.bin': [(3, 32, 38, 97), (3, 32, 178, 83), (3, 32, 177, 124)],
}


FONTS = ['/Cmn/Font/FontLD08x_LZ.bin', '/Cmn/Font/FontLD10x_LZ.bin', '/Cmn/Font/FontLD12x_LZ.bin']


def symbol_pictures(d, hits, pat):
    d = bytearray(d)
    starts = narc_offsets(d)
    for sub, w, x, y in hits:
        base = rgcn(d, starts[sub])

        def at(px, py):
            o = base + ((py // 8) * w + px // 8) * 32 + ((py % 8) * 8 + px % 8) // 2
            return o, (px % 2) * 4

        def get(px, py):
            o, sh = at(px, py)
            return (d[o] >> sh) & 15

        ink = get(x, y)
        cells = [(i, j) for j in range(7) for i in range(7)]
        if any((YEN[j][i] == '#') != (get(x + i, y + j) == ink) for i, j in cells):
            raise RuntimeError('unexpected graphics')
        rest = [get(x + i, y + j) for i, j in cells if YEN[j][i] != '#']
        bg = max(set(rest), key=rest.count)
        for i, j in cells:
            o, sh = at(x + i, y + j)
            v = ink if pat[j][i] == '#' else bg
            d[o] = (d[o] & (0xF0 >> sh)) | (v << sh)
    return bytes(d)


def font_blocks(d):
    base = d.find(b'RTFN')
    p = base + u16(d, base + 12)
    out = {}
    for _ in range(u16(d, base + 14)):
        out.setdefault(bytes(d[p:p + 4]), []).append(p)
        p += u32(d, p + 4)
    return out


def glyph_index(d, maps, code):
    for p in maps:
        first, last, kind, d0 = u16(d, p + 8), u16(d, p + 10), u16(d, p + 12), p + 20
        if not first <= code <= last:
            continue
        if kind == 0:
            return u16(d, d0) + code - first
        if kind == 1:
            g = u16(d, d0 + (code - first) * 2)
            return None if g == 0xFFFF else g
        for i in range(u16(d, d0)):
            if u16(d, d0 + 2 + i * 4) == code:
                return u16(d, d0 + 4 + i * 4)
    return None


def font_cell(d):
    blocks = font_blocks(d)
    plgc, hdwc = blocks[b'PLGC'][0], blocks[b'HDWC'][0]
    return plgc, hdwc, blocks[b'PAMC'], d[plgc + 8], d[plgc + 9], u16(d, plgc + 10)


def glyph_bits(d, plgc, cw, ch, csz, g):
    raw = d[plgc + 16 + g * csz:plgc + 16 + (g + 1) * csz]
    return [(raw[i // 8] >> (7 - i % 8)) & 1 for i in range(cw * ch)]


def glyph_metrics(d, hdwc, g):
    o = hdwc + 16 + (g - u16(d, hdwc + 8)) * 3
    return bytes(d[o:o + 3])


def font_symbol(d, ch):
    """(bits, metrics) of the glyph a font (the bytes of its file) draws for the character ch; None when it has no glyph for it."""
    plgc, hdwc, maps, width, height, size = font_cell(d)
    g = glyph_index(d, maps, ord(ch))
    return None if g is None else (glyph_bits(d, plgc, width, height, size, g), glyph_metrics(d, hdwc, g))


def set_symbol(d, ch):
    """The font (the bytes of its file) with the glyph of the yen sign drawn as the character ch is: its picture and its widths, so that
    the symbol looks and spaces the way ch does everywhere else. Raises ValueError when the font has no glyph for ch."""
    found = font_symbol(d, ch)
    if found is None:
        raise ValueError(f'The fonts of the game cannot draw {ch!r}.')
    bits, metrics = found
    d = bytearray(d)
    plgc, hdwc, maps, width, height, size = font_cell(d)
    g = glyph_index(d, maps, YEN_CODE)
    bits = bits + [0] * (size * 8 - len(bits))
    d[plgc + 16 + g * size:plgc + 16 + (g + 1) * size] = bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, size * 8, 8))
    o = hdwc + 16 + (g - u16(d, hdwc + 8)) * 3
    d[o:o + 3] = metrics
    return bytes(d)
