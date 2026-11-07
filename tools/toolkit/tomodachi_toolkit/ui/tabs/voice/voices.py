"""The panel of a voice, a mood or an effect: the presets of the speech engine as sliders, written to the ROM."""
import re
import tkinter as tk
from tkinter import ttk

from ....features.speech.presets import SCRIPT_KEYS, SCRIPT_REL, SPEECH_PROPS, script_check, script_join, script_parse, script_set, script_value
from ...theme import ERROR, MUTED, PANEL, SAND, font

KEYS = 'BSXVAPIJRGr'                                          # the order of the rows
SPAN = {'B': 1500, 'S': 200, 'V': 1000, 'A': 200, 'P': 200}   # how far the slider goes when a value is relative
NUMBER = re.compile(r'\+?-?\d+')                              # 4800, -5, +200, +-60


class SettingRow(ttk.Frame):
    """One property of a script: name, slider, number, relative switch and a button that removes it.

    on_edit(key, text) saves the new value text and returns an error text, or None when it was accepted.
    number and relative are Tk variables lent by the panel: rows come and go, the variables stay (a variable that is
    freed while the speech thread runs would be freed from that thread).
    """

    def __init__(self, master, key, text, number, relative, on_edit, on_remove):
        super().__init__(master)
        self.key, self.on_edit, self.accepted, self.quiet = key, on_edit, text, False
        self.name, self.lo, self.hi, self.neutral = SPEECH_PROPS[SCRIPT_KEYS[key]]
        ttk.Label(self, text=self.name, width=11).grid(row=0, column=0, sticky='w')
        if text in ('', '+'):
            note = 'set by the command in the line' + (' (relative)' if text else '')
            ttk.Label(self, text=note, foreground=MUTED).grid(row=0, column=1, columnspan=3, sticky='w')
        else:
            self.number, self.relative = number, relative
            self.scale = ttk.Scale(self, orient='horizontal', length=170, command=self.slid)
            self.scale.grid(row=0, column=1, padx=(0, 8))
            self.spin = ttk.Spinbox(self, textvariable=self.number, width=6, command=self.edit)
            self.spin.grid(row=0, column=2)
            self.spin.bind('<Return>', lambda e: self.edit())
            self.spin.bind('<FocusOut>', lambda e: self.edit())
            if key in SCRIPT_REL:
                ttk.Checkbutton(self, text='relative', variable=self.relative, command=self.toggled).grid(row=0, column=3, padx=(8, 0))
            self.show(text)
        ttk.Button(self, text='✕', width=2, style='Small.TButton', command=lambda: on_remove(key)).grid(row=0, column=4, padx=(8, 0))

    def show(self, text):
        """Puts a value text (4800, -5, +200, +-60) on the widgets."""
        n = int(text.lstrip('+'))
        self.quiet = True
        self.relative.set(text.startswith('+'))
        self.set_range(text.startswith('+'), n)
        self.number.set(str(n))
        self.scale.set(n)
        self.quiet = False

    def set_range(self, relative, n):
        """Absolute values go from the engine's minimum to its maximum; relative ones around zero."""
        span = max(SPAN.get(self.key, 200), abs(n))
        lo, hi = (-span, span) if relative else (self.lo, self.hi)
        self.scale.configure(from_=lo, to=hi)
        self.spin.configure(from_=lo, to=hi)

    def slid(self, value):
        n = str(int(round(float(value))))
        if not self.quiet and n != self.number.get():
            self.number.set(n)
            self.edit()

    def toggled(self):
        relative = self.relative.get()
        n = 0 if relative else self.neutral
        self.quiet = True
        self.set_range(relative, n)
        self.number.set(str(n))
        self.scale.set(n)
        self.quiet = False
        self.edit()

    def edit(self):
        """Sends what the widgets show to the panel; puts the last accepted value back when it is refused."""
        if not self.winfo_exists():
            return
        try:
            n = int(self.number.get())
        except ValueError:
            self.show(self.accepted)
            return
        text = ('+' if self.relative.get() else '') + str(n)
        if text == self.accepted:
            return
        if self.on_edit(self.key, text) is None:
            self.accepted = text
            self.quiet = True
            self.scale.set(n)
            self.quiet = False
        else:
            self.show(self.accepted)


