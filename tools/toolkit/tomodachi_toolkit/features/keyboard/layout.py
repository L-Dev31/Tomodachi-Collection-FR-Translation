"""Which character each key of the soft keyboards types and shows.

For every keyboard the game keeps one table of characters per layer in its ARM9 program (UTF-16, one entry per key, after a
byte order mark) and, apart from them, the rectangle of every key on the touch screen. A key is drawn with the character of
the table and types it, so changing a table changes both. The rectangles are what the pictures of the keyboards are made for,
so they stay as they are: the keys can change their characters and swap places, but the keyboards keep their shape.
"""
import struct

from ...core.binary import u16, u32


BASE = 0x02000000
MARK = 0xFEFF


class LayoutError(ValueError):
    """The keyboard tables are not where this toolkit expects them (another version of the game)."""


# keyboard: (address of its descriptor, number of keys that type a character, [(layer, label, address of its table)])
SPECS = {
    'QWERTY': (0x021129DC, 45, (('lower', 'Lowercase', 0x02111E5C), ('caps', 'Caps', 0x02111E00), ('shift', 'Shift', 0x02111EB8))),
    'Japanese': (0x021129EC, 51, (('hiragana', 'Hiragana', 0x02111F84), ('katakana', 'Katakana', 0x02111FEC))),
    'Accents': (0x021129FC, 52, (('accents', 'Accents', 0x02111F14),)),
    'Symbols': (0x02112A0C, 51, (('symbols', 'Symbols', 0x021120C4),)),
    'Emojis': (0x02112A1C, 55, (('emojis', 'Emojis', 0x02112054),)),
}


# the keys that do not type a character, by number (the others are numbered after them)
FUNCTION_KEYS = {
    'QWERTY': {1: 'Delete', 2: 'Space', 3: 'Shift', 4: 'Caps'},
    'Japanese': {1: 'Delete', 2: 'Space'},
    'Accents': {1: 'Delete', 2: 'Space'},
    'Symbols': {1: 'Delete', 2: 'Space'},
    'Emojis': {1: 'Delete', 2: 'Space'},
}


def usable_code(code):
    """True for a character code a key can type: not a control character (the game types nothing for those), not half of a
    surrogate pair, not a byte order mark."""
    return 0x20 <= code <= 0xFFFD and not 0xD800 <= code <= 0xDFFF and code != MARK


class Key:
    """A key: where it is on the touch screen (x, y, w, h in pixels), its number in the game and, for a key that types a
    character, `index`: its place in the tables (None for the function keys: delete, space, shift...)."""
    __slots__ = ('number', 'x', 'y', 'w', 'h', 'index')

    def __init__(self, number, x, y, w, h, index):
        self.number, self.x, self.y, self.w, self.h, self.index = number, x, y, w, h, index


class Keyboard:
    """One soft keyboard.

    name     'QWERTY', 'Japanese', 'Accents', 'Symbols' or 'Emojis'
    layers   [(layer, label)]: the sets of characters the keyboard switches between
    keys     every key, by number
    typing   the keys that type a character, by index
    text     {layer: string of one character per typing key, by index}
    """

    def __init__(self, name, layers, keys, text):
        self.name, self.layers, self.keys, self.text = name, list(layers), list(keys), dict(text)
        self.typing = sorted((k for k in keys if k.index is not None), key=lambda k: k.index)
        self.size = len(self.typing)

    def rows(self):
        """The typing keys as the rows of the screen, each from left to right."""
        rows = {}
        for k in self.typing:
            rows.setdefault(k.y, []).append(k)
        return [sorted(rows[y], key=lambda k: k.x) for y in sorted(rows)]

    def shape(self):
        """How many keys each row of the screen has."""
        return [len(row) for row in self.rows()]

    def split(self, text):
        """A string of one character per key (by index) as one string per row of the screen."""
        return [''.join(text[k.index] for k in row) for row in self.rows()]

    def join(self, rows):
        """What split undoes. rows: one string (or list of characters) per row. Raises ValueError for another shape."""
        if [len(row) for row in rows] != self.shape():
            raise ValueError(f'The {self.name} keyboard has rows of {", ".join(map(str, self.shape()))} keys')
        out = [''] * self.size
        for keys, row in zip(self.rows(), rows):
            for k, ch in zip(keys, row):
                out[k.index] = ch
        return ''.join(out)

    def label(self, layer):
        return dict(self.layers)[layer]

    def function_name(self, key):
        return FUNCTION_KEYS.get(self.name, {}).get(key.number, '')


