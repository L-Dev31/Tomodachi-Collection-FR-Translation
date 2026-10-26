"""Finds the models of the ROM."""

from ...core.narc import narc_files
from .bmd import bmd_textures


def model_items(path, d):
    try:
        subs = narc_files(d)
    except Exception:
        return []
    out = []
    for i, f in enumerate(subs):
        if f[:4] == b'BMD0':
            try:
                texs, _ = bmd_textures(f)
            except Exception:
                continue
            base = path.rsplit('/', 1)[1]
            base = base[:-7] if base.endswith('_LZ.bin') else base
            out.append({'path': path, 'idx': i, 'name': base, 'group': path.rsplit('/', 1)[0].strip('/'), 'textures': len(texs)})
    return out
