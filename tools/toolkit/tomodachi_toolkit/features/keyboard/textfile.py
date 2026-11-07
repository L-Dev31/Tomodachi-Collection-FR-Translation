"""A keyboard layout as a text file a person can read and edit: one line per row of keys, one word per key."""
import re
import unicodedata

from .layout import SPECS, usable_code
from .order import KEYBOARDS


HEAD = 'Tomodachi Collection keyboard: '


NOTE = ('# One line per row of the keyboard, one word per key, from left to right.\n'
        '# A word is the character itself, or U+ and its code (U+00E9). U+0020 is a key that types nothing.\n')


def word(ch, first=False):
    """How a character is written in a layout file (first: it starts a line, where # and [ would be taken for something else)."""
    if unicodedata.category(ch)[0] in 'CZM' or first and ch in '#[':
        return f'U+{ord(ch):04X}'
    return ch


def file_name(keyboard):
    """The name of the file that holds a keyboard, in a folder of layouts."""
    return f'{keyboard.name}.txt'


def layout_to_text(keyboard, layers=None):
    """The text file of a Keyboard. layers: {layer: string} (the characters the keyboard has now when left out)."""
    layers = layers or keyboard.text
    out = [HEAD + keyboard.name, NOTE]
    for layer, label in keyboard.layers:
        out.append(f'[{label}]')
        out += [' '.join(word(ch, i == 0) for i, ch in enumerate(row)) for row in keyboard.split(layers[layer])]
        out.append('')
    return '\n'.join(out)


def parse_word(token, line):
    """The character a word of a layout file stands for. Raises ValueError (with the line number) when it stands for none."""
    m = re.fullmatch(r'[Uu]\+([0-9A-Fa-f]{4})', token)
    ch = chr(int(m.group(1), 16)) if m else token
    if len(ch) != 1:
        raise ValueError(f'Line {line}: "{token}" is not one character (write U+ and its code for the others)')
    if not usable_code(ord(ch)):
        raise ValueError(f'Line {line}: U+{ord(ch):04X} cannot be typed')
    return ch


def layout_from_text(keyboard, content, usable=None):
    """{layer: string} read from the text file of a keyboard (the layers the file does not have are left out). Raises
    ValueError with the line and the reason when the file is not a layout of this keyboard. usable tells which characters
    the game can draw."""
    by_label = {label.lower(): key for key, label in keyboard.layers}
    by_label.update({key: key for key, _ in keyboard.layers})
    current, rows, found = None, [], {}

    def close(line):
        if current is not None:
            try:
                found[current] = keyboard.join(rows)
            except ValueError as e:
                raise ValueError(f'Layer {keyboard.label(current)} (line {line}): {e}') from None

    lines = content.splitlines()
    for number, text in enumerate(lines, 1):
        text = text.strip()
        if not text:
            continue
        if text.startswith(HEAD):
            if text[len(HEAD):].strip() != keyboard.name:
                raise ValueError(f'This file is the {text[len(HEAD):].strip()} keyboard, not the {keyboard.name} one')
            continue
        if text.startswith('#'):
            continue
        if text.startswith('['):
            close(number)
            label = text.strip('[] ').lower()
            if label not in by_label:
                raise ValueError(f'Line {number}: the {keyboard.name} keyboard has no layer called {text}')
            current, rows = by_label[label], []
            continue
        if current is None:
            raise ValueError(f'Line {number}: the keys come after a layer name such as [{keyboard.layers[0][1]}]')
        rows.append([parse_word(token, number) for token in text.split()])
    close(len(lines))
    if not found:
        raise ValueError(f'No layer of the {keyboard.name} keyboard in this file')
    if usable is not None:
        for layer, text in found.items():
            for ch in text:
                if not usable(ch):
                    raise ValueError(f'{keyboard.label(layer)}: the game cannot draw U+{ord(ch):04X} ({ch})')
    return found


def keyboard_of(content):
    """The name of the keyboard a layout file is for (None when it does not say)."""
    for text in content.splitlines():
        if text.startswith(HEAD):
            name = text[len(HEAD):].strip()
            return name if name in SPECS else None
    return None


ORDER_FILE = 'Order.txt'

ORDER_NOTE = ('# The tabs of the keyboard, from top to bottom: every keyboard once.\n'
              '# Move a line to move a tab.\n')


def order_to_text(order):
    """The text file of the order of the tabs of the keyboard."""
    return ORDER_NOTE + '\n'.join(order) + '\n'


def order_from_text(content):
    """The order of the tabs a text file writes (a list of keyboard names). Raises ValueError when it is not each keyboard once."""
    names = {name.lower(): name for name in KEYBOARDS}
    order = []
    for number, text in enumerate(content.splitlines(), 1):
        text = text.strip()
        if not text or text.startswith('#'):
            continue
        if text.lower() not in names:
            raise ValueError(f'Line {number}: "{text}" is not a keyboard ({", ".join(KEYBOARDS)})')
        order.append(names[text.lower()])
    if sorted(order) != sorted(KEYBOARDS):
        raise ValueError(f'The order has to list every keyboard once ({", ".join(KEYBOARDS)})')
    return order
