"""SSEQ: a music sequence of the sound archive. The file is a small header and the sequence data, a stream of commands that
every track of the sequence reads at its own pace (notes, rests, volume, tempo, jumps ...). Times count in ticks, 48 per quarter note."""
import struct

TICKS = 48                  # ticks of a quarter note

# command number -> (name, kinds of its numbers); kinds: b s8, B u8, h s16, H u16, 3 u24 offset, v variable length
COMMANDS = {
    0x80: ('rest', 'v'), 0x81: ('prog', 'v'), 0x93: ('open', 'B3'), 0x94: ('jump', '3'), 0x95: ('call', '3'),
    0xC0: ('pan', 'B'), 0xC1: ('vol', 'B'), 0xC2: ('master', 'B'), 0xC3: ('transpose', 'b'), 0xC4: ('bend', 'b'),
    0xC5: ('range', 'B'), 0xC6: ('prio', 'B'), 0xC7: ('notewait', 'B'), 0xC8: ('tie', 'B'), 0xC9: ('porta', 'B'),
    0xCA: ('moddepth', 'B'), 0xCB: ('modspeed', 'B'), 0xCC: ('modtype', 'B'), 0xCD: ('modrange', 'B'), 0xCE: ('portaon', 'B'),
    0xCF: ('portatime', 'B'), 0xD0: ('attack', 'B'), 0xD1: ('decay', 'B'), 0xD2: ('sustain', 'B'), 0xD3: ('release', 'B'),
    0xD4: ('loopstart', 'B'), 0xD5: ('expr', 'B'), 0xD6: ('print', 'B'),
    0xE0: ('moddelay', 'H'), 0xE1: ('tempo', 'H'), 0xE3: ('sweep', 'h'),
    0xFC: ('loopend', ''), 0xFD: ('return', ''), 0xFE: ('alloc', 'H'), 0xFF: ('end', ''),
}
VARIABLES = {0xB0: 'set', 0xB1: 'add', 0xB2: 'sub', 0xB3: 'mul', 0xB4: 'div', 0xB5: 'shift', 0xB6: 'rand',
             0xB8: 'eq', 0xB9: 'ge', 0xBA: 'gt', 0xBB: 'le', 0xBC: 'lt', 0xBD: 'ne'}
for _op, _name in VARIABLES.items():
    COMMANDS[_op] = ('var_' + _name, 'Bh')
NAMES = {name: op for op, (name, _) in COMMANDS.items()}
RANDOM, FROM_VAR, IF = 0xA0, 0xA1, 0xA2                    # prefixes: the last number of the next command is random / read from a variable / the command runs only if the last comparison held
END_COMMANDS = ('end', 'return', 'jump')


class SseqError(ValueError):
    pass


def read_vlq(d, p):
    """(number, next position) of a variable length number: 7 bits per byte, the high bit says more follow."""
    v = 0
    for _ in range(4):
        b = d[p]
        p += 1
        v = v << 7 | b & 0x7F
        if not b & 0x80:
            return v, p
    raise SseqError('Bad variable length number at %#x' % (p - 4))


def vlq(v):
    """A number as a variable length number."""
    if not 0 <= v < 1 << 28:
        raise SseqError('Number out of range: %d' % v)
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append(v & 0x7F | 0x80)
        v >>= 7
    return bytes(reversed(out))


class Command:
    """One command of the stream: `at` its position, `size` its length in bytes, `name`, `args` (numbers), `prefix` (RANDOM, FROM_VAR, IF
    or None) and `extra` the numbers the prefix adds (min and max, or the variable)."""
    __slots__ = ('at', 'size', 'op', 'name', 'args', 'prefix', 'extra', 'under')

    def __repr__(self):
        return '<%#x %s%s %s>' % (self.at, self.name, '' if self.prefix is None else ' %#x' % self.prefix, self.args)


