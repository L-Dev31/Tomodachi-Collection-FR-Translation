"""Nintendo DS ROM image: file table, ARM9, overlays, appending files."""
import struct

from .compression import blz
from .binary import crc16, u16, u32


MARK = bytes.fromhex('2106c0dedec00621')


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
