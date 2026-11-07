"""Small reusable widgets of the toolkit."""
import sys
import tkinter as tk
from tkinter import ttk

import numpy as np

from ..core.png import png_write
from .theme import BROWN, CANVAS, DARK, FAMILY, LINK, MUTED, PANEL, SAND, font


def card(parent, padx=14, pady=14):
    """A white panel with a thin sand border."""
    return tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=SAND, padx=padx, pady=pady)


def caption(parent, text, **grid):
    """Small orange heading inside a card."""
    label = tk.Label(parent, text=text, bg=PANEL, fg=DARK, font=font(8, True))
    if grid:
        label.grid(**grid)
    return label


def batch_buttons(parent, export, import_, revert=None):
    """The buttons every tab has for working on many things at once, always in this order: Batch export (everything the tab holds to a
    folder), Batch import (from a folder) and Revert all (every change of the tab taken back). A command that is None leaves its button
    out. Returns the frame that holds them; the caller packs it where it belongs. The buttons are its attributes export_button,
    import_button and revert_button (None when left out)."""
    frame = ttk.Frame(parent)
    frame.export_button = ttk.Button(frame, text='Batch export', style='Soft.TButton', command=export) if export else None
    frame.import_button = ttk.Button(frame, text='Batch import', style='Soft.TButton', command=import_) if import_ else None
    frame.revert_button = ttk.Button(frame, text='Revert all', style='Soft.TButton', command=revert) if revert else None
    for i, button in enumerate(b for b in (frame.export_button, frame.import_button, frame.revert_button) if b is not None):
        button.pack(side='left', padx=(6 if i else 0, 0))
    return frame


RIGHT = '<Button-2>' if sys.platform == 'darwin' else '<Button-3>'      # the right click


def popup(widget, event, entries):
    """A menu at the pointer. entries: (label, command) pairs, None for a line between two groups; a command that is None greys its entry."""
    menu = tk.Menu(widget, tearoff=0)
    for entry in entries:
        if entry is None:
            menu.add_separator()
        else:
            menu.add_command(label=entry[0], command=entry[1], state='normal' if entry[1] else 'disabled')
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def copy_text(widget, text):
    widget.clipboard_clear()
    widget.clipboard_append(text)


def flash(label, text, rest='', ms=1600):
    """Shows text in a label for a moment, then rest: the answer to something that leaves no other trace."""
    if getattr(label, 'flash_job', None):
        label.after_cancel(label.flash_job)
    label.config(text=text)
    label.flash_job = label.after(ms, lambda: label.config(text=rest))


class InfoTable(ttk.Frame):
    """What is selected, as a table of (name, value) rows. A row that has a third item (a function) is a link: it is underlined and a
    click on it calls the function."""

    def __init__(self, master):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=('value',), show='tree', selectmode='none', height=1)
        self.tree.column('#0', width=96, stretch=False)
        self.tree.column('value', width=320)
        self.tree.tag_configure('link', foreground=LINK, font=(FAMILY, 9, 'underline'))
        self.tree.pack(fill='x')
        self.links = {}
        self.tree.bind('<Button-1>', self.click)
        self.tree.bind('<Motion>', lambda e: self.tree.configure(cursor='hand2' if self.tree.identify_row(e.y) in self.links else ''))

    def show(self, rows):
        tree = self.tree
        tree.delete(*tree.get_children())
        self.links = {}
        for row in rows:
            iid = tree.insert('', 'end', text=row[0], values=(row[1],), tags=('link',) if len(row) > 2 else ())
            if len(row) > 2:
                self.links[iid] = row[2]
        tree.configure(height=max(1, len(rows)))

    def click(self, event):
        command = self.links.get(self.tree.identify_row(event.y))
        if command:
            command()
        return 'break'


class RevertButton(ttk.Button):
    """'Revert changes': a button of the layout. The tab packs it at the bottom right of its pane, where it keeps its place like any other
    widget. It is greyed out when there is nothing to take back: show(on) says whether there is."""

    def __init__(self, master, command):
        super().__init__(master, text='Revert changes', style='Soft.TButton', command=command)
        self.state(['disabled'])

    def show(self, on):
        self.state(['!disabled'] if on else ['disabled'])


class Hint:
    """A few words that appear under a widget when the pointer rests on it (and go when it leaves or clicks)."""

    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay, self.tip, self.job = widget, text, delay, None, None
        widget.bind('<Enter>', self.enter, add='+')
        widget.bind('<Leave>', self.leave, add='+')
        widget.bind('<ButtonPress>', self.leave, add='+')

    def enter(self, event=None):
        self.leave()
        self.job = self.widget.after(self.delay, self.show)

    def show(self):
        self.job = None
        tip = self.tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry('+%d+%d' % (self.widget.winfo_rootx() + 12, self.widget.winfo_rooty() + self.widget.winfo_height() + 4))
        tk.Label(tip, text=self.text, bg='#FFF8E6', fg=BROWN, bd=1, relief='solid', padx=7, pady=4, justify='left', wraplength=320,
                 font=font(9)).pack()

    def leave(self, event=None):
        if self.job is not None:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


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
    picture = np.frombuffer(bytes(rgba), np.uint8).reshape(h, w, 4)
    alpha = picture[..., 3:].astype(np.uint16)
    if alpha.min(initial=255) == 255:
        return bytes(rgba)
    squares = (np.arange(w) // 8)[None, :] + (np.arange(h) // 8)[:, None]
    grey = np.where(squares % 2, 205, 235).astype(np.uint16)[..., None]
    shown = np.full((h, w, 4), 255, np.uint8)
    shown[..., :3] = (picture[..., :3] * alpha + grey * (255 - alpha)) // 255
    return shown.tobytes()


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
