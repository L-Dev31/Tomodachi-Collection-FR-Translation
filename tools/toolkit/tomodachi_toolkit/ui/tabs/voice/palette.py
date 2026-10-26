"""The palette: the sounds and the marks of the speech engine to click on, so that nothing has to be typed."""
import tkinter as tk
from tkinter import ttk

from ....features.speech.kana import BASIC, COMBINED, FOREIGN, MARKS, SMALL_ONLY, VOICED
from ...theme import BG, BROWN, MUTED, PANEL, SAND, font

HINT = 'Click a sound to put it in the line.'
SOUND = (12, 40, 32)          # for the sounds: cells in a row, width and height of a cell
MARK = (4, 120, 32)           # the same for the marks
ROWS = 4                      # rows of the tallest section: every section has the same height so that the page does not jump
MARKS_NAME = 'Marks'
OFF = '#B9A07A'


def flat(*tables):
    """The (katakana, romaji) pairs of some tables, in order."""
    return [pair for table in tables for row in table for pair in row]


SECTIONS = (
    ('Basic', flat(BASIC)),
    ('Voiced', flat(VOICED)),
    ('Combined', flat(COMBINED)),
    ('Foreign', flat(FOREIGN, [SMALL_ONLY])),
)


class Palette(ttk.Frame):
    """pick(text) is called with the sound or the mark that was clicked. Widgets can be added to .tools (under the palette)."""

    def __init__(self, master, pick):
        super().__init__(master)
        self.pick, self.enabled, self.cells, self.over = pick, True, [], None
        self.section = tk.StringVar(value=SECTIONS[0][0])
        head = ttk.Frame(self)
        head.pack(fill='x')
        for name in [n for n, _ in SECTIONS] + [MARKS_NAME]:
            ttk.Radiobutton(head, text=name, value=name, variable=self.section, style='Toolbutton', command=self.show).pack(side='left', padx=(0, 3))
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, width=SOUND[0] * SOUND[1] + 1, height=ROWS * SOUND[2] + 1)
        self.canvas.pack(anchor='w', pady=(8, 0))
        self.canvas.bind('<Motion>', self.motion)
        self.canvas.bind('<Leave>', lambda e: self.point(None))
        self.canvas.bind('<Button-1>', self.click)
        bottom = ttk.Frame(self)
        bottom.pack(fill='x', pady=(4, 0))
        self.tools = ttk.Frame(bottom)                # the page puts its widgets here
        self.tools.pack(side='right')
        self.info = tk.StringVar(value=HINT)
        ttk.Label(bottom, textvariable=self.info, foreground=MUTED, wraplength=300, justify='left').pack(side='left', fill='x', expand=True)
        self.show()

    def entries(self):
        """[(text to put in the line, big text, small text, text shown when pointed at)] of the section that is open."""
        name = self.section.get()
        if name == MARKS_NAME:
            return [(mark, mark, title, f'{mark}  {title}: {about}') for mark, (title, about) in MARKS.items()]
        return [(kana, kana, romaji, f'{kana}  {romaji}') for kana, romaji in dict(SECTIONS)[name]]

    def show(self):
        c, ink = self.canvas, BROWN if self.enabled else OFF
        c.delete('all')
        self.cells, self.over = [], None
        marks = self.section.get() == MARKS_NAME
        cols, w, h = MARK if marks else SOUND
        for n, (text, big, small, tip) in enumerate(self.entries()):
            x, y = (n % cols) * w, (n // cols) * h
            rect = c.create_rectangle(x + 1, y + 1, x + w - 1, y + h - 1, fill=PANEL if self.enabled else BG, outline=SAND)
            if marks:
                c.create_text(x + 16, y + h // 2, text=big, fill=ink, font=font(14, True))
                c.create_text(x + 34, y + h // 2, text=small, fill=ink, font=font(8), anchor='w')
            else:
                c.create_text(x + w // 2, y + 12, text=big, fill=ink, font=font(13, True))
                c.create_text(x + w // 2, y + 25, text=small, fill=MUTED if self.enabled else OFF, font=font(7))
            self.cells.append((x, y, w, h, rect, tip, text))
        self.info.set(HINT)

    def set_enabled(self, on):
        if on != self.enabled:
            self.enabled = on
            self.show()

    def cell_at(self, event):
        for i, (x, y, w, h, *_) in enumerate(self.cells):
            if x <= event.x < x + w and y <= event.y < y + h:
                return i
        return None

    def point(self, i):
        """Shows what the cell under the mouse is."""
        if i == self.over:
            return
        if self.over is not None:
            self.canvas.itemconfigure(self.cells[self.over][4], fill=PANEL if self.enabled else BG)
        self.over = i
        if i is not None and self.enabled:
            self.canvas.itemconfigure(self.cells[i][4], fill=SAND)
        self.info.set(HINT if i is None else self.cells[i][5])

    def motion(self, event):
        self.point(self.cell_at(event))

    def click(self, event):
        i = self.cell_at(event)
        if i is not None and self.enabled:
            self.pick(self.cells[i][6])
