"""The keyboard of the game on a canvas: every key where it is on the touch screen, with the character it types."""
import tkinter as tk

from ...theme import BG, BROWN, CANVAS, MUTED, ORANGE, PANEL, SAND, font
from ...widgets import RIGHT


MARGIN = 6
SELECTED = '#FFE2BF'


class KeyboardBoard(tk.Canvas):
    """Draws a Keyboard (features/keyboard/layout.py) the way the game does, with the pictures of the game's font, `scale` times
    as big. A click on a key selects it (on_select(index)); dragging a key onto another one swaps them (on_swap(index, index));
    a right click calls on_menu(index, event)."""

    def __init__(self, master, glyphs, keyboard, on_select, on_swap, on_menu, scale=3):
        self.left = min(k.x for k in keyboard.keys)
        self.top = min(k.y for k in keyboard.keys)
        width = (max(k.x + k.w for k in keyboard.keys) - self.left) * scale + 2 * MARGIN
        height = (max(k.y + k.h for k in keyboard.keys) - self.top) * scale + 2 * MARGIN
        super().__init__(master, width=width, height=height, bg=CANVAS, highlightthickness=0, takefocus=True)
        self.glyphs, self.keyboard, self.scale = glyphs, keyboard, scale
        self.on_select, self.on_swap, self.on_menu = on_select, on_swap, on_menu
        self.text, self.selected, self.changed = '', None, set()
        self.source, self.dragging, self.origin = None, False, (0, 0)
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<B1-Motion>', self.motion)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind(RIGHT, self.menu)

    def box(self, key):
        """The rectangle of a key on the canvas."""
        x1 = MARGIN + (key.x - self.left) * self.scale
        y1 = MARGIN + (key.y - self.top) * self.scale
        return x1, y1, x1 + key.w * self.scale, y1 + key.h * self.scale

    def show(self, text, selected=None, changed=()):
        """Draws the keys. text: the character of every key, by index; selected: the index of the key that is selected;
        changed: the indexes of the keys that do not type what they type in the ROM (they get the page colour and a dot)."""
        self.text, self.selected, self.changed = text, selected, set(changed)
        self.delete('all')
        for key in self.keyboard.keys:
            self.draw_key(key)

    def draw_key(self, key):
        x1, y1, x2, y2 = self.box(key)
        if key.index is None:
            self.create_rectangle(x1, y1, x2, y2, fill=SAND, outline=SAND)
            self.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.keyboard.function_name(key), fill=MUTED, font=font(8))
            return
        selected, changed = key.index == self.selected, key.index in self.changed
        face = SELECTED if selected else BG if changed else PANEL
        self.create_rectangle(x1, y1, x2, y2, fill=face, outline=ORANGE if selected else SAND, width=3 if selected else 1)
        ch = self.text[key.index]
        if ch != ' ':
            self.create_image(*self.place(key, ch), image=self.glyphs.image(ch, BROWN, face, self.scale), anchor='nw')
        if changed:
            self.create_oval(x2 - 4 * self.scale, y1 + self.scale, x2 - self.scale, y1 + 4 * self.scale, fill=ORANGE, outline='')

    def place(self, key, ch):
        """Where the picture of a character goes in a key: in the middle of it, as the game draws it."""
        x1, y1, _, _ = self.box(key)
        return (x1 + (key.w - self.glyphs.width(ch)) * self.scale // 2, y1 + (key.h - self.glyphs.height) * self.scale // 2)

    def key_at(self, x, y):
        """The key under a point of the canvas (None when there is none)."""
        for key in self.keyboard.keys:
            x1, y1, x2, y2 = self.box(key)
            if x1 <= x < x2 and y1 <= y < y2:
                return key
        return None

    def press(self, event):
        self.focus_set()
        key = self.key_at(event.x, event.y)
        self.source = key if key is not None and key.index is not None else None
        self.dragging, self.origin = False, (event.x, event.y)

    def motion(self, event):
        if self.source is None:
            return
        if not self.dragging and abs(event.x - self.origin[0]) + abs(event.y - self.origin[1]) < 6:
            return
        self.dragging = True
        self.delete('drag')
        target = self.key_at(event.x, event.y)
        if target is not None and target.index is not None and target.index != self.source.index:
            x1, y1, x2, y2 = self.box(target)
            self.create_rectangle(x1, y1, x2, y2, outline=ORANGE, width=3, dash=(4, 3), tags='drag')
        ch = self.text[self.source.index]
        if ch != ' ':
            self.create_image(event.x, event.y, image=self.glyphs.image(ch, BROWN, PANEL, self.scale), tags='drag')

    def release(self, event):
        self.delete('drag')
        source, dragging = self.source, self.dragging
        self.source, self.dragging = None, False
        if source is None:
            return
        target = self.key_at(event.x, event.y)
        if dragging and target is not None and target.index is not None and target.index != source.index:
            self.on_swap(source.index, target.index)
        else:
            self.on_select(source.index)

    def menu(self, event):
        key = self.key_at(event.x, event.y)
        if key is not None and key.index is not None:
            self.on_menu(key.index, event)
