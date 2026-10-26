"""What every tab of the window has in common."""
from tkinter import ttk


class Tab(ttk.Frame):
    """A page of a notebook (the parent: the top one, or the one of its group).

    key      name of its part in the patch configuration and in the project file ('' when it has none)
    title    label of the notebook tab
    heading  label of its line in the summary of the ROM tab ('' when it has none)
    """

    key = ''
    title = ''
    heading = ''

    def __init__(self, app, parent, padding=14):
        super().__init__(parent, padding=padding)
        self.app = app
        self.build()

    @property
    def session(self):
        return self.app.session

    def build(self):
        raise NotImplementedError

    def on_rom(self):
        """A ROM was opened (self.session is the new one): forget the edits and show the first state."""

    def on_show(self):
        """The tab was selected: load what is slow to load."""

    def patch_config(self):
        """The part of the patch configuration of this tab, or None when nothing changed. May raise ValueError."""
        return None

    def project_part(self):
        """What the .tomods file keeps for this tab (empty when nothing changed)."""
        return {}

    def restore(self, part):
        """Puts a project part back. Returns a list of notes for what could not be restored."""
        return []

    def summary(self):
        return 'Unchanged'

    def changed(self):
        self.app.refresh_summary()
