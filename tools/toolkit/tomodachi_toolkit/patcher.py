"""Builds the patched ROM from a configuration."""

from .features.currency.apply import apply_currency
from .features.images.apply import apply_images
from .features.models.apply import apply_models
from .features.speech.apply import apply_lines, apply_speech, speech_parts
from .features.audio.apply import apply_audio
from .features.keyboard import apply_keyboard
from .features.meta import apply_meta
from .features.bmg import apply_bmg
from .core.rom import Rom


def patch(data, cfg, log=print):
    """The ROM bytes with every part of cfg applied. cfg keys: currency, keyboard, meta, bmg, images, models, audio, speech."""
    rom = Rom(data)
    arm9 = bytearray(rom.arm9())
    if 'currency' in cfg:
        apply_currency(rom, arm9, cfg['currency'], log)
    if 'keyboard' in cfg:
        apply_keyboard(rom, arm9, cfg['keyboard'], log)
    if 'meta' in cfg:
        apply_meta(rom, cfg['meta'], log)
    if 'bmg' in cfg:
        apply_bmg(rom, cfg['bmg'], log)
    if 'images' in cfg:
        apply_images(rom, cfg['images'], log)
    if 'models' in cfg:
        apply_models(rom, cfg['models'], log)
    if 'audio' in cfg:
        apply_audio(rom, cfg['audio'], log)
    if 'speech' in cfg:
        presets, lines = speech_parts(cfg['speech'])
        if presets:
            apply_speech(arm9, presets, log)
        if lines:
            apply_lines(rom, lines, log)
    rom.set_arm9(bytes(arm9))
    return rom.save()
