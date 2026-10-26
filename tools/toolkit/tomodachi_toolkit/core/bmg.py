"""BMG (MESGbmg1) message files: structure check, reading and editing the messages, and the NARC wrapper the game keeps them in.

A message is UTF-16 text that ends with a zero word. The game also hides codes in the text: the word 0x001A, a size byte
and the rest of the code (the name of a Mii, the header of a speech bubble, the place of a number...). A code may hold
zero words, so a text has to be read code by code.

Text form (bmg_text / bmg_raw): the characters as they are and every code as {hex}, the bytes that follow the word
0x001A. A real brace is written twice."""
import struct

from .binary import u16, u32
from .narc import narc_parts

ESCAPE = 0x1A
HEADER = 0x20          # bytes before the first section


def bmg_narc(f, old):
    t = narc_parts(old)
    p = t[b'BTNF']
    names = bytes(old[p:p + u32(old, p + 4)])
    pad = -len(f) % 4
    gm = b'GMIF' + struct.pack('<I', 8 + len(f) + pad) + f + b'\0' * pad
    fat = b'BTAF' + struct.pack('<IIII', 20, 1, 0, len(f))
    return b'NARC\xfe\xff\x00\x01' + struct.pack('<IHH', 16 + len(fat) + len(names) + len(gm), 16, 3) + fat + names + gm


def bmg_problems(f):
    f = bytes(f)
    if f[:8] != b'MESGbmg1':
        return ['not a MESGbmg1 file']
    out, n, p, tags = [], len(f), 0x20, []
    if u32(f, 8) != n:
        out.append(f'header says {u32(f, 8)} bytes, file has {n}')
    while p + 8 <= n:
        size = u32(f, p + 4)
        if size < 8 or p + size > n:
            out.append(f'section {f[p:p + 4].decode("latin1")} runs past the end')
            break
        tags.append(f[p:p + 4])
        if p % 4 or size % 4:
            out.append(f'section {f[p:p + 4].decode("latin1")} not aligned to 4')
        p += size
    else:
        if p != n:
            out.append('sections do not end at the end of the file')
    out += [f'missing {t.decode()}' for t in (b'INF1', b'DAT1', b'MID1') if t not in tags]
    return out


# ----- texts

def code_size(raw, o):
    """Bytes taken by the code that starts at o (where the word 0x001A is)."""
    return max(raw[o + 2] if o + 2 < len(raw) else 0, 4)


def text_end(pool, o):
    """Where the message that starts at o ends: the place of its zero word (or the end of the pool when it has none)."""
    n = len(pool)
    while o + 1 < n:
        if pool[o] == ESCAPE and pool[o + 1] == 0:
            o += code_size(pool, o)
        elif pool[o] == 0 and pool[o + 1] == 0:
            return o
        else:
            o += 2
    return min(o, n)


def _chars(b):
    return b.decode('utf-16le', 'surrogatepass').replace('{', '{{').replace('}', '}}')


def bmg_text(raw):
    """The bytes of a message (no final zero word) as text, codes written as {hex}."""
    out, o, start, n = [], 0, 0, len(raw) - len(raw) % 2
    while o + 1 < n:
        if raw[o] == ESCAPE and raw[o + 1] == 0:
            size = code_size(raw, o)
            out.append(_chars(raw[start:o]))
            out.append('{' + bytes(raw[o + 2:o + size]).hex() + '}')
            o = start = o + size
        else:
            o += 2
    out.append(_chars(raw[start:n]))
    return ''.join(out)


def bmg_raw(text):
    """The bytes of a message from its text form. Raises ValueError for a code that is not written right."""
    out, i, n = bytearray(), 0, len(text)
    while i < n:
        c = text[i]
        if c == '{' and text[i + 1:i + 2] != '{':
            j = text.find('}', i)
            if j < 0:
                raise ValueError('A code starts with { and does not end.')
            try:
                code = bytes.fromhex(text[i + 1:j])
            except ValueError:
                raise ValueError(f'Bad code {text[i:j + 1]}.') from None
            if len(code) < 2 or code[0] != len(code) + 2:
                raise ValueError(f'Bad code {text[i:j + 1]}: its size byte must be {len(code) + 2}.')
            out += b'\x1a\x00' + code
            i = j + 1
        elif c in '{}':
            if text[i + 1:i + 2] != c:
                raise ValueError('A brace has to be written twice: {{ or }}.')
            out += c.encode('utf-16le')
            i += 2
        else:
            out += c.encode('utf-16le', 'surrogatepass')
            i += 1
    return bytes(out)


class _Slot:
    """One message of the text pool: its bytes, and how many messages of the file use it."""
    __slots__ = ('raw', 'ended', 'refs')

    def __init__(self, raw, ended):
        self.raw, self.ended, self.refs = raw, ended, 0


