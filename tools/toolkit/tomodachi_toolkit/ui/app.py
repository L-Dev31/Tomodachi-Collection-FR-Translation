"""The window: the tabs, the ROM that is open, and what needs all the tabs (patch, BPS export, project file)."""
import tkinter as tk
from tkinter import filedialog, messagebox

from ..core.binary import u32
from ..core.bps import bps_apply, bps_make, bps_meta
from ..patcher import patch
from ..project import PROJECT_MARK, project_dump, project_load
from .player import AudioPlayer
from .session import Session
from .pages import Pages
from .tabs import GROUPS
from .theme import BG, DARK, apply_theme, font


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Tomodachi Location Toolkit')
        self.configure(bg=BG)
        self.minsize(640, 600)
        self.geometry('920x720')
        apply_theme(self)
        self.session = None
        self.player = AudioPlayer()
        self.ready = False
        self.pages = Pages(self, GROUPS, self.tab_shown)
        self.pages.pack(fill='both', expand=True, padx=12, pady=(12, 0))
        self.tabs = self.pages.tabs
        self.rom_tab = self.tabs[0]
        self.rom_tab.add_summary(self.tabs)
        footer = tk.Frame(self, bg=BG, pady=10)
        footer.pack(fill='x')
        tk.Label(footer, text='2026 by L-DEV31 - TomoDS Team', bg=BG, fg=DARK, font=font(9)).pack()
        self.bind_all('<Control-f>', self.find)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.ready = True
        self.lock()
        self.refresh_summary()

    def close(self):
        self.player.close()
        self.destroy()

    # ----- tabs

    def current_tab(self):
        return self.pages.current()

    def show_tab(self, tab):
        """Goes to a tab, whatever group it is in."""
        self.pages.show(tab)

    def tab_shown(self):
        if self.session is not None:
            self.current_tab().on_show()

    def find(self, event=None):
        """Ctrl+F: go to the search box of the tab that has one."""
        entry = getattr(self.current_tab(), 'search', None)
        if self.session is not None and entry is not None:
            entry.focus_set()
            entry.select_range(0, 'end')

    def lock(self):
        """Only the ROM tab works until a ROM is open."""
        on = self.session is not None
        for tab in self.tabs[1:]:
            self.pages.set_enabled(tab, on)
        self.rom_tab.set_enabled(on)

    def refresh_summary(self):
        if not self.ready:
            return
        for tab in self.tabs:
            line = self.rom_tab.lines.get(tab.key)
            if line is not None:
                line.set(tab.summary())

    def log(self, text):
        self.rom_tab.status.config(text=text)
        self.update()

    # ----- the ROM

    def open_rom(self):
        path = filedialog.askopenfilename(filetypes=[('Nintendo DS ROM', '*.nds')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                session = Session(path, f.read())
        except Exception as e:
            messagebox.showerror('Not a Tomodachi ROM', str(e))
            return
        self.player.stop()
        self.session = session
        for tab in self.tabs:
            tab.on_rom()
        self.lock()
        self.refresh_summary()
        self.tab_shown()

    def build_cfg(self):
        """What every tab changed, as the configuration of patch(). Shows the problem and returns None when a tab refuses."""
        cfg = {}
        for tab in self.tabs:
            if not tab.key:
                continue
            try:
                part = tab.patch_config()
            except ValueError as e:
                messagebox.showerror(tab.title, str(e))
                return None
            if part is not None:
                cfg[tab.key] = part
        return cfg

    def patch_rom(self):
        cfg = self.build_cfg()
        if cfg is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.nds', initialfile='tomodachi_patched.nds')
        if not out:
            return
        try:
            result = patch(self.session.data, cfg, self.log)
            with open(out, 'wb') as f:
                f.write(result)
            self.log('Done')
        except Exception as e:
            self.log('')
            messagebox.showerror('Patch failed', str(e))

    # ----- BPS patches

    def export_bps(self):
        cfg = self.build_cfg()
        if cfg is None:
            return
        out = filedialog.asksaveasfilename(defaultextension='.bps', initialfile='tomodachi.bps', filetypes=[('BPS patch (Flips)', '*.bps')])
        if not out:
            return
        try:
            src = self.session.data
            tgt = patch(src, cfg, self.log)
            self.log('Building BPS patch')
            bps = bps_make(src, tgt)
            if bps_apply(src, bps) != tgt:
                raise RuntimeError('Patch check failed')
            with open(out, 'wb') as f:
                f.write(bps)
            self.log(f'Patch saved ({len(bps) / 1024:,.0f} KB)')
        except Exception as e:
            self.log('')
            messagebox.showerror('Export failed', str(e))

    # ----- project files

    def save_project(self):
        try:
            parts = {tab.key: tab.project_part() for tab in self.tabs if tab.key}
        except ValueError as e:
            messagebox.showerror('Save project', str(e))
            return
        out = filedialog.asksaveasfilename(defaultextension='.tomods', initialfile='tomodachi.tomods', filetypes=[('Toolkit project', '*.tomods')])
        if not out:
            return
        try:
            source = {'crc32': self.session.crc32, 'name': self.session.name}
            blob = project_dump(parts['currency'], parts['keyboard'], parts['meta'], parts['bmg'], parts['images'],
                                parts['models'], parts['audio'], parts['speech'], source)
            with open(out, 'wb') as f:
                f.write(blob)
            self.log(f'Project saved ({len(blob) / 1024:,.0f} KB)')
        except Exception as e:
            self.log('')
            messagebox.showerror('Save project', str(e))

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[('Toolkit project', '*.tomods'), ('BPS patch with a project inside (older toolkit)', '*.bps')])
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                blob = f.read()
            crc = None
            if path.lower().endswith('.bps'):
                meta = bps_meta(blob)
                if not meta.startswith(PROJECT_MARK):
                    messagebox.showinfo('No project inside', 'This patch holds no toolkit project. Flips applies BPS patches; the toolkit opens the projects (.tomods) and the patches of older versions that carry one.')
                    return
                crc, blob = u32(blob, len(blob) - 12), meta
            proj = project_load(blob)
            crc = proj['source'].get('crc32', crc)
            if crc is not None and crc != self.session.crc32:
                if not messagebox.askyesno('Different ROM', 'The open ROM is not the one this project was made from. Settings can still be restored, but check the result.\n\nContinue?'):
                    return
            notes = self.restore_project(proj)
        except Exception as e:
            messagebox.showerror('Open project', str(e))
            return
        self.log('Project restored')
        if notes:
            messagebox.showwarning('Project restored with notes', '\n'.join(notes))

    def restore_project(self, proj):
        """Puts every part of a loaded project back in its tab. Returns the notes of what could not be restored."""
        notes = []
        for tab in self.tabs:
            if tab.key:
                notes += tab.restore(proj[tab.key])
        self.refresh_summary()
        return notes
