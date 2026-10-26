"""Nintendo LZ10 (type 0x10) and the BLZ (backward LZ) used for the ARM9 and overlays."""

from .binary import u32


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
