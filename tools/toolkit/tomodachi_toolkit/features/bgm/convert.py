"""Sequences to MIDI files and back, and the writer of sequence data.

In the MIDI file every track of the sequence is a channel (track n is channel n + 1 in the editors), the tempo and the loop are on
a first track. What a MIDI file can say about a sequence:
  notes, program changes (bank select above 127), pitch bend with its range (RPN 0), tempo
  controllers 7 volume, 10 pan, 11 expression, 1 modulation depth, 76 modulation speed, 78 modulation delay, 5 portamento time,
  65 portamento on, 84 portamento key, 73 attack, 75 decay, 102 sustain, 72 release, 103 priority, 104 modulation type,
  105 modulation range, 106 master volume
  loops: markers named loopStart and loopEnd (or controller 111 for the start, as the players of games do)
  game variables: text events like `var0 = 100` (the game reads them to follow the music)."""
import re

from . import midi
from .sseq import SseqError, TICKS, encode
from .timeline import DEFAULT_TEMPO, Line, Timeline, _tempo_map

# event name -> controller number
CONTROLLERS = {'vol': 7, 'pan': 10, 'expr': 11, 'moddepth': 1, 'modspeed': 76, 'moddelay': 78, 'portatime': 5, 'portaon': 65,
               'porta': 84, 'attack': 73, 'decay': 75, 'sustain': 102, 'release': 72, 'prio': 103, 'modtype': 104, 'modrange': 105,
               'master': 106}
BY_CONTROLLER = {n: name for name, n in CONTROLLERS.items()}
OPERATORS = {'set': '=', 'add': '+=', 'sub': '-=', 'mul': '*=', 'div': '/=', 'shift': '<<=', 'rand': '?='}
OPERATOR_NAMES = {symbol: name for name, symbol in OPERATORS.items()}
VARIABLE = re.compile(r'^\s*var\s*(\d+)\s*(=|\+=|-=|\*=|/=|<<=|\?=)\s*(-?\d+)\s*$', re.I)
LOOP_START = re.compile(r'^\s*loop[\s_-]*start\s*$', re.I)
LOOP_END = re.compile(r'^\s*loop[\s_-]*end\s*$', re.I)
DEFAULT_VOLUME = 127            # of a track that does not set one; a MIDI player starts at 100
BEND_RANGE = 8192


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _microseconds(bpm):
    return round(60000000 / max(1, bpm))


# ----- sequence to MIDI

def to_midi(tl, title=''):
    """The bytes of the MIDI file of a Timeline."""
    cond = [(0, midi.meta_text(title, 3))] if title else []
    cond.append((0, midi.time_signature()))
    tl = _looped(tl)
    cond += [(t, midi.tempo(_microseconds(b))) for t, b in _with_default_tempo(tl.tempos)]
    if tl.loop:
        cond += [(tl.loop[0], midi.meta_text('loopStart', 6)), (tl.loop[1], midi.meta_text('loopEnd', 6))]
    tracks = [cond]
    for n, line in sorted(tl.lines.items()):
        if line.empty() or n > 15:
            continue
        out = [(0, 1, 0, midi.meta_text('Track %d' % n, 3))]
        if not any(t == 0 and name == 'vol' for t, name, v in line.events):
            out.append((0, 1, 0, midi.controller(n, 7, DEFAULT_VOLUME)))
        for t, name, v in line.events:
            for ev in _midi_events(n, name, v):
                out.append((t, 1, 0, ev))
        for t, k, v, length in line.notes:           # the notes of a key that start together go in the order they end
            out.append((t, 2, t + max(1, length), midi.note_on(n, k, max(1, v))))
            out.append((t + max(1, length), 0, 0, midi.note_off(n, k)))
        for t, var, op, v in line.variables:
            out.append((t, 1, 0, midi.meta_text('var%d %s %d' % (var, OPERATORS[op], v))))
        out.sort(key=lambda e: e[:3])
        tracks.append([(t, ev) for t, order, end, ev in out])
    return midi.write_midi(TICKS, tracks)


def _with_default_tempo(tempos):
    tempos = list(tempos)
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, DEFAULT_TEMPO))
    return tempos


def _looped(tl):
    """The Timeline without what comes at or after the end of its loop: the loop repeats before those events would play."""
    if not tl.loop:
        return tl
    stop, out = tl.loop[1], Timeline()
    out.loop, out.length, out.tempos = tl.loop, tl.length, [(t, b) for t, b in tl.tempos if t < stop]
    for n, line in tl.lines.items():
        new = Line(n)
        new.notes = [x for x in line.notes if x[0] < stop]
        new.events = [x for x in line.events if x[0] < stop]
        new.variables = [x for x in line.variables if x[0] < stop]
        new.end, new.loop = line.end, line.loop
        out.lines[n] = new
    return out


