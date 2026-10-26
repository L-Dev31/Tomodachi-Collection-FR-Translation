"""Writes changed models into the ROM."""

from ..subfiles import apply_subfiles


def apply_models(rom, new, log):
    """new: {path: {sub file index: new BMD0 bytes}} (see apply_subfiles)."""
    apply_subfiles(rom, new, log, 'Model')
