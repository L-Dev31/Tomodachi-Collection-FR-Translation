"""The Voices page: the presets of the speech engine (voices, moods and effects) as sliders, written to the ROM."""
import re
import tkinter as tk
from tkinter import messagebox, ttk

from ....features.speech.presets import SCRIPT_KEYS, SCRIPT_REL, SPEECH_PROPS, script_check, script_join, script_parse, script_set, script_value
from ...theme import ERROR, MUTED, PANEL, SAND

KEYS = 'BSXVAPIJRGr'                                          # the order of the rows
SPAN = {'B': 1500, 'S': 200, 'V': 1000, 'A': 200, 'P': 200}   # how far the slider goes when a value is relative
NUMBER = re.compile(r'\+?-?\d+')                              # 4800, -5, +200, +-60
HINTS = {
    'voice': 'A voice is a set of base settings (pitch, speed, tone) for the speech engine.',
    'mood': 'A mood changes the voice for a whole line. A line starts with it (see the Rhythm page).',
    'effect': 'An effect is a command put inside a line, with a value (see the Rhythm page).',
}


class SettingRow(ttk.Frame):
    """One property of a script: name, slider, number, relative switch and a button that removes it.

    on_edit(key, text) saves the new value text and returns an error text, or None when it was accepted.
    number and relative are Tk variables lent by the page: rows come and go, the variables stay (a variable that is
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
        """Sends what the widgets show to the page; puts the last accepted value back when it is refused."""
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


class SettingsPage(ttk.Frame):
    """Edits one preset at a time: the one chosen in the list at the top (a voice, a mood or an effect)."""

    def __init__(self, master, tab):
        super().__init__(master, padding=8)
        self.tab = tab
        self.catalog, self.names, self.rows = None, [], {}
        self.syncing, self.script_shown = False, False
        self.variables = {key: (tk.StringVar(), tk.BooleanVar()) for key in KEYS}
        self.message, self.about = tk.StringVar(), tk.StringVar()
        head = ttk.Frame(self)
        head.pack(fill='x')
        ttk.Label(head, text='Settings of').pack(side='left')
        self.box = ttk.Combobox(head, state='readonly', width=26)
        self.box.pack(side='left', padx=6)
        self.box.bind('<<ComboboxSelected>>', lambda e: self.show())
        self.reset_all_button = ttk.Button(head, text='Reset all', style='Mini.TButton', command=self.reset_all)
        self.reset_all_button.pack(side='right')
        self.reset_button = ttk.Button(head, text='Reset', style='Mini.TButton', command=self.reset)
        self.reset_button.pack(side='right', padx=(0, 6))
        ttk.Label(self, textvariable=self.about, foreground=MUTED, wraplength=560, justify='left').pack(fill='x', pady=(6, 0))
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

    def kind(self, name):
        c = self.catalog
        return 'voice' if name in c.voices else 'mood' if name in c.emotions else 'effect'

    def label(self, name):
        c = self.catalog
        kind = self.kind(name)
        text = c.voice_label(name) if kind == 'voice' else c.label(name) if kind == 'mood' else c.command_label(name)
        return c.mark(name, f'{kind.capitalize()}: {text}')

    def load(self, catalog):
        self.catalog = catalog
        self.names = list(catalog.voices) + list(catalog.emotions) + list(catalog.commands)
        self.refresh_marks(keep=False)
        self.box.current(0)
        self.show()

    def unload(self):
        self.catalog, self.names = None, []
        self.box['values'] = []
        self.box.set('')
        for w in self.rows_box.winfo_children():
            w.destroy()
        self.rows = {}
        self.about.set('')
        self.message.set('')
        self.sync_script('')
        self.reset_button.state(['disabled'])
        self.reset_all_button.state(['disabled'])
        self.add_button.state(['disabled'])

    def target(self):
        """Name of the preset that is edited, or None."""
        i = self.box.current()
        return self.names[i] if self.catalog is not None and 0 <= i < len(self.names) else None

    def choose(self, name):
        """Shows the settings of a preset (a name like '<\\Spk_male')."""
        if self.catalog is not None and name in self.names:
            self.box.current(self.names.index(name))
            self.show()

    # ----- drawing

    def refresh_marks(self, keep=True):
        """The dots of the changed presets in the list, and the state of the reset buttons."""
        c = self.catalog
        if c is None:
            return
        i = self.box.current()
        self.box['values'] = [self.label(n) for n in self.names]
        if keep and i >= 0:
            self.box.current(i)
        name = self.target()
        self.reset_button.state(['!disabled'] if name and c.changed(name) else ['disabled'])
        self.reset_all_button.state(['!disabled'] if c.edits else ['disabled'])

    def show(self):
        """Draws the page for the preset that is chosen now."""
        if self.catalog is None:
            return
        self.message.set('')
        self.refresh_marks()
        self.rebuild()

    def rebuild(self, sync=True):
        """Rows for the properties of the script, the menu of the ones that can be added, the script text."""
        c, name = self.catalog, self.target()
        for w in self.rows_box.winfo_children():
            w.destroy()
        self.rows = {}
        self.add_menu.delete(0, 'end')
        if name is None:
            self.about.set('')
            self.add_button.state(['disabled'])
            self.sync_script('')
            return
        self.about.set(HINTS[self.kind(name)])
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

    def apply(self, key, text):
        """Writes one property into the script of the preset ('' removes it). Returns an error text, or None."""
        name = self.target()
        script = script_join(script_set(script_parse(self.catalog.script(name)), key, text))
        bad = script_check(script)
        self.message.set(bad or '')
        if bad:
            return bad
        self.catalog.set(name, script)
        self.sync_script(script)
        self.changed(name)
        return None

    def edit(self, key, text):
        return self.apply(key, text)

    def remove(self, key):
        if self.apply(key, '') is None:
            self.after_idle(self.rebuild)

    def add(self, key):
        if self.apply(key, str(SPEECH_PROPS[SCRIPT_KEYS[key]][3])) is None:
            self.rebuild()

    def script_typed(self, event=None):
        """The script text was edited by hand: keep it when it is valid and let the rows follow it."""
        name = self.target()
        if self.syncing or name is None:
            return
        script = self.catalog.norm(self.script.get('1.0', 'end'))
        bad = script_check(script)
        self.message.set(bad or '')
        if bad:
            return
        self.catalog.set(name, script)
        self.changed(name)
        self.rebuild(sync=False)

    def changed(self, name):
        self.refresh_marks()
        self.tab.preset_changed(name)

    def reset(self):
        name = self.target()
        if name and self.catalog.changed(name):
            self.catalog.reset(name)
            self.changed(name)
            self.show()

    def reset_all(self):
        c = self.catalog
        if c.edits and messagebox.askyesno('Reset presets', f'Put the {len(c.edits)} changed preset(s) back as they are in the ROM?'):
            c.reset_all()
            self.changed(None)
            self.show()
