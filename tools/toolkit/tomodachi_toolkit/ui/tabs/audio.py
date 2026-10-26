"""Audio tab: the sounds of the game (waves of the sound archive) as WAV files."""
import os
import re
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...features.audio.sdat import wave_length, wave_pcm
from ...features.audio.wav import resample, wav_read, wav_write
from ..theme import BROWN, CANVAS, DARK, SAND
from .listing import ListingTab


def swav_size(w, n):
    """Bytes a wave of n samples takes in the sound archive, in the encoding of the wave w."""
    return 12 + (4 + (n // 2 + 1) if w['enc'] == 2 else n * 2 if w['enc'] == 1 else n) + 3 & ~3


def bank_names(banks, limit):
    return ', '.join(b.replace('BANK_', '') for b in banks[:limit])


class AudioTab(ListingTab):
    key = 'audio'
    title = 'Audio'
    heading = 'Audio'

    def build(self):
        self.snd, self.new, self.sel = None, {}, None
        self.fit = tk.BooleanVar(value=True)
        right = self.build_listing(
            weights=(2, 3), revert_all=self.revert_all, show='tree headings', columns=('dur', 'rate'),
            more=[('Export listed sounds to a folder...', self.export_all),
                  ('Replace from a folder (files named like exports)...', self.replace_folder)])
        self.tree.heading('#0', text='Sound (wave number, bank)')
        self.tree.heading('dur', text='Length')
        self.tree.heading('rate', text='Hz')
        self.tree.column('#0', width=230)
        self.tree.column('dur', width=60, anchor='e')
        self.tree.column('rate', width=60, anchor='e')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        tools = ttk.Frame(right)
        tools.pack(fill='x')
        self.buttons = [ttk.Button(tools, text=t, style=s, command=c) for t, s, c in (
            ('Play', 'Soft.TButton', self.play), ('Replace with WAV', 'Accent.TButton', self.replace),
            ('Export WAV', 'Soft.TButton', self.export), ('Revert', 'Soft.TButton', self.revert))]
        for b in self.buttons:
            b.pack(side='left', padx=(0, 6))
        ttk.Checkbutton(right, text='Shrink to the original size when the new sound is longer', variable=self.fit).pack(anchor='w', pady=(8, 0))
        self.wave = tk.Canvas(right, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, height=120, width=420)
        self.wave.pack(fill='x', pady=(8, 0))
        self.wave.bind('<Configure>', lambda e: self.draw())
        self.info = tk.StringVar()
        ttk.Label(right, textvariable=self.info, foreground=BROWN, wraplength=420, justify='left').pack(anchor='w', pady=(6, 0))
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.sel = None
        self.wave.delete('all')
        self.info.set('Select a sound in the list.' if self.snd else '')
        self.set_state()

    def set_state(self):
        for b in self.buttons:
            b.state(['!disabled'] if self.sel is not None else ['disabled'])

    def on_rom(self):
        self.snd, self.new = None, {}
        self.tree.delete(*self.tree.get_children())
        self.count.set('')
        self.reset_view()

    def on_show(self):
        if self.snd is None:
            try:
                self.snd = self.session.sound()
            except Exception as e:
                self.info.set(f'Cannot read the sound data: {e}')
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
            text = f"#{i:03d}  {bank_names(self.snd.banks.get(i, []), 2) or 'unused'}"
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
        self.set_state()
        self.draw()

    def draw(self):
        i = self.sel
        c = self.wave
        c.delete('all')
        if i is None or self.snd is None:
            return
        rate, pcm = self.pcm(i)
        w = self.snd.waves[i]
        enc = {0: 'PCM 8 bit', 1: 'PCM 16 bit', 2: 'ADPCM'}.get(w['enc'], '?')
        used = bank_names(self.snd.banks.get(i, []), 8) or 'no bank'
        self.info.set(f"Wave #{i}   {len(pcm) / max(rate, 1):.2f} s at {rate} Hz   {enc}{'   loops' if w['loop'] else ''}\nUsed by: {used}"
                      + ('   (REPLACED)' if i in self.new else ''))
        width, height = max(c.winfo_width(), 200), 120
        n = len(pcm)
        for x in range(width if n else 0):
            seg = pcm[x * n // width:max((x + 1) * n // width, x * n // width + 1)]
            if seg:
                c.create_line(x, height / 2 - max(seg) * 55 / 32768, x, height / 2 - min(seg) * 55 / 32768 + 1, fill=DARK)

    # ----- play, import and export

    def play(self):
        if self.sel is None:
            return
        rate, pcm = self.pcm(self.sel)
        error = self.app.player.play(rate, pcm)
        if error:
            messagebox.showerror('Play', error)

    def import_wav(self, i, data):
        """Stores a WAV as the new sound of wave i. Returns a note when the sound was changed to fit, else ''."""
        rate, pcm = wav_read(data)
        w = self.snd.waves[i]
        limit = w['end'] - w['off']
        note = ''
        if swav_size(w, len(pcm)) > limit:
            if not self.fit.get():
                note = f'It is {swav_size(w, len(pcm)) - limit:,} bytes bigger than the original: the ROM may not have room for it.'
            else:
                r = rate
                while swav_size(w, len(resample(pcm, rate, r))) > limit and r > 4000:
                    r = int(r * 0.92)
                if swav_size(w, len(resample(pcm, rate, r))) > limit:
                    raise ValueError('This sound is too long to fit in the space of the original.')
                pcm, rate = resample(pcm, rate, r), r
                note = f'Downsampled to {rate} Hz to fit the original size.'
        self.new[i] = {'rate': rate, 'pcm': struct.pack('<%dh' % len(pcm), *pcm)}
        return note

    def replace(self):
        i = self.sel
        if i is None:
            return
        path = filedialog.askopenfilename(filetypes=[('WAV audio', '*.wav')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                note = self.import_wav(i, f.read())
        except Exception as e:
            messagebox.showerror('Replace sound', str(e))
            return
        self.fill()
        self.draw()
        if note:
            messagebox.showwarning('Replace sound', f'Wave #{i} was imported.\n\n{note}')

    def export(self):
        i = self.sel
        if i is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.wav', initialfile=f'wave_{i:03d}.wav', filetypes=[('WAV audio', '*.wav')])
        if not out:
            return
        try:
            rate, pcm = self.pcm(i)
            with open(out, 'wb') as f:
                f.write(wav_write(rate, pcm))
        except Exception as e:
            messagebox.showerror('Export sound', str(e))

    def revert(self):
        i = self.sel
        if i is not None and self.new.pop(i, None) is not None:
            self.fill()
            self.draw()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert sounds', f'Revert {len(self.new)} replaced sound(s)?'):
            self.new.clear()
            self.fill()
            self.draw()

    def export_all(self):
        folder = filedialog.askdirectory()
        if not folder or self.snd is None:
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

    def replace_folder(self):
        folder = filedialog.askdirectory()
        if not folder or self.snd is None:
            return
        done, notes, errors = 0, 0, []
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
                    continue
                notes += bool(self.import_wav(i, data))
                done += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
        self.fill()
        self.draw()
        text = f'{done} sound(s) imported.'
        if notes:
            text += f' {notes} of them were changed to fit the original size or are too big.'
        messagebox.showinfo('Replace from folder', text + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

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
        self.fill()
        return notes

    def summary(self):
        return f'{len(self.new)} replaced' if self.new else 'Unchanged'
