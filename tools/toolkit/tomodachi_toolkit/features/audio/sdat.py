"""SDAT sound archive: waves, banks, rebuild."""
import struct

from ...core.binary import u32
from .adpcm import ima_decode, ima_encode


def sdat_parse(sd):
    so, ss, io, isz, fo, fsz, lo, lsz = struct.unpack_from('<8I', sd, 0x10)
    cs = lambda o: sd[so + o:sd.index(b'\0', so + o)].decode('latin1')
    names = {}
    for k, o in enumerate(struct.unpack_from('<8I', sd, so + 8)):
        if not o:
            continue
        n = u32(sd, so + o)
        names[k] = [cs(u32(sd, so + o + 4 + 4 * i)) if u32(sd, so + o + 4 + 4 * i) else None for i in range(n)]
    infos = {}
    for k, o in enumerate(struct.unpack_from('<8I', sd, io + 8)):
        if not o:
            continue
        n = u32(sd, io + o)
        infos[k] = [io + u32(sd, io + o + 4 + 4 * i) if u32(sd, io + o + 4 + 4 * i) else None for i in range(n)]
    n = u32(sd, fo + 8)
    fat = [struct.unpack_from('<II', sd, fo + 12 + 16 * i) for i in range(n)]
    return names, infos, fat


def sdat_file(sd, fat, fid):
    o, n = fat[fid & 0xFFFFFF]
    return sd[o:o + n]


def sdat_rebuild(sd, repl):
    """repl: {fid: new file bytes}. Returns a new SDAT with the FAT and FILE blocks rebuilt."""
    so, ss, io, isz, fo, fsz, lo, lsz = struct.unpack_from('<8I', sd, 0x10)
    fat = sdat_parse(sd)[2]
    if all(len(b) <= fat[i][1] for i, b in repl.items()):
        out = bytearray(sd)
        for i, b in repl.items():
            out[fat[i][0]:fat[i][0] + len(b)] = b
        return bytes(out)
    files = [repl.get(i, sd[o:o + n]) for i, (o, n) in enumerate(fat)]
    pos, ents, body = lo + 16, [], bytearray()
    for f in files:
        pos = (pos + 31) & ~31
        body += b'\0' * (pos - (lo + 16) - len(body))
        ents.append((pos, len(f)))
        body += f
        pos += len(f)
    fsize = (16 + len(body) + 3) & ~3
    out = bytearray(sd[:lo])
    for i, (o, n) in enumerate(ents):
        struct.pack_into('<II', out, fo + 12 + 16 * i, o, n)
    out += b'FILE' + struct.pack('<III', fsize, len(files), 0) + body
    out += b'\0' * (lo + fsize - len(out))
    struct.pack_into('<I', out, 8, len(out))
    struct.pack_into('<I', out, 0x2C, fsize)
    return bytes(out)


def swar_waves(f):
    n = u32(f, 0x38)
    offs = [u32(f, 0x3C + 4 * i) for i in range(n)]
    out = []
    for i, o in enumerate(offs):
        enc, loop, rate, tm, lp, ln = struct.unpack_from('<BBHHHI', f, o)
        end = offs[i + 1] if i + 1 < n else len(f)
        out.append({'enc': enc, 'loop': loop, 'rate': rate, 'lp': lp, 'ln': ln, 'off': o, 'data': o + 12, 'end': end})
    return out


def wave_pcm(f, w):
    d = f[w['data']:w['data'] + (w['lp'] + w['ln']) * 4]
    if w['enc'] == 2:
        return ima_decode(d)
    if w['enc'] == 1:
        return list(struct.unpack('<%dh' % (len(d) // 2), d[:len(d) // 2 * 2]))
    return [(x - 256 if x > 127 else x) << 8 for x in d]


def wave_length(w):
    """Number of samples of a wave, worked out from its size (no decoding)."""
    words = w['lp'] + w['ln']
    if w['enc'] == 2:
        return (words * 4 - 4) * 2 + 1
    return words * 2 if w['enc'] == 1 else words * 4


def wave_encode(w, rate, pcm):
    """Build a SWAV (header + data) replacing wave w, keeping its encoding and loop flag."""
    if w['enc'] == 2:
        data = ima_encode(pcm)
    elif w['enc'] == 1:
        data = struct.pack('<%dh' % len(pcm), *pcm)
    else:
        data = bytes((s >> 8) & 255 for s in pcm)
    data += b'\0' * (-len(data) % 4)
    words = len(data) // 4
    old = max(1, w['lp'] + w['ln'])
    lp = 0
    if w['loop']:
        lp = max(1 if w['enc'] == 2 else 0, min(words - 1, round(w['lp'] * words / old)))
    return struct.pack('<BBHHHI', w['enc'], w['loop'], rate, min(65535, 16756991 // max(rate, 1)), lp, words - lp) + data


def swar_build(f, repl):
    """repl: {wave index: new SWAV bytes}. Returns the rebuilt SWAR."""
    waves = swar_waves(f)
    head = bytearray(f[:0x3C + 4 * len(waves)])
    body = bytearray()
    base = len(head)
    for i, w in enumerate(waves):
        struct.pack_into('<I', head, 0x3C + 4 * i, base + len(body))
        body += repl.get(i, f[w['off']:w['end']])
    out = bytearray(head) + body
    if len(out) <= len(f) and not any(len(repl.get(i, b'')) != w['end'] - w['off'] for i, w in enumerate(waves) if i in repl):
        return bytes(out) + f[len(out):]
    struct.pack_into('<I', out, 8, len(out))
    struct.pack_into('<I', out, 0x14, len(out) - 0x10)
    return bytes(out)


def bank_waves(b):
    n = u32(b, 0x38)
    out = {}
    for i in range(n):
        t = b[0x3C + 4 * i]
        off = struct.unpack_from('<H', b, 0x3D + 4 * i)[0]
        ws = set()
        if t == 1:
            ws.add(struct.unpack_from('<H', b, off)[0])
        elif t in (16, 17):
            if t == 16:
                first, cnt = off + 2, b[off + 1] - b[off] + 1
            else:
                first, cnt = off + 8, sum(1 for k in range(8) if b[off + k])
            for k in range(cnt):
                ro = first + k * 12
                if ro + 4 <= len(b) and struct.unpack_from('<H', b, ro)[0] == 1:
                    ws.add(struct.unpack_from('<H', b, ro + 2)[0])
        out[i] = ws
    return out


class Sound:
    """Reads the game's SDAT inside a Rom: the wave archive and which banks use each wave."""

    def __init__(self, rom):
        self.path = '/sound_data.sdat'
        files = rom.files()
        s, e = rom.fat(files[self.path])
        self.sd = bytes(rom.d[s:e])
        self.names, self.infos, self.fat = sdat_parse(self.sd)
        self.swar_fid = u32(self.sd, self.infos[3][0]) & 0xFFFFFF
        self.swar = sdat_file(self.sd, self.fat, self.swar_fid)
        self.waves = swar_waves(self.swar)
        self.banks = {}
        for i, o in enumerate(self.infos[2]):
            if o is None:
                continue
            b = sdat_file(self.sd, self.fat, u32(self.sd, o))
            for ws in bank_waves(b).values():
                for w in ws:
                    self.banks.setdefault(w, [])
                    nm = self.names[2][i]
                    if nm not in self.banks[w]:
                        self.banks[w].append(nm)

    def label(self, i):
        b = self.banks.get(i, [])
        return b[0].replace('BANK_', '').title() if b else 'Unused'
