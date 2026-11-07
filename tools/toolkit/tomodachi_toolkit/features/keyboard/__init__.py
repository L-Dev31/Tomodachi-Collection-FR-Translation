"""The soft keyboard: the order of its tabs and the characters of its keys."""
from .charset import Characters, load_characters
from .edit import LayoutEditor
from .layout import SPECS, Keyboard, LayoutError, apply_layouts, layouts_problem, read_keyboards, text_problem
from .order import KB_FILE, KB_ICON, KB_KIND, KEYBOARDS, apply_order, kb_pixels
from .presets import presets_for
from .textfile import ORDER_FILE, file_name, keyboard_of, layout_from_text, layout_to_text, order_from_text, order_to_text

__all__ = ['Characters', 'load_characters', 'LayoutEditor', 'SPECS', 'Keyboard', 'LayoutError', 'apply_layouts', 'layouts_problem',
           'read_keyboards', 'text_problem', 'KB_FILE', 'KB_ICON', 'KB_KIND', 'KEYBOARDS', 'apply_order', 'kb_pixels', 'presets_for',
           'ORDER_FILE', 'file_name', 'keyboard_of', 'layout_from_text', 'layout_to_text', 'order_from_text', 'order_to_text',
           'keyboard_config', 'apply_keyboard']


def keyboard_config(cfg):
    """(order, layouts) of the keyboard part of a configuration. It is a dict {'order': [...], 'layouts': {...}} (either may be
    left out); an older configuration is the order alone."""
    if isinstance(cfg, dict):
        return cfg.get('order'), cfg.get('layouts') or {}
    return cfg, {}


def apply_keyboard(rom, arm9, cfg, log):
    """Applies the keyboard part of a configuration: the order of the tabs and the characters of the keys."""
    order, layouts = keyboard_config(cfg)
    if order and list(order) != KEYBOARDS:
        apply_order(rom, arm9, order, log)
    if layouts:
        apply_layouts(arm9, layouts, log, load_characters(rom).has)
