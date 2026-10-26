"""WAV files and resampling."""
import struct


def wav_write(rate, pcm):
    data = struct.pack('<%dh' % len(pcm), *pcm)
    return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data


def wav_read(b):
    b = bytes(b)
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('Not a WAV file')
    p, fmt, data = 12, None, None
    while p + 8 <= len(b):
        tag, n = b[p:p + 4], struct.unpack_from('<I', b, p + 4)[0]
        if tag == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', b, p + 8)
        elif tag == b'data':
            data = b[p + 8:p + 8 + n]
        p += 8 + n + (n & 1)
    if not fmt or data is None:
        raise ValueError('Broken WAV file')
    tag, ch, rate, _, _, bits = fmt
    if tag not in (1, 3, 0xFFFE) or ch < 1 or bits not in (8, 16, 24, 32):
        raise ValueError('Unsupported WAV format (use 8, 16, 24 or 32 bit PCM)')
    width = bits // 8
    n = len(data) // (width * ch)
    out = []
    for i in range(n):
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
    return rate, out


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
