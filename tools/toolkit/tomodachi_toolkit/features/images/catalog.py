"""Finds the editable images of the ROM."""

from ...core.nitro import ncgr_info, nscr_info, ntiles
from ...core.narc import narc_files


IMG_DIRS = ('/Cmn/Kbd/', '/Cmn/Nin/', '/Job/', '/News/', '/Pht/', '/Scn/')


def img_items(path, d):
    try:
        subs = narc_files(d)
    except Exception:
        return []
    pals = [i for i, f in enumerate(subs) if f[:4] == b'RLCN']
    ncgrs = [i for i, f in enumerate(subs) if f[:4] == b'RGCN']
    out = []
    for i in ncgrs:
        try:
            info = ncgr_info(subs[i])
        except Exception:
            continue
        n = ntiles(info)
        scrs = []
        for j, f in enumerate(subs):
            if f[:4] == b'RCSN':
                try:
                    s = nscr_info(f)
                except Exception:
                    continue
                if s['cells'] and max(c & 1023 for c in s['cells']) < n and s['w'] % 8 == 0:
                    scrs.append((j, s['w'], s['h']))
        base = path.rsplit('/', 1)[1]
        base = base[:-7] if base.endswith('_LZ.bin') else base
        out.append({'path': path, 'idx': i, 'name': base + (f'#{i}' if len(ncgrs) > 1 else ''), 'group': path.rsplit('/', 1)[0].strip('/'),
                    'pals': pals, 'scrs': scrs, 'tw': info['tw'] if info['tw'] > 0 else 0, 'tiles': n, 'bits': info['bits']})
    return out
