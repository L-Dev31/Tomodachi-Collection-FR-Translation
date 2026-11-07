"""Text tab: the message files of the game (the text of the dialogs), made to be edited. Left, the files. Right, the messages of the selected
file, and under them the message as the ROM has it next to the message as it will be (typed there, kept at once). A right click on a file
takes it out or puts another one in its place; a right click on a message copies it or takes it back."""
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.bmg import BmgFile, bmg_problems
from ...features.bmg import bmg_list
from ..theme import BG, BROWN, DARK, ERROR, MUTED, PANEL, SAND, font
from ..widgets import RIGHT, copy_text, popup, tree_with_scrollbar
from .listing import ListingTab

CODE = re.compile(r'(?<!\{)\{[0-9a-fA-F]+\}(?!\})')         # a game code inside a text


def one_line(text):
    """A message for a list: the codes as ◇ and the line breaks as arrows."""
    return CODE.sub('◇', text).replace('\r', '').replace('\n', ' ↵ ')[:300]


class BmgTab(ListingTab):
    key = 'bmg'
    title = 'Text'
    heading = 'Text'

    def build(self):
        self.files, self.new, self.sel, self.cache = {}, {}, None, {}     # files: {path: (name, problems)}; new: {path: (name, bytes)} the changed ones
        self.rom_files, self.counts = {}, {}                              # the message files of the ROM, and how many messages each has
        self.rom = self.bmg = self.row = None                             # the file on show as the ROM has it and as it will be; the message selected
        self.longest, self.loading = 0, False
        right = self.build_listing(weights=(2, 5), batch=(self.export_all, self.import_all, self.revert_all), show='tree headings', columns=('count', 'state'))
        self.tree.heading('#0', text='Message file')
        self.tree.heading('count', text='Messages')
        self.tree.heading('state', text='State')
        self.tree.column('#0', width=190)
        self.tree.column('count', width=60, anchor='e', stretch=False)
        self.tree.column('state', width=110)
        self.tree.tag_configure('bad', foreground=ERROR)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.build_menu(self.entries)
        self.note = ttk.Label(right, foreground=ERROR, wraplength=620, justify='left')       # why the file cannot be read, when it cannot
        self.split = ttk.Panedwindow(right, orient='vertical')
        self.split.pack(fill='both', expand=True)
        top, bottom = ttk.Frame(self.split), ttk.Frame(self.split)
        self.split.add(top, weight=3)
        self.split.add(bottom, weight=2)
        self.messages = tree_with_scrollbar(top, show='headings', columns=('num', 'id', 'text'), selectmode='browse', height=10)
        for column, text, width, anchor in (('num', '#', 56, 'e'), ('id', 'ID', 70, 'e'), ('text', 'Message', 480, 'w')):
            self.messages.heading(column, text=text)
            self.messages.column(column, width=width, anchor=anchor, stretch=column == 'text')
        self.messages.bind('<<TreeviewSelect>>', self.pick_message)
        self.messages.bind(RIGHT, self.message_menu)
        self.messages.bind('<Return>', lambda e: self.box.focus_set())
        panes = ttk.Panedwindow(bottom, orient='horizontal')
        panes.pack(fill='both', expand=True)
        old, new = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(old, weight=1)
        panes.add(new, weight=1)
        ttk.Label(old, text='ROM', foreground=MUTED).pack(anchor='w')
        self.original = self.text_box(old, False)
        ttk.Label(new, text='Text', foreground=DARK).pack(anchor='w')
        self.box = self.text_box(new, True)
        self.box.bind('<<Modified>>', self.typed)
        self.box.bind('<Control-Down>', lambda e: self.step(1))
        self.box.bind('<Control-Up>', lambda e: self.step(-1))
        self.box.bind(RIGHT, lambda e: popup(self.box, e, [('Restore the ROM text', self.revert_message if self.row is not None else None)]))
        line = ttk.Frame(bottom)
        line.pack(fill='x', pady=(4, 0))
        self.status, self.problem = tk.StringVar(), tk.StringVar()
        ttk.Label(line, textvariable=self.status, foreground=MUTED).pack(side='left')
        ttk.Label(line, textvariable=self.problem, foreground=ERROR).pack(side='left', padx=12)

    def text_box(self, parent, editable):
        """A text with its scroll bar; the game codes in it are marked."""
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        box = tk.Text(frame, height=6, width=20, wrap='word', undo=editable, font=font(11), bg=PANEL if editable else BG, fg=DARK if editable else BROWN,
                      insertbackground=DARK, relief='flat', highlightthickness=1, highlightbackground=SAND, padx=6, pady=4,
                      state='normal' if editable else 'disabled')
        bar = ttk.Scrollbar(frame, orient='vertical', command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        box.tag_configure('code', background=SAND, foreground=BROWN)
        return box

    def write(self, box, text):
        """Puts a text in a box (the game codes marked)."""
        box.configure(state='normal')
        box.delete('1.0', 'end')
        box.insert('1.0', text)
        for m in CODE.finditer(text):
            box.tag_add('code', f'1.0+{m.start()}c', f'1.0+{m.end()}c')
        if box is self.box:
            box.edit_reset()
            box.edit_modified(False)
        else:
            box.configure(state='disabled')

    # ----- the files

    def on_rom(self):
        self.new, self.sel, self.cache, self.counts = {}, None, {}, {}
        self.files = bmg_list(self.session.rom)
        self.rom_files = {p: self.session.subfiles(p)[0] for p in self.files}
        for p, data in self.rom_files.items():
            try:
                self.counts[p] = BmgFile(data).count
            except ValueError:
                self.counts[p] = 0
        self.show_file()
        self.fill()

    def message_file(self, path):
        """The message file as it will be patched: the changed one, else the one of the ROM."""
        return self.new[path][1] if path in self.new else self.rom_files[path]

    def texts_of(self, path):
        """The messages of a file in lower case, to search them."""
        data = self.message_file(path)
        hit = self.cache.get(path)
        if hit is None or hit[0] != data:
            try:
                b = BmgFile(data)
                hit = (data, [b.text(i).lower() for i in range(b.count)])
            except ValueError:
                hit = (data, [])
            self.cache[path] = hit
        return hit[1]

    def file_state(self, path):
        name, bad = self.files[path]
        if path in self.new:
            return 'edited' if self.new[path][0] == 'edited' else f'replaced: {self.new[path][0]}'
        return bad[0] if bad else ''

    def fill(self):
        self.fill_files()
        self.fill_messages()

    def fill_files(self):
        tree, q, only = self.tree, self.query.get().strip().lower(), self.only.get()
        tree.delete(*tree.get_children())
        shown = 0
        for path, (name, bad) in sorted(self.files.items(), key=lambda kv: kv[1][0].lower()):
            mod = path in self.new
            if (q and q not in name.lower() and not any(q in t for t in self.texts_of(path))) or (only and not mod):
                continue
            tree.insert('', 'end', iid=path, text=('● ' if mod else '') + name, values=(self.counts.get(path, 0), self.file_state(path)),
                        tags=('mod',) if mod else ('bad',) if bad else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.files)}   ● {len(self.new)} changed' if self.files else '')
        if self.sel is not None and tree.exists(self.sel):
            tree.selection_set(self.sel)
            tree.see(self.sel)
        self.changed()

    def mark_file(self, path):
        """The row of a file after one of its messages changed."""
        if self.tree.exists(path):
            mod = path in self.new
            self.tree.item(path, text=('● ' if mod else '') + self.files[path][0], values=(self.counts.get(path, 0), self.file_state(path)),
                           tags=('mod',) if mod else ('bad',) if self.files[path][1] else ())
        self.count.set(f'{len(self.tree.get_children())} / {len(self.files)}   ● {len(self.new)} changed')

    def select(self, event=None):
        sel = self.tree.selection()
        if sel and sel[0] != self.sel:
            self.sel, self.row = sel[0], None
            self.show_file()
        self.sync_revert()

    # ----- the messages

    def show_file(self):
        """Reads the selected file (the ROM's and the one that will be patched) and lists its messages."""
        self.rom = self.bmg = None
        self.longest = 0
        path = self.sel
        self.note.pack_forget()
        if path is not None:
            try:
                self.rom = BmgFile(self.rom_files[path])
                self.longest = max([len(self.rom.raw(i)) // 2 for i in range(self.rom.count)] or [0])
            except ValueError:
                pass
            try:
                self.bmg = BmgFile(self.message_file(path))
            except ValueError as e:
                self.note.configure(text=f'{self.files[path][0]} cannot be read: {e}. Replace it with a file that is whole.')
                self.note.pack(fill='x', before=self.split)
        self.fill_messages()

    def is_modified(self, i):
        return self.rom is not None and (i >= self.rom.count or self.bmg.raw(i) != self.rom.raw(i))

    def fill_messages(self):
        tree = self.messages
        tree.delete(*tree.get_children())
        self.problem.set('')
        if self.bmg is None:
            self.row = None
            self.pick_message()
            return
        q, only = self.query.get().strip().lower(), self.only.get()
        by_name = bool(q) and q in self.files[self.sel][0].lower()
        for i in range(self.bmg.count):
            text, mod = self.bmg.text(i), self.is_modified(i)
            if (only and not mod) or (q and not by_name and q not in text.lower() and q != str(i)):
                continue
            ident = self.bmg.ids[i] if self.bmg.ids and self.bmg.ids[i] is not None else None
            tree.insert('', 'end', iid=str(i), values=(('● ' if mod else '') + str(i), '' if ident is None else f'{ident:X}', one_line(text)),
                        tags=('mod',) if mod else ())
        if self.row is not None and tree.exists(str(self.row)):
            tree.selection_set(str(self.row))
            tree.see(str(self.row))
        else:
            self.row = None
            self.pick_message()

    def pick_message(self, event=None):
        """A message was selected: the ROM's text and the text to edit."""
        sel = self.messages.selection()
        if sel:
            self.row = int(sel[0])
        i = self.row if sel else None
        self.loading = True
        if i is None or self.bmg is None:
            self.write(self.original, '')
            self.write(self.box, '')
            self.box.configure(state='disabled')
            self.status.set('')
        else:
            self.write(self.original, self.rom.text(i) if self.rom is not None and i < self.rom.count else '')
            self.write(self.box, self.bmg.text(i))
            self.describe(i)
        self.loading = False
        self.problem.set('')
        self.sync_revert()

    def describe(self, i):
        """Under the texts: which message, and how long it is next to how long the ROM's is."""
        raw = len(self.bmg.raw(i)) // 2
        was = len(self.rom.raw(i)) // 2 if self.rom is not None and i < self.rom.count else None
        ident = self.bmg.ids[i] if self.bmg.ids and self.bmg.ids[i] is not None else None
        self.status.set(f'Message {i}' + (f'   ID {ident:X}' if ident is not None else '') + f'   {raw} characters'
                        + ('' if was is None or was == raw else f' (ROM {was})') + (f'   longest of the file in the ROM: {self.longest}' if raw > self.longest else ''))

    def typed(self, event=None):
        """The text is typed or pasted: it is the message at once, when the file can hold it."""
        if not self.box.edit_modified():
            return
        self.box.edit_modified(False)
        if self.loading or self.bmg is None or self.row is None:
            return
        text = self.box.get('1.0', 'end-1c')
        if text == self.bmg.text(self.row):
            return
        try:
            self.bmg.set_text(self.row, text)
        except ValueError as e:
            self.problem.set(str(e))
            return
        self.problem.set('')
        self.box.tag_remove('code', '1.0', 'end')
        for m in CODE.finditer(text):
            self.box.tag_add('code', f'1.0+{m.start()}c', f'1.0+{m.end()}c')
        self.commit()

    def commit(self):
        """Keeps the file as it is now as the file to patch (or forgets it when it is the ROM's)."""
        path, i = self.sel, self.row
        data = self.bmg.to_bytes()
        if data == self.rom_files[path]:
            self.new.pop(path, None)
        else:
            self.new[path] = (self.new[path][0] if path in self.new else 'edited', data)
        mod = self.is_modified(i)
        if self.messages.exists(str(i)):
            ident = self.messages.item(str(i), 'values')[1]
            self.messages.item(str(i), values=(('● ' if mod else '') + str(i), ident, one_line(self.bmg.text(i))), tags=('mod',) if mod else ())
        self.describe(i)
        self.mark_file(path)
        self.changed()

    def step(self, direction):
        """Ctrl+Down and Ctrl+Up in the text: the next or the previous message."""
        rows = self.messages.get_children()
        if self.row is not None and str(self.row) in rows:
            k = rows.index(str(self.row)) + direction
            if 0 <= k < len(rows):
                self.messages.selection_set(rows[k])
                self.messages.see(rows[k])
                self.box.focus_set()
        return 'break'

    def message_menu(self, event):
        iid = self.messages.identify_row(event.y)
        if iid and self.bmg is not None:
            self.messages.selection_set(iid)
            i = int(iid)
            popup(self.messages, event, [('Copy the text', lambda: copy_text(self, self.bmg.text(i))),
                                         ('Copy the ROM text', (lambda: copy_text(self, self.rom.text(i))) if self.rom is not None and i < self.rom.count else None),
                                         None, ('Revert message', self.revert_message if self.is_modified(i) else None)])

    def revert_message(self):
        """The message back to the text the ROM has."""
        i = self.row
        if i is not None and self.rom is not None and i < self.rom.count:
            self.bmg.set_raw(i, self.rom.raw(i))
            self.loading = True
            self.write(self.box, self.bmg.text(i))
            self.loading = False
            self.commit()
            self.sync_revert()

    # ----- one file

    def entries(self, path):
        return [('Export file...', lambda: self.export(path)), ('Replace file...', lambda: self.replace(path)),
                None, ('Revert', (lambda: self.revert_file(path)) if path in self.new else None)]

    def use_file(self, path, file):
        """The message file `file` is the one the game will have at path (no change when it is the ROM's own). Returns whether it changed."""
        with open(file, 'rb') as f:
            data = f.read()
        bad = bmg_problems(data)
        if bad:
            raise ValueError(f'{os.path.basename(file)}: {bad[0]}')
        if data == self.message_file(path):
            return False
        if data == self.rom_files[path]:
            self.new.pop(path, None)
        else:
            self.new[path] = (os.path.basename(file), data)
        return True

    def replace(self, path=None):
        path = path or self.sel
        file = filedialog.askopenfilename(filetypes=[('BMG message file', '*.bmg')]) if path else ''
        if file:
            try:
                self.use_file(path, file)
            except (OSError, ValueError) as e:
                messagebox.showerror('Replace file', str(e))
                return
            self.refresh()

    def export(self, path=None):
        path = path or self.sel
        out = filedialog.asksaveasfilename(initialfile=self.files[path][0], filetypes=[('BMG message file', '*.bmg'), ('All files', '*')]) if path else ''
        if out:
            try:
                with open(out, 'wb') as f:
                    f.write(self.message_file(path))
            except OSError as e:
                messagebox.showerror('Export file', str(e))

    def item_changed(self):
        return self.sel in self.new

    def revert(self):
        """The button: the message on show when it was changed, else the whole file."""
        if self.row is not None and self.bmg is not None and self.is_modified(self.row):
            self.revert_message()
        else:
            self.revert_file(self.sel)

    def revert_file(self, path):
        if path in self.new:
            del self.new[path]
            self.refresh()

    def refresh(self):
        self.fill_files()
        self.show_file()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert text', f'Revert {len(self.new)} changed message file(s)?'):
            self.new.clear()
            self.refresh()

    # ----- whole folders

    def export_all(self):
        """Every message file of the game in a folder, with the name the game gives it: the changed one where there is one."""
        if not self.files:
            return
        folder = filedialog.askdirectory(title='Folder to export the message files to')
        if not folder:
            return
        done, errors = 0, []
        for path, (name, _) in sorted(self.files.items(), key=lambda kv: kv[1][0].lower()):
            try:
                with open(os.path.join(folder, name), 'wb') as f:
                    f.write(self.message_file(path))
                done += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
        messagebox.showinfo('Export text', f'{done} message file(s) exported to {folder}.' + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    def import_all(self):
        """The message files of a folder that have the name of a game file (any case) replace it."""
        if not self.files:
            return
        folder = filedialog.askdirectory(title='Folder with the message files (named like the ones of the game)')
        if not folder:
            return
        have = {n.lower(): n for n in os.listdir(folder)}
        done, errors = 0, []
        for path, (name, _) in self.files.items():
            if name.lower() in have:
                try:
                    done += self.use_file(path, os.path.join(folder, have[name.lower()]))
                except (OSError, ValueError) as e:
                    errors.append(str(e))
        self.refresh()
        messagebox.showinfo('Import text', f'{done} file(s) selected.' + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    # ----- patch and project

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
                self.new[by_name[name]] = ('edited', data)
            else:
                notes.append(f'BMG {name} does not exist in this ROM: skipped.')
        self.refresh()
        return notes

    def summary(self):
        return f'{len(self.new)} changed' if self.new else 'Unchanged'
