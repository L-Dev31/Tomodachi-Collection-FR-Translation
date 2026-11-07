"""The ROM that is open. Read only: every tab keeps its own edits and the patch is built from them."""
import collections
import os
import zlib

from ..core.compression import lz10
from ..core.narc import narc_files
from ..core.rom import Rom
from ..features.audio.sdat import Sound
from ..features.currency.symbols import load_symbols
from ..features.keyboard import KB_FILE, LayoutError, load_characters, read_keyboards


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
        self._keyboards = None
        self._characters = None
        self._symbols = None
        self._sound = None
        self._subs = collections.OrderedDict()

    def arm9(self):
        """The ARM9 program of the original ROM (decompressed)."""
        if self._arm9 is None:
            self._arm9 = self.rom.arm9()
        return self._arm9

    def keyboards(self):
        """The soft keyboards of the ROM with the characters of their keys (None when its tables are not where the toolkit looks)."""
        if self._keyboards is None:
            try:
                self._keyboards = read_keyboards(self.arm9())
            except LayoutError:
                self._keyboards = False
        return self._keyboards or None

    def set_font_changes(self, added):
        """The characters the Fonts tab added ({font file: {code: rows}}): the keyboard and the text see them at once. The ROM is
        changed only by the patch."""
        from ..features.fonts.grow import FONT_FILES, patched_font
        from ..features.keyboard.charset import Characters
        key_font, text_font = FONT_FILES[1], FONT_FILES[0]
        self._characters = Characters(patched_font(self.rom, key_font, added.get(key_font)), patched_font(self.rom, text_font, added.get(text_font)))
        self._symbols = None

    def characters(self):
        """The characters the game can draw (features/keyboard/charset.py), read the first time they are asked for."""
        if self._characters is None:
            self._characters = load_characters(self.rom)
        return self._characters

    def symbols(self):
        """The characters that can be the symbol of the money (features/currency/symbols.py), read the first time they are asked for."""
        if self._symbols is None:
            self._symbols = load_symbols(self.rom)
        return self._symbols

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
