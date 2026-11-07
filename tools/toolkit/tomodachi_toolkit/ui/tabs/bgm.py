"""BGM tab: the music of the game (the sequences of the sound archive) to hear, and to take out or put back as MIDI or SSEQ files. The
music comes out with its instruments (a SoundFont for the MIDI files, the bank and the waves of the game for the SSEQ files)."""
import collections
import os
import re
import struct
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...features.bgm.catalog import bank_file, bank_names, bank_programs, sequence_file, sequences
from ...features.bgm.convert import assemble, fingerprint, from_midi, to_midi
from ...features.bgm.soundfont import Waves, soundfont
from ...features.bgm.sseq import SseqError, sseq_data, sseq_file
from ...features.bgm.synth import RATE, Bank, Synth, SynthError
from ...features.bgm.timeline import play
from ..theme import BROWN, CANVAS, MUTED, SAND
from ..transport import Transport
from ..widgets import InfoTable
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
        self.transport = Transport(lambda: self.app.player)      # the sound that plays, and the point it is at
        self.loaded = None                    # the sequence whose sound the transport holds
        self.start = 0.0                      # where listening starts, in seconds (the point, while the sound is not loaded)
        self.job = None                       # the sound being prepared
        self.tick_timer, self.poll_timer = None, None       # the line that follows the music; the look at the sound being prepared
        right = self.build_listing(
            weights=(2, 3), batch=(self.export_all, self.import_all, self.revert_all), show='tree headings', columns=('time', 'tracks', 'size'))
        self.tree.heading('#0', text='Sequence')
        self.tree.heading('time', text='Length')
        self.tree.heading('tracks', text='Tracks')
        self.tree.heading('size', text='Bytes')
        self.tree.column('#0', width=210)
        self.tree.column('time', width=55, anchor='e')
        self.tree.column('tracks', width=50, anchor='e')
        self.tree.column('size', width=60, anchor='e')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.note_text = tk.StringVar()
        self.build_menu(self.entries)
        self.table = InfoTable(right)
        self.table.pack(fill='x')
        row = ttk.Frame(right)
        row.pack(fill='x', pady=(8, 0))
        self.play_button = ttk.Button(row, text='▶ Play', style='Soft.TButton', command=self.listen)
        self.play_button.pack(side='left')
        self.play_text = tk.StringVar()
        ttk.Label(row, textvariable=self.play_text, foreground=MUTED).pack(side='left', padx=10)
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
        self.roll.bind('<Button-1>', self.seek_click)
        ttk.Label(right, textvariable=self.note_text, foreground=MUTED, wraplength=460, justify='left').pack(anchor='w', pady=(6, 0))
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.hush()
        self.sel = None
        self.roll.delete('all')
        self.table.show([])
        self.note_text.set('')
        self.set_state()

    def set_state(self):
        on = self.sel is not None
        self.play_button.state(['!disabled'] if on else ['disabled'])
        self.sync_revert()
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
        self.pause()

    def on_show(self):
        if self.snd is None:
            try:
                snd = self.session.sound()
                infos = {s.index: s for s in sequences(snd)}
            except Exception as e:
                self.table.show([('Error', f'Cannot read the music of the game: {e}')])
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

    def entries(self, iid):
        if not iid.isdigit():
            return []
        i = int(iid)
        return [('Play', self.listen), ('Export...', lambda: self.export(i)), ('Replace with MIDI or SSEQ...', lambda: self.replace(i)),
                None, ('Revert', (lambda: self.revert(i)) if i in self.new else None)]

    def item_changed(self):
        return self.sel in self.new

    def show_bank(self, name):
        """The music that plays with a bank (a link of the Audio tab): the list shows those sequences and the first is selected."""
        self.on_show()
        self.only.set(False)
        self.query.set(name.replace('BANK_', ''))
        leaves = [i for g in self.tree.get_children() for i in self.tree.get_children(g)]
        if leaves:
            self.tree.selection_set(leaves[0])
            self.tree.see(leaves[0])

    def describe(self):
        i = self.sel
        if i is None or self.snd is None:
            return
        s = self.infos[i]
        try:
            tl = self.timeline(i)
            loop = f'from {clock(tl.seconds(tl.loop[0]))} to {clock(tl.seconds(tl.loop[1]))}' if tl.loop else 'plays once'
            tempo = sorted({b for t, b in tl.tempos})
            speed = f'{tempo[0]} BPM' if len(tempo) == 1 else (f'{tempo[0]} to {tempo[-1]} BPM' if tempo else '120 BPM')
            rows = [('Length', clock(tl.seconds(tl.length))), ('Tracks', str(len(tl.lines))), ('Notes', f'{tl.note_count():,}'), ('Tempo', speed), ('Loop', loop)]
        except SseqError as e:
            rows = [('Error', f'Cannot read this sequence: {e}')]
        size = len(self.file(i))
        more = f' (the game has {s.size:,})' if size != s.size else ''
        self.table.show([('Sequence', s.name + ('   (changed)' if i in self.new else '')), ('Number', f'{i}   {s.player}')] + rows + [('File', f'{size:,} bytes{more}')])
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
        self.draw_head()

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
        self.roll.create_line(x, 0, x, height, fill=BROWN, width=3, tags='head')

    # ----- hearing the music

    def listen(self):
        """The Play button: plays the sequence from its point, as it will be in the game. Pause keeps the point, so Play goes on from there.
        While the sound is being prepared, the button cancels that."""
        if self.job is not None:
            self.cancel_job()
            self.after_play()
            return
        if self.transport.playing:
            self.pause()
            return
        i = self.sel
        if i is None or self.snd is None:
            return
        if self.loaded == i:                  # paused: go on from the point
            error = self.transport.play()
            if error:
                messagebox.showerror('Play', error)
            self.after_play()
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
            self.begin(pcm)
            return
        if self.synth is None:
            self.synth = Synth(self.snd.swar)
        job = self.job = Rendering()
        threading.Thread(target=job.work, args=(self.synth, tl, instruments, volume), daemon=True).start()
        self.play_text.set('Preparing the sound... 0%')
        self.after_play()
        self.poll_timer = self.after(100, self.poll, job, key, tl)

    def poll(self, job, key, tl):
        """Looks at the sound being prepared: shows how far it is, plays it when it is ready."""
        if job is not self.job:
            return
        self.poll_timer = None
        if not job.done:
            self.play_text.set('Preparing the sound... %d%%' % int(job.progress * 100))
            self.poll_timer = self.after(100, self.poll, job, key, tl)
            return
        self.job = None
        self.after_play()
        if job.error or job.pcm is None:
            if job.error:
                self.play_text.set(f'Cannot play this: {job.error}')
            return
        self.heard[key] = job.pcm
        while len(self.heard) > HEARD:
            self.heard.popitem(last=False)
        self.begin(job.pcm)

    def begin(self, pcm):
        """Puts a sound that is ready in the transport, at the point, and plays it. The transport keeps it, so Pause and Play work on it."""
        if not any(pcm):
            self.after_play()
            self.play_text.set('Nothing to hear: the bank has none of the instruments this music asks for.')
            return
        self.transport.load(pcm, RATE, self.start)
        self.loaded = self.sel
        error = self.transport.play()
        self.after_play()
        if error:
            messagebox.showerror('Play', error)

    def cancel_job(self):
        """Drops the sound being prepared: its thread is asked to stop, and the look at it ends."""
        if self.job is not None:
            self.job.stop.set()
            self.job = None
        if self.poll_timer is not None:
            self.after_cancel(self.poll_timer)
            self.poll_timer = None

    def pause(self):
        """Pauses the music and keeps its point, so that Play goes on from there. A sound still being prepared is dropped."""
        self.cancel_job()
        self.transport.pause()
        self.after_play()

    def hush(self):
        """Stops the music for good: the sound is dropped and the point goes back to the start. An edit of the sequence or of its settings
        does this, as the sound made from the old ones is no longer the one to play."""
        self.cancel_job()
        self.transport.stop()
        self.loaded, self.start = None, 0.0
        self.after_play()

    def after_play(self):
        """Keeps the button, the text under it and the line on the piano roll in step with the music: the line follows the sound while it
        plays, and stays at the point when it is paused."""
        if self.tick_timer is not None:
            self.after_cancel(self.tick_timer)
            self.tick_timer = None
        here = self.sel is not None and self.loaded == self.sel
        playing = here and self.transport.playing
        if self.job is not None:
            self.play_button.config(text='Cancel')
        else:
            self.play_button.config(text='Pause' if playing else '▶ Play')
        self.show_time(here)
        self.draw_head()
        if playing:
            self.tick_timer = self.after(40, self.tick)          # the line moves 25 times a second, so it follows the music

    def show_time(self, here):
        """The text under the button: the time reached in the music and its length, or where the listening starts."""
        if self.job is not None:
            return                                # the preparation shows its own progress
        if not here:
            self.play_text.set(f'Starts at {clock(self.start)}' if self.start > 0 else '')
            return
        music = max(self.transport.duration - TAIL, 0.0)
        now = min(self.transport.position(), music)
        if self.transport.playing:
            word = 'Playing'
        elif self.transport.position() >= self.transport.duration - 0.02:
            word = 'Ended'
        else:
            word = 'Paused at'
        self.play_text.set(f'{word} {clock(now)} / {clock(music)}')

    def tick(self):
        self.tick_timer = None
        if self.transport.playing and self.transport.position() >= self.transport.duration:
            self.transport.pause()                # the sound is over: the point stays at its end, and Play starts it again
        self.after_play()

    def draw_head(self):
        """The line on the piano roll where the music is: where it has reached while it plays, else the point it starts from."""
        self.roll.delete('head')
        if self.sel is None or self.snd is None:
            return
        try:
            tl = self.timeline(self.sel)
        except SseqError:
            return
        seconds = self.transport.position() if self.loaded == self.sel else self.start
        self.move_head(tl.ticks_at(seconds))

    def seek_click(self, event):
        """A click on the piano roll sets the point where the listening starts. A sound that plays goes on from there."""
        i = self.sel
        if i is None or self.snd is None:
            return
        try:
            tl = self.timeline(i)
        except SseqError:
            return
        width, _ = self.roll_size()
        self.start = tl.seconds(round(min(max(event.x, 0), width) / width * max(tl.length, 1)))
        if self.loaded == i:
            error = self.transport.seek(self.start)
            if error:
                messagebox.showerror('Play', error)
        self.after_play()

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

    def replace(self, i=None):
        i = self.sel if i is None else i
        path = filedialog.askopenfilename(filetypes=MIDI_TYPES) if i is not None else ''
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

    def bank_folder(self, bank):
        """The name of the folder of a bank in an export: the name of the bank in the archive."""
        return re.sub(r'[^\w.-]+', '_', self.bank_label(bank)).strip('._') or 'bank_%d' % bank

    def instruments(self, bank, extensions, waves=None):
        """The files of the instruments of a bank, by extension: '.sf2' (a SoundFont), '.sbnk' (the bank as the game has it) and '.swar'
        (the waves of the game). Returns ({extension: bytes}, why some are missing or ''). waves: the Waves of the archive, when there
        are some already (to make many SoundFonts quickly)."""
        files, why = {}, ''
        try:
            data = bank_file(self.snd, bank)
        except (IndexError, TypeError, struct.error):
            return files, 'the instruments of this bank cannot be read'
        if '.sbnk' in extensions:
            files['.sbnk'] = data
        if '.swar' in extensions:
            files['.swar'] = self.snd.swar
        if '.sf2' in extensions:
            try:
                files['.sf2'] = soundfont(data, self.snd.swar, self.bank_label(bank), waves)
            except SynthError as e:
                why = str(e).rstrip('.')
        return files, why

    def export(self, i=None):
        """Saves the music of the sequence as a MIDI file or as an SSEQ file: the name or the type chosen in the dialog says which. The
        instruments come out beside it with the same name: a SoundFont for the MIDI file, the bank and the waves for the SSEQ file."""
        i = self.sel if i is None else i
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
        base = os.path.splitext(out)[0]
        try:
            blob = self.file(i) if kind == 'sseq' else to_midi(self.timeline(i), self.infos[i].name)
            more, why = self.instruments(self.setting(i, 'bank'), ('.sbnk', '.swar') if kind == 'sseq' else ('.sf2',))
            with open(out, 'wb') as f:
                f.write(blob)
            for suffix, data in more.items():
                with open(base + suffix, 'wb') as f:
                    f.write(data)
        except (OSError, ValueError) as e:
            messagebox.showerror('Export music', str(e))
            return
        name, put = os.path.basename(out), [os.path.basename(base) + suffix for suffix in more]
        if not put:
            said = f'Exported {name}.'
        elif kind == 'mid':
            said = f'Exported {name} and {put[0]}: play the MIDI file with that SoundFont to hear the music of the game.'
        else:
            said = f'Exported {name} with {put[0]} and {put[1]}, the instruments of the game.'
        self.note_text.set(said + (f' No instruments: {why}.' if why else ''))

    def revert(self, i=None):
        i = self.sel if i is None else i
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
        """The listed sequences in a folder, each as a .mid and a .sseq, in a folder per bank. The instruments are in the folder of the
        bank: the SoundFont (.sf2) for the .mid files, the bank as the game has it (.sbnk) for the .sseq files. The waves of the game
        (.swar, that every .sbnk uses) are once at the top."""
        if self.snd is None:
            return
        folder = filedialog.askdirectory(title='Folder to export the listed sequences to (with their instruments)')
        if not folder:
            return
        ids = self.listed()
        if not ids:
            messagebox.showinfo('Export music', 'There is no sequence in the list.')
            return
        waves, folders, problems, done = Waves(self.snd.swar), {}, {}, 0
        try:
            for n, i in enumerate(ids):
                bank = self.setting(i, 'bank')
                if bank not in folders:
                    where = folders[bank] = os.path.join(folder, self.bank_folder(bank))
                    os.makedirs(where, exist_ok=True)
                    files, why = self.instruments(bank, ('.sf2', '.sbnk'), waves)
                    for suffix, data in files.items():
                        with open(os.path.join(where, self.bank_folder(bank) + suffix), 'wb') as f:
                            f.write(data)
                    if why:
                        problems[self.bank_label(bank)] = why
                base = os.path.join(folders[bank], stem(self.infos[i]))
                with open(base + '.mid', 'wb') as f:
                    f.write(to_midi(self.timeline(i), self.infos[i].name))
                with open(base + '.sseq', 'wb') as f:
                    f.write(self.file(i))
                done += 1
                if n % 10 == 0:
                    self.count.set(f'Exporting {n} / {len(ids)}...')
                    self.update_idletasks()
            with open(os.path.join(folder, 'waves.swar'), 'wb') as f:
                f.write(self.snd.swar)
        except (OSError, ValueError) as e:
            messagebox.showerror('Export music', str(e))
        self.fill()
        text = (f'{done} sequence(s) exported to {folder}, in a folder per bank: a .mid and a .sseq each, with the instruments of the bank '
                f'(a SoundFont for the .mid files, the .sbnk for the .sseq files; waves.swar has the waves they use).')
        if problems:
            text += '\n\nNo instruments for:\n' + '\n'.join(f'{name}: {why}' for name, why in list(problems.items())[:12])
        messagebox.showinfo('Export music', text)

    def import_all(self):
        """The .sseq and .mid files of a folder (and of the folders in it) that are named like the export names them. Music that is the
        same as now is skipped."""
        if self.snd is None:
            return
        folder = filedialog.askdirectory(title='Folder with the .mid and .sseq files named like the exports')
        if not folder:
            return
        found = collections.defaultdict(dict)
        for root, dirs, names in os.walk(folder):
            dirs.sort()
            for name in sorted(names):
                m = FILE_NAME.match(name)
                if m and int(m.group(1)) in self.infos:
                    found[int(m.group(1))][m.group(2).lower().replace('midi', 'mid')] = os.path.join(root, name)
        done, same, errors = 0, 0, []
        for i, files in sorted(found.items()):
            try:
                if self.import_changed(i, files):
                    done += 1
                else:
                    same += 1
            except (OSError, ValueError) as e:
                errors.append(f'{os.path.basename(next(iter(files.values())))}: {e}')
        self.fill()
        self.describe()
        self.draw()
        text = f'{done} sequence(s) imported' + (f', {same} the same as they are now' if same else '') + '.'
        messagebox.showinfo('Import music', text + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

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
