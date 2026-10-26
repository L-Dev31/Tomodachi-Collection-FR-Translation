"""BMG tab: replace the message files of the game."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.bmg import bmg_problems
from ...features.bmg import bmg_list
from ..theme import BROWN, DARK, ERROR, MUTED, PANEL, font
from .base import Tab


class BmgTab(Tab):
    key = 'bmg'
    title = 'BMG'
    heading = 'BMG'

    def build(self):
        self.files, self.new = {}, {}
        bar = ttk.Frame(self)
        bar.pack(fill='x')
        ttk.Button(bar, text='Replace from folder', style='Soft.TButton', command=self.from_folder).pack(side='left')
        ttk.Button(bar, text='Cancel all', style='Soft.TButton', command=self.clear).pack(side='left', padx=(8, 0))
        box = ttk.Labelframe(self, text='Game BMG files', padding=8)
        box.pack(fill='both', expand=True, pady=(10, 0))
        canvas = tk.Canvas(box, bg=PANEL, height=300, width=470, highlightthickness=0)
        scroll = ttk.Scrollbar(box, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.rows = tk.Frame(canvas, bg=PANEL)
        canvas.create_window((0, 0), window=self.rows, anchor='nw')
        self.rows.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        canvas.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
        canvas.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

    def on_rom(self):
        self.new.clear()
        self.files = bmg_list(self.session.rom)
        self.draw()

    def draw(self):
        for w in self.rows.winfo_children():
            w.destroy()
        for r, (path, (name, bad)) in enumerate(sorted(self.files.items(), key=lambda kv: kv[1][0].lower())):
            new = self.new.get(path)
            if new:
                text, color = f'will use {new[0]} ({len(new[1])} bytes)', DARK
            else:
                text, color = ('ROM copy: ' + bad[0], ERROR) if bad else ('ROM copy: ok', MUTED)
            tk.Label(self.rows, text=name, bg=PANEL, fg=BROWN, font=font(9, True), anchor='w', width=26).grid(row=r, column=0, sticky='w', pady=2)
            tk.Label(self.rows, text=text, bg=PANEL, fg=color, font=font(8), anchor='w', width=34).grid(row=r, column=1, sticky='w')
            ttk.Button(self.rows, text='Replace', style='Soft.TButton', command=lambda p=path: self.pick(p)).grid(row=r, column=2, padx=(4, 0))
            ttk.Button(self.rows, text='Cancel', style='Soft.TButton', command=lambda p=path: self.cancel(p), state='normal' if new else 'disabled').grid(row=r, column=3, padx=(4, 0))
        self.changed()

    def set_file(self, path, file):
        with open(file, 'rb') as f:
            data = f.read()
        bad = bmg_problems(data)
        if bad:
            raise ValueError(f'{os.path.basename(file)}: {bad[0]}')
        self.new[path] = (os.path.basename(file), data)

    def pick(self, path):
        file = filedialog.askopenfilename(filetypes=[('BMG message file', '*.bmg')])
        if not file:
            return
        try:
            self.set_file(path, file)
        except Exception as e:
            messagebox.showerror('BMG', str(e))
        self.draw()

    def cancel(self, path):
        self.new.pop(path, None)
        self.draw()

    def clear(self):
        self.new.clear()
        self.draw()

    def from_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        have = {n.lower(): n for n in os.listdir(folder)}
        done, errors = 0, []
        for path, (name, _) in self.files.items():
            if name.lower() in have:
                try:
                    self.set_file(path, os.path.join(folder, have[name.lower()]))
                    done += 1
                except Exception as e:
                    errors.append(str(e))
        self.draw()
        messagebox.showinfo('BMG', f'{done} file(s) selected.' + ('\n\nSkipped:\n' + '\n'.join(errors) if errors else ''))

    def patch_config(self):
        return {p: b for p, (n, b) in self.new.items()} or None

    def project_part(self):
        return {self.files[p][0]: b for p, (n, b) in self.new.items()}

    def restore(self, part):
        by_name = {n: p for p, (n, _) in self.files.items()}
        self.new.clear()
        notes = []
        for name, data in part.items():
            if name in by_name:
                self.new[by_name[name]] = (name, data)
            else:
                notes.append(f'BMG {name} does not exist in this ROM: skipped.')
        self.draw()
        return notes

    def summary(self):
        return f'{len(self.new)} replaced' if self.new else 'Unchanged'
