"""The characters that can be the symbol of the money."""
from ..keyboard.charset import Characters, load_font
from .glyphs import FONTS


def load_symbols(rom):
    """The Characters (features/keyboard/charset.py) that every font the symbol is written into draws, because the glyph of the symbol
    is copied into each of them (a Rom)."""
    small, key, text = (load_font(rom, path) for path in FONTS)
    return Characters(key, small, text)
