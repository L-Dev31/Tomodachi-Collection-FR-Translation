"""Tabs of tabs: the window has one page per group. A group of several tabs holds a notebook of its own."""
from tkinter import ttk


class Pages(ttk.Notebook):
    """The top notebook. `groups` is [(label, [Tab classes])]; `shown()` is called when another tab becomes the one on show.

    A group with one tab shows it directly under the label of the group. A group with several shows a second row of tabs;
    it starts on its first tab and then keeps the one the person went to last.
    """

    def __init__(self, app, groups, shown):
        super().__init__(app)
        self.tabs = []                  # every tab, in order
        self.groups = []                # [(label, [tabs])]
        self.inner = {}                 # page of a group (a frame) -> the notebook it holds
        self.page_of = {}               # label of a group -> its page in this notebook
        self.shown = shown
        for label, classes in groups:
            if len(classes) == 1:
                tab = classes[0](app, self)
                self.add(tab, text=f'  {label}  ')
                members = [tab]
                self.page_of[label] = tab
            else:
                page = ttk.Frame(self)
                notebook = ttk.Notebook(page, style='Sub.TNotebook')
                notebook.pack(fill='both', expand=True)
                notebook.bind('<<NotebookTabChanged>>', lambda e: shown())
                members = []
                for cls in classes:
                    tab = cls(app, notebook)
                    notebook.add(tab, text=f'  {tab.title}  ')
                    members.append(tab)
                self.add(page, text=f'  {label}  ')
                self.inner[page] = notebook
                self.page_of[label] = page
            self.tabs += members
            self.groups.append((label, members))
        self.bind('<<NotebookTabChanged>>', lambda e: self.group_opened())

    # ----- what is on show

    def holder(self, tab):
        """The notebook that holds a tab directly."""
        return tab.master

    def current(self):
        """The tab that is on show."""
        page = self.nametowidget(self.select())
        notebook = self.inner.get(page)
        return page if notebook is None else self.nametowidget(notebook.select())

    def group_opened(self):
        """Another page of the top notebook is on show."""
        self.settle()
        self.shown()

    def show(self, tab):
        """Goes to a tab, whatever group it is in."""
        notebook = self.holder(tab)
        if notebook is not self:
            self.select(notebook.master)
        notebook.select(tab)

    def settle(self):
        """Every group shows one of its tabs. A notebook whose tabs were all disabled has none selected (and shows nothing)
        until it is told which: the first one that works."""
        for notebook in self.inner.values():
            if not notebook.select():
                tab = next((n for n in notebook.tabs() if notebook.tab(n, 'state') == 'normal'), None)
                if tab is not None:
                    notebook.select(tab)

    def group_of(self, tab):
        return next(label for label, members in self.groups if tab in members)

    # ----- enabling

    def set_enabled(self, tab, on):
        self.holder(tab).tab(tab, state='normal' if on else 'disabled')
        self.settle()
        self.sync_groups()

    def sync_groups(self):
        """A group whose tabs are all disabled is disabled itself."""
        for page, notebook in self.inner.items():
            live = any(notebook.tab(name, 'state') == 'normal' for name in notebook.tabs())
            self.tab(page, state='normal' if live else 'disabled')

    def state_of(self, tab):
        return str(self.holder(tab).tab(tab, 'state'))
