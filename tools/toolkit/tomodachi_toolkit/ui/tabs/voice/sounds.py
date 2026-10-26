"""The Sounds page: the sounds of the line as blocks, and a palette to change what it says."""
from tkinter import ttk

from .palette import Palette
from .strip import LineStrip

MODES = (('Add after the block', 'after'), ('Add before the block', 'before'), ('Replace the block', 'replace'))


class SoundsPage(ttk.Frame):
    """Changes the pronunciation of the line: which sounds it says and which marks (pauses, melody) are between them."""

    def __init__(self, master, editor):
        super().__init__(master, padding=8)
        self.editor = editor
        self.strip = LineStrip(self, select=editor.select, key=editor.key)
        self.strip.pack(fill='x')
        self.clear_button = ttk.Button(self.strip.tools, text='Clear line', style='Mini.TButton', command=editor.clear)
        self.clear_button.pack(side='right')
        self.delete_button = ttk.Button(self.strip.tools, text='Delete block', style='Mini.TButton', command=editor.delete)
        self.delete_button.pack(side='right', padx=(0, 4))
        self.palette = Palette(self, lambda text: editor.put(text, self.mode()))
        self.palette.pack(fill='x', pady=(10, 0))
        self.mode_box = ttk.Combobox(self.palette.tools, state='readonly', width=20, values=[t for t, _ in MODES])
        self.mode_box.current(0)
        self.mode_box.pack(side='right')
        self.refresh()

    def mode(self):
        """'after', 'before' or 'replace': where the sounds that are clicked go."""
        return MODES[max(self.mode_box.current(), 0)][1]

    def refresh(self):
        e = self.editor
        cols = e.columns()
        hint = 'Choose a line in the list.' if not e.active else 'Nothing is said in this line. Click a sound below to add some.'
        self.strip.show(cols, e.sel, hint=hint)
        self.palette.set_enabled(e.active)
        self.delete_button.state(['!disabled'] if e.sel is not None else ['disabled'])
        self.clear_button.state(['!disabled'] if cols else ['disabled'])
