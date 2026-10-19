import os
import collections
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
KEYBOARDS = ['Japanese', 'QWERTY', 'Accents', 'Symbols', 'Emojis']
KB_KIND = {'Japanese': 1, 'QWERTY': 0, 'Accents': 2, 'Symbols': 3, 'Emojis': 4}
KB_ICON = {'Japanese': 5, 'QWERTY': 0, 'Accents': 6, 'Symbols': 7, 'Emojis': 8}
KB_MAP = 0x20B7AD4
KB_STORES = (0x2081BF4, 0x2081BF8, 0x2081BFC)
KB_START = 0x2081AA4
KB_FILE = '/Cmn/Kbd/SoftKeyboard_LZ.bin'
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


def meta(rom, cfg, log):
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


def grey_to_white(r, g, b):
    if max(r, g, b) - min(r, g, b) <= 40 and (r + g + b) // 3 > 120:
        return '#ffffff'
    return '#%02x%02x%02x' % (r, g, b)


def kb_pixels(data):
    rom = Rom(data)
    s, e = rom.fat(rom.files()[KB_FILE])
    d = lz10(bytes(rom.d[s:e]))
    starts = narc(d)
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


def keyboard(rom, arm9, order, log):
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
    tiles = rgcn(d, narc(d)[2])
    old = bytes(d)
    for slot, name in enumerate(order):
        dst = tiles + KB_ICON[KEYBOARDS[slot]] * 128
        src = tiles + KB_ICON[name] * 128
        d[dst:dst + 128] = old[src:src + 128]
    rom.put_file(fid, lz10c(bytes(d)))


def currency(rom, arm9, cfg, log):
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


def patch(data, cfg, log=print):
    rom = Rom(data)
    arm9 = bytearray(rom.arm9())
    if 'currency' in cfg:
        currency(rom, arm9, cfg['currency'], log)
    if 'keyboard' in cfg:
        keyboard(rom, arm9, cfg['keyboard'], log)
    if 'meta' in cfg:
        meta(rom, cfg['meta'], log)
    rom.set_arm9(bytes(arm9))
    return rom.save()


def fetch_rates():
    with urllib.request.urlopen(RATE_URL, timeout=10) as r:
        return json.load(r)['rates']


