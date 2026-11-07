"""The editor of an animation. Left, what the animation moves (the bones of a skeleton, the materials of a model, the parts that show up);
right, the keys of the one selected, in a table whose values are changed by a double click. A value in brackets lies between two keys and
follows them; a star says that other animations read the same value."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..features.models.animedit import apply_table, table_csv
from .theme import ERROR, MUTED, font
from .widgets import tree_with_scrollbar


class AnimView(ttk.Frame):
    """change(data, anim) is called with the new bytes of the file (and the animation read from them) after a value was changed."""

    def __init__(self, master, change):
        super().__init__(master)
        self.change, self.build, self.data, self.anim, self.sheets = change, None, None, None, []
        self.title, self.message, self.group = tk.StringVar(), tk.StringVar(), tk.StringVar()
        top = ttk.Frame(self)
        top.pack(fill='x')
        ttk.Label(top, textvariable=self.title, font=font(10, True)).pack(side='left')
        self.choice = ttk.Frame(top)
        self.choice.pack(side='right')
        ttk.Button(top, text='Import table...', style='Mini.TButton', command=self.import_table).pack(side='right', padx=(6, 0))
        ttk.Button(top, text='Export table...', style='Mini.TButton', command=self.export_table).pack(side='right')
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True, pady=(4, 0))
        left = ttk.Frame(body)
        left.pack(side='left', fill='y')
        self.tracks = tree_with_scrollbar(left, show='tree', selectmode='browse', height=6)
        self.tracks.column('#0', width=120)
        self.tracks.bind('<<TreeviewSelect>>', self.pick_track)
        right = ttk.Frame(body)
        right.pack(side='left', fill='both', expand=True, padx=(6, 0))
        self.table = ttk.Treeview(right, show='headings', selectmode='browse', height=6)
        down = ttk.Scrollbar(right, orient='vertical', command=self.table.yview)
        across = ttk.Scrollbar(right, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=down.set, xscrollcommand=across.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        down.grid(row=0, column=1, sticky='ns')
        across.grid(row=1, column=0, sticky='ew')
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.table.bind('<Double-Button-1>', self.double)
        self.line = ttk.Label(self, textvariable=self.message, foreground=MUTED, wraplength=520, justify='left')
        self.line.pack(fill='x', pady=(4, 0))
        self.items, self.track, self.page, self.editing = {}, 0, '', None

    # ----- what is shown

    def load(self, data, build):
        """data: the file; build(data) gives (the animation, its sheets: see features/models/animedit.py)."""
        self.build, self.data, self.track, self.page = build, data, 0, ''
        self.anim, self.sheets = build(data)
        self.title.set(f'{self.anim.name}   {self.anim.frames} frames')
        self.tracks.delete(*self.tracks.get_children())
        for i, sheet in enumerate(self.sheets):
            self.tracks.insert('', 'end', iid=str(i), text=sheet.name)
        self.message.set('')
        if self.sheets:
            self.tracks.selection_set('0')
        self.draw()

    def pick_track(self, event=None):
        sel = self.tracks.selection()
        if sel and int(sel[0]) != self.track:
            self.track = int(sel[0])
            self.draw()

    def draw(self):
        for w in self.choice.winfo_children():
            w.destroy()
        if not self.sheets:
            self.table.delete(*self.table.get_children())
            return
        groups = self.sheets[self.track].groups
        if self.page not in [g.title for g in groups]:
            self.page = next((g.title for g in groups if g.rows), groups[0].title)
        if len(groups) > 1:
            for g in groups:
                ttk.Radiobutton(self.choice, text=g.title, value=g.title, variable=self.group, style='Toolbutton', command=self.turn).pack(side='left', padx=(3, 0))
        self.group.set(self.page)
        self.fill(next(g for g in groups if g.title == self.page))

    def turn(self):
        self.page = self.group.get()
        self.draw()

    def fill(self, group):
        t = self.table
        keep = t.yview()[0]
        t.delete(*t.get_children())
        ids = [str(i) for i in range(len(group.columns) + 1)]
        t['columns'] = ids
        for i, title in zip(ids, ('Frame',) + tuple(group.columns)):
            t.heading(i, text=title)
            t.column(i, width=64 if i == '0' else max(56, 10 * len(title)), anchor='e', stretch=False)
        self.items = {}
        for r, row in enumerate(group.rows):
            iid = str(r)
            t.insert('', 'end', iid=iid, values=(row.label,) + tuple(item.text for item in row.items))
            for c, item in enumerate(row.items, 1):
                self.items[(iid, f'#{c + 1}')] = item
        t.yview_moveto(keep)
        shared = any(item.text.endswith('*') for row in group.rows for item in row.items)
        self.message.set(group.note or ('* is read by other animations too: changing it changes them.' if shared else ''))
        self.line.configure(foreground=MUTED)

    # ----- changing a value

    def double(self, event):
        iid, column = self.table.identify_row(event.y), self.table.identify_column(event.x)
        item = self.items.get((iid, column))
        if item is None:
            return
        if item.toggle:
            self.apply(item, '', iid)
        elif item.edit is None:
            self.say('Between two keys: the value follows them.', False)
        else:
            self.type_in(iid, column, item)

    def type_in(self, iid, column, item):
        """An entry over the cell: Enter keeps what is typed, Escape or a click elsewhere leaves the value as it is."""
        x, y, w, h = self.table.bbox(iid, column)
        entry = ttk.Entry(self.table, justify='right')
        entry.insert(0, item.text.strip('()* '))
        entry.select_range(0, 'end')
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        done = []

        def finish(keep):
            if not done:
                done.append(1)
                text = entry.get()
                entry.destroy()
                if keep:
                    self.apply(item, text, iid)
        entry.bind('<Return>', lambda e: finish(True))
        entry.bind('<Escape>', lambda e: finish(False))
        entry.bind('<FocusOut>', lambda e: finish(False))

    def apply(self, item, text, iid):
        try:
            new = item.edit(self.data, text)
        except ValueError as e:
            self.say(str(e), True)
            return
        if new != self.data:
            self.data = new
            self.anim, self.sheets = self.build(new)
            self.draw()
            if self.table.exists(iid):
                self.table.selection_set(iid)
            self.change(new, self.anim)

    # ----- the table as a file

    def export_table(self):
        """The whole table of the animation as a CSV file: a spreadsheet opens it, and Import table reads it back."""
        if self.anim is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.csv', initialfile=f'{self.anim.name}.csv', filetypes=[('Table of an animation (CSV)', '*.csv')])
        if out:
            try:
                with open(out, 'w', encoding='utf-8-sig', newline='') as f:
                    f.write(table_csv(self.sheets))
            except OSError as e:
                messagebox.showerror('Export table', str(e))

    def import_table(self):
        """Reads a table written by Export table (or edited in a spreadsheet): the values that differ are written and the animation is made again."""
        if self.anim is None:
            return
        path = filedialog.askopenfilename(filetypes=[('Table of an animation (CSV)', '*.csv'), ('All files', '*')])
        if not path:
            return
        try:
            with open(path, encoding='utf-8-sig', newline='') as f:
                text = f.read()
            data, changed, problems = apply_table(self.data, self.sheets, text)
        except (OSError, ValueError) as e:
            messagebox.showerror('Import table', f'{os.path.basename(path)}: {e}')
            return
        if changed:
            self.data = data
            self.anim, self.sheets = self.build(data)
            self.draw()
            self.change(data, self.anim)
        message = f'{changed} value(s) changed.' + ('\n\nNot written:\n' + '\n'.join(problems[:12]) if problems else '')
        (messagebox.showwarning if problems else messagebox.showinfo)('Import table', message)

    def say(self, text, bad):
        self.message.set(text)
        self.line.configure(foreground=ERROR if bad else MUTED)
