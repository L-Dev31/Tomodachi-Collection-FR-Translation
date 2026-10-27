"""BGM tab: the music of the game (the sequences of the sound archive) to hear, and to take out or put back as MIDI or SSEQ files."""
import collections
import os
import re
import struct
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...features.bgm.catalog import bank_file, bank_names, bank_programs, sequence_file, sequences
from ...features.bgm.convert import assemble, fingerprint, from_midi, to_midi
from ...features.bgm.sseq import SseqError, sseq_data, sseq_file
from ...features.bgm.synth import RATE, Bank, Synth, SynthError
from ...features.bgm.timeline import play
from ..theme import BROWN, CANVAS, DARK, MUTED, SAND
from .listing import ListingTab

TRACK_COLORS = ('#F7822B', '#4F86D9', '#3FA36B', '#C4488E', '#8E6BD8', '#D9A400', '#2FA3B8', '#B3573A', '#6C7A89', '#7A9E2E', '#D96A14',
                '#4A6FA5', '#9C4B6E', '#5C9E8F', '#B58A2E', '#7B5CB8')
MIDI_TYPES = [('MIDI or SSEQ music', '*.mid *.midi *.sseq'), ('MIDI file', '*.mid *.midi'), ('SSEQ sequence', '*.sseq')]
EXPORT_TYPES = [('MIDI file', '*.mid'), ('SSEQ sequence (the format of the game)', '*.sseq')]
FILE_NAME = re.compile(r'^bgm_(\d+)_.*\.(mid|midi|sseq)$', re.I)
HEARD = 4                       # sounds kept to be played again without working them out (a few megabytes each)
TAIL = 0.5                      # seconds the sound goes on after the music (the notes that ring on)


def clock(seconds):
    return '%d:%02d' % divmod(int(seconds + 0.5), 60)


def stem(info):
    """The start of the names of the files of a sequence: its number, then its name, so the files sort like the list."""
    return 'bgm_%03d_%s' % (info.index, info.name)


class Rendering:
    """A sound being worked out in the background: the thread writes here, the window reads it (the thread never touches the window)."""

    def __init__(self):
        self.stop = threading.Event()
        self.progress, self.pcm, self.error, self.done = 0.0, None, '', False

    def work(self, synth, timeline, bank, volume):
        try:
            self.pcm = synth.render(timeline, bank, volume, progress=self.advance, stop=self.stop.is_set)
        except Exception as e:                  # whatever goes wrong must reach the window, not die in the thread
            self.error = str(e) or type(e).__name__
        self.done = True

    def advance(self, fraction):
        self.progress = fraction


