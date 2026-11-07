"""Plays a sequence in the head: what every track does and when, as lists of notes and changes (no sound). Calls, loops with a count
and conditions are followed, the endless loop of a track ends the list and is kept as the loop of the sequence."""
import heapq

from .sseq import FROM_VAR, IF, RANDOM, SseqError, TICKS, decode

DEFAULT_TEMPO = 120
LIMIT = 3_000_000                # commands one track may run before it is given up as endless
# the numbers a controller command sets, by event name (the other commands are not events)
CONTROLS = ('prog', 'vol', 'expr', 'pan', 'bend', 'range', 'prio', 'master', 'porta', 'portaon', 'portatime', 'moddepth', 'modspeed',
            'modtype', 'modrange', 'moddelay', 'attack', 'decay', 'sustain', 'release', 'sweep')


class Line:
    """What one track plays. notes: [(tick, key, velocity, length)]; events: [(tick, name, number)], name one of CONTROLS; variables:
    [(tick, variable, operation, number)] the game reads. All lists are in time order."""
    __slots__ = ('number', 'notes', 'events', 'variables', 'end', 'loop')

    def __init__(self, number):
        self.number, self.notes, self.events, self.variables = number, [], [], []
        self.end, self.loop = 0, None           # tick the track stops at; (first tick, last tick) when it repeats

    def empty(self):
        return not (self.notes or self.events or self.variables)


class Timeline:
    """lines {track number: Line}, tempos [(tick, beats per minute)], loop (first tick, last tick) or None, length in ticks."""

    def __init__(self):
        self.lines, self.tempos, self.loop, self.length = {}, [], None, 0

    def tempo_at(self, tick):
        bpm = DEFAULT_TEMPO
        for t, b in self.tempos:
            if t > tick:
                break
            bpm = b
        return bpm

    def seconds(self, ticks):
        """Seconds a number of ticks lasts at the tempos of the sequence."""
        out, last, bpm = 0.0, 0, DEFAULT_TEMPO
        for t, b in self.tempos:
            if t >= ticks:
                break
            out += (t - last) * 60.0 / (TICKS * bpm)
            last, bpm = t, b
        return out + (ticks - last) * 60.0 / (TICKS * bpm)

    def ticks_at(self, seconds):
        """The tick a number of seconds from the start falls on (the other way round from seconds())."""
        at, last, bpm = 0.0, 0, DEFAULT_TEMPO
        for t, b in self.tempos:
            span = (t - last) * 60.0 / (TICKS * bpm)
            if at + span > seconds:
                break
            at += span
            last, bpm = t, b
        return last + (seconds - at) * TICKS * bpm / 60.0

    def note_count(self):
        return sum(len(line.notes) for line in self.lines.values())


class _Run:
    """The state of a track while it plays."""
    __slots__ = ('number', 'pc', 'time', 'stack', 'loops', 'notewait', 'transpose', 'cond', 'first', 'steps', 'line')

    def __init__(self, number, pc, time):
        self.number, self.pc, self.time = number, pc, time
        self.stack, self.loops = [], []
        self.notewait, self.transpose, self.cond = True, 0, False
        self.first, self.steps = {}, 0
        self.line = Line(number)


def _variable(vs, op, n, v):
    """Applies a variable command; comparisons return the verdict, the others None."""
    a = vs.get(n, 0)
    if op == 'set':
        vs[n] = v
    elif op == 'add':
        vs[n] = a + v
    elif op == 'sub':
        vs[n] = a - v
    elif op == 'mul':
        vs[n] = a * v
    elif op == 'div':
        vs[n] = int(a / v) if v else a
    elif op == 'shift':
        vs[n] = a << v if v >= 0 else a >> -v
    elif op == 'rand':
        vs[n] = 0
    else:
        return {'eq': a == v, 'ge': a >= v, 'gt': a > v, 'le': a <= v, 'lt': a < v, 'ne': a != v}[op]
    return None


