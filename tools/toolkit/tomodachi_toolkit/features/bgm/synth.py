"""A small software synthesizer: plays a sequence by itself so that the music can be heard while it is being changed.

The notes of a sequence (its Timeline) are played with the instruments of a bank (SBNK) and the waves of the wave archive (SWAR), the
way the sound engine of the console does it: every note is a wave played faster or slower to reach its pitch (the nearest sample, no
smoothing), under the envelope of the engine (attack, decay, sustain, release, worked out 192 times a second). The result is mixed to
16 bit mono. It is made to listen to the notes, not to replace the sound of the console: no stereo, no vibrato, no portamento, and the
volume and the pitch bend count at the start of every note.
"""
import bisect
import struct
import threading
from array import array
from functools import lru_cache
from math import log10

import numpy as np

from ...core.binary import u16, u32
from ..audio.sdat import swar_waves, wave_loop_start, wave_pcm
from .sseq import TICKS
from .timeline import DEFAULT_TEMPO

RATE = 22050                    # samples per second of what is made
UPDATES = 192                   # times per second the engine moves its envelopes
DECIBEL = 960                   # units of the engine in a decibel (it counts levels down from 0, the full level)
SILENT = -92544                 # the level of a note that makes no sound, in the units of the engine
AUDIBLE = -57600                # a note that is 60 decibels down is over
MAX_RELEASE = 4 * UPDATES       # updates a note may fade for
MAX_TONE = 12                   # seconds a note can last (a tone is worked out once for all the notes of its pitch)
MAX_KEPT = 16_000_000           # samples of waves and of tones kept for the next sequence (what is over that is worked out again)
LOUDNESS = 0.8                  # of the full scale, for the loud parts of the music
PSG_LEVEL = 9000                # volume of the pulse and noise instruments next to the recorded ones


class SynthError(ValueError):
    pass


# ----- the instruments of a bank

class Region:
    """One sound an instrument can make: `kind` 1 a recorded wave, 2 a pulse wave (`wave` is its width, 0 to 7), 3 noise; `key` the
    note the wave was recorded at; the envelope numbers (0 to 127) and the pan."""
    __slots__ = ('kind', 'wave', 'key', 'attack', 'decay', 'sustain', 'release', 'pan')

    def __init__(self, kind, wave, key, attack, decay, sustain, release, pan):
        self.kind, self.wave, self.key = kind, wave, key
        self.attack, self.decay, self.sustain, self.release, self.pan = attack, decay, sustain, release, pan


def read_region(kind, data, offset):
    wave, _, key, attack, decay, sustain, release, pan = struct.unpack_from('<HHBBBBBB', data, offset)
    return Region(kind, wave, key, attack, decay, sustain, release, pan)


def read_entry(data, offset):
    """A region of a range or regional instrument: a kind then the same numbers as a single instrument."""
    kind = u16(data, offset)
    return read_region(kind, data, offset + 2) if kind in (1, 2, 3) else None


class Bank:
    """The instruments of an SBNK file. region_of(program, key) is the Region a note plays (None when the bank has none for it).

    An instrument is one region for every key ('one'), a region for each key of a range ('range') or a region for each part of the
    keys, the way the drums of a kit are laid out ('regional')."""

    def __init__(self, data):
        data = bytes(data)
        self.programs = {}
        try:
            for program in range(u32(data, 0x38)):
                kind, offset = data[0x3C + 4 * program], u16(data, 0x3D + 4 * program)
                if kind in (1, 2, 3):
                    self.programs[program] = ('one', read_region(kind, data, offset))
                elif kind == 16:
                    low, high = data[offset], data[offset + 1]
                    self.programs[program] = ('range', low, [read_entry(data, offset + 2 + 12 * k) for k in range(high - low + 1)])
                elif kind == 17:
                    ends = list(data[offset:offset + 8])
                    count = next((i for i, end in enumerate(ends) if not end), 8)
                    self.programs[program] = ('regional', ends[:count], [read_entry(data, offset + 8 + 12 * k) for k in range(count)])
        except (IndexError, struct.error) as e:
            raise SynthError('This is not an instrument bank') from e

    def region_of(self, program, key):
        found = self.programs.get(program)
        if found is None:
            return None
        if found[0] == 'one':
            return found[1]
        if found[0] == 'range':
            _, low, regions = found
            return regions[key - low] if 0 <= key - low < len(regions) else None
        _, ends, regions = found
        return next((region for end, region in zip(ends, regions) if key <= end), None)


