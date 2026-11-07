"""The strip: the sounds of a line as blocks in a row and, under them, a graph of the pitch, length or volume of each sound."""
import tkinter as tk
from tkinter import ttk

from ....features.speech.about import code_info, effect_style
from ....features.speech.kana import ASCII_MARKS, mark_name, romaji
from ....features.speech.line import CARRIERS, CHANNEL
from ...theme import BG, BROWN, CANVAS, DARK, ORANGE, PANEL, SAND, font
from ...widgets import RIGHT
from .palette import mix

COL = 46            # width of the column of a sound
PAD = 8             # space before the first column
BLOCKS = 64         # height of the row of blocks
LANE = 100          # height of the graph
EDGE = 8            # space above and under the graph
AXIS = 44           # width of the numbers at the left of the graph
SELECTED = '#FFE3B8'


def shown_mark(c):
    """The mark as it is drawn (a line break is drawn as an arrow, the ASCII marks as the fullwidth ones)."""
    return '↵' if c in '\r\n' else ASCII_MARKS.get(c, c)


class LineStrip(ttk.Frame):
    """The columns of a LineModel (model.columns()) as blocks, with the graph of one channel under them. Between the two is `middle`, a
    frame for the controls of the graph.

    select(k)       a column was clicked (k counts the columns, not the items of the line)
    paint(k, value, first)  the graph was drawn on at column k
    key(name)       a key was pressed with the strip focused: Left, Right, Up, Down, Delete
    menu(k, event)  a column was right clicked
    """

    def __init__(self, master, select, paint, key, menu):
        super().__init__(master)
        self.on_select, self.on_paint, self.on_key, self.on_menu = select, paint, key, menu
        self.columns, self.selected, self.channel, self.drag = [], None, None, False
        top = ttk.Frame(self)
        top.pack(fill='x')
        tk.Frame(top, width=AXIS, height=1, bg=BG).pack(side='left')            # keeps the blocks above their bars
        self.blocks = tk.Canvas(top, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=BLOCKS, width=300, takefocus=1)
        self.blocks.pack(side='left', fill='x', expand=True)
        self.middle = ttk.Frame(self)
        self.middle.pack(fill='x', pady=6)
        low = ttk.Frame(self)
        low.pack(fill='x')
        self.axis = tk.Canvas(low, bg=CANVAS, highlightthickness=0, width=AXIS, height=LANE + 2 * EDGE)
        self.axis.pack(side='left')
        self.graph = tk.Canvas(low, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=LANE + 2 * EDGE, width=300, takefocus=1)
        self.graph.pack(side='left', fill='x', expand=True)
        self.scroll = ttk.Scrollbar(self, orient='horizontal', command=self.xview)
        self.scroll.pack(fill='x')
        self.blocks.configure(xscrollcommand=self.scroll.set)
        for c in (self.blocks, self.graph):
            c.bind('<Configure>', lambda e: self.draw())
            c.bind('<MouseWheel>', lambda e: self.xview('scroll', -3 if e.delta > 0 else 3, 'units'))
            c.bind('<Button-4>', lambda e: self.xview('scroll', -3, 'units'))
            c.bind('<Button-5>', lambda e: self.xview('scroll', 3, 'units'))
            for name in ('Left', 'Right', 'Up', 'Down', 'Delete', 'BackSpace'):
                c.bind(f'<{name}>', lambda e, n=name: self.key(n))
        self.blocks.bind('<ButtonPress-1>', lambda e: self.press(e, self.blocks, False))
        self.graph.bind('<ButtonPress-1>', lambda e: self.press(e, self.graph, True))
        self.graph.bind('<B1-Motion>', self.motion)
        self.graph.bind('<ButtonRelease-1>', lambda e: setattr(self, 'drag', False))
        self.blocks.bind(RIGHT, self.right)

    # ----- content

    def show(self, columns, selected=None, channel=None):
        """Draws these columns. selected: the column that is selected; channel: the key of the channel the graph shows."""
        self.columns, self.selected, self.channel = columns, selected, channel
        self.draw()

    def xview(self, *args):
        self.blocks.xview(*args)
        self.graph.xview(*args)

    def rewind(self):
        """Shows the start of the line again (a new line was opened)."""
        self.xview('moveto', 0)

    def x0(self, k):
        return PAD + k * COL

    def column_at(self, canvas, x):
        k = int((canvas.canvasx(x) - PAD) // COL)
        return k if 0 <= k < len(self.columns) else None

    def lane_value(self, y):
        """The value of the channel at a height of the graph (snapped to its step and kept in its range)."""
        ch = CHANNEL[self.channel]
        v = ch.hi - (self.graph.canvasy(y) - EDGE) / LANE * (ch.hi - ch.lo)
        return max(ch.lo, min(ch.hi, round(v / ch.step) * ch.step))

    def lane_y(self, ch, v):
        return EDGE + (ch.hi - v) / (ch.hi - ch.lo) * LANE

    # ----- drawing

    def draw(self):
        width = max(len(self.columns) * COL + 2 * PAD, self.blocks.winfo_width())
        for c, height in ((self.blocks, BLOCKS), (self.graph, LANE + 2 * EDGE)):
            c.delete('all')
            c.configure(scrollregion=(0, 0, width, height))
            if self.selected is not None:
                c.create_rectangle(self.x0(self.selected), 0, self.x0(self.selected) + COL, height, fill=SELECTED, outline='')
        for k, col in enumerate(self.columns):
            self.draw_column(k, col)
        self.draw_graph(width)
        self.reveal()

    def draw_column(self, k, col):
        c, it = self.blocks, col.item
        x = self.x0(k)
        on = k == self.selected
        left, right, top, bottom = x + 3, x + COL - 3, 6, 56
        mid = (left + right) // 2
        edge = ORANGE if on else SAND
        if it.kind == 'mora':
            c.create_rectangle(left, top, right, bottom, fill=PANEL, outline=edge, width=2)
            c.create_text(mid, top + 20, text=it.text, fill=BROWN, font=font(16, True))
            c.create_text(mid, bottom - 9, text=romaji(it.text), fill=BROWN, font=font(7))
        elif it.kind == 'mark':
            c.create_rectangle(left, top + 6, right, bottom, fill=SAND, outline=edge, width=2)
            c.create_text(mid, top + 22, text=shown_mark(it.text), fill=DARK, font=font(15, True))
            c.create_text(mid, bottom - 9, text=mark_name(it.text), fill=BROWN, font=font(6))
        elif it.kind == 'slot':
            style = code_info(it.text)
            c.create_rectangle(left, top, right, bottom, fill=mix(style.colour, 0.16), outline=style.colour, width=3 if on else 2)
            c.create_text(mid, top + 20, text=style.icon, fill=style.colour, font=font(16, True))
            c.create_text(mid, bottom - 9, text=style.short, fill=BROWN, font=font(6))
        elif it.kind == 'tag':
            style = effect_style(it.name)
            value = '' if it.value is None else f' {it.value}'
            c.create_rectangle(left, top, right, bottom, fill=mix(style.colour, 0.16), outline=style.colour, width=3 if on else 2)
            c.create_text(mid, top + 20, text=style.icon, fill=style.colour, font=font(16, True))
            c.create_text(mid, bottom - 9, text=(style.short + value)[:9], fill=BROWN, font=font(6))
        else:
            c.create_rectangle(left, top + 12, right, bottom - 4, fill=CANVAS, outline=ORANGE if on else BROWN, width=2 if on else 1)
            c.create_text(mid, (top + bottom) // 2 + 4, text=it.text[:7], fill=BROWN, font=font(7))

    def draw_graph(self, width):
        c, a = self.graph, self.axis
        a.delete('all')
        if not self.channel:
            return
        ch = CHANNEL[self.channel]
        c.create_rectangle(0, EDGE, width, EDGE + LANE, fill=PANEL, outline='')
        a.create_text(AXIS - 6, EDGE - 2, text=ch.unit, anchor='e', fill=BROWN, font=font(7))
        step = 6 if ch.key == 'pitch' else 50 if ch.key == 'length' else 10
        for v in range(ch.lo, ch.hi + 1):
            if v % step == 0:
                y = self.lane_y(ch, v)
                c.create_line(0, y, width, y, fill=DARK if v == 0 else SAND, width=2 if v == 0 else 1)
                a.create_text(AXIS - 6, y, text=f'{v:+d}' if v else '0', anchor='e', fill=BROWN, font=font(8))
        zero = self.lane_y(ch, 0)
        for k, col in enumerate(self.columns):
            if col.item.kind in CARRIERS:
                y, x = self.lane_y(ch, max(ch.lo, min(ch.hi, getattr(col, self.channel)))), self.x0(k)
                c.create_rectangle(x + 9, min(y, zero), x + COL - 9, max(y, zero) + (1 if y == zero else 0), fill=DARK if k == self.selected else ORANGE, outline='')
                c.create_rectangle(x + 5, y - 2, x + COL - 5, y + 2, fill=BROWN, outline='')

    def reveal(self):
        """Scrolls so that the selected column can be seen."""
        c = self.blocks
        if self.selected is None or not self.columns or c.winfo_width() < 50:
            return                                   # nothing selected, or the canvas is not laid out yet
        total = max(len(self.columns) * COL + 2 * PAD, c.winfo_width())
        left, right = (f * total for f in c.xview())
        x = self.x0(self.selected)
        if x < left:
            self.xview('moveto', max(0, (x - COL) / total))
        elif x + COL > right:
            self.xview('moveto', min(1, (x + 2 * COL - c.winfo_width()) / total))

    # ----- the mouse and the keys

    def press(self, event, canvas, painting):
        canvas.focus_set()
        k = self.column_at(canvas, event.x)
        self.drag = False
        if k is None:
            return
        self.on_select(k)
        if painting and self.channel and self.columns[k].item.kind in CARRIERS:
            self.drag = True
            self.on_paint(k, self.lane_value(event.y), True)

    def motion(self, event):
        k = self.column_at(self.graph, event.x) if self.drag else None
        if k is not None and self.columns[k].item.kind in CARRIERS:
            self.on_paint(k, self.lane_value(event.y), False)

    def right(self, event):
        k = self.column_at(self.blocks, event.x)
        if k is not None:
            self.on_select(k)
            self.on_menu(k, event)

    def key(self, name):
        self.on_key(name)
        return 'break'
