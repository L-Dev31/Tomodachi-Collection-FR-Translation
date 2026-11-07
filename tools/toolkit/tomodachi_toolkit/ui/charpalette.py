"""The characters the game can draw as a grid of pictures, to pick one (for a key of the keyboard, for the symbol of the money)."""
import tkinter as tk
from tkinter import ttk

from .theme import BROWN, MUTED, ORANGE, PANEL, SAND
from .widgets import RIGHT, copy_text, popup


CELL_W, CELL_H, ZOOM = 30, 34, 2
ALL = 'All characters'


class CharPalette(ttk.Frame):
    """A search bar, a choice of group and the characters as a grid of pictures. A click on one calls on_pick(character); a right click
    offers to copy it; the pointer over one writes its code and its name at the bottom right. `group`: the name of the group shown first (all of them when it is None or has no character)."""

    def __init__(self, master, glyphs, characters, on_pick, height=170, group=None):
        super().__init__(master)
        self.glyphs, self.characters, self.on_pick = glyphs, characters, on_pick
        self.items, self.where, self.columns, self.marked = [], {}, 0, None
        self.names = [(ALL, len(characters.all))] + characters.groups()
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        self.choice = ttk.Combobox(bar, values=[f'{name} ({count})' for name, count in self.names], state='readonly', width=26)
        self.choice.current(next((i for i, (name, _) in enumerate(self.names) if name == group), 0))
        self.choice.pack(side='left')
        self.choice.bind('<<ComboboxSelected>>', lambda e: self.refill())
        self.query = tk.StringVar()
        self.entry = ttk.Entry(bar, textvariable=self.query, width=22)
        self.entry.pack(side='left', padx=(12, 0))
        self.query.trace_add('write', lambda *_: self.refill())
        self.info = tk.StringVar()
        ttk.Label(self, textvariable=self.info, foreground=MUTED).pack(side='bottom', anchor='e', pady=(4, 0))     # the character under the pointer
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True, pady=(6, 0))
        self.canvas = tk.Canvas(body, bg=PANEL, highlightthickness=1, highlightbackground=SAND, height=height)
        scroll = ttk.Scrollbar(body, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.fit())
        self.canvas.bind('<ButtonRelease-1>', lambda e: self.click(self.at(e)))
        self.canvas.bind(RIGHT, self.menu)
        self.canvas.bind('<Motion>', lambda e: self.point(self.at(e)))
        self.canvas.bind('<Leave>', lambda e: self.point(None))
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        self.canvas.bind('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))
        self.refill()

    def group(self):
        """The group that is chosen (None for all of them)."""
        name = self.names[self.choice.current()][0]
        return None if name == ALL else name

    def refill(self):
        """Lists the characters of the group and the search again."""
        self.items = self.characters.listing(self.group(), self.query.get())
        self.where = {ch: i for i, ch in enumerate(self.items)}
        self.canvas.yview_moveto(0)
        self.draw()

    def fit(self):
        """Draws the grid again when the width of the canvas changed how many characters a row holds."""
        columns = max(1, self.canvas.winfo_width() // CELL_W)
        if columns != self.columns and self.canvas.winfo_width() > 1:
            self.draw()

    def draw(self):
        width = self.canvas.winfo_width()
        if width <= 1:
            return                                   # not on screen yet: the first <Configure> draws
        self.columns = max(1, width // CELL_W)
        self.canvas.delete('all')
        for i, ch in enumerate(self.items):
            x, y = i % self.columns * CELL_W, i // self.columns * CELL_H
            self.canvas.create_rectangle(x + 1, y + 1, x + CELL_W - 1, y + CELL_H - 1, outline=SAND, tags=f'cell{i}')
            self.canvas.create_image(x + CELL_W // 2, y + CELL_H // 2, image=self.glyphs.image(ch, BROWN, PANEL, ZOOM))
        rows = (len(self.items) + self.columns - 1) // self.columns
        self.canvas.configure(scrollregion=(0, 0, self.columns * CELL_W, max(rows * CELL_H, 1)))
        if not self.items:
            self.canvas.create_text(12, 14, anchor='nw', text='No character matches.', fill=MUTED)
        self.outline(self.marked)

    def mark(self, ch):
        """Outlines a character (the one the selected key types now) when it is listed."""
        old, self.marked = self.marked, ch
        self.outline(old)
        self.outline(ch)

    def outline(self, ch):
        """Draws the cell of a character as marked or not."""
        if ch in self.where:
            on = ch == self.marked
            self.canvas.itemconfigure(f'cell{self.where[ch]}', outline=ORANGE if on else SAND, width=3 if on else 1)

    def at(self, event):
        """The character under the pointer (None when there is none)."""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if x < 0 or y < 0 or x >= self.columns * CELL_W:
            return None
        i = int(y // CELL_H) * self.columns + int(x // CELL_W)
        return self.items[i] if 0 <= i < len(self.items) else None

    def point(self, ch):
        """Writes at the bottom right what the character under the pointer is: its code and its name (nothing when there is none)."""
        self.info.set('' if ch is None else f'{ch}   U+{ord(ch):04X}   {self.characters.name(ch)}')

    def click(self, ch):
        if ch is not None:
            self.on_pick(ch)

    def menu(self, event):
        ch = self.at(event)
        if ch is not None:
            popup(self.canvas, event, [('Copy', lambda: copy_text(self, ch))])
