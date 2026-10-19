import struct

import prices


def test_thunk_math():
    for rate in (0.0056, 1.0, 150.0):
        code = prices.thunk(0, prices.FMT, rate)
        words = [struct.unpack_from('<I', code, i)[0] for i in range(0, len(code), 4)]
        imm = words[4] & 0xFFF
        half = (imm & 0xFF) << (32 - (imm >> 8) * 2) & 0xFFFFFFFF if imm >> 8 else imm
        for value in (0, 89, 400, 6800, 9100):
            out = max(1, (value * words[-1] + half) >> half.bit_length()) if value else 0
            assert abs(out - prices.convert(value, rate)) <= 1


if __name__ == '__main__':
    test_thunk_math()
    print('ok')
