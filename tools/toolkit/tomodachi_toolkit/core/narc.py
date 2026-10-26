"""NARC archives: list, read and rebuild their sub files."""
import struct

from .binary import u16, u32


def narc_offsets(d):
    p = u16(d, 12)
    tbl = {}
    while p < len(d):
        tbl[bytes(d[p:p + 4])] = p
        p += u32(d, p + 4)
    fat, gm = tbl[b'BTAF'], tbl[b'GMIF']
    return [(u32(d, fat + 12 + i * 8) + gm + 8) for i in range(u16(d, fat + 8))]


def narc_parts(d):
    p = u16(d, 12)
    tbl = {}
    while p < len(d):
        tbl[bytes(d[p:p + 4])] = p
        p += u32(d, p + 4)
    return tbl


def narc_files(d):
    t = narc_parts(d)
    fat, gm = t[b'BTAF'], t[b'GMIF'] + 8
    return [bytes(d[gm + u32(d, fat + 12 + i * 8):gm + u32(d, fat + 16 + i * 8)]) for i in range(u16(d, fat + 8))]


def narc_name(d):
    p = narc_parts(d)[b'BTNF'] + 16
    return bytes(d[p + 1:p + 1 + (d[p] & 127)]).decode('latin1')


def narc_index(d):
    t = narc_parts(d)
    fat, gm = t[b'BTAF'], t[b'GMIF'] + 8
    return [(gm + u32(d, fat + 12 + i * 8), gm + u32(d, fat + 16 + i * 8)) for i in range(u16(d, fat + 8))]


def narc_set(d, repl):
    """The archive d with some sub files replaced ({index: bytes}). Same size files are patched in place;
    any other size rebuilds the file table (see narc_replace)."""
    idx = narc_index(d)
    if any(len(f) != idx[i][1] - idx[i][0] for i, f in repl.items()):
        return narc_replace(d, repl)
    d = bytearray(d)
    for i, f in repl.items():
        s, e = idx[i]
        d[s:e] = f
    return bytes(d)


def narc_replace(d, repl):
    """The archive d with some files replaced by files of any size ({index: bytes}). The names block is kept."""
    parts = narc_parts(d)
    files = narc_files(d)
    for i, f in repl.items():
        files[i] = bytes(f)
    names = bytes(d[parts[b'BTNF']:parts[b'BTNF'] + u32(d, parts[b'BTNF'] + 4)])
    gm, ents = bytearray(), []
    for f in files:
        gm += b'\0' * (-len(gm) % 4)
        ents.append((len(gm), len(gm) + len(f)))
        gm += f
    gm += b'\0' * (-len(gm) % 4)
    fat = b'BTAF' + struct.pack('<IHH', 12 + 8 * len(files), len(files), 0) + b''.join(struct.pack('<II', s, e) for s, e in ents)
    gmif = b'GMIF' + struct.pack('<I', 8 + len(gm)) + bytes(gm)
    return b'NARC\xfe\xff\x00\x01' + struct.pack('<IHH', 16 + len(fat) + len(names) + len(gmif), 16, 3) + fat + names + gmif
