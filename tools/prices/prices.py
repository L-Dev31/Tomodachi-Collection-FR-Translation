import json
import math
import struct
import tkinter as tk
import urllib.request
from tkinter import filedialog, messagebox, ttk

RATE_URL = 'https://open.er-api.com/v6/latest/JPY'
MARK = bytes.fromhex('2106c0dedec00621')
FMT = 0x20364E0
PLAIN = 0x20363A8
CAVE = 0x20ECD18
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
SYMBOL = {}
for codes, spec in (
        ('USD AUD CAD HKD NZD SGD TWD ARS BSD BBD BMD BZD BND CLP COP CUP DOP FJD GYD JMD KYD LRD MXN NAD SBD SRD TTD TVD UYU XCD ZWL TOP KID', ('$', 0x24, None, 0)),
        ('GBP EGP FKP GIP SHP GGP IMP JEP LBP SYP SSP SDG', ('£', 0xA3, 'L', 1)),
        ('JPY CNY CNH', ('¥', 0xFFE5, None, 0)),
        ('EUR', ('€', 0x20AC, 'C', 2)),
        ('ANG AWG XCG', ('ƒ', 0x192, 'f', 0)),
        ('KRW', ('₩', None, 'W', 2)),
        ('INR', ('₹', None, 'R', 2)),
        ('RUB', ('₽', None, 'P', 2)),
        ('PHP', ('₱', None, 'P', 2)),
        ('TRY', ('₺', None, 'L', 2)),
        ('VND', ('₫', None, 'D', 2)),
        ('NGN', ('₦', None, 'N', 2)),
        ('KZT', ('₸', None, 'T', 1)),
        ('MNT', ('₮', None, 'T', 2)),
        ('GHS', ('₵', None, 'C', 1)),
        ('CRC', ('₡', None, 'C', 2)),
        ('PYG', ('₲', None, 'G', 2)),
        ('LAK', ('₭', None, 'K', 2)),
        ('AZN', ('₼', None, 'M', 1)),
        ('GEL', ('₾', None, 'L', 2)),
        ('ILS', ('₪', None, 'I', 2)),
        ('UAH', ('₴', None, 'H', 2)),
        ('DKK FOK HRK ISK NOK SEK', ('k', None, 'k', 0)),
        ('PLN', ('z', None, 'z', 0)),
        ('AED DZD IQD MKD RSD TND STN GMD MAD AMD', ('D', None, 'D', 0)),
        ('ALL BGN HNL LSL SZL MDL RON LYD SLE SLL', ('L', None, 'L', 0)),
        ('AOA BAM CZK KES KWD MMK MWK PGK ZMW', ('K', None, 'K', 0)),
        ('BIF CDF CHF DJF GNF HUF KMF RWF XAF XOF XPF', ('F', None, 'F', 0)),
        ('KGS PEN SAR SOS TJS UZS XDR', ('S', None, 'S', 0)),
        ('BRL IDR IRR KHR LKR MUR MVR MYR NPR OMR PKR SCR YER ZAR', ('R', None, 'R', 0)),
        ('BOB BYN ETB PAB VES THB BHD', ('B', None, 'B', 0)),
        ('NIO', ('C', None, 'C', 0)),
        ('CVE', ('E', None, 'E', 0)),
        ('HTG', ('G', None, 'G', 0)),
        ('GTQ QAR', ('Q', None, 'Q', 0)),
        ('BTN ERN', ('N', None, 'N', 0)),
        ('MZN', ('M', None, 'M', 0)),
        ('BWP MOP', ('P', None, 'P', 0)),
        ('AFN MGA', ('A', None, 'A', 0)),
        ('CLF MRU UGX', ('U', None, 'U', 0)),
        ('BDT TMT TZS WST', ('T', None, 'T', 0)),
        ('VUV', ('V', None, 'V', 0)),
        ('ZWG', ('Z', None, 'Z', 0)),
        ('JOD', ('J', None, 'J', 0)),
):
    for code in codes.split():
        SYMBOL[code] = spec
