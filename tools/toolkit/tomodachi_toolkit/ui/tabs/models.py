"""Models tab: the 3D models of the game. Left, the archives of the ROM as in the Images tab. At the right, the model plays on top; below,
the files of the selected archive as a tree and a picture of what is selected in it. A right click on a row exports or replaces it."""
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.png import png_read, png_write
from ...features.models.actions import READERS, model_actions, shared_actions
from ...features.models.anim import bca_animations
from ...features.models.bmd import TEX_FORMATS, bmd_textures
from ...features.models.geometry import mdl_models
from ...features.models.obj_export import obj_export, obj_ident
from ...features.models.obj_import import obj_import
from ...features.models.animedit import sheets_of
from ...features.models.tables import palette_picture
from ...features.models.textures import tex_encode, tex_render
from ..animview import AnimView
from ..modelview import ModelView
from ..theme import BROWN, PANEL, SAND
from ..widgets import RIGHT, ImageView, popup, tree_with_scrollbar
from .listing import ListingTab


MODEL_FOLDERS = ('/Mdl/', '/Job/', '/News/', '/Scn/Affn/', '/Scn/Mrg/')   # the folders of the ROM where models are
KINDS = {b'BMD0': ('bmd', 'Model', 'Shape'), b'BCA0': ('bca', 'Skeleton animations', 'Skeleton animation'),
         b'BTA0': ('bta', 'Texture scroll animations', 'Texture scroll animation'), b'BTP0': ('btp', 'Texture swap animations', 'Texture swap animation'),
         b'BVA0': ('bva', 'Part visibility animations', 'Part visibility animation'), b'BMA0': ('bma', 'Material colour animations', 'Material colour animation'),
         b'RLCN': ('nclr', 'Palette (NCLR)', ''), b'RGCN': ('ncgr', 'Tile graphics (NCGR)', ''), b'RCSN': ('nscr', 'Screen (NSCR)', ''),
         b'RECN': ('ncer', 'Cells (NCER)', ''), b'RNAN': ('nanr', 'Cell animations (NANR)', '')}
ANIMATIONS = dict(READERS)                                                  # magic of an animation file -> function that reads it
MODEL_PARTS = ('cat', 'shape', 'texture', 'palette')                        # rows that belong to a BMD0 file


def kind_of(data):
    """(extension, what the file is) of a sub file of an archive, from its magic."""
    magic = bytes(data[:4])
    if magic in KINDS:
        return KINDS[magic][:2]
    word = magic.split(b'\0')[0]
    return (word.decode().lower(), f'{word.decode()} data') if len(word) >= 2 and word.isalnum() else ('bin', 'Raw data')


def size_text(n):
    return f'{n / 1024:.1f} KB' if n >= 1024 else f'{n} bytes'


def file_stem(name):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