class VoicePanel(ttk.Frame):
    """Edits the preset (a voice, a mood or an effect) that the tab shows. The tab tells it when a preset changed: preset_changed(name)."""

    def __init__(self, master, tab):
        super().__init__(master, padding=8)
        self.tab = tab
        self.catalog, self.name, self.rows = None, None, {}
        self.syncing, self.script_shown = False, False
        self.variables = {key: (tk.StringVar(), tk.BooleanVar()) for key in KEYS}
        self.title, self.message = tk.StringVar(), tk.StringVar()
        head = ttk.Frame(self)
        head.pack(fill='x')
        ttk.Label(head, textvariable=self.title, font=font(10, True)).pack(side='left')
        self.rows_box = ttk.Frame(self)
        self.rows_box.pack(fill='x', pady=(8, 0))
        bar = ttk.Frame(self)
        bar.pack(fill='x', pady=(6, 0))
        self.add_button = ttk.Menubutton(bar, text='Add a setting')
        self.add_menu = tk.Menu(self.add_button, tearoff=0)
        self.add_button['menu'] = self.add_menu
        self.add_button.pack(side='left')
        self.script_button = ttk.Button(bar, text='Script ▸', style='Mini.TButton', command=self.toggle_script)
        self.script_button.pack(side='right')
        self.script = tk.Text(self, height=5, width=40, font=('Consolas', 9), bg=PANEL, relief='flat', highlightthickness=1, highlightbackground=SAND)
        self.script.bind('<KeyRelease>', self.script_typed)
        self.message_label = ttk.Label(self, textvariable=self.message, foreground=ERROR, wraplength=560, justify='left')
        self.message_label.pack(fill='x', pady=(6, 0))

    # ----- the presets of the ROM

    def load(self, catalog):
        self.catalog = catalog

    def unload(self):
        self.catalog, self.name = None, None

    def kind(self, name):
        c = self.catalog
        return 'voice' if name in c.voices else 'mood' if name in c.emotions else 'effect'

    def label(self, name):
        """How the tree names a preset."""
        c = self.catalog
        return c.voice_label(name) if name in c.voices else c.label(name) if name in c.emotions else c.command_label(name)

    def show(self, name):
        """Draws the panel for a preset (a name like '<\\Spk_male')."""
        self.name = name
        self.message.set('')
        self.title.set(f'{self.kind(name).capitalize()}: {self.label(name)}')
        self.rebuild()

    # ----- drawing

    def rebuild(self, sync=True):
        """Rows for the properties of the script, the menu of the ones that can be added, the script text."""
        c, name = self.catalog, self.name
        for w in self.rows_box.winfo_children():
            w.destroy()
        self.rows = {}
        self.add_menu.delete(0, 'end')
        script = c.script(name)
        items = script_parse(script)
        for key in KEYS:
            value = script_value(items, key)
            if value is not None and (value in ('', '+') or NUMBER.fullmatch(value)):
                row = SettingRow(self.rows_box, key, value, *self.variables[key], self.edit, self.remove)
                row.pack(fill='x', pady=2)
                self.rows[key] = row
        for key in KEYS:
            if key not in self.rows:
                label, lo, hi, _ = SPEECH_PROPS[SCRIPT_KEYS[key]]
                self.add_menu.add_command(label=f'{label}   ({lo} to {hi})', command=lambda k=key: self.add(k))
        self.add_button.state(['!disabled'] if self.add_menu.index('end') is not None else ['disabled'])
        if sync:
            self.sync_script(script)

    def sync_script(self, script):
        self.syncing = True
        self.script.delete('1.0', 'end')
        self.script.insert('1.0', script)
        self.syncing = False

    def toggle_script(self):
        self.script_shown = not self.script_shown
        if self.script_shown:
            self.script.pack(fill='x', pady=(6, 0), before=self.message_label)
        else:
            self.script.pack_forget()
        self.script_button.configure(text='Script ▾' if self.script_shown else 'Script ▸')

    # ----- editing

    def edit(self, key, text):
        """Writes one property into the script of the preset ('' removes it). Returns an error text, or None."""
        script = script_join(script_set(script_parse(self.catalog.script(self.name)), key, text))
        bad = script_check(script)
        self.message.set(bad or '')
        if bad:
            return bad
        self.catalog.set(self.name, script)
        self.sync_script(script)
        self.changed()
        return None

    def remove(self, key):
        if self.edit(key, '') is None:
            self.after_idle(self.rebuild)

    def add(self, key):
        if self.edit(key, str(SPEECH_PROPS[SCRIPT_KEYS[key]][3])) is None:
            self.rebuild()

    def script_typed(self, event=None):
        """The script text was edited by hand: keep it when it is valid and let the rows follow it."""
        if self.syncing or self.name is None:
            return
        script = self.catalog.norm(self.script.get('1.0', 'end'))
        bad = script_check(script)
        self.message.set(bad or '')
        if bad:
            return
        self.catalog.set(self.name, script)
        self.changed()
        self.rebuild(sync=False)

    def changed(self):
        self.tab.preset_changed(self.name)
