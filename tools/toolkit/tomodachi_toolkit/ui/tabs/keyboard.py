"""Keyboard tab: order of the tabs of the on-screen keyboard."""
import tkinter as tk
from tkinter import ttk

from ...features.keyboard import KEYBOARDS, kb_pixels
from ..theme import ORANGE
from .base import Tab


class KeyboardTab(Tab):
    key = 'keyboard'
    title = 'Keyboard'
    heading = 'Keyboard'

    def build(self):
        self.order = list(KEYBOARDS)
        self.icons = {}
        box = ttk.Labelframe(self, text='Tab order, top to bottom', padding=12)
        box.pack(fill='x', pady=(10, 0))
        self.rows = ttk.Frame(box)
        self.rows.pack(anchor='w')
        ttk.Button(box, text='Reset order', style='Soft.TButton', command=self.reset_order).pack(anchor='w', pady=(8, 0))

    def on_rom(self):
        self.icons = {}
        for name, rows in kb_pixels(self.session.data).items():
            img = tk.PhotoImage(master=self, width=16, height=16)
            for y, row in enumerate(rows):
                img.put('{' + ' '.join(c or ORANGE for c in row) + '}', to=(0, y))
            self.icons[name] = img.zoom(3)
        self.draw()

    def draw(self):
        for w in self.rows.winfo_children():
            w.destroy()
        if not self.icons:
            return
        for i, name in enumerate(self.order):
            row = ttk.Frame(self.rows)
            row.pack(fill='x', pady=2)
            holder = tk.Frame(row, width=54, height=54, bg=ORANGE)
            holder.pack_propagate(False)
            holder.pack(side='left')
            tk.Label(holder, image=self.icons[name], bg=ORANGE, bd=0).place(relx=0.5, rely=0.5, anchor='center')
            ttk.Label(row, text=name, width=12).pack(side='left', padx=10)
            ttk.Button(row, text='▲', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, -1)).pack(side='left', padx=(0, 4))
            ttk.Button(row, text='▼', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, 1)).pack(side='left')

    def move(self, i, step):
        j = i + step
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self.draw()
            self.changed()

    def reset_order(self):
        self.order = list(KEYBOARDS)
        self.draw()
        self.changed()

    def patch_config(self):
        return list(self.order) if self.order != KEYBOARDS else None

    def project_part(self):
        return list(self.order)

    def restore(self, part):
        self.order = list(part)
        self.draw()
        return []

    def summary(self):
        return 'Default order' if self.order == KEYBOARDS else '  ›  '.join(self.order)
