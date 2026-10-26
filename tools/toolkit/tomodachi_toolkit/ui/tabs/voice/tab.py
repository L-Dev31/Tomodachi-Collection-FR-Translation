"""Voice tab: the lines the Miis say (by bank), their pronunciation and rhythm, and the voice presets.

The right side has two frames. Listen is a test (a voice, a play button): nothing there is written to the ROM. Everything
in the other frame is: the text of the line (Sounds and Rhythm pages) and the presets of the voices (Voices page)."""
import tkinter as tk
from tkinter import messagebox, ttk

from ....features.speech.apply import speech_parts
from ....features.speech.catalog import PresetCatalog
from ....features.speech.engine import Speaker
from ....features.speech.line import LIMIT
from ....features.speech.lines import FAMILIES, LineEdits, speech_banks, tag_values
from ....features.speech.synth import Synthesizer
from ...theme import MUTED, font
from ..listing import ListingTab
from .editor import LineEditor
from .listen import ListenBar
from .rhythm import RhythmPage
from .settings import SettingsPage
from .sounds import SoundsPage

MARK = '● '
CHOOSE = 'Choose a line in the list.'


def bank_order(bank):
    """The conversations first (Talk, then the personalities), then the other banks."""
    name = bank.path.rsplit('/', 1)[-1]
    family = next((i for i, f in enumerate(FAMILIES) if name.startswith(f)), len(FAMILIES))
    return family, len(bank.name), bank.name


