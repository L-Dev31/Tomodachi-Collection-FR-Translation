"""WAV files and resampling."""
import struct
import sys
from array import array


def pcm_bytes(pcm):
    """16 bit little endian bytes of samples: a list of numbers, or an array of 'h' (what the synthesizer makes)."""
    if isinstance(pcm, array) and pcm.typecode == 'h':
        if sys.byteorder == 'big':
            pcm = array('h', pcm)
            pcm.byteswap()
        return pcm.tobytes()
    return struct.pack('<%dh' % len(pcm), *pcm)


def wav_write(rate, pcm):
    data = pcm_bytes(pcm)
    return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data


def wav_read(b):
    b = bytes(b)
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('Not a WAV file')
    p, fmt, data = 12, None, None
    cues, smpl = [], None
    while p + 8 <= len(b):
        tag, n = b[p:p + 4], struct.unpack_from('<I', b, p + 4)[0]
        if tag == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', b, p + 8)
        elif tag == b'data':
            data = b[p + 8:p + 8 + n]
        elif tag == b'cue ':
            # cue points
            num = struct.unpack_from('<I', b, p + 8)[0]
            for i in range(num):
                off = p + 12 + 24 * i
                if off + 24 <= len(b):
                    cues.append(struct.unpack_from('<IIIII', b, off)[3])
        elif tag == b'smpl':
            # sample chunk
            if n >= 60:
                smpl = {
                    'loops': struct.unpack_from('<I', b, p + 8 + 28)[0],
                    'loop_start': struct.unpack_from('<I', b, p + 8 + 36)[0] if n >= 44 else None,
                    'loop_end': struct.unpack_from('<I', b, p + 8 + 40)[0] if n >= 48 else None,
                }
        p += 8 + n + (n & 1)
    if not fmt or data is None:
        raise ValueError('Broken WAV file')
    tag, ch, rate, _, _, bits = fmt
    if tag not in (1, 3, 0xFFFE) or ch < 1 or bits not in (8, 16, 24, 32):
        raise ValueError('Unsupported WAV format (use 8, 16, 24 or 32 bit PCM)')
    width = bits // 8
    count = len(data) // (width * ch)
    out = []
    for i in range(count):
        tot = 0
        for c in range(ch):
            o = (i * ch + c) * width
            if tag == 3 and bits == 32:
                v = struct.unpack_from('<f', data, o)[0] * 32767
            elif bits == 8:
                v = (data[o] - 128) << 8
            elif bits == 16:
                v = struct.unpack_from('<h', data, o)[0]
            elif bits == 24:
                v = int.from_bytes(data[o:o + 3], 'little', signed=True) >> 8
            else:
                v = struct.unpack_from('<i', data, o)[0] >> 16
            tot += v
        out.append(max(-32768, min(32767, int(tot / ch))))
    loop = None
    if smpl and smpl['loops'] > 0 and smpl['loop_start'] is not None and smpl['loop_end'] is not None:
        loop = (smpl['loop_start'], smpl['loop_end'] + 1)
    elif cues and len(cues) >= 2:
        loop = (cues[0], cues[1])
    elif cues and len(cues) == 1:
        loop = (cues[0], len(out))
    return rate, out, loop


def resample(pcm, src, dst):
    if src == dst or len(pcm) < 2:
        return list(pcm)
    n = max(2, int(len(pcm) * dst / src))
    step = (len(pcm) - 1) / (n - 1)
    out = []
    for i in range(n):
        x = i * step
        j = int(x)
        f = x - j
        a = pcm[j]
        b = pcm[min(j + 1, len(pcm) - 1)]
        out.append(int(a + (b - a) * f))
    return out
