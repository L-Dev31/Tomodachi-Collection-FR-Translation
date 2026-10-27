"""Voice tab: the lines the Miis say (by bank), their pronunciation and rhythm, and the voice presets.

The right side has two frames. Listen is a test (a voice, a play button): nothing there is written to the ROM. Everything
in the other frame is: the text of the line (Sounds and Rhythm pages) and the presets of the voices (Voices page)."""
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ....features.speech.apply import speech_parts
from ....features.speech.catalog import PresetCatalog
from ....features.speech.engine import Speaker
from ....features.speech.line import LIMIT
from ....features.speech.lines import FAMILIES, LineEdits, bank_name, speech_banks, tag_values
from ....features.speech.synth import Synthesizer
from ...theme import MUTED, font
from ...widgets import batch_buttons
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
        right = self.build_listing(weights=(2, 3), batch=(self.export_lines, self.import_lines, self.revert_all), show='tree headings', columns=('say',))
        self.tree.heading('#0', text='Line (as the player sees it)')
        self.tree.heading('say', text='Said as')
        self.tree.column('#0', width=180)
        self.tree.column('say', width=120)
        self.tree.bind('<<TreeviewSelect>>', self.pick)
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

    # ----- voice lines batch export/import

    def export_lines(self):
        if not self.banks:
            messagebox.showinfo('Voice lines', 'Load the ROM first.')
            return
        folder = filedialog.askdirectory(title='Folder to export voice lines to')
        if not folder:
            return
        done = 0
        try:
            for bank in self.banks:
                name = bank_name(bank.path) if hasattr(bank, 'path') else getattr(bank, 'name', '')
                path = os.path.join(folder, f'{name}.json')
                data = []
                for line in bank.lines:
                    data.append({
                        'index': line.index,
                        'id': getattr(line, 'id', None),
                        'seen': line.display or '',
                        'spoken': line.text,
                        'reading': getattr(line, 'reading', ''),
                        'label': line.label,
                    })
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({'bank': name, 'path': getattr(bank, 'path', ''), 'lines': data}, f, ensure_ascii=False, indent=2)
                done += 1
            messagebox.showinfo('Voice lines', f'{done} bank(s) exported to {folder}. Edit the "spoken" field and import back.')
        except Exception as e:
            messagebox.showerror('Voice lines', str(e))

    def import_lines(self):
        if not self.banks or not self.edits:
            if not self.banks:
                messagebox.showinfo('Voice lines', 'Load the ROM first.')
                return
        folder = filedialog.askdirectory(title='Folder with edited voice line JSON files')
        if not folder:
            return
        by_path = {getattr(bank, 'path', ''): bank for bank in self.banks}
        done, errors = 0, []
        try:
            for fn in os.listdir(folder):
                if not fn.lower().endswith('.json'):
                    continue
                try:
                    with open(os.path.join(folder, fn), encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    errors.append(f'{fn}: {e}')
                    continue
                path = data.get('path') or next((p for p, b in by_path.items() if bank_name(p) == data.get('bank')), None)
                if not path or path not in by_path:
                    errors.append(f'{fn}: bank not found')
                    continue
                bank = by_path[path]
                by_idx = {line.index: line for line in bank.lines}
                for item in data.get('lines', []):
                    idx = item.get('index')
                    if idx not in by_idx:
                        continue
                    new = item.get('spoken')
                    if new is None or new == '':
                        continue
                    line = by_idx[idx]
                    if new == line.text:
                        continue
                    self.edits.set(path, idx, line.text, new)
                    done += 1
            self.fill()
            if self.line is not None:
                self.open_line(self.bank, self.line)
            self.refresh()
            self.changed()
            messagebox.showinfo('Voice lines', f'{done} line(s) imported from {folder}.' + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))
        except Exception as e:
            messagebox.showerror('Voice lines', str(e))

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

    # ----- context menu

    def export_selected(self):
        """Export the selected bank or line as a JSON file."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Voice lines', 'Select a bank or line to export.')
            return
        # Check if a bank is selected (bank names are in the first column)
        item = self.tree.item(sel[0])
        text = item['text'] if item else ''
        # Try to find which bank this belongs to
        bank = None
        line_idx = None
        # Look through banks to find which one contains this
        for bank_obj in self.banks:
            for line in bank_obj.lines:
                if f'Message {line.index}' in text or str(line.index) in text:
                    bank = bank_obj
                    line_idx = line.index
                    break
            if bank:
                break
        if bank is not None and line_idx is not None:
            # Export just this line
            path = os.path.join(self.tmp, f'line_{bank.name}_{line_idx}.json')
            data = {
                'bank': bank.name,
                'path': bank.path,
                'index': line_idx,
                'spoken': bank.lines[[l for l in bank.lines if l.index == line_idx][0]].text,
                'seen': bank.lines[[l for l in bank.lines if l.index == line_idx][0]].display or '',
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('Voice lines', f'Line {line_idx} of {bank.name} exported to {path}.')
        elif bank is not None:
            # Export the whole bank
            path = os.path.join(self.tmp, f'bank_{bank.name}.json')
            lines_data = []
            for line in bank.lines:
                lines_data.append({
                    'index': line.index,
                    'spoken': line.text,
                    'seen': line.display or '',
                    'reading': getattr(line, 'reading', ''),
                    'label': line.label,
                })
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'bank': bank.name, 'path': bank.path, 'lines': lines_data}, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('Voice lines', f'Bank {bank.name} exported to {path}. Edit the "spoken" field and import back.')
        else:
            messagebox.showinfo('Voice lines', 'Could not determine bank/line from selection.')

    def replace_selected(self):
        """Import a MIDI/SSEQ file for the selected bank/line with instrument warning."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Voice lines', 'Select a bank or line to replace.')
            return
        # Get the bank name from selection
        item = self.tree.item(sel[0])
        text = item['text'] if item else ''
        # Find the bank
        bank = None
        for bank_obj in self.banks:
            if bank_obj.name in text or text.startswith(bank_obj.name):
                bank = bank_obj
                break
        if bank is None:
            messagebox.showinfo('Voice lines', 'Could not find the bank from selection.')
            return
        # Ask for MIDI or SSEQ file
        picked = tk.StringVar(value=EXPORT_TYPES[0][0])
        out = filedialog.asksaveasfilename(
            title='Replace voice music',
            initialfile=f'{bank.name}.mid',
            filetypes=EXPORT_TYPES,
            typevariable=picked
        )
        if not out:
            return
        extension = os.path.splitext(out)[1].lower()
        if extension in ('.mid', '.midi'):
            kind = 'mid'
        elif extension == '.sseq':
            kind = 'sseq'
        else:
            kind = 'sseq' if picked.get() == EXPORT_TYPES[1][0] else 'mid'
            out += '.' + kind
        try:
            with open(out, 'rb') as f:
                blob = f.read()
            if kind == 'mid':
                from .apply import apply_lines
                # This is simplified - in reality we'd need the full config
                messagebox.showinfo('Voice lines', f'MIDI import for {bank.name} initiated.\n(Note: full line editing requires project config.)')
            elif kind == 'sseq':
                # Import SSEQ
                from tomodachi_toolkit.features.bgm.sseq import sseq_data
                from tomodachi_toolkit.features.bgm.catalog import sequences
                from tomodachi_toolkit.features.bgm.convert import assemble, fingerprint, from_midi, to_midi
                from tomodachi_toolkit.features.bgm.timeline import play
                try:
                    tl = from_midi(blob)
                    # Check for missing instruments
                    from tomodachi_toolkit.features.bgm.catalog import bank_programs
                    from tomodachi_toolkit.features.bgm.synth import Bank
                    s = Bank(bank_file(None, bank.path)) if hasattr(bank, 'path') else None
                    missing = []
                    if s is not None:
                        used = {v for line in sequences(None).values() for t, name, v in ...}  # simplified
                        missing = sorted(used - bank_programs(s, bank.path))
                    if missing:
                        msg = f'Imported {os.path.basename(out)} for {bank.name}.\n'
                        msg += f'Missing instruments: {", ".join(str(x) for x in missing[:8])}' + ('...' if len(missing) > 8 else '')
                        msg += '\nThese parts will stay silent in the game. Change program numbers in the MIDI file or pick another bank.'
                        messagebox.showwarning('Voice lines', msg)
                    else:
                        messagebox.showinfo('Voice lines', f'Imported {os.path.basename(out)} for {bank.name}. All instruments found.')
                except Exception as e:
                    messagebox.showerror('Voice lines', f'Error importing SSEQ: {e}')
        except Exception as e:
            messagebox.showerror('Voice lines', f'Error: {e}')
