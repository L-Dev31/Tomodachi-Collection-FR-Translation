import struct

import toolkit


def test_thunk_math():
    for rate in (0.0056, 1.0, 150.0):
        code = toolkit.thunk(0, toolkit.FMT, rate)
        words = [struct.unpack_from('<I', code, i)[0] for i in range(0, len(code), 4)]
        imm = words[4] & 0xFFF
        half = (imm & 0xFF) << (32 - (imm >> 8) * 2) & 0xFFFFFFFF if imm >> 8 else imm
        for value in (0, 89, 400, 6800, 9100):
            out = max(1, (value * words[-1] + half) >> half.bit_length()) if value else 0
            assert abs(out - toolkit.convert(value, rate)) <= 1


def test_icon():
    pixels = [(255, 0, 0, 255)] * 512 + [(0, 0, 0, 0)] * 512
    grid = toolkit.icon_grid(*toolkit.quantize(pixels))
    assert grid[0][0] == '#ff0000' and grid[31][31] is None


def test_fit():
    out = toolkit.fit32(48, 24, [(255, 0, 0, 255)] * (48 * 24))
    assert len(out) == 1024 and out[0] == (0, 0, 0, 0) and out[8 * 32] == (255, 0, 0, 255) and out[31 * 32] == (0, 0, 0, 0)


def test_cents_rule():
    assert not toolkit.cents_ok('KRW', 9.2) and not toolkit.cents_ok('IDR', 100.0)
    assert toolkit.cents_ok('EUR', 0.0061) and not toolkit.cents_ok('ARS', 9.6)


def test_tables():
    base = 0x02000000
    arm9 = bytearray(0x20F7000 - base)
    struct.pack_into('<I', arm9, toolkit.T1 - base, 250 | 5 << 24)
    struct.pack_into('<I', arm9, toolkit.T2 - base, 0x800000 | 990000)
    toolkit.convert_tables(arm9, 0.5, lambda s: None)
    assert toolkit.u32(arm9, toolkit.T1 - base) == 5 << 24 | 125
    assert toolkit.u32(arm9, toolkit.T2 - base) == 0x800000 | 495000
    struct.pack_into('<I', arm9, toolkit.T2 - base, 0x800000 | 990000)
    toolkit.convert_tables(arm9, 10, lambda s: None)
    assert toolkit.u32(arm9, toolkit.T2 - base) == 0xFFFFFF


if __name__ == '__main__':
    test_thunk_math()
    test_icon()
    test_fit()
    test_cents_rule()
    test_tables()
    print('ok')
