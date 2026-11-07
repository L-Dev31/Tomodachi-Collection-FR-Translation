"""A SoundFont (SF2) made from an instrument bank of the game, so that the MIDI file of a sequence sounds like the game in any MIDI player.

A SoundFont is a set of recorded sounds (samples) and of instruments that say which sound plays for which keys and how a note swells and
dies away. A bank of the game (SBNK) says just the same and keeps its sounds in the wave archive (SWAR), so one is turned into the other:
every instrument of the bank becomes the preset that has its program number (the number a sequence picks with a program change), every
part of its keys becomes a zone, and the envelopes of the sound engine become SoundFont envelopes (the numbers of the engine are in
synth.py). A MIDI player looks in bank 128 for the drums of its channel 10, so every preset is in that bank too.
"""
import functools
import math
import random
import struct
import sys
from array import array

from ..audio.sdat import swar_waves, wave_loop_start, wave_pcm
from .synth import DECIBEL, PSG_LEVEL, SILENT, UPDATES, Bank, SynthError, attack_rate, fall_rate, sustain_level

DRUMS = 128                     # the bank the players of MIDI files look in for the drums of channel 10
PAD = 46                        # points the format wants after every sample (the loop goes on in them, silence follows a sample alone)
SHORTEST, SHORTEST_LOOP = 48, 32        # points a sample and its loop have at least, or the players refuse them
PULSE_POINTS = 64               # points in one cycle of a pulse wave
NOISE_STEPS, NOISE_HOLD = 4096, 4       # random levels of the noise and points every level is held for
ROOT = 69                       # the key the pulse and the noise instruments of the engine play at their own pitch: the A of 440 hertz
RATES = (400, 50000)            # the sample rates a SoundFont can have

# the generators (the numbers of the format) a zone is made of
KEY_RANGE, PAN, ATTACK, DECAY, SUSTAIN, RELEASE, INSTRUMENT, SAMPLE_ID, SAMPLE_MODES = 43, 17, 34, 36, 37, 38, 41, 53, 54
COARSE_TUNE, FINE_TUNE = 51, 52


# ----- the numbers of the engine in the units of the format

def timecents(seconds):
    """A time in the unit of the envelopes of a SoundFont (1200 to the octave, 0 is a second), within what they can say."""
    return max(-12000, min(8000, round(1200 * math.log2(max(seconds, 1e-6)))))


@functools.lru_cache(maxsize=None)
def attack_time(number):
    """Seconds the engine takes to open a note, from its attack number, until it is within half a decibel of the full level."""
    rate, level, updates = attack_rate(number), SILENT, 0
    while level < -DECIBEL // 2 and updates < 60 * UPDATES:
        level = -((-level * rate) >> 8)
        updates += 1
    return updates / UPDATES


@functools.lru_cache(maxsize=None)
def fall_time(number):
    """Seconds the engine takes to lower a note by 100 decibels, from its decay or release number: what a SoundFont says for both."""
    return 100 * DECIBEL / (fall_rate(number) * UPDATES)


def sustain_attenuation(number):
    """How far down the decay stops, in centibels, from the sustain number."""
    return max(0, min(1000, round(-sustain_level(number) * 10 / DECIBEL)))


# ----- the sounds

class Waves:
    """The waves of a wave archive as 16 bit samples, decoded the first time they are asked for. Hand the same one to every soundfont
    made from the same archive and each wave is decoded once."""

    def __init__(self, swar):
        self.swar, self.infos, self.found = swar, swar_waves(swar), {}

    def get(self, number):
        """(samples, number of the sample the wave starts again from or None, rate) of a wave; None when it cannot be played."""
        if number not in self.found:
            found = None
            if 0 <= number < len(self.infos) and self.infos[number]['enc'] in (0, 1, 2):
                info = self.infos[number]
                samples = array('h', wave_pcm(self.swar, info))
                start = wave_loop_start(info)
                if samples:
                    found = (samples, start if info['loop'] and 0 <= start < len(samples) else None, max(info['rate'], 1))
            self.found[number] = found
        return self.found[number]


def pulse(width):
    """One cycle of a pulse wave as wide as the number says (1/8 to 8/8 of the cycle)."""
    high = (min(width, 7) + 1) * PULSE_POINTS // 8
    return array('h', [PSG_LEVEL] * high + [-PSG_LEVEL] * (PULSE_POINTS - high))


def noise():
    """Levels at random, held a few points each (the engine changes the level of its noise as often as the pitch says)."""
    rng = random.Random(0)
    levels = [PSG_LEVEL if rng.random() < 0.5 else -PSG_LEVEL for _ in range(NOISE_STEPS)]
    return array('h', [level for level in levels for _ in range(NOISE_HOLD)])


