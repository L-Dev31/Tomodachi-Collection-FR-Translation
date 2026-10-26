"""Order of the soft keyboard tabs."""
import struct

from ..core.compression import lz10, lz10c
from ..core.binary import u16, u32
from ..core.nitro import rgcn
from ..core.narc import narc_offsets
from ..core.rom import Rom


KEYBOARDS = ['Japanese', 'QWERTY', 'Accents', 'Symbols', 'Emojis']


KB_KIND = {'Japanese': 1, 'QWERTY': 0, 'Accents': 2, 'Symbols': 3, 'Emojis': 4}


KB_ICON = {'Japanese': 5, 'QWERTY': 0, 'Accents': 6, 'Symbols': 7, 'Emojis': 8}


KB_MAP = 0x20B7AD4


KB_STORES = (0x2081BF4, 0x2081BF8, 0x2081BFC)


KB_START = 0x2081AA4


KB_FILE = '/Cmn/Kbd/SoftKeyboard_LZ.bin'


def grey_to_white(r, g, b):
    if max(r, g, b) - min(r, g, b) <= 40 and (r + g + b) // 3 > 120:
        return '#ffffff'
    return '#%02x%02x%02x' % (r, g, b)


def kb_pixels(data):
    rom = Rom(data)
    s, e = rom.fat(rom.files()[KB_FILE])
    d = lz10(bytes(rom.d[s:e]))
    starts = narc_offsets(d)
    pal = starts[0] + 0x28
    tiles = rgcn(d, starts[2])
    out = {}
    for name, block in KB_ICON.items():
        rows = []
        for y in range(16):
            row = []
            for x in range(16):
                t = block * 4 + (y // 8) * 2 + x // 8
                v = d[tiles + t * 32 + (y % 8) * 4 + (x % 8) // 2]
                v = v >> 4 if x % 2 else v & 15
                c = u16(d, pal + v * 2)
                row.append(None if not v else grey_to_white((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31))
            rows.append(row)
        out[name] = rows
    return out


def apply_keyboard(rom, arm9, order, log):
    base = 0x02000000
    if sorted(order) != sorted(KEYBOARDS):
        raise RuntimeError('invalid keyboard order')
    if [u32(arm9, a - base) for a in KB_STORES] != [0xE58D2000, 0xE58D1004, 0xE58D0008] or u32(arm9, KB_START - base) != 0xE3A00001:
        raise RuntimeError('keyboard code not recognised (already reordered?)')
    for a in KB_STORES:
        struct.pack_into('<I', arm9, a - base, 0xE1A00000)
    struct.pack_into('<5I', arm9, KB_MAP - base, *[KB_KIND[n] for n in order])
    struct.pack_into('<I', arm9, KB_START - base, 0xE3A00000 | KB_KIND[order[0]])
    log(KB_FILE)
    fid = rom.files()[KB_FILE]
    s, e = rom.fat(fid)
    d = bytearray(lz10(bytes(rom.d[s:e])))
    tiles = rgcn(d, narc_offsets(d)[2])
    old = bytes(d)
    for slot, name in enumerate(order):
        dst = tiles + KB_ICON[KEYBOARDS[slot]] * 128
        src = tiles + KB_ICON[name] * 128
        d[dst:dst + 128] = old[src:src + 128]
    rom.put_file(fid, lz10c(bytes(d)))