def play(data, max_ticks=None):
    """The Timeline of sequence data. `max_ticks` stops every track past that time (for the sequences that never end and never repeat).
    Raises SseqError when the data cannot be read."""
    tl, vs = Timeline(), {}
    runs, queue = {}, []

    def start(number, pc, time):
        if number in runs:
            return
        runs[number] = _Run(number, pc, time)
        heapq.heappush(queue, (time, number))

    start(0, 0, 0)
    size = len(data)
    while queue:
        time, number = heapq.heappop(queue)
        run = runs[number]
        line = run.line
        while True:
            if max_ticks is not None and run.time > max_ticks:
                line.end = run.time
                break
            if run.pc >= size:
                raise SseqError('Track %d runs past the end of the sequence' % number)
            run.steps += 1
            if run.steps > LIMIT:
                raise SseqError('Track %d never stops or waits' % number)
            c = decode(data, run.pc)
            first = run.first.get(run.pc)
            if first is None:
                run.first[run.pc] = run.time
            nxt = run.pc + c.size
            if c.prefix == IF and not run.cond:
                run.pc = nxt
                continue
            args = list(c.args)
            if c.prefix == RANDOM:
                args.append(c.extra[0])
            elif c.prefix == FROM_VAR:
                args.append(vs.get(c.extra[0], 0))
            name = c.name
            wait = 0
            if name == 'note':
                key = min(127, max(0, c.op + run.transpose))
                length = args[1]
                line.notes.append((run.time, key, args[0] & 127, length))
                if run.notewait:
                    wait = length
            elif name == 'rest':
                wait = args[0]
            elif name == 'open':
                start(args[0], args[1], run.time)
            elif name == 'jump':
                target = args[0]
                seen = run.first.get(target)
                if seen is not None:
                    if run.time > seen:
                        line.loop = (seen, run.time)
                    line.end = run.time
                    break
                run.pc = target
                continue
            elif name == 'call':
                if len(run.stack) >= 16:
                    raise SseqError('Calls nest too deep in track %d' % number)
                run.stack.append(nxt)
                run.pc = args[0]
                continue
            elif name == 'return':
                if not run.stack:
                    line.end = run.time
                    break
                run.pc = run.stack.pop()
                continue
            elif name == 'loopstart':
                run.loops.append([nxt, args[0]])
            elif name == 'loopend':
                if run.loops:
                    top = run.loops[-1]
                    if top[1] == 0:                         # endless: the track repeats from there
                        seen = run.first.get(top[0])
                        if seen is not None and run.time > seen:
                            line.loop = (seen, run.time)
                        line.end = run.time
                        break
                    top[1] -= 1
                    if top[1] > 0:
                        run.pc = top[0]
                        continue
                    run.loops.pop()
            elif name == 'end':
                line.end = run.time
                break
            elif name == 'transpose':
                run.transpose = args[0]
            elif name == 'notewait':
                run.notewait = bool(args[0])
            elif name == 'tempo':
                tl.tempos.append((run.time, args[0]))
            elif name.startswith('var_'):
                verdict = _variable(vs, name[4:], args[0], args[1])
                if verdict is None:
                    line.variables.append((run.time, args[0], name[4:], args[1]))
                else:
                    run.cond = verdict
            elif name in CONTROLS:
                line.events.append((run.time, name, args[0]))
            run.pc = nxt
            if wait:
                run.time += wait
                heapq.heappush(queue, (run.time, number))
                break
    tl.lines = {n: r.line for n, r in sorted(runs.items())}
    tl.tempos = _tempo_map(tl.tempos)
    loops = [line.loop for line in tl.lines.values() if line.loop]
    tl.length = max([line.end for line in tl.lines.values()] + [t + n for line in tl.lines.values() for t, k, v, n in line.notes] + [0])
    tl.loop = _global_loop(loops)
    return tl


def _tempo_map(tempos):
    """Tempo changes in time order, the last of two at the same tick winning, repeated values dropped."""
    out = {}
    for t, b in sorted(tempos, key=lambda x: x[0]):
        out[t] = b
    result, last = [], None
    for t in sorted(out):
        if out[t] != last:
            result.append((t, out[t]))
            last = out[t]
    return result


def _global_loop(loops):
    """The loop of the sequence from the loops of its tracks: the earliest start and the latest end."""
    if not loops:
        return None
    return (min(s for s, e in loops), max(e for s, e in loops))
