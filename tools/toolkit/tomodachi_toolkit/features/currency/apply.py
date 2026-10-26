"""Applies a currency to the ROM: price tables, display hooks, symbol."""
import math
import struct

from ...core.compression import lz10, lz10c
from ...core.binary import u32
from .glyphs import FONTS, GLYPHS, font_symbol, set_symbol, symbol_pictures
from .thunks import branch, cents_thunk, thunk
from .data import SYMBOL


FMT = 0x20364E0


PLAIN = 0x20363A8


CAVE = 0x20ECD18


T1, T1_ROWS, T1_MASK = 0x20F5AD8, 255, 0xFFFFFF


T2, T2_ROWS, T2_MASK, T2_MAX = 0x20F3BBC, 300, 0x7FFFFF, 990000


INCOME_CALL, INCOME = 0x2149844, 0x2149E1C


SITES = {
    'arm9': [(0x20AA998, FMT), (0x20AAA10, FMT), (0x20AB4BC, FMT), (0x20A903C, PLAIN)],
    68: [(0x214BAF4, FMT)],
    72: [(0x214F240, FMT)],
    75: [(0x2161408, FMT)],
    83: [(0x214B6EC, FMT)],
    84: [(0x214AD48, FMT), (0x214AEF4, PLAIN)],
    85: [(0x214BB24, FMT)],
    100: [(0x2149EBC, PLAIN)],
}


YEN_TEXT = 0x2114FD0


WHOLE = {'BIF', 'CLP', 'DJF', 'GNF', 'IDR', 'ISK', 'JPY', 'KMF', 'KRW', 'PYG', 'RWF', 'UGX', 'UYI', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'}


def cents_ok(code, rate):
    return code not in WHOLE and rate * 100 * T2_MAX <= T2_MASK


def convert_tables(arm9, scale, log):
    base = 0x02000000
    capped = 0
    for addr, rows, mask in ((T1, T1_ROWS, T1_MASK), (T2, T2_ROWS, T2_MASK)):
        o = addr - base
        for i in range(rows):
            w = u32(arm9, o + i * 20)
            price = w & mask
            if not price:
                continue
            new = convert(price, scale)
            if new > mask:
                new = mask
                capped += 1
            struct.pack_into('<I', arm9, o + i * 20, (w & ~mask & 0xFFFFFFFF) | new)
    if capped:
        log('%d prices capped at the field maximum' % capped)


def convert(value, rate):
    return max(1, math.floor(value * rate + 0.5)) if value else 0


def apply_currency(rom, arm9, cfg, log):
    rate, code, sym = cfg['rate'], cfg['code'], cfg['sym']
    whole = cfg['whole'] or not cents_ok(code, rate)
    scale = rate if whole else rate * 100
    base = 0x02000000
    thunks = {}
    pos = CAVE
    if any(arm9[CAVE - base:CAVE - base + 128]):
        raise RuntimeError('already patched or unsupported ROM')
    convert_tables(arm9, scale, log)

    def hook(buf, origin, addr, target):
        o = addr - origin
        if bytes(buf[o:o + 4]) != branch(addr, target, True):
            raise RuntimeError('unexpected code at %X' % addr)
        buf[o:o + 4] = branch(addr, thunks[target], True)

    if not whole:
        for target in (FMT, PLAIN):
            blob = (cents_thunk if target == FMT else thunk)(pos, target, 0.01)
            arm9[pos - base:pos - base + len(blob)] = blob
            thunks[target] = pos
            pos += len(blob)
        for addr, target in SITES['arm9']:
            hook(arm9, base, addr, target)
    if bytes(arm9[YEN_TEXT - base:YEN_TEXT - base + 2]) != bytes([0x86, 0x51]):
        raise RuntimeError('unexpected yen text')
    arm9[YEN_TEXT - base:YEN_TEXT - base + 2] = bytes([0xE5, 0xFF])
    for oid, sites in SITES.items():
        if oid == 'arm9' or whole:
            continue
        log('overlay %d' % oid)
        ent, fid, ram, blob = rom.overlay(oid)
        blob = bytearray(blob)
        for addr, target in sites:
            hook(blob, ram, addr, target)
        rom.put_file(fid, bytes(blob))
        struct.pack_into('<I', rom.d, ent + 28, 0)
    wrap, thunk_at = pos, pos + 16
    stub = thunk_at + len(thunk(thunk_at, 0, scale))
    code_blob = b''.join([struct.pack('<I', 0xE92D4008), branch(wrap + 4, INCOME, True), struct.pack('<I', 0xE8BD4008),
                          branch(wrap + 12, thunk_at, False), thunk(thunk_at, stub, scale), struct.pack('<I', 0xE12FFF1E)])
    arm9[wrap - base:wrap - base + len(code_blob)] = code_blob
    ent, fid, ram, blob = rom.overlay(82)
    blob = bytearray(blob)
    o = INCOME_CALL - ram
    if bytes(blob[o:o + 4]) != branch(INCOME_CALL, INCOME, True):
        raise RuntimeError('unexpected code at %X' % INCOME_CALL)
    blob[o:o + 4] = branch(INCOME_CALL, wrap, True)
    rom.put_file(fid, bytes(blob))
    struct.pack_into('<I', rom.d, ent + 28, 0)
    files = rom.files()
    char, cp, letter, bars = SYMBOL[code]
    letter = letter or code[0]
    spec = (ord(sym), letter, bars) if sym != char else (cp, letter, bars)
    s, e = rom.fat(files[FONTS[0]])
    bits = font_symbol(lz10(bytes(rom.d[s:e])), spec)[0]
    pat = [''.join('#' if bits[j * 7 + i] else '.' for i in range(7)) for j in range(7)]
    for path in FONTS:
        log(path)
        fid = files[path]
        s, e = rom.fat(fid)
        rom.put_file(fid, lz10c(set_symbol(lz10(bytes(rom.d[s:e])), spec)))
    for path, hits in (GLYPHS.items() if spec[0] != 0xFFE5 else []):
        log(path)
        fid = files[path]
        s, e = rom.fat(fid)
        rom.put_file(fid, lz10c(symbol_pictures(lz10(bytes(rom.d[s:e])), hits, pat)))
