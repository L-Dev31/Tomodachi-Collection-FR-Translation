"""Text for the speech engine: katakana, the marks of kana.MARKS and <\\Name=value> commands, as Shift-JIS bytes.

The text form of the game's messages (core.bmg.bmg_text) is used everywhere: the game's codes are written {hex} and a
real brace is written twice."""
import re

from .kana import ASCII_MARKS, MARKS, is_kana

# Characters that are in some game lines and that the engine skips: digits, the percent sign and spaces.
IGNORED = '0123456789０１２３４５６７８９%％ \u3000\t'

# A command inside a text: <\Name> or <\Name=value> (one game text has the backslash twice).
TAG_RE = re.compile(r'<\\+([A-Za-z_]+)(?:=([-+]?\d+))?>')

# One piece of a text: a command, a game code, a doubled brace or any other character.
PIECE_RE = re.compile(r'<\\+(?P<tag>[A-Za-z_]+)(?:=(?P<value>[-+]?\d+))?>|\{\{|\}\}|\{(?P<code>[0-9a-fA-F]+)\}|(?P<char>.)', re.S)

# The game codes that stand for a syllable of a song or for a name or a number: they are replaced to listen to a line.
SYLLABLE_CODE = '080101'


def pieces(text):
    """The pieces of a text, in order: ('tag', name, value or None, raw), ('code', hex), ('char', c)."""
    for m in PIECE_RE.finditer(text):
        if m.group('tag'):
            yield 'tag', m.group('tag'), m.group('value'), m.group(0)
        elif m.group('code'):
            yield 'code', m.group('code').lower()
        else:
            yield 'char', {'{{': '{', '}}': '}'}.get(m.group(0), m.group(0))


def is_readable(c):
    """True for a character the engine reads or skips: katakana, the marks (fullwidth or ASCII), digits."""
    return is_kana(c) or c in MARKS or c in ASCII_MARKS or c in IGNORED


def is_speakable(text):
    """True when the engine can read the text as it is: katakana, marks, commands and game codes only, with at
    least one katakana or one code."""
    seen = False
    for piece in pieces(text):
        if piece[0] == 'char':
            if not is_readable(piece[1]):
                return False
            seen = seen or is_kana(piece[1]) and piece[1] != 'ー'
        elif piece[0] == 'code':
            seen = True
    return seen


def tag_text(name, value=None):
    """The command as it is written in a text: '<\\Spd=150>', or '<\\monotone>' when it has no value."""
    return f'<\\{name}' + ('' if value is None else f'={value}') + '>'


def listening_text(text, name='ミー', syllable='ラ'):
    """A line as it is said when it is tried: each game code is replaced by a word (the sample name, or a syllable for
    the codes of songs). Returns text that speech_bytes accepts."""
    out = []
    for piece in pieces(text):
        if piece[0] == 'code':
            out.append(syllable if piece[1].startswith(SYLLABLE_CODE) else name)
        elif piece[0] == 'tag':
            out.append(tag_text(piece[1], piece[2]))
        else:
            out.append(piece[1])
    return ''.join(out)


def speech_bytes(text):
    """A text with commands -> the Shift-JIS bytes the engine reads. Raises ValueError for a character it cannot read."""
    out = []
    for piece in pieces(text):
        if piece[0] == 'tag':
            out.append(tag_text(piece[1], piece[2]))
        elif piece[0] == 'code':
            raise ValueError('The text still has a game code: replace it first (see listening_text).')
        elif is_readable(piece[1]):
            out.append(piece[1])
        else:
            raise ValueError(f'The engine cannot read "{piece[1]}".')
    return ''.join(out).encode('cp932')
