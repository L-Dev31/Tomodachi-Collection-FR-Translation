"""Writes replaced sequences into the ROM."""
import struct

from ...core.binary import u32
from ..audio.apply import store_sdat
from ..audio.sdat import Sound, sdat_rebuild


def apply_bgm(rom, new, log):
    """new: {sequence number: {'file': SSEQ file or None, 'bank': bank number or None, 'volume': 0..127 or None}}."""
    snd = Sound(rom)
    sd = bytearray(snd.sd)
    repl = {}
    for i, edit in sorted(new.items()):
        if not 0 <= i < len(snd.infos[0]) or snd.infos[0][i] is None:
            raise RuntimeError(f'Sequence {i} does not exist in this ROM')
        o = snd.infos[0][i]
        if edit.get('bank') is not None:
            struct.pack_into('<H', sd, o + 4, edit['bank'])
        if edit.get('volume') is not None:
            sd[o + 6] = edit['volume']
        if edit.get('file'):
            repl[u32(sd, o) & 0xFFFFFF] = bytes(edit['file'])
    store_sdat(rom, snd, sdat_rebuild(bytes(sd), repl), log)
    log(f'BGM: {len(new)} sequence(s)')