# ----- the numbers of the engine

def attack_rate(number):
    """How fast the engine opens a note, from its attack number (0 is the slowest, 127 is at once)."""
    number = min(number, 127)
    return 127 - number if number >= 109 else 255 - number


def fall_rate(number):
    """How far the engine lowers a note at every update, from its decay or release number (0 is the slowest, 127 is at once)."""
    number = min(number, 127)
    if number == 127:
        return 0xFFFF
    if number == 126:
        return 0x3C00
    return number * 2 + 1 if number < 50 else 0x1E00 // (126 - number)


def sustain_level(number):
    """Where the decay stops, from the sustain number (127 is the full level), in the units of the engine."""
    number = min(number, 127)
    return SILENT if number == 0 else int(40 * DECIBEL * log10(number / 127))


def gain_of(units):
    """The multiplier a level in the units of the engine stands for."""
    return 10.0 ** (units / (20.0 * DECIBEL))


def square_law(number):
    """The multiplier a volume, velocity or expression number (0 to 127) stands for: the engine treats them as squares."""
    return (max(0, min(127, number)) / 127.0) ** 2


def envelope(updates, attack, decay, sustain, release):
    """The level of a note at every update of the engine, in its units: `updates` of the note held down (an attack, then a decay down
    to the sustain), then its release until it is down 60 decibels."""
    attack, decay, release, sustain = attack_rate(attack), fall_rate(decay), fall_rate(release), sustain_level(sustain)
    level, out, phase = SILENT, [], 0
    for _ in range(updates):
        if phase == 0:
            level = -((-level * attack) >> 8)
            if level >= 0:
                level, phase = 0, 1
        elif phase == 1:
            level -= decay
            if level <= sustain:
                level, phase = sustain, 2
        out.append(level)
    release = max(release, -(-(level - AUDIBLE) // MAX_RELEASE))            # a release too slow to end in time is hurried (no click)
    for _ in range(MAX_RELEASE):
        if level <= AUDIBLE:
            break
        level -= release
        out.append(level)
    return out


@lru_cache(maxsize=4096)
def gain_curve(updates, attack, decay, sustain, release):
    """The multiplier of a note at every update of the engine (what envelope() says, in multipliers). Worked out once for the notes that
    share their numbers; the array is not to be changed."""
    curve = gain_of(np.array(envelope(updates, attack, decay, sustain, release), np.float64))
    curve.setflags(write=False)
    return curve


# ----- the time of a sequence

class Clock:
    """Turns the ticks of a sequence into samples at the tempos it sets."""

    def __init__(self, tempos, rate):
        steps = {0: DEFAULT_TEMPO}
        steps.update(dict(tempos))
        self.ticks = sorted(steps)
        self.speed = [rate * 60.0 / (TICKS * max(steps[t], 1)) for t in self.ticks]           # samples per tick
        self.base, at = [], 0.0
        for i, tick in enumerate(self.ticks):
            self.base.append(at)
            if i + 1 < len(self.ticks):
                at += (self.ticks[i + 1] - tick) * self.speed[i]

    def samples(self, tick):
        i = bisect.bisect_right(self.ticks, tick) - 1
        return int(self.base[i] + (tick - self.ticks[i]) * self.speed[i])


class Controls:
    """What the controllers of a track say at any tick: the instrument, the volume and the rest."""
    START = {'prog': 0, 'vol': 127, 'expr': 127, 'master': 127, 'bend': 0, 'range': 2}
    ENVELOPE = ('attack', 'decay', 'sustain', 'release')

    def __init__(self, events):
        names = tuple(self.START) + self.ENVELOPE
        self.ticks = {name: [] for name in names}
        self.values = {name: [] for name in names}
        for tick, name, value in events:
            if name in self.ticks:
                self.ticks[name].append(tick)
                self.values[name].append(value)

    def at(self, name, tick):
        """The latest number the controller was given by this tick (None for an envelope number that was never given)."""
        i = bisect.bisect_right(self.ticks[name], tick)
        return self.values[name][i - 1] if i else self.START.get(name)


# ----- the synthesizer

class Synth:
    """Plays sequences with the waves of one wave archive (the bytes of a SWAR). It keeps what it worked out (decoded waves, tones)
    so that the next sequence is quicker. One sequence is rendered at a time."""

    def __init__(self, swar, rate=RATE):
        self.swar, self.rate = swar, rate
        self.infos = swar_waves(swar)
        self.decoded = {}               # wave number -> (samples, the part of them that repeats or None, recorded rate)
        self.tones = {}                 # (kind, wave, pitch) -> (samples at that pitch, whether the wave ended)
        self.busy = threading.Lock()

    def wave(self, number):
        """(samples, loop, recorded rate) of a wave of the archive: a wave that repeats goes on by repeating `loop` (its last part).
        None when the wave cannot be played."""
        if number not in self.decoded:
            found = None
            if 0 <= number < len(self.infos) and self.infos[number]['enc'] in (0, 1, 2):
                info = self.infos[number]
                samples = np.array(wave_pcm(self.swar, info), np.int16)
                start = wave_loop_start(info)
                if len(samples):
                    loop = samples[start:] if info['loop'] and 0 <= start < len(samples) else None
                    found = (samples, loop if loop is not None and len(loop) else None, max(info['rate'], 1))
            self.decoded[number] = found
        return self.decoded[number]

    def forget(self):
        """Lets go of the decoded waves and of the tones when they take too much room."""
        if sum(len(found[0]) for found in self.decoded.values() if found) > MAX_KEPT:
            self.decoded.clear()
        if sum(len(made[0]) for made in self.tones.values()) > MAX_KEPT:
            self.tones.clear()

    def tone(self, region, pitch, count):
        """The first `count` samples of a region played at a pitch (in sixteenths of a semitone above its recorded note); fewer when
        its wave ends before that or when the note is too long to be worked out."""
        count = min(count, MAX_TONE * self.rate)
        key = (region.kind, region.wave, pitch)
        held = self.tones.get(key)
        if held is not None and (held[1] or len(held[0]) >= count):
            return held[0]
        count = min(max(count, 2 * len(held[0]) if held else count), MAX_TONE * self.rate)
        if region.kind == 1:
            made = self.recorded(region.wave, pitch, count)
        elif region.kind == 2:
            made = self.pulse(region.wave, pitch, count)
        else:
            made = self.noise(pitch, count)
        self.tones[key] = made
        return made[0]

    def recorded(self, number, pitch, count):
        wave = self.wave(number)
        if wave is None:
            return np.zeros(0, np.int16), True
        samples, loop, rate = wave
        step = rate / self.rate * 2.0 ** (pitch / 192.0)
        if loop is None:
            ended = int(count * step) + 2 > len(samples)
            count = min(count, max(0, int((len(samples) - 1) / step))) if ended else count
            return samples[(np.arange(count) * step).astype(np.int64)], ended
        at = (np.arange(count) * step).astype(np.int64)
        start = len(samples) - len(loop)
        return samples[np.where(at < start, at, start + (at - start) % len(loop))], False

    def pulse(self, width, pitch, count):
        """A pulse wave as wide as `width` says (1/8 to 8/8 of a cycle), at a pitch counted from the A of 440 hertz."""
        period = self.rate / (440.0 * 2.0 ** (pitch / 192.0))
        high = (min(width, 7) + 1) / 8.0
        return np.where((np.arange(count) % period) / period < high, PSG_LEVEL, -PSG_LEVEL).astype(np.int16), False

    def noise(self, pitch, count):
        """Noise that changes as often as the pitch says."""
        every = max(1.0, self.rate / (440.0 * 2.0 ** (pitch / 192.0)) / 2)
        which = (np.arange(count) / every).astype(np.int64)
        signs = np.random.default_rng(pitch & 0xFFFFFFFF).integers(0, 2, int(which[-1]) + 1 if count else 0) * 2 - 1
        return (signs[which] * PSG_LEVEL).astype(np.int16), False

    # ----- a whole sequence

    def render(self, timeline, bank, volume=127, seconds=None, progress=None, stop=None):
        """The sound of a Timeline played with a Bank, once through: from the start to the end of its loop (the whole of a sequence
        that does not loop). Returns 16 bit samples (an array of 'h'), or None when stop() said to give up. volume is the volume of
        the sequence (0 to 127); seconds cuts the sound short; progress(fraction) is called now and then."""
        with self.busy:
            self.forget()
            clock = Clock(timeline.tempos, self.rate)
            last = clock.samples(timeline.loop[1] if timeline.loop else timeline.length)
            if seconds is not None:
                last = min(last, int(seconds * self.rate))
            total = max(sum(len(line.notes) for line in timeline.lines.values()), 1)
            mix = np.zeros(last + MAX_RELEASE * self.rate // UPDATES + self.rate)
            done = 0
            for line in timeline.lines.values():
                controls = Controls(line.events)
                for tick, key, velocity, length in line.notes:
                    done += 1
                    if done % 32 == 0:
                        if stop is not None and stop():
                            return None
                        if progress is not None:
                            progress(done / total)
                    start = clock.samples(tick)
                    if start < last and length > 0:
                        self.note(mix, clock, controls, bank, tick, start, key, velocity, length)
            if progress is not None:
                progress(1.0)
            return self.finish(mix, last, square_law(volume))

    def note(self, mix, clock, controls, bank, tick, start, key, velocity, length):
        """Adds one note to the mix."""
        region = bank.region_of(controls.at('prog', tick), key)
        if region is None:
            return
        bend = controls.at('bend', tick) * controls.at('range', tick) / 127.0
        pitch = round((key - (region.key if region.kind == 1 else 69) + bend) * 16)
        own = [controls.at(name, tick) for name in Controls.ENVELOPE]
        attack, decay, sustain, release = [mine if mine is not None else theirs for mine, theirs in
                                           zip(own, (region.attack, region.decay, region.sustain, region.release))]
        step = self.rate / UPDATES
        held = max(1, clock.samples(tick + length) - start)
        loudness = (square_law(velocity) * square_law(controls.at('vol', tick)) * square_law(controls.at('expr', tick))
                    * square_law(controls.at('master', tick)))
        gains = gain_curve(int(held / step) + 1, attack, decay, sustain, release) * loudness
        gains[gains <= 1e-5] = 0.0                                   # too quiet to count
        tone = self.tone(region, pitch, int(len(gains) * step) + 2)
        edges = (np.arange(len(gains) + 1) * step).astype(np.int64)       # the engine moves the level at these samples of the note
        count = min(int(edges[-1]), len(tone), len(mix) - start)
        if count > 0:
            mix[start:start + count] += tone[:count] * np.repeat(gains, np.diff(edges))[:count]

    def finish(self, mix, last, scale=1.0):
        """The mix as 16 bit samples, made as loud as is reasonable for the loud parts of the music; what is louder still is rounded
        off softly instead of being cut. `scale` (the volume of the sequence) then makes the whole sound quieter."""
        samples = mix[:last + self.rate // 2]
        top = np.sort(np.abs(samples[::13]))                            # the sound itself, not the silence between the notes
        top = top[top > 0]
        reference = top[int(len(top) * 0.997)] if len(top) else np.abs(samples).max(initial=0)
        if not reference:
            return array('h', bytes(2 * len(samples)))
        loud = np.tanh(samples * (1.1 * LOUDNESS / reference)) * (32767 * scale)
        return array('h', loud.astype(np.int16).tobytes())