def _midi_events(ch, name, v):
    """The MIDI events of a controller command (a list of bytes)."""
    if name == 'prog':
        bank, number = v >> 7, v & 127
        return ([midi.controller(ch, 0, bank & 127)] if bank else []) + [midi.program(ch, number)]
    if name == 'bend':
        return [midi.pitch_bend(ch, _clamp(round(BEND_RANGE + v * BEND_RANGE / 127), 0, 16383))]
    if name == 'range':
        return [midi.controller(ch, 101, 0), midi.controller(ch, 100, 0), midi.controller(ch, 6, _clamp(v, 0, 127))]
    if name == 'portaon':
        return [midi.controller(ch, CONTROLLERS[name], 127 if v else 0)]
    if name in CONTROLLERS:
        return [midi.controller(ch, CONTROLLERS[name], _clamp(v, 0, 127))]
    return []


# ----- MIDI to sequence

class _Channel:
    __slots__ = ('line', 'held', 'delayed', 'pedal', 'bank', 'rpn', 'notes')

    def __init__(self, n):
        self.line = Line(n)
        self.held = {}              # key -> [(start tick, velocity)] notes not released yet
        self.delayed = []           # (start, key, velocity) released while the pedal was down
        self.pedal = False
        self.bank = 0
        self.rpn = [127, 127]


def from_midi(blob):
    """The Timeline of a MIDI file. Channel n becomes track n. Raises midi.MidiError."""
    division, events = midi.read_midi(blob)
    scale = TICKS / division

    def q(t):
        return int(t * scale + 0.5)

    chans, tempos, tracks_channels = {}, [], {}
    for t, track, kind, a, b, c in events:
        if kind in ('on', 'off', 'cc', 'prog', 'bend'):
            tracks_channels.setdefault(track, set()).add(a)
    loop_start = loop_end = cc_loop = None
    end_tick = 0

    def chan(n):
        if n not in chans:
            chans[n] = _Channel(n)
        return chans[n]

    def finish(ch, start, key, vel, t):
        a = q(start)
        ch.line.notes.append((a, key, vel, max(1, q(t) - a)))

    def release(ch, t):
        for start, key, vel in ch.delayed:
            finish(ch, start, key, vel, t)
        ch.delayed = []

    for t, track, kind, a, b, c in events:
        end_tick = max(end_tick, t)
        if kind == 'on':
            chan(a).held.setdefault(b, []).append((t, c))
        elif kind == 'off':
            ch = chan(a)
            stack = ch.held.get(b)
            if stack:
                start, vel = stack.pop(0)
                if ch.pedal:
                    ch.delayed.append((start, b, vel))
                else:
                    finish(ch, start, b, vel, t)
        elif kind == 'prog':
            ch = chan(a)
            ch.line.events.append((q(t), 'prog', ch.bank << 7 | b))
        elif kind == 'bend':
            chan(a).line.events.append((q(t), 'bend', _clamp(round((b - BEND_RANGE) * 127 / BEND_RANGE), -128, 127)))
        elif kind == 'tempo':
            tempos.append((q(t), _clamp(round(60000000 / max(1, a)), 1, 65535)))
        elif kind == 'cc':
            ch = chan(a)
            if b == 64:
                down = c >= 64
                if ch.pedal and not down:
                    release(ch, t)
                ch.pedal = down
            elif b in (120, 123):
                for key, stack in ch.held.items():
                    for start, vel in stack:
                        finish(ch, start, key, vel, t)
                ch.held = {}
                release(ch, t)
            elif b == 0:
                ch.bank = c
            elif b in (100, 101):
                ch.rpn[0 if b == 101 else 1] = c
            elif b == 6 and ch.rpn == [0, 0]:
                ch.line.events.append((q(t), 'range', c))
            elif b == 111:
                cc_loop = t if cc_loop is None else min(cc_loop, t)
            elif b in BY_CONTROLLER:
                name = BY_CONTROLLER[b]
                ch.line.events.append((q(t), name, (1 if c >= 64 else 0) if name == 'portaon' else c))
        elif kind in ('marker', 'text'):
            if LOOP_START.match(a):
                loop_start = t if loop_start is None else min(loop_start, t)
            elif LOOP_END.match(a):
                loop_end = t if loop_end is None else max(loop_end, t)
            else:
                m = VARIABLE.match(a)
                if m and int(m.group(1)) < 32:
                    owner = tracks_channels.get(track, set())
                    ch = chan(min(owner) if len(owner) == 1 else 0)
                    ch.line.variables.append((q(t), int(m.group(1)), OPERATOR_NAMES[m.group(2)], _clamp(int(m.group(3)), -32768, 32767)))
    for ch in chans.values():
        release(ch, end_tick)
        for key, stack in ch.held.items():
            for start, vel in stack:
                finish(ch, start, key, vel, max(end_tick, start + 1))
    tl = Timeline()
    for n, ch in sorted(chans.items()):
        line = ch.line
        line.notes.sort()
        line.events = _thin(sorted(line.events, key=lambda e: e[0]))
        line.variables.sort(key=lambda e: e[0])
        if line.notes and not any(t == 0 and name == 'vol' for t, name, v in line.events):
            line.events.insert(0, (0, 'vol', 100))
        tl.lines[n] = line
    tl.tempos = _tempo_map(tempos)
    length = max([q(end_tick)] + [t + n for line in tl.lines.values() for t, k, v, n in line.notes])
    start = loop_start if loop_start is not None else cc_loop
    if start is not None or loop_end is not None:
        a = q(start or 0)
        b = q(loop_end) if loop_end is not None else length
        if b > a:
            tl.loop = (a, b)
    tl.length = length
    for line in tl.lines.values():
        line.end = tl.loop[1] if tl.loop else max([line.end] + [t + n for t, k, v, n in line.notes])
    return tl


