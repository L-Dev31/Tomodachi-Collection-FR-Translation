"""The characters the game can draw: what a key can be given."""
import unicodedata

from ...core.compression import lz10
from ...core.narc import narc_files
from ...core.nftr import Font


KEY_FONT = '/Cmn/Font/FontLD10x_LZ.bin'
TEXT_FONT = '/Cmn/Font/FontLD12x_LZ.bin'


CATEGORIES = ('Letters', 'Accented letters', 'Numbers', 'Punctuation', 'Symbols', 'Arrows and shapes', 'Game icons',
              'Hiragana', 'Katakana', 'Kanji', 'Greek and Cyrillic', 'Full width', 'Other')


def load_font(rom, path):
    """The Font of a font file of the ROM."""
    s, e = rom.fat(rom.files()[path])
    raw = bytes(rom.d[s:e])
    return Font(narc_files(lz10(raw) if raw[:1] == b'\x10' else raw)[0])


def category(ch):
    """The name (one of CATEGORIES) of the group a character is listed in."""
    c = ord(ch)
    if 0xE000 <= c <= 0xF8FF:
        return 'Game icons'
    if 0x3041 <= c <= 0x309F:
        return 'Hiragana'
    if 0x30A0 <= c <= 0x30FF:
        return 'Katakana'
    if 0x3400 <= c <= 0x9FFF and unicodedata.category(ch) == 'Lo':
        return 'Kanji'
    if 0x370 <= c <= 0x52F:
        return 'Greek and Cyrillic'
    if 0xFF00 <= c <= 0xFFEF:
        return 'Full width'
    kind = unicodedata.category(ch)
    if kind[0] == 'L':
        return 'Letters' if c < 0x80 else 'Accented letters'
    if kind[0] == 'N':
        return 'Numbers'
    if kind[0] == 'P':
        return 'Punctuation'
    if 0x2190 <= c <= 0x21FF or 0x2500 <= c <= 0x27BF:
        return 'Arrows and shapes'
    if kind[0] == 'S':
        return 'Symbols'
    return 'Other'


def name(ch):
    """What the character is, in words."""
    c = ord(ch)
    if 0xE000 <= c <= 0xF8FF:
        return f'Game icon {c:04X}'
    return unicodedata.name(ch, '').title() or f'Character {c:04X}'


def code_of(query):
    """The character code a search text writes (e9, 0xE9, U+00E9), or None."""
    q = query.strip().lower()
    for prefix in ('u+', '0x'):
        if q.startswith(prefix):
            q = q[2:]
    if 2 <= len(q) <= 4 and all(c in '0123456789abcdef' for c in q):
        return int(q, 16)
    return None


class Characters:
    """The characters a key can be given: those the font of the keys and the font of the message windows both draw (a name
    typed on a key has to be readable wherever the game shows it). More fonts narrow the list down to what they all draw."""

    def __init__(self, key_font, *other_fonts):
        self.font = key_font
        self.codes = frozenset(key_font.codes).intersection(*(f.codes for f in other_fonts))
        self.all = sorted(chr(c) for c in self.codes if c > 0x20)
        self._names = {}

    def has(self, ch):
        return isinstance(ch, str) and len(ch) == 1 and ord(ch) in self.codes

    def listing(self, group=None, query=''):
        """The characters of a group (all of them for None) that match the search text: the character itself, its code (e9,
        U+00E9) or the words of its name."""
        words = query.lower().split()
        code = code_of(query)
        out = []
        for ch in self.all:
            if group is not None and category(ch) != group:
                continue
            if words:
                if ch == query.strip() or ord(ch) == code:
                    out.append(ch)
                elif all(w in self.name(ch).lower() for w in words):
                    out.append(ch)
            else:
                out.append(ch)
        return out

    def name(self, ch):
        if ch not in self._names:
            self._names[ch] = name(ch)
        return self._names[ch]

    def groups(self):
        """[(group, how many characters)] of the groups that have some."""
        count = {}
        for ch in self.all:
            count[category(ch)] = count.get(category(ch), 0) + 1
        return [(g, count[g]) for g in CATEGORIES if g in count]


def load_characters(rom):
    """The Characters of a ROM (a Rom)."""
    return Characters(load_font(rom, KEY_FONT), load_font(rom, TEXT_FONT))
