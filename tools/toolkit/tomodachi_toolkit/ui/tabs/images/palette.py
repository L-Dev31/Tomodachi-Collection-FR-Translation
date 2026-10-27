"""The palette of a picture as the game has it: rows of 16 colours."""
import tkinter as tk
from tkinter import ttk

from ...theme import BROWN, CANVAS, DARK

CELL = 11                       # pixels of a swatch
ACROSS = 16                     # colours in a row
PAD = 3
LIGHT, GREY = '#F4F1EA', '#C9C3B6'      # the two greys of the squares that stand for a transparent colour


def hex_of(color):
    return '#%02X%02X%02X' % tuple(color)


class PaletteView(ttk.Frame):
    """The colours of a palette as rows of 16 swatches. The first colour of a row is drawn as a chequer when `step` says it is
    transparent (every 16th colour of a 4 bit picture).

    pick(i) is called when a swatch is clicked, edit(i) when it is double clicked and hover(i) when the pointer is over one (None when
    it leaves). `rows` are the rows to outline, `selected` the colour that was picked."""

    def __init__(self, master, pick, edit, hover):
        super().__init__(master)
        self.pick, self.edit, self.hover = pick, edit, hover
        self.colors, self.rows, self.selected, self.step = [], (), None, ACROSS
        self.canvas = tk.Canvas(self, bg=CANVAS, bd=0, highlightthickness=0, width=ACROSS * CELL + 2 * PAD, height=2 * PAD + CELL)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', lambda e: self.act(e, self.pick))
        self.canvas.bind('<Double-Button-1>', lambda e: self.act(e, self.edit))
        self.canvas.bind('<Motion>', lambda e: self.hover(self.index_at(e)))
        self.canvas.bind('<Leave>', lambda e: self.hover(None))

    def box(self, i):
        """(left, top) of the swatch of colour i."""
        return PAD + (i % ACROSS) * CELL, PAD + (i // ACROSS) * CELL

    def index_at(self, event):
        """The colour under the pointer, or None."""
        col, row = (event.x - PAD) // CELL, (event.y - PAD) // CELL
        i = row * ACROSS + col
        return i if 0 <= col < ACROSS and row >= 0 and i < len(self.colors) else None

    def act(self, event, command):
        i = self.index_at(event)
        if i is not None:
            command(i)

    def set(self, colors, rows=(), selected=None, step=ACROSS):
        """Shows a palette (a list of (r, g, b)) with some rows outlined and one colour picked."""
        self.colors, self.rows, self.selected, self.step = list(colors), tuple(rows), selected, step
        self.canvas.configure(height=2 * PAD + CELL * max(1, (len(self.colors) + ACROSS - 1) // ACROSS))
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete('all')
        half = CELL // 2
        for i, color in enumerate(self.colors):
            x, y = self.box(i)
            if i % self.step == 0:
                for dx, dy, grey in ((0, 0, LIGHT), (half, 0, GREY), (0, half, GREY), (half, half, LIGHT)):
                    c.create_rectangle(x + dx, y + dy, x + dx + half, y + dy + half, fill=grey, outline='')
            else:
                c.create_rectangle(x, y, x + CELL - 1, y + CELL - 1, fill=hex_of(color), outline='')
        for row in self.rows:
            if 0 <= row < (len(self.colors) + ACROSS - 1) // ACROSS:
                x, y = self.box(row * ACROSS)
                c.create_rectangle(x - 2, y - 2, x + ACROSS * CELL - 1, y + CELL, outline=DARK, width=2)
        if self.selected is not None and 0 <= self.selected < len(self.colors):
            x, y = self.box(self.selected)
            c.create_rectangle(x, y, x + CELL - 2, y + CELL - 2, outline=BROWN, width=2)
