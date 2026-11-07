"""Keyboard tab: the order of the tabs of the on-screen keyboard and the characters of their keys."""
import tkinter as tk
from tkinter import ttk

from ....features.keyboard import KEYBOARDS, keyboard_config, kb_pixels, text_problem
from ...glyphs import Glyphs
from ...theme import DARK, MUTED, ORANGE
from ...widgets import RevertButton
from ..base import Tab
from .editor import KeyboardEditor


class KeyboardTab(Tab):
    key = 'keyboard'
    title = 'Keyboard'
    heading = 'Keyboard'

    def build(self):
        self.order = list(KEYBOARDS)
        self.layouts = {}               # {keyboard: {layer: characters}} of the layers whose keys type something else than in the ROM
        self.icons = {}
        self.pictures = None            # the pictures of the characters (made when the first keyboard is opened)
        self.dialog = None              # the settings window of a keyboard, while there is one
        self.revert_button = RevertButton(self, self.revert_all)
        self.revert_button.pack(side='bottom', anchor='e', pady=(10, 0))       # packed first: it keeps its place at the bottom
        self.rows = ttk.Frame(self)
        self.rows.pack(anchor='w')
        self.note = ttk.Label(self, foreground=MUTED, wraplength=520, justify='left')
        self.note.pack(anchor='w', pady=(8, 0))

    # ----- the ROM

    def on_rom(self):
        self.order, self.layouts, self.pictures = list(KEYBOARDS), {}, None
        if self.dialog is not None:
            self.dialog.destroy()
            self.dialog = None
        self.icons = {}
        for name, rows in kb_pixels(self.session.data).items():
            img = tk.PhotoImage(master=self, width=16, height=16)
            for y, row in enumerate(rows):
                img.put('{' + ' '.join(c or ORANGE for c in row) + '}', to=(0, y))
            self.icons[name] = img.zoom(3)
        self.draw()

    def boards(self):
        """{name: Keyboard} as the ROM has them (None when this ROM does not keep them where the toolkit looks)."""
        return self.session.keyboards()

    def characters_of(self, name):
        """{layer: characters} of a keyboard as it is now: the ROM's keys with the changes made here."""
        board = self.boards()[name]
        return {layer: self.layouts.get(name, {}).get(layer, board.text[layer]) for layer, _ in board.layers}

    # ----- the list

    def draw(self):
        for w in self.rows.winfo_children():
            w.destroy()
        if not self.icons:
            return
        boards = self.boards()
        for i, name in enumerate(self.order):
            row = ttk.Frame(self.rows)
            row.pack(fill='x', pady=2)
            holder = tk.Frame(row, width=54, height=54, bg=ORANGE)
            holder.pack_propagate(False)
            holder.pack(side='left')
            tk.Label(holder, image=self.icons[name], bg=ORANGE, bd=0).place(relx=0.5, rely=0.5, anchor='center')
            ttk.Label(row, text=('● ' if name in self.layouts else '') + name, width=12, foreground=DARK if name in self.layouts else None).pack(side='left', padx=10)
            ttk.Button(row, text='▲', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, -1)).pack(side='left', padx=(0, 4))
            ttk.Button(row, text='▼', width=3, style='Soft.TButton', command=lambda i=i: self.move(i, 1)).pack(side='left', padx=(0, 10))
            settings = ttk.Button(row, text='Keys', style='Soft.TButton', command=lambda n=name: self.settings(n))
            settings.pack(side='left')
            if boards is None:
                settings.state(['disabled'])
        self.note.configure(text='' if boards is not None else 'The keys of this ROM cannot be read.')

    def move(self, i, step):
        j = i + step
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self.draw()
            self.changed()

    # ----- the settings of a keyboard

    def glyphs(self):
        """The pictures of the characters of the game (the font of its keys)."""
        if self.pictures is None:
            self.pictures = Glyphs(self, self.session.characters().font)
        return self.pictures

    def settings(self, name):
        """Opens the window that changes the keys of a keyboard (one at a time)."""
        if self.boards() is None:
            return None
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return self.dialog
        self.dialog = KeyboardEditor(self.winfo_toplevel(), self.boards()[name], self.characters_of(name), self.glyphs(),
                                     self.session.characters(), lambda layers: self.keep_layers(name, layers))
        return self.dialog

    def keep_layers(self, name, layers):
        """The keys of a keyboard now type `layers` ({layer: characters}, only those that differ from the ROM)."""
        if layers:
            self.layouts[name] = dict(layers)
        else:
            self.layouts.pop(name, None)
        self.draw()
        self.changed()

    def revert_all(self):
        self.order, self.layouts = list(KEYBOARDS), {}
        self.draw()
        self.changed()

    def changed(self):
        super().changed()
        self.revert_button.show(self.order != KEYBOARDS or bool(self.layouts))

    # ----- patch and project

    def patch_config(self):
        cfg = {}
        if self.order != KEYBOARDS:
            cfg['order'] = list(self.order)
        if self.layouts:
            cfg['layouts'] = {name: dict(layers) for name, layers in self.layouts.items()}
        return cfg or None

    def project_part(self):
        return {'order': list(self.order), 'layouts': {name: dict(layers) for name, layers in self.layouts.items()}}

    def restore(self, part):
        order, layouts = keyboard_config(part)
        self.order = list(order) if order else list(KEYBOARDS)
        self.layouts = {}
        notes = []
        boards = self.boards()
        if layouts and boards is None:
            notes.append('The keys of the keyboards were not restored: this ROM does not keep them where the toolkit looks.')
        elif layouts:
            characters = self.session.characters()
            for name, layers in layouts.items():
                board, keep = boards[name], {}
                for layer, text in layers.items():
                    problem = text_problem(board.size, text, characters.has)
                    if problem:
                        notes.append(f'Keyboard {name}, {board.label(layer)}: {problem}. Skipped.')
                    elif text != board.text[layer]:
                        keep[layer] = text
                if keep:
                    self.layouts[name] = keep
        self.draw()
        return notes

    def summary(self):
        text = 'Default order' if self.order == KEYBOARDS else '  ›  '.join(self.order)
        if self.layouts:
            text += '; keys changed: ' + ', '.join(name for name in KEYBOARDS if name in self.layouts)
        return text
