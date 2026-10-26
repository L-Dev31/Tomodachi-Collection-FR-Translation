"""BPS patches (the Flips format): create, read the metadata, apply."""
import struct
import zlib

from .binary import u32


def vint(n):
    out = bytearray()
    while True:
        x = n & 127
        n >>= 7
        if not n:
            out.append(128 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def bps_make(src, tgt, meta=b''):
    src, tgt, meta = bytes(src), bytes(tgt), bytes(meta)
    out = bytearray(b'BPS1') + vint(len(src)) + vint(len(tgt)) + vint(len(meta)) + meta
    n, m, i = len(tgt), min(len(src), len(tgt)), 0
    while i < n:
        j = i
        while j < m:
            if src[j:j + 4096] == tgt[j:j + 4096]:
                j += 4096
                continue
            while j < m and src[j] == tgt[j]:
                j += 1
            break
        j = min(j, m)
        if j > i:
            out += vint((j - i - 1) << 2)
            i = j
            continue
        k = i
        while k < n and not (k < m and src[k:k + 8] == tgt[k:k + 8] and k + 8 <= m):
            k += 1
        out += vint(((k - i - 1) << 2) | 1) + tgt[i:k]
        i = k
    out += struct.pack('<II', zlib.crc32(src), zlib.crc32(tgt))
    return bytes(out) + struct.pack('<I', zlib.crc32(out))


def bps_read(p, o):
    n, shift = 0, 1
    while True:
        x = p[o]
        o += 1
        n += (x & 127) * shift
        if x & 128:
            return n, o
        shift <<= 7
        n += shift


def bps_meta(patch):
    patch = bytes(patch)
    if patch[:4] != b'BPS1' or len(patch) < 19:
        raise ValueError('Not a BPS patch')
    o = 4
    _, o = bps_read(patch, o)
    _, o = bps_read(patch, o)
    n, o = bps_read(patch, o)
    return patch[o:o + n]


def bps_apply(src, patch):
    src, patch = bytes(src), bytes(patch)
    if patch[:4] != b'BPS1' or len(patch) < 19:
        raise ValueError('Not a BPS patch')
    if zlib.crc32(patch[:-4]) != u32(patch, len(patch) - 4):
        raise ValueError('Corrupt patch (checksum)')
    o = 4
    ssize, o = bps_read(patch, o)
    tsize, o = bps_read(patch, o)
    msize, o = bps_read(patch, o)
    o += msize
    if ssize != len(src) or zlib.crc32(src) != u32(patch, len(patch) - 12):
        raise ValueError('This patch is for a different ROM')
    out, end, sp, tp = bytearray(), len(patch) - 12, 0, 0
    while o < end:
        v, o = bps_read(patch, o)
        n, kind = (v >> 2) + 1, v & 3
        if kind == 0:
            out += src[len(out):len(out) + n]
        elif kind == 1:
            out += patch[o:o + n]
            o += n
        else:
            d, o = bps_read(patch, o)
            d = -(d >> 1) if d & 1 else d >> 1
            if kind == 2:
                sp += d
                out += src[sp:sp + n]
                sp += n
            else:
                tp += d
                for _ in range(n):
                    out.append(out[tp])
                    tp += 1
    if len(out) != tsize or zlib.crc32(out) != u32(patch, len(patch) - 8):
        raise ValueError('Patched ROM does not match the expected checksum')
    return bytes(out)
