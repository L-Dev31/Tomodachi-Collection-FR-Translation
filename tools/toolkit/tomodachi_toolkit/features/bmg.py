"""BMG message files of the ROM: list, read and replace."""

from ..core.compression import lz10, lz10c
from ..core.narc import narc_files, narc_name
from ..core.bmg import bmg_narc, bmg_problems


def bmg_list(rom):
    out = {}
    for path, fid in rom.files().items():
        if path.startswith('/Msg/') and path.endswith('_LZ.bin'):
            s, e = rom.fat(fid)
            try:
                d = lz10(bytes(rom.d[s:e]))
                f = narc_files(d)[0]
                out[path] = (narc_name(d), bmg_problems(f))
            except Exception as ex:
                out[path] = (path.rsplit('/', 1)[1], [f'unreadable: {ex}'])
    return out


def bmg_archive(rom, files, path):
    """The archive (NARC, decompressed) the game keeps the message file path in. files is rom.files()."""
    s, e = rom.fat(files[path])
    return lz10(bytes(rom.d[s:e]))


def bmg_put(rom, files, path, archive, f):
    """Stores the message file f in the ROM, in the place of the one held by archive."""
    rom.put_file(files[path], lz10c(bmg_narc(f, archive)))


def apply_bmg(rom, new, log):
    files = rom.files()
    for path, f in new.items():
        bmg_put(rom, files, path, bmg_archive(rom, files, path), f)
        log(f'BMG {path.rsplit("/", 1)[1]}')
