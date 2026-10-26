"""Little endian readers and the CRC-16 used by the DS header."""
import struct


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def crc16(b, s, e):
    crc = 0xFFFF
    for i in range(s, e):
        crc ^= b[i]
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc
