"""Audio tab: the sounds of the game (waves of the sound archive) as WAV files. A right click on a sound plays, exports or replaces it. Play starts
the sound from its point and Pause keeps the point; a click on the wave moves it. A line on the wave shows where the sound is."""
import collections
import os
import re
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...features.audio.sdat import wave_length, wave_pcm
from ...features.audio.wav import resample, resample_length, wav_read, wav_write
from ...features.bgm.catalog import bank_names, sequences
from ..theme import BROWN, CANVAS, DARK, SAND
from ..transport import Transport
from ..widgets import InfoTable
from .listing import ListingTab


def swav_size(w, n):
    """Bytes a wave of n samples takes in the sound archive, as wave_encode makes it: the 12 bytes of its header and its data (for ADPCM the
    4 bytes of the predictor, then two samples a byte), padded to 4 bytes."""
    data = 4 + n // 2 if w['enc'] == 2 else n * 2 if w['enc'] == 1 else n
    return 12 + (data + 3) // 4 * 4


def bank_names_text(banks, limit):
    return ', '.join(b.replace('BANK_', '') for b in banks[:limit])


class AudioTab(ListingTab):
    key = 'audio'
    title = 'Audio'
    heading = 'Audio'

    def build(self):
        self.snd, self.new, self.sel, self.music = None, {}, None, None       # music: {bank name: [numbers of the sequences that play with it]}
        self.transport = Transport(lambda: self.app.player)                    # the sound that plays, and the point it is at
        self.loaded, self.timer = None, None                                   # the wave the transport holds; the timer that moves the line
        right = self.build_listing(
            weights=(2, 3), batch=(self.export_all, self.import_all, self.revert_all), show='tree headings', columns=('dur', 'rate'))
        self.tree.heading('#0', text='Sound (wave number, bank)')
        self.tree.heading('dur', text='Length')
        self.tree.heading('rate', text='Hz')
        self.tree.column('#0', width=230)
        self.tree.column('dur', width=60, anchor='e')
        self.tree.column('rate', width=60, anchor='e')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.build_menu(lambda iid: [('Play', lambda: self.play(int(iid))), ('Export WAV...', lambda: self.export(int(iid))),
                                     ('Replace with WAV...', lambda: self.replace(int(iid))),
                                     None, ('Revert', (lambda: self.revert(int(iid))) if int(iid) in self.new else None)] if iid.isdigit() else [])
        self.table = InfoTable(right)
        self.table.pack(fill='x')
        row = ttk.Frame(right)
        row.pack(fill='x', pady=(8, 0))
        self.play_button = ttk.Button(row, text='▶ Play', style='Soft.TButton', command=self.play)
        self.play_button.pack(side='left')
        self.wave = tk.Canvas(right, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=120, width=420)
        self.wave.pack(fill='both', expand=True, pady=(8, 0))
        self.wave.bind('<Configure>', lambda e: self.draw())
        self.wave.bind('<Button-1>', self.seek_click)
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.sel = None
        self.forget_loaded()
        self.wave.delete('all')
        self.table.show([])
        self.set_state()

    def forget_loaded(self):
        """The sound the transport holds is taken away (it was changed, or another list was shown): its point goes back to the start."""
        self.transport.stop()
        self.loaded = None

    def on_hide(self):
        self.transport.pause()
        self.refresh_play()

    def set_state(self):
        self.play_button.state(['!disabled'] if self.sel is not None else ['disabled'])
        self.sync_revert()

    def on_rom(self):
        self.snd, self.new, self.music = None, {}, None
        self.tree.delete(*self.tree.get_children())
        self.count.set('')
        self.reset_view()

    def on_show(self):
        if self.snd is None:
            try:
                self.snd = self.session.sound()
            except Exception as e:
                self.table.show([('Error', f'Cannot read the sound data: {e}')])
                return
            self.reset_view()
            self.fill()

    def length(self, i):
        """Samples of a wave as it will be patched."""
        return len(self.new[i]['pcm']) // 2 if i in self.new else wave_length(self.snd.waves[i])

    def rate(self, i):
        return self.new[i]['rate'] if i in self.new else self.snd.waves[i]['rate']

    def pcm(self, i):
        """(rate, samples) of a wave as it will be patched."""
        if i in self.new:
            a = self.new[i]
            return a['rate'], list(struct.unpack('<%dh' % (len(a['pcm']) // 2), a['pcm']))
        w = self.snd.waves[i]
        return w['rate'], wave_pcm(self.snd.swar, w)

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        if self.snd is None:
            self.count.set('')
            return
        q = self.query.get().strip().lower()
        groups, shown = {}, 0
        for i in range(len(self.snd.waves)):
            if self.only.get() and i not in self.new:
                continue
            text = f"#{i:03d}  {bank_names_text(self.snd.banks.get(i, []), 2) or 'unused'}"
            if q and q not in text.lower() and q != str(i):
                continue
            g = self.snd.label(i)
            if g not in groups:
                groups[g] = self.tree.insert('', 'end', iid='g:' + g, text=g, open=bool(q) or self.only.get())
            mod = i in self.new
            self.tree.insert(groups[g], 'end', iid=str(i), text=('● ' if mod else '') + text,
                             values=(f'{self.length(i) / max(self.rate(i), 1):.2f}s', self.rate(i)), tags=('mod',) if mod else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.snd.waves)}   ● {len(self.new)} replaced')
        if self.sel is not None and self.tree.exists(str(self.sel)):
            self.tree.selection_set(str(self.sel))
            self.tree.see(str(self.sel))
        self.changed()

    def select(self, event=None):
        sel = self.tree.selection()
        if not sel or not sel[0].isdigit():
            return
        i = int(sel[0])
        if i == self.sel and event is not None:
            return
        self.sel = i
        self.transport.pause()          # a sound that plays stops when another one is chosen; its point is kept
        self.set_state()
        self.draw()

    def music_of(self, bank):
        """The numbers of the sequences of the music that play with a bank (the sounds of the other sequences are effects)."""
        if self.music is None:
            names = dict(bank_names(self.snd))
            self.music = collections.defaultdict(list)
            for s in sequences(self.snd):
                self.music[names.get(s.bank)].append(s.index)
        return self.music[bank]

    def draw(self):
        i = self.sel
        c = self.wave
        c.delete('all')
        if i is None or self.snd is None:
            return
        rate, pcm = self.pcm(i)
        w = self.snd.waves[i]
        enc = {0: 'PCM 8 bit', 1: 'PCM 16 bit', 2: 'ADPCM'}.get(w['enc'], '?')
        rows = [('Wave', f'#{i}' + ('   (replaced)' if i in self.new else '')), ('Length', f'{len(pcm) / max(rate, 1):.2f} s'),
                ('Rate', f'{rate} Hz'), ('Encoding', enc + (', loops' if w['loop'] else ''))]
        used = self.snd.banks.get(i, [])
        for k, bank in enumerate(used[:8]):
            n = len(self.music_of(bank))
            label = bank.replace('BANK_', '')
            rows.append(('Used by' if not k else '', f'{label}   ({n} music)', lambda b=bank: self.app.open_bank(b)) if n else
                        ('Used by' if not k else '', f'{label}   (sound effects only)'))
        if not used:
            rows.append(('Used by', 'no bank'))
        self.table.show(rows)
        width, height = max(c.winfo_width(), 200), max(c.winfo_height(), 120)
        n = len(pcm)
        for x in range(width if n else 0):
            seg = pcm[x * n // width:max((x + 1) * n // width, x * n // width + 1)]
            if seg:
                c.create_line(x, height / 2 - max(seg) * (height / 2 - 5) / 32768, x, height / 2 - min(seg) * (height / 2 - 5) / 32768 + 1, fill=DARK)
        self.refresh_play()

    # ----- play, pause and the point

    def load_sound(self, i):
        """Puts the sound of wave i in the transport, at its start."""
        rate, pcm = self.pcm(i)
        self.transport.load(pcm, rate)
        self.loaded = i

    def play(self, i=None):
        """The Play button: plays the selected sound from its point, or pauses it (the point is kept, so Play goes on from there). A right click on
        a sound plays it from its start."""
        if i is None:
            if self.transport.playing:
                self.transport.pause()
                return self.refresh_play()
            i = self.sel
            if i is None:
                return
            if self.loaded != i:
                self.load_sound(i)
        else:
            self.load_sound(i)
        error = self.transport.play()
        if error:
            messagebox.showerror('Play', error)
        self.refresh_play()

    def seek_click(self, event):
        """A click on the wave puts the point to listen from there: a sound that plays goes on from it."""
        if self.sel is None or self.snd is None:
            return
        if self.loaded != self.sel:
            self.load_sound(self.sel)
        width = max(self.wave.winfo_width(), 1)
        error = self.transport.seek(min(max(event.x, 0), width) / width * self.transport.duration)
        if error:
            messagebox.showerror('Play', error)
        self.refresh_play()

    def refresh_play(self):
        """The Play button, and the line on the wave where the sound is: it moves while the sound plays, and stays where it was paused."""
        here = self.sel is not None and self.loaded == self.sel
        playing = here and self.transport.playing
        self.play_button.configure(text='Pause' if playing else '▶ Play')
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        self.head(self.transport.position() if here else 0.0)
        if playing:
            self.timer = self.after(30, self.tick)

    def tick(self):
        self.timer = None
        if self.transport.playing and self.transport.position() >= self.transport.duration:
            self.transport.pause()                  # the sound is over: the point stays at its end
        self.refresh_play()

    def head(self, seconds):
        """The line on the wave at a point of the sound (in seconds)."""
        c = self.wave
        c.delete('playhead')
        if self.sel is None:
            return
        share = seconds / self.transport.duration if self.transport.duration > 0 else 0.0
        x = min(max(share, 0.0), 1.0) * max(c.winfo_width(), 1)
        c.create_line(x, 0, x, c.winfo_height(), fill=BROWN, width=2, tags='playhead')

    # ----- play, import and export

    def too_long(self, i, data):
        """How many bytes a WAV file is bigger than the wave i it would replace (0 when it fits)."""
        rate, pcm = wav_read(data)
        w = self.snd.waves[i]
        return max(0, swav_size(w, len(pcm)) - (w['end'] - w['off']))

    def shrink_asked(self, pairs):
        """The question of an import: when a new sound is longer than the one it replaces, shrink it to the size of the original (it is then
        played at a lower rate), or keep it as it is (the ROM may have no room for it). One question for all of them. pairs: [(wave, WAV
        bytes)]. Returns True to shrink."""
        longer = [i for i, data in pairs if self.too_long(i, data)]
        if not longer:
            return True
        names = ', '.join(f'#{i}' for i in longer[:6]) + (' ...' if len(longer) > 6 else '')
        return messagebox.askyesno('Import sound', f'{len(longer)} sound(s) are longer than the original: {names}.\n\n'
                                   'Shrink them to the size of the original (they are then played at a lower rate)?\n'
                                   'No keeps them as they are: the ROM may not have room for them.')

    def import_wav(self, i, data, fit=True):
        """Stores a WAV as the new sound of wave i. fit: shrink it to the size of the original when it is longer. Returns a note when the
        sound was changed to fit, else ''."""
        rate, pcm = wav_read(data)
        w = self.snd.waves[i]
        limit = w['end'] - w['off']
        note = ''
        if swav_size(w, len(pcm)) > limit:
            if not fit:
                note = f'It is {swav_size(w, len(pcm)) - limit:,} bytes bigger than the original: the ROM may not have room for it.'
            else:
                r = rate
                while swav_size(w, resample_length(len(pcm), rate, r)) > limit and r > 4000:
                    r = int(r * 0.92)
                if swav_size(w, resample_length(len(pcm), rate, r)) > limit:
                    raise ValueError('This sound is too long to fit in the space of the original.')
                pcm, rate = resample(pcm, rate, r), r
                note = f'Downsampled to {rate} Hz to fit the original size.'
        self.new[i] = {'rate': rate, 'pcm': struct.pack('<%dh' % len(pcm), *pcm)}
        return note

    def replace(self, i=None):
        i = self.sel if i is None else i
        path = filedialog.askopenfilename(filetypes=[('WAV audio', '*.wav')]) if i is not None else ''
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                data = f.read()
            fit = self.shrink_asked([(i, data)])
            note = self.import_wav(i, data, fit)
        except Exception as e:
            messagebox.showerror('Replace sound', str(e))
            return
        self.forget_loaded()
        self.fill()
        self.draw()
        if note:
            messagebox.showwarning('Replace sound', f'Wave #{i} was imported.\n\n{note}')

    def export(self, i=None):
        i = self.sel if i is None else i
        out = filedialog.asksaveasfilename(defaultextension='.wav', initialfile=f'wave_{i:03d}.wav', filetypes=[('WAV audio', '*.wav')]) if i is not None else ''
        if not out:
            return
        try:
            rate, pcm = self.pcm(i)
            with open(out, 'wb') as f:
                f.write(wav_write(rate, pcm))
        except Exception as e:
            messagebox.showerror('Export sound', str(e))

    def item_changed(self):
        return self.sel in self.new

    def revert(self, i=None):
        i = self.sel if i is None else i
        if i is not None and self.new.pop(i, None) is not None:
            if self.loaded == i:
                self.forget_loaded()
            self.fill()
            self.draw()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert sounds', f'Revert {len(self.new)} replaced sound(s)?'):
            self.new.clear()
            self.forget_loaded()
            self.fill()
            self.draw()

    def export_all(self):
        """The listed sounds as WAV files in a folder (wave_012.wav ...)."""
        if self.snd is None:
            return
        folder = filedialog.askdirectory(title='Folder to export the listed sounds to')
        if not folder:
            return
        ids = [int(i) for g in self.tree.get_children() for i in self.tree.get_children(g)]
        try:
            for n, i in enumerate(ids):
                rate, pcm = self.pcm(i)
                with open(os.path.join(folder, f'wave_{i:03d}.wav'), 'wb') as f:
                    f.write(wav_write(rate, pcm))
                if n % 10 == 0:
                    self.count.set(f'Exporting {n} / {len(ids)}...')
                    self.update_idletasks()
        except Exception as e:
            messagebox.showerror('Export sounds', str(e))
        self.fill()
        messagebox.showinfo('Export sounds', f'{len(ids)} sound(s) exported to {folder}')

    def import_all(self):
        """The WAV files of a folder that are named like the export names them. A sound that is the same as now is skipped; the longer ones are
        shrunk or kept after one question for all of them."""
        if self.snd is None:
            return
        folder = filedialog.askdirectory(title='Folder with the WAV files named like the exports')
        if not folder:
            return
        same, errors, pairs = 0, [], []
        for name in sorted(os.listdir(folder)):
            m = re.fullmatch(r'wave_(\d+)\.wav', name.lower())
            if not m or int(m.group(1)) >= len(self.snd.waves):
                continue
            i = int(m.group(1))
            try:
                with open(os.path.join(folder, name), 'rb') as f:
                    data = f.read()
                rate, pcm = wav_read(data)
                cur_rate, cur = self.pcm(i)
                if rate == cur_rate and pcm == cur:
                    same += 1
                    continue
                pairs.append((i, name, data))
            except Exception as e:
                errors.append(f'{name}: {e}')
        fit = self.shrink_asked([(i, data) for i, _, data in pairs])
        done, notes = 0, 0
        for i, name, data in pairs:
            try:
                notes += bool(self.import_wav(i, data, fit))
                done += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
        self.forget_loaded()
        self.fill()
        self.draw()
        text = f'{done} sound(s) imported' + (f', {same} the same as they are now' if same else '') + '.'
        if notes:
            text += f' {notes} of them were changed to fit the original size or are too big.'
        messagebox.showinfo('Import sounds', text + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    # ----- patch and project

    def patch_config(self):
        return dict(self.new) or None

    def project_part(self):
        return dict(self.new)

    def restore(self, part):
        self.new.clear()
        notes = []
        if part:
            self.on_show()
        for i, a in part.items():
            if self.snd is not None and i < len(self.snd.waves):
                self.new[i] = a
            else:
                notes.append(f'Sound #{i} does not exist in this ROM: skipped.')
        self.forget_loaded()
        self.fill()
        self.draw()
        return notes

    def summary(self):
        return f'{len(self.new)} replaced' if self.new else 'Unchanged'