def read_keyboard(arm9, name):
    """The Keyboard `name` as the ARM9 program (bytes) holds it. Raises LayoutError when the tables are not recognised."""
    descriptor, size, layers = SPECS[name]
    try:
        table, specials = u32(arm9, descriptor - BASE), u16(arm9, descriptor - BASE + 12)
        keys, o = [], table - BASE
        while 0 <= o <= len(arm9) - 8:
            x, y, w, h, _, number = struct.unpack_from('<BBBBHH', arm9, o)
            if number != len(keys) + 1 or not w or not h:
                break
            keys.append(Key(number, x, y, w, h, number - specials - 1 if number > specials else None))
            o += 8
        if len(keys) - specials != size or specials < 0:
            raise LayoutError(f'The {name} keyboard has a different number of keys')
        text = {}
        for layer, _, address in layers:
            if u16(arm9, address - BASE) != MARK:
                raise LayoutError(f'The {name} characters are not where they are expected')
            codes = struct.unpack_from(f'<{size}H', arm9, address - BASE + 2)
            if not all(usable_code(c) for c in codes):
                raise LayoutError(f'The {name} characters are not recognised')
            text[layer] = ''.join(map(chr, codes))
    except struct.error:
        raise LayoutError(f'The {name} keyboard is not in this program') from None
    return Keyboard(name, [(layer, label) for layer, label, _ in layers], keys, text)


def read_keyboards(arm9):
    """{name: Keyboard} of the five keyboards of an ARM9 program. Raises LayoutError when its tables are not recognised."""
    return {name: read_keyboard(arm9, name) for name in SPECS}


def text_problem(size, text, usable=None):
    """Why `text` cannot be the characters of a layer of `size` keys (None when it can). usable: a function that tells whether
    the game can draw a character."""
    if not isinstance(text, str) or len(text) != size:
        return f'a layer has {size} keys'
    for ch in text:
        if not usable_code(ord(ch)):
            return f'U+{ord(ch):04X} cannot be typed'
        if usable is not None and not usable(ch):
            return f'the game cannot draw U+{ord(ch):04X}'
    return None


def layouts_problem(layouts, usable=None):
    """Why `layouts` ({keyboard: {layer: text}}) is not a set of key layouts the toolkit can write (None when it is)."""
    if not isinstance(layouts, dict):
        return 'bad keyboard layouts'
    for name, layers in layouts.items():
        if name not in SPECS or not isinstance(layers, dict):
            return f'unknown keyboard {name}'
        known = {layer: None for layer, _, _ in SPECS[name][2]}
        for layer, text in layers.items():
            if layer not in known:
                return f'unknown layer {layer} of the {name} keyboard'
            problem = text_problem(SPECS[name][1], text, usable)
            if problem:
                return f'{name}, {layer}: {problem}'
    return None


def apply_layouts(arm9, layouts, log=print, usable=None):
    """Writes the characters of `layouts` ({keyboard: {layer: string of one character per key}}) into arm9 (a bytearray)."""
    problem = layouts_problem(layouts, usable)
    if problem:
        raise ValueError(problem[0].upper() + problem[1:])
    read_keyboards(arm9)
    for name, layers in layouts.items():
        for layer, _, address in SPECS[name][2]:
            if layer in layers:
                struct.pack_into(f'<{len(layers[layer])}H', arm9, address - BASE + 2, *map(ord, layers[layer]))
        if layers:
            log(f'Keyboard layout: {name}')