NAMES = dict(line.split(' ', 1) for line in '''
AED UAE Dirham
AFN Afghan Afghani
ALL Albanian Lek
AMD Armenian Dram
ANG Netherlands Antillean Guilder
AOA Angolan Kwanza
ARS Argentine Peso
AUD Australian Dollar
AWG Aruban Florin
AZN Azerbaijani Manat
BAM Bosnia-Herzegovina Mark
BBD Barbadian Dollar
BDT Bangladeshi Taka
BGN Bulgarian Lev
BHD Bahraini Dinar
BIF Burundian Franc
BMD Bermudan Dollar
BND Brunei Dollar
BOB Bolivian Boliviano
BRL Brazilian Real
BSD Bahamian Dollar
BTN Bhutanese Ngultrum
BWP Botswanan Pula
BYN Belarusian Ruble
BZD Belize Dollar
CAD Canadian Dollar
CDF Congolese Franc
CHF Swiss Franc
CLF Chilean Unit of Account
CLP Chilean Peso
CNH Chinese Yuan (offshore)
CNY Chinese Yuan
COP Colombian Peso
CRC Costa Rican Colón
CUP Cuban Peso
CVE Cape Verdean Escudo
CZK Czech Koruna
DJF Djiboutian Franc
DKK Danish Krone
DOP Dominican Peso
DZD Algerian Dinar
EGP Egyptian Pound
ERN Eritrean Nakfa
ETB Ethiopian Birr
EUR Euro
FJD Fijian Dollar
FKP Falkland Islands Pound
FOK Faroese Króna
GBP British Pound
GEL Georgian Lari
GGP Guernsey Pound
GHS Ghanaian Cedi
GIP Gibraltar Pound
GMD Gambian Dalasi
GNF Guinean Franc
GTQ Guatemalan Quetzal
GYD Guyanese Dollar
HKD Hong Kong Dollar
HNL Honduran Lempira
HRK Croatian Kuna
HTG Haitian Gourde
HUF Hungarian Forint
IDR Indonesian Rupiah
ILS Israeli New Shekel
IMP Manx Pound
INR Indian Rupee
IQD Iraqi Dinar
IRR Iranian Rial
ISK Icelandic Króna
JEP Jersey Pound
JMD Jamaican Dollar
JOD Jordanian Dinar
JPY Japanese Yen
KES Kenyan Shilling
KGS Kyrgyzstani Som
KHR Cambodian Riel
KID Kiribati Dollar
KMF Comorian Franc
KRW South Korean Won
KWD Kuwaiti Dinar
KYD Cayman Islands Dollar
KZT Kazakhstani Tenge
LAK Lao Kip
LBP Lebanese Pound
LKR Sri Lankan Rupee
LRD Liberian Dollar
LSL Lesotho Loti
LYD Libyan Dinar
MAD Moroccan Dirham
MDL Moldovan Leu
MGA Malagasy Ariary
MKD Macedonian Denar
MMK Myanmar Kyat
MNT Mongolian Tugrik
MOP Macanese Pataca
MRU Mauritanian Ouguiya
MUR Mauritian Rupee
MVR Maldivian Rufiyaa
MWK Malawian Kwacha
MXN Mexican Peso
MYR Malaysian Ringgit
MZN Mozambican Metical
NAD Namibian Dollar
NGN Nigerian Naira
NIO Nicaraguan Córdoba
NOK Norwegian Krone
NPR Nepalese Rupee
NZD New Zealand Dollar
OMR Omani Rial
PAB Panamanian Balboa
PEN Peruvian Sol
PGK Papua New Guinean Kina
PHP Philippine Peso
PKR Pakistani Rupee
PLN Polish Złoty
PYG Paraguayan Guaraní
QAR Qatari Riyal
RON Romanian Leu
RSD Serbian Dinar
RUB Russian Ruble
RWF Rwandan Franc
SAR Saudi Riyal
SBD Solomon Islands Dollar
SCR Seychellois Rupee
SDG Sudanese Pound
SEK Swedish Krona
SGD Singapore Dollar
SHP Saint Helena Pound
SLE Sierra Leonean Leone
SLL Sierra Leonean Leone (old)
SOS Somali Shilling
SRD Surinamese Dollar
SSP South Sudanese Pound
STN São Tomé and Príncipe Dobra
SYP Syrian Pound
SZL Swazi Lilangeni
THB Thai Baht
TJS Tajikistani Somoni
TMT Turkmenistani Manat
TND Tunisian Dinar
TOP Tongan Paʻanga
TRY Turkish Lira
TTD Trinidad and Tobago Dollar
TVD Tuvaluan Dollar
TWD New Taiwan Dollar
TZS Tanzanian Shilling
UAH Ukrainian Hryvnia
UGX Ugandan Shilling
USD US Dollar
UYU Uruguayan Peso
UZS Uzbekistani Som
VES Venezuelan Bolívar
VND Vietnamese Dong
VUV Vanuatu Vatu
WST Samoan Tala
XAF Central African CFA Franc
XCD East Caribbean Dollar
XCG Caribbean Guilder
XDR Special Drawing Rights
XOF West African CFA Franc
XPF CFP Franc
YER Yemeni Rial
ZAR South African Rand
ZMW Zambian Kwacha
ZWG Zimbabwe Gold
ZWL Zimbabwean Dollar
'''.strip().splitlines())
YEN_TEXT = 0x2114FD0


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def lz10(b):
    size = b[1] | (b[2] << 8) | (b[3] << 16)
    out = bytearray(size)
    ip, op = 4, 0
    while op < size:
        flags = b[ip]
        ip += 1
        for i in range(7, -1, -1):
            if op >= size:
                break
            if flags & (1 << i):
                b1, b2 = b[ip], b[ip + 1]
                ip += 2
                disp = (((b1 & 15) << 8) | b2) + 1
                for _ in range(min((b1 >> 4) + 3, size - op)):
                    out[op] = out[op - disp]
                    op += 1
            else:
                out[op] = b[ip]
                op += 1
                ip += 1
    return bytes(out)