class BgmTab(ListingTab):
    key = 'bgm'
    title = 'BGM'
    heading = 'BGM'

    def build(self):
        self.snd, self.infos, self.new, self.sel = None, {}, {}, None
        self.memo = {}                        # sequence number -> (file, Timeline)
        self.loading = False
        self.synth = None                     # works out the sound of a sequence (made when it is first needed)
        self.heard = collections.OrderedDict()          # (file, bank, volume) -> the sound, the latest ones
        self.job, self.playing, self.timer = None, None, None      # the sound being prepared; (token, start, seconds, Timeline) while it plays
        right = self.build_listing(
            weights=(2, 3), batch=(self.export_all, self.replace_folder, self.revert_all),
            show='tree headings', columns=('time', 'tracks', 'size'))
        self.tree.heading('#0', text='Sequence')
        self.tree.heading('time', text='Length')
        self.tree.heading('tracks', text='Tracks')
        self.tree.heading('size', text='Bytes')
        self.tree.column('#0', width=210)
        self.tree.column('time', width=55, anchor='e')
        self.tree.column('tracks', width=50, anchor='e')
        self.tree.column('size', width=60, anchor='e')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.title_text, self.info_text, self.note_text = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(right, textvariable=self.title_text, foreground=DARK, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(right, textvariable=self.info_text, foreground=BROWN, wraplength=460, justify='left').pack(anchor='w', pady=(2, 8))
        row = ttk.Frame(right)
        row.pack(fill='x')
        self.play_button = ttk.Button(row, text='Play', style='Soft.TButton', width=6, command=self.listen)
        self.buttons = [self.play_button] + [ttk.Button(row, text=t, style=s, command=c) for t, s, c in (
            ('Replace with MIDI or SSEQ...', 'Accent.TButton', self.replace), ('Export...', 'Soft.TButton', self.export),
            ('Revert', 'Soft.TButton', self.revert))]
        for b in self.buttons:
            b.pack(side='left', padx=(0, 6))
        self.play_text = tk.StringVar()
        ttk.Label(right, textvariable=self.play_text, foreground=MUTED).pack(anchor='w', pady=(6, 0))
        settings = ttk.Frame(right)
        settings.pack(fill='x', pady=(4, 0))
        ttk.Label(settings, text='Instruments (bank)').pack(side='left')
        self.bank = ttk.Combobox(settings, state='readonly', width=30)
        self.bank.pack(side='left', padx=(6, 14))
        self.bank.bind('<<ComboboxSelected>>', self.bank_chosen)
        ttk.Label(settings, text='Volume').pack(side='left')
        self.volume = tk.StringVar()
        self.volume_box = ttk.Spinbox(settings, from_=0, to=127, width=5, textvariable=self.volume, command=self.volume_chosen)
        self.volume_box.pack(side='left', padx=6)
        self.volume_box.bind('<Return>', self.volume_chosen)
        self.volume_box.bind('<FocusOut>', self.volume_chosen)
        self.roll = tk.Canvas(right, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=170, width=460)
        self.roll.pack(fill='both', expand=True, pady=(10, 0))
        self.roll.bind('<Configure>', lambda e: self.draw())
        ttk.Label(right, textvariable=self.note_text, foreground=MUTED, wraplength=460, justify='left').pack(anchor='w', pady=(6, 0))
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.hush()
        self.sel = None
        self.roll.delete('all')
        self.title_text.set('')
        self.info_text.set('Select a sequence in the list.' if self.snd else '')
        self.note_text.set('')
        self.set_state()

    def set_state(self):
        on = self.sel is not None
        for b in self.buttons:
            b.state(['!disabled'] if on else ['disabled'])
        for w in (self.bank, self.volume_box):
            w.state(['!disabled'] if on else ['disabled'])
        if not on:
            self.volume.set('')
            self.bank.set('')

    def on_rom(self):
        self.snd, self.infos, self.new, self.memo = None, {}, {}, {}
        self.synth = None
        self.heard.clear()
        self.tree.delete(*self.tree.get_children())
        self.count.set('')
        self.reset_view()

    def on_hide(self):
        self.hush()

    def on_show(self):
        if self.snd is None:
            try:
                snd = self.session.sound()
                infos = {s.index: s for s in sequences(snd)}
            except Exception as e:
                self.info_text.set(f'Cannot read the music of the game: {e}')
                return
            self.snd, self.infos = snd, infos
            self.banks = bank_names(snd)
            self.bank['values'] = [f'{n}  {name.replace("BANK_", "")}' for n, name in self.banks]
            self.reset_view()
            self.fill()

    def file(self, i):
        """The SSEQ file of a sequence as it will be patched."""
        edit = self.new.get(i)
        return edit['file'] if edit and edit.get('file') else self.original(i)

    def original(self, i):
        return sequence_file(self.snd, self.infos[i])

    def timeline(self, i):
        """The Timeline of a sequence as it will be patched (remembered while its file stays the same)."""
        f = self.file(i)
        if i not in self.memo or self.memo[i][0] is not f:
            self.memo[i] = (f, play(sseq_data(f)))
        return self.memo[i][1]

    def setting(self, i, key):
        """The bank or the volume of a sequence as it will be patched."""
        edit = self.new.get(i)
        return edit[key] if edit and edit.get(key) is not None else getattr(self.infos[i], key)

    def group_of(self, name, counts):
        word = name.replace('SEQ_', '', 1).split('_')[0]
        return word if counts[word] > 1 else 'OTHER'

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        if self.snd is None:
            self.count.set('')
            return
        q = self.query.get().strip().lower()
        counts = collections.Counter(s.name.replace('SEQ_', '', 1).split('_')[0] for s in self.infos.values())
        groups, shown = {}, 0
        for i, s in sorted(self.infos.items()):
            if self.only.get() and i not in self.new:
                continue
            text = f'{s.name}  {self.bank_label(self.setting(i, "bank"))}'
            if q and q not in text.lower() and q != str(i):
                continue
            g = self.group_of(s.name, counts).title()
            if g not in groups:
                groups[g] = self.tree.insert('', 'end', iid='g:' + g, text=g, open=bool(q) or self.only.get())
            mod = i in self.new
            try:
                tl = self.timeline(i)
                values = (clock(tl.seconds(tl.length)), len(tl.lines), len(self.file(i)))
            except SseqError:
                values = ('?', '?', len(self.file(i)))
            self.tree.insert(groups[g], 'end', iid=str(i), text=('● ' if mod else '') + s.name.replace('SEQ_', '', 1), values=values,
                             tags=('mod',) if mod else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.infos)}   ● {len(self.new)} changed')
        if self.sel is not None and self.tree.exists(str(self.sel)):
            self.tree.selection_set(str(self.sel))
            self.tree.see(str(self.sel))
        self.changed()

    def bank_label(self, bank):
        for n, name in self.banks:
            if n == bank:
                return name.replace('BANK_', '')
        return str(bank)

    def select(self, event=None):
        sel = self.tree.selection()
        if not sel or not sel[0].isdigit():
            return
        i = int(sel[0])
        if i == self.sel and event is not None:
            return
        self.hush()
        self.sel = i
        self.note_text.set('')
        self.set_state()
        self.describe()
        self.draw()

    def describe(self):
        i = self.sel
        if i is None or self.snd is None:
            return
        s = self.infos[i]
        self.title_text.set(s.name + ('   (changed)' if i in self.new else ''))
        try:
            tl = self.timeline(i)
            notes = tl.note_count()
            loop = f'loops from {clock(tl.seconds(tl.loop[0]))} to {clock(tl.seconds(tl.loop[1]))}' if tl.loop else 'plays once'
            tempo = sorted({b for t, b in tl.tempos})
            speed = f'{tempo[0]} BPM' if len(tempo) == 1 else (f'{tempo[0]} to {tempo[-1]} BPM' if tempo else '120 BPM')
            line = f'{len(tl.lines)} track(s), {notes:,} notes, {clock(tl.seconds(tl.length))}, {speed}, {loop}.'
        except SseqError as e:
            line = f'Cannot read this sequence: {e}'
        size = len(self.file(i))
        original = s.size
        more = f' (the game has {original:,})' if size != original else ''
        self.info_text.set(f'Number {i}, {s.player}.  {line}\nFile of {size:,} bytes{more}.')
        self.loading = True
        banks = [n for n, name in self.banks]
        bank = self.setting(i, 'bank')
        if bank in banks:
            self.bank.current(banks.index(bank))
        else:
            self.bank.set(str(bank))
        self.volume.set(str(self.setting(i, 'volume')))
        self.loading = False

    def draw(self):
        """A small piano roll of the sequence: a row of notes per pitch, every track in its own colour, the loop shaded."""
        i = self.sel
        c = self.roll
        c.delete('all')
        if i is None or self.snd is None:
            return
        try:
            tl = self.timeline(i)
        except SseqError:
            return
        width, height = self.roll_size()
        notes = [(n, t, k, length) for n, line in tl.lines.items() for t, k, v, length in line.notes]
        if not notes:
            return
        lo, hi = min(k for n, t, k, length in notes) - 1, max(k for n, t, k, length in notes) + 1
        total = max(tl.length, 1)
        if tl.loop:
            c.create_rectangle(tl.loop[0] * width / total, 0, tl.loop[1] * width / total, height, fill='#F9EBD0', outline='')
        step = (height - 6) / (hi - lo + 1)
        thick = max(1.0, min(4.0, step))
        for n, t, k, length in notes:
            x = t * width / total
            y = height - 3 - (k - lo) * step
            c.create_rectangle(x, y - thick, max(x + 1, (t + max(length, 1)) * width / total), y, fill=TRACK_COLORS[n % 16], outline='')
        if self.playing is not None:
            self.move_head(tl.ticks_at(time.monotonic() - self.playing[1]))

    def roll_size(self):
        return max(self.roll.winfo_width(), 200), max(self.roll.winfo_height(), 120)

    def move_head(self, tick):
        """Puts the line that shows where the music is on the piano roll at a tick (or takes it away when tick is None)."""
        self.roll.delete('head')
        if tick is None or self.sel is None:
            return
        try:
            total = max(self.timeline(self.sel).length, 1)
        except SseqError:
            return
        width, height = self.roll_size()
        x = min(width - 2, max(1.0, tick * width / total))
        self.roll.create_line(x, 0, x, height, fill=DARK, width=2, tags='head')

    # ----- hearing the music

    def listen(self):
        """The Play button: plays the sequence as it will be in the game, or stops it while it is being prepared or played."""
        if self.job is not None or self.playing is not None:
            self.hush()
            return
        i = self.sel
        if i is None or self.snd is None:
            return
        try:
            tl = self.timeline(i)
            if not tl.note_count():
                self.play_text.set('This sequence has no notes.')
                return
            bank, volume = self.setting(i, 'bank'), self.setting(i, 'volume')
            key = (self.file(i), bank, volume)
            pcm = self.heard.get(key)
            instruments = None if pcm is not None else Bank(bank_file(self.snd, bank))
        except (SseqError, SynthError) as e:
            self.play_text.set(f'Cannot play this: {e}')
            return
        except (IndexError, TypeError, struct.error):
            self.play_text.set('Cannot play this: the instruments of this bank cannot be read.')
            return
        if pcm is not None:
            self.heard.move_to_end(key)
            self.begin(pcm, tl)
            return
        if self.synth is None:
            self.synth = Synth(self.snd.swar)
        job = self.job = Rendering()
        threading.Thread(target=job.work, args=(self.synth, tl, instruments, volume), daemon=True).start()
        self.play_button.config(text='Stop')
        self.play_text.set('Preparing the sound... 0%')
        self.timer = self.after(100, self.poll, job, key, tl)

    def poll(self, job, key, tl):
        """Looks at the sound being prepared: shows how far it is, plays it when it is ready."""
        if job is not self.job:
            return
        self.timer = None
        if not job.done:
            self.play_text.set('Preparing the sound... %d%%' % int(job.progress * 100))
            self.timer = self.after(100, self.poll, job, key, tl)
            return
        self.job = None
        if job.error or job.pcm is None:
            self.hush()
            if job.error:
                self.play_text.set(f'Cannot play this: {job.error}')
            return
        self.heard[key] = job.pcm
        while len(self.heard) > HEARD:
            self.heard.popitem(last=False)
        self.begin(job.pcm, tl)

    def begin(self, pcm, tl):
        """Plays a sound that is ready and follows it with the line on the piano roll."""
        if not any(pcm):
            self.hush()
            self.play_text.set('Nothing to hear: the bank has none of the instruments this music asks for.')
            return
        error = self.app.player.play(RATE, pcm)
        if error:
            self.hush()
            messagebox.showerror('Play', error)
            return
        token = object()
        self.playing = (token, time.monotonic(), len(pcm) / RATE, tl)
        self.play_button.config(text='Stop')
        self.tick(token)

    def tick(self, token):
        if self.playing is None or self.playing[0] is not token:
            return
        _, began, seconds, tl = self.playing
        elapsed = time.monotonic() - began
        if elapsed >= seconds + 0.3:
            self.hush()
            return
        music = max(seconds - TAIL, 0.0)
        self.play_text.set(f'Playing {clock(min(elapsed, music))} / {clock(music)}')
        self.move_head(tl.ticks_at(elapsed))
        self.timer = self.after(200, self.tick, token)

    def hush(self):
        """Stops the sound that is being prepared or played, and shows the tab at rest."""
        if self.job is not None:
            self.job.stop.set()
            self.job = None
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.playing is not None:
            self.playing = None
            self.app.player.stop()
        self.play_button.config(text='Play')
        self.play_text.set('')
        self.roll.delete('head')

    # ----- changes

    def edit_of(self, i):
        return self.new.get(i) or {'file': None, 'bank': None, 'volume': None}

    def store(self, i, edit):
        """Keeps the edit of a sequence, or forgets it when it changes nothing."""
        self.hush()
        if edit['file'] is None and edit['bank'] is None and edit['volume'] is None:
            self.new.pop(i, None)
        else:
            self.new[i] = edit

    def bank_chosen(self, event=None):
        i = self.sel
        if i is None or self.loading or self.bank.current() < 0:
            return
        bank = self.banks[self.bank.current()][0]
        edit = self.edit_of(i)
        edit['bank'] = None if bank == self.infos[i].bank else bank
        self.store(i, edit)
        self.fill()
        self.describe()
        self.warn_programs(i)

    def volume_chosen(self, event=None):
        i = self.sel
        if i is None or self.loading:
            return
        try:
            v = int(self.volume.get())
        except ValueError:
            v = self.setting(i, 'volume')
        v = max(0, min(127, v))
        edit = self.edit_of(i)
        value = None if v == self.infos[i].volume else v
        self.volume.set(str(v))
        if value != edit['volume']:
            edit['volume'] = value
            self.store(i, edit)
            self.fill()
            self.describe()

    def warn_programs(self, i):
        """Says when the music asks for instruments the bank does not have (they stay silent in the game)."""
        tl = self.timeline(i)
        used = {v for line in tl.lines.values() for t, name, v in line.events if name == 'prog'}
        missing = sorted(used - bank_programs(self.snd, self.setting(i, 'bank')))
        self.note_text.set(('The bank has no instrument number ' + ', '.join(map(str, missing)) + ': those parts stay silent in the game. '
                            'Change the program numbers in the MIDI file, or pick another bank.') if missing else '')
        return missing

    def import_blob(self, i, blob):
        """Takes a MIDI or SSEQ file as the music of sequence i. Raises ValueError when the file is no good."""
        blob = bytes(blob)
        if blob[:4] == b'MThd':
            tl = from_midi(blob)
            if not tl.note_count():
                raise ValueError('This MIDI file has no notes.')
            file = sseq_file(assemble(tl))
        elif blob[:4] == b'SSEQ':
            sseq_data(blob)
            file = blob
        else:
            raise ValueError('This is neither a MIDI file nor an SSEQ file.')
        play(sseq_data(file))
        edit = self.edit_of(i)
        edit['file'] = None if file == self.original(i) else file
        self.store(i, edit)

    def replace(self):
        i = self.sel
        if i is None:
            return
        path = filedialog.askopenfilename(filetypes=MIDI_TYPES)
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                self.import_blob(i, f.read())
        except (OSError, ValueError) as e:
            messagebox.showerror('Replace music', str(e))
            return
        self.fill()
        self.describe()
        self.draw()
        missing = self.warn_programs(i)
        if not missing:
            self.note_text.set(f'Imported {os.path.basename(path)}.')

    def export(self):
        """Saves the music of the sequence as a MIDI file or as an SSEQ file: the name or the type chosen in the dialog says which."""
        i = self.sel
        if i is None:
            return
        picked = tk.StringVar(value=EXPORT_TYPES[0][0])
        out = filedialog.asksaveasfilename(title='Export music', initialfile=stem(self.infos[i]) + '.mid', filetypes=EXPORT_TYPES,
                                           typevariable=picked)
        if not out:
            return
        extension = os.path.splitext(out)[1].lower()
        if extension in ('.mid', '.midi'):
            kind = 'mid'
        elif extension == '.sseq':
            kind = 'sseq'
        else:                                   # no extension, or one that is neither: the type chosen in the dialog decides
            kind = 'sseq' if picked.get() == EXPORT_TYPES[1][0] else 'mid'
            out += '.' + kind
        try:
            blob = self.file(i) if kind == 'sseq' else to_midi(self.timeline(i), self.infos[i].name)
            with open(out, 'wb') as f:
                f.write(blob)
        except (OSError, ValueError) as e:
            messagebox.showerror('Export music', str(e))
            return
        self.note_text.set(f'Exported {os.path.basename(out)}.')

    def revert(self):
        i = self.sel
        if i is not None and self.new.pop(i, None) is not None:
            self.hush()
            self.fill()
            self.describe()
            self.draw()
            self.note_text.set('')

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert music', f'Revert {len(self.new)} changed sequence(s)?'):
            self.hush()
            self.new.clear()
            self.fill()
            self.describe()
            self.draw()
            self.note_text.set('')

    # ----- whole folders

    def listed(self):
        """Numbers of the sequences of the list, as shown."""
        return [int(i) for g in self.tree.get_children() for i in self.tree.get_children(g)]

    def export_all(self):
        folder = filedialog.askdirectory()
        if not folder or self.snd is None:
            return
        ids = self.listed()
        done = 0
        try:
            for n, i in enumerate(ids):
                base = os.path.join(folder, stem(self.infos[i]))
                with open(base + '.mid', 'wb') as f:
                    f.write(to_midi(self.timeline(i), self.infos[i].name))
                with open(base + '.sseq', 'wb') as f:
                    f.write(self.file(i))
                done += 1
                if n % 10 == 0:
                    self.count.set(f'Exporting {n} / {len(ids)}...')
                    self.update_idletasks()
        except (OSError, ValueError) as e:
            messagebox.showerror('Export music', str(e))
        self.fill()
        messagebox.showinfo('Export music', f'{done} sequence(s) exported to {folder}: a .mid and a .sseq each.')

    def replace_folder(self):
        self.import_all()

    def import_all(self):
        folder = filedialog.askdirectory(title='Folder with music files')
        if not folder or self.snd is None:
            return
        found = collections.defaultdict(dict)
        for name in sorted(os.listdir(folder)):
            m = FILE_NAME.match(name)
            if m and int(m.group(1)) in self.infos:
                found[int(m.group(1))][m.group(2).lower().replace('midi', 'mid')] = os.path.join(folder, name)
        done, errors = 0, []
        for i, files in sorted(found.items()):
            try:
                if self.import_changed(i, files):
                    done += 1
            except (OSError, ValueError) as e:
                errors.append(f'{os.path.basename(next(iter(files.values())))}: {e}')
        self.fill()
        self.describe()
        self.draw()
        text = f'{done} sequence(s) replaced.'
        messagebox.showinfo('Replace from folder', text + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    def import_changed(self, i, files):
        """Imports the file of a sequence that differs from the music it has now (the .sseq first, then the .mid). True when one was."""
        if 'sseq' in files:
            with open(files['sseq'], 'rb') as f:
                blob = f.read()
            if blob != self.file(i):
                self.import_blob(i, blob)
                return True
        if 'mid' in files:
            with open(files['mid'], 'rb') as f:
                blob = f.read()
            if fingerprint(from_midi(blob)) != fingerprint(self.timeline(i)):
                self.import_blob(i, blob)
                return True
        return False

    # ----- patch and project

    def patch_config(self):
        return {i: dict(e) for i, e in self.new.items()} or None

    def project_part(self):
        return {i: dict(e) for i, e in self.new.items()}

    def restore(self, part):
        self.hush()
        self.new.clear()
        self.memo.clear()
        notes = []
        if part:
            self.on_show()
        for i, edit in part.items():
            if self.snd is None or i not in self.infos:
                notes.append(f'Sequence {i} does not exist in this ROM: skipped.')
            else:
                self.new[i] = dict(edit)
        self.fill()
        self.describe()
        self.draw()
        return notes

    def summary(self):
        if not self.new:
            return 'Unchanged'
        grown = 0
        for i, e in self.new.items():
            if e.get('file') and self.snd is not None and i in self.infos:
                grown += len(e['file']) - self.infos[i].size
        return f'{len(self.new)} changed' + (f' ({grown:+,} bytes)' if grown else '')
