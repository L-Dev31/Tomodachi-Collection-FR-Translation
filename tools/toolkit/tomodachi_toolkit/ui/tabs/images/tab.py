"""Images tab: the pictures of the game (tile sheets and screens) as PNG files."""
import collections
import os
import re
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from ....core.nitro import ncgr_info, nclr_colors, nclr_set, nscr_info
from ....core.png import png_read, png_write, png_write_indexed
from ....features.images.catalog import IMG_DIRS, img_items
from ....features.images.render import encode_screen, encode_sheet, render_screen, render_sheet, sheet_indices
from ...theme import BROWN, DARK, MUTED
from ...widgets import Hint, ImageView, InfoTable
from ..listing import ListingTab
from .palette import PaletteView, hex_of

GREYS = [(i * 17, i * 17, i * 17) for i in range(16)] * 16
SHEET = 'All the tiles, side by side'


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
        self.layouts, self.pals, self.color = {SHEET: None}, {'Greys': None}, None      # how the picture can be shown, its palettes, the colour picked
        right = self.build_listing(search_width=26, weights=(1, 4), batch=(self.export_all, self.import_all, self.revert_all))
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.build_menu(lambda iid: [('Export PNG...', self.export), ('Replace with PNG...', self.replace), None,
                                     ('Revert', self.revert if any(k in self.new for k in self.keys_of(self.by_iid[iid])) else None)]
                        if iid in self.by_iid else [])
        self.table = InfoTable(right)
        self.table.pack(fill='x')
        # How to show the picture: only the choices that mean something for the selected image appear.
        self.options = ttk.Frame(right)
        self.layout, self.pal = tk.StringVar(), tk.StringVar()
        self.bank, self.wt = tk.IntVar(value=0), tk.IntVar(value=16)
        self.layout_box = ttk.Combobox(self.options, textvariable=self.layout, state='readonly', width=36)
        self.wt_box = ttk.Spinbox(self.options, from_=1, to=64, textvariable=self.wt, width=3, command=lambda: self.show(True))
        self.fields = {}
        for name, label, widget, hint in (
                ('layout', 'Show as', self.layout_box, 'All the tiles: the small 8 x 8 pieces the picture is made of, side by side, as the '
                 'game stores them.\nA screen: the same tiles put together the way the game shows them.'),
                ('wt', 'Tiles per row', self.wt_box, 'How many 8 x 8 tiles the sheet shows on each line. It only changes how the pieces '
                 'are laid out in the picture you export or import: use the same number both times.')):
            field = ttk.Frame(self.options)
            text = ttk.Label(field, text=label, foreground=MUTED)
            text.pack(side='left', padx=(0, 3))
            widget.pack(in_=field, side='left')
            for part in (text, widget):
                Hint(part, hint)
            self.fields[name] = field
        self.layout_box.bind('<<ComboboxSelected>>', lambda e: self.layout_changed())
        self.wt_box.bind('<Return>', lambda e: self.show(True))
        # the picture, with its palette beside it
        self.body = ttk.Frame(right)
        self.body.pack(fill='both', expand=True, pady=(8, 0))
        self.side = ttk.Frame(self.body)
        ttk.Label(self.side, text='Palette', foreground=DARK, font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.pal_box = ttk.Combobox(self.side, textvariable=self.pal, state='readonly', width=16)
        self.pal_box.bind('<<ComboboxSelected>>', lambda e: self.show())
        self.palette = PaletteView(self.side, self.pick_color, self.change_color, self.hover_color)
        self.palette.pack(anchor='w', pady=(4, 0))
        self.color_text, self.pal_note = tk.StringVar(), tk.StringVar()
        ttk.Label(self.side, textvariable=self.color_text, foreground=BROWN, wraplength=182, justify='left').pack(anchor='w', pady=(4, 0))
        self.change_button = ttk.Button(self.side, text='Change this colour...', style='Mini.TButton', command=self.change_color)
        self.change_button.pack(anchor='w', pady=(2, 0))
        ttk.Label(self.side, textvariable=self.pal_note, foreground=MUTED, wraplength=182, justify='left').pack(anchor='w', pady=(8, 0))
        self.viewer = ImageView(self.body, width=320)
        self.viewer.pack(side='left', fill='both', expand=True)
        self.reset_view()

    # ----- the list

    def reset_view(self):
        self.options.pack_forget()
        self.side.pack_forget()
        self.viewer.clear()
        self.table.show([])
        self.set_state()

    def set_state(self):
        self.sync_revert()

    def item_changed(self):
        return self.sel is not None and any(k in self.new for k in self.keys_of(self.sel))

    def on_rom(self):
        self.scan_id += 1
        self.items, self.by_iid, self.new, self.sel, self.color = [], {}, {}, None, None
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
            mod = any(k in self.new for k in self.keys_of(it))
            if (q and q not in it['name'].lower() and q not in it['group'].lower()) or (self.only.get() and not mod):
                continue
            if it['group'] not in groups:
                groups[it['group']] = self.tree.insert('', 'end', iid='g:' + it['group'], text=it['group'], open=bool(q) or self.only.get())
            iid = f"{it['path']}|{it['idx']}"
            self.by_iid[iid] = it
            self.tree.insert(groups[it['group']], 'end', iid=iid, text=('● ' if mod else '') + it['name'], tags=('mod',) if mod else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.items)}   ● {len(self.new)} changed' if self.items else '')
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
        self.layouts = {SHEET: None}
        for j, w, h in it['scrs']:
            self.layouts[f'Screen {len(self.layouts)}  ({w} x {h}), as in the game'] = j
        self.layout_box['values'] = list(self.layouts)
        self.layout.set(SHEET)
        self.pals = {f'Palette {n + 1}': p for n, p in enumerate(it['pals'])} or {'Greys': None}
        self.pal_box['values'] = list(self.pals)
        self.pal.set(next(iter(self.pals)))
        self.bank.set(0)
        self.wt.set(it['tw'] or 16)
        self.color = None
        self.table.show([('Image', it['name']), ('Folder', it['group']), ('Depth', f"{it['bits']} bit"), ('Palettes', str(len(it['pals']))),
                         ('Screens', str(len(it['scrs'])))])
        self.set_state()
        self.show_fields()
        self.side.pack(side='right', anchor='n', padx=(10, 0), before=self.viewer)
        if len(self.pals) > 1:
            self.pal_box.pack(anchor='w', before=self.palette)
        else:
            self.pal_box.pack_forget()
        self.show(True)

    def keys_of(self, it):
        """What the tab keeps of a picture when it is changed: the picture itself and the palettes of its archive."""
        return [(it['path'], it['idx'])] + [(it['path'], j) for j in it['pals']]

    def layout_changed(self):
        self.show_fields()
        self.show(True)

    def show_fields(self):
        """Shows the choices that apply: how to show the picture when it has game screens, tiles per row when the file does not say."""
        it = self.sel
        sheet = self.layouts[self.layout.get()] is None
        wanted = {'layout': len(self.layouts) > 1, 'wt': sheet and not it['tw']}
        for field in self.fields.values():
            field.pack_forget()
        for name, field in self.fields.items():
            if wanted[name]:
                field.pack(side='left', padx=(0, 12))
        if any(wanted.values()):
            self.options.pack(fill='x', pady=(8, 0), before=self.body)
        else:
            self.options.pack_forget()

    def view(self):
        """The reading chosen in the window for the selected image."""
        return {'pal': self.pals[self.pal.get()], 'scr': self.layouts[self.layout.get()],
                'bank': self.bank.get(), 'wt': self.wt.get()}

    def palette_file(self, it, j):
        """The palette file as it will be patched: the changed one, else the one of the ROM."""
        return self.new.get((it['path'], j)) or self.session.subfiles(it['path'])[j]

    def resolve(self, it, view):
        subs = self.session.subfiles(it['path'])
        cols = nclr_colors(self.palette_file(it, view['pal'])) if view['pal'] is not None else GREYS
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
        view = self.view()
        try:
            cols, scr, bank, wt = self.resolve(it, view)
            self.show_palette(it, view, cols, scr, bank)
            w, h, rgba = self.pixels(self.current(it), cols, scr, bank, wt)
        except Exception as e:
            self.viewer.clear(f'Cannot display this image:\n{e}')
            return
        self.viewer.show(w, h, rgba, refit=refit)

    # ----- the palette

    def step(self):
        """Colours between two transparent ones: every 16th colour of a 4 bit picture, only the first of an 8 bit one."""
        return 16 if self.sel['bits'] == 4 else 256

    def show_palette(self, it, view, cols, scr, bank):
        """Draws the palette with the rows the picture uses, and says what the rows mean for the way the picture is shown."""
        four = it['bits'] == 4
        rows = (sorted({cell >> 12 for cell in scr['cells']}) if scr else [bank]) if four else []
        self.palette.set(cols, rows, self.color, self.step())
        if view['pal'] is None:
            note = 'This picture has no palette of its own: shades of grey are shown.'
        elif not four:
            note = 'This picture can use all the colours of the palette.'
        elif scr:
            note = 'The outlined rows hold the colours the game picks for the tiles of this screen.'
        else:
            note = 'The tiles use one row of 16 colours (outlined). Click another row to see them in its colours.'
        self.pal_note.set(note)
        self.describe_color(self.color)
        self.change_button.state(['!disabled'] if self.editable() else ['disabled'])

    def describe_color(self, i):
        cols = self.palette.colors
        if i is None or i >= len(cols):
            self.color_text.set('Click a colour to pick it.')
        else:
            self.color_text.set(f'Colour {i}   ' + ('transparent' if i % self.step() == 0 else hex_of(cols[i])))

    def editable(self):
        """Whether the colour that is picked can be changed: it belongs to a palette of the archive and it is not a transparent one."""
        return (self.sel is not None and self.view()['pal'] is not None and self.color is not None
                and self.color < len(self.palette.colors) and self.color % self.step() != 0)

    def pick_color(self, i):
        """A click on a swatch picks the colour, and also its row when the picture is a sheet of 4 bit tiles."""
        self.color = i
        if self.sel is not None and self.sel['bits'] == 4 and self.layouts[self.layout.get()] is None:
            self.bank.set(i // 16)
        self.show()

    def hover_color(self, i):
        self.describe_color(self.color if i is None else i)

    def change_color(self, i=None):
        """Asks for a new colour for the colour that is picked (or for swatch i, when it was double clicked) and puts it in the palette."""
        if i is not None:
            self.color = i
        if not self.editable():
            return
        it, j = self.sel, self.view()['pal']
        file = self.palette_file(it, j)
        chosen = colorchooser.askcolor(color=hex_of(nclr_colors(file)[self.color]), parent=self, title=f'Colour {self.color} of the palette')
        if not chosen or chosen[0] is None:
            return
        new = nclr_set(file, self.color, [int(round(v)) for v in chosen[0]])
        key = (it['path'], j)
        if new == self.session.subfiles(it['path'])[j]:
            self.new.pop(key, None)
        else:
            self.new[key] = new
        self.fill()
        self.show()

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
        if it and any([self.new.pop(key, None) is not None for key in self.keys_of(it)]):
            self.fill()
            self.show()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert images', f'Revert {len(self.new)} change(s) to images and palettes?'):
            self.new.clear()
            self.fill()
            self.show()

    def export_all(self):
        """The listed images as PNG files in a folder (named like the list names them)."""
        if self.scanning:
            return
        folder = filedialog.askdirectory(title='Folder to export the listed images to')
        if not folder:
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

    def import_all(self):
        """The PNG files of a folder that are named like the export names them. One that looks like the picture the ROM has is no change."""
        if self.scanning:
            return
        folder = filedialog.askdirectory(title='Folder with the PNG files named like the exports')
        if not folder:
            return
        have = {n.lower(): n for n in os.listdir(folder)}
        done = same = 0
        errors = []
        for it in self.items:
            name = (it['file'] + '.png').lower()
            if name not in have:
                continue
            key = (it['path'], it['idx'])
            before = self.new.get(key)
            try:
                with open(os.path.join(folder, have[name]), 'rb') as f:
                    self.import_png(it, f.read(), default_view(it))
            except Exception as e:
                errors.append(f'{have[name]}: {e}')
                continue
            if self.new.get(key) != before:
                done += 1
            else:
                same += 1
        self.fill()
        self.show()
        messagebox.showinfo('Import images', f'{done} image(s) imported' + (f', {same} the same as they are now' if same else '') + '.'
                            + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

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
        palettes = sum(1 for data in self.new.values() if data[:4] == b'RLCN')
        parts = ([f'{len(self.new) - palettes} replaced'] if len(self.new) > palettes else []) + ([f'{palettes} palette(s) changed'] if palettes else [])
        return ', '.join(parts) or 'Unchanged'
