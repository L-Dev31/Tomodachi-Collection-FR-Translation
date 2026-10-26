"""Small reusable widgets of the toolkit."""
import sys
import tkinter as tk
from tkinter import ttk

from ..core.png import png_write
from .theme import CANVAS, DARK, MUTED, PANEL, SAND, font


def card(parent, padx=14, pady=14):
    """A white panel with a thin sand border."""
    return tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=padx, pady=pady)


def caption(parent, text, **grid):
    """Small orange heading inside a card."""
    label = tk.Label(parent, text=text, bg=PANEL, fg=DARK, font=font(8, True))
    if grid:
        label.grid(**grid)
    return label


def tree_with_scrollbar(parent, **options):
    """A Treeview with its vertical scroll bar, packed into parent. Returns the tree."""
    tree = ttk.Treeview(parent, **options)
    bar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side='left', fill='both', expand=True)
    bar.pack(side='right', fill='y')
    tree.tag_configure('mod', foreground=DARK, font=font(9, True))
    return tree


def checker_composite(w, h, rgba):
    """RGBA bytes whose transparent parts are drawn over a grey checkerboard (fully opaque result)."""
    if rgba[3::4].count(255) == w * h:
        return bytes(rgba)
    shown = bytearray(rgba)
    for i in range(3, len(shown), 4):
        a = shown[i]
        if a < 255:
            x, y = divmod(i // 4, w)[::-1]
            g = 205 if (x // 8 + y // 8) % 2 else 235
            for k in range(3):
                shown[i - 3 + k] = (shown[i - 3 + k] * a + g * (255 - a)) // 255
            shown[i] = 255
    return bytes(shown)


class ImageView(ttk.Frame):
    """Shows a picture on a scrollable canvas. The first view fits the picture to the canvas;
    Ctrl + mouse wheel (what a touchpad pinch sends) zooms, the wheel alone scrolls."""

    MAX_ZOOM = 24

    def __init__(self, master, width=520, height=340):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, width=width, height=height)
        hs = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        vs = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        hs.pack(side='bottom', fill='x')
        vs.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.zoom = None
        self.picture = None
        self._photo = None
        self._pinch = 0
        self._hint = ''
        self.canvas.bind('<Configure>', lambda e: self._place_hint())
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<Button-4>', lambda e: self._notch(1, e))
        self.canvas.bind('<Button-5>', lambda e: self._notch(-1, e))
        self.canvas.bind('<Shift-MouseWheel>', lambda e: self.canvas.xview_scroll(-1 if e.delta > 0 else 1, 'units'))

    def clear(self, hint=''):
        """Empties the view. hint is a line of text shown in the middle of the empty view."""
        self.canvas.delete('all')
        self.canvas.configure(scrollregion=(0, 0, 1, 1))
        self.picture, self._photo, self._hint = None, None, hint
        self._place_hint()

    def _place_hint(self):
        self.canvas.delete('hint')
        if self._hint and self.picture is None:
            width = self.canvas.winfo_width()
            self.canvas.create_text(width // 2, self.canvas.winfo_height() // 2, text=self._hint, fill=MUTED, font=font(10),
                                    justify='center', width=max(width - 40, 100), tags='hint')

    def show(self, w, h, rgba, refit=False):
        """Draws the picture. Keeps the zoom of the previous one unless refit (or no zoom yet)."""
        self.picture = (w, h, rgba)
        if refit or self.zoom is None:
            self.zoom = self._fit(w, h)
        self._draw()

    def _limit(self, w, h):
        return max(1, min(self.MAX_ZOOM, int((16_000_000 / max(w * h, 1)) ** 0.5)))

    def _fit(self, w, h):
        self.update_idletasks()
        cw, ch = max(self.canvas.winfo_width(), 120), max(self.canvas.winfo_height(), 120)
        return max(1, min(self._limit(w, h), (cw - 6) // w, (ch - 6) // h))

    def _draw(self):
        w, h, rgba = self.picture
        self.zoom = max(1, min(self.zoom, self._limit(w, h)))
        photo = tk.PhotoImage(master=self, data=png_write(w, h, checker_composite(w, h, rgba)))
        self._photo = photo.zoom(self.zoom) if self.zoom > 1 else photo
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, w * self.zoom, h * self.zoom))

    def _set_zoom(self, z):
        if self.picture is None or z == self.zoom or z < 1:
            return
        (x0, x1), (y0, y1) = self.canvas.xview(), self.canvas.yview()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.zoom = z
        self._draw()
        self.canvas.xview_moveto(max(0, cx - (x1 - x0) * 0.5))
        self.canvas.yview_moveto(max(0, cy - (y1 - y0) * 0.5))

    def _notch(self, direction, event):
        if event.state & 4:
            self._set_zoom(self.zoom + direction)
        else:
            self.canvas.yview_scroll(-2 * direction, 'units')

    def _wheel(self, event):
        if not event.state & 4:
            self.canvas.yview_scroll(-2 if event.delta > 0 else 2, 'units')
            return
        step = 1 if sys.platform == 'darwin' else 120
        self._pinch += event.delta
        while abs(self._pinch) >= step:
            direction = 1 if self._pinch > 0 else -1
            self._pinch -= direction * step
            self._set_zoom(self.zoom + direction)