def decode(d, p):
    """The Command at position p of the sequence data."""
    c = Command()
    c.at, c.prefix, c.extra, c.under = p, None, (), None
    try:
        op = d[p]
        p += 1
        if op in (RANDOM, FROM_VAR, IF):
            c.prefix = op
            c.under = op
            op = d[p]
            p += 1
            if op in (RANDOM, FROM_VAR, IF):
                raise SseqError('Two prefixes in a row at %#x' % c.at)
        c.op = op
        if op < 0x80:
            c.name, kinds = 'note', 'Bv'
        elif op in COMMANDS:
            c.name, kinds = COMMANDS[op]
        else:
            raise SseqError('Unknown command %#x at %#x' % (op, c.at))
        kinds = {'B3': 'B3', 'Bh': 'Bh'}.get(kinds, kinds)
        if c.prefix in (RANDOM, FROM_VAR):
            if not kinds:
                raise SseqError('The prefix has no number to replace at %#x' % c.at)
            kinds = kinds[:-1]
        args = []
        for k in kinds:
            if k == 'B':
                args.append(d[p])
                p += 1
            elif k == 'b':
                args.append(d[p] - 256 if d[p] > 127 else d[p])
                p += 1
            elif k == 'H':
                args.append(d[p] | d[p + 1] << 8)
                p += 2
            elif k == 'h':
                v = d[p] | d[p + 1] << 8
                args.append(v - 65536 if v > 32767 else v)
                p += 2
            elif k == '3':
                args.append(d[p] | d[p + 1] << 8 | d[p + 2] << 16)
                p += 3
            elif k == 'v':
                v, p = read_vlq(d, p)
                args.append(v)
        if c.prefix == RANDOM:
            lo, hi = struct.unpack_from('<hh', d, p)
            c.extra = (lo, hi)
            p += 4
        elif c.prefix == FROM_VAR:
            c.extra = (d[p],)
            p += 1
        c.args = args
    except IndexError:
        raise SseqError('The sequence ends in the middle of a command at %#x' % c.at) from None
    c.size = p - c.at
    return c


def encode(name, *args):
    """The bytes of a command (a note takes the key, the velocity and the length)."""
    if name == 'note':
        key, vel, length = args
        if not 0 <= key < 128 or not 0 <= vel < 128:
            raise SseqError('Note out of range: key %d, velocity %d' % (key, vel))
        return bytes([key, vel]) + vlq(length)
    op = NAMES[name]
    kinds = COMMANDS[op][1]
    if len(args) != len(kinds) and kinds != 'B3':
        raise SseqError('The command %s takes %d number(s)' % (name, len(kinds)))
    out = bytearray([op])
    values = list(args)
    for k in {'B3': 'B3', 'Bh': 'Bh'}.get(kinds, kinds):
        v = values.pop(0)
        try:
            if k == 'B':
                out.append(v)
            elif k == 'b':
                out.append(v & 255)
            elif k == 'H':
                out += struct.pack('<H', v)
            elif k == 'h':
                out += struct.pack('<h', v)
            elif k == '3':
                out += struct.pack('<I', v)[:3]
            elif k == 'v':
                out += vlq(v)
        except (struct.error, ValueError):
            raise SseqError('Number %d does not fit the command %s' % (v, name)) from None
    return bytes(out)


# ----- the file

def sseq_data(f):
    """The sequence data of an SSEQ file."""
    f = bytes(f)
    if f[:4] != b'SSEQ' or f[16:20] != b'DATA' or len(f) < 28:
        raise SseqError('This is not an SSEQ file')
    start, = struct.unpack_from('<I', f, 24)
    size, = struct.unpack_from('<I', f, 20)
    end = min(len(f), 16 + size)
    if not 28 <= start <= end:
        raise SseqError('Bad SSEQ header')
    return f[start:end]


def sseq_file(data):
    """The SSEQ file of sequence data."""
    data = bytes(data)
    pad = -len(data) % 4
    size = 28 + len(data) + pad
    return b'SSEQ\xff\xfe\x00\x01' + struct.pack('<IHH', size, 16, 1) + b'DATA' + struct.pack('<II', size - 16, 28) + data + b'\0' * pad


def listing(data):
    """Every command of the sequence data from `start`, as text lines (for the curious and for the tests)."""
    out, p = [], 0
    while p < len(data):
        try:
            c = decode(data, p)
        except SseqError:
            out.append('%04x  ??' % p)
            break
        out.append('%04x  %s%s %s%s' % (c.at, {None: '', RANDOM: 'random ', FROM_VAR: 'var ', IF: 'if '}[c.prefix], c.name,
                                        ' '.join(str(a) for a in c.args), ' ' + str(c.extra) if c.extra else ''))
        p += c.size
    return out
