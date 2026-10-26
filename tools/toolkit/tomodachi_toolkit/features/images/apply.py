"""Writes replaced images into the ROM."""

from ..subfiles import apply_subfiles


def apply_images(rom, new, log):
    """new: {path: {sub file index: new NCGR bytes}} (see apply_subfiles)."""
    apply_subfiles(rom, new, log, 'Image')
