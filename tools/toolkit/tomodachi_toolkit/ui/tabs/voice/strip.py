"""The strip: the sounds of a line as blocks in a row and, under them, a graph of the pitch, length or volume of each sound."""
import tkinter as tk
from tkinter import ttk

from ....features.speech.kana import ASCII_MARKS, mark_info, mark_name, romaji
from ....features.speech.line import CARRIERS, CHANNEL
from ...theme import BROWN, CANVAS, DARK, MUTED, ORANGE, PANEL, SAND, font

COL = 46            # width of the column of a sound
PAD = 8             # space before the first column
TOP = 6             # space above the blocks
BLOCK = 50          # height of a block
LANE = 100          # height of the graph
GAP = 14            # space between the blocks and the graph
AXIS = 44           # width of the numbers at the left of the graph
SELECTED = '#FFE3B8'
CODE_NAMES = {'08011f': 'name', '080101': '♪'}       # what a game code is, when it is known


def shown_mark(c):
    """The mark as it is drawn (a line break is drawn as an arrow, the ASCII marks as the fullwidth ones)."""
    return '↵' if c in '\r\n' else ASCII_MARKS.get(c, c)


class LineStrip(ttk.Frame):
    """Draws the columns of a LineModel (model.columns()).

    select(k)       a column was clicked (k counts the columns, not the items of the line)
    paint(k, value) the graph was drawn on at column k (only with graph=True)
    key(name)       a key was pressed with the strip focused: Left, Right, Up, Down, Delete
    edit(k)         a column was double clicked
    """

    def __init__(self, master, select, paint=None, key=None, edit=None, graph=False):
        super().__init__(master)
        self.on_select, self.on_paint, self.on_key, self.on_edit = select, paint, key, edit
        self.graph = graph
        self.columns, self.selected, self.channel, self.hint = [], None, None, ''
        self.drag = False
        self.height = TOP + BLOCK + (GAP + LANE + 8 if graph else 8)
        body = ttk.Frame(self)
        body.pack(fill='x')
        self.axis = None
        if graph:
            self.axis = tk.Canvas(body, bg=CANVAS, highlightthickness=0, width=AXIS, height=self.height)
            self.axis.pack(side='left')
        self.canvas = tk.Canvas(body, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=self.height, width=300, takefocus=1)
        self.canvas.pack(side='left', fill='x', expand=True)
        self.scroll = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scroll.set)
        self.scroll.pack(fill='x')
        self.info = tk.StringVar()
        bottom = ttk.Frame(self)
        bottom.pack(fill='x', pady=(4, 0))
        self.tools = ttk.Frame(bottom)                # the page puts its buttons here
        self.tools.pack(side='right', anchor='n')
        ttk.Label(bottom, textvariable=self.info, foreground=BROWN, wraplength=390, justify='left').pack(side='left', fill='x', expand=True)
        c = self.canvas
        c.bind('<Configure>', lambda e: self.draw())
        c.bind('<ButtonPress-1>', self.press)
        c.bind('<B1-Motion>', self.motion)
        c.bind('<ButtonRelease-1>', self.release)
        c.bind('<Double-Button-1>', self.double)
        c.bind('<Motion>', self.hover)
        c.bind('<Leave>', lambda e: self.describe(self.selected))
        c.bind('<MouseWheel>', lambda e: c.xview_scroll(-3 if e.delta > 0 else 3, 'units'))
        c.bind('<Button-4>', lambda e: c.xview_scroll(-3, 'units'))
        c.bind('<Button-5>', lambda e: c.xview_scroll(3, 'units'))
        for name in ('Left', 'Right', 'Up', 'Down', 'Delete', 'BackSpace'):
            c.bind(f'<{name}>', lambda e, n=name: self.key(n))

    # ----- content

    def show(self, columns, selected=None, channel=None, hint=''):
        """Draws these columns. selected: the column that is selected; channel: the key of the channel the graph shows."""
        self.columns, self.selected, self.channel, self.hint = columns, selected, channel, hint
        self.draw()
        self.describe(selected)

    def rewind(self):
        """Shows the start of the line again (a new line was opened)."""
        self.canvas.xview_moveto(0)

    def x0(self, k):
        return PAD + k * COL

    def column_at(self, x):
        k = int((self.canvas.canvasx(x) - PAD) // COL)
        return k if 0 <= k < len(self.columns) else None

    def lane_value(self, y):
        """The value of the channel at a height of the graph (snapped to its step and kept in its range)."""
        ch = CHANNEL[self.channel]
        top = TOP + BLOCK + GAP
        v = ch.hi - (y - top) / LANE * (ch.hi - ch.lo)
        return max(ch.lo, min(ch.hi, round(v / ch.step) * ch.step))

    # ----- drawing

    def draw(self):
        c = self.canvas
        c.delete('all')
        n = len(self.columns)
        view = max(c.winfo_width(), 100)
        width = max(n * COL + 2 * PAD, view)
        c.configure(scrollregion=(0, 0, width, self.height))
        if self.axis is not None:
            self.draw_axis()
        if not n:
            c.create_text(view // 2, TOP + BLOCK // 2 + (LANE // 2 if self.graph else 0), text=self.hint or 'No sound in this line.',
                          fill=MUTED, font=font(10), width=max(view - 40, 80))
            return
        for k, col in enumerate(self.columns):
            self.draw_column(k, col)
        if self.graph and self.channel:
            self.draw_graph()
        self.reveal()

    def draw_axis(self):
        a = self.axis
        a.delete('all')
        if not self.channel:
            return
        ch = CHANNEL[self.channel]
        top = TOP + BLOCK + GAP
        a.create_text(AXIS - 6, top - 8, text=ch.unit, anchor='e', fill=MUTED, font=font(7))
        for v in self.marks(ch):
            y = top + (ch.hi - v) / (ch.hi - ch.lo) * LANE
            a.create_text(AXIS - 6, y, text=f'{v:+d}' if v else '0', anchor='e', fill=MUTED, font=font(8))

    @staticmethod
    def marks(ch):
        """The values written on the side of the graph."""
        span = ch.hi - ch.lo
        step = 6 if ch.key == 'pitch' else 50 if ch.key == 'length' else 10
        out = [v for v in range(ch.lo, ch.hi + 1) if v % step == 0] if span else []
        return out

    def draw_column(self, k, col):
        c, it = self.canvas, col.item
        x = self.x0(k)
        if k == self.selected:
            c.create_rectangle(x, 0, x + COL, self.height, fill=SELECTED, outline='')
        left, right, top, bottom = x + 3, x + COL - 3, TOP, TOP + BLOCK
        mid = (left + right) // 2
        if it.kind == 'mora':
            c.create_rectangle(left, top, right, bottom, fill=PANEL, outline=ORANGE if k == self.selected else SAND, width=2)
            c.create_text(mid, top + 20, text=it.text, fill=BROWN, font=font(16, True))
            c.create_text(mid, bottom - 9, text=romaji(it.text), fill=MUTED, font=font(7))
        elif it.kind == 'mark':
            c.create_rectangle(left, top + 6, right, bottom, fill=SAND, outline=ORANGE if k == self.selected else SAND, width=2)
            c.create_text(mid, top + 22, text=shown_mark(it.text), fill=DARK, font=font(15, True))
            c.create_text(mid, bottom - 9, text=mark_name(it.text), fill=BROWN, font=font(6))
        elif it.kind == 'slot':
            c.create_rectangle(left, top, right, bottom, fill=PANEL, outline=ORANGE if k == self.selected else MUTED, width=2, dash=(3, 2))
            c.create_text(mid, top + 20, text='◇', fill=MUTED, font=font(16))
            c.create_text(mid, bottom - 9, text=CODE_NAMES.get(it.text[:6], 'game'), fill=MUTED, font=font(7))
        else:
            label = f'{it.name} {it.value}' if it.kind == 'tag' and it.value is not None else it.name if it.kind == 'tag' else it.text
            c.create_rectangle(left, top + 12, right, bottom - 4, fill=CANVAS, outline=ORANGE if k == self.selected else MUTED, width=2 if k == self.selected else 1)
            c.create_text(mid, (top + bottom) // 2 + 4, text=label if len(label) <= 8 else label[:7] + '…', fill=MUTED, font=font(7))

    def draw_graph(self):
        c, ch = self.canvas, CHANNEL[self.channel]
        top = TOP + BLOCK + GAP
        width = max(len(self.columns) * COL + 2 * PAD, c.winfo_width())
        c.create_rectangle(0, top, width, top + LANE, fill=PANEL, outline='')
        for v in self.marks(ch):
            y = top + (ch.hi - v) / (ch.hi - ch.lo) * LANE
            c.create_line(0, y, width, y, fill=DARK if v == 0 else SAND, width=2 if v == 0 else 1)
        zero = top + (ch.hi - 0) / (ch.hi - ch.lo) * LANE
        for k, col in enumerate(self.columns):
            if col.item.kind not in CARRIERS:
                continue
            value = max(ch.lo, min(ch.hi, getattr(col, self.channel)))
            y = top + (ch.hi - value) / (ch.hi - ch.lo) * LANE
            x = self.x0(k)
            c.create_rectangle(x + 9, min(y, zero), x + COL - 9, max(y, zero) + (1 if y == zero else 0),
                               fill=DARK if k == self.selected else ORANGE, outline='')
            c.create_rectangle(x + 5, y - 2, x + COL - 5, y + 2, fill=BROWN, outline='')

    def reveal(self):
        """Scrolls so that the selected column can be seen."""
        if self.selected is None or not self.columns or self.canvas.winfo_width() < 50:
            return                                   # nothing selected, or the canvas is not laid out yet
        total = max(len(self.columns) * COL + 2 * PAD, self.canvas.winfo_width())
        left, right = (f * total for f in self.canvas.xview())
        x = self.x0(self.selected)
        if x < left:
            self.canvas.xview_moveto(max(0, (x - COL) / total))
        elif x + COL > right:
            self.canvas.xview_moveto(min(1, (x + 2 * COL - self.canvas.winfo_width()) / total))

    # ----- text under the strip

    def describe(self, k):
        if k is None or k >= len(self.columns):
            self.info.set('')
            return
        col = self.columns[k]
        it = col.item
        if it.kind == 'mora':
            text = f'{it.text}  ({romaji(it.text) or "?"})'
        elif it.kind == 'mark':
            text = f'{shown_mark(it.text)}  {mark_name(it.text)}: {mark_info(it.text)}'
        elif it.kind == 'slot':
            text = 'A game code: the game puts a name, a number or a syllable of a song here.'
        elif it.kind == 'tag':
            text = f'Command {it.name}' + (f' = {it.value}' if it.value is not None else '')
        else:
            text = f'"{it.text}" is skipped by the engine.'
        if self.graph and it.kind in CARRIERS:
            text += f'   pitch {col.pitch:+.1f} semitones, length {col.length:+.0f}, volume {col.volume:+.1f} dB'
        self.info.set(text)

    # ----- the mouse and the keys

    def press(self, event):
        self.canvas.focus_set()
        k = self.column_at(event.x)
        self.drag = False
        if k is None:
            return
        self.on_select(k)
        if self.graph and self.channel and event.y >= TOP + BLOCK + GAP // 2 and self.columns[k].item.kind in CARRIERS:
            self.drag = True
            self.on_paint(k, self.lane_value(self.canvas.canvasy(event.y)), True)

    def motion(self, event):
        if not self.drag:
            return
        k = self.column_at(event.x)
        if k is not None and self.columns[k].item.kind in CARRIERS:
            self.on_paint(k, self.lane_value(self.canvas.canvasy(event.y)), False)

    def release(self, event):
        self.drag = False

    def double(self, event):
        k = self.column_at(event.x)
        if k is not None and self.on_edit is not None:
            self.on_edit(k)

    def hover(self, event):
        if not self.drag:
            k = self.column_at(event.x)
            self.describe(self.selected if k is None else k)

    def key(self, name):
        if self.on_key is not None:
            self.on_key(name)
        return 'break'
