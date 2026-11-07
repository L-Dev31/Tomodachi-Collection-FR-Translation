"""Writes replaced sounds into the ROM."""
import struct

from .sdat import Sound, sdat_rebuild, swar_build, wave_encode


def apply_audio(rom, new, log):
    snd = Sound(rom)
    repl = {}
    for i, a in new.items():
        pcm = list(struct.unpack('<%dh' % (len(a['pcm']) // 2), a['pcm']))
        swav = wave_encode(snd.waves[i], a['rate'], pcm)
        room = snd.waves[i]['end'] - snd.waves[i]['off']
        repl[i] = swav + b'\0' * (room - len(swav)) if len(swav) <= room else swav
    store_sdat(rom, snd, sdat_rebuild(snd.sd, {snd.swar_fid: swar_build(snd.swar, repl)}), log)
    log(f'Audio: {len(new)} sound(s)')


def store_sdat(rom, snd, out, log):
    """Puts a rebuilt sound archive in the ROM, where the old one was. When it grew, the files that follow it move to the end of the image."""
    fid = rom.files()[snd.path]
    s, e = rom.fat(fid)
    rom.grow_file(fid, out)
    if len(out) > e - s:
        log(f'Sound archive: {len(out) - (e - s):,} bytes bigger')