def lz10c(data):
    n = len(data)
    out = bytearray([0x10, n & 255, (n >> 8) & 255, (n >> 16) & 255])
    heads, chain = {}, [0] * n

    def add(i):
        if i + 2 < n:
            k = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
            chain[i] = heads.get(k, -1)
            heads[k] = i

    i = 0
    while i < n:
        flags, block = 0, bytearray()
        for bit in range(8):
            if i >= n:
                break
            best, dist = 0, 0
            if i + 2 < n:
                j = heads.get(data[i] | (data[i + 1] << 8) | (data[i + 2] << 16), -1)
                tries = 0
                while j >= 0 and tries < 64 and i - j <= 4096:
                    if i - j >= 2:
                        m = 0
                        while m < min(18, n - i) and data[j + m] == data[i + m]:
                            m += 1
                        if m > best:
                            best, dist = m, i - j
                    j = chain[j]
                    tries += 1
            if best >= 3:
                flags |= 0x80 >> bit
                block += bytes([((best - 3) << 4) | ((dist - 1) >> 8), (dist - 1) & 255])
                for t in range(best):
                    add(i + t)
                i += best
            else:
                block.append(data[i])
                add(i)
                i += 1
        out.append(flags)
        out += block
    return bytes(out) + b'\0' * (-len(out) % 4)


