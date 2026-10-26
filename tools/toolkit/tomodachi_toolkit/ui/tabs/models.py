"""Models tab: the 3D models of the game. Textures go through PNG files, shapes through OBJ files (Blender and others)."""
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.png import png_read, png_write
from ...features.models.actions import model_actions
from ...features.models.bmd import TEX_FORMATS, bmd_textures
from ...features.models.obj_export import obj_export, obj_ident
from ...features.models.obj_import import obj_import
from ...features.models.textures import tex_encode, tex_render
from ..theme import PANEL, SAND, font
from ..modelview import ModelView
from ..widgets import ImageView
from .listing import ListingTab


MODEL_FOLDERS = ('/Mdl/', '/Job/', '/News/', '/Scn/Affn/', '/Scn/Mrg/')   # the folders of the ROM where models are


def file_stem(name):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


class ModelsTab(ListingTab):
    key = 'models'
    title = 'Models'
    heading = 'Models'

    def build(self):
        self.items, self.by_iid, self.new, self.cur = [], {}, {}, None
        self.texs, self.pals = [], []
        right = self.build_listing(search_width=22, weights=(1, 3), revert_all=self.revert_all)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.view = tk.StringVar(value='3d')
        modes = ttk.Frame(right)
        modes.pack(fill='x', pady=(0, 6))
        ttk.Radiobutton(modes, text='3D view', value='3d', variable=self.view, command=self.show_view).pack(side='left')
        ttk.Radiobutton(modes, text='Texture', value='texture', variable=self.view, command=self.show_view).pack(side='left', padx=(12, 0))
        self.stage = ttk.Frame(right)
        self.stage.pack(fill='both', expand=True)
        self.model_view = ModelView(self.stage, width=420, height=260)
        self.viewer = ImageView(self.stage, width=420, height=260)
        textures = ttk.Labelframe(right, text='Textures', padding=8)
        textures.pack(fill='x', pady=(8, 0))
        self.listbox = tk.Listbox(textures, height=4, exportselection=False, bg=PANEL, relief='flat', highlightthickness=1,
                                  highlightbackground=SAND, font=font(9))
        self.listbox.pack(fill='x')
        self.listbox.bind('<<ListboxSelect>>', self.pick)
        row = ttk.Frame(textures)
        row.pack(fill='x', pady=(8, 0))
        self.texture_buttons = self.add_buttons(row, (
            ('Replace with PNG', 'Accent.TButton', self.replace_texture),
            ('Export PNG', 'Soft.TButton', self.export_texture),
            ('Export all', 'Soft.TButton', self.export_textures)))
        shapes = ttk.Labelframe(right, text='3D shapes', padding=8)
        shapes.pack(fill='x', pady=(8, 0))
        self.model_buttons = self.add_buttons(shapes, (
            ('Export OBJ', 'Soft.TButton', self.export_model),
            ('Import OBJ', 'Accent.TButton', self.import_model)))
        self.revert_button = ttk.Button(shapes, text='Revert model', style='Soft.TButton', command=self.revert)
        self.revert_button.pack(side='right')
        self.show_view()
        self.reset_view()

    @staticmethod
    def add_buttons(parent, specs):
        buttons = [ttk.Button(parent, text=t, style=s, command=c) for t, s, c in specs]
        for b in buttons:
            b.pack(side='left', padx=(0, 6))
        return buttons

    # ----- the list

    def reset_view(self):
        self.cur, self.texs = None, []
        self.listbox.delete(0, 'end')
        self.viewer.clear('Select a model in the list.')
        self.model_view.clear('Select a model in the list.')
        self.set_state()

    def show_view(self):
        """Shows the 3D view or the picture of the texture that is selected in the list."""
        shown, hidden = (self.model_view, self.viewer) if self.view.get() == '3d' else (self.viewer, self.model_view)
        hidden.pack_forget()
        shown.pack(fill='both', expand=True)
        if shown is self.model_view:
            shown.refresh()

    def show_model(self, keep=False):
        """Draws the model as it is now (the changed one, else the one of the ROM)."""
        if self.cur is None:
            return
        path = self.cur[0]
        self.model_view.load(self.file(*self.cur), lambda counts: model_actions(self.session, path, counts), keep=keep)

    def set_state(self):
        def on(buttons, yes):
            for b in buttons:
                b.state(['!disabled'] if yes else ['disabled'])
        on(self.texture_buttons, self.cur is not None and bool(self.texs))
        on(self.model_buttons + [self.revert_button], self.cur is not None)

    def on_rom(self):
        self.new = {}
        self.items = []
        for path in sorted(self.session.files):
            if path.startswith(MODEL_FOLDERS):
                name = path.rsplit('/', 1)[1]
                self.items.append({'path': path, 'name': name[:-7] if name.endswith('_LZ.bin') else name, 'group': path.rsplit('/', 1)[0].strip('/')})
        self.reset_view()
        self.fill()

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        self.by_iid = {}
        q = self.query.get().strip().lower()
        changed = {p for p, _ in self.new}
        shown, groups = 0, {}
        for it in self.items:
            mod = it['path'] in changed
            if (q and q not in it['name'].lower() and q not in it['group'].lower()) or (self.only.get() and not mod):
                continue
            if it['group'] not in groups:
                groups[it['group']] = self.tree.insert('', 'end', iid='g:' + it['group'], text=it['group'], open=bool(q) or self.only.get())
            self.by_iid[it['path']] = it
            self.tree.insert(groups[it['group']], 'end', iid=it['path'], text=('● ' if mod else '') + it['name'], tags=('mod',) if mod else ())
            shown += 1
        self.count.set(f'{shown} / {len(self.items)}   ● {len(changed)} changed' if self.items else '')
        if self.cur and self.cur[0] in self.by_iid:
            self.tree.selection_set(self.cur[0])
            self.tree.see(self.cur[0])
        self.changed()

    def file(self, path, idx):
        """The model file as it will be patched: the changed one, else the one of the ROM."""
        return self.new.get((path, idx)) or self.session.subfiles(path)[idx]

    def select(self, event=None):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.by_iid:
            return
        path = sel[0]
        if self.cur and self.cur[0] == path and event is not None:
            return
        self.reset_view()
        try:
            subs = self.session.subfiles(path)
        except Exception as e:
            self.viewer.clear(f'Cannot open this file:\n{e}')
            return
        idx = next((i for i, f in enumerate(subs) if f[:4] == b'BMD0'), None)
        if idx is None:
            self.viewer.clear('No 3D model in this file (animation or effect data only).')
            return
        self.cur = (path, idx)
        try:
            self.read_textures()
        except Exception as e:
            self.texs = []
            self.viewer.clear(f'Cannot read the textures:\n{e}')
            self.set_state()
            return
        for t in self.texs:
            self.listbox.insert('end', f"{t['name']}   {t['w']} x {t['h']}   {TEX_FORMATS.get(t['fmt'], '?')}")
        self.set_state()
        if self.texs:
            self.listbox.selection_set(0)
            self.pick(show=False)
        else:
            self.viewer.clear('This model has no texture.')
        self.view.set('3d')
        self.show_view()
        self.show_model()

    def name(self):
        return self.cur[0].rsplit('/', 1)[1].removesuffix('_LZ.bin') if self.cur else ''

    def read_textures(self):
        """The textures of the model as it is now. Where they sit in the file moves when the shapes change size."""
        self.texs, self.pals = bmd_textures(self.file(*self.cur))

    # ----- textures

    def texture(self):
        sel = self.listbox.curselection()
        return self.texs[sel[0]] if sel and self.cur is not None else None

    def pick(self, event=None, show=True):
        t = self.texture()
        if t is None:
            return
        if event is not None and show:
            self.view.set('texture')
            self.show_view()
        try:
            w, h, rgba = tex_render(self.file(*self.cur), t, self.pals)
        except Exception as e:
            self.viewer.clear(f'Cannot display this texture:\n{e}')
            return
        self.viewer.show(w, h, rgba, refit=True)

    def replace_texture(self):
        t = self.texture()
        if t is None:
            return
        path = filedialog.askopenfilename(filetypes=[('PNG image', '*.png')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                w, h, rgba = png_read(f.read())
            new, snapped = tex_encode(self.file(*self.cur), t, self.pals, w, h, rgba)
        except Exception as e:
            messagebox.showerror('Replace texture', str(e))
            return
        if new == self.session.subfiles(self.cur[0])[self.cur[1]]:
            self.new.pop(self.cur, None)
        else:
            self.new[self.cur] = new
        self.read_textures()
        self.fill()
        self.pick()
        self.show_model(keep=True)
        if snapped:
            messagebox.showwarning('Replace texture', f"{t['name']} was imported.\n\n{snapped:,} pixel(s) were snapped to the closest palette colour.")

    def export_texture(self):
        t = self.texture()
        if t is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.png', initialfile=file_stem(t['name']) + '.png', filetypes=[('PNG image', '*.png')])
        if not out:
            return
        try:
            w, h, rgba = tex_render(self.file(*self.cur), t, self.pals)
            with open(out, 'wb') as f:
                f.write(png_write(w, h, rgba))
        except Exception as e:
            messagebox.showerror('Export texture', str(e))

    def export_textures(self):
        if self.cur is None or not self.texs:
            return
        folder = filedialog.askdirectory()
        if not folder:
            return
        try:
            b = self.file(*self.cur)
            for t in self.texs:
                w, h, rgba = tex_render(b, t, self.pals)
                with open(os.path.join(folder, file_stem(t['name']) + '.png'), 'wb') as f:
                    f.write(png_write(w, h, rgba))
        except Exception as e:
            messagebox.showerror('Export textures', str(e))
            return
        messagebox.showinfo('Export textures', f'{len(self.texs)} texture(s) exported to {folder}')

    # ----- 3D shapes

    def export_model(self):
        if self.cur is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.obj', initialfile=file_stem(self.name()) + '.obj', filetypes=[('Wavefront OBJ', '*.obj')])
        if not out:
            return
        folder = os.path.dirname(out)
        stem = obj_ident(os.path.splitext(os.path.basename(out))[0])
        try:
            obj, mtl, pngs, info = obj_export(self.file(*self.cur), stem)
            with open(out, 'w', encoding='utf-8', newline='\n') as f:
                f.write(obj)
            with open(os.path.join(folder, stem + '.mtl'), 'w', encoding='utf-8', newline='\n') as f:
                f.write(mtl)
            for fn, data in pngs.items():
                with open(os.path.join(folder, fn), 'wb') as f:
                    f.write(data)
        except Exception as e:
            messagebox.showerror('Export model', str(e))
            return
        text = f"{info['shapes']} shape(s), {info['polys']:,} polygon(s) exported with their materials and {len(pngs)} texture file(s)."
        if info['notes']:
            text += '\n\n' + '\n'.join(info['notes'])
        messagebox.showinfo('Export model', text)

    def import_model(self):
        if self.cur is None:
            return
        file = filedialog.askopenfilename(filetypes=[('Wavefront OBJ', '*.obj')])
        if not file:
            return
        try:
            with open(file, encoding='utf-8', errors='replace') as f:
                text = f.read()
            out, rep = obj_import(self.file(*self.cur), text)
        except Exception as e:
            messagebox.showerror('Import model', str(e))
            return
        notes = '\n'.join(rep['warnings'][:12]) + (f"\nand {len(rep['warnings']) - 12} more" if len(rep['warnings']) > 12 else '')
        if out is None:
            messagebox.showinfo('Import model', 'Nothing changed: the shapes of this file are the same as in the ROM.' + ('\n\n' + notes if notes else ''))
            return
        if out == self.session.subfiles(self.cur[0])[self.cur[1]]:
            self.new.pop(self.cur, None)
        else:
            self.new[self.cur] = out
        try:
            self.read_textures()
        except Exception as e:
            messagebox.showerror('Import model', f'The model was imported but its textures cannot be read any more: {e}')
        self.fill()
        self.pick()
        self.show_model(keep=True)
        lines = [f"{len(rep['shapes'])} shape(s) rebuilt:"]
        lines += [f'   {name}: {old} to {new} polygons' for name, old, new in rep['shapes'][:12]]
        if len(rep['shapes']) > 12:
            lines.append(f"   and {len(rep['shapes']) - 12} more")
        lines.append(f"Model data: {rep['size'][0]:,} to {rep['size'][1]:,} bytes.")
        if notes:
            lines += ['', notes]
        (messagebox.showwarning if rep['warnings'] else messagebox.showinfo)('Import model', '\n'.join(lines))

    # ----- revert

    def revert(self):
        if self.cur and self.new.pop(self.cur, None) is not None:
            keep = self.cur
            self.fill()
            self.cur = None
            self.tree.selection_set(keep[0])
            self.select()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert models', f'Revert {len(self.new)} changed model(s)?'):
            self.new.clear()
            self.fill()
            if self.cur:
                keep = self.cur
                self.cur = None
                self.tree.selection_set(keep[0])
                self.select()

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
                notes.append(f'Model file {path} does not exist in this ROM: skipped.')
                continue
            for i, data in subs.items():
                if i < len(have) and data[:4] == have[i][:4] == b'BMD0':
                    self.new[(path, i)] = data
                else:
                    notes.append(f'Model {path} #{i} does not fit this ROM: skipped.')
        self.fill()
        if self.cur:
            keep = self.cur
            self.cur = None
            self.tree.selection_set(keep[0])
            self.select()
        return notes

    def summary(self):
        return f'{len({p for p, _ in self.new})} changed' if self.new else 'Unchanged'
