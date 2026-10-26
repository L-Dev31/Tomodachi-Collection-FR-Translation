"""The ROM that is open. Read only: every tab keeps its own edits and the patch is built from them."""
import collections
import os
import zlib

from ..core.compression import lz10
from ..core.narc import narc_files
from ..core.rom import Rom
from ..features.audio.sdat import Sound
from ..features.keyboard import KB_FILE


class Session:
    def __init__(self, path, data):
        self.path = path
        self.name = os.path.basename(path)
        self.data = bytes(data)
        self.rom = Rom(self.data)
        self.files = self.rom.files()
        if KB_FILE not in self.files:
            raise ValueError(f'{KB_FILE} is missing: this is not a Tomodachi Collection ROM.')
        self.crc32 = zlib.crc32(self.rom.d)
        self._arm9 = None
        self._sound = None
        self._subs = collections.OrderedDict()

    def arm9(self):
        """The ARM9 program of the original ROM (decompressed)."""
        if self._arm9 is None:
            self._arm9 = self.rom.arm9()
        return self._arm9

    def sound(self):
        """The sound data (SDAT) of the ROM, read the first time it is asked for."""
        if self._sound is None:
            self._sound = Sound(self.rom)
        return self._sound

    def raw(self, path):
        """A file of the ROM as the game reads it (LZ10 files are decompressed)."""
        s, e = self.rom.fat(self.files[path])
        raw = bytes(self.rom.d[s:e])
        return lz10(raw) if raw[:1] == b'\x10' else raw

    def subfiles(self, path):
        """The sub files of a NARC of the ROM, cached for the last few archives used."""
        if path in self._subs:
            self._subs.move_to_end(path)
        else:
            self._subs[path] = narc_files(self.raw(path))
            while len(self._subs) > 6:
                self._subs.popitem(last=False)
        return self._subs[path]