class VoiceTab(ListingTab):
    key = 'speech'
    title = 'Voice'
    heading = 'Voice'

    def build(self):
        self.speaker = self.catalog = self.synth = None
        self.banks, self.rows, self.edits = [], {}, LineEdits()
        self.loaded, self.shown, self.notice = False, 0, ''
        self.bank = self.line = None
        self.editor = LineEditor(changed=self.line_changed, moved=self.refresh)
        right = self.build_listing(weights=(2, 3), revert_all=self.revert_all, show='tree headings', columns=('say',))
        self.tree.heading('#0', text='Line (as the player sees it)')
        self.tree.heading('say', text='Said as')
        self.tree.column('#0', width=180)
        self.tree.column('say', width=120)
        self.tree.bind('<<TreeviewSelect>>', self.pick)
        self.listen = ListenBar(right, self)
        self.listen.pack(fill='x')
        frame = ttk.Labelframe(right, text='Written to the ROM', padding=8)
        frame.pack(fill='both', expand=True, pady=(8, 0))
        head = ttk.Frame(frame)
        head.pack(fill='x')
        self.title_var, self.detail_var = tk.StringVar(), tk.StringVar()
        text = ttk.Frame(head)
        text.pack(side='left', fill='x', expand=True)
        ttk.Label(text, textvariable=self.title_var, font=font(10, True), wraplength=330, justify='left').pack(anchor='w')
        ttk.Label(text, textvariable=self.detail_var, foreground=MUTED, wraplength=330, justify='left').pack(anchor='w')
        self.revert_button = ttk.Button(head, text='Revert line', style='Mini.TButton', command=self.editor.revert)
        self.revert_button.pack(side='right')
        self.undo_button = ttk.Button(head, text='Undo', style='Mini.TButton', command=self.editor.undo)
        self.undo_button.pack(side='right', padx=(0, 6))
        self.pages = ttk.Notebook(frame)
        self.pages.pack(fill='both', expand=True, pady=(8, 0))
        self.sounds = SoundsPage(self.pages, self.editor)
        self.rhythm = RhythmPage(self.pages, self)
        self.settings = SettingsPage(self.pages, self)
        for page, name in ((self.sounds, 'Sounds'), (self.rhythm, 'Rhythm'), (self.settings, 'Voices')):
            self.pages.add(page, text=f'  {name}  ')
        self.header()

    # ----- the ROM

    def on_rom(self):
        if self.synth is not None:
            self.synth.cancel()
        self.speaker = self.catalog = self.synth = None
        self.banks, self.rows, self.loaded, self.notice = [], {}, False, ''
        self.edits.clear()
        self.bank = self.line = None
        self.editor.close()
        self.editor.moods = ()
        self.tree.delete(*self.tree.get_children())
        self.count.set('')
        self.listen.unload()
        self.rhythm.unload()
        self.settings.unload()
        self.refresh()

    def on_show(self):
        self.load()

    def load(self):
        """Reads the lines of the ROM and its speech engine the first time the tab is needed."""
        if self.loaded or self.session is None:
            return
        self.loaded = True
        self.count.set('Reading the lines of the game...')
        self.update_idletasks()
        s = self.session
        try:
            self.banks = sorted(speech_banks(s.files, lambda p: s.subfiles(p)[0]), key=bank_order)
        except Exception as e:
            self.banks, self.notice = [], f'The lines of this ROM cannot be read: {e}'
        try:
            self.speaker, note = Speaker(s.arm9()), ''
        except Exception as e:
            self.speaker, note = None, f'The voice engine is not available: {e}'
        if self.speaker is None:
            self.listen.unload(note)
        else:
            sp = self.speaker
            self.synth = Synthesizer(sp)
            self.catalog = PresetCatalog(sp.presets, sp.voices, sp.emotions, tag_values(self.banks))
            self.editor.moods = tuple(n[2:] for n in sp.emotions)
            self.listen.load(self.catalog)
            self.rhythm.load(self.catalog)
            self.settings.load(self.catalog)
        self.fill()
        self.refresh()

    # ----- the list

    def group_text(self, bank):
        n = self.edits.count(bank.path)
        return f"{MARK if n else ''}{bank.name}   ({len(bank)})" + (f'   {n} changed' if n else '')

    def fill(self):
        tree, q, only = self.tree, self.query.get().strip().lower(), self.only.get()
        tree.delete(*tree.get_children())
        self.rows, shown = {}, 0
        for bank in self.banks:
            group = None
            for line in bank.lines:
                mod = self.edits.new_text(bank.path, line.index) is not None
                if (only and not mod) or (q and q != str(line.index) and q not in f'{line.label} {line.reading} {bank.name}'.lower()):
                    continue
                if group is None:
                    group = tree.insert('', 'end', iid='g:' + bank.path, text=self.group_text(bank), open=bool(q) or only)
                iid = f'{bank.path}#{line.index}'
                self.rows[iid] = (bank, line)
                tree.insert(group, 'end', iid=iid, text=(MARK if mod else '') + line.label, values=(line.reading if line.display else '',),
                            tags=('mod',) if mod else ())
                shown += 1
        self.shown = shown
        self.show_count()
        if self.line is not None:
            iid = f'{self.bank.path}#{self.line.index}'
            if tree.exists(iid):
                tree.selection_set(iid)
                tree.see(iid)
        self.changed()

    def show_count(self):
        total = sum(len(b) for b in self.banks)
        presets = len(self.catalog.edits) if self.catalog is not None else 0
        self.count.set(f'{self.shown} / {total}   ● {len(self.edits)} line(s), {presets} preset(s) changed' if total else '')

    def mark(self, bank, line):
        """Redraws the row of a line and the row of its bank after a change."""
        iid, mod = f'{bank.path}#{line.index}', self.edits.new_text(bank.path, line.index) is not None
        if self.tree.exists(iid):
            self.tree.item(iid, text=(MARK if mod else '') + line.label, tags=('mod',) if mod else ())
        if self.tree.exists('g:' + bank.path):
            self.tree.item('g:' + bank.path, text=self.group_text(bank))
        self.show_count()

    def pick(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        if sel[0] not in self.rows:                 # a bank: open or close it
            self.tree.item(sel[0], open=not self.tree.item(sel[0], 'open'))
            return
        bank, line = self.rows[sel[0]]
        if line is not self.line:
            self.open_line(bank, line)

    def open_line(self, bank, line):
        self.bank, self.line = bank, line
        self.editor.open(line.text, self.edits.new_text(bank.path, line.index))
        self.sounds.strip.rewind()
        self.rhythm.strip.rewind()
        self.listen.reset()
        self.refresh()

    # ----- what is shown for the line

    def header(self):
        e = self.editor
        if not e.active:
            self.title_var.set(self.notice or CHOOSE)
            self.detail_var.set('')
        else:
            line, m = self.line, e.model
            self.title_var.set(line.label if len(line.label) <= 80 else line.label[:79] + '…')
            detail = f'{self.bank.name}, message {line.index}      {m.length()} / {LIMIT} characters'
            if m.text() != line.text:
                detail += f'\nIn the ROM: {line.reading}'
            self.detail_var.set(detail)
        self.undo_button.state(['!disabled'] if e.active and e.model.history else ['disabled'])
        self.revert_button.state(['!disabled'] if e.active and e.model.edited else ['disabled'])

    def refresh(self):
        """Redraws everything that depends on the line and on the selected block."""
        self.sounds.refresh()
        self.rhythm.refresh()
        self.header()
        self.listen.set_state()

    def line_changed(self):
        """The text of the line changed: keep it as a change of the ROM, or forget it when it is the text of the ROM."""
        self.edits.set(self.bank.path, self.line.index, self.line.text, self.editor.model.text())
        self.mark(self.bank, self.line)
        self.refresh()
        self.changed()

    # ----- presets

    def edit_preset(self, name):
        """Shows the Voices page with the settings of a preset."""
        self.pages.select(self.settings)
        self.settings.choose(name)

    def preset_changed(self, name):
        """A preset was edited (name) or all were reset (None)."""
        self.listen.refresh_labels()
        self.show_count()
        self.changed()

    # ----- changes

    def revert_all(self):
        lines = len(self.edits)
        presets = len(self.catalog.edits) if self.catalog is not None else 0
        if not (lines or presets):
            return
        if not messagebox.askyesno('Revert', f'Put {lines} line(s) and {presets} voice preset(s) back as they are in the ROM?'):
            return
        self.edits.clear()
        if self.catalog is not None:
            self.catalog.reset_all()
        if self.line is not None:
            self.open_line(self.bank, self.line)
        self.fill()
        self.listen.refresh_labels()
        self.settings.show()

    def patch_config(self):
        presets = dict(self.catalog.edits) if self.catalog is not None else {}
        lines = self.edits.config()
        return {'presets': presets, 'lines': lines} if presets or lines else None

    def project_part(self):
        return self.patch_config() or {}

    def restore(self, part):
        presets, lines = speech_parts(part)
        if presets or lines:
            self.load()
        notes = []
        if self.catalog is not None:
            notes += self.catalog.restore(presets)
        elif presets:
            notes.append('Voice presets skipped: the voice engine is not available in this ROM.')
        if self.banks:
            notes += self.edits.restore(lines, self.banks)
        elif lines:
            notes.append('Speech lines skipped: the lines of this ROM could not be read.')
        if self.line is not None:
            self.open_line(self.bank, self.line)
        self.fill()
        self.listen.refresh_labels()
        self.settings.show()
        return notes

    def summary(self):
        parts = []
        if len(self.edits):
            parts.append(f'{len(self.edits)} line(s)')
        if self.catalog is not None and self.catalog.edits:
            parts.append(f'{len(self.catalog.edits)} preset(s)')
        return ', '.join(parts) + ' changed' if parts else 'Unchanged'
