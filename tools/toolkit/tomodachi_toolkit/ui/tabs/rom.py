"""ROM tab: open the game, see what will be applied, patch, export and project files."""
import os
import tkinter as tk
from tkinter import ttk

from ...features.meta import banner_pixels
from ..theme import BG, BROWN, DARK, MUTED, PANEL, WARM, font
from ..widgets import caption, card
from .base import Tab


class RomTab(Tab):
    title = 'ROM'

    def build(self):
        self.name = tk.StringVar(value='No ROM loaded')
        self.folder = tk.StringVar(value='Open a Tomodachi Collection .nds file to unlock the other tabs.')
        self.size = tk.StringVar()
        self.lines = {}
        box = card(self)
        box.pack(fill='x')
        holder = tk.Frame(box, width=64, height=64, bg=WARM)
        holder.pack_propagate(False)
        holder.grid(row=0, column=0, rowspan=3, sticky='n')
        self.badge = tk.Label(holder, text='?', bg=WARM, fg='white', font=font(22, True), bd=0)
        self.badge.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(box, textvariable=self.name, bg=PANEL, fg=BROWN, font=font(11, True), anchor='w').grid(row=0, column=1, sticky='w', padx=12)
        tk.Label(box, textvariable=self.folder, bg=PANEL, fg=MUTED, font=font(8), anchor='w', justify='left', wraplength=210).grid(row=1, column=1, sticky='w', padx=12)
        tk.Label(box, textvariable=self.size, bg=PANEL, fg=DARK, font=font(9, True), anchor='w').grid(row=2, column=1, sticky='w', padx=12)
        self.open_button = ttk.Button(box, text='Open ROM', style='Accent.TButton', command=self.app.open_rom)
        self.open_button.grid(row=0, column=2, rowspan=3, sticky='e')
        box.columnconfigure(1, weight=1)
        self.summary_box = card(self, pady=12)
        self.summary_box.pack(fill='x', pady=(12, 0))
        caption(self.summary_box, 'WILL BE APPLIED', row=0, column=0, columnspan=2, sticky='w')
        self.patch_button = ttk.Button(self, text='Patch ROM', style='Big.TButton', command=self.app.patch_rom)
        self.patch_button.pack(fill='x', pady=(14, 0))
        self.buttons = [self.patch_button]
        for row_buttons in ((('Export BPS patch (for Flips)', self.app.export_bps),),
                            (('Save project (.tomods)', self.app.save_project), ('Open project (.tomods)', self.app.open_project))):
            row = ttk.Frame(self)
            row.pack(fill='x', pady=(8, 0))
            for n, (text, command) in enumerate(row_buttons):
                b = ttk.Button(row, text=text, style='Soft.TButton', command=command)
                b.pack(side='left', expand=True, fill='x', padx=(8 if n else 0, 0))
                self.buttons.append(b)
        self.status = tk.Label(self, text='', bg=BG, fg=DARK, font=font(9))
        self.status.pack(pady=(8, 0))

    def add_summary(self, tabs):
        """One line per tab that has a heading. The values are StringVars the app refreshes."""
        for r, tab in enumerate((t for t in tabs if t.heading), 1):
            var = tk.StringVar()
            self.lines[tab.key] = var
            tk.Label(self.summary_box, text=tab.heading, bg=PANEL, fg=MUTED, font=font(9), anchor='w', width=9).grid(row=r, column=0, sticky='nw', pady=(8, 0))
            tk.Label(self.summary_box, textvariable=var, bg=PANEL, fg=BROWN, font=font(9, True), anchor='w', justify='left', wraplength=290).grid(row=r, column=1, sticky='w', pady=(8, 0))

    def set_enabled(self, on):
        for b in self.buttons:
            b.state(['!disabled'] if on else ['disabled'])

    def on_rom(self):
        session = self.session
        img = tk.PhotoImage(master=self, width=32, height=32)
        for y, row in enumerate(banner_pixels(session.data)):
            img.put('{' + ' '.join(c or PANEL for c in row) + '}', to=(0, y))
        self.banner = img.zoom(2)
        self.badge.config(image=self.banner, text='', bg=PANEL)
        folder = os.path.dirname(session.path)
        self.name.set(session.name)
        self.folder.set(folder if len(folder) <= 42 else '…' + folder[-41:])
        self.size.set(f'{os.path.getsize(session.path) / 1048576:.1f} MB')
        self.open_button.config(text='Change ROM', style='Soft.TButton')
        self.status.config(text='')
