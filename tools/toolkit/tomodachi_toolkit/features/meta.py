"""Banner: title in six languages, icon and internal name."""
import collections
import struct

from ..core.binary import crc16, u16, u32


REQUIREMENTS = (
    "Converted automatically:\n"
    "\u2022 PNG or GIF (no JPG)\n"
    "\u2022 Any size, fitted to 32x32\n"
    "  (transparent padding if not square)\n"
    "\u2022 15 colours + transparent\n"
    "  (more are reduced)"
)


LANGS = ['Japanese', 'English', 'French', 'German', 'Italian', 'Spanish']


def icon_grid(tiles, pal):
    out = []
    for y in range(32):
        row = []
        for x in range(32):
            v = tiles[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2]
            v = v >> 4 if x % 2 else v & 15
            c = u16(pal, v * 2)
            row.append(None if not v else '#%02x%02x%02x' % ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31))
        out.append(row)
    return out


def banner_pixels(data):
    b = u32(data, 0x68)
    return icon_grid(data[b + 0x20:b + 0x220], data[b + 0x220:b + 0x240])


def banner_read(data):
    b = u32(data, 0x68)
    titles = {n: bytes(data[b + 0x240 + i * 0x100:b + 0x340 + i * 0x100]).decode('utf-16le', 'replace').split('\0')[0] for i, n in enumerate(LANGS)}
    return titles, bytes(data[0:12]).decode('ascii', 'replace').rstrip('\0')


def fit32(w, h, pixels):
    s = 32 / max(w, h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    ox, oy = (32 - nw) // 2, (32 - nh) // 2
    out = [(0, 0, 0, 0)] * 1024
    for y in range(nh):
        for x in range(nw):
            out[(oy + y) * 32 + ox + x] = pixels[(y * h // nh) * w + x * w // nw]
    return out


def quantize(pixels):
    colors = [(r >> 3, g >> 3, b >> 3) for r, g, b, a in pixels if a >= 128]
    pal = [c for c, _ in collections.Counter(colors).most_common(15)]
    out = bytearray(512)
    for n, (r, g, b, a) in enumerate(pixels):
        v = 0
        if a >= 128:
            v = 1 + min(range(len(pal)), key=lambda k: (pal[k][0] - (r >> 3)) ** 2 + (pal[k][1] - (g >> 3)) ** 2 + (pal[k][2] - (b >> 3)) ** 2)
        x, y = n % 32, n // 32
        out[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= v << 4 if x % 2 else v
    return bytes(out), struct.pack('<16H', 0, *[c[0] | c[1] << 5 | c[2] << 10 for c in pal], *[0] * (15 - len(pal)))


def apply_meta(rom, cfg, log):
    d = rom.d
    b = u32(d, 0x68)
    for name, text in cfg.get('titles', {}).items():
        raw = text.encode('utf-16le')
        if len(raw) > 0x100:
            raise RuntimeError(f'{name} title is too long')
        o = b + 0x240 + LANGS.index(name) * 0x100
        d[o:o + 0x100] = raw.ljust(0x100, b'\0')
    if 'icon' in cfg:
        d[b + 0x20:b + 0x220], d[b + 0x220:b + 0x240] = cfg['icon']
    if 'internal' in cfg:
        d[0:12] = cfg['internal'].encode('ascii').ljust(12, b'\0')
    for n, end in enumerate((0x840, 0x940, 0xA40)[:u16(d, b) & 0xFF]):
        struct.pack_into('<H', d, b + 2 + n * 2, crc16(d, b + 0x20, b + end))