def _thin(events):
    """Controller events without the ones that repeat the value the track already has."""
    out, last = [], {}
    for e in events:
        if last.get(e[1]) != e[2]:
            out.append(e)
            last[e[1]] = e[2]
    return out


# ----- Timeline to sequence data

COMMAND_OF = {'vol': 'vol', 'pan': 'pan', 'master': 'master', 'bend': 'bend', 'range': 'range', 'prio': 'prio', 'porta': 'porta',
              'moddepth': 'moddepth', 'modspeed': 'modspeed', 'modtype': 'modtype', 'modrange': 'modrange', 'portaon': 'portaon',
              'portatime': 'portatime', 'attack': 'attack', 'decay': 'decay', 'sustain': 'sustain', 'release': 'release',
              'expr': 'expr', 'moddelay': 'moddelay', 'sweep': 'sweep', 'prog': 'prog'}
LABEL = object()


def _track(line, tempos, loop):
    """(bytes, offset of the loop start inside them or None) of one track. The jump back has its target left as zeros at the end."""
    items = []                                  # (tick, order, bytes or marker)
    stop = loop[1] if loop else None
    if line.notes:
        items.append((0, -3, encode('notewait', 0)))
    for t, bpm in tempos:
        items.append((t, -1, encode('tempo', bpm)))
    for t, name, v in line.events:
        items.append((t, 0, encode(COMMAND_OF[name], v)))
    for t, var, op, v in line.variables:
        items.append((t, 0, encode('var_' + op, var, v)))
    for t, k, vel, length in line.notes:
        items.append((t, 1, encode('note', k, vel, length)))
    if loop:
        items.append((loop[0], -2, LABEL))
    items.sort(key=lambda e: (e[0], e[1]))
    out, label, now = bytearray(), None, 0
    last = 0
    for t, order, data in items:
        if stop is not None and t >= stop:
            break
        if t > now:
            out += encode('rest', t - now)
            now = t
        if data is LABEL:
            label = len(out)
        else:
            out += data
        last = max(last, t)
    if loop:
        if stop > now:
            out += encode('rest', stop - now)
        out += encode('jump', 0)
    else:
        finish = max([line.end, last] + [t + n for t, k, v, n in line.notes])
        if finish > now:
            out += encode('rest', finish - now)
        out += encode('end')
    return bytes(out), label


def assemble(tl):
    """The sequence data of a Timeline. Raises SseqError."""
    numbers = sorted(set(n for n, line in tl.lines.items() if not line.empty()) | {0})
    if any(not 0 <= n < 16 for n in numbers):
        raise SseqError('A sequence has 16 tracks at most')
    loop = tl.loop if tl.loop and tl.loop[1] > tl.loop[0] else None
    empty = Line(0)
    tempos = _with_default_tempo(tl.tempos)
    bodies = [_track(tl.lines.get(n, empty), tempos if n == 0 else [], loop) for n in numbers]
    header = 3 + 5 * (len(numbers) - 1)
    base, pos = {}, header
    for n, (body, label) in zip(numbers, bodies):
        base[n] = pos
        pos += len(body)
    out = bytearray(encode('alloc', sum(1 << n for n in numbers)))
    for n in numbers[1:]:
        out += encode('open', n, base[n])
    for n, (body, label) in zip(numbers, bodies):
        body = bytearray(body)
        if loop and label is not None:
            body[-3:] = (base[n] + label).to_bytes(3, 'little')
        out += body
    if len(out) >= 1 << 24:
        raise SseqError('This sequence is too big')
    return bytes(out)


def fingerprint(tl):
    """What a MIDI file keeps of a Timeline, in a form that is equal for two Timelines that play the same: tempos, loop, and for every
    track its notes, its controller changes (repeated values left out) and its game variables."""
    tl = _looped(tl)
    lines = {}
    for n, line in sorted(tl.lines.items()):
        if line.empty():
            continue
        events = [e for e in _thin(sorted(line.events, key=lambda e: e[0])) if e != (0, 'vol', DEFAULT_VOLUME)]
        lines[n] = (sorted((t, k, v, max(1, length)) for t, k, v, length in line.notes), sorted(events), sorted(line.variables))
    return _with_default_tempo(tl.tempos), tl.loop, lines
