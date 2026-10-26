"""ARM code that converts prices when they are displayed."""
import struct


def arm_imm(v):
    for rot in range(0, 32, 2):
        r = ((v << rot) | (v >> (32 - rot))) & 0xFFFFFFFF if rot else v
        if r < 256:
            return (rot // 2 << 8) | r
    raise ValueError(v)


def branch(src, dst, link):
    return struct.pack('<I', (0xEB000000 if link else 0xEA000000) | (((dst - src - 8) >> 2) & 0xFFFFFF))


def thunk(addr, target, rate):
    shift = 32
    while round(rate * 2 ** shift) >= 2 ** 32:
        shift -= 1
    code = [0xE92D100E, 0xE1A0C000, 0, 0xE0832190, 0xE2922000 | arm_imm(1 << (shift - 1)), 0xE2A33000]
    code += [0xE1A00003] if shift == 32 else [0xE1A00022 + (shift << 7), 0xE1800003 | ((32 - shift) << 7)]
    code += [0xE3500000, 0x1A000001, 0xE35C0000, 0x13A00001, 0xE8BD100E]
    code[2] = 0xE59F1000 | (4 * len(code) + 4 - 16)
    body = b''.join(struct.pack('<I', w) for w in code)
    body += branch(addr + len(body), target, False)
    return body + struct.pack('<I', round(rate * 2 ** shift))


CENTS = bytes.fromhex(
    'fe402de90040a0e1d8509fe5940586e0010590e20060a6e2a00ba0e1860480e1000050e30100001a000054e30100a013'
    'b4709fe5905786e0a662a0e16430a0e3960305e0057040e008d04de228509de500508de504708de50600a0e108109de5'
    '0c209de510309de5e4ffffeb08109de504709de50120a0e1b030d2e1000053e302208212fbffff1a025042e2b030d5e1'
    '58409fe5040053e10520a001cd30a0e3970305e0a555a0e10a30a0e3950306e0066047e038309fe5035085e0036086e0'
    '2e70a0e3b070c2e1b250c2e1b460c2e10030a0e3b630c2e1b640c201b830c20108d08de2fe80bde8000000321f85eb51'
    'e5ff000010ff0000')


def cents_thunk(addr, target, rate):
    if rate * 100 * 9999999 >= 2 ** 32:
        raise RuntimeError('cents not available for this currency')
    blob = bytearray(CENTS)
    struct.pack_into('<I', blob, 232, round(rate * 100 * 2 ** 23))
    struct.pack_into('<I', blob, 104, 0xEB000000 | (((target - (addr + 104 + 8)) >> 2) & 0xFFFFFF))
    return bytes(blob)