class Samples:
    """The sample data of a SoundFont and the headers of its samples. A sound is written once, however many keys it is the root of."""

    def __init__(self):
        self.data, self.placed, self.headers, self.numbers = array('h'), {}, [], {}

    def number(self, source, key, name, pcm, loop, rate):
        """The number of the sample that plays a sound with `key` as its own pitch. source names the sound; pcm (16 bit points), loop
        (the point it starts again from, or None) and rate say what it is."""
        if (source, key) not in self.numbers:
            if source not in self.placed:
                self.placed[source] = self.place(pcm, loop)
            start, end, loop_start, loop_end = self.placed[source]
            self.numbers[source, key] = len(self.headers)
            self.headers.append((f'{name} k{key}', start, end, loop_start, loop_end, max(RATES[0], min(RATES[1], rate)), min(key, 127)))
        return self.numbers[source, key]

    def place(self, pcm, loop):
        """Writes a sound into the data with what the format wants after it; returns its start, end and loop points."""
        pcm = array('h', pcm)
        if loop is not None:                       # a loop that is too short for the players is repeated until it is long enough
            body = pcm[loop:]
            pcm.extend(body * (-(-max(SHORTEST_LOOP, SHORTEST - loop) // len(body)) - 1))
        elif len(pcm) < SHORTEST:
            pcm.extend([0] * (SHORTEST - len(pcm)))
        start = len(self.data)
        self.data.extend(pcm)
        end = len(self.data)
        if loop is None:
            self.data.extend([0] * PAD)
            return start, end, end - 2, end - 1
        ring = pcm[loop:]
        self.data.extend((ring * (PAD // len(ring) + 1))[:PAD])
        return start, end, start + loop, end


# ----- the instruments

def key_ranges(entry):
    """[(lowest key, highest key, Region)] of an instrument of a Bank: the parts of the keys that have a sound, neighbours that play the
    same sound joined into one."""
    if entry[0] == 'one':
        spans = [(0, 127, entry[1])]
    elif entry[0] == 'range':
        spans = [(entry[1] + i, entry[1] + i, region) for i, region in enumerate(entry[2])]
    else:
        spans, first = [], 0
        for end, region in zip(entry[1], entry[2]):
            spans.append((first, end, region))
            first = end + 1
    out = []
    for low, high, region in spans:
        low, high = max(low, 0), min(high, 127)
        if region is None or low > high:
            continue
        if out and out[-1][1] + 1 == low and all(getattr(out[-1][2], f) == getattr(region, f) for f in region.__slots__):
            out[-1] = (out[-1][0], high, region)
        else:
            out.append((low, high, region))
    return out


def sound_of(region, waves):
    """(source, key, name, pcm, loop, rate) of the sound a region plays, or None when the archive cannot play its wave."""
    if region.kind == 1:
        wave = waves.get(region.wave)
        return None if wave is None else (('wave', region.wave), region.key, f'wave {region.wave}', wave[0], wave[1], wave[2])
    if region.kind == 2:
        return ('pulse', region.wave), ROOT, f'pulse {min(region.wave, 7) + 1}/8', pulse(region.wave), 0, PULSE_POINTS * 440
    return 'noise', ROOT, 'noise', noise(), 0, NOISE_HOLD * 880


def zone(low, high, region, number, looped, rate):
    """The generators of the zone of a region: its keys, pan, envelope, whether its sound repeats, and the sample (always last). The
    zone also tunes the sample when its rate is one a SoundFont cannot say (above 50000 hertz), so that it plays at the pitch it had."""
    pan = max(-500, min(500, round((region.pan - 64) * 500 / 64)))
    tune = round(1200 * math.log2(rate / max(RATES[0], min(RATES[1], rate))))
    gens = [(KEY_RANGE, bytes([low, high]))] if (low, high) != (0, 127) else []
    gens += [(PAN, struct.pack('<h', pan))] if pan else []
    gens += [(COARSE_TUNE, struct.pack('<h', tune // 100)), (FINE_TUNE, struct.pack('<h', tune % 100))] if tune else []
    gens += [(ATTACK, struct.pack('<h', timecents(attack_time(min(region.attack, 127))))),
             (DECAY, struct.pack('<h', timecents(fall_time(min(region.decay, 127))))),
             (SUSTAIN, struct.pack('<H', sustain_attenuation(region.sustain))),
             (RELEASE, struct.pack('<h', timecents(fall_time(min(region.release, 127)))))]
    return gens + ([(SAMPLE_MODES, struct.pack('<H', 1))] if looped else []) + [(SAMPLE_ID, struct.pack('<H', number))]


# ----- the file

def chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')


def text_chunk(tag, text):
    """A text of the INFO list: it ends with a zero, and its size (zero included) is even."""
    data = text.encode('ascii', 'replace') + b'\0'
    return chunk(tag, data + b'\0' * (len(data) % 2))


def listing(kind, *chunks):
    body = kind + b''.join(chunks)
    return b'LIST' + struct.pack('<I', len(body)) + body


def label(text):
    return text.encode('ascii', 'replace')[:19].ljust(20, b'\0')


def tables(entries):
    """(headers, bags, generators) of a list of presets or of instruments: entries is [(zones)] and a zone is a list of generators. A
    header holds the number of the first bag of its entry, a bag the number of the first generator of its zone."""
    firsts, bags, gens = [], [], []
    for zones in entries:
        firsts.append(len(bags))
        for zone_gens in zones:
            bags.append(len(gens))
            gens += zone_gens
    return firsts, bags, gens


def soundfont(bank_data, swar, name='Instruments', waves=None):
    """The bytes of the SoundFont of a bank (the bytes of an SBNK file) with the waves of a wave archive (the bytes of a SWAR file).
    waves: the Waves of that archive when there are some already (to make many soundfonts quickly). Raises SynthError when the bank
    cannot be read or has no instrument that can be played."""
    bank = Bank(bank_data)
    waves = waves or Waves(swar)
    samples, instruments, presets = Samples(), [], []
    for program, entry in sorted(bank.programs.items()):
        zones = []
        for low, high, region in key_ranges(entry):
            sound = sound_of(region, waves)
            if sound is not None:
                source, key, title, pcm, loop, rate = sound
                zones.append(zone(low, high, region, samples.number(source, key, title, pcm, loop, rate), loop is not None, rate))
        if zones:
            instruments.append(zones)
            for kind in (program >> 7, DRUMS) if program < 128 else (program >> 7,):
                presets.append((f'Program {program}', kind, program & 127, len(instruments) - 1))
    if not presets:
        raise SynthError('This bank has no instrument that can be played.')
    presets.sort(key=lambda p: (p[1], p[2]))
    pfirst, pbag, pgen = tables([[[(INSTRUMENT, struct.pack('<H', p[3]))]] for p in presets])
    ifirst, ibag, igen = tables(instruments)
    sound = array('h', samples.data)
    if sys.byteorder == 'big':
        sound.byteswap()
    info = listing(b'INFO', chunk(b'ifil', struct.pack('<HH', 2, 1)), text_chunk(b'isng', 'EMU8000'), text_chunk(b'INAM', name),
                   text_chunk(b'ICMT', 'Made by the Tomodachi Collection toolkit from an instrument bank and the wave archive of the game.'),
                   text_chunk(b'ISFT', 'Tomodachi Collection toolkit'))
    pdta = listing(
        b'pdta',
        chunk(b'phdr', b''.join(label(p[0]) + struct.pack('<HHHIII', p[2], p[1], first, 0, 0, 0) for p, first in zip(presets, pfirst))
              + label('EOP') + struct.pack('<HHHIII', 0, 0, len(pbag), 0, 0, 0)),
        chunk(b'pbag', b''.join(struct.pack('<HH', g, 0) for g in pbag) + struct.pack('<HH', len(pgen), 0)),
        chunk(b'pmod', bytes(10)),
        chunk(b'pgen', b''.join(struct.pack('<H', op) + amount for op, amount in pgen) + bytes(4)),
        chunk(b'inst', b''.join(label(f'Instrument {i}') + struct.pack('<H', first) for i, first in enumerate(ifirst))
              + label('EOI') + struct.pack('<H', len(ibag))),
        chunk(b'ibag', b''.join(struct.pack('<HH', g, 0) for g in ibag) + struct.pack('<HH', len(igen), 0)),
        chunk(b'imod', bytes(10)),
        chunk(b'igen', b''.join(struct.pack('<H', op) + amount for op, amount in igen) + bytes(4)),
        chunk(b'shdr', b''.join(label(n) + struct.pack('<IIIIIBbHH', start, end, a, b, rate, key, 0, 0, 1)
                                for n, start, end, a, b, rate, key in samples.headers)
              + label('EOS') + bytes(26)))
    body = b'sfbk' + info + listing(b'sdta', chunk(b'smpl', sound.tobytes())) + pdta
    return b'RIFF' + struct.pack('<I', len(body)) + body
