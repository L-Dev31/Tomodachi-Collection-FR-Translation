"""The line being edited and the selected block. The pages of the tab only draw them and call these methods.

Nothing here draws anything: moved() is called when the selection (or a message) changed, changed() when the text of
the line changed."""
from ....features.speech.line import CARRIERS, CHANNEL, LineModel


class LineEditor:
    def __init__(self, moods=(), changed=None, moved=None):
        self.moods = tuple(moods)
        self.changed = changed or (lambda: None)
        self.moved = moved or (lambda: None)
        self.model = None
        self.sel = None          # ordinal of the selected column (see LineModel.columns), None when there is none
        self.error = ''          # why the last change was refused
        self.drag = None         # length of the undo history when the painting of a graph started

    # ----- the line

    def open(self, text, current=None):
        """Starts editing a line. text: its text in the ROM; current: its text when it already has changes."""
        self.model = LineModel(text, self.moods, current)
        self.sel, self.error, self.drag = None, '', None

    def close(self):
        self.model = self.sel = self.drag = None
        self.error = ''

    @property
    def active(self):
        return self.model is not None

    def columns(self):
        return self.model.columns() if self.model is not None else []

    def index(self):
        """Index in the line of the selected item, or None."""
        cols = self.columns()
        return cols[self.sel].index if self.sel is not None and self.sel < len(cols) else None

    def item(self):
        """The selected item, or None."""
        i = self.index()
        return None if i is None else self.model.items[i]

    # ----- selection

    def select(self, k):
        cols = self.columns()
        self.sel = k if k is not None and 0 <= k < len(cols) else None
        self.drag = None
        self.moved()

    def step(self, direction):
        """Moves the selection to the previous (-1) or next (+1) block."""
        n = len(self.columns())
        if not n:
            return
        if self.sel is None:
            self.select(n - 1 if direction < 0 else 0)
        else:
            self.select(max(0, min(n - 1, self.sel + direction)))

    def key(self, name, channel=None):
        """A key pressed on a strip. channel is the channel its graph shows (None when it has no graph)."""
        if self.model is None:
            return
        if name == 'Left':
            self.step(-1)
        elif name == 'Right':
            self.step(1)
        elif name in ('Up', 'Down') and channel:
            self.nudge(channel, 1 if name == 'Up' else -1)
        elif name in ('Delete', 'BackSpace'):
            self.delete()

    # ----- changes

    def attempt(self, action):
        """Runs action(model). A change the model refuses (ValueError) is kept in self.error. Returns (done, result)."""
        try:
            result = action(self.model)
        except ValueError as e:
            self.error = str(e)
            self.moved()
            return False, None
        self.error = ''
        return True, result

    def done(self):
        """Keeps the selection inside the line and tells that the text changed."""
        n = len(self.columns())
        if self.sel is not None and self.sel >= n:
            self.sel = n - 1 if n else None
        self.changed()

    def put(self, text, mode='after'):
        """Puts the sounds or marks of text in the line: after or before the selected block ('after', 'before') or
        instead of it ('replace'). With no block selected they go to the end of the line."""
        m, i = self.model, self.index()
        if i is None:
            ok, last = self.attempt(lambda m: m.insert(len(m.items), text))
        elif mode == 'replace':
            ok, last = self.attempt(lambda m: m.replace(i, text))
        else:
            at, kept = (i, m.items[i]) if mode == 'before' else (i + 1, None)
            ok, last = self.attempt(lambda m: m.insert(at, text))
            if ok and kept is not None and last + 1 < len(m.items) and m.items[last + 1] == kept:
                last += 1                         # the selection stays on the block, the new ones are in front of it
        if ok:
            self.sel = m.column_of(last)
            self.done()

    def delete(self):
        i = self.index()
        if i is not None and self.attempt(lambda m: m.delete(i))[0]:
            self.done()

    def clear(self):
        if self.model.items and self.attempt(lambda m: m.clear())[0]:
            self.sel = None
            self.done()

    def undo(self):
        if self.model is not None and self.model.history:
            self.model.undo()
            self.error = ''
            self.done()

    def revert(self):
        if self.model is not None and self.model.edited:
            self.model.revert()
            self.error = ''
            self.sel = None
            self.done()

    # ----- pitch, length and volume

    def paint(self, k, key, value, first=True):
        """Gives the sound in column k this value of a channel. A whole drag over a graph is one step of undo."""
        cols = self.columns()
        if not 0 <= k < len(cols) or cols[k].item.kind not in CARRIERS:
            return
        m = self.model
        if first or self.drag is None:
            self.drag = len(m.history)
        ok, _ = self.attempt(lambda m: m.set_value(cols[k].index, key, value))
        if ok and len(m.history) > self.drag + 1:
            del m.history[self.drag + 1:]
        self.sel = k
        if ok:
            self.done()

    def nudge(self, key, steps):
        """Moves the value of the selected sound by steps of the channel."""
        cols, k = self.columns(), self.sel
        if k is None or cols[k].item.kind not in CARRIERS:
            return
        c = CHANNEL[key]
        value = round(getattr(cols[k], key) / c.step) * c.step + steps * c.step
        self.paint(k, key, max(c.lo, min(c.hi, value)), True)

    def shift_all(self, key, amount):
        """Moves the whole line by amount (semitones, points or dB)."""
        if self.attempt(lambda m: m.shift_all(key, amount))[0]:
            self.done()

    def flatten(self, key):
        """Takes back every move of a channel: all the sounds have the normal pitch, length or volume."""
        if self.attempt(lambda m: m.reset_channel(key))[0]:
            self.done()

    # ----- mood and effects

    def mood(self):
        return self.model.mood() if self.model is not None else None

    def set_mood(self, name):
        if self.attempt(lambda m: m.set_mood(name or None))[0]:
            self.done()

    def effect(self):
        """The selected item when it is a command with a value (an effect), else None."""
        it = self.item()
        return it if it is not None and it.kind == 'tag' and it.value is not None else None

    def add_effect(self, name, value=None):
        """Puts a command in front of the selected block (in front of the first sound when none is selected)."""
        m, i = self.model, self.index()
        if i is None:
            cols = self.columns()
            i = cols[0].index if cols else len(m.items)
        ok, at = self.attempt(lambda m: m.add_tag(i, name, value))
        if ok:
            self.sel = m.column_of(at)
            self.done()

    def set_effect(self, value):
        """Gives the selected command another value."""
        i, it = self.index(), self.effect()
        if it is not None and str(value) != it.value and self.attempt(lambda m: m.set_tag(i, value))[0]:
            self.done()
