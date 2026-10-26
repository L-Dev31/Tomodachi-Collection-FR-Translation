"""IMA ADPCM codec."""
import struct


IMA_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]


IMA_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]


def ima_decode(data):
    pred, idx = struct.unpack_from('<hH', data, 0)
    idx = min(idx, 88)
    out = [pred]
    for b in data[4:]:
        for nib in (b & 15, b >> 4):
            step = IMA_STEP[idx]
            diff = step >> 3
            if nib & 1:
                diff += step >> 2
            if nib & 2:
                diff += step >> 1
            if nib & 4:
                diff += step
            pred = max(-32768, min(32767, pred - diff if nib & 8 else pred + diff))
            idx = max(0, min(88, idx + IMA_INDEX[nib & 7]))
            out.append(pred)
    return out


def ima_encode(pcm):
    """pcm: list of int16. Returns bytes: 4 byte header then nibbles, padded to a multiple of 4."""
    pred, idx = (pcm[0] if pcm else 0), 0
    out = bytearray(struct.pack('<hH', pred, idx))
    nibs = []
    for s in pcm[1:]:
        step = IMA_STEP[idx]
        d = s - pred
        nib = 8 if d < 0 else 0
        d = abs(d)
        if d >= step:
            nib |= 4
            d -= step
        if d >= step >> 1:
            nib |= 2
            d -= step >> 1
        if d >= step >> 2:
            nib |= 1
        diff = step >> 3
        if nib & 1:
            diff += step >> 2
        if nib & 2:
            diff += step >> 1
        if nib & 4:
            diff += step
        pred = max(-32768, min(32767, pred - diff if nib & 8 else pred + diff))
        idx = max(0, min(88, idx + IMA_INDEX[nib & 7]))
        nibs.append(nib)
    if len(nibs) % 2:
        nibs.append(0)
    for i in range(0, len(nibs), 2):
        out.append(nibs[i] | nibs[i + 1] << 4)
    while len(out) % 4:
        out.append(0)
    return bytes(out)