def blz(f):
    n = len(f)
    inc = u32(f, n - 4)
    if not inc:
        return bytes(f[:n - 4])
    enc = u32(f, n - 8) & 0xFFFFFF
    dec = n - enc
    raw = bytearray(dec + enc + inc)
    raw[0:dec] = f[0:dec]
    e = bytes(f[dec:dec + enc - f[n - 5]])[::-1]
    p, o, fl, m = 0, dec, 0, 0
    while o < len(raw):
        m >>= 1
        if not m:
            if p >= len(e):
                break
            fl = e[p]
            p += 1
            m = 0x80
        if not fl & m:
            if p >= len(e):
                break
            raw[o] = e[p]
            o += 1
            p += 1
        else:
            if p + 1 >= len(e):
                break
            pos = (e[p] << 8) | e[p + 1]
            p += 2
            dist = (pos & 0xFFF) + 3
            for _ in range(min((pos >> 12) + 3, len(raw) - o)):
                raw[o] = raw[o - dist]
                o += 1
    raw[dec:] = raw[dec:][::-1]
    return bytes(raw)


def crc16(b, s, e):
    crc = 0xFFFF
    for i in range(s, e):
        crc ^= b[i]
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def arm_imm(v):
    for rot in range(0, 32, 2):
        r = ((v << rot) | (v >> (32 - rot))) & 0xFFFFFFFF if rot else v
        if r < 256:
            return (rot // 2 << 8) | r
    raise ValueError(v)


def branch(src, dst, link):
    return struct.pack('<I', (0xEB000000 if link else 0xEA000000) | (((dst - src - 8) >> 2) & 0xFFFFFF))


def thunk(addr, target, rate):
    shift = 32
    while round(rate * 2 ** shift) >= 2 ** 32:
        shift -= 1
    code = [0xE92D100E, 0xE1A0C000, 0, 0xE0832190, 0xE2922000 | arm_imm(1 << (shift - 1)), 0xE2A33000]
    code += [0xE1A00003] if shift == 32 else [0xE1A00022 + (shift << 7), 0xE1800003 | ((32 - shift) << 7)]
    code += [0xE3500000, 0x1A000001, 0xE35C0000, 0x13A00001, 0xE8BD100E]
    code[2] = 0xE59F1000 | (4 * len(code) + 4 - 16)
    body = b''.join(struct.pack('<I', w) for w in code)
    body += branch(addr + len(body), target, False)
    return body + struct.pack('<I', round(rate * 2 ** shift))


CENTS = bytes.fromhex(
    'fe402de90040a0e1d8509fe5940586e0010590e20060a6e2a00ba0e1860480e1000050e30100001a000054e30100a013'
    'b4709fe5905786e0a662a0e16430a0e3960305e0057040e008d04de228509de500508de504708de50600a0e108109de5'
    '0c209de510309de5e4ffffeb08109de504709de50120a0e1b030d2e1000053e302208212fbffff1a025042e2b030d5e1'
    '58409fe5040053e10520a001cd30a0e3970305e0a555a0e10a30a0e3950306e0066047e038309fe5035085e0036086e0'
    '2e70a0e3b070c2e1b250c2e1b460c2e10030a0e3b630c2e1b640c201b830c20108d08de2fe80bde8000000321f85eb51'
    'e5ff000010ff0000')


def cents_thunk(addr, target, rate):
    if rate * 100 * 9999999 >= 2 ** 32:
        raise RuntimeError('cents not available for this currency')
    blob = bytearray(CENTS)
    struct.pack_into('<I', blob, 232, round(rate * 100 * 2 ** 23))
    struct.pack_into('<I', blob, 104, 0xEB000000 | (((target - (addr + 104 + 8)) >> 2) & 0xFFFFFF))
    return bytes(blob)


def convert(value, rate):
    return max(1, math.floor(value * rate + 0.5)) if value else 0


class Rom:
    def __init__(self, data):
        self.d = bytearray(data)
        self.tail = 0

    def fat(self, fid):
        o = u32(self.d, 0x48) + fid * 8
        return u32(self.d, o), u32(self.d, o + 4)

    def set_fat(self, fid, s, e):
        o = u32(self.d, 0x48) + fid * 8
        struct.pack_into('<II', self.d, o, s, e)

    def files(self):
        fnt, out = u32(self.d, 0x40), {}

        def walk(dir_id, prefix):
            entry = fnt + (dir_id & 0xFFF) * 8
            p, fid = fnt + u32(self.d, entry), u16(self.d, entry + 4)
            while self.d[p]:
                b = self.d[p]
                name = self.d[p + 1:p + 1 + (b & 127)].decode('latin1')
                p += 1 + (b & 127)
                if b & 128:
                    walk(u16(self.d, p), prefix + name + '/')
                    p += 2
                else:
                    out[prefix + name] = fid
                    fid += 1

        walk(0xF000, '/')
        return out

    def append(self, blob):
        if not self.tail:
            ends = [self.fat(i)[1] for i in range(u32(self.d, 0x4C) // 8)]
            self.tail = (max(ends + [u32(self.d, 0x50) + u32(self.d, 0x54), u32(self.d, 0x80)]) + 0x1FF) & ~0x1FF
        off = self.tail
        if off + len(blob) > len(self.d):
            self.d.extend(b'\xff' * (off + len(blob) - len(self.d)))
        self.d[off:off + len(blob)] = blob
        self.tail = (off + len(blob) + 0x1FF) & ~0x1FF
        return off

    def put_file(self, fid, blob):
        off = self.append(blob)
        self.set_fat(fid, off, off + len(blob))

    def arm9(self):
        off, size = u32(self.d, 0x20), u32(self.d, 0x2C)
        f = bytes(self.d[off:off + size])
        i = f.find(MARK)
        if i < 0:
            raise RuntimeError('ARM9 module not recognised')
        return blz(f) if u32(f, i - 8) else f

    def set_arm9(self, raw):
        off = 0x4000
        end = off + len(raw) + 12
        old = u32(self.d, 0x20) + u32(self.d, 0x2C)
        footer = bytes(self.d[old:old + 12])
        for o in (0x30, 0x68):
            if 0 < u32(self.d, o) < end:
                raise RuntimeError('ARM7 or banner in the way')
        t, n = u32(self.d, 0x50), u32(self.d, 0x54)
        if t < end:
            blob = bytes(self.d[t:t + n])
            self.d[t:t + n] = b'\xff' * n
            struct.pack_into('<I', self.d, 0x50, self.append(blob))
        for fid in range(u32(self.d, 0x4C) // 8):
            s, e = self.fat(fid)
            if s < end and e > off and e > s:
                blob = bytes(self.d[s:e])
                self.d[s:e] = b'\xff' * (e - s)
                self.put_file(fid, blob)
        raw = bytearray(raw)
        struct.pack_into('<I', raw, raw.find(MARK) - 8, 0)
        self.d[off:off + len(raw)] = raw
        self.d[off + len(raw):end] = footer
        struct.pack_into('<I', self.d, 0x20, off)
        struct.pack_into('<I', self.d, 0x2C, len(raw))

    def overlay(self, oid):
        t = u32(self.d, 0x50)
        for ent in range(t, t + u32(self.d, 0x54), 32):
            if u32(self.d, ent) == oid:
                fid, comp = u32(self.d, ent + 24), u32(self.d, ent + 28)
                s, e = self.fat(fid)
                data = bytes(self.d[s:e])
                return ent, fid, u32(self.d, ent + 4), (blz(data) if comp & 0x1000000 else data)
        raise RuntimeError('overlay %d missing' % oid)

    def save(self):
        if self.tail:
            struct.pack_into('<I', self.d, 0x80, self.tail)
            cap = 0
            while (128 << 10) << cap < len(self.d):
                cap += 1
            self.d[0x14] = max(self.d[0x14], cap)
        struct.pack_into('<H', self.d, 0x15E, crc16(self.d, 0, 0x15E))
        return bytes(self.d)


def rgcn(d, a):
    p = a + 0x10
    while d[p:p + 4] != b'RAHC':
        p += u32(d, p + 4)
    return p + 8 + u32(d, p + 28)


def narc(d):
    p = u16(d, 12)
    tbl = {}
    while p < len(d):
        tbl[bytes(d[p:p + 4])] = p
        p += u32(d, p + 4)
    fat, gm = tbl[b'BTAF'], tbl[b'GMIF']
    return [(u32(d, fat + 12 + i * 8) + gm + 8) for i in range(u16(d, fat + 8))]


def symbol_pictures(d, hits, pat):
    d = bytearray(d)
    starts = narc(d)
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


def cell(d):
    blocks = font_blocks(d)
    plgc, hdwc = blocks[b'PLGC'][0], blocks[b'HDWC'][0]
    return plgc, hdwc, blocks[b'PAMC'], d[plgc + 8], d[plgc + 9], u16(d, plgc + 10)


def glyph_bits(d, plgc, cw, ch, csz, g):
    raw = d[plgc + 16 + g * csz:plgc + 16 + (g + 1) * csz]
    return [(raw[i // 8] >> (7 - i % 8)) & 1 for i in range(cw * ch)]


def glyph_metrics(d, hdwc, g):
    o = hdwc + 16 + (g - u16(d, hdwc + 8)) * 3
    return bytes(d[o:o + 3])


def symbol(d, spec):
    cp, letter, bars = spec
    plgc, hdwc, maps, cw, ch, csz = cell(d)
    g = glyph_index(d, maps, cp) if cp is not None else None
    if g is not None:
        return glyph_bits(d, plgc, cw, ch, csz, g), glyph_metrics(d, hdwc, g)
    if letter:
        g = glyph_index(d, maps, ord(letter))
        bits = glyph_bits(d, plgc, cw, ch, csz, g)
        for k in range(bars):
            y = ch * (k + 1) // (bars + 1)
            bits[y * cw:(y + 1) * cw] = [1] * cw
        return bits, glyph_metrics(d, hdwc, g)


def set_symbol(d, spec):
    d = bytearray(d)
    plgc, hdwc, maps, cw, ch, csz = cell(d)
    g = glyph_index(d, maps, 0xFFE5)
    bits = symbol(d, spec)[0]
    bits = bits + [0] * (csz * 8 - len(bits))
    d[plgc + 16 + g * csz:plgc + 16 + (g + 1) * csz] = bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, csz * 8, 8))
    return bytes(d)


def patch(data, rate, code, sym, whole=True, log=print):
    rom = Rom(data)
    arm9 = bytearray(rom.arm9())
    base = 0x02000000
    thunks = {}
    pos = CAVE
    if any(arm9[CAVE - base:CAVE - base + 128]):
        raise RuntimeError('already patched or unsupported ROM')
    for target in (FMT, PLAIN):
        blob = (cents_thunk if not whole and target == FMT else thunk)(pos, target, rate)
        arm9[pos - base:pos - base + len(blob)] = blob
        thunks[target] = pos
        pos += len(blob)

    def hook(buf, origin, addr, target):
        o = addr - origin
        if bytes(buf[o:o + 4]) != branch(addr, target, True):
            raise RuntimeError('unexpected code at %X' % addr)
        buf[o:o + 4] = branch(addr, thunks[target], True)

    for addr, target in SITES['arm9']:
        hook(arm9, base, addr, target)
    if bytes(arm9[YEN_TEXT - base:YEN_TEXT - base + 2]) != bytes([0x86, 0x51]):
        raise RuntimeError('unexpected yen text')
    arm9[YEN_TEXT - base:YEN_TEXT - base + 2] = bytes([0xE5, 0xFF])
    rom.set_arm9(bytes(arm9))
    for oid, sites in SITES.items():
        if oid == 'arm9':
            continue
        log('overlay %d' % oid)
        ent, fid, ram, blob = rom.overlay(oid)
        blob = bytearray(blob)
        for addr, target in sites:
            hook(blob, ram, addr, target)
        rom.put_file(fid, bytes(blob))
        struct.pack_into('<I', rom.d, ent + 28, 0)
    files = rom.files()
    char, cp, letter, bars = SYMBOL[code]
    letter = letter or code[0]
    spec = (ord(sym), letter, bars) if sym != char else (cp, letter, bars)
    s, e = rom.fat(files[FONTS[0]])
    bits = symbol(lz10(bytes(rom.d[s:e])), spec)[0]
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
    return rom.save()


def fetch_rates():
    with urllib.request.urlopen(RATE_URL, timeout=10) as r:
        return json.load(r)['rates']


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Tomodachi currency')
        self.path = tk.StringVar()
        self.choice = tk.StringVar()
        self.symbol = tk.StringVar()
        self.info = tk.StringVar()
        self.whole = tk.BooleanVar(value=True)
        try:
            self.rates = fetch_rates()
        except Exception as e:
            self.rates = {}
            messagebox.showerror('Rates', f'Rate API unavailable:\n{e}')
        self.names = [f'{c}  {NAMES.get(c, "")}' for c in sorted(self.rates)]
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack()
        tk.Label(frame, text='Currency').grid(row=0, column=0, sticky='w', pady=4)
        combo = ttk.Combobox(frame, textvariable=self.choice, values=self.names, state='readonly', width=36)
        combo.grid(row=0, column=1, columnspan=2, sticky='w')
        combo.bind('<<ComboboxSelected>>', lambda e: self.pick())
        tk.Label(frame, text='Symbol').grid(row=1, column=0, sticky='w', pady=4)
        tk.Entry(frame, textvariable=self.symbol, width=4).grid(row=1, column=1, sticky='w')
        tk.Button(frame, text='Reset', command=self.reset).grid(row=1, column=2, sticky='w')
        tk.Checkbutton(frame, text='Round to whole units', variable=self.whole).grid(row=2, column=0, columnspan=3, sticky='w', pady=4)
        tk.Label(frame, textvariable=self.info).grid(row=3, column=0, columnspan=3, sticky='w')
        tk.Label(frame, textvariable=self.path, width=48, anchor='w').grid(row=4, column=0, columnspan=3, sticky='w', pady=(12, 0))
        tk.Button(frame, text='Open ROM', command=self.open_rom).grid(row=5, column=0, sticky='w', pady=4)
        tk.Button(frame, text='Patch ROM', command=self.run).grid(row=5, column=1, sticky='w', pady=4)
        self.status = tk.Label(frame, text='', anchor='w')
        self.status.grid(row=6, column=0, columnspan=3, sticky='w')
        self.choice.set(next((n for n in self.names if n.startswith('EUR ')), self.names[0] if self.names else ''))
        self.pick()

    def code(self):
        return self.choice.get().split()[0] if self.choice.get() else ''

    def pick(self):
        code = self.code()
        self.symbol.set(SYMBOL[code][0])
        rate = self.rates.get(code)
        self.info.set(f'1 {code} = {1 / rate:,.2f} JPY' if rate else '')

    def reset(self):
        self.symbol.set(SYMBOL[self.code()][0])

    def open_rom(self):
        path = filedialog.askopenfilename(filetypes=[('Nintendo DS ROM', '*.nds')])
        if path:
            self.path.set(path)

    def log(self, text):
        self.status.config(text=text)
        self.update()

    def run(self):
        code, sym = self.code(), self.symbol.get()
        if not self.path.get() or not code:
            return
        if len(sym) != 1:
            messagebox.showerror('Symbol', 'One character only.')
            return
        out = filedialog.asksaveasfilename(defaultextension='.nds', initialfile=f'tomodachi_{code}.nds')
        if not out:
            return
        try:
            with open(self.path.get(), 'rb') as f:
                result = patch(f.read(), self.rates[code], code, sym, self.whole.get(), self.log)
            with open(out, 'wb') as f:
                f.write(result)
            self.log('Done')
        except Exception as e:
            self.log('')
            messagebox.showerror('Patch failed', str(e))


if __name__ == '__main__':
    App().mainloop()
