"""The panel of a speech line: hear it, and change what it says and how it is said, in two views of the same line.

Visual: the sounds as blocks, the graph of their pitch, length or volume under them, and the palettes to click on (sounds and marks,
game codes, effects). Text: the line as the game holds it (katakana, marks, <\\Name=value> commands and {hex} game codes, nothing converted),
typed or pasted; it is the text of the line at once. Every change is kept at once."""
import re
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ....features.audio.wav import wav_write
from ....features.speech.about import EFFECTS, code_info, effect_style
from ....features.speech.engine import SPEECH_SAMPLE_RATE
from ....features.speech.line import CHANNEL, CHANNELS, LIMIT, item_text, problem, size
from ....features.speech.presets import SCRIPT_KEYS, SPEECH_PROPS
from ....features.speech.text import listening_text, speech_bytes
from ...theme import DARK, ERROR, MUTED, PANEL, SAND, font
from ...widgets import copy_text, popup
from .palette import WORD, Cell, Palette, sound_sections
from .strip import LineStrip

NONE = 'none'


def code_cell(code):
    """The cell of a game code in its palette: its icon and colour, its name, and what it stands for when the pointer is on it."""
    style = code_info(code)
    return Cell('{' + code + '}', style.label, colour=style.colour, icon=style.icon, hint=style.hint)


