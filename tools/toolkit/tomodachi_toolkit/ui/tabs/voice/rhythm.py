"""The Rhythm page: the pitch, the length and the volume of every sound, the mood of the line, the effects."""
import re
import tkinter as tk
from tkinter import ttk

from ....features.speech.line import CHANNELS, CHANNEL
from ....features.speech.presets import SCRIPT_KEYS, SPEECH_PROPS
from ...theme import MUTED
from .strip import LineStrip

HIDDEN_EFFECTS = ('RPit', 'RSpd', 'RVol')       # the graph writes these
NONE = 'none'
HINT = 'Click or drag in the graph.'


class RhythmPage(ttk.Frame):
    """Changes how the line is said: pitch, length and volume per sound (drawn on a graph), a mood for the whole line, effects."""

    def __init__(self, master, tab):
        super().__init__(master, padding=8)
        self.tab, self.editor, self.catalog = tab, tab.editor, None
        self.moods, self.effects = [], []
        self.channel, self.value = tk.StringVar(value=CHANNELS[0].key), tk.StringVar()
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        ttk.Label(bar, text='Graph').pack(side='left', padx=(0, 6))
        for c in CHANNELS:
            ttk.Radiobutton(bar, text=c.label, value=c.key, variable=self.channel, style='Toolbutton', command=self.refresh).pack(side='left', padx=(0, 3))
        self.flat_button = ttk.Button(bar, text='Flatten', style='Mini.TButton', command=lambda: self.editor.flatten(self.channel.get()))
        self.flat_button.pack(side='right')
        self.more_button = ttk.Button(bar, text='+', style='Mini.TButton', width=2, command=lambda: self.shift(1))
        self.more_button.pack(side='right', padx=(0, 4))
        self.less_button = ttk.Button(bar, text='−', style='Mini.TButton', width=2, command=lambda: self.shift(-1))
        self.less_button.pack(side='right', padx=(0, 3))
        ttk.Label(bar, text='All sounds').pack(side='right', padx=(0, 6))
        self.strip = LineStrip(self, select=self.editor.select, paint=self.paint, key=lambda n: self.editor.key(n, self.channel.get()), graph=True)
        self.strip.pack(fill='x', pady=(6, 0))
        # the value of the selected effect, next to the text that describes it
        self.effect_row = ttk.Frame(self.strip.tools)
        self.spin = ttk.Spinbox(self.effect_row, textvariable=self.value, width=7, command=self.effect_edited)
        self.spin.pack(side='left', padx=(0, 4))
        self.spin.bind('<Return>', lambda e: self.effect_edited())
        self.spin.bind('<FocusOut>', lambda e: self.effect_edited())
        ttk.Button(self.effect_row, text='Remove', style='Mini.TButton', command=self.editor.delete).pack(side='left')
        self.hint = tk.StringVar()
        ttk.Label(self, textvariable=self.hint, foreground=MUTED, wraplength=480, justify='left').pack(fill='x', pady=(2, 0))
        top = ttk.Frame(self)
        top.pack(fill='x', pady=(6, 0))
        ttk.Label(top, text='Mood of the line').pack(side='left')
        self.mood_box = ttk.Combobox(top, state='readonly', width=11)
        self.mood_box.pack(side='left', padx=(6, 6))
        self.mood_box.bind('<<ComboboxSelected>>', self.mood_chosen)
        self.mood_edit = ttk.Button(top, text='Edit mood', style='Mini.TButton', command=self.edit_mood)
        self.mood_edit.pack(side='left')
        self.effect_button = ttk.Button(top, text='Add effect', style='Mini.TButton', command=self.pop_effects)
        self.effect_button.pack(side='right')
        self.effect_menu = tk.Menu(self.effect_button, tearoff=0)
        self.refresh()

    # ----- the catalog of the ROM

    def load(self, catalog):
        """Fills the mood list and the effect menu from the presets of the ROM."""
        self.catalog = catalog
        self.moods = [n[2:] for n in catalog.emotions]
        self.mood_box['values'] = [NONE] + [catalog.label(n) for n in catalog.emotions]
        self.effects = [n for n in catalog.commands if n[2:] not in HIDDEN_EFFECTS]
        self.effect_menu.delete(0, 'end')
        for name in self.effects:
            self.effect_menu.add_command(label=catalog.command_label(name), command=lambda n=name: self.add_effect(n))
        self.refresh()

    def unload(self):
        self.catalog, self.moods, self.effects = None, [], []
        self.mood_box['values'] = []
        self.effect_menu.delete(0, 'end')
        self.refresh()

    # ----- what the widgets do

    def paint(self, k, value, first):
        self.editor.paint(k, self.channel.get(), value, first)

    def shift(self, direction):
        key = self.channel.get()
        self.editor.shift_all(key, direction * CHANNEL[key].step)

    def mood_chosen(self, event=None):
        i = self.mood_box.current()
        self.editor.set_mood(None if i <= 0 else self.moods[i - 1])

    def edit_mood(self):
        mood = self.editor.mood()
        if mood:
            self.tab.edit_preset(f'<\\{mood}')

    def pop_effects(self):
        b = self.effect_button
        self.effect_menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def add_effect(self, name):
        self.editor.add_effect(name[2:], self.catalog.default_value(name))

    def effect_edited(self):
        text = self.value.get().strip()
        if self.editor.effect() is not None and re.fullmatch(r'[-+]?\d+', text):
            self.editor.set_effect(str(int(text)))

    def effect_range(self, name):
        """(low, high) a command may be given, from the property its preset sets."""
        found = self.catalog.placeholder(f'<\\{name}') if self.catalog is not None else None
        if found and found[0] in SCRIPT_KEYS:
            _, lo, hi, _ = SPEECH_PROPS[SCRIPT_KEYS[found[0]]]
            return (-hi, hi) if found[1] else (lo, hi)
        return -99999, 99999

    # ----- drawing

    def refresh(self):
        e, key = self.editor, self.channel.get()
        on = e.active
        hint = 'Choose a line in the list.' if not on else 'There is no sound to change in this line.'
        self.strip.show(e.columns(), e.sel, key, hint)
        mood = e.mood()
        if self.moods:
            self.mood_box.current(self.moods.index(mood) + 1 if mood in self.moods else 0)
        else:
            self.mood_box.set('')
        ready = on and self.catalog is not None
        self.mood_box.configure(state='readonly' if ready else 'disabled')
        self.mood_edit.state(['!disabled'] if ready and mood in self.moods else ['disabled'])
        self.effect_button.state(['!disabled'] if ready and self.effects else ['disabled'])
        for b in (self.flat_button, self.more_button, self.less_button):
            b.state(['!disabled'] if on else ['disabled'])
        c = CHANNEL[key]
        self.hint.set(e.error or f'{c.label}: {c.hint[0].lower()}{c.hint[1:]} {HINT}')
        it = e.effect()
        if it is None:
            self.effect_row.pack_forget()
        else:
            lo, hi = self.effect_range(it.name)
            self.spin.configure(from_=lo, to=hi)
            self.value.set(it.value)
            self.effect_row.pack()
