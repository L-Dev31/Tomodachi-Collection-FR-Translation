"""Fonts tab: the fonts of the game, their glyphs and the pictures of the glyphs.

A glyph is looked at in a grid, and changed pixel by pixel in the editor: its picture is written in its own cell, the size of the font
does not change. Last, on the tab, characters that the messages and the keys fonts lack are added from a TrueType font; they are then
accepted by the Keyboard, the Text and the Voice tabs."""
import tkinter as tk
import unicodedata
from tkinter import ttk

from ...core.nftr import Font
from ...features.fonts.grow import ALL_FONTS, FONT_FILES, apply_changes, default_ttf, font_bytes, installed_fonts, render_rows, ttf_draws
from ...features.keyboard.charset import load_font
from ..theme import BROWN, CANVAS, MUTED, SAND
from ..widgets import RevertButton
from .base import Tab

BLOCKS = (('Cyrillic', 0x400, 0x4FF), ('Greek', 0x370, 0x3FF), ('Latin Extended-A', 0x100, 0x17F))
LANGUAGES = (('Turkish letters', 'şŞğĞıİ'), ('Polish letters', 'ąĄęĘśŚłŁżŻźŹćĆńŃ'))     # the letters a keyboard layout of the language needs
MESSAGES, KEYS = FONT_FILES
NAMES = {MESSAGES: 'Messages', KEYS: 'Keys', '/Cmn/Font/FontLD08x_LZ.bin': 'Small'}
GRID_COLS, GRID_ROWS, GRID_SCALE, EDIT_SCALE, PREVIEW = 16, 8, 2, 14, 8
PER_PAGE = GRID_COLS * GRID_ROWS
NO_FONT = 'No base font'                      # the letters are then empty cells
CHANGED = '#FFE3B8'                             # the background of a glyph that was changed


