"""The palettes: cells to click on, so that nothing has to be typed. The sounds and the marks of the speech engine; the game codes and the
effects, each with its own colour and icon. Under a palette, the cell under the pointer says what it makes the Mii say."""
import collections
import tkinter as tk
from tkinter import ttk

from ....features.speech.kana import BASIC, COMBINED, FOREIGN, MARKS, SMALL_ONLY, VOICED
from ...theme import BG, BROWN, PANEL, SAND, font
from ...widgets import RIGHT, copy_text, popup

SOUND = (12, 40, 32)          # a section of sounds: cells in a row, width and height of a cell
WORD = (4, 124, 36)           # a section of marks, game codes or effects: wider cells, with an icon and a name
ROWS = 4                      # rows the canvas shows at least, so that a palette of sounds keeps its height
DEFAULT = 'Point at a cell to read what it makes the Mii say.'
Cell = collections.namedtuple('Cell', 'text label sub colour icon hint', defaults=('', '', None, None, ''))
Hit = collections.namedtuple('Hit', 'x y w h rect base cell')


def mix(colour, share):
    """A colour mixed with white: share is how much of the colour is kept (0 to 1)."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return '#%02X%02X%02X' % tuple(round(255 - (255 - v) * share) for v in (r, g, b))


def flat(*tables):
    """The (katakana, romaji) pairs of some tables, in order."""
    return [pair for table in tables for row in table for pair in row]


def sound_sections():
    """The sections of the palette of sounds: [(name, geometry, cells)]. A sound says how it is pronounced, a mark what it does."""
    kana = [('Basic', flat(BASIC)), ('Voiced', flat(VOICED)), ('Combined', flat(COMBINED)), ('Foreign', flat(FOREIGN, [SMALL_ONLY]))]
    sections = [(name, SOUND, [Cell(k, k, r, hint=f'{k}: said "{r}"') for k, r in pairs]) for name, pairs in kana]
    marks = [Cell(m, m, title, hint=f'{m} {title}: {about}') for m, (title, about) in MARKS.items()]
    return sections + [('Marks', WORD, marks)]


class Palette(ttk.Frame):
    """Cells to click. set(sections) gives them: [(name, geometry, cells)], one button per section when there are several. pick(text) is called
    with the text of the cell that was clicked; a right click offers Copy and the entries that menu(text) gives. Under the cells, the cell under
    the pointer says what it makes the Mii say."""

    def __init__(self, master, pick, menu):
        super().__init__(master)
        self.pick, self.menu, self.cells, self.over, self.sections = pick, menu, [], None, {}
        self.section = tk.StringVar()
        self.head = ttk.Frame(self)
        self.head.pack(fill='x')
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, width=SOUND[0] * SOUND[1] + 1, height=ROWS * SOUND[2] + 1)
        self.canvas.pack(anchor='w', pady=(6, 0))
        self.hint = tk.StringVar(value=DEFAULT)
        ttk.Label(self, textvariable=self.hint, foreground=BROWN, wraplength=500, justify='left').pack(anchor='w', pady=(4, 0))
        self.canvas.bind('<Motion>', lambda e: self.point(self.cell_at(e)))
        self.canvas.bind('<Leave>', lambda e: self.point(None))
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind(RIGHT, self.right)

    def set(self, sections):
        self.sections = {name: (geometry, cells) for name, geometry, cells in sections}
        for w in self.head.winfo_children():
            w.destroy()
        names = list(self.sections)
        if len(names) > 1:
            for name in names:
                ttk.Radiobutton(self.head, text=name, value=name, variable=self.section, style='Toolbutton', command=self.show).pack(side='left', padx=(0, 3))
        width = max([SOUND[0] * SOUND[1]] + [geometry[0] * geometry[1] for geometry, cells in self.sections.values()])
        height = max([ROWS * SOUND[2]] + [-(-len(cells) // geometry[0]) * geometry[2] for geometry, cells in self.sections.values()])
        self.canvas.configure(width=width + 1, height=height + 1)
        self.section.set(names[0] if names else '')
        self.show()

    def show(self):
        c = self.canvas
        c.delete('all')
        self.cells, self.over = [], None
        self.hint.set(DEFAULT)
        if self.section.get() not in self.sections:
            return
        (cols, w, h), cells = self.sections[self.section.get()]
        for n, cell in enumerate(cells):
            x, y = (n % cols) * w, (n // cols) * h
            if cell.colour:
                base = mix(cell.colour, 0.16)
                rect = c.create_rectangle(x + 2, y + 2, x + w - 2, y + h - 2, fill=base, outline=cell.colour, width=1)
                c.create_text(x + 16, y + h // 2, text=cell.icon, fill=cell.colour, font=font(13, True))
                c.create_text(x + 30, y + h // 2, text=cell.label, fill=BROWN, font=font(9, True), anchor='w', width=w - 34)
            else:
                base = PANEL
                rect = c.create_rectangle(x + 1, y + 1, x + w - 1, y + h - 1, fill=PANEL, outline=SAND)
                big = 13 if w == SOUND[1] else 10
                if cell.sub:
                    c.create_text(x + w // 2, y + 12, text=cell.label, fill=BROWN, font=font(big, True))
                    c.create_text(x + w // 2, y + 25, text=cell.sub, fill=BROWN, font=font(7), width=w - 6)
                else:
                    c.create_text(x + w // 2, y + h // 2, text=cell.label, fill=BROWN, font=font(big, True))
            self.cells.append(Hit(x, y, w, h, rect, base, cell))

    def cell_at(self, event):
        for i, hit in enumerate(self.cells):
            if hit.x <= event.x < hit.x + hit.w and hit.y <= event.y < hit.y + hit.h:
                return i
        return None

    def point(self, i):
        """Shows what the cell under the pointer makes the Mii say, and colours it."""
        if i == self.over:
            return
        if self.over is not None:
            self.canvas.itemconfigure(self.cells[self.over].rect, fill=self.cells[self.over].base)
        self.over = i
        if i is None:
            self.hint.set(DEFAULT)
            return
        self.canvas.itemconfigure(self.cells[i].rect, fill=SAND)
        self.hint.set(self.cells[i].cell.hint or DEFAULT)

    def click(self, event):
        i = self.cell_at(event)
        if i is not None:
            self.pick(self.cells[i].cell.text)

    def right(self, event):
        i = self.cell_at(event)
        if i is not None:
            text = self.cells[i].cell.text
            popup(self.canvas, event, [('Copy', lambda: copy_text(self, text))] + list(self.menu(text)))
