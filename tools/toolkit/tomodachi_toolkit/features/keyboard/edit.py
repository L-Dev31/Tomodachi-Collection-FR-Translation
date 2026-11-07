"""The edits of one keyboard before they are applied: a working copy of its characters with undo."""


def case_variants(layer, ch):
    """{layer: character} the other layers of the QWERTY keyboard get when a letter is typed on one of them."""
    if len(ch.upper()) != 1 or len(ch.lower()) != 1 or ch.upper() == ch.lower():
        return {}
    return {'lower': ch.lower(), 'caps': ch.upper(), 'shift': ch.upper()}


def kana_variants(layer, ch):
    """The same for the Japanese keyboard: a hiragana is also on the katakana layer and the other way round."""
    c = ord(ch)
    if 0x3041 <= c <= 0x3096:
        return {'hiragana': ch, 'katakana': chr(c + 0x60)}
    if 0x30A1 <= c <= 0x30F6:
        return {'hiragana': chr(c - 0x60), 'katakana': ch}
    return {}


VARIANTS = {'QWERTY': case_variants, 'Japanese': kana_variants}


class LayoutEditor:
    """keyboard: the Keyboard (see layout.py); text: {layer: string} what the keys type now; original: the same as the ROM has it.

    The characters are changed by key (its index in the tables) and layer. Every change can be undone."""

    def __init__(self, keyboard, text, original):
        self.keyboard = keyboard
        self.original = {layer: list(chars) for layer, chars in original.items()}
        self.text = {layer: list(text[layer]) for layer, _ in keyboard.layers}
        self.history, self.future = [], []

    def copy(self):
        return {layer: list(chars) for layer, chars in self.text.items()}

    def snapshot(self):
        self.history.append(self.copy())
        self.future.clear()

    def undo(self):
        """Takes back the last change. Returns the (layer, key index) of the first key it changed, or None when there is nothing to take back."""
        return self.step(self.history, self.future)

    def redo(self):
        """Does again what undo took back. Returns what undo returns."""
        return self.step(self.future, self.history)

    def step(self, source, target):
        if not source:
            return None
        target.append(self.copy())
        before, self.text = self.text, source.pop()
        return next(((layer, i) for layer, chars in self.text.items() for i, ch in enumerate(chars) if ch != before[layer][i]),
                    (self.keyboard.layers[0][0], 0))

    def chars(self, index):
        """{layer: character} of a key."""
        return {layer: chars[index] for layer, chars in self.text.items()}

    def set_char(self, index, layer, ch, sync=True, usable=None):
        """Gives a key a character on a layer. sync: the other layers get the same letter in their own way (capital letters
        on the layers that have them, katakana for hiragana) when the game can draw it (usable). Returns whether anything
        changed (nothing does when the keys already type that)."""
        changes = {layer: ch}
        if sync:
            for other, c in VARIANTS.get(self.keyboard.name, lambda *_: {})(layer, ch).items():
                if other != layer and other in self.text and (usable is None or usable(c)):
                    changes[other] = c
        return self.put(index, changes)

    def put(self, index, changes):
        """Sets characters of one key ({layer: character}); one undo step. Returns whether anything changed."""
        if all(self.text[layer][index] == ch for layer, ch in changes.items()):
            return False
        self.snapshot()
        for layer, ch in changes.items():
            self.text[layer][index] = ch
        return True

    def blank(self, index):
        """Makes a key type nothing on every layer."""
        return self.put(index, {layer: ' ' for layer in self.text})

    def swap(self, a, b):
        """Exchanges two keys on every layer."""
        if a == b or all(chars[a] == chars[b] for chars in self.text.values()):
            return
        self.snapshot()
        for chars in self.text.values():
            chars[a], chars[b] = chars[b], chars[a]

    def load(self, layers):
        """Takes whole layers ({layer: string}), such as a preset or a file."""
        layers = {layer: list(text) for layer, text in layers.items() if layer in self.text}
        if all(self.text[layer] == chars for layer, chars in layers.items()):
            return
        self.snapshot()
        self.text.update(layers)

    def reset_key(self, index):
        """Puts a key back as the ROM has it (on every layer)."""
        return self.put(index, {layer: chars[index] for layer, chars in self.original.items() if layer in self.text})

    def reset(self):
        """Puts the whole keyboard back as the ROM has it."""
        if not self.changed():
            return
        self.snapshot()
        self.text = {layer: list(chars) for layer, chars in self.original.items() if layer in self.text}

    def changed(self, index=None):
        """Whether the characters differ from the ROM's (of one key when given its index)."""
        if index is None:
            return any(self.text[layer] != self.original[layer] for layer in self.text)
        return any(self.text[layer][index] != self.original[layer][index] for layer in self.text)

    def result(self):
        """{layer: string} of the layers that differ from the ROM's (empty when none does)."""
        return {layer: ''.join(chars) for layer, chars in self.text.items() if chars != self.original[layer]}