class FontsTab(Tab):
    key = 'fonts'
    title = 'Fonts'
    heading = 'Fonts'

    def build(self):
        self.changes = {}                       # {font file: {code: rows}}: glyphs changed in place, or characters added
        self.originals, self.shown = {}, {}     # the Font of the ROM, and the Font with the changes, per font file
        self.current, self.page, self.code = MESSAGES, 0, None
        self.work, self.paint, self.visible, self.cell = None, None, [], (1, 1)
        self.chars = tk.StringVar()
        self.fonts_found = installed_fonts()
        default = next((name for name, path in self.fonts_found.items() if path == default_ttf()), NO_FONT)
        self.base = tk.StringVar(value=default)
        self.note = tk.StringVar()
        self.search = tk.StringVar()
        self.page_text, self.where = tk.StringVar(), tk.StringVar()
        self.revert_button = RevertButton(self, self.revert)
        self.revert_button.pack(side='bottom', anchor='e', pady=(10, 0))       # packed first: it keeps its place at the bottom
        ttk.Label(self, foreground=MUTED, text='Click a glyph, then change its pixels.').pack(anchor='w')
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, pady=(10, 0))
        self.fonts_list = ttk.Treeview(main, columns=('size', 'glyphs', 'changed'), show='tree headings', selectmode='browse', height=3)
        self.fonts_list.heading('#0', text='Font')
        self.fonts_list.heading('size', text='Size')
        self.fonts_list.heading('glyphs', text='Glyphs')
        self.fonts_list.heading('changed', text='Changed')
        self.fonts_list.column('#0', width=110)
        self.fonts_list.column('size', width=70, anchor='e')
        self.fonts_list.column('glyphs', width=60, anchor='e')
        self.fonts_list.column('changed', width=150)
        self.fonts_list.pack(side='left', fill='y')
        self.fonts_list.bind('<<TreeviewSelect>>', self.choose_font)
        right = ttk.Frame(main)
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))
        nav = ttk.Frame(right)
        nav.pack(fill='x')
        ttk.Button(nav, text='◀', style='Mini.TButton', width=3, command=lambda: self.turn(-1)).pack(side='left')
        ttk.Button(nav, text='▶', style='Mini.TButton', width=3, command=lambda: self.turn(1)).pack(side='left', padx=(4, 0))
        ttk.Label(nav, textvariable=self.page_text, foreground=MUTED).pack(side='left', padx=8)
        search = ttk.Entry(nav, textvariable=self.search, width=14)
        search.pack(side='right')
        search.bind('<Return>', lambda e: self.goto())
        ttk.Label(nav, text='Find a character or its code (U+XXXX)', foreground=MUTED).pack(side='right', padx=6)
        self.grid_canvas = tk.Canvas(right, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, width=400, height=200)
        self.grid_canvas.pack(anchor='w', pady=(8, 0))
        self.grid_canvas.bind('<ButtonPress-1>', self.pick_glyph)
        bottom = ttk.Frame(right)
        bottom.pack(fill='x', pady=(8, 0))
        self.editor = tk.Canvas(bottom, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, width=200, height=200)
        self.editor.pack(side='left', anchor='n')
        self.editor.bind('<ButtonPress-1>', self.paint_start)
        self.editor.bind('<B1-Motion>', self.paint_move)
        self.editor.bind('<ButtonRelease-1>', self.paint_end)
        side = ttk.Frame(bottom)
        side.pack(side='left', anchor='n', padx=(12, 0))
        ttk.Label(side, textvariable=self.where, foreground=BROWN, wraplength=260, justify='left').pack(anchor='w')
        ttk.Button(side, text='Revert glyph', style='Mini.TButton', command=self.revert_glyph).pack(anchor='w', pady=(8, 0))
        # the characters that the fonts lack: the last part of the tab
        add = ttk.Labelframe(self, text='Add letters (last)', padding=10)
        add.pack(fill='x', pady=(12, 0))
        row = ttk.Frame(add)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.chars, width=34).pack(side='left')
        for name, lo, hi in BLOCKS:
            ttk.Button(row, text=f'+ {name}', style='Mini.TButton', command=lambda lo=lo, hi=hi: self.fill_block(lo, hi)).pack(side='left', padx=(6, 0))
        for name, letters in LANGUAGES:
            ttk.Button(row, text=f'+ {name}', style='Mini.TButton', command=lambda letters=letters: self.fill_chars(letters)).pack(side='left', padx=(6, 0))
        src = ttk.Frame(add)
        src.pack(fill='x', pady=(8, 0))
        ttk.Label(src, text='Base font').pack(side='left')
        self.base_box = ttk.Combobox(src, textvariable=self.base, state='readonly', width=40, values=[NO_FONT] + list(self.fonts_found))
        self.base_box.pack(side='left', padx=6)
        ttk.Button(add, text='Add', style='MiniAccent.TButton', command=self.add_chars).pack(anchor='e', pady=(8, 0))
        ttk.Label(self, textvariable=self.note, foreground=MUTED, wraplength=760, justify='left').pack(anchor='w', pady=(8, 0))
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True, pady=(8, 0))
        self.tree = ttk.Treeview(body, columns=('code', 'name'), show='headings', selectmode='browse', height=6)
        self.tree.heading('code', text='Code')
        self.tree.heading('name', text='Character')
        self.tree.column('code', width=90)
        self.tree.column('name', width=320)
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.show_picture())
        side = ttk.Frame(body)
        side.pack(side='right', fill='y', padx=(10, 0))
        self.picture = tk.Canvas(side, bg=CANVAS, width=12 * PREVIEW, height=20 * PREVIEW, highlightthickness=1, highlightbackground=SAND)
        self.picture.pack()
        self.preview_text = tk.StringVar()
        ttk.Label(side, textvariable=self.preview_text, foreground=BROWN).pack(pady=(6, 0))
        ttk.Button(side, text='Remove', style='Mini.TButton', command=self.remove).pack(pady=(8, 0))
        self.refresh()
        self.redraw()

    # ----- the fonts of the ROM

    def original(self, path):
        if path not in self.originals:
            self.originals[path] = load_font(self.session.rom, path)
        return self.originals[path]

    def shown_font(self, path):
        """The font as it will be patched: the ROM's, with the changes made on the tab."""
        if path not in self.shown:
            glyphs = self.changes.get(path)
            self.shown[path] = Font(apply_changes(font_bytes(self.session.rom, path), glyphs)) if glyphs else self.original(path)
        return self.shown[path]

    def on_rom(self):
        self.changes, self.originals, self.shown = {}, {}, {}
        self.current, self.page, self.code, self.work = MESSAGES, 0, None, None
        self.note.set('')
        self.refresh()
        self.redraw()

    def push(self):
        """Makes the changes visible to the other tabs now (the ROM itself changes at the patch)."""
        self.shown = {}
        if self.session is not None:
            self.session.set_font_changes(self.changes)

    def cleanup(self):
        for path in list(self.changes):
            if not self.changes[path]:
                del self.changes[path]

    def changed_font(self):
        """Some change is made: the font is shown again and everything that depends on it is refreshed."""
        self.cleanup()
        self.push()
        self.refresh()
        self.redraw()
        self.changed()

    def added_codes(self):
        return sorted({code for path in (MESSAGES, KEYS) for code in self.changes.get(path, {}) if code not in self.original(path).codes})

    # ----- the grid of glyphs

    def choose_font(self, event=None):
        sel = self.fonts_list.selection()
        if sel and sel[0] != self.current:
            self.current, self.page, self.code, self.work = sel[0], 0, None, None
            self.redraw()

    def turn(self, step):
        self.page = max(0, self.page + step)
        self.redraw()

    def redraw(self):
        if self.session is None:
            return
        font = self.shown_font(self.current)
        codes = sorted(font.codes)
        pages = max(1, -(-len(codes) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        self.page_text.set(f'page {self.page + 1} of {pages}   ({len(codes)} glyphs)')
        self.visible = codes[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        cw, ch = font.width * GRID_SCALE + 8, font.height * GRID_SCALE + 8
        self.cell = (cw, ch)
        c = self.grid_canvas
        c.delete('all')
        c.configure(width=GRID_COLS * cw + 1, height=GRID_ROWS * ch + 1)
        changed = self.changes.get(self.current, {})
        for i, code in enumerate(self.visible):
            x0, y0 = (i % GRID_COLS) * cw, (i // GRID_COLS) * ch
            if code in changed:
                c.create_rectangle(x0 + 1, y0 + 1, x0 + cw - 1, y0 + ch - 1, fill=CHANGED, outline='')
            if code == self.code:
                c.create_rectangle(x0 + 1, y0 + 1, x0 + cw - 1, y0 + ch - 1, outline=BROWN, width=2)
            for y, row in enumerate(font.glyph(code) or []):
                for x, px in enumerate(row):
                    if px:
                        c.create_rectangle(x0 + 4 + x * GRID_SCALE, y0 + 4 + y * GRID_SCALE, x0 + 4 + (x + 1) * GRID_SCALE,
                                           y0 + 4 + (y + 1) * GRID_SCALE, fill=BROWN, outline='')
        self.redraw_editor()

    def pick_glyph(self, event):
        cw, ch = self.cell
        i = (event.y // ch) * GRID_COLS + event.x // cw
        if 0 <= i < len(self.visible) and event.x < GRID_COLS * cw and event.y < GRID_ROWS * ch:
            self.select(self.visible[i])

    def select(self, code):
        self.code, self.work = code, None
        self.redraw()

    def goto(self):
        """Finds a character (typed) or a code (U+XXXX or four hex digits) in the font on show."""
        text = self.search.get().strip()
        code = None
        if len(text) == 1:
            code = ord(text)
        else:
            try:
                code = int(text[2:] if text[:2].upper() == 'U+' else text, 16)
            except ValueError:
                code = None
        font = self.shown_font(self.current)
        if code is None or code not in font.codes:
            self.note.set(f'{self.search.get()!r} is not a glyph of this font.')
            return
        self.page = sorted(font.codes).index(code) // PER_PAGE
        self.select(code)

    # ----- the editor

    def cell_at(self, event):
        if self.code is None:
            return None
        font = self.shown_font(self.current)
        x, y = event.x // EDIT_SCALE, event.y // EDIT_SCALE
        return (x, y) if 0 <= x < font.width and 0 <= y < font.height else None

    def redraw_editor(self):
        c = self.editor
        c.delete('all')
        if self.code is None:
            self.where.set('Click a glyph to look at it.')
            c.configure(width=200, height=200)
            return
        font = self.shown_font(self.current)
        rows = self.work if self.work is not None else (font.glyph(self.code) or [])
        c.configure(width=font.width * EDIT_SCALE + 1, height=font.height * EDIT_SCALE + 1)
        for y, row in enumerate(rows):
            for x, px in enumerate(row):
                c.create_rectangle(x * EDIT_SCALE, y * EDIT_SCALE, (x + 1) * EDIT_SCALE, (y + 1) * EDIT_SCALE,
                                   fill=BROWN if px else CANVAS, outline=SAND)
        ch = chr(self.code)
        name = unicodedata.name(ch, '').title() or 'Character'
        self.where.set(f'{ch if ch.isprintable() else ""}   U+{self.code:04X}\n{name}')

    def paint_start(self, event):
        if self.code is None:
            return
        font = self.shown_font(self.current)
        self.work = [list(r) for r in (font.glyph(self.code) or [])]
        p = self.cell_at(event)
        if p is None:
            self.work = None
            return
        self.paint = 0 if self.work[p[1]][p[0]] else 1
        self.work[p[1]][p[0]] = self.paint
        self.redraw_editor()

    def paint_move(self, event):
        p = self.cell_at(event)
        if p is None or self.work is None or self.paint is None:
            return
        self.work[p[1]][p[0]] = self.paint
        self.redraw_editor()

    def paint_end(self, event):
        if self.work is None or self.code is None:
            return
        font = self.shown_font(self.current)
        work, self.work, self.paint = self.work, None, None
        if work != (font.glyph(self.code) or []):
            self.changes.setdefault(self.current, {})[self.code] = work
            self.changed_font()
        else:
            self.redraw_editor()

    def revert_glyph(self):
        if self.code is not None and self.code in self.changes.get(self.current, {}):
            del self.changes[self.current][self.code]
            self.work = None
            self.changed_font()

    # ----- adding characters (the last part of the tab)

    def fill_block(self, lo, hi):
        """Fills the box with the letters of a block that no font draws yet (the list is then added with the Add button)."""
        self.fill_chars(''.join(chr(c) for c in range(lo, hi + 1) if unicodedata.category(chr(c))[0] == 'L'))

    def fill_chars(self, chars):
        """Fills the box with the characters of `chars` that no font draws yet."""
        if self.session is None:
            return
        letters = [ch for ch in dict.fromkeys(chars) if not all(self.original(p).has(ch) for p in (MESSAGES, KEYS))
                   and ord(ch) not in self.added_codes()]
        self.chars.set(''.join(letters))
        self.note.set(f'{len(letters)} letter(s) to add; press Add.' if letters else 'Every letter of these is drawn already.')

    def add_chars(self):
        if self.session is None:
            return
        text = ''.join(dict.fromkeys(ch for ch in self.chars.get() if not ch.isspace()))
        base = self.base.get()
        ttf_file = self.fonts_found.get(base)
        if ttf_file is None and base != NO_FONT:
            self.note.set('Choose a base font, or no base font for empty cells.')
            return
        drawn = [ch for ch in text if all(self.original(p).has(ch) for p in (MESSAGES, KEYS))]
        before = {p: dict(g) for p, g in self.changes.items()}
        missing, added = [], []
        for path in (MESSAGES, KEYS):
            font = self.original(path)
            glyphs = self.changes.setdefault(path, {})
            for ch in text:
                if font.has(ch) or ord(ch) in glyphs:
                    continue
                if ttf_file is None:
                    glyphs[ord(ch)] = [[0] * font.width for _ in range(font.height)]
                    if ch not in added:
                        added.append(ch)
                    continue
                if not ttf_draws(ch, ttf_file):
                    if ch not in missing:
                        missing.append(ch)
                    continue
                glyphs[ord(ch)] = render_rows(ch, font.width, font.height, ttf_file)
                if ch not in added:
                    added.append(ch)
        self.cleanup()
        try:
            self.push()
        except ValueError as e:
            self.changes = before
            self.push()
            self.note.set(f'The characters cannot be added: {e}')
            return
        parts = []
        if added:
            parts.append(f'{len(added)} character(s) added: {"".join(added)}')
        if drawn:
            parts.append(f'already drawn by the game: {"".join(drawn)}')
        if missing:
            parts.append(f'{base} has no picture for: {"".join(missing)}')
        self.note.set('. '.join(parts) + ('.' if parts else 'Nothing to add.'))
        self.refresh()
        self.redraw()
        self.changed()

    def remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        code = int(sel[0])
        for glyphs in self.changes.values():
            glyphs.pop(code, None)
        self.changed_font()

    def revert(self):
        self.changes = {}
        self.code, self.work = None, None
        self.note.set('')
        self.changed_font()

    # ----- what is on show

    def refresh(self):
        if self.session is None:
            return
        self.fonts_list.delete(*self.fonts_list.get_children())
        for path in ALL_FONTS:
            font = self.original(path)
            glyphs = self.changes.get(path, {})
            edited = sum(1 for c in glyphs if c in font.codes)
            added = sum(1 for c in glyphs if c not in font.codes)
            parts = [f'{edited} edited'] if edited else []
            parts += [f'{added} added'] if added else []
            self.fonts_list.insert('', 'end', iid=path, text=NAMES.get(path, path),
                                   values=(f'{font.width} x {font.height}', font.glyph_count, ', '.join(parts)))
        if self.current in ALL_FONTS:
            self.fonts_list.selection_set(self.current)
        self.tree.delete(*self.tree.get_children())
        for code in self.added_codes():
            self.tree.insert('', 'end', iid=str(code), values=(f'U+{code:04X}', unicodedata.name(chr(code), '').title() or chr(code)))
        self.revert_button.show(bool(self.changes))
        self.show_picture()

    def show_picture(self):
        self.picture.delete('all')
        sel = self.tree.selection()
        if not sel:
            self.preview_text.set('')
            return
        code = int(sel[0])
        rows = next((g[code] for g in self.changes.values() if code in g), None)
        self.preview_text.set(f'{chr(code)}   U+{code:04X}')
        for y, row in enumerate(rows or []):
            for x, px in enumerate(row):
                if px:
                    self.picture.create_rectangle(x * PREVIEW + 6, y * PREVIEW + 6, (x + 1) * PREVIEW + 6, (y + 1) * PREVIEW + 6,
                                                  fill=BROWN, outline='')

    # ----- patch and project

    def patch_config(self):
        return {p: {code: rows for code, rows in glyphs.items()} for p, glyphs in self.changes.items() if glyphs} or None

    def project_part(self):
        return {p: {str(code): [''.join('1' if px else '0' for px in row) for row in rows] for code, rows in glyphs.items()}
                for p, glyphs in self.changes.items() if glyphs}

    def restore(self, part):
        notes = []
        self.changes = {}
        for path, glyphs in part.items():
            if path not in ALL_FONTS:
                notes.append(f'Font {path} is not one of the fonts of the game: skipped.')
                continue
            for code, rows in glyphs.items():
                self.changes.setdefault(path, {})[int(code)] = [[1 if ch == '1' else 0 for ch in row] for row in rows]
        self.push()
        self.refresh()
        self.redraw()
        return notes

    def summary(self):
        added = len(self.added_codes())
        edited = sum(1 for p, glyphs in self.changes.items() for c in glyphs if c in self.original(p).codes)
        parts = ([f'{added} character(s) added'] if added else []) + ([f'{edited} glyph(s) edited'] if edited else [])
        return ', '.join(parts) if parts else 'Unchanged'
