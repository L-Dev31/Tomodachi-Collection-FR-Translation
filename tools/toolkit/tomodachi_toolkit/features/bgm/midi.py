"""Standard MIDI files, read and written with the mido library: just what the sequences need (notes, controllers, programs, pitch bend,
tempo, text)."""
import io
import struct

import mido


class MidiError(ValueError):
    pass


# ----- reading

def read_midi(blob):
    """(ticks per quarter note, events). An event is (tick, track, kind, a, b, c) in file order sorted by time; kinds:
    'on' (channel, key, velocity), 'off' (channel, key, 0), 'cc' (channel, controller, value), 'prog' (channel, program, 0),
    'bend' (channel, 0..16383, 0), 'tempo' (microseconds per quarter note, 0, 0), 'text' (text, 0, 0), 'marker' (text, 0, 0),
    'end' (0, 0, 0)."""
    data = bytes(blob)
    if data[:4] != b'MThd':
        raise MidiError('This is not a MIDI file')
    if len(data) < 14:
        raise MidiError('The MIDI file ends too early')
    kind, division = struct.unpack_from('>HxxH', data, 8)
    if kind not in (0, 1):
        raise MidiError('MIDI files of type %d are not supported (use type 0 or 1)' % kind)
    if division & 0x8000:
        raise MidiError('MIDI files timed in SMPTE frames are not supported')
    if not division:
        raise MidiError('Bad MIDI time division')
    try:
        tracks = mido.MidiFile(file=io.BytesIO(data), clip=True).tracks
    except EOFError:
        raise MidiError('The MIDI file ends too early') from None
    except (OSError, ValueError, KeyError, IndexError, struct.error) as e:
        raise MidiError('Bad MIDI file: %s' % e) from None
    events = []
    for number, track in enumerate(tracks):
        tick = 0
        for msg in track:
            tick += msg.time
            found = _event(msg)
            if found is not None:
                events.append((tick, number) + found)
    events.sort(key=lambda e: e[0])                                  # stable: events of the same tick stay in file order
    return division, events


def _event(msg):
    """(kind, a, b, c) of a message of a file, or None for one the sequences have no use for."""
    kind = msg.type
    if kind == 'note_on':
        return ('on', msg.channel, msg.note, msg.velocity) if msg.velocity else ('off', msg.channel, msg.note, 0)
    if kind == 'note_off':
        return 'off', msg.channel, msg.note, 0
    if kind == 'control_change':
        return 'cc', msg.channel, msg.control, msg.value
    if kind == 'program_change':
        return 'prog', msg.channel, msg.program, 0
    if kind == 'pitchwheel':
        return 'bend', msg.channel, msg.pitch + 8192, 0
    if kind == 'set_tempo':
        return 'tempo', msg.tempo, 0, 0
    if kind in ('text', 'marker'):
        return kind, msg.text, 0, 0
    if kind == 'end_of_track':
        return 'end', 0, 0, 0
    return None


# ----- writing: the messages of a file

def note_on(ch, key, vel):
    return mido.Message('note_on', channel=ch, note=key, velocity=vel)


def note_off(ch, key):
    return mido.Message('note_off', channel=ch, note=key, velocity=0)


def controller(ch, n, v):
    return mido.Message('control_change', channel=ch, control=n, value=v)


def program(ch, v):
    return mido.Message('program_change', channel=ch, program=v)


def pitch_bend(ch, v):
    """v: 0 to 16383, 8192 being no bend."""
    return mido.Message('pitchwheel', channel=ch, pitch=v - 8192)


def tempo(us):
    return mido.MetaMessage('set_tempo', tempo=min(us, 0xFFFFFF))


def meta_text(text, kind=1):
    """A text of a track: kind 1 a text, 3 the name of the track, 6 a marker."""
    text = text.encode('latin1', 'replace').decode('latin1')
    if kind == 3:
        return mido.MetaMessage('track_name', name=text)
    return mido.MetaMessage('marker' if kind == 6 else 'text', text=text)


def time_signature(num=4, den=4):
    return mido.MetaMessage('time_signature', numerator=num, denominator=den)


def write_midi(division, tracks):
    """A type 1 MIDI file. tracks: a list of lists of (tick, message from the functions above); the messages of a track are written in
    the order given (stable for equal ticks)."""
    out = mido.MidiFile(type=1, ticks_per_beat=division)
    for events in tracks:
        track, last = mido.MidiTrack(), 0
        for tick, msg in sorted(events, key=lambda e: e[0]):
            track.append(msg.copy(time=tick - last))
            last = tick
        out.tracks.append(track)
    buffer = io.BytesIO()
    out.save(file=buffer)
    return buffer.getvalue()
