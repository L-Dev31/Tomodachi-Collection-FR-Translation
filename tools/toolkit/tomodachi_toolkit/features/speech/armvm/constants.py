"""Constants of the ARM interpreter."""


MASK32 = 0xFFFFFFFF


ARM_BASE = 0x02000000


ARM_SIZE = 0x800000


ARM_SENT = 0xFFFF0000


ARM_ALL = frozenset('NZCV')


ARM_NONE = frozenset()


ARM_CREAD = [frozenset(s) for s in ('Z', 'Z', 'C', 'C', 'N', 'N', 'V', 'V', 'CZ', 'CZ', 'NV', 'NV', 'ZNV', 'ZNV', '', 'NZCV')]


ARM_LOGICAL = (0, 1, 8, 9, 12, 13, 14, 15)


ARM_MAXB = 64
