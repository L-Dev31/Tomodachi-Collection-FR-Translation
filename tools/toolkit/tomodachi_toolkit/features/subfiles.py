"""Replaces sub files inside the NARC archives of the ROM (shared by images and models)."""

from ..core.compression import lz10, lz10c
from ..core.narc import narc_set


def apply_subfiles(rom, new, log, label):
    """new: {path of a NARC in the ROM: {sub file index: new bytes}}. A sub file may change size.
    The archive keeps its compression: LZ10 when it was LZ10, raw otherwise."""
    files = rom.files()
    for path, subs in new.items():
        fid = files[path]
        s, e = rom.fat(fid)
        raw = bytes(rom.d[s:e])
        packed = raw[:1] == b'\x10'
        out = narc_set(lz10(raw) if packed else raw, subs)
        rom.put_file(fid, lz10c(out) if packed else out)
        log(f'{label} {path.rsplit("/", 1)[1]}')
