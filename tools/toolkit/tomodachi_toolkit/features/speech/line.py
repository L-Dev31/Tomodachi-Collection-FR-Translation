"""A speech line taken apart for editing: the sounds, the marks and the commands, and how each sound is said.

A line is a list of items. Sounds (moras), marks, game codes (slots), commands (tags) and other characters keep their
order, so a line that nobody touched is written back exactly as it was.

Pitch, length and volume are not stored per sound: the game moves them with the relative commands <\\RPit=n>, <\\RSpd=n>
and <\\RVol=n>, which add up from where they stand to the end of the line. The model reads the running total in front of
each sound, and writes the commands again when a sound is given another value, without moving the sounds after it."""
import collections

from ...core.bmg import bmg_raw
from .kana import ASCII_MARKS, MARKS, is_kana, sounds
from .text import pieces, tag_text

LIMIT = 255      # the longest speech message of the game, in 16 bit characters (codes count for their size)

Item = collections.namedtuple('Item', 'kind text name value')
# kind   'mora'   text: the katakana        'mark'  text: the mark (fullwidth or ASCII)
#        'slot'   text: hex of a game code  'tag'   name, value and text: the command as it was written ('' when made here)
#        'other'  text: a character the engine skips or cannot read
Column = collections.namedtuple('Column', 'index item pitch length volume')

Channel = collections.namedtuple('Channel', 'key tag per lo hi step label unit hint')
CHANNELS = (
    Channel('pitch', 'RPit', 59, -12, 12, 1, 'Pitch', 'semitones', 'Higher or lower, in semitones.'),
    Channel('length', 'RSpd', 1, -50, 150, 10, 'Length', 'points', 'How long the sound lasts. More is slower, less is faster.'),
    Channel('volume', 'RVol', 10, -30, 10, 1, 'Volume', 'dB', 'Louder or quieter, in decibels.'),
)
CHANNEL = {c.key: c for c in CHANNELS}
TAG_CHANNEL = {c.tag: c.key for c in CHANNELS}
ABSOLUTE = {'Pit': 'pitch', 'Spd': 'length', 'Vol': 'volume'}      # commands that set a value instead of moving it
CARRIERS = ('mora', 'slot')                                         # items that have a pitch, a length and a volume


def parse(text):
    """The items of a text (in the form of core.bmg.bmg_text)."""
    items, run = [], ''

    def flush():
        nonlocal run
        items.extend(Item('mora', s, '', None) for s in sounds(run))
        run = ''

    for piece in pieces(text):
        if piece[0] == 'char':
            c = piece[1]
            if is_kana(c):
                run += c
                continue
            flush()
            items.append(Item('mark' if c in MARKS or c in ASCII_MARKS else 'other', c, '', None))
        else:
            flush()
            items.append(Item('tag', piece[3], piece[1], piece[2]) if piece[0] == 'tag' else Item('slot', piece[1], '', None))
    flush()
    return items


def item_text(item):
    """An item as it is written in a text."""
    if item.kind == 'slot':
        return '{' + item.text + '}'
    if item.kind == 'tag':
        return item.text or tag_text(item.name, item.value)
    if item.kind == 'other' and item.text in '{}':
        return item.text * 2
    return item.text


def items_text(items):
    return ''.join(map(item_text, items))


def reading(text):
    """What a line says, for a list: its katakana and marks, the commands left out and the game codes shown as ◇."""
    out = []
    for piece in pieces(text):
        if piece[0] == 'code':
            out.append('◇')
        elif piece[0] == 'char':
            out.append(piece[1])
    return ''.join(out)


