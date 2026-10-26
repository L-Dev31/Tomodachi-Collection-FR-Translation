"""A tab made of a search bar, a list on the left and a detail area on the right."""
import tkinter as tk
from tkinter import ttk

from ..theme import MUTED
from ..widgets import tree_with_scrollbar
from .base import Tab


class ListingTab(Tab):
    """Subclasses implement fill() (rebuild the list from self.query and self.only)."""

    def build_listing(self, search_width=22, more=(), revert_all=None, weights=(1, 3), **tree_options):
        """Builds the bar and the two panes. more: [(label, command) or None for a separator] for the More menu.
        Returns the right pane."""
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
        if more:
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
        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True, pady=(8, 0))
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=weights[0])
        body.add(right, weight=weights[1])
        options = {'show': 'tree', 'selectmode': 'browse', 'height': 16}
        options.update(tree_options)
        self.tree = tree_with_scrollbar(left, **options)
        return right

    def fill(self):
        raise NotImplementedError
