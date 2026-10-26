"""The Listen bar: hear the line with a voice. It is a test: nothing here is written to the ROM."""
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ....features.audio.wav import wav_write
from ....features.speech.engine import SPEECH_SAMPLE_RATE
from ....features.speech.text import listening_text, speech_bytes
from ...theme import DARK


class ListenBar(ttk.Labelframe):
    """Plays the line as it is now ("Play") or as it is in the ROM ("Original") with the voice chosen here."""

    def __init__(self, master, tab):
        super().__init__(master, text='Listen   (a test: nothing here is written to the ROM)', padding=(8, 4, 8, 6))
        self.tab = tab
        self.catalog, self.voice_i, self.job, self.pcm = None, 0, None, None
        self.status = tk.StringVar()
        top = ttk.Frame(self)
        top.pack(fill='x')
        ttk.Label(top, text='Voice').pack(side='left')
        self.voice_box = ttk.Combobox(top, state='readonly', width=20)
        self.voice_box.pack(side='left', padx=(6, 8))
        self.voice_box.bind('<<ComboboxSelected>>', self.voice_chosen)
        self.edit_button = ttk.Button(top, text='Voice settings', style='Mini.TButton', command=self.edit_voice)
        self.edit_button.pack(side='left')
        row = ttk.Frame(self)
        row.pack(fill='x', pady=(6, 0))
        self.play_button = ttk.Button(row, text='Play', style='MiniAccent.TButton', command=self.speak)
        self.original_button = ttk.Button(row, text='Original', style='Mini.TButton', command=lambda: self.speak(original=True))
        self.stop_button = ttk.Button(row, text='Stop', style='Mini.TButton', command=self.stop)
        self.save_button = ttk.Button(row, text='Save WAV', style='Mini.TButton', command=self.save)
        for b in (self.play_button, self.original_button, self.stop_button, self.save_button):
            b.pack(side='left', padx=(0, 6))
        ttk.Label(row, textvariable=self.status, foreground=DARK, wraplength=260, justify='left').pack(side='left', padx=(6, 0))
        self.set_state()

    # ----- the voice

    def voice_name(self):
        return self.catalog.voices[self.voice_i]

    def voice_chosen(self, event=None):
        self.voice_i = self.voice_box.current()

    def edit_voice(self):
        if self.catalog is not None:
            self.tab.edit_preset(self.voice_name())

    def load(self, catalog):
        self.catalog, self.voice_i, self.pcm = catalog, 0, None
        self.status.set('')
        self.refresh_labels()
        self.set_state()

    def unload(self, note=''):
        self.stop()
        self.catalog, self.job, self.pcm = None, None, None
        self.voice_box['values'] = []
        self.voice_box.set('')
        self.status.set(note)
        self.set_state()

    def refresh_labels(self):
        """The voice names, with a dot in front of the ones whose settings were changed."""
        c = self.catalog
        if c is not None:
            self.voice_box['values'] = [c.mark(n, c.voice_label(n)) for n in c.voices]
            self.voice_box.current(self.voice_i)

    def reset(self):
        """A line was opened: forget the sound of the last one."""
        self.stop()
        self.pcm = None
        self.status.set('')
        self.set_state()

    def set_state(self):
        tab, on = self.tab, self.catalog is not None
        busy = on and tab.synth.busy
        line = tab.editor.active
        self.voice_box.configure(state='readonly' if on else 'disabled')
        self.edit_button.state(['!disabled'] if on else ['disabled'])
        self.play_button.state(['!disabled'] if on and line and not busy else ['disabled'])
        self.original_button.state(['!disabled'] if on and line and tab.editor.model.edited and not busy else ['disabled'])
        self.stop_button.state(['!disabled'] if on else ['disabled'])
        self.save_button.state(['!disabled'] if self.pcm and not busy else ['disabled'])

    # ----- sound

    def speak(self, original=False):
        tab = self.tab
        synth, model = tab.synth, tab.editor.model
        if synth is None or synth.busy or model is None:
            return
        try:
            data = speech_bytes(listening_text(model.original if original else model.text()))
        except ValueError as e:
            messagebox.showerror('Voice', str(e))
            return
        if not data.strip():
            self.status.set('There is nothing to say in this line.')
            return
        voice, edits = self.voice_name(), dict(self.catalog.edits)
        pcm = synth.cached(synth.key(data, voice, None, edits))
        if pcm is not None:
            self.play(pcm)
            return
        self.job = synth.start(data, voice, None, edits)
        self.set_state()
        self.after(150, self.poll, self.job)

    def poll(self, job):
        if job is not self.job:
            return
        if job.result is None:
            self.status.set(f'Making the sound... {self.tab.synth.seconds:.1f} s')
            self.after(150, self.poll, job)
            return
        self.job = None
        kind, value = job.result
        if kind == 'ok':
            self.play(value)
        elif kind == 'cancel':
            self.status.set('')
        else:
            self.status.set('')
            messagebox.showerror('Voice', f'The speech engine failed: {value}')
        self.set_state()

    def play(self, pcm):
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

    def save(self):
        if not self.pcm:
            return
        out = filedialog.asksaveasfilename(defaultextension='.wav', initialfile='speech.wav', filetypes=[('WAV audio', '*.wav')])
        if not out:
            return
        try:
            with open(out, 'wb') as f:
                f.write(wav_write(SPEECH_SAMPLE_RATE, struct.unpack('<%dh' % (len(self.pcm) // 2), self.pcm)))
        except OSError as e:
            messagebox.showerror('Save WAV', str(e))
