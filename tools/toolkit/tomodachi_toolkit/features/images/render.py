"""Draw tile sheets and screens to RGBA and encode RGBA back to tiles."""

from ...core.nitro import ncgr_info, ntiles, pal_rgba, put_tile, tile_pixels


def render_sheet(f, cols, bank, wt):
    info = ncgr_info(f)
    n = ntiles(info)
    ht = (n + wt - 1) // wt
    w, h = wt * 8, ht * 8
    out = bytearray(w * h * 4)
    for t in range(n):
        px = tile_pixels(f, info, t)
        tx, ty = (t % wt) * 8, (t // wt) * 8
        for i, v in enumerate(px):
            o = ((ty + i // 8) * w + tx + i % 8) * 4
            out[o:o + 4] = bytes(pal_rgba(cols, bank, info['bits'], v))
    return w, h, bytes(out)


def render_screen(f, cols, scr):
    info = ncgr_info(f)
    w, h = scr['w'], scr['h']
    wt = w // 8
    out = bytearray(w * h * 4)
    for c, cell in enumerate(scr['cells'][:wt * (h // 8)]):
        t, hf, vf, bank = cell & 1023, cell >> 10 & 1, cell >> 11 & 1, cell >> 12
        px = tile_pixels(f, info, t)
        tx, ty = (c % wt) * 8, (c // wt) * 8
        for i in range(64):
            x, y = i % 8, i // 8
            v = px[(y ^ 7 if vf else y) * 8 + (x ^ 7 if hf else x)]
            o = ((ty + y) * w + tx + x) * 4
            out[o:o + 4] = bytes(pal_rgba(cols, bank, info['bits'], v))
    return w, h, bytes(out)


def nearest(cols, bank, bits, rgba):
    if rgba[3] < 128:
        return 0, 0
    base = bank * 16 if bits == 4 else 0
    best, bd = 0, 1 << 30
    for i in range(min(16 if bits == 4 else 256, len(cols) - base)):
        c = cols[base + i]
        d = (c[0] - rgba[0]) ** 2 + (c[1] - rgba[1]) ** 2 + (c[2] - rgba[2]) ** 2 + (i == 0)
        if d < bd:
            best, bd = i, d
    return best, bd


def encode_sheet(f, cols, bank, wt, w, h, rgba):
    info = ncgr_info(f)
    n = ntiles(info)
    want = (wt * 8, ((n + wt - 1) // wt) * 8)
    if (w, h) != want:
        raise ValueError(f'Image must be {want[0]} x {want[1]} pixels (it is {w} x {h})')
    buf, cache, snapped = bytearray(f), {}, 0
    for t in range(n):
        tx, ty = (t % wt) * 8, (t // wt) * 8
        idx = []
        for i in range(64):
            o = ((ty + i // 8) * w + tx + i % 8) * 4
            px = bytes(rgba[o:o + 4])
            if px not in cache:
                cache[px] = nearest(cols, bank, info['bits'], px)
            idx.append(cache[px][0])
            snapped += cache[px][1] > 64
        put_tile(buf, info, t, idx)
    return bytes(buf), 0, snapped


def encode_screen(f, cols, scr, w, h, rgba):
    info = ncgr_info(f)
    if (w, h) != (scr['w'], scr['h']):
        raise ValueError(f'Image must be {scr["w"]} x {scr["h"]} pixels (it is {w} x {h})')
    wt = w // 8
    buf, seen, cache, clash, snapped = bytearray(f), {}, {}, 0, 0
    for c, cell in enumerate(scr['cells'][:wt * (h // 8)]):
        t, hf, vf, bank = cell & 1023, cell >> 10 & 1, cell >> 11 & 1, cell >> 12
        tx, ty = (c % wt) * 8, (c // wt) * 8
        idx = [0] * 64
        for i in range(64):
            x, y = i % 8, i // 8
            o = ((ty + y) * w + tx + x) * 4
            key = (bytes(rgba[o:o + 4]), bank)
            if key not in cache:
                cache[key] = nearest(cols, bank, info['bits'], key[0])
            idx[(y ^ 7 if vf else y) * 8 + (x ^ 7 if hf else x)] = cache[key][0]
            snapped += cache[key][1] > 64
        if t in seen:
            clash += seen[t] != idx
            continue
        seen[t] = idx
        put_tile(buf, info, t, idx)
    return bytes(buf), clash, snapped


def sheet_indices(f, wt):
    info = ncgr_info(f)
    n = ntiles(info)
    w, h = wt * 8, ((n + wt - 1) // wt) * 8
    out = bytearray(w * h)
    for t in range(n):
        for i, v in enumerate(tile_pixels(f, info, t)):
            out[((t // wt) * 8 + i // 8) * w + (t % wt) * 8 + i % 8] = v
    return w, h, bytes(out)