class LinePanel(ttk.Frame):
    def __init__(self, master, tab):
        super().__init__(master, padding=8)
        self.tab, self.editor, self.catalog = tab, tab.editor, None
        self.voice_i, self.job, self.pcm, self.shown = 0, None, None, None       # shown: the text that the box was given
        self.moods, self.effect_of = [], {}
        self.channel, self.value = tk.StringVar(value=CHANNELS[0].key), tk.StringVar()
        self.status, self.count = tk.StringVar(), tk.StringVar()
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        self.play_button = ttk.Button(bar, text='▶ Play', style='MiniAccent.TButton', command=self.play)
        self.play_button.pack(side='left')
        ttk.Label(bar, text='Voice').pack(side='left', padx=(10, 4))
        self.voice_box = ttk.Combobox(bar, state='readonly', width=12)
        self.voice_box.pack(side='left')
        self.voice_box.bind('<<ComboboxSelected>>', lambda e: setattr(self, 'voice_i', self.voice_box.current()))
        ttk.Label(bar, text='Emotion').pack(side='left', padx=(10, 4))
        self.mood_box = ttk.Combobox(bar, state='readonly', width=12)
        self.mood_box.pack(side='left')
        self.mood_box.bind('<<ComboboxSelected>>', self.mood_chosen)
        ttk.Label(bar, textvariable=self.status, foreground=DARK).pack(side='left', padx=10)
        ttk.Label(bar, textvariable=self.count, foreground=MUTED).pack(side='right')
        self.pages = ttk.Notebook(self, style='Sub.TNotebook')
        self.pages.pack(fill='both', expand=True, pady=(6, 0))
        visual, text = ttk.Frame(self.pages, padding=(0, 6)), ttk.Frame(self.pages, padding=(0, 6))
        self.pages.add(visual, text='  Visual  ')
        self.pages.add(text, text='  Text  ')
        # the visual view: blocks, the controls of the graph, the graph, then the palettes
        self.strip = LineStrip(visual, select=self.editor.select, paint=self.paint, key=lambda n: self.editor.key(n, self.channel.get()), menu=self.block_menu)
        self.strip.pack(fill='x')
        mid = self.strip.middle
        for c in CHANNELS:
            ttk.Radiobutton(mid, text=c.label, value=c.key, variable=self.channel, style='Toolbutton', command=self.refresh).pack(side='left', padx=(0, 3))
        self.less_button = ttk.Button(mid, text='−', style='Mini.TButton', width=2, command=lambda: self.shift(-1))
        self.less_button.pack(side='left', padx=(8, 3))
        self.more_button = ttk.Button(mid, text='+', style='Mini.TButton', width=2, command=lambda: self.shift(1))
        self.more_button.pack(side='left')
        self.flat_button = ttk.Button(mid, text='Flatten', style='Mini.TButton', command=lambda: self.editor.flatten(self.channel.get()))
        self.flat_button.pack(side='left', padx=(3, 0))
        self.effect_row = ttk.Frame(mid)
        self.spin = ttk.Spinbox(self.effect_row, textvariable=self.value, width=7, command=self.effect_edited)
        self.spin.pack(side='left')
        self.spin.bind('<Return>', lambda e: self.effect_edited())
        self.spin.bind('<FocusOut>', lambda e: self.effect_edited())
        ttk.Label(self.effect_row, text='Effect value').pack(side='left', padx=(0, 6))
        self.palettes = ttk.Notebook(visual, style='Sub.TNotebook')
        self.palettes.pack(fill='x', pady=(8, 0))
        self.sounds = Palette(self.palettes, self.editor.put, self.palette_menu)
        self.codes = Palette(self.palettes, self.editor.put, self.palette_menu)
        self.effects = Palette(self.palettes, self.add_effect, lambda text: [])
        for page, name in ((self.sounds, 'Sounds'), (self.codes, 'Game codes'), (self.effects, 'Effects')):
            self.palettes.add(page, text=f'  {name}  ')
        self.sounds.set(sound_sections())
        # the text view
        body = ttk.Frame(text)
        body.pack(fill='both', expand=True)
        self.box = tk.Text(body, height=8, width=40, wrap='char', undo=True, font=font(11), bg=PANEL, fg=DARK, insertbackground=DARK,
                           relief='flat', highlightthickness=1, highlightbackground=SAND, padx=6, pady=4)
        scroll = ttk.Scrollbar(body, orient='vertical', command=self.box.yview)
        self.box.configure(yscrollcommand=scroll.set)
        self.box.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.box.bind('<<Modified>>', self.typed)
        self.note = ttk.Label(text, foreground=ERROR, wraplength=520, justify='left')
        self.note.pack(fill='x', pady=(6, 0))

    # ----- the catalog of the ROM

    def load(self, catalog, codes):
        """Fills the voice and emotion lists and the palettes of game codes and effects. codes: [(game code, lines that use it)]."""
        self.catalog, self.voice_i = catalog, 0
        self.moods = [n[2:] for n in catalog.emotions]
        self.mood_box['values'] = [NONE] + [catalog.label(n) for n in catalog.emotions]
        ordered = sorted((code for code, n in codes), key=lambda code: code_info(code).rank)
        self.codes.set([('Game codes', WORD, [code_cell(code) for code in ordered])])
        self.effect_of = {}
        have, cells = {name[2:]: name for name in catalog.commands}, []
        for effect in EFFECTS:
            if effect.tag in have:
                text = catalog.tag(have[effect.tag], catalog.default_value(have[effect.tag]))
                self.effect_of[text] = (effect.tag, catalog.default_value(have[effect.tag]))
                style = effect_style(effect.tag)
                cells.append(Cell(text, style.label, colour=style.colour, icon=style.icon, hint=style.hint))
        self.effects.set([('Effects', WORD, cells)])
        self.refresh_labels()
        self.set_state()

    def unload(self):
        self.stop()
        self.catalog, self.job, self.pcm = None, None, None
        self.moods, self.effect_of = [], {}
        self.voice_box['values'] = self.mood_box['values'] = []
        self.codes.set([])
        self.effects.set([])
        self.set_state()

    def refresh_labels(self):
        """The voice names, with a dot in front of the ones whose settings were changed."""
        c = self.catalog
        if c is not None:
            self.voice_box['values'] = [c.mark(n, c.voice_label(n)) for n in c.voices]
            self.voice_box.current(self.voice_i)

    def voice_name(self):
        return self.catalog.voices[self.voice_i]

    # ----- what is on show

    def show(self):
        """A line was opened: the box and the blocks show it, the sound of the last one is forgotten."""
        self.stop()
        self.pcm = None
        self.status.set('')
        self.strip.rewind()
        self.fill_box()
        self.refresh()

    def typed_text(self):
        return self.box.get('1.0', 'end-1c')

    def fill_box(self):
        e = self.editor
        self.box.delete('1.0', 'end')
        self.shown = e.model.text() if e.active else ''
        self.box.insert('1.0', self.shown)
        self.box.edit_reset()
        self.box.edit_modified(False)

    def refresh(self):
        """Redraws what depends on the line and on the selected block."""
        e, key = self.editor, self.channel.get()
        self.strip.show(e.columns(), e.sel, key)
        text = e.model.text() if e.active else ''
        if text != self.shown:                           # the line changed: if the text was typed here the box is right, else it follows
            if self.typed_text() == text:
                self.shown = text
            else:
                self.fill_box()
        self.update_note()
        mood = e.mood()
        if self.moods:
            self.mood_box.current(self.moods.index(mood) + 1 if mood in self.moods else 0)
        it = e.effect()
        if it is None:
            self.effect_row.pack_forget()
        else:
            lo, hi = self.effect_range(it.name)
            self.spin.configure(from_=lo, to=hi)
            self.value.set(it.value)
            self.effect_row.pack(side='right')
        self.set_state()

    def update_note(self):
        """The size of the text, and why the game cannot hold it when it cannot."""
        text = self.typed_text()
        try:
            self.count.set(f'{size(text)} / {LIMIT}')
        except ValueError:
            self.count.set('')
        self.note.configure(text=self.editor.error or problem(text) or '')

    def typed(self, event=None):
        """The text was typed or pasted: it is the text of the line at once, when the game can hold it."""
        if self.box.edit_modified():
            self.box.edit_modified(False)
            text = self.typed_text()
            if self.editor.active and text != self.editor.model.text():
                self.editor.set_text(text)
            self.update_note()

    # ----- the blocks

    def paint(self, k, value, first):
        self.editor.paint(k, self.channel.get(), value, first)

    def shift(self, direction):
        key = self.channel.get()
        self.editor.shift_all(key, direction * CHANNEL[key].step)

    def mood_chosen(self, event=None):
        i = self.mood_box.current()
        self.editor.set_mood(None if i <= 0 else self.moods[i - 1])

    def add_effect(self, text):
        self.editor.add_effect(*self.effect_of[text])

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

    def block_menu(self, k, event):
        it = self.editor.columns()[k].item
        popup(self.strip.blocks, event, [('Copy', lambda: copy_text(self, item_text(it))), ('Delete', self.editor.delete)])

    def palette_menu(self, text):
        if self.editor.sel is None:
            return []
        return [('Insert before the block', lambda: self.editor.put(text, 'before')), ('Replace the block', lambda: self.editor.put(text, 'replace'))]

    # ----- sound

    def set_state(self):
        synth = self.tab.synth
        busy = synth is not None and synth.busy
        on = self.catalog is not None
        self.play_button.configure(text='■ Stop' if busy else '▶ Play')
        self.play_button.state(['!disabled'] if on else ['disabled'])
        for box in (self.voice_box, self.mood_box):
            box.configure(state='readonly' if on else 'disabled')

    def play(self, original=False):
        """Plays the line as it is now ("original": as it is in the ROM) with the voice chosen here. While a sound is being made the
        button stops it."""
        synth = self.tab.synth
        if synth is not None and synth.busy:
            self.stop()
        else:
            self.make(self.listen, original)

    def make(self, then, original=False):
        """Makes the sound of the line and gives it to then(pcm)."""
        synth, model = self.tab.synth, self.editor.model
        if synth is None or synth.busy or model is None:
            return
        try:
            data = speech_bytes(listening_text(model.original if original else model.text()))
        except ValueError as e:
            messagebox.showerror('Voice', str(e))
            return
        if not data.strip():
            self.status.set('Nothing to say')
            return
        voice, edits = self.voice_name(), dict(self.catalog.edits)
        pcm = synth.cached(synth.key(data, voice, None, edits))
        if pcm is not None:
            then(pcm)
            return
        self.job = synth.start(data, voice, None, edits)
        self.set_state()
        self.after(150, self.poll, self.job, then)

    def poll(self, job, then):
        if job is not self.job:
            return
        if job.result is None:
            self.status.set(f'{self.tab.synth.seconds:.1f} s')
            self.after(150, self.poll, job, then)
            return
        self.job = None
        kind, value = job.result
        self.status.set('')
        if kind == 'ok':
            then(value)
        elif kind == 'error':
            messagebox.showerror('Voice', f'The speech engine failed: {value}')
        self.set_state()

    def listen(self, pcm):
        self.pcm = pcm
        n = len(pcm) // 2
        self.status.set(f'{n / SPEECH_SAMPLE_RATE:.2f} s')
        error = self.tab.app.player.play(SPEECH_SAMPLE_RATE, struct.unpack('<%dh' % n, pcm))
        if error:
            messagebox.showerror('Play', error)
        self.set_state()

    def stop(self):
        if self.tab.synth is not None:
            self.tab.synth.cancel()
        self.tab.app.player.stop()

    def export_wav(self):
        self.make(self.save_wav)

    def save_wav(self, pcm):
        out = filedialog.asksaveasfilename(defaultextension='.wav', initialfile='speech.wav', filetypes=[('WAV audio', '*.wav')])
        if out:
            try:
                with open(out, 'wb') as f:
                    f.write(wav_write(SPEECH_SAMPLE_RATE, struct.unpack('<%dh' % (len(pcm) // 2), pcm)))
            except OSError as e:
                messagebox.showerror('Export WAV', str(e))
        self.set_state()