def write_obj_files(out, stem, obj, mtl, pngs):
    """Writes an exported model (obj_export): the .obj at `out`, and beside it stem.mtl and the PNG files of the textures."""
    folder = os.path.dirname(out)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(obj)
    with open(os.path.join(folder, stem + '.mtl'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(mtl)
    for name, data in pngs.items():
        with open(os.path.join(folder, name), 'wb') as f:
            f.write(data)


class Patched:
    """The session with the changed sub files in the place of the ones of the ROM: what the animations are read from, so that the model plays
    what is being edited."""

    def __init__(self, tab):
        self.tab = tab

    @property
    def files(self):
        return self.tab.session.files

    def subfiles(self, path):
        return [self.tab.new.get((path, i), f) for i, f in enumerate(self.tab.session.subfiles(path))]


class ModelsTab(ListingTab):
    key = 'models'
    title = 'Models'
    heading = 'Models'

    def build(self):
        self.items, self.nodes, self.pending, self.new = [], {}, set(), {}
        self.shared = []
        self.arch, self.cur, self.texs, self.pals = None, None, [], []       # arch: the archive on show; cur: (archive, sub file) of the BMD0 on show
        right = self.build_listing(weights=(1, 4), batch=(self.export_all, self.import_all, self.revert_all))
        self.tree.bind('<<TreeviewSelect>>', self.pick_archive)
        self.build_menu(lambda iid: self.entries({'kind': 'archive', 'path': iid[2:]}) if iid.startswith('a:') else [])
        split = ttk.Panedwindow(right, orient='vertical')
        split.pack(fill='both', expand=True)
        self.model_view = ModelView(split, height=230)
        bottom = ttk.Panedwindow(split, orient='horizontal')
        split.add(self.model_view, weight=3)
        split.add(bottom, weight=2)
        left, self.stage = ttk.Frame(bottom), ttk.Frame(bottom)
        bottom.add(left, weight=2)
        bottom.add(self.stage, weight=3)
        self.inner = tree_with_scrollbar(left, show='tree headings', columns=('type', 'size'), selectmode='browse', height=7)      # the files of the archive
        for column, text, width in (('#0', 'File', 120), ('type', 'Type', 150), ('size', 'Size', 70)):
            self.inner.heading(column, text=text)
            self.inner.column(column, width=width, anchor='e' if column == 'size' else 'w')
        self.inner.bind('<<TreeviewSelect>>', self.select)
        self.inner.bind('<<TreeviewOpen>>', self.opened)
        self.inner.bind(RIGHT, self.menu)
        self.viewer = ImageView(self.stage, width=300, height=150)
        self.shape_view = ModelView(self.stage, width=300, height=150, controls=False)
        self.dump_box = ttk.Frame(self.stage)                    # the bytes of a file that has no other view
        self.dump = tk.Text(self.dump_box, wrap='none', height=6, font=('Consolas', 9), bg=PANEL, fg=BROWN, relief='flat', highlightthickness=1,
                            highlightbackground=SAND, state='disabled')
        dump_scroll = ttk.Scrollbar(self.dump_box, orient='vertical', command=self.dump.yview)
        self.dump.configure(yscrollcommand=dump_scroll.set)
        self.dump.pack(side='left', fill='both', expand=True)
        dump_scroll.pack(side='right', fill='y')
        self.anim_view = AnimView(self.stage, self.anim_changed)
        self.patched, self.edited = Patched(self), None          # the files as they will be patched; (archive, sub file) of the animation being edited

    # ----- the archives

    def on_rom(self):
        self.new, self.arch, self.cur = {}, None, None
        self.items = [{'path': p, 'name': p.rsplit('/', 1)[1].removesuffix('_LZ.bin'), 'group': p.rsplit('/', 1)[0].strip('/')}
                      for p in sorted(self.session.files) if p.startswith(MODEL_FOLDERS)]
        self.model_view.clear()
        self.build_inner()
        self.show_stage()
        self.fill()

    def visible(self):
        """The archives of the list as the search and Modified only leave them."""
        q, only, changed = self.query.get().strip().lower(), self.only.get(), {p for p, _ in self.new}
        return [it for it in self.items if (not q or q in it['name'].lower() or q in it['group'].lower()) and (not only or it['path'] in changed)]

    def fill(self):
        tree = self.tree
        opened = {i for i in tree.get_children() if tree.item(i, 'open')}
        tree.delete(*tree.get_children())
        searching, groups, listed, changed = bool(self.query.get().strip()) or self.only.get(), {}, self.visible(), {p for p, _ in self.new}
        for it in listed:
            if it['group'] not in groups:
                gid = 'g:' + it['group']
                groups[it['group']] = tree.insert('', 'end', iid=gid, text=it['group'], open=searching or gid in opened)
            mod = it['path'] in changed
            tree.insert(groups[it['group']], 'end', iid='a:' + it['path'], text=('● ' if mod else '') + it['name'], tags=('mod',) if mod else ())
        self.count.set(f'{len(listed)} / {len(self.items)}   ● {len(changed)} changed' if self.items else '')
        if self.arch is not None and tree.exists('a:' + self.arch):
            tree.selection_set('a:' + self.arch)
            tree.see('a:' + self.arch)
        self.changed()

    def pick_archive(self, event=None):
        sel = self.tree.selection()
        if sel and sel[0].startswith('a:') and sel[0][2:] != self.arch:
            self.show_archive(sel[0][2:])
            self.sync_revert()

    def show_archive(self, path):
        """Puts an archive on show: its files in the tree below the model, its model in the 3D view."""
        self.arch = path
        self.build_inner()
        self.load_archive()

    def load_archive(self):
        """Puts the model of the archive on show in the 3D view (read again), and clears the picture beside the files."""
        try:
            idx = self.model_index(self.arch)
        except Exception:
            idx = None
        self.load((self.arch, idx) if idx is not None else None, True)
        self.show_stage()

    def refresh_archive(self):
        """The data of the archive on show changed a lot (a project, a folder of files): its files and its model are read again."""
        if self.arch is not None:
            self.build_inner(keep=True)
            self.load_archive()
            self.select()

    def mark(self, path):
        """The dots of the rows of an archive."""
        mod = any(p == path for p, _ in self.new)
        if self.tree.exists('a:' + path):
            self.tree.item('a:' + path, text=('● ' if mod else '') + path.rsplit('/', 1)[1].removesuffix('_LZ.bin'), tags=('mod',) if mod else ())
        for iid, info in self.nodes.items():
            if info['kind'] == 'file' and info['path'] == path:
                mod = self.is_changed(info)
                self.inner.item(iid, text=('● ' if mod else '') + info['label'], tags=('mod',) if mod else ())

    # ----- the files of the archive

    def build_inner(self, keep=False):
        """Makes the tree of the files of the archive on show. keep: the same archive again, what was open and selected stays so."""
        tree = self.inner
        opened = [i for i in self.nodes if tree.exists(i) and tree.item(i, 'open')] if keep else []
        picked = tree.selection() if keep else ()
        tree.delete(*tree.get_children())
        self.nodes, self.pending = {}, set()
        if self.arch is None:
            return
        try:
            count = len(self.session.subfiles(self.arch))
        except Exception:
            return
        for i in range(count):
            data = self.file(self.arch, i)
            magic, (ext, what) = bytes(data[:4]), kind_of(data)
            self.add('', f'f:{i}', f'{i:02d}.{ext}', {'kind': 'file', 'path': self.arch, 'idx': i, 'magic': magic},
                     magic == b'BMD0' or magic in ANIMATIONS, what, size_text(len(data)))
        self.add_shared()
        for iid in opened if keep else sorted(self.pending):                # the first time every file that has something in it is open
            if tree.exists(iid):
                if iid in self.pending:
                    self.expand(iid)
                tree.item(iid, open=True)
        if picked and tree.exists(picked[0]):
            tree.selection_set(picked[0])

    def add_shared(self):
        """A model without skeleton animations of its own plays the shared ones of the Mii skeleton (in /Mdl/Ica): they are listed too."""
        try:
            idx = self.model_index(self.arch)
            if idx is None or any(i['magic'] == b'BCA0' for i in self.nodes.values() if i['kind'] == 'file'):
                return
            count = len(mdl_models(self.file(self.arch, idx))[0]['nodes'])
            actions = shared_actions(self.patched).get(count, [])
        except Exception:
            return
        if actions:
            self.add('', 'shared', 'Shared animations', {'kind': 'shared', 'path': self.arch, 'label': ''}, True, 'Skeleton animations of the Mii', f'{len(actions)} animations')
            self.shared = actions

    def add(self, parent, iid, label, info, folder, what='', size=''):
        """A row of the tree of files: its name, what it is, its size. folder: it has rows below it, made when it is opened."""
        info['label'] = label
        self.nodes[iid] = info
        mod = self.is_changed(info)
        self.inner.insert(parent, 'end', iid=iid, text=('● ' if mod else '') + label, values=(what, size), tags=('mod',) if mod else ())
        if folder:
            self.inner.insert(iid, 'end', iid=iid + '|')       # makes the arrow
            self.pending.add(iid)

    def is_changed(self, info):
        return info['kind'] == 'file' and (info['path'], info['idx']) in self.new

    def opened(self, event=None):
        iid = self.inner.focus()
        if iid in self.pending:
            self.expand(iid)

    def expand(self, iid):
        """Makes the rows below a row (the first time it is opened)."""
        self.pending.discard(iid)
        self.inner.delete(*self.inner.get_children(iid))
        info = self.nodes[iid]
        try:
            if info['kind'] == 'shared':
                for k, a in enumerate(self.shared):
                    self.add(iid, f'shared:{k}', a.name, {'kind': 'sharedanim', 'path': info['path'], 'k': k, 'name': a.name}, False, 'Skeleton animation', f'{a.frames} frames')
            elif info['kind'] == 'file':
                self.expand_file(iid, info)
            else:
                self.expand_category(iid, info)
        except Exception:
            pass                                             # a file that cannot be read has nothing below it

    def expand_file(self, iid, info):
        path, idx, b = info['path'], info['idx'], self.file(info['path'], info['idx'])
        if info['magic'] == b'BMD0':
            texs, pals = bmd_textures(b)
            counts = {'shapes': sum(len(m['shapes']) for m in mdl_models(b)), 'textures': len(texs), 'palettes': len(pals)}
            for what, n in counts.items():
                if n:
                    self.add(iid, f'{iid}:{what}', what.capitalize(), {'kind': 'cat', 'path': path, 'idx': idx, 'what': what}, True, f'{n} in this model')
        else:
            single = KINDS[info['magic']][2]
            for k, anim in enumerate(ANIMATIONS[info['magic']](b)):
                self.add(iid, f'{iid}:{k}', anim.name, {'kind': 'anim', 'path': path, 'idx': idx, 'k': k, 'name': anim.name}, False, single, f'{anim.frames} frames')

    def expand_category(self, iid, info):
        path, idx, what = info['path'], info['idx'], info['what']
        b = self.file(path, idx)
        if what == 'shapes':
            models = mdl_models(b)
            for mi, model in enumerate(models):
                for si, shape in enumerate(model['shapes']):
                    label = shape['name'] if len(models) == 1 else f"{model['name']} / {shape['name']}"
                    self.add(iid, f'{iid}:{mi}:{si}', label, {'kind': 'shape', 'path': path, 'idx': idx, 'model': mi, 'shape': si}, False, 'Shape')
        else:
            texs, pals = bmd_textures(b)
            for t in (texs if what == 'textures' else pals):
                self.add(iid, f'{iid}:{t["name"]}', t['name'], {'kind': what[:-1], 'path': path, 'idx': idx, 'name': t['name']}, False,
                         f"Texture, {TEX_FORMATS.get(t['fmt'], '?')}" if what == 'textures' else 'Palette', f"{t['w']} x {t['h']}" if what == 'textures' else size_text(t['size']))

    # ----- what is on show

    def file(self, path, idx):
        """The sub file as it will be patched: the changed one, else the one of the ROM."""
        return self.new.get((path, idx)) or self.session.subfiles(path)[idx]

    def model_index(self, path):
        """Which sub file of an archive holds its 3D model (None when none does: animation or effect data only)."""
        return next((i for i in range(len(self.session.subfiles(path))) if self.file(path, i)[:4] == b'BMD0'), None)

    def read_textures(self):
        """The textures of the model as it is now. Where they sit in the file moves when the shapes change size."""
        self.texs, self.pals = bmd_textures(self.file(*self.cur))

    def show_stage(self, widget=None):
        """Puts one of the three views (picture, table, shape) in the place of the others."""
        for w in (self.viewer, self.anim_view, self.shape_view, self.dump_box):
            if w is not widget:
                w.pack_forget()
        if widget is not None:
            widget.pack(fill='both', expand=True)

    def select(self, event=None):
        """A row of the files of the archive was selected: the model follows it, and its picture, table or shape is shown."""
        sel = self.inner.selection()
        info = self.nodes.get(sel[0]) if sel else None
        if info is None:
            return
        kind, path = info['kind'], info['path']
        if kind in MODEL_PARTS or (kind == 'file' and info['magic'] == b'BMD0'):
            idx = info['idx']
        else:
            try:
                idx = self.model_index(path)
            except Exception:
                idx = None
        self.load((path, idx) if idx is not None else None)
        self.sync_revert()
        if kind in ('texture', 'palette', 'shape') and self.cur is not None or kind in ('anim', 'sharedanim'):
            getattr(self, 'show_' + kind)(info)
        elif kind == 'file' and info['magic'] != b'BMD0' and info['magic'] not in ANIMATIONS:
            self.show_dump(info)
        else:
            self.show_stage()

    def load(self, key, force=False):
        """Puts the BMD0 key=(archive, sub file) in the 3D view (None: no model). It stays when it is already there, unless force."""
        if key == self.cur and not force:
            return
        self.cur = key
        self.texs, self.pals = [], []
        if key is None:
            self.model_view.clear()
            return
        try:
            self.read_textures()
        except Exception:
            pass
        self.show_model()

    def show_model(self, keep=False):
        """Draws the model as it is now (the changed one, else the one of the ROM)."""
        if self.cur is not None:
            path = self.cur[0]
            self.model_view.load(self.file(*self.cur), lambda scene: model_actions(self.patched, path, scene), keep=keep)

    def show_texture(self, info):
        t = next((t for t in self.texs if t['name'] == info['name']), None)
        if t is not None:
            self.show_stage(self.viewer)
            self.viewer.show(*tex_render(self.file(*self.cur), t, self.pals), refit=True)

    def show_palette(self, info):
        p = next((p for p in self.pals if p['name'] == info['name']), None)
        if p is not None:
            self.show_stage(self.viewer)
            self.viewer.show(*palette_picture(self.file(*self.cur), p), refit=True)

    def show_shape(self, info):
        self.show_stage(self.shape_view)
        self.shape_view.load(self.file(*self.cur), None, model=info['model'], only=info['shape'])

    def show_dump(self, info):
        """The first bytes of a file that has no other view: offset, bytes, characters."""
        data = bytes(self.file(info['path'], info['idx'])[:4096])
        lines = [f'{o:04X}  {data[o:o + 16].hex(" "):<47}  {"".join(chr(b) if 32 <= b < 127 else "." for b in data[o:o + 16])}' for o in range(0, len(data), 16)]
        self.dump.configure(state='normal')
        self.dump.delete('1.0', 'end')
        self.dump.insert('1.0', '\n'.join(lines))
        self.dump.configure(state='disabled')
        self.show_stage(self.dump_box)

    def show_sharedanim(self, info):
        """A shared animation of the Mii skeleton: it is a file of /Mdl/Ica, and that is where a change goes."""
        action = self.shared[info['k']]
        layer = action.layers[0]
        subs = self.patched.subfiles(action.source)
        idx = next(i for i, f in enumerate(subs) if f[:4] == b'BCA0' and any(a.name == layer.name for a in bca_animations(f)))
        self.edit_animation(action.source, idx, [a.name for a in bca_animations(subs[idx])].index(layer.name))

    def show_anim(self, info):
        self.edit_animation(info['path'], info['idx'], info['k'])

    def edit_animation(self, path, idx, k):
        """Opens the editor on the animation k of the file (path, idx), and plays it on the model."""
        b = self.file(path, idx)
        magic = bytes(b[:4])
        names = []
        if self.cur is not None:
            models = mdl_models(self.file(*self.cur))
            wanted = len(ANIMATIONS[magic](b)[k].nodes) if magic == b'BCA0' else 0
            names = next(([n['name'] for n in m['nodes']] for m in models if len(m['nodes']) == wanted), [])

        def build(data):
            anim = ANIMATIONS[magic](data)[k]
            return anim, sheets_of(anim, names)
        self.edited = (path, idx)
        self.anim_view.load(b, build)
        self.show_stage(self.anim_view)
        self.model_view.show_action(self.anim_view.anim.name)

    def anim_changed(self, data, anim):
        """A value of the animation was changed in the editor: the file is kept, the model plays the new animation."""
        key = self.edited
        self.keep(key, data)
        self.mark(key[0])
        if key[0].startswith('/Mdl/Ica/'):
            self.patched.__dict__.pop('shared_actions', None)         # the shared animations are read again the next time a model is shown
        self.model_view.replace_layer(anim)
        self.changed()

    def touch(self, path, rebuild=False):
        """Shows what changed in the files of an archive: the dots, the files tree, the model on show, the picture."""
        if rebuild and path == self.arch:
            self.build_inner(keep=True)
        self.mark(path)
        if self.cur is not None and self.cur[0] == path:
            try:
                self.read_textures()
            except Exception:
                self.texs, self.pals = [], []
            self.show_model(keep=True)
            self.select()
        self.changed()

    def keep(self, key, data):
        """Makes `data` the file (archive, sub file) will have; the ROM's own file is no change."""
        if data == self.session.subfiles(key[0])[key[1]]:
            self.new.pop(key, None)
        else:
            self.new[key] = data

    # ----- the right click

    def menu(self, event):
        iid = self.inner.identify_row(event.y)
        if iid:
            self.inner.selection_set(iid)
            self.select()
            entries = self.entries(self.nodes[iid])
            if entries:
                popup(self.inner, event, entries)

    def entries(self, info):
        kind, path, out = info['kind'], info['path'], []
        if kind == 'texture':
            out += [('Export PNG...', lambda: self.export_texture(info)), ('Replace with PNG...', lambda: self.replace_texture(info))]
        if self.cur is not None and (kind in ('archive', 'cat', 'shape') or kind == 'file' and info['magic'] == b'BMD0'):
            out += [('Export OBJ...', self.export_model), ('Import OBJ...', self.import_model)]
            if self.texs:
                out += [('Export all PNG...', self.export_textures)]
        if kind in ('file', 'anim'):
            file = info if kind == 'file' else {**info, 'magic': bytes(self.file(path, info['idx'])[:4])}
            out += [('Export file...', lambda: self.export_file(file)), ('Replace file...', lambda: self.replace_file(file))]
        if kind in ('anim', 'sharedanim'):
            out += [('Export table...', lambda: self.table_action(info, 'export')), ('Import table...', lambda: self.table_action(info, 'import'))]
        own = (path, info['idx']) if kind in ('file', 'anim') else self.cur
        keys = [k for k in self.new if k[0] == path and (kind == 'archive' or k == own)]
        if kind == 'sharedanim':
            keys = [k for k in [self.edited] if k in self.new]
        if keys:
            out += [None, ('Revert', lambda: self.revert(keys))]
        return out

    # ----- textures

    def table_action(self, info, what):
        """The menu of an animation: it is shown in the editor, then its table is exported or imported there (what is 'export' or 'import')."""
        if info['kind'] == 'sharedanim':
            self.show_sharedanim(info)
        else:
            self.show_anim(info)
        getattr(self.anim_view, what + '_table')()

    def export_texture(self, info):
        t = next((t for t in self.texs if t['name'] == info['name']), None)
        out = filedialog.asksaveasfilename(defaultextension='.png', initialfile=file_stem(info['name']) + '.png', filetypes=[('PNG image', '*.png')])
        if t is None or not out:
            return
        try:
            with open(out, 'wb') as f:
                f.write(png_write(*tex_render(self.file(*self.cur), t, self.pals)))
        except Exception as e:
            messagebox.showerror('Export texture', str(e))

    def replace_texture(self, info):
        t = next((t for t in self.texs if t['name'] == info['name']), None)
        path = filedialog.askopenfilename(filetypes=[('PNG image', '*.png')])
        if t is None or not path:
            return
        try:
            with open(path, 'rb') as f:
                w, h, rgba = png_read(f.read())
            new, snapped = tex_encode(self.file(*self.cur), t, self.pals, w, h, rgba)
        except Exception as e:
            messagebox.showerror('Replace texture', str(e))
            return
        self.keep(self.cur, new)
        self.touch(self.cur[0])
        if snapped:
            messagebox.showwarning('Replace texture', f"{t['name']} was imported.\n\n{snapped:,} pixel(s) were snapped to the closest palette colour.")

    def export_textures(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        try:
            b = self.file(*self.cur)
            for t in self.texs:
                with open(os.path.join(folder, file_stem(t['name']) + '.png'), 'wb') as f:
                    f.write(png_write(*tex_render(b, t, self.pals)))
        except Exception as e:
            messagebox.showerror('Export textures', str(e))
            return
        messagebox.showinfo('Export textures', f'{len(self.texs)} texture(s) exported to {folder}')

    # ----- shapes

    def export_model(self):
        name = self.cur[0].rsplit('/', 1)[1].removesuffix('_LZ.bin')
        out = filedialog.asksaveasfilename(defaultextension='.obj', initialfile=file_stem(name) + '.obj', filetypes=[('Wavefront OBJ', '*.obj')])
        if not out:
            return
        stem = obj_ident(os.path.splitext(os.path.basename(out))[0])
        try:
            obj, mtl, pngs, info = obj_export(self.file(*self.cur), stem)
            write_obj_files(out, stem, obj, mtl, pngs)
        except Exception as e:
            messagebox.showerror('Export model', str(e))
            return
        text = f"{info['shapes']} shape(s), {info['polys']:,} polygon(s) exported with their materials and {len(pngs)} texture file(s)."
        if info['notes']:
            text += '\n\n' + '\n'.join(info['notes'])
        messagebox.showinfo('Export model', text)

    def import_model(self):
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
        self.keep(self.cur, out)
        self.touch(self.cur[0])
        lines = [f"{len(rep['shapes'])} shape(s) rebuilt:"]
        lines += [f'   {name}: {old} to {new} polygons' for name, old, new in rep['shapes'][:12]]
        if len(rep['shapes']) > 12:
            lines.append(f"   and {len(rep['shapes']) - 12} more")
        lines.append(f"Model data: {rep['size'][0]:,} to {rep['size'][1]:,} bytes.")
        if notes:
            lines += ['', notes]
        (messagebox.showwarning if rep['warnings'] else messagebox.showinfo)('Import model', '\n'.join(lines))

    # ----- files

    def export_file(self, info):
        out = filedialog.asksaveasfilename(initialfile=f"{info['path'].rsplit('/', 1)[1].removesuffix('_LZ.bin')}_{info['idx']:02d}.{kind_of(info['magic'])[0]}")
        if out:
            try:
                with open(out, 'wb') as f:
                    f.write(self.file(info['path'], info['idx']))
            except OSError as e:
                messagebox.showerror('Export file', str(e))

    def replace_file(self, info):
        path = filedialog.askopenfilename()
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                data = f.read()
            if data[:4] != info['magic']:
                raise ValueError(f"This file is not a {info['magic'].decode('latin1')} file.")
        except (OSError, ValueError) as e:
            messagebox.showerror('Replace file', str(e))
            return
        self.keep((info['path'], info['idx']), data)
        self.touch(info['path'], True)

    # ----- revert

    def selected_keys(self):
        """The changed files that the row selected in the files of the archive stands for (the whole archive when none is selected)."""
        sel = self.inner.selection()
        info = self.nodes.get(sel[0]) if sel else {'kind': 'archive', 'path': self.arch}
        if info is None or self.arch is None:
            return []
        if info['kind'] == 'sharedanim':
            return [k for k in [self.edited] if k in self.new]
        own = (info['path'], info['idx']) if info['kind'] in ('file', 'anim') else self.cur
        return [k for k in self.new if k[0] == self.arch and (info['kind'] == 'archive' or k == own)]

    def item_changed(self):
        return bool(self.selected_keys())

    def revert(self, keys=None):
        keys = self.selected_keys() if keys is None else keys
        for key in keys:
            self.new.pop(key, None)
        for path in {p for p, _ in keys}:
            self.touch(path, True)
        if any(p.startswith('/Mdl/Ica/') for p, _ in keys):
            self.patched.__dict__.pop('shared_actions', None)
        self.select()

    def revert_all(self):
        if self.new and messagebox.askyesno('Revert models', f'Revert {len(self.new)} changed file(s)?'):
            self.revert(list(self.new))

    # ----- batch

    def export_all(self):
        """The listed models as OBJ files (with their materials and textures) in a folder that has the folders of the ROM (Mdl, Job...)."""
        items = self.visible()
        if not items:
            return
        if len(items) > 100 and not messagebox.askyesno('Export models', f'Export {len(items):,} models? Each one is a few files, it can take a while.'):
            return
        folder = filedialog.askdirectory(title='Folder to export the listed models to')
        if not folder:
            return
        done = 0
        try:
            for n, it in enumerate(items):
                if n % 5 == 0:
                    self.count.set(f'Exporting {n} / {len(items)}...')
                    self.update_idletasks()
                idx = self.model_index(it['path'])
                if idx is None:
                    continue
                where = os.path.join(folder, *it['group'].split('/'))
                os.makedirs(where, exist_ok=True)
                stem = obj_ident(file_stem(it['name']))
                obj, mtl, pngs, info = obj_export(self.file(it['path'], idx), stem)
                write_obj_files(os.path.join(where, stem + '.obj'), stem, obj, mtl, pngs)
                done += 1
        except Exception as e:
            messagebox.showerror('Export models', str(e))
        self.fill()
        messagebox.showinfo('Export models', f'{done} model(s) exported to {folder}, in folders named like the ones of the ROM.')

    def find_models(self, folder):
        """[(model file of the ROM, folder, name of its .obj)] for the .obj files a folder has, where the export puts them (in the folder
        of its group) or beside each other."""
        found = []
        for it in self.items:
            stem = obj_ident(file_stem(it['name']))
            for where in (os.path.join(folder, *it['group'].split('/')), folder):
                have = {n.lower(): n for n in os.listdir(where)} if os.path.isdir(where) else {}
                if stem.lower() + '.obj' in have:
                    found.append((it, where, have[stem.lower() + '.obj']))
                    break
        return found

    def import_all(self):
        """The models of a folder: the OBJ files, and the PNG files beside them that the export made for their textures. What looks like
        what the ROM has is no change."""
        folder = filedialog.askdirectory(title='Folder with the OBJ files of the models (and their PNG textures)')
        if not folder:
            return
        models = shapes = textures = same = 0
        errors, notes = [], 0
        for it, where, obj_name in self.find_models(folder):
            idx = self.model_index(it['path'])
            if idx is None:
                continue
            key = (it['path'], idx)
            before = self.new.get(key)
            try:
                with open(os.path.join(where, obj_name), encoding='utf-8', errors='replace') as f:
                    out, rep = obj_import(self.file(*key), f.read())
                notes += len(rep['warnings'])
                if out is not None:
                    self.keep(key, out)
                    shapes += len(rep['shapes'])
                textures += self.import_pngs(key, where, os.path.splitext(obj_name)[0])
            except Exception as e:
                errors.append(f'{obj_name}: {e}')
                continue
            if self.new.get(key) != before:
                models += 1
            else:
                same += 1
        self.fill()
        self.refresh_archive()
        text = f'{models} model(s) imported ({shapes} shape(s) rebuilt, {textures} texture(s))' + (f', {same} the same as they are now' if same else '') + '.'
        if notes:
            text += f'\n{notes} warning(s): import one model by itself to read them.'
        messagebox.showinfo('Import models', text + ('\n\nSkipped:\n' + '\n'.join(errors[:12]) if errors else ''))

    def import_pngs(self, key, folder, stem):
        """The PNG files the export made for the textures of a model (stem_texture.png) that differ from the texture now. Returns how many."""
        have = {n.lower(): n for n in os.listdir(folder)}
        done = 0
        for name in [t['name'] for t in bmd_textures(self.file(*key))[0]]:
            file = have.get(f'{stem}_{obj_ident(name)}.png'.lower())
            if file is None:
                continue
            current = self.file(*key)                          # where the textures sit moves when a texture or a shape changes size
            texs, pals = bmd_textures(current)
            t = next(t for t in texs if t['name'] == name)
            with open(os.path.join(folder, file), 'rb') as f:
                w, h, rgba = png_read(f.read())
            now = tex_render(current, t, pals)
            if (now[0], now[1]) == (w, h) and bytes(now[2]) == bytes(rgba):
                continue                                       # the picture the texture has already
            new, _ = tex_encode(current, t, pals, w, h, rgba)
            if new != current:
                self.keep(key, new)
                done += 1
        return done

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
                if i < len(have) and data[:4] == have[i][:4]:
                    self.new[(path, i)] = data
                else:
                    notes.append(f'Model {path} #{i} does not fit this ROM: skipped.')
        self.fill()
        self.refresh_archive()
        return notes

    def summary(self):
        return f'{len({p for p, _ in self.new})} changed' if self.new else 'Unchanged'
