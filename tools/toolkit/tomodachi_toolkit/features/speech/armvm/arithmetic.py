"""Saturating arithmetic and register shifts."""

from .constants import MASK32


def to_s32(x):
    return (x ^ 0x80000000) - 0x80000000


def saturate(x):
    return max(-0x80000000, min(0x7FFFFFFF, x))


def qadd(a, b):
    return saturate(to_s32(a) + to_s32(b)) & MASK32


def qsub(a, b):
    return saturate(to_s32(a) - to_s32(b)) & MASK32


def qdadd(a, b):
    return saturate(to_s32(a) + saturate(2 * to_s32(b))) & MASK32


def qdsub(a, b):
    return saturate(to_s32(a) - saturate(2 * to_s32(b))) & MASK32


def shift_reg(kind, v, a):
    """Shift by a register amount (its low byte). Returns (value, carry or None when unchanged)."""
    if a == 0:
        return v, None
    if kind == 0:
        if a < 32:
            return (v << a) & MASK32, (v >> (32 - a)) & 1
        return 0, (v & 1) if a == 32 else 0
    if kind == 1:
        if a < 32:
            return v >> a, (v >> (a - 1)) & 1
        return 0, (v >> 31) if a == 32 else 0
    if kind == 2:
        s = to_s32(v)
        if a < 32:
            return (s >> a) & MASK32, (v >> (a - 1)) & 1
        return (MASK32 if s < 0 else 0), v >> 31
    a &= 31
    if a == 0:
        return v, v >> 31
    return ((v >> a) | (v << (32 - a))) & MASK32, (v >> (a - 1)) & 1


def shift_val(kind, v, a):
    return shift_reg(kind, v, a)[0]
