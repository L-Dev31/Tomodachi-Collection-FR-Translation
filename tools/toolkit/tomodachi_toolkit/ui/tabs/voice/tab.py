"""Voice tab: the lines the Miis say, in a tree by bank (the message file that holds them), and the voices (the presets of the speech engine).

Left: the banks and their lines, then the voices. Right: the line or the voice that is selected. A right click on a row exports, imports or
reverts it. The lines are read from the message files as the Text tab will patch them."""
import os
from tkinter import filedialog, messagebox

from ....core.bmg import BmgFile
from ....features.speech.apply import speech_parts
from ....features.speech.catalog import PresetCatalog
from ....features.speech.engine import Speaker
from ....features.speech.files import export_files, file_name, import_files, read_file, write
from ....features.speech.lines import FAMILIES, Bank, LineEdits, code_counts, file_lines, is_speech_file, speech_banks, tag_values
from ....features.speech.synth import Synthesizer
from ..listing import ListingTab
from .editor import LineEditor
from .line import LinePanel
from .voices import VoicePanel

MARK = '● '


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
        self.banks, self.rows, self.sources, self.edits = [], {}, {}, LineEdits()      # sources: {path: the message file the lines were read from}
        self.loaded, self.notice, self.shown, self.voices = False, '', 0, 0
        self.bank = self.line = self.panel = None           # panel: the one of the two on the right that is shown
        self.editor = LineEditor(changed=self.line_changed, moved=self.refresh)
        right = self.build_listing(weights=(2, 3), batch=(self.export_all, self.import_all, self.revert_all), show='tree headings', columns=('say',))
        self.tree.heading('#0', text='Line (as the player sees it)')
        self.tree.heading('say', text='Said as')
        self.tree.column('#0', width=190)
        self.tree.column('say', width=130)
        self.tree.bind('<<TreeviewSelect>>', self.pick)
        self.tree.bind('<Button-1>', self.click, add='+')
        self.build_menu(self.entries)
        self.line_panel = LinePanel(right, self)
        self.voice_panel = VoicePanel(right, self)

    # ----- the ROM

    def on_rom(self):
        if self.synth is not None:
            self.synth.cancel()
        self.speaker = self.catalog = self.synth = None
        self.banks, self.rows, self.sources, self.loaded, self.notice = [], {}, {}, False, ''
        self.bank = self.line = None
        self.edits.clear()
        self.editor.close()
        self.editor.moods = ()
        self.line_panel.unload()
        self.voice_panel.unload()
        self.show_panel()
        self.fill()

    def on_show(self):
        if self.loaded:
            self.read_again()
        else:
            self.load()

    def on_hide(self):
        self.line_panel.stop()

    def message_file(self, path):
        """The message file as the Text tab will patch it."""
        return self.app.tab_of('bmg').message_file(path)

    def load(self):
        """Reads the lines of the ROM and its speech engine the first time the tab is needed."""
        if self.loaded or self.session is None:
            return
        self.loaded = True
        self.count.set('Reading the lines of the game...')
        self.update_idletasks()
        s = self.session
        try:
            self.banks = sorted(speech_banks(s.files, self.source), key=bank_order)
        except Exception as e:
            self.banks, self.notice = [], f'The lines of this ROM cannot be read: {e}'
        try:
            self.speaker = Speaker(s.arm9())
        except Exception as e:
            self.speaker, self.notice = None, self.notice or f'The voice engine is not available: {e}'
        if self.speaker is not None:
            sp = self.speaker
            self.synth = Synthesizer(sp)
            self.catalog = PresetCatalog(sp.presets, sp.voices, sp.emotions, tag_values(self.banks))
            self.editor.moods = tuple(n[2:] for n in sp.emotions)
            self.line_panel.load(self.catalog, code_counts(self.banks))
            self.voice_panel.load(self.catalog)
        self.fill()

    def source(self, path):
        self.sources[path] = self.message_file(path)
        return self.sources[path]

    def read_again(self):
        """The Text tab may have replaced a message file since the lines were read: the lines of that bank are read again, and the changes
        made to them are dropped (they were made to the lines of the other file)."""
        again = [b.path for b in self.banks if self.message_file(b.path) != self.sources.get(b.path)]
        for path in again:
            self.edits.drop(path)
            self.banks = [b for b in self.banks if b.path != path]
            try:
                lines = file_lines(path, BmgFile(self.source(path))) if is_speech_file(path) else []
            except Exception:
                lines = []
            if lines:
                self.banks.append(Bank(path, lines))
            if self.bank is not None and self.bank.path == path:
                self.bank = self.line = None
                self.editor.close()
                self.show_panel()
        if again:
            self.banks.sort(key=bank_order)
            self.fill()

    # ----- the tree

    def group_text(self, bank):
        n = self.edits.count(bank.path)
        return f"{MARK if n else ''}{bank.name}   ({len(bank)})" + (f'   {n} changed' if n else '')

    def voices_text(self):
        n = len(self.catalog.edits)
        return f"{MARK if n else ''}Voices ({self.voices})" + (f'   {n} changed' if n else '')

    def fill(self):
        tree, q, only = self.tree, self.query.get().strip().lower(), self.only.get()
        opened = {i for i in tree.get_children() if tree.item(i, 'open')}
        tree.delete(*tree.get_children())
        self.rows, self.shown = {}, 0
        for bank in self.banks:
            group = None
            for line in bank.lines:
                mod = self.edits.new_text(bank.path, line.index) is not None
                if (only and not mod) or (q and q != str(line.index) and q not in f'{line.label} {line.reading} {bank.name}'.lower()):
                    continue
                if group is None:
                    group = tree.insert('', 'end', iid='g:' + bank.path, text=self.group_text(bank), open=bool(q) or only or 'g:' + bank.path in opened)
                iid = f'{bank.path}#{line.index}'
                self.rows[iid] = (bank, line)
                tree.insert(group, 'end', iid=iid, text=(MARK if mod else '') + line.label, values=(line.reading if line.display else '',), tags=('mod',) if mod else ())
                self.shown += 1
        c = self.catalog
        names = [n for n in c.voices + c.emotions + c.commands if (not only or c.changed(n)) and (not q or q in self.voice_panel.label(n).lower() or q in 'voices')] if c else []
        self.voices = len(names)
        if names:
            tree.insert('', 'end', iid='v:', text=self.voices_text(), open=bool(q) or only or 'v:' in opened)
            for name in names:
                tree.insert('v:', 'end', iid='p:' + name, text=c.mark(name, self.voice_panel.label(name)), values=(self.voice_panel.kind(name),),
                            tags=('mod',) if c.changed(name) else ())
        self.show_count()
        shown = f'{self.line.path}#{self.line.index}' if self.line is not None else 'p:' + self.voice_panel.name if self.panel is self.voice_panel else None
        if shown and tree.exists(shown):
            tree.selection_set(shown)
            tree.see(shown)
        self.changed()

    def show_count(self):
        total = sum(len(b) for b in self.banks)
        presets = len(self.catalog.edits) if self.catalog is not None else 0
        self.count.set(self.notice or (f'{self.shown} / {total}   ● {len(self.edits)} line(s), {presets} voice(s) changed' if total else ''))

    def mark(self, bank, line):
        """Redraws the row of a line and the row of its bank after a change."""
        iid, mod = f'{bank.path}#{line.index}', self.edits.new_text(bank.path, line.index) is not None
        if self.tree.exists(iid):
            self.tree.item(iid, text=(MARK if mod else '') + line.label, tags=('mod',) if mod else ())
        if self.tree.exists('g:' + bank.path):
            self.tree.item('g:' + bank.path, text=self.group_text(bank))
        self.show_count()

    def show_panel(self, panel=None):
        self.panel = panel
        for p in (self.line_panel, self.voice_panel):
            if p is not panel:
                p.pack_forget()
        if panel is not None:
            panel.pack(fill='both', expand=True)

    def click(self, event):
        """A click on a bank (or on the voices) opens or closes it."""
        iid = self.tree.identify_row(event.y)
        if iid and iid not in self.rows and not iid.startswith('p:') and 'indicator' not in self.tree.identify_element(event.x, event.y):
            self.tree.item(iid, open=not self.tree.item(iid, 'open'))

    def pick(self, event=None):
        sel = self.tree.selection()
        if sel and sel[0] in self.rows:
            bank, line = self.rows[sel[0]]
            if line is not self.line:
                self.open_line(bank, line)
        elif sel and sel[0].startswith('p:'):
            self.bank = self.line = None
            self.editor.close()
            self.voice_panel.show(sel[0][2:])
            self.show_panel(self.voice_panel)
        self.sync_revert()

    def open_line(self, bank, line):
        self.bank, self.line = bank, line
        self.editor.open(line.text, self.edits.new_text(bank.path, line.index))
        self.line_panel.show()
        self.show_panel(self.line_panel)

    def refresh(self):
        """The selection (or a message) of the line changed."""
        if self.line is not None:
            self.line_panel.refresh()

    def line_changed(self):
        """The text of the line changed: keep it as a change of the ROM, or forget it when it is the text of the ROM."""
        self.edits.set(self.bank.path, self.line.index, self.line.text, self.editor.model.text())
        self.mark(self.bank, self.line)
        self.line_panel.refresh()
        self.changed()

    def preset_changed(self, name):
        """A voice, a mood or an effect was edited."""
        c, iid = self.catalog, 'p:' + name
        if self.tree.exists(iid):
            self.tree.item(iid, text=c.mark(name, self.voice_panel.label(name)), tags=('mod',) if c.changed(name) else ())
        if self.tree.exists('v:'):
            self.tree.item('v:', text=self.voices_text())
        self.line_panel.refresh_labels()
        self.show_count()
        self.changed()

    # ----- the right click

    def entries(self, iid):
        c = self.catalog
        if iid in self.rows:
            bank, line = self.rows[iid]
            edited = self.edits.new_text(bank.path, line.index) is not None
            return [('Play original', (lambda: self.line_panel.play(True)) if edited and self.synth else None),
                    ('Export WAV...', self.line_panel.export_wav if self.synth else None), None,
                    ('Export line...', self.export_line), ('Import line...', self.import_line),
                    ('Revert line', self.revert if edited else None)]
        if iid.startswith('p:'):
            return [('Revert voice', (lambda: self.revert_voices(iid[2:])) if c.changed(iid[2:]) else None)]
        if iid == 'v:':
            return [('Revert all voices', self.revert_voices if c.edits else None)]
        bank = next((b for b in self.banks if 'g:' + b.path == iid), None)
        return [('Export lines...', lambda: self.export_bank(bank)), ('Import lines...', lambda: self.import_bank(bank)),
                None, ('Revert lines', (lambda: self.revert_bank(bank)) if self.edits.count(bank.path) else None)] if bank else []

    def item_changed(self):
        if self.panel is self.line_panel:
            return self.line is not None and self.edits.new_text(self.bank.path, self.line.index) is not None
        return self.panel is self.voice_panel and self.catalog is not None and self.catalog.changed(self.voice_panel.name)

    def revert(self):
        """Takes back the changes of the line or of the voice on show."""
        if self.panel is self.line_panel:
            self.editor.revert()
        elif self.panel is self.voice_panel:
            self.revert_voices(self.voice_panel.name)

    # ----- lines

    def export_line(self):
        out = filedialog.asksaveasfilename(title='Export the line', defaultextension='.txt', initialfile=file_name(self.line), filetypes=[('Text file', '*.txt')])
        if out:
            try:
                write(out, self.editor.model.text())
            except OSError as e:
                messagebox.showerror('Export line', str(e))

    def import_line(self):
        name = filedialog.askopenfilename(title='Import the line', filetypes=[('Text file', '*.txt'), ('All files', '*')])
        if not name:
            return
        try:
            text = read_file(name, self.editor.model.text())
        except (OSError, ValueError) as e:
            messagebox.showerror('Import line', f'{os.path.basename(name)}: {e}')
            return
        if not self.editor.set_text(text):
            messagebox.showerror('Import line', self.editor.error)

    def export_bank(self, bank):
        """Every line of a bank (the playlist of a conversation) as a text file, in a folder that carries the name of the bank."""
        folder = filedialog.askdirectory(title=f'Folder to export the lines of {bank.name} to')
        if folder:
            try:
                count = export_files(folder, [bank], self.edits)
            except OSError as e:
                messagebox.showerror('Export lines', str(e))
                return
            messagebox.showinfo('Export lines', f'{count} line(s) exported to {os.path.join(folder, bank.name)}.')

    def import_bank(self, bank):
        folder = filedialog.askdirectory(title=f'Folder with the lines of {bank.name} (the folder that Export lines made)')
        if not folder:
            return
        if os.path.basename(folder.rstrip('/\\')).lower() == bank.name.lower():
            folder = os.path.dirname(folder.rstrip('/\\'))
        lines, _, problems = import_files(folder, [bank], self.edits)
        self.reload()
        messagebox.showinfo('Import lines', f'{lines} line(s) changed.' + ('\n\nSkipped:\n' + '\n'.join(problems[:12]) if problems else ''))

    def revert_bank(self, bank):
        self.edits.drop(bank.path)
        self.reload()

    def revert_voices(self, name=None):
        """One voice back as it is in the ROM, or all of them."""
        self.catalog.reset_all() if name is None else self.catalog.reset(name)
        self.reload()

    def reload(self):
        """Shows what the edits hold, after many changes at once (all reverted, a project, a folder of files)."""
        if self.line is not None:
            self.open_line(self.bank, self.line)
        self.fill()
        if self.catalog is not None:
            self.line_panel.refresh_labels()
            if self.panel is self.voice_panel:
                self.voice_panel.show(self.voice_panel.name)

    # ----- batch

    def revert_all(self):
        lines = len(self.edits)
        presets = len(self.catalog.edits) if self.catalog is not None else 0
        if not (lines or presets):
            return
        if not messagebox.askyesno('Revert', f'Put {lines} line(s) and {presets} voice(s) back as they are in the ROM?'):
            return
        self.edits.clear()
        if self.catalog is not None:
            self.catalog.reset_all()
        self.reload()

    def export_all(self):
        """Every line (as it is now) and every voice as a text file in a folder."""
        if not self.banks:
            return
        folder = filedialog.askdirectory(title='Folder to export the lines and the voices to')
        if not folder:
            return
        try:
            count = export_files(folder, self.banks, self.edits, self.catalog)
        except OSError as e:
            messagebox.showerror('Export voice', str(e))
            return
        messagebox.showinfo('Export voice', f'{count} file(s) exported to {folder}.')

    def import_all(self):
        """The text files of a folder that Batch export wrote (or that are named like them) replace the lines and the voices."""
        if not self.banks:
            return
        folder = filedialog.askdirectory(title='Folder with the lines and the voices (as Batch export writes them)')
        if not folder:
            return
        lines, presets, problems = import_files(folder, self.banks, self.edits, self.catalog)
        self.reload()
        messagebox.showinfo('Import voice', f'{lines} line(s) and {presets} voice(s) changed.'
                            + ('\n\nSkipped:\n' + '\n'.join(problems[:12]) if problems else ''))

    # ----- patch and project

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
        self.reload()
        return notes

    def summary(self):
        parts = []
        if len(self.edits):
            parts.append(f'{len(self.edits)} line(s)')
        if self.catalog is not None and self.catalog.edits:
            parts.append(f'{len(self.catalog.edits)} voice(s)')
        return ', '.join(parts) + ' changed' if parts else 'Unchanged'