class LineModel:
    """One line being edited. Every change can be undone; text() is the original text until something is changed."""

    def __init__(self, text, moods=(), current=None):
        """text: the text in the ROM. current: the text being edited when it is not the one in the ROM (it stays one
        step away from the original: undo goes back to it)."""
        self.original, self.moods = text, frozenset(moods)
        self.items = parse(text)
        self.history = []
        if current is not None and current != text:
            self.history.append(self.items)
            self.items = parse(current)

    # ----- what the line is

    @property
    def edited(self):
        return bool(self.history)

    def text(self):
        return items_text(self.items) if self.history else self.original

    def length(self):
        """Size of the line in the game (16 bit characters), to compare with LIMIT."""
        return len(bmg_raw(items_text(self.items))) // 2

    def mood_index(self):
        """Index of the command that sets the mood of the whole line (a mood name before any sound), or None."""
        for i, it in enumerate(self.items):
            if it.kind != 'tag':
                return None
            if it.name in self.moods and it.value is None:
                return i
        return None

    def mood(self):
        i = self.mood_index()
        return None if i is None else self.items[i].name

    def hidden(self, i):
        """True for the items the strip does not draw: the pitch, length and volume commands and the mood of the line."""
        it = self.items[i]
        return i == self.mood_index() or (it.kind == 'tag' and it.name in TAG_CHANNEL and it.value is not None)

    def columns(self):
        """The items the strip shows, each with its pitch (semitones), length (points) and volume (dB) at that place."""
        state = {c.key: 0 for c in CHANNELS}
        mood, out = self.mood_index(), []
        for i, it in enumerate(self.items):
            if it.kind == 'tag':
                key = TAG_CHANNEL.get(it.name) if it.value is not None else None
                if key:
                    state[key] += int(it.value)
                    continue
                if ABSOLUTE.get(it.name) and it.value is not None:
                    state[ABSOLUTE[it.name]] = 0
            if i != mood:
                out.append(Column(i, it, *(state[c.key] / c.per for c in CHANNELS)))
        return out

    def column_of(self, index):
        """Ordinal of the column that shows the item at index, or of the next one when that item is not shown, else the
        last one (None when there is no column)."""
        cols = self.columns()
        for k, c in enumerate(cols):
            if c.index >= index:
                return k
        return len(cols) - 1 if cols else None

    def next_carrier(self, index):
        return next((j for j in range(index + 1, len(self.items)) if self.items[j].kind in CARRIERS), None)

    def first_carrier(self):
        return next((j for j, it in enumerate(self.items) if it.kind in CARRIERS), None)

    # ----- changes

    def _push(self):
        self.history.append(list(self.items))

    def _tidy(self, index):
        """Writes the items as text and reads them again, so that a small kana that follows a sound joins it (キ and ャ
        are one sound, as the engine reads them). Returns the new index of the item that was at index."""
        cut = len(items_text(self.items[:index + 1]))
        self.items = parse(items_text(self.items))
        total = 0
        for i, it in enumerate(self.items):
            total += len(item_text(it))
            if total >= cut:
                return i
        return len(self.items) - 1

    def _keep(self):
        """Takes back the change just made when the line became too long."""
        if self.length() > LIMIT:
            self.items = self.history.pop()
            raise ValueError(f'A speech line can hold {LIMIT} characters at most.')

    def undo(self):
        if self.history:
            self.items = self.history.pop()

    def revert(self):
        self.items, self.history = parse(self.original), []

    def clear(self):
        if self.items:
            self._push()
            self.items = []

    def insert(self, at, text):
        """Puts the items of text (sounds, marks) in front of the item at index at. Returns the index of the last new item."""
        new = parse(text)
        if not new:
            return at - 1
        self._push()
        self.items[at:at] = new
        last = self._tidy(at + len(new) - 1)
        self._keep()
        return last

    def replace(self, index, text):
        """Replaces the item at index by the items of text. Returns the index of the last new item."""
        new = parse(text)
        self._push()
        self.items[index:index + 1] = new
        last = self._tidy(index + len(new) - 1)
        self._keep()
        return last

    def delete(self, index):
        self._push()
        del self.items[index]
        self._tidy(index - 1)

    def add_tag(self, at, name, value=None):
        """Puts a command in front of the item at index at. Returns its index."""
        self._push()
        self.items.insert(at, Item('tag', '', name, None if value is None else str(value)))
        self._keep()
        return at

    def set_tag(self, index, value):
        """Gives the command at index another value."""
        it = self.items[index]
        self._push()
        self.items[index] = Item('tag', '', it.name, None if value is None else str(value))

    def set_mood(self, name):
        """Sets the mood of the whole line (a mood name), or removes it (None)."""
        i = self.mood_index()
        if (None if i is None else self.items[i].name) == name:
            return
        self._push()
        if i is not None:
            del self.items[i]
        if name:
            self.items.insert(0, Item('tag', '', name, None))

    # ----- pitch, length, volume

    def running(self, index, key):
        """The running total of a channel in front of the item at index, in the units of the commands."""
        tag, channel, total = CHANNEL[key].tag, key, 0
        for it in self.items[:index]:
            if it.kind == 'tag' and it.value is not None:
                if it.name == tag:
                    total += int(it.value)
                elif ABSOLUTE.get(it.name) == channel:
                    total = 0
        return total

    def _shift(self, at, key, delta):
        """Adds delta to the running total of a channel from the item at index at on, by changing the command just
        before it (or making one). Returns the new index of the item that was at index at."""
        tag, k = CHANNEL[key].tag, at
        while k > 0 and self.items[k - 1].kind == 'tag':
            k -= 1
            it = self.items[k]
            if it.name == tag and it.value is not None:
                total = int(it.value) + delta
                if total:
                    self.items[k] = Item('tag', '', tag, str(total))
                    return at
                del self.items[k]
                return at - 1
            if ABSOLUTE.get(it.name) == key and it.value is not None:
                break
        self.items.insert(at, Item('tag', '', tag, str(delta)))
        return at + 1

    def _sets_between(self, first, last, key):
        """True when a command that sets (not moves) this channel stands between two items: what comes before it no
        longer counts after it."""
        return any(it.kind == 'tag' and it.value is not None and ABSOLUTE.get(it.name) == key for it in self.items[first + 1:last])

    def set_value(self, index, key, value):
        """Makes the sound at index be said with this pitch (semitones), length (points) or volume (dB). The sounds
        after it keep the values they had."""
        c = CHANNEL[key]
        if self.items[index].kind not in CARRIERS:
            raise ValueError('Only a sound has a pitch, a length and a volume.')
        delta = round(value * c.per) - self.running(index, key)
        if not delta:
            return
        self._push()
        index = self._shift(index, key, delta)
        after = self.next_carrier(index)
        if after is not None and not self._sets_between(index, after, key):
            self._shift(after, key, -delta)
        self._keep()

    def shift_all(self, key, amount):
        """Moves the whole line by amount (semitones, points or dB)."""
        first = self.first_carrier()
        delta = round(amount * CHANNEL[key].per)
        if first is not None and delta:
            self._push()
            self._shift(first, key, delta)
            self._keep()

    def reset_channel(self, key):
        """Removes every move of a channel: all the sounds are said with the normal pitch, length or volume."""
        tag = CHANNEL[key].tag
        if any(it.kind == 'tag' and it.name == tag and it.value is not None for it in self.items):
            self._push()
            self.items = [it for it in self.items if not (it.kind == 'tag' and it.name == tag and it.value is not None)]
