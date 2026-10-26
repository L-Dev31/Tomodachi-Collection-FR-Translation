"""Applies the speech settings to the ROM: the edited presets (in the ARM9) and the edited lines (in the message files)."""

from .lines import apply_lines
from .presets import preset_tables, preset_write

__all__ = ['apply_lines', 'apply_speech', 'speech_parts']


def speech_parts(cfg):
    """(presets, lines) of the 'speech' part of a configuration or of a project. The part is
    {'presets': {name: script}, 'lines': {path: {index: [old, new]}}}; older projects hold the presets alone."""
    cfg = cfg or {}
    if 'presets' in cfg or 'lines' in cfg:
        return dict(cfg.get('presets') or {}), dict(cfg.get('lines') or {})
    return dict(cfg), {}


def apply_speech(arm9, presets, log=print):
    """Applies edited preset scripts (name -> script) to every copy of the table."""
    bases = preset_tables(arm9)
    if not bases:
        raise RuntimeError('Voice presets not found in this ARM9')
    for name, script in presets.items():
        preset_write(arm9, bases, name, script)
    log(f'Speech: {len(presets)} preset(s)')