class BmgFile:
    """A message file taken apart. Change messages with set_raw / set_text, then write it with to_bytes().
    A file nobody changed comes back byte for byte as it was read."""

    def __init__(self, data):
        f = bytes(data)
        if f[:8] != b'MESGbmg1':
            raise ValueError('not a MESGbmg1 file')
        self.original, self.header, self.sections, self.dirty = f, f[:HEADER], [], False
        p = HEADER
        while p + 8 <= len(f):
            size = u32(f, p + 4)
            if size < 8 or p + size > len(f):
                raise ValueError(f'section {f[p:p + 4].decode("latin1")} runs past the end')
            self.sections.append([f[p:p + 4], f[p + 8:p + size]])
            p += size
        self.tail = f[p:]
        tags = [t for t, _ in self.sections]
        if b'INF1' not in tags or b'DAT1' not in tags:
            raise ValueError('missing INF1 or DAT1')
        self.inf, self.dat = tags.index(b'INF1'), tags.index(b'DAT1')
        inf, pool = self.sections[self.inf][1], self.sections[self.dat][1]
        self.count, self.size = u16(inf, 0), u16(inf, 2)
        if self.size < 4 or 8 + self.count * self.size > len(inf):
            raise ValueError('INF1 is damaged')
        offsets = [u32(inf, 8 + i * self.size) for i in range(self.count)]
        self.attrs = [bytes(inf[8 + i * self.size + 4:8 + (i + 1) * self.size]) for i in range(self.count)]
        self.layout, slots, cur = [], {}, 0
        for o in sorted(set(offsets)):
            if o < cur or o > len(pool):
                raise ValueError('messages overlap or start outside the text pool')
            if o > cur:
                self.layout.append(pool[cur:o])
            e = text_end(pool, o)
            ended = pool[e:e + 2] == b'\0\0'
            slots[o] = _Slot(pool[o:e], ended)
            self.layout.append(slots[o])
            cur = e + 2 if ended else e
        if cur < len(pool):
            self.layout.append(pool[cur:])
        self.entry = [slots[o] for o in offsets]
        for slot in self.entry:
            slot.refs += 1
        self.ids = None
        if b'MID1' in tags:
            mid = self.sections[tags.index(b'MID1')][1]
            have = min(u16(mid, 0), (len(mid) - 8) // 4)
            self.ids = [u32(mid, 8 + 4 * i) if i < have else None for i in range(self.count)]
        self.align = next((a for a in (32, 16, 8, 4) if (8 + len(pool)) % a == 0), 2)

    # ----- messages

    def raw(self, i):
        return self.entry[i].raw

    def text(self, i):
        return bmg_text(self.entry[i].raw)

    def set_raw(self, i, raw):
        raw = bytes(raw)
        slot = self.entry[i]
        if raw == slot.raw:
            return
        if len(raw) % 2:
            raise ValueError('A message is made of 16 bit characters.')
        if slot.refs > 1:                       # other messages use this text: this one gets its own copy
            slot.refs -= 1
            new = _Slot(raw, True)
            new.refs = 1
            self.layout.insert(next(k for k, part in enumerate(self.layout) if part is slot) + 1, new)
            self.entry[i] = new
        else:
            slot.raw, slot.ended = raw, True
        self.dirty = True

    def set_text(self, i, text):
        self.set_raw(i, bmg_raw(text))

    # ----- the file

    def to_bytes(self):
        if not self.dirty:
            return self.original
        pool, where = bytearray(), {}
        last = len(self.layout) - 1
        for k, part in enumerate(self.layout):
            if isinstance(part, _Slot):
                where[id(part)] = len(pool)
                pool += part.raw + (b'\0\0' if part.ended else b'')
            elif k == last:
                pool += part.rstrip(b'\0')          # the padding at the end is made again below
            else:
                pool += part
        pool += b'\0' * (-(8 + len(pool)) % self.align)
        inf = bytearray(self.sections[self.inf][1])
        for i, slot in enumerate(self.entry):
            struct.pack_into('<I', inf, 8 + i * self.size, where[id(slot)])
        body = b''
        for k, (tag, data) in enumerate(self.sections):
            data = bytes(inf) if k == self.inf else bytes(pool) if k == self.dat else data
            body += tag + struct.pack('<I', 8 + len(data)) + data
        body += self.tail
        return self.header[:8] + struct.pack('<I', HEADER + len(body)) + self.header[12:] + body


def bmg_strings(f):
    """The messages of a MESGbmg1 file as text (see bmg_text), in message order."""
    b = BmgFile(f)
    return [b.text(i) for i in range(b.count)]
