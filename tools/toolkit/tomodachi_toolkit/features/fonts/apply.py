"""Writes the changes of the Fonts tab (pixels of glyphs, and characters added) into the fonts of the ROM."""

from ..subfiles import apply_subfiles
from .grow import apply_changes, font_bytes


def apply_fonts(rom, cfg, log):
    """cfg: {font file of the ROM: {character code: glyph picture rows}} (see grow.apply_changes)."""
    new = {path: {0: apply_changes(font_bytes(rom, path), glyphs)} for path, glyphs in cfg.items() if glyphs}
    if new:
        apply_subfiles(rom, new, log, 'Font')
