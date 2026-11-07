"""The sequences of the sound archive: their names, banks and files."""
import struct

from ...core.binary import u32
from ..audio.sdat import sdat_file


class SequenceInfo:
    """One sequence: `index` (its number in the archive), `name`, `fid` (its file), `bank` (number) and `bank_name`, `volume`, `player`
    (the name of its player: BGM, SE ...), `size` (bytes of the file)."""
    __slots__ = ('index', 'name', 'fid', 'bank', 'bank_name', 'volume', 'player', 'size')


def sequences(snd):
    """The SequenceInfo of every sequence of a Sound, in archive order."""
    out = []
    for i, o in enumerate(snd.infos[0]):
        if o is None:
            continue
        fid, bank, volume, cpr, ppr, player = struct.unpack_from('<IHBBBB', snd.sd, o)
        s = SequenceInfo()
        s.index, s.fid, s.bank, s.volume = i, fid & 0xFFFFFF, bank, volume
        s.name = snd.names[0][i] or 'SEQ_%03d' % i
        banks = snd.names.get(2, [])
        s.bank_name = banks[bank] if bank < len(banks) and banks[bank] else 'BANK_%d' % bank
        players = snd.names.get(4, [])
        s.player = (players[player] if player < len(players) and players[player] else 'PLAYER_%d' % player).replace('PLAYER_', '')
        s.size = snd.fat[s.fid][1]
        out.append(s)
    return out


def sequence_file(snd, info):
    """The SSEQ file of a sequence of the original archive."""
    return bytes(sdat_file(snd.sd, snd.fat, info.fid))


def bank_names(snd):
    """[(bank number, name)] of the banks of the archive."""
    return [(i, n) for i, n in enumerate(snd.names.get(2, [])) if n]


def bank_file(snd, bank):
    """The SBNK file (the instruments) of a bank of the archive. Raises IndexError or TypeError when the archive has no such bank."""
    return bytes(sdat_file(snd.sd, snd.fat, u32(snd.sd, snd.infos[2][bank]) & 0xFFFFFF))


def bank_programs(snd, bank):
    """The numbers of the instruments a bank defines (a sequence picks one with a program change)."""
    try:
        b = bank_file(snd, bank)
        return {i for i in range(u32(b, 0x38)) if b[0x3C + 4 * i]}
    except (IndexError, TypeError, struct.error):
        return set()
