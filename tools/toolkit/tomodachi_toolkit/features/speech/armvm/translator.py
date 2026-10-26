"""Translates ARM basic blocks to Python source."""

from .constants import ARM_LOGICAL, MASK32
from .analysis import flag_rw
from .errors import ArmUnsupported


class Blk:
    """Translation state of one basic block."""

    def __init__(self):
        self.lines, self.ind = [], 0
        self.need, self.defined, self.written = set(), set(), set()
        self.fl = None            # None: flags as they were at block entry (locals N Z C V loaded on demand)
        self.use_entry = False
        self.tmp = 0
        self.cdepth = 0
        self.pcx, self.pcmask = None, False

    def emit(self, s):
        self.lines.append('    ' * self.ind + s)

    def t(self, prefix='t'):
        self.tmp += 1
        return f'{prefix}{self.tmp}'

    def rd(self, n, pc):
        if n == 15:
            return str((pc + 8) & MASK32)
        if n not in self.defined:
            self.need.add(n)
        return f'r{n}'

    def wr(self, n, expr):
        if self.cdepth:
            if n not in self.defined:
                self.need.add(n)
        else:
            self.defined.add(n)
        self.written.add(n)
        self.emit(f'r{n} = {expr}')

    # ----- flags: a descriptor tells how N Z C V can be computed from temporaries
    def fx(self, d, f):
        if d is None:
            self.use_entry = True
            return f
        k = d[0]
        if k == 'exp':
            return f
        if k == 'sub':
            _, a, b = d
            if f == 'Z':
                return f'{a} == {b}'
            if f == 'C':
                return f'{a} >= {b}'
            if f == 'N':
                return f'(({a} - {b}) & 0x80000000) != 0'
            return f'((({a} ^ {b}) & ({a} ^ ({a} - {b}))) & 0x80000000) != 0'
        if k == 'add':
            _, a, b, r = d
            if f == 'Z':
                return f'{r} == 0'
            if f == 'C':
                return f'{r} < {a}'
            if f == 'N':
                return f'({r} & 0x80000000) != 0'
            return f'((~({a} ^ {b}) & ({a} ^ {r})) & 0x80000000) != 0'
        _, r, c, prev = d
        if f == 'Z':
            return f'{r} == 0'
        if f == 'N':
            return f'({r} & 0x80000000) != 0'
        if f == 'C':
            return c if c is not None else self.fx(prev, 'C')
        return self.fx(prev, 'V')

    @staticmethod
    def sx(a):
        return str(int(a) ^ 0x80000000) if a.isdigit() else f'({a} ^ 0x80000000)'

    def cond(self, cc):
        d = self.fl
        if cc == 14:
            return 'True'
        if d is not None and d[0] == 'sub':
            _, a, b = d
            sa, sb = self.sx(a), self.sx(b)
            m = {0: f'{a} == {b}', 1: f'{a} != {b}', 2: f'{a} >= {b}', 3: f'{a} < {b}', 8: f'{a} > {b}', 9: f'{a} <= {b}',
                 10: f'{sa} >= {sb}', 11: f'{sa} < {sb}', 12: f'{sa} > {sb}', 13: f'{sa} <= {sb}'}
            if cc in m:
                return m[cc]
        fx = self.fx
        if cc == 0:
            return fx(d, 'Z')
        if cc == 1:
            return f'not ({fx(d, "Z")})'
        if cc == 2:
            return fx(d, 'C')
        if cc == 3:
            return f'not ({fx(d, "C")})'
        if cc == 4:
            return fx(d, 'N')
        if cc == 5:
            return f'not ({fx(d, "N")})'
        if cc == 6:
            return fx(d, 'V')
        if cc == 7:
            return f'not ({fx(d, "V")})'
        if cc == 8:
            return f'({fx(d, "C")}) and not ({fx(d, "Z")})'
        if cc == 9:
            return f'not ({fx(d, "C")}) or ({fx(d, "Z")})'
        n, v = fx(d, 'N'), fx(d, 'V')
        if cc == 10:
            return f'({n}) == ({v})'
        if cc == 11:
            return f'({n}) != ({v})'
        if cc == 12:
            return f'not ({fx(d, "Z")}) and ({n}) == ({v})'
        return f'({fx(d, "Z")}) or ({n}) != ({v})'

    def materialize(self):
        """Make the flags explicit locals N Z C V (so they can be modified conditionally)."""
        d = self.fl
        if d is None:
            self.use_entry = True
        elif d[0] != 'exp':
            n, z, c, v = (self.fx(d, f) for f in 'NZCV')
            self.emit(f'N, Z, C, V = {n}, {z}, {c}, {v}')
        self.fl = ('exp',)

    def carry_in(self):
        return self.fx(self.fl, 'C')

    # ----- operands
    def op2(self, w, pc, need_c):
        """Returns (expression, carry expression or None); expression None means register shift needing carry."""
        if w & (1 << 25):
            imm, rot = w & 0xFF, (w >> 8 & 15) * 2
            val = ((imm >> rot) | (imm << (32 - rot))) & MASK32 if rot else imm
            return str(val), (str(val >> 31) if rot and need_c else None)
        rm, typ = w & 15, w >> 5 & 3
        v = self.rd(rm, pc)
        if w & 0x10:
            rs = self.rd(w >> 8 & 15, pc)
            if need_c:
                return None, (typ, v, rs)
            return f'_shv({typ}, {v}, {rs} & 255)', None
        amt = w >> 7 & 31
        if typ == 0:
            if amt == 0:
                return v, None
            return f'(({v} << {amt}) & 0xFFFFFFFF)', (f'(({v} >> {32 - amt}) & 1)' if need_c else None)
        if typ == 1:
            if amt == 0:
                return '0', (f'({v} >> 31)' if need_c else None)
            return f'({v} >> {amt})', (f'(({v} >> {amt - 1}) & 1)' if need_c else None)
        if typ == 2:
            if amt == 0:
                return f'(0xFFFFFFFF if {v} >> 31 else 0)', (f'({v} >> 31)' if need_c else None)
            return f'(((({v} ^ 0x80000000) - 0x80000000) >> {amt}) & 0xFFFFFFFF)', (f'(({v} >> {amt - 1}) & 1)' if need_c else None)
        if amt == 0:
            c = self.carry_in()
            return f'((({c}) << 31) | ({v} >> 1))', (f'({v} & 1)' if need_c else None)
        return f'((({v} >> {amt}) | ({v} << {32 - amt})) & 0xFFFFFFFF)', (f'(({v} >> {amt - 1}) & 1)' if need_c else None)

    def shifted(self, rm, typ, amt, pc):
        v = self.rd(rm, pc)
        if typ == 0:
            return v if amt == 0 else f'(({v} << {amt}) & 0xFFFFFFFF)'
        if typ == 1:
            return '0' if amt == 0 else f'({v} >> {amt})'
        if typ == 2:
            return f'(0xFFFFFFFF if {v} >> 31 else 0)' if amt == 0 else f'(((({v} ^ 0x80000000) - 0x80000000) >> {amt}) & 0xFFFFFFFF)'
        if amt == 0:
            return f'((({self.carry_in()}) << 31) | ({v} >> 1))'
        return f'((({v} >> {amt}) | ({v} << {32 - amt})) & 0xFFFFFFFF)'

    # ----- data processing
    def set_rd(self, rdn, expr):
        if rdn == 15:
            self.pcx, self.pcmask = expr, True
        else:
            self.wr(rdn, expr)

    def dp(self, pc, w, la):
        op, s, rn, rdn = w >> 21 & 15, w >> 20 & 1, w >> 16 & 15, w >> 12 & 15
        cmpop = 8 <= op <= 11
        logical = op in ARM_LOGICAL
        _, df = flag_rw(w)
        want = bool(s) and bool(df & la)
        if cmpop and not want:
            return
        if s and rdn == 15 and not cmpop:
            raise ArmUnsupported('exception return')
        need_c = logical and want and 'C' in df and 'C' in la
        b, carry = self.op2(w, pc, need_c)
        regc = False
        if b is None:
            typ, v, rs = carry
            if want and logical:
                self.materialize()
                self.emit(f'tv, tc = _shift({typ}, {v}, {rs} & 255)')
                b, carry, regc = 'tv', 'tc', True
            else:
                b, carry = f'_shv({typ}, {v}, {rs} & 255)', None
        a = self.rd(rn, pc) if op not in (13, 15) else None
        if op in (2, 3, 4, 10, 11) and want:
            self.tmp += 1
            fa, fb = f'fa{self.tmp}', f'fb{self.tmp}'
            if op == 3:
                a, b = b, a
            if not a.isdigit():
                self.emit(f'{fa} = {a}')
                a = fa
            if not b.isdigit():
                self.emit(f'{fb} = {b}')
                b = fb
            if op in (2, 3, 10):
                res = f'({a} - {b}) & 0xFFFFFFFF'
                nd = ('sub', a, b)
            else:
                res = f'fr{self.tmp}'
                self.emit(f'{res} = ({a} + {b}) & 0xFFFFFFFF')
                nd = ('add', a, b, res)
            if self.cdepth:
                n, z, c, v = (self.fx(nd, f) for f in 'NZCV')
                self.emit(f'N, Z, C, V = {n}, {z}, {c}, {v}')
                self.fl = ('exp',)
            else:
                self.fl = nd
            if not cmpop:
                self.set_rd(rdn, res)
            return
        if op in (5, 6, 7):
            c = self.carry_in()
            if want:
                self.materialize()
                c = 'C'
            fa, fb, x, fr = self.t('fa'), self.t('fb'), self.t('x'), self.t('fr')
            self.emit(f'{fa} = {a}')
            self.emit(f'{fb} = {b}')
            if op == 5:
                self.emit(f'{x} = {fa} + {fb} + ({c})')
            elif op == 6:
                self.emit(f'{x} = {fa} - {fb} - 1 + ({c})')
            else:
                self.emit(f'{x} = {fb} - {fa} - 1 + ({c})')
            self.emit(f'{fr} = {x} & 0xFFFFFFFF')
            if want:
                if op == 5:
                    self.emit(f'N, Z, C, V = ({fr} & 0x80000000) != 0, {fr} == 0, {x} > 0xFFFFFFFF, ((~({fa} ^ {fb}) & ({fa} ^ {fr})) & 0x80000000) != 0')
                elif op == 6:
                    self.emit(f'N, Z, C, V = ({fr} & 0x80000000) != 0, {fr} == 0, {x} >= 0, ((({fa} ^ {fb}) & ({fa} ^ {fr})) & 0x80000000) != 0')
                else:
                    self.emit(f'N, Z, C, V = ({fr} & 0x80000000) != 0, {fr} == 0, {x} >= 0, ((({fb} ^ {fa}) & ({fb} ^ {fr})) & 0x80000000) != 0')
                self.fl = ('exp',)
            self.set_rd(rdn, fr)
            return
        expr = {0: f'{a} & {b}', 1: f'{a} ^ {b}', 8: f'{a} & {b}', 9: f'{a} ^ {b}', 12: f'{a} | {b}', 13: b,
                14: f'{a} & ({b} ^ 0xFFFFFFFF)', 15: f'{b} ^ 0xFFFFFFFF',
                2: f'({a} - {b}) & 0xFFFFFFFF', 3: f'({b} - {a}) & 0xFFFFFFFF', 4: f'({a} + {b}) & 0xFFFFFFFF'}[op]
        if not want:
            self.set_rd(rdn, expr)
            return
        fr = self.t('fr')
        self.emit(f'{fr} = {expr}')
        if regc:
            self.emit('if tc is not None: C = tc')
            self.emit(f'N, Z = ({fr} & 0x80000000) != 0, {fr} == 0')
            self.fl = ('exp',)
        elif self.cdepth:
            self.materialize()
            if 'C' in df and carry is not None:
                self.emit(f'N, Z, C = ({fr} & 0x80000000) != 0, {fr} == 0, {carry}')
            else:
                self.emit(f'N, Z = ({fr} & 0x80000000) != 0, {fr} == 0')
        else:
            c = None
            if 'C' in df and carry is not None:
                c = self.t('fc')
                self.emit(f'{c} = {carry}')
            self.fl = ('logic', fr, c, self.fl)
        if not cmpop:
            self.set_rd(rdn, fr)

    # ----- multiplies
    def flagged(self, expr, la, s, rd):
        if s and ({'N', 'Z'} & la):
            fr = self.t('fr')
            self.emit(f'{fr} = {expr}')
            if self.cdepth:
                self.materialize()
                self.emit(f'N, Z = ({fr} & 0x80000000) != 0, {fr} == 0')
            else:
                self.fl = ('logic', fr, None, self.fl)
            self.wr(rd, fr)
        else:
            self.wr(rd, expr)

    def mul(self, pc, w, la):
        rd, rn, rs, rm = w >> 16 & 15, w >> 12 & 15, w >> 8 & 15, w & 15
        e = f'{self.rd(rm, pc)} * {self.rd(rs, pc)}'
        if w & (1 << 21):
            e += f' + {self.rd(rn, pc)}'
        self.flagged(f'({e}) & 0xFFFFFFFF', la, w >> 20 & 1, rd)

    def lmul(self, pc, w, la):
        s, signed, acc = w >> 20 & 1, w >> 22 & 1, w >> 21 & 1
        hi, lo, rs, rm = w >> 16 & 15, w >> 12 & 15, w >> 8 & 15, w & 15
        a, b = self.rd(rm, pc), self.rd(rs, pc)
        if signed:
            a, b = f'(({a} ^ 0x80000000) - 0x80000000)', f'(({b} ^ 0x80000000) - 0x80000000)'
        e = f'{a} * {b}'
        if acc:
            e += f' + ((({self.rd(hi, pc)}) << 32) | {self.rd(lo, pc)})'
        p = self.t('p')
        self.emit(f'{p} = ({e}) & 0xFFFFFFFFFFFFFFFF')
        self.wr(lo, f'{p} & 0xFFFFFFFF')
        self.wr(hi, f'{p} >> 32')
        if s and ({'N', 'Z'} & la):
            fz = self.t('fz')
            self.emit(f'{fz} = (({p} >> 32) & 0x80000000) | (1 if {p} else 0)')
            if self.cdepth:
                self.materialize()
                self.emit(f'N, Z = ({fz} & 0x80000000) != 0, {fz} == 0')
            else:
                self.fl = ('logic', fz, None, self.fl)

    @staticmethod
    def half(v, top):
        return f'((({v} >> 16) ^ 0x8000) - 0x8000)' if top else f'((({v} & 0xFFFF) ^ 0x8000) - 0x8000)'

    def dsp(self, pc, w):
        op = w >> 21 & 3
        rd, rn, rs, rm = w >> 16 & 15, w >> 12 & 15, w >> 8 & 15, w & 15
        x, y = w >> 5 & 1, w >> 6 & 1
        if op == 0:      # SMLAxy
            self.wr(rd, f'({self.half(self.rd(rm, pc), x)} * {self.half(self.rd(rs, pc), y)} + {self.rd(rn, pc)}) & 0xFFFFFFFF')
        elif op == 1:    # SMLAWy / SMULWy
            e = f'((((({self.rd(rm, pc)}) ^ 0x80000000) - 0x80000000) * {self.half(self.rd(rs, pc), y)}) >> 16)'
            if x == 0:
                e += f' + {self.rd(rn, pc)}'
            self.wr(rd, f'({e}) & 0xFFFFFFFF')
        elif op == 2:    # SMLALxy
            e = f'{self.half(self.rd(rm, pc), x)} * {self.half(self.rd(rs, pc), y)} + ((({self.rd(rd, pc)}) << 32) | {self.rd(rn, pc)})'
            p = self.t('p')
            self.emit(f'{p} = ({e}) & 0xFFFFFFFFFFFFFFFF')
            self.wr(rn, f'{p} & 0xFFFFFFFF')
            self.wr(rd, f'{p} >> 32')
        else:            # SMULxy
            self.wr(rd, f'({self.half(self.rd(rm, pc), x)} * {self.half(self.rd(rs, pc), y)}) & 0xFFFFFFFF')

    def qop(self, pc, w):
        op = w >> 21 & 3
        rn, rd, rm = w >> 16 & 15, w >> 12 & 15, w & 15
        self.wr(rd, f'{("_qadd", "_qsub", "_qdadd", "_qdsub")[op]}({self.rd(rm, pc)}, {self.rd(rn, pc)})')

    # ----- loads and stores
    def ldst(self, pc, w):
        load, byte = w >> 20 & 1, w >> 22 & 1
        rn, rdn = w >> 16 & 15, w >> 12 & 15
        up, pre, wb = w >> 23 & 1, w >> 24 & 1, w >> 21 & 1
        base = self.rd(rn, pc)
        if w & (1 << 25):
            off = self.shifted(w & 15, w >> 5 & 3, w >> 7 & 31, pc)
        else:
            off = str(w & 0xFFF)
        sign = '+' if up else '-'
        post = None
        if pre:
            if wb:
                self.emit(f'ea = ({base} {sign} {off}) & 0xFFFFFFFF')
                ea = 'ea'
            else:
                ea = f'({base} {sign} {off})'
        else:
            ea = base
            post = f'({base} {sign} {off}) & 0xFFFFFFFF'
        if post is not None and load and w & (1 << 25) and (w & 15) == rdn:
            self.emit(f'wb = {post}')
            post = 'wb'
        idx = f'{ea} & 0x7FFFFF' if byte else f'({ea} & 0x7FFFFC) >> 2'
        arr = 'M8' if byte else 'M32'
        if load:
            if rdn == 15:
                self.pcx, self.pcmask = f'{arr}[{idx}]', False
                self.emit(f'npc = {self.pcx}')
                self.pcx = 'npc'
            else:
                self.wr(rdn, f'{arr}[{idx}]')
        else:
            v = self.rd(rdn, pc) if rdn != 15 else str((pc + 12) & MASK32)
            self.emit(f'{arr}[{idx}] = {v}' + (' & 0xFF' if byte else ''))
        if post is not None:
            if not (load and rdn == rn):
                self.wr(rn, post)
        elif wb and not (load and rdn == rn):
            self.wr(rn, 'ea')

    def ldsth(self, pc, w):
        load, sh = w >> 20 & 1, w >> 5 & 3
        rn, rdn = w >> 16 & 15, w >> 12 & 15
        up, pre, wb = w >> 23 & 1, w >> 24 & 1, w >> 21 & 1
        base = self.rd(rn, pc)
        if w & (1 << 22):
            off = str((w >> 4 & 0xF0) | (w & 15))
        else:
            off = self.rd(w & 15, pc)
        sign = '+' if up else '-'
        post = None
        if pre:
            if wb:
                self.emit(f'ea = ({base} {sign} {off}) & 0xFFFFFFFF')
                ea = 'ea'
            else:
                ea = f'({base} {sign} {off})'
        else:
            ea = base
            post = f'({base} {sign} {off}) & 0xFFFFFFFF'
        if post is not None and load and not w & (1 << 22) and (w & 15) == rdn:
            self.emit(f'wb = {post}')
            post = 'wb'
        if load:
            if sh == 1:
                self.wr(rdn, f'M16[({ea} & 0x7FFFFE) >> 1]')
            elif sh == 2:
                self.wr(rdn, f'S8[{ea} & 0x7FFFFF] & 0xFFFFFFFF')
            else:
                self.wr(rdn, f'S16[({ea} & 0x7FFFFE) >> 1] & 0xFFFFFFFF')
        elif sh == 1:
            self.emit(f'M16[({ea} & 0x7FFFFE) >> 1] = {self.rd(rdn, pc)} & 0xFFFF')
        elif sh == 2:    # LDRD
            self.emit(f'ea = {ea}')
            self.wr(rdn, 'M32[(ea & 0x7FFFFC) >> 2]')
            self.wr(rdn + 1, 'M32[((ea + 4) & 0x7FFFFC) >> 2]')
        else:            # STRD
            self.emit(f'ea = {ea}')
            self.emit(f'M32[(ea & 0x7FFFFC) >> 2] = {self.rd(rdn, pc)}')
            self.emit(f'M32[((ea + 4) & 0x7FFFFC) >> 2] = {self.rd(rdn + 1, pc)}')
        if post is not None:
            if not (load and sh != 2 and rdn == rn):
                self.wr(rn, post)
        elif wb and not (load and sh != 2 and rdn == rn):
            self.wr(rn, 'ea')

    def block(self, pc, w):
        rn, regs = w >> 16 & 15, w & 0xFFFF
        pre, up, wb, load = w >> 24 & 1, w >> 23 & 1, w >> 21 & 1, w >> 20 & 1
        if w & (1 << 22):
            raise ArmUnsupported('ldm/stm with S bit')
        n = bin(regs).count('1')
        base = self.rd(rn, pc)
        if up:
            start = 4 if pre else 0
        else:
            start = -4 * n if pre else -4 * n + 4
        self.emit(f'ea = {base} + {start}')
        k = 0
        for r in range(16):
            if regs >> r & 1:
                addr = f'((ea + {4 * k}) & 0x7FFFFC) >> 2' if k else '(ea & 0x7FFFFC) >> 2'
                if load:
                    if r == 15:
                        self.emit(f'npc = M32[{addr}]')
                        self.pcx, self.pcmask = 'npc', False
                    else:
                        self.wr(r, f'M32[{addr}]')
                else:
                    self.emit(f'M32[{addr}] = ' + (self.rd(r, pc) if r != 15 else str((pc + 12) & MASK32)))
                k += 1
        if wb and not (load and regs >> rn & 1):
            self.wr(rn, f'({base} + {4 * n if up else -4 * n}) & 0xFFFFFFFF')

    def bx(self, pc, w):
        self.emit(f'npc = {self.rd(w & 15, pc)}')
        if w & 0x20:
            self.wr(14, str((pc + 4) & MASK32))
        self.pcx, self.pcmask = 'npc', False

    # ----- decode
    def ins(self, pc, w, la):
        t = w >> 25 & 7
        if t == 0 and w & 0x90 == 0x90:
            if w & 0x60 == 0:
                if w & 0x01000000:
                    raise ArmUnsupported(f'swp at {pc:08x}')
                if w & 0x00800000:
                    self.lmul(pc, w, la)
                else:
                    self.mul(pc, w, la)
            else:
                self.ldsth(pc, w)
        elif t in (0, 1):
            op, s = w >> 21 & 15, w >> 20 & 1
            if 8 <= op <= 11 and not s:
                if t == 1:
                    raise ArmUnsupported(f'msr/undefined {w:08x} at {pc:08x}')
                low = w >> 4 & 15
                if (w & 0x0FFFFFD0) == 0x012FFF10:
                    self.bx(pc, w)
                elif (w & 0x0FFF0FF0) == 0x016F0F10:
                    self.wr(w >> 12 & 15, f'32 - {self.rd(w & 15, pc)}.bit_length()')
                elif low == 5:
                    self.qop(pc, w)
                elif low & 9 == 8:
                    self.dsp(pc, w)
                else:
                    raise ArmUnsupported(f'misc instruction {w:08x} at {pc:08x}')
            else:
                self.dp(pc, w, la)
        elif t in (2, 3):
            if t == 3 and w & 0x10:
                raise ArmUnsupported(f'undefined {w:08x} at {pc:08x}')
            self.ldst(pc, w)
        elif t == 4:
            self.block(pc, w)
        else:
            raise ArmUnsupported(f'coprocessor/swi {w:08x} at {pc:08x}')
