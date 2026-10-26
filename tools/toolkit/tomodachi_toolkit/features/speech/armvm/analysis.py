"""Instruction analysis: flags read and written, block terminators."""

from .constants import ARM_ALL, ARM_CREAD, ARM_LOGICAL, ARM_NONE, MASK32


def flag_rw(w):
    """(flags read, flags defined) by instruction word w (condition included in reads)."""
    cc = w >> 28
    rd = ARM_CREAD[cc]
    t = w >> 25 & 7
    if cc == 15 or t > 1:
        return rd, ARM_NONE
    if t == 0 and w & 0x90 == 0x90:
        if w & 0x60 == 0 and w & 0x01000000 == 0 and w & 0x00100000:
            return rd, frozenset('NZ')
        return rd, ARM_NONE
    op, s = w >> 21 & 15, w >> 20 & 1
    if 8 <= op <= 11 and not s:
        if (w & 0x0FBF0FFF) == 0x010F0000:
            rd = ARM_ALL
        return rd, ARM_NONE
    if op in (5, 6, 7):
        rd = rd | {'C'}
    if t == 0 and not w & 0x10 and (w >> 5 & 3) == 3 and not (w >> 7 & 31):
        rd = rd | {'C'}
    if t == 0 and w & 0x10:
        rd = rd | {'C'}
    if not s:
        return rd, ARM_NONE
    if op in ARM_LOGICAL:
        df = {'N', 'Z'}
        if t == 1:
            if (w >> 8 & 15) != 0:
                df.add('C')
        elif w & 0x10:
            df.add('C')      # shift by register: C is rewritten (or kept), it is also listed as read
        elif (w >> 5 & 3) != 0 or (w >> 7 & 31) != 0:
            df.add('C')
        return rd, frozenset(df)
    return rd, ARM_ALL


def is_term(w):
    """True when the instruction ends a basic block."""
    cc = w >> 28
    if cc == 15:
        return True
    t = w >> 25 & 7
    if t == 5:
        return True
    if t == 0:
        if w & 0x90 == 0x90:
            return False
        if (w & 0x0FFFFFD0) == 0x012FFF10:
            return True
    if t in (0, 1):
        op = w >> 21 & 15
        if 8 <= op <= 11:
            return False
        return (w >> 12 & 15) == 15
    if t in (2, 3):
        return bool(w & (1 << 20)) and (w >> 12 & 15) == 15
    if t == 4:
        return bool(w & (1 << 20)) and bool(w & 0x8000)
    return True


def branch_target(pc, w):
    return (pc + 8 + (((w & 0xFFFFFF) ^ 0x800000) - 0x800000) * 4) & MASK32
