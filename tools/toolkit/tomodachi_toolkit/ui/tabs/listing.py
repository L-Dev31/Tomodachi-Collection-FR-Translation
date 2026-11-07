"""A tab made of a search bar, a list on the left and a detail area on the right."""
import tkinter as tk
from tkinter import ttk

from ..theme import MUTED
from ..widgets import RIGHT, RevertButton, batch_buttons, popup, tree_with_scrollbar
from .base import Tab


class ListingTab(Tab):
    """Subclasses implement fill() (rebuild the list from self.query and self.only)."""

    def build_bar(self, search_width=22, batch=None):
        """The bar of the tab: search box, Modified only, count and, at the right, the batch buttons (batch: the (export, import, revert)
        commands of Batch export, Batch import and Revert all; see batch_buttons, None leaves one out)."""
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

    def build_listing(self, search_width=22, batch=None, weights=(1, 3), **tree_options):
        """Builds the bar and the two panes. Returns the right pane."""
        self.build_bar(search_width, batch)
        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True, pady=(8, 0))
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=weights[0])
        body.add(right, weight=weights[1])
        options = {'show': 'tree', 'selectmode': 'browse', 'height': 16}
        options.update(tree_options)
        self.tree = tree_with_scrollbar(left, **options)
        self.revert_button = RevertButton(right, self.revert)
        self.revert_button.pack(side='bottom', anchor='e', pady=(8, 0))     # packed first: the content of the pane fills what is left
        return right

    def build_menu(self, entries):
        """The right click on a row of the list selects it and shows a menu: entries(iid) gives its (label, command) pairs (None between two
        groups, a command that is None greys its entry), or nothing for a row that has no menu."""
        def show(event):
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
                items = entries(iid)
                if items:
                    popup(self.tree, event, items)
        self.tree.bind(RIGHT, show)

    def item_changed(self):
        """Whether the item on show has changes that can be taken back: then 'Revert changes', at the bottom right of the pane, is enabled."""
        return False

    def revert(self):
        """Takes back the changes of the item on show."""

    def sync_revert(self):
        self.revert_button.show(self.item_changed())

    def changed(self):
        super().changed()
        if hasattr(self, 'revert_button'):
            self.sync_revert()

    def fill(self):
        raise NotImplementedError