BG = '#FFF3D9'
PANEL = '#FFFFFF'
ORANGE = '#F7822B'
DARK = '#D96A14'
BROWN = '#5B3A1C'
WARM = '#A39382'
MUTED = '#9A7B5B'
SAND = '#F6DDB0'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Tomodachi Location Toolkit')
        self.configure(bg=BG)
        self.resizable(False, False)
        self.rom = None
        self.choice = tk.StringVar()
        self.symbol = tk.StringVar()
        self.info = tk.StringVar()
        self.whole = tk.BooleanVar(value=False)
        self.order = list(KEYBOARDS)
        self.icons = {}
        self.lang = tk.StringVar(value='English')
        self.internal = tk.StringVar()
        self.cur = 'English'
        self.icon_new = None
        try:
            self.rates = fetch_rates()
        except Exception as e:
            self.rates = {}
            messagebox.showerror('Rates', f'Rate API unavailable:\n{e}')
        self.names = [f'{c}  {NAMES.get(c, "")}' for c in sorted(self.rates)]
        self.style()
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', padx=12, pady=(12, 0))
        self.tabs.add(self.rom_tab(self.tabs), text='  ROM  ')
        self.tabs.add(self.meta_tab(self.tabs), text='  Meta  ')
        self.tabs.add(self.currency_tab(self.tabs), text='  Currency  ')
        self.tabs.add(self.keyboard_tab(self.tabs), text='  Keyboard  ')
        footer = tk.Frame(self, bg=BG, pady=10)
        footer.pack(fill='x')
        tk.Label(footer, text='2026 by L-DEV31 - TomoDS Team', bg=BG, fg=DARK, font=('Segoe UI', 9)).pack()
        self.choice.set(next((n for n in self.names if n.startswith('JPY ')), self.names[0] if self.names else ''))
        self.lock()
        self.pick()

    def lock(self):
        on = self.rom is not None
        for index in (1, 2, 3):
            self.tabs.tab(index, state='normal' if on else 'disabled')
        self.patch_btn.state(['!disabled'] if on else ['disabled'])

    def rom_tab(self, parent):
        page = ttk.Frame(parent, padding=14)
        self.rom_name = tk.StringVar(value='No ROM loaded')
        self.rom_dir = tk.StringVar(value='Open a Tomodachi Collection .nds file to unlock the other tabs.')
        self.rom_size = tk.StringVar()
        self.sum_currency = tk.StringVar()
        self.sum_keyboard = tk.StringVar()
        self.sum_meta = tk.StringVar()
        card = tk.Frame(page, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=14, pady=14)
        card.pack(fill='x')
        holder = tk.Frame(card, width=64, height=64, bg=WARM)
        holder.pack_propagate(False)
        holder.grid(row=0, column=0, rowspan=3, sticky='n')
        self.badge = tk.Label(holder, text='?', bg=WARM, fg='white', font=('Segoe UI', 22, 'bold'), bd=0)
        self.badge.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(card, textvariable=self.rom_name, bg=PANEL, fg=BROWN, font=('Segoe UI', 11, 'bold'), anchor='w').grid(row=0, column=1, sticky='w', padx=12)
        tk.Label(card, textvariable=self.rom_dir, bg=PANEL, fg=MUTED, font=('Segoe UI', 8), anchor='w', justify='left', wraplength=210).grid(row=1, column=1, sticky='w', padx=12)
        tk.Label(card, textvariable=self.rom_size, bg=PANEL, fg=DARK, font=('Segoe UI', 9, 'bold'), anchor='w').grid(row=2, column=1, sticky='w', padx=12)
        self.open_btn = ttk.Button(card, text='Open ROM', style='Accent.TButton', command=self.open_rom)
        self.open_btn.grid(row=0, column=2, rowspan=3, sticky='e')
        card.columnconfigure(1, weight=1)
        info = tk.Frame(page, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=14, pady=12)
        info.pack(fill='x', pady=(12, 0))
        tk.Label(info, text='WILL BE APPLIED', bg=PANEL, fg=DARK, font=('Segoe UI', 8, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w')
        for r, (label, var) in enumerate((('Meta', self.sum_meta), ('Currency', self.sum_currency), ('Keyboard', self.sum_keyboard)), 1):
            tk.Label(info, text=label, bg=PANEL, fg=MUTED, font=('Segoe UI', 9), anchor='w', width=9).grid(row=r, column=0, sticky='nw', pady=(8, 0))
            tk.Label(info, textvariable=var, bg=PANEL, fg=BROWN, font=('Segoe UI', 9, 'bold'), anchor='w', justify='left', wraplength=290).grid(row=r, column=1, sticky='w', pady=(8, 0))
        self.patch_btn = ttk.Button(page, text='Patch ROM', style='Big.TButton', command=self.run)
        self.patch_btn.pack(fill='x', pady=(14, 0))
        self.status = tk.Label(page, text='', bg=BG, fg=DARK, font=('Segoe UI', 9))
        self.status.pack(pady=(8, 0))
        self.symbol.trace_add('write', lambda *_: self.refresh_summary())
        return page

    def show_rom(self, path, data):
        img = tk.PhotoImage(master=self, width=32, height=32)
        for y, row in enumerate(banner_pixels(data)):
            img.put('{' + ' '.join(c or PANEL for c in row) + '}', to=(0, y))
        self.banner = img.zoom(2)
        self.badge.config(image=self.banner, text='', bg=PANEL)
        folder = os.path.dirname(path)
        self.rom_name.set(os.path.basename(path))
        self.rom_dir.set(folder if len(folder) <= 42 else '\u2026' + folder[-41:])
        self.rom_size.set(f'{os.path.getsize(path) / 1048576:.1f} MB')
        self.open_btn.config(text='Change ROM', style='Soft.TButton')

    def meta_tab(self, parent):
        page = ttk.Frame(parent, padding=14)
        card = tk.Frame(page, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=14, pady=14)
        card.pack(fill='x')
        self.meta_badge = tk.Label(card, bg=PANEL, bd=0)
        self.meta_badge.grid(row=0, column=0, rowspan=2, sticky='n')
        ttk.Button(card, text='Change icon', style='Accent.TButton', command=self.change_icon).grid(row=0, column=1, padx=16, sticky='w')
        ttk.Button(card, text='Reset icon', style='Soft.TButton', command=self.reset_icon).grid(row=1, column=1, padx=16, pady=(6, 0), sticky='w')
        tk.Label(card, text=REQUIREMENTS, bg=PANEL, fg=MUTED, font=('Segoe UI', 8), justify='left').grid(row=0, column=2, rowspan=2, sticky='w')
        box = tk.Frame(page, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=14, pady=12)
        box.pack(fill='x', pady=(12, 0))
        tk.Label(box, text='GAME TITLE', bg=PANEL, fg=DARK, font=('Segoe UI', 8, 'bold')).grid(row=0, column=0, sticky='w')
        lang_box = ttk.Combobox(box, textvariable=self.lang, values=LANGS, state='readonly', width=10)
        lang_box.grid(row=0, column=1, sticky='e')
        lang_box.bind('<<ComboboxSelected>>', lambda e: self.show_title())
        self.title_text = tk.Text(box, height=3, width=40, wrap='none', bg='#FFFDF8', fg=BROWN, relief='flat', highlightthickness=1,
                                  highlightbackground=SAND, font=('Segoe UI', 10), padx=8, pady=6)
        self.title_text.grid(row=1, column=0, columnspan=2, pady=(8, 0))
        self.title_text.bind('<KeyRelease>', lambda e: self.refresh_summary())
        ttk.Button(box, text='Apply to all languages', style='Soft.TButton', command=self.apply_all).grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        tk.Label(box, text='INTERNAL NAME (12 CHARACTERS)', bg=PANEL, fg=DARK, font=('Segoe UI', 8, 'bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=(12, 0))
        ttk.Entry(box, textvariable=self.internal, width=18).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
        self.internal.trace_add('write', lambda *_: self.refresh_summary())
        return page

    def keep_title(self):
        self.titles[self.cur] = self.title_text.get('1.0', 'end-1c')

    def apply_all(self):
        self.keep_title()
        for n in LANGS:
            self.titles[n] = self.titles[self.cur]
        self.refresh_summary()

    def show_title(self):
        self.keep_title()
        self.cur = self.lang.get()
        self.title_text.delete('1.0', 'end')
        self.title_text.insert('end', self.titles[self.cur])

    def load_meta(self, data):
        b = u32(data, 0x68)
        self.titles, name = banner_read(data)
        self.orig_titles = dict(self.titles)
        self.orig_internal = name
        self.orig_icon = (bytes(data[b + 0x20:b + 0x220]), bytes(data[b + 0x220:b + 0x240]))
        self.icon_new = None
        self.cur = self.lang.get()
        self.title_text.delete('1.0', 'end')
        self.title_text.insert('end', self.titles[self.cur])
        self.internal.set(name)
        self.draw_icon(self.orig_icon)

    def draw_icon(self, icon):
        img = tk.PhotoImage(master=self, width=32, height=32)
        for y, row in enumerate(icon_grid(*icon)):
            img.put('{' + ' '.join(c or PANEL for c in row) + '}', to=(0, y))
        self.meta_img = img.zoom(2)
        self.meta_badge.config(image=self.meta_img)

    def read_pixels(self, path):
        img = tk.PhotoImage(master=self, file=path)
        k = (max(img.width(), img.height()) + 31) // 32
        if k > 1:
            img = img.subsample(k)
        w, h = img.width(), img.height()
        pixels = [(*img.get(x, y), 0 if img.transparency_get(x, y) else 255) for y in range(h) for x in range(w)]
        return fit32(w, h, pixels)

    def change_icon(self):
        path = filedialog.askopenfilename(filetypes=[('Image', '*.png *.gif')])
        if not path:
            return
        try:
            icon = quantize(self.read_pixels(path))
        except Exception as e:
            messagebox.showerror('Icon', str(e))
            return
        self.icon_new = icon
        self.draw_icon(icon)
        self.refresh_summary()

    def reset_icon(self):
        self.icon_new = None
        self.draw_icon(self.orig_icon)
        self.refresh_summary()

    def meta_cfg(self):
        self.keep_title()
        cfg = {}
        titles = {n: t for n, t in self.titles.items() if t != self.orig_titles[n]}
        if titles:
            cfg['titles'] = titles
        if self.icon_new:
            cfg['icon'] = self.icon_new
        name = self.internal.get().strip()
        if name != self.orig_internal:
            if len(name) > 12 or not name.isascii():
                raise ValueError('Internal name: 12 ASCII characters max.')
            cfg['internal'] = name
        return cfg

    def refresh_summary(self):
        if self.rom is None:
            self.sum_meta.set('Unchanged')
        else:
            try:
                names = {'titles': 'Title', 'icon': 'Icon', 'internal': 'Name'}
                self.sum_meta.set(', '.join(names[k] for k in self.meta_cfg()) or 'Unchanged')
            except ValueError as e:
                self.sum_meta.set(str(e))
        code = self.code()
        mode = 'whole units' if self.whole.get() or not cents_ok(code, self.rates.get(code, 0)) else 'with cents'
        self.sum_currency.set(f'{code}  {self.symbol.get()}  ·  {mode}' if code else 'unavailable')
        self.sum_keyboard.set('Default order' if self.order == KEYBOARDS else '  \u203a  '.join(self.order))

    def style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TFrame', background=BG)
        s.configure('TLabel', background=BG, foreground=BROWN)
        s.configure('TCheckbutton', background=BG, foreground=BROWN)
        s.map('TCheckbutton', background=[('active', BG)])
        s.configure('TLabelframe', background=BG, bordercolor=SAND)
        s.configure('TLabelframe.Label', background=BG, foreground=DARK, font=('Segoe UI', 9, 'bold'))
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=SAND, foreground=BROWN, padding=(14, 6), font=('Segoe UI', 10))
        s.map('TNotebook.Tab', background=[('selected', ORANGE)], foreground=[('selected', 'white')])
        s.configure('TCombobox', fieldbackground=PANEL, background=SAND)
        s.configure('Accent.TButton', background=ORANGE, foreground='white', padding=(18, 6), font=('Segoe UI', 10, 'bold'), borderwidth=0)
        s.map('Accent.TButton', background=[('active', DARK), ('disabled', SAND)], foreground=[('disabled', '#B9A07A')])
        s.configure('Big.TButton', background=ORANGE, foreground='white', padding=(18, 11), font=('Segoe UI', 11, 'bold'), borderwidth=0)
        s.map('Big.TButton', background=[('active', DARK), ('disabled', SAND)], foreground=[('disabled', '#B9A07A')])
        s.configure('Soft.TButton', background=SAND, foreground=BROWN, padding=(14, 6), borderwidth=0)
        s.map('Soft.TButton', background=[('active', '#EFCB8F')])

    def currency_tab(self, parent):
        page = ttk.Frame(parent, padding=14)
        box = ttk.Labelframe(page, text='Currency', padding=12)
        box.pack(fill='x', pady=(10, 0))
        combo = ttk.Combobox(box, textvariable=self.choice, values=self.names, state='readonly', width=40)
        combo.grid(row=0, column=0, columnspan=3, sticky='w')
        combo.bind('<<ComboboxSelected>>', lambda e: self.pick())
        ttk.Label(box, text='Symbol').grid(row=1, column=0, sticky='w', pady=(10, 0))
        entry = ttk.Entry(box, textvariable=self.symbol, width=4, validate='key', validatecommand=(self.register(lambda s: len(s) <= 1), '%P'))
        entry.grid(row=1, column=1, sticky='w', pady=(10, 0))
        entry.bind('<FocusOut>', lambda e: self.symbol.get() or self.reset())
        ttk.Button(box, text='Reset', style='Soft.TButton', command=self.reset).grid(row=1, column=2, sticky='w', pady=(10, 0))
        ttk.Label(box, textvariable=self.info, foreground=DARK).grid(row=2, column=0, columnspan=3, sticky='w', pady=(10, 0))
        self.round_cb = ttk.Checkbutton(box, text='Round prices to whole units', variable=self.whole, command=self.refresh_summary)
        self.round_cb.grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))
        return page

    def keyboard_tab(self, parent):
        page = ttk.Frame(parent, padding=14)
        box = ttk.Labelframe(page, text='Tab order, top to bottom', padding=12)
        box.pack(fill='x', pady=(10, 0))
        self.rows = ttk.Frame(box)
        self.rows.pack(anchor='w')
        ttk.Button(box, text='Reset order', style='Soft.TButton', command=self.reset_order).pack(anchor='w', pady=(8, 0))
        return page

    def draw_order(self):
        for w in self.rows.winfo_children():
            w.destroy()
        for i, name in enumerate(self.order):
            row = ttk.Frame(self.rows)
            row.pack(fill='x', pady=2)
            holder = tk.Frame(row, width=54, height=54, bg=ORANGE)
            holder.pack_propagate(False)
            holder.pack(side='left')
            tk.Label(holder, image=self.icons[name], bg=ORANGE, bd=0).place(relx=0.5, rely=0.5, anchor='center')
            ttk.Label(row, text=name, width=12).pack(side='left', padx=10)
            ttk.Button(row, text='▲', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, -1)).pack(side='left', padx=(0, 4))
            ttk.Button(row, text='▼', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, 1)).pack(side='left')

    def move(self, i, step):
        j = i + step
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self.draw_order()
            self.refresh_summary()

    def reset_order(self):
        self.order = list(KEYBOARDS)
        self.draw_order()
        self.refresh_summary()

    def load_icons(self, data):
        icons = {}
        for name, rows in kb_pixels(data).items():
            img = tk.PhotoImage(master=self, width=16, height=16)
            for y, row in enumerate(rows):
                img.put('{' + ' '.join(c or ORANGE for c in row) + '}', to=(0, y))
            icons[name] = img.zoom(3)
        return icons

    def code(self):
        return self.choice.get().split()[0] if self.choice.get() else ''

    def pick(self):
        code = self.code()
        if not code:
            return
        self.symbol.set(SYMBOL[code][0])
        rate = self.rates.get(code)
        self.info.set(f'1 {code} = {1 / rate:,.2f} JPY' if rate else '')
        self.sync_round()
        if rate:
            scale = rate if self.whole.get() else rate * 100
            if T2_MAX * scale > T2_MASK:
                self.info.set(self.info.get() + f'  ·  prices above {T2_MASK / scale:,.0f} JPY are capped')
        self.refresh_summary()

    def sync_round(self):
        code = self.code()
        rate = self.rates.get(code)
        free = bool(rate) and cents_ok(code, rate)
        if not free:
            self.whole.set(True)
        elif self.round_cb.instate(['disabled']):
            self.whole.set(False)
        self.round_cb.state(['!disabled'] if free else ['disabled'])

    def reset(self):
        self.symbol.set(SYMBOL[self.code()][0])
        self.refresh_summary()

    def open_rom(self):
        path = filedialog.askopenfilename(filetypes=[('Nintendo DS ROM', '*.nds')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                data = f.read()
            icons = self.load_icons(data)
        except Exception as e:
            messagebox.showerror('Not a Tomodachi ROM', str(e))
            return
        self.rom = path
        self.icons = icons
        self.show_rom(path, data)
        self.load_meta(data)
        self.status.config(text='')
        self.draw_order()
        self.lock()

    def log(self, text):
        self.status.config(text=text)
        self.update()

    def run(self):
        code, sym = self.code(), self.symbol.get()
        if not code:
            messagebox.showerror('Rates', 'No exchange rates: check the network.')
            return
        cfg = {'currency': {'rate': self.rates[code], 'code': code, 'sym': sym, 'whole': self.whole.get()}}
        if self.order != KEYBOARDS:
            cfg['keyboard'] = list(self.order)
        try:
            meta_cfg = self.meta_cfg()
        except ValueError as e:
            messagebox.showerror('Meta', str(e))
            return
        if meta_cfg:
            cfg['meta'] = meta_cfg
        out = filedialog.asksaveasfilename(defaultextension='.nds', initialfile='tomodachi_patched.nds')
        if not out:
            return
        try:
            with open(self.rom, 'rb') as f:
                result = patch(f.read(), cfg, self.log)
            with open(out, 'wb') as f:
                f.write(result)
            self.log('Done')
        except Exception as e:
            self.log('')
            messagebox.showerror('Patch failed', str(e))


if __name__ == '__main__':
    App().mainloop()
