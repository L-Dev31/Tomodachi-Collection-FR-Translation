"""Images tab: the pictures of the game (tile sheets and screens) as PNG files."""
import collections
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.nitro import ncgr_info, nclr_colors, nscr_info
from ...core.png import png_read, png_write, png_write_indexed
from ...features.images.catalog import IMG_DIRS, img_items
from ...features.images.render import encode_screen, encode_sheet, render_screen, render_sheet, sheet_indices
from ..theme import MUTED
from ..widgets import ImageView
from .listing import ListingTab

GREYS = [(i * 17, i * 17, i * 17) for i in range(16)] * 16


def default_view(it):
    """How an image is read when no view is chosen (exports and folder imports): first palette, plain tile sheet."""
    return {'pal': it['pals'][0] if it['pals'] else None, 'scr': None, 'bank': 0, 'wt': it['tw'] or 16}


class ImagesTab(ListingTab):
    key = 'images'
    title = 'Images'
    heading = 'Images'

    def build(self):
        self.items, self.by_iid, self.new, self.sel = [], {}, {}, None
        self.scanned, self.scanning, self.scan_id = False, False, 0
        self.layouts, self.pals = {'Tile sheet': None}, {'Greys': None}
        right = self.build_listing(
            search_width=26, weights=(1, 4), revert_all=self.revert_all,
            more=[('Export listed images to a folder...', self.export_all),
                  ('Replace from a folder (files named like exports)...', self.replace_folder)])
        self.tree.bind('<<TreeviewSelect>>', self.select)
        tools = ttk.Frame(right)
        tools.pack(fill='x')
        self.buttons = [ttk.Button(tools, text=t, style=s, command=c) for t, s, c in (
            ('Replace with PNG', 'Accent.TButton', self.replace),
            ('Export PNG', 'Soft.TButton', self.export),
            ('Revert', 'Soft.TButton', self.revert))]
        for b in self.buttons:
            b.pack(side='left', padx=(0, 6))
        # How to read the picture. Only the choices that mean something for the selected image are shown.
        self.options = ttk.Frame(right)
        self.options.pack(fill='x', pady=(8, 0))
        self.layout, self.pal = tk.StringVar(), tk.StringVar()
        self.bank, self.wt = tk.IntVar(value=0), tk.IntVar(value=16)
        self.layout_box = ttk.Combobox(self.options, textvariable=self.layout, state='readonly', width=24)
        self.pal_box = ttk.Combobox(self.options, textvariable=self.pal, state='readonly', width=11)
        self.bank_box = ttk.Spinbox(self.options, from_=0, to=15, textvariable=self.bank, width=3, command=self.show)
        self.wt_box = ttk.Spinbox(self.options, from_=1, to=64, textvariable=self.wt, width=3, command=lambda: self.show(True))
        self.fields = {}
        for name, label, widget in (('layout', 'View', self.layout_box), ('pal', 'Palette', self.pal_box),
                                    ('bank', 'Bank', self.bank_box), ('wt', 'Tiles/row', self.wt_box)):
            field = ttk.Frame(self.options)
            ttk.Label(field, text=label, foreground=MUTED).pack(side='left', padx=(0, 3))
            widget.pack(in_=field, side='left')
            self.fields[name] = field
        self.layout_box.bind('<<ComboboxSelected>>', lambda e: self.layout_changed())
        self.pal_box.bind('<<ComboboxSelected>>', lambda e: self.show())
        for box in (self.bank_box, self.wt_box):
            box.bind('<Return>', lambda e: self.show(True))
        self.viewer = ImageView(right)
        self.viewer.pack(fill='both', expand=True, pady=(8, 0))
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.viewer.clear('Select an image in the list.')
        self.set_state()

    def set_state(self):
        for b in self.buttons:
            b.state(['!disabled'] if self.sel is not None else ['disabled'])

    def on_rom(self):
        self.scan_id += 1
        self.items, self.by_iid, self.new, self.sel = [], {}, {}, None
        self.scanned = self.scanning = False
        self.tree.delete(*self.tree.get_children())
        self.count.set('')
        self.reset_view()

    def on_show(self):
        if not self.scanned:
            self.scan()

    def scan(self):
        self.scanned = self.scanning = True
        self.todo = sorted(p for p in self.session.files if p.startswith(IMG_DIRS))
        self.items, self.pos = [], 0
        self.after(10, self.scan_step, self.scan_id)

    def scan_step(self, token):
        if token != self.scan_id:
            return
        stop = min(self.pos + 15, len(self.todo))
        for path in self.todo[self.pos:stop]:
            try:
                data = self.session.raw(path)
            except Exception:
                continue
            if data[:4] == b'NARC':
                self.items += img_items(path, data)
        self.pos = stop
        if stop < len(self.todo):
            self.count.set(f'Scanning game images... {100 * stop // len(self.todo)}%')
            self.after(1, self.scan_step, token)
            return
        names = collections.Counter(i['name'] for i in self.items)
        for it in self.items:
            suffix = '' if names[it['name']] == 1 else '@' + it['group'].replace('/', '_')
            it['file'] = re.sub(r'[^A-Za-z0-9_.-]', '_', it['name'] + suffix)
        self.scanning = False
        self.fill()

    def fill(self):
        if self.scanning:
            return
        self.tree.delete(*self.tree.get_children())
        self.by_iid = {}
        q = self.query.get().strip().lower()
        shown, groups = 0, {}
        for it in sorted(self.items, key=lambda i: (i['group'], i['name'].lower())):
            mod = (it['path'], it['idx']) in self.new
            if (q and q not in it['name'].lower() and q not in it['group'].lower()) or (self.only.get() and not mod):
                continue
            if it['group'] not in groups:
                groups[it['group']] = self.tree.insert('', 'end', iid='g:' + it['group'], text=it['group'], open=bool(q) or self.only.get())
            iid = f"{it['path']}|{it['idx']}"
            self.by_iid[iid] = it
            self.tree.insert(groups[it['group']], 'end', iid=iid, text=('● ' if mod else '') + it['name'], tags=('mod',) if mod else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.items)}   ● {len(self.new)} replaced' if self.items else '')
        if self.sel is not None:
            iid = f"{self.sel['path']}|{self.sel['idx']}"
            if iid in self.by_iid:
                self.tree.selection_set(iid)
                self.tree.see(iid)
        self.changed()

    # ----- the picture

    def select(self, event=None):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.by_iid:
            return
        it = self.by_iid[sel[0]]
        if it is self.sel and event is not None:
            return
        self.sel = it
        self.layouts = {'Tile sheet': None}
        for j, w, h in it['scrs']:
            self.layouts[f'Game screen {len(self.layouts)}  ({w}x{h})'] = j
        self.layout_box['values'] = list(self.layouts)
        self.layout.set('Tile sheet')
        self.pals = {f'Palette {n + 1}': p for n, p in enumerate(it['pals'])} or {'Greys': None}
        self.pal_box['values'] = list(self.pals)
        self.pal.set(next(iter(self.pals)))
        self.bank.set(0)
        self.wt.set(it['tw'] or 16)
        self.set_state()
        self.show_fields()
        self.show(True)

    def layout_changed(self):
        self.show_fields()
        self.show(True)

    def show_fields(self):
        """Shows the choices that apply: several screens, several palettes, banks of 4 bit images, tiles per row."""
        it = self.sel
        sheet = self.layouts[self.layout.get()] is None
        wanted = {'layout': len(self.layouts) > 1, 'pal': len(self.pals) > 1,
                  'bank': sheet and it['bits'] == 4, 'wt': sheet and not it['tw']}
        for name, field in self.fields.items():
            field.pack_forget()
        for name, field in self.fields.items():
            if wanted[name]:
                field.pack(side='left', padx=(0, 12))

    def view(self):
        """The reading chosen in the window for the selected image."""
        return {'pal': self.pals[self.pal.get()], 'scr': self.layouts[self.layout.get()],
                'bank': self.bank.get(), 'wt': self.wt.get()}

    def resolve(self, it, view):
        subs = self.session.subfiles(it['path'])
        cols = nclr_colors(subs[view['pal']]) if view['pal'] is not None else GREYS
        scr = nscr_info(subs[view['scr']]) if view['scr'] is not None else None
        return cols, scr, view['bank'], view['wt']

    def current(self, it):
        """The picture as it will be patched: the replaced one, else the one of the ROM."""
        return self.new.get((it['path'], it['idx'])) or self.session.subfiles(it['path'])[it['idx']]

    def pixels(self, f, cols, scr, bank, wt):
        return render_screen(f, cols, scr) if scr else render_sheet(f, cols, bank, wt)

    def show(self, refit=False):
        it = self.sel
        if it is None:
            return
        try:
            cols, scr, bank, wt = self.resolve(it, self.view())
            w, h, rgba = self.pixels(self.current(it), cols, scr, bank, wt)
        except Exception as e:
            self.viewer.clear(f'Cannot display this image:\n{e}')
            return
        self.viewer.show(w, h, rgba, refit=refit)

    # ----- import and export

    def import_png(self, it, data, view):
        """Encodes a PNG into the picture (kept in self.new unless it looks the same). Returns (clashes, snapped pixels)."""
        w, h, rgba = png_read(data)
        cols, scr, bank, wt = self.resolve(it, view)
        f = self.current(it)
        if scr:
            new, clash, snapped = encode_screen(f, cols, scr, w, h, rgba)
        else:
            new, clash, snapped = encode_sheet(f, cols, bank, wt, w, h, rgba)
        key = (it['path'], it['idx'])
        orig = self.session.subfiles(it['path'])[it['idx']]
        if new == orig or self.pixels(orig, cols, scr, bank, wt) == self.pixels(new, cols, scr, bank, wt):
            self.new.pop(key, None)
        else:
            self.new[key] = new
        return clash, snapped

    def png_bytes(self, it, view):
        cols, scr, bank, wt = self.resolve(it, view)
        f = self.current(it)
        if scr:
            w, h, rgba = render_screen(f, cols, scr)
            return png_write(w, h, rgba)
        w, h, idx = sheet_indices(f, wt)
        bits = ncgr_info(f)['bits']
        base = bank * 16 if bits == 4 else 0
        pal = [cols[base + i] if base + i < len(cols) else (0, 0, 0) for i in range(16 if bits == 4 else 256)]
        return png_write_indexed(w, h, idx, pal, 4 if bits == 4 and w % 2 == 0 else 8)

    def replace(self):
        it = self.sel
        if it is None:
            return
        path = filedialog.askopenfilename(filetypes=[('PNG image', '*.png')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                clash, snapped = self.import_png(it, f.read(), self.view())
        except Exception as e:
            messagebox.showerror('Replace image', str(e))
            return
        self.fill()
        self.show()
        problems = []
        if snapped:
            problems.append(f'{snapped:,} pixel(s) were not in the palette and were snapped to the closest colour.')
        if clash:
            problems.append(f'{clash} reused tile(s) had different pictures: only the first one was kept.')
        if problems:
            messagebox.showwarning('Replace image', f"{it['name']} was imported.\n\n" + '\n'.join(problems))

    def export(self):
        it = self.sel
        if it is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.png', initialfile=it['file'] + '.png', filetypes=[('PNG image', '*.png')])
        if not out:
            return
        try:
            with open(out, 'wb') as f:
                f.write(self.png_bytes(it, self.view()))
        except Exception as e:
            messagebox.showerror('Export image', str(e))

    def revert(self):
        it = self.sel
        if it and self.new.pop((it['path'], it['idx']), None) is not None:
            self.fill()
            self.show()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert images', f'Revert {len(self.new)} replaced image(s)?'):
            self.new.clear()
            self.fill()
            self.show()

    def export_all(self):
        folder = filedialog.askdirectory()
        if not folder or self.scanning:
            return
        items = list(self.by_iid.values())
        try:
            for n, it in enumerate(items):
                with open(os.path.join(folder, it['file'] + '.png'), 'wb') as f:
                    f.write(self.png_bytes(it, default_view(it)))
                if n % 20 == 0:
                    self.count.set(f'Exporting {n} / {len(items)}...')
                    self.update_idletasks()
        except Exception as e:
            messagebox.showerror('Export images', str(e))
        self.fill()
        messagebox.showinfo('Export images', f'{len(items)} image(s) exported to {folder}')

    def replace_folder(self):
        folder = filedialog.askdirectory()
        if not folder or self.scanning:
            return
        have = {n.lower(): n for n in os.listdir(folder)}
        done, errors = 0, []
        for it in self.items:
            name = (it['file'] + '.png').lower()
            if name not in have:
                continue
            try:
                with open(os.path.join(folder, have[name]), 'rb') as f:
                    self.import_png(it, f.read(), default_view(it))
                done += 1
            except Exception as e:
                errors.append(f'{have[name]}: {e}')
        self.fill()
        self.show()
        messagebox.showinfo('Replace from folder', f'{done} image(s) imported.' + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    # ----- patch and project

    def patch_config(self):
        out = {}
        for (path, i), data in self.new.items():
            out.setdefault(path, {})[i] = data
        return out or None

    def project_part(self):
        return self.patch_config() or {}

    def restore(self, part):
        self.new.clear()
        notes = []
        for path, subs in part.items():
            try:
                have = self.session.subfiles(path)
            except Exception:
                notes.append(f'Image file {path} does not exist in this ROM: skipped.')
                continue
            for i, data in subs.items():
                if i < len(have) and len(data) == len(have[i]) and data[:4] == have[i][:4]:
                    self.new[(path, i)] = data
                else:
                    notes.append(f'Image {path} #{i} does not fit this ROM: skipped.')
        self.fill()
        self.show()
        return notes

    def summary(self):
        return f'{len(self.new)} replaced' if self.new else 'Unchanged'
