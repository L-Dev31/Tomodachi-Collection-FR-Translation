"""The window that changes the characters of the keys of one keyboard."""
import tkinter as tk
from tkinter import messagebox, ttk

from ....features.keyboard.edit import LayoutEditor
from ....features.keyboard.presets import presets_for
from ...charpalette import CharPalette
from ...theme import BG, CANVAS, MUTED
from ...widgets import copy_text, flash, popup
from .board import KeyboardBoard


TYPING_KEYS = {'Left': (-1, 0), 'Right': (1, 0), 'Up': (0, -1), 'Down': (0, 1)}


class KeyboardEditor(tk.Toplevel):
    """Settings of one keyboard: click a key and pick the character it should type (or type it on the computer's keyboard),
    drag a key onto another to swap them, or start from a ready made layout (QWERTY, AZERTY, Dvorak ...). Ctrl+Z and Ctrl+Shift+Z
    undo and redo; a right click on a key offers Copy, Blank and Restore.

    keyboard    the Keyboard as the ROM has it (features/keyboard/layout.py)
    current     {layer: string} what its keys type now (the ROM's characters with the changes made so far)
    glyphs      the pictures of the characters (ui/glyphs.py)
    characters  the characters the game can draw (features/keyboard/charset.py)
    on_apply    called with {layer: string} for the layers that differ from the ROM's (empty when none does)
    """

    def __init__(self, parent, keyboard, current, glyphs, characters, on_apply):
        super().__init__(parent, bg=BG)
        self.keyboard, self.glyphs, self.characters, self.on_apply = keyboard, glyphs, characters, on_apply
        self.editor = LayoutEditor(keyboard, current, keyboard.text)
        self.start = self.editor.result()
        self.layer = tk.StringVar(value=keyboard.layers[0][0])
        self.selected = None
        self.title(f'{keyboard.name} keyboard')
        self.transient(parent)
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        self.bind('<Escape>', lambda e: self.cancel())
        for key in ('z', 'Z'):
            self.bind(f'<Control-KeyPress-{key}>', lambda e: self.step(bool(e.state & 1)))
        self.build(3 if self.winfo_screenheight() >= 900 else 2)
        self.refresh()
        self.place_over(parent)
        self.hold()

    # ----- the window

    def build(self, scale):
        keyboard = self.keyboard
        top = ttk.Frame(self, padding=(12, 10, 12, 0))
        top.pack(fill='x')
        if len(keyboard.layers) > 1:
            for layer, label in keyboard.layers:
                ttk.Radiobutton(top, text=label, value=layer, variable=self.layer, style='Toolbutton', command=self.refresh).pack(side='left', padx=(0, 3))
        presets = presets_for(keyboard, self.characters.has)
        if presets:
            self.preset_layers = dict(presets)
            ttk.Label(top, text='Presets').pack(side='left', padx=(14, 4))
            self.preset_box = ttk.Combobox(top, state='readonly', width=26, values=[title for title, _ in presets])
            self.preset_box.pack(side='left')
            self.preset_box.bind('<<ComboboxSelected>>', self.preset_chosen)
        ttk.Button(top, text='Reset', style='Mini.TButton', command=self.reset).pack(side='right')

        stage = tk.Frame(self, bg=CANVAS)
        stage.pack(fill='x', padx=12, pady=(10, 0))
        self.board = KeyboardBoard(stage, self.glyphs, keyboard, self.select, self.swap, self.key_menu, scale)
        self.board.pack(padx=8, pady=6)
        self.board.bind('<Key>', self.typed)

        box = ttk.Frame(self)
        box.pack(fill='both', expand=True, padx=12, pady=(10, 0))
        self.palette = CharPalette(box, self.glyphs, self.characters, self.give, height=150 if scale == 2 else 190)
        self.palette.pack(fill='both', expand=True)

        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill='x')
        self.status = ttk.Label(bottom, foreground=MUTED)
        self.status.pack(side='left')
        ttk.Button(bottom, text='Apply', style='MiniAccent.TButton', command=self.apply).pack(side='right')
        ttk.Button(bottom, text='Cancel', style='Mini.TButton', command=self.cancel).pack(side='right', padx=(0, 8))

    def place_over(self, parent):
        """Opens the window in the middle of the one it belongs to."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + max(parent.winfo_width() - w, 0) // 2
        y = parent.winfo_rooty() + max(parent.winfo_height() - h, 0) // 2
        self.geometry(f'+{max(x, 0)}+{max(y, 0)}')

    def hold(self):
        """The window takes the mouse and the keyboard (when it can: not every system allows it before the window is shown)."""
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.board.focus_set()

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    # ----- what is on show

    def refresh(self):
        layer = self.layer.get()
        chars, original = self.editor.text[layer], self.editor.original[layer]
        self.board.show(''.join(chars), self.selected, [i for i, ch in enumerate(chars) if ch != original[i]])
        self.palette.mark(chars[self.selected] if self.selected is not None else None)

    def say(self, text):
        flash(self.status, text)

    # ----- changing keys

    def select(self, index):
        self.selected = index
        self.refresh()

    def swap(self, a, b):
        self.editor.swap(a, b)
        self.selected = b
        self.refresh()

    def give(self, ch):
        """Gives the selected key a character on the layer that is on show (the other layers get its capital or its twin when they have one).
        Returns whether it did."""
        if self.selected is None:
            self.say('Click a key first')
            return False
        if not self.characters.has(ch):
            self.say(f'The game cannot draw U+{ord(ch):04X}')
            return False
        self.editor.set_char(self.selected, self.layer.get(), ch, True, self.characters.has)
        self.refresh()
        return True

    def key_menu(self, index, event):
        self.select(index)
        popup(self.board, event, [('Copy', lambda: copy_text(self, self.editor.text[self.layer.get()][index])),
                                  ('Blank', lambda: self.change(self.editor.blank, index)),
                                  ('Restore', (lambda: self.change(self.editor.reset_key, index)) if self.editor.changed(index) else None)])

    def change(self, action, *args):
        action(*args)
        self.refresh()

    def reset(self):
        self.change(self.editor.reset)

    def preset_chosen(self, event=None):
        title = self.preset_box.get()
        if title in self.preset_layers:
            self.start_from(title, self.preset_layers[title])

    def start_from(self, title, layers):
        self.editor.load(layers)
        self.refresh()
        self.say(title)

    def step(self, redo):
        """Ctrl+Z and Ctrl+Shift+Z: the key that changed is selected, so that the change can be seen."""
        hit = self.editor.redo() if redo else self.editor.undo()
        if hit:
            self.layer.set(hit[0])
            self.selected = hit[1]
            self.refresh()
        self.say(('Redo' if redo else 'Undo') if hit else 'Nothing to ' + ('redo' if redo else 'undo'))
        return 'break'

    def neighbour(self, index, dx, dy):
        """The key next to a key: the previous or next one on the way a text is read, or the closest one in the row above or
        below."""
        rows = self.keyboard.rows()
        if dx:
            order = [k.index for row in rows for k in row]
            i = order.index(index) + dx
            return order[i] if 0 <= i < len(order) else index
        row, column = next((r, c) for r, line in enumerate(rows) for c, k in enumerate(line) if k.index == index)
        if not 0 <= row + dy < len(rows):
            return index
        key = rows[row][column]
        middle = key.x + key.w / 2
        return min(rows[row + dy], key=lambda k: abs(k.x + k.w / 2 - middle)).index

    def typed(self, event):
        """A key of the computer's keyboard while the keyboard of the game has the focus: the arrows move the selection, a
        character is given to the selected key (and the next key is selected, to type a whole row)."""
        if event.keysym in TYPING_KEYS:
            self.select(0 if self.selected is None else self.neighbour(self.selected, *TYPING_KEYS[event.keysym]))
            return 'break'
        if len(event.char) == 1 and event.char.isprintable() and not event.state & 0x4:
            if self.give(event.char):
                self.select(self.neighbour(self.selected, 1, 0))
            return 'break'
        return None

    # ----- leaving

    def apply(self):
        self.on_apply(self.editor.result())
        self.close()

    def cancel(self):
        if self.editor.result() != self.start and not messagebox.askyesno('Keyboard layout', 'Close without applying the changes made here?', parent=self):
            return
        self.close()
