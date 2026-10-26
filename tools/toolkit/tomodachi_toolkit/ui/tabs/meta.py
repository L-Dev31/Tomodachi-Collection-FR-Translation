"""Meta tab: the banner of the game (icon, title in six languages) and the internal name."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.binary import u32
from ...features.meta import LANGS, REQUIREMENTS, banner_read, fit32, icon_grid, quantize
from ..theme import BROWN, MUTED, PANEL, SAND, font
from ..widgets import caption, card
from .base import Tab


class MetaTab(Tab):
    key = 'meta'
    title = 'Meta'
    heading = 'Meta'

    def build(self):
        self.lang = tk.StringVar(value='English')
        self.internal = tk.StringVar()
        self.current = 'English'
        self.titles, self.orig_titles, self.orig_internal, self.orig_icon, self.icon_new = {}, {}, '', None, None
        box = card(self)
        box.pack(fill='x')
        self.badge = tk.Label(box, bg=PANEL, bd=0)
        self.badge.grid(row=0, column=0, rowspan=2, sticky='n')
        ttk.Button(box, text='Change icon', style='Accent.TButton', command=self.change_icon).grid(row=0, column=1, padx=16, sticky='w')
        ttk.Button(box, text='Reset icon', style='Soft.TButton', command=self.reset_icon).grid(row=1, column=1, padx=16, pady=(6, 0), sticky='w')
        tk.Label(box, text=REQUIREMENTS, bg=PANEL, fg=MUTED, font=font(8), justify='left').grid(row=0, column=2, rowspan=2, sticky='w')
        title = card(self, pady=12)
        title.pack(fill='x', pady=(12, 0))
        caption(title, 'GAME TITLE', row=0, column=0, sticky='w')
        lang_box = ttk.Combobox(title, textvariable=self.lang, values=LANGS, state='readonly', width=10)
        lang_box.grid(row=0, column=1, sticky='e')
        lang_box.bind('<<ComboboxSelected>>', lambda e: self.show_title())
        self.text = tk.Text(title, height=3, width=40, wrap='none', bg='#FFFDF8', fg=BROWN, relief='flat', highlightthickness=1,
                            highlightbackground=SAND, font=font(10), padx=8, pady=6)
        self.text.grid(row=1, column=0, columnspan=2, pady=(8, 0))
        self.text.bind('<KeyRelease>', lambda e: self.changed())
        ttk.Button(title, text='Apply to all languages', style='Soft.TButton', command=self.apply_all).grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        caption(title, 'INTERNAL NAME (12 CHARACTERS)', row=3, column=0, columnspan=2, sticky='w', pady=(12, 0))
        ttk.Entry(title, textvariable=self.internal, width=18).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
        self.internal.trace_add('write', lambda *_: self.changed())

    def on_rom(self):
        data = self.session.data
        b = u32(data, 0x68)
        self.titles, name = banner_read(data)
        self.orig_titles = dict(self.titles)
        self.orig_internal = name
        self.orig_icon = (bytes(data[b + 0x20:b + 0x220]), bytes(data[b + 0x220:b + 0x240]))
        self.icon_new = None
        self.current = self.lang.get()
        self.text.delete('1.0', 'end')
        self.text.insert('end', self.titles[self.current])
        self.internal.set(name)
        self.draw_icon(self.orig_icon)

    def keep_title(self):
        if self.titles:
            self.titles[self.current] = self.text.get('1.0', 'end-1c')

    def apply_all(self):
        self.keep_title()
        for n in LANGS:
            self.titles[n] = self.titles[self.current]
        self.changed()

    def show_title(self):
        self.keep_title()
        self.current = self.lang.get()
        self.text.delete('1.0', 'end')
        self.text.insert('end', self.titles.get(self.current, ''))

    def draw_icon(self, icon):
        img = tk.PhotoImage(master=self, width=32, height=32)
        for y, row in enumerate(icon_grid(*icon)):
            img.put('{' + ' '.join(c or PANEL for c in row) + '}', to=(0, y))
        self.icon_image = img.zoom(2)
        self.badge.config(image=self.icon_image)

    def read_pixels(self, path):
        img = tk.PhotoImage(master=self, file=path)
        k = (max(img.width(), img.height()) + 31) // 32
        if k > 1:
            img = img.subsample(k)
        w, h = img.width(), img.height()
        pixels = [(*img.get(x, y), 0 if img.transparency_get(x, y) else 255) for y in range(h) for x in range(w)]
        return fit32(w, h, pixels)

    def change_icon(self):
        path = filedialog.askopenfilename(filetypes=[('Image', '*.png *.gif')])
        if not path:
            return
        try:
            icon = quantize(self.read_pixels(path))
        except Exception as e:
            messagebox.showerror('Icon', str(e))
            return
        self.icon_new = icon
        self.draw_icon(icon)
        self.changed()

    def reset_icon(self):
        self.icon_new = None
        if self.orig_icon:
            self.draw_icon(self.orig_icon)
        self.changed()

    def patch_config(self):
        if self.session is None:
            return None
        self.keep_title()
        cfg = {}
        titles = {n: t for n, t in self.titles.items() if t != self.orig_titles[n]}
        if titles:
            cfg['titles'] = titles
        if self.icon_new:
            cfg['icon'] = self.icon_new
        name = self.internal.get().strip()
        if name != self.orig_internal:
            if len(name) > 12 or not name.isascii():
                raise ValueError('Internal name: 12 ASCII characters max.')
            cfg['internal'] = name
        return cfg or None

    def project_part(self):
        return self.patch_config() or {}

    def restore(self, part):
        self.titles = dict(self.orig_titles)
        self.titles.update(part.get('titles', {}))
        self.text.delete('1.0', 'end')
        self.text.insert('end', self.titles[self.current])
        self.internal.set(part.get('internal', self.orig_internal))
        self.icon_new = part.get('icon')
        self.draw_icon(self.icon_new or self.orig_icon)
        return []

    def summary(self):
        if self.session is None:
            return 'Unchanged'
        try:
            names = {'titles': 'Title', 'icon': 'Icon', 'internal': 'Name'}
            return ', '.join(names[k] for k in (self.patch_config() or {})) or 'Unchanged'
        except ValueError as e:
            return str(e)
