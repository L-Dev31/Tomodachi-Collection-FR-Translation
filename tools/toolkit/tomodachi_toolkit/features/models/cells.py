"""A number of an animation file that can be changed in place: where it is, how it is stored and how much one step of it is worth."""
import struct

LIMITS = {'h': (-0x8000, 0x7FFF), 'i': (-0x80000000, 0x7FFFFFFF), 'H': (0, 0xFFFF), 'B': (0, 0xFF)}
SIZES = {'h': 2, 'i': 4, 'H': 2, 'B': 1}


class Cell:
    """off: where it is in the file; fmt: how it is stored (struct letter); scale: stored value = number * scale; inverse: a scale of a
    skeleton is followed by its inverse, which is kept right; bit: the number is one bit of the byte at off."""
    __slots__ = ('off', 'fmt', 'scale', 'inverse', 'bit')

    def __init__(self, off, fmt, scale=1, inverse=False, bit=None):
        self.off, self.fmt, self.scale, self.inverse, self.bit = off, fmt, scale, inverse, bit

    @property
    def end(self):
        """The first byte after what the cell uses."""
        return self.off + SIZES[self.fmt] * (2 if self.inverse else 1)

    def get(self, b):
        if self.bit is not None:
            return (b[self.off] >> self.bit) & 1
        return struct.unpack_from('<' + self.fmt, b, self.off)[0] / self.scale

    def put(self, b, value):
        """Writes a number into b (a bytearray). Raises ValueError when it does not fit."""
        if self.bit is not None:
            b[self.off] = (b[self.off] & ~(1 << self.bit) & 0xFF) | ((1 if value else 0) << self.bit)
            return
        lo, hi = LIMITS[self.fmt]
        raw = round(value * self.scale)
        if not lo <= raw <= hi:
            raise ValueError(f'The number must be between {lo / self.scale:g} and {hi / self.scale:g}.')
        struct.pack_into('<' + self.fmt, b, self.off, raw)
        if self.inverse:
            inv = round(self.scale * self.scale / raw) if raw else 0
            struct.pack_into('<' + self.fmt, b, self.off + SIZES[self.fmt], max(lo, min(hi, inv)))
