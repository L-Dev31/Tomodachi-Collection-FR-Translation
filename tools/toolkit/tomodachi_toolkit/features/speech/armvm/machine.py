"""The interpreter itself: memory, registers, hooks and calls."""

from .arithmetic import qadd, qdadd, qdsub, qsub, shift_reg, shift_val
from .translator import Blk
from .constants import ARM_ALL, ARM_BASE, ARM_MAXB, ARM_SENT, ARM_SIZE, MASK32
from .analysis import branch_target, flag_rw, is_term
from .errors import ArmUnsupported


class ArmVm:
    def __init__(self, image, sp=0x027E3F00):
        self.mem = bytearray(ARM_SIZE)
        self.mem[:len(image)] = image
        mv = memoryview(self.mem)
        self.M8, self.M16, self.S16, self.M32, self.S8 = self.mem, mv.cast('H'), mv.cast('h'), mv.cast('I'), mv.cast('b')
        self.R = [0] * 16
        self.F = [0, 0, 0, 0]
        self.cache = {}
        self.live = {}
        self.sp0 = sp
        self.ns = {'_shv': shift_val, '_shift': shift_reg, '_qadd': qadd, '_qsub': qsub, '_qdadd': qdadd, '_qdsub': qdsub}
        self.nblocks = 0

    # ----- memory
    def word(self, pc):
        return self.M32[((pc - ARM_BASE) & 0x7FFFFC) >> 2]

    def write(self, addr, data):
        o = addr - ARM_BASE
        self.mem[o:o + len(data)] = data

    def read(self, addr, n):
        o = addr - ARM_BASE
        return bytes(self.mem[o:o + n])

    def u32(self, addr):
        return self.M32[(addr - ARM_BASE) >> 2]

    def set_u32(self, addr, v):
        self.M32[(addr - ARM_BASE) >> 2] = v & MASK32

    # ----- execution
    def run(self, pc):
        cache, R = self.cache, self.R
        while pc != ARM_SENT:
            f = cache.get(pc)
            if f is None:
                f = self.compile(pc)
            pc = f(R)

    def call(self, addr, args=(), stack=()):
        R = self.R
        for i in range(4):
            R[i] = args[i] & MASK32 if i < len(args) else 0
        sp = self.sp0 - 0x40
        for i, v in enumerate(stack):
            self.set_u32(sp + 4 * i, v)
        R[13], R[14] = sp, ARM_SENT
        self.run(addr)
        return R[0]

    def hook(self, addr, fn):
        """fn(R) runs instead of the code at addr and must return the next pc."""
        self.cache[addr] = fn

    # ----- flag liveness at an address (conservative)
    def live_in(self, addr, depth=0, busy=None):
        if addr in self.live:
            return self.live[addr]
        busy = busy if busy is not None else set()
        if addr in busy or depth > 4:
            return ARM_ALL
        busy.add(addr)
        live, dead, pc = set(), set(), addr
        for _ in range(48):
            w = self.word(pc)
            cc = w >> 28
            rd, df = flag_rw(w)
            live |= rd - dead
            if cc == 14:
                dead |= df
            if dead >= ARM_ALL:
                break
            if cc != 15 and w >> 25 & 7 == 5:
                if w >> 24 & 1:
                    live |= ARM_ALL - dead
                    break
                tgt = branch_target(pc, w)
                nxt = set(self.live_in(tgt, depth + 1, busy))
                if cc != 14:
                    nxt |= set(self.live_in(pc + 4, depth + 1, busy))
                live |= nxt - dead
                break
            if is_term(w):
                live |= ARM_ALL - dead
                break
            pc += 4
        else:
            live |= ARM_ALL - dead
        busy.discard(addr)
        res = frozenset(live)
        if depth == 0:
            self.live[addr] = res
        return res

    # ----- translation
    def compile(self, start):
        if start & 3:
            raise ArmUnsupported(f'jump to {start:#x} (Thumb or unaligned)')
        if not ARM_BASE <= start < ARM_BASE + ARM_SIZE:
            raise ArmUnsupported(f'jump outside RAM: {start:#x}')
        ws, pc = [], start
        while True:
            w = self.word(pc)
            ws.append((pc, w))
            if is_term(w) or len(ws) >= ARM_MAXB:
                break
            pc += 4
        n = len(ws)
        lastpc, lastw = ws[-1]
        lastcc = lastw >> 28
        last_branch = is_term(lastw) and lastcc != 15 and lastw >> 25 & 7 == 5
        if not is_term(lastw):
            out = self.live_in(lastpc + 4)
        elif last_branch and not lastw >> 24 & 1:
            out = self.live_in(branch_target(lastpc, lastw))
            if lastcc != 14:
                out = out | self.live_in(lastpc + 4)
        else:
            out = ARM_ALL
        la = [None] * n
        cur = set(out)
        for i in range(n - 1, -1, -1):
            la[i] = frozenset(cur)
            rdf, df = flag_rw(ws[i][1])
            if ws[i][1] >> 28 == 14:
                cur -= df
            cur |= rdf
        b = Blk()
        for i, (pc, w) in enumerate(ws):
            cc = w >> 28
            if cc == 15:
                raise ArmUnsupported(f'unconditional-space instruction {w:08x} at {pc:08x}')
            last = i == n - 1
            if last and last_branch:
                break
            b.emit(f'# {pc:08x}: {w:08x}')
            dyn = last and is_term(w)
            guard = cc != 14
            if guard:
                if flag_rw(w)[1] & la[i]:
                    b.materialize()
                if dyn:
                    b.emit(f'npc = {(pc + 4) & MASK32}')
                b.emit(f'if {b.cond(cc)}:')
                b.ind += 1
                b.cdepth = 1
            n0 = len(b.lines)
            b.pcx = None
            b.ins(pc, w, la[i])
            if dyn:
                if b.pcx is None:
                    raise ArmUnsupported(f'terminator without target at {pc:08x}')
                if b.pcx != 'npc':
                    b.emit(f'npc = ({b.pcx}) & 0xFFFFFFFC' if b.pcmask else f'npc = {b.pcx}')
            if len(b.lines) == n0:
                b.emit('pass')
            if guard:
                b.ind -= 1
                b.cdepth = 0
        body_uses_entry = b.use_entry
        loop, after = False, []
        if last_branch:
            pc, w = lastpc, lastw
            tgt, fall, link = branch_target(pc, w), (pc + 4) & MASK32, bool(w >> 24 & 1)
            if lastcc == 14:
                if link:
                    b.wr(14, str(fall))
                b.lines.extend(self.exits(b, str(tgt), out))
            else:
                c = b.cond(lastcc)
                if tgt == start and not link and not body_uses_entry:
                    loop = True
                    b.lines.extend([f'if {c}:', '    continue', 'break'])
                    after = self.exits(b, str(fall), out)
                else:
                    b.emit(f'if {c}:')
                    b.ind += 1
                    if link:
                        b.cdepth = 1
                        b.wr(14, str(fall))
                        b.cdepth = 0
                    b.lines.extend('    ' * b.ind + x for x in self.exits(b, str(tgt), out))
                    b.ind -= 1
                    b.lines.extend(self.exits(b, str(fall), out))
        elif is_term(lastw):
            b.lines.extend(self.exits(b, 'npc', out))
        else:
            b.lines.extend(self.exits(b, str((lastpc + 4) & MASK32), out))
        return self.assemble(b, start, loop, after)

    @staticmethod
    def exits(b, target, live_out):
        out = [f'R[{r}] = r{r}' for r in sorted(b.written)]
        if live_out and b.fl is not None:
            n, z, c, v = (b.fx(b.fl, f) for f in 'NZCV')
            out.append(f'F[0], F[1], F[2], F[3] = {n}, {z}, {c}, {v}')
        out.append(f'return {target}')
        return out

    def assemble(self, b, start, loop, after):
        head = ['def make(M8, M16, S16, M32, S8, F):', '    def blk(R):']
        for r in sorted(b.need):
            head.append(f'        r{r} = R[{r}]')
        if b.use_entry:
            head.append('        N, Z, C, V = F')
        if loop:
            src = head + ['        while True:'] + ['            ' + x for x in b.lines] + ['        ' + x for x in after]
        else:
            src = head + ['        ' + x for x in b.lines]
        src.append('    return blk')
        text = '\n'.join(src)
        self.nblocks += 1
        ns = dict(self.ns)
        exec(compile(text, f'<arm {start:08x}>', 'exec'), ns)
        f = ns['make'](self.M8, self.M16, self.S16, self.M32, self.S8, self.F)
        self.cache[start] = f
        return f
