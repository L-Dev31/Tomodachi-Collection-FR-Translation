"""A tab made of a search bar, a list on the left and a detail area on the right."""
import tkinter as tk
from tkinter import ttk

from ..theme import MUTED
from ..widgets import batch_buttons, tree_with_scrollbar
from .base import Tab


class ListingTab(Tab):
    """Subclasses implement fill() (rebuild the list from self.query and self.only)."""

    def build_listing(self, search_width=22, batch=None, more=(), revert_all=None, weights=(1, 3), **tree_options):
        """Builds the bar and the two panes. batch: (export, import, revert) commands of the Batch export, Batch import and Revert all
        buttons at the right of the bar (see batch_buttons; None leaves one out). Returns the right pane."""
        self.query = tk.StringVar()
        self.only = tk.BooleanVar(value=False)
        self.count = tk.StringVar()
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        self.search = ttk.Entry(bar, textvariable=self.query, width=search_width)
        self.search.pack(side='left')
        self.query.trace_add('write', lambda *_: self.fill())
        ttk.Checkbutton(bar, text='Modified only', variable=self.only, command=self.fill).pack(side='left', padx=8)
        ttk.Label(bar, textvariable=self.count, foreground=MUTED).pack(side='left')
        if batch:
            self.batch = batch_buttons(bar, *batch)
            self.batch.pack(side='right')
        elif more:
            button = ttk.Menubutton(bar, text='More')
            self.more_menu = tk.Menu(button, tearoff=0)
            for item in more:
                if item is None:
                    self.more_menu.add_separator()
                else:
                    self.more_menu.add_command(label=item[0], command=item[1])
            button['menu'] = self.more_menu
            button.pack(side='right')
            if revert_all:
                ttk.Button(bar, text='Revert all', style='Soft.TButton', command=revert_all).pack(side='right')
        elif revert_all:
            ttk.Button(bar, text='Revert all', style='Soft.TButton', command=revert_all).pack(side='right')
        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True, pady=(8, 0))
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=weights[0])
        body.add(right, weight=weights[1])
        options = {'show': 'tree', 'selectmode': 'browse', 'height': 16}
        options.update(tree_options)
        self.tree = tree_with_scrollbar(left, **options)
        self._menu = tk.Menu(self.tree, tearoff=0)
        self._menu.add_command(label='Export selected', command=self._ctx_export)
        self._menu.add_command(label='Replace selected...', command=self._ctx_replace)
        self._menu.add_separator()
        self._menu.add_command(label='Revert selected', command=self._ctx_revert)
        self.tree.bind('<Button-3>', self._ctx_show)
        self.tree.bind('<Control-Button-1>', self._ctx_show)
        return right

    def _ctx_show(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _ctx_export(self):
        """Export the selected item(s): for Voice, bank or line; for others, the selected row."""
        # Try tab-specific first
        fn = getattr(self, 'export_selected', None)
        if callable(fn):
            fn()
            return
        # Fallback to generic
        fm = getattr(self, 'export_model', None)
        if callable(fm):
            fm()
            return
        fe = getattr(self, 'export_lines', None)
        if callable(fe):
            fe()
            return

    def _ctx_replace(self):
        """Replace the selected item with a file import."""
        fn = getattr(self, 'replace_selected', None)
        if callable(fn):
            fn()
            return
        fr = getattr(self, 'replace', None)
        if callable(fr):
            fr()
            return

    def _ctx_revert(self):
        """Revert the selected item(s) to the ROM original."""
        fr = getattr(self, 'revert_selected', None)
        if callable(fr):
            fr()
            return
        fr = getattr(self, 'revert', None)
        if callable(fr):
            fr()
            return

    def fill(self):
        raise NotImplementedError
