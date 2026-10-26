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
    out = sdat_rebuild(snd.sd, {snd.swar_fid: swar_build(snd.swar, repl)})
    files = rom.files()
    s, e = rom.fat(files[snd.path])
    if len(out) > e - s:
        raise RuntimeError(f'Audio is {len(out) - (e - s):,} bytes too big for the ROM: shorten or downsample the new sounds.')
    rom.d[s:s + len(out)] = out
    rom.set_fat(files[snd.path], s, s + len(out))
    log(f'Audio: {len(new)} sound(s)')
