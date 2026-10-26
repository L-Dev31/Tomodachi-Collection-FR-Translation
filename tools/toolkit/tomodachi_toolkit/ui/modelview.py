"""A 3D view of a model that plays its animations. Drag to turn, wheel to zoom, right drag to move, double click to start over."""
import sys
import time
import tkinter as tk
from tkinter import ttk

from ..features.models.geometry import mdl_models
from ..features.models.render import Scene, render, to_ppm
from .theme import CANVAS, MUTED, SAND, font

FPS = 30                       # speed of the animations
BACKGROUND = int(CANVAS[1:], 16)
SLOW, FAST = 0.06, 0.02        # seconds a picture may take before it is drawn smaller, and under which it is drawn bigger again
ALL = 'All models'
NO_ACTION = 'No animation'


class ModelView(ttk.Frame):
    """Shows the models of a BMD0 file. `load` takes the file and a function that finds the animations of the models on show."""

    def __init__(self, master, width=420, height=300):
        super().__init__(master)
        top = ttk.Frame(self)
        top.pack(fill='x', pady=(0, 4))
        self.model_name = tk.StringVar()
        self.model_label = ttk.Label(top, text='Model')
        self.model_box = ttk.Combobox(top, textvariable=self.model_name, state='readonly', width=22)
        self.model_box.bind('<<ComboboxSelected>>', lambda e: self.pick_model())
        ttk.Label(top, text='Drag to turn   Wheel to zoom   Right drag to move   Double click to reset', foreground=MUTED).pack(side='right')
        self.canvas = tk.Canvas(self, bg=CANVAS, highlightthickness=1, highlightbackground=SAND, width=width, height=height)
        self.canvas.pack(fill='both', expand=True)
        bar = ttk.Frame(self)
        bar.pack(fill='x', pady=(4, 0))
        self.play_text = tk.StringVar(value='Pause')
        self.play_button = ttk.Button(bar, textvariable=self.play_text, style='Soft.TButton', width=7, command=self.toggle)
        self.play_button.pack(side='left')
        self.action_name = tk.StringVar()
        self.action_box = ttk.Combobox(bar, textvariable=self.action_name, state='readonly', width=30)
        self.action_box.pack(side='left', padx=8)
        self.action_box.bind('<<ComboboxSelected>>', lambda e: self.pick_action())
        self.counter = tk.StringVar()
        ttk.Label(bar, textvariable=self.counter, width=11, anchor='e').pack(side='right')
        self.slider = ttk.Scale(bar, from_=0, to=1, orient='horizontal', command=self.scrub)
        self.slider.pack(side='left', fill='x', expand=True)
        self.data, self.fetch, self.scene, self.cam = None, None, None, None
        self.actions, self.action = [], None
        self.models = []
        self.src = tk.PhotoImage(master=self)
        self.dst = tk.PhotoImage(master=self)
        self.item = None
        self.text = ''
        self.scale = 1
        self.playing = False
        self.frame, self.t_ref, self.f_ref = 0.0, 0.0, 0.0
        self.timer, self.queued = None, False
        self.drag = None
        self.settle_timer = None
        self.setting = False
        c = self.canvas
        c.bind('<Configure>', lambda e: self.refresh())
        c.bind('<ButtonPress-1>', lambda e: self.press(e, 'turn'))
        c.bind('<B1-Motion>', self.motion)
        c.bind('<Shift-ButtonPress-1>', lambda e: self.press(e, 'move'))
        for b in (2, 3):
            c.bind('<ButtonPress-%d>' % b, lambda e: self.press(e, 'move'))
            c.bind('<B%d-Motion>' % b, self.motion)
            c.bind('<ButtonRelease-%d>' % b, self.release)
        c.bind('<ButtonRelease-1>', self.release)
        c.bind('<Double-Button-1>', lambda e: self.reset_camera())
        c.bind('<MouseWheel>', self.wheel)
        c.bind('<Button-4>', lambda e: self.zoom(1))
        c.bind('<Button-5>', lambda e: self.zoom(-1))
        self.clear('Select a model in the list.')

    # ----- content

    def clear(self, text=''):
        """Empties the view and shows a line of text in it."""
        self.stop_timer()
        self.data = self.scene = self.cam = self.action = None
        self.actions, self.models = [], []
        self.playing = False
        self.text = text
        self.model_label.pack_forget()
        self.model_box.pack_forget()
        self.canvas.delete('all')
        self.item = None
        self.fill_actions()
        self.draw_text()

    def draw_text(self):
        self.canvas.delete('hint')
        if self.text and self.scene is None:
            w = self.canvas.winfo_width()
            self.canvas.create_text(w // 2, self.canvas.winfo_height() // 2, text=self.text, fill=MUTED, font=font(10), justify='center',
                                    width=max(w - 40, 100), tags='hint')

    def load(self, data, fetch=None, keep=False):
        """Shows the models of the BMD0 file data. fetch(counts) returns (animations, index of the first to play) for the models whose
        numbers of nodes are counts. keep: keep the choice of model, the camera and the animation of the previous file."""
        old = (self.model_name.get(), self.cam, self.action.label if self.action else None, self.frame) if keep and self.scene else None
        self.data, self.fetch = data, fetch
        try:
            self.models = [m['name'] for m in mdl_models(data)]
        except Exception as e:
            self.clear(f'Cannot read this model:\n{e}')
            return
        if not self.models:
            self.clear('No 3D model in this file.')
            return
        names = list(self.models) + ([ALL] if len(self.models) > 1 else [])
        self.model_box.configure(values=names)
        if len(names) > 1:
            self.model_label.pack(side='left')
            self.model_box.pack(side='left', padx=(6, 0))
        else:
            self.model_label.pack_forget()
            self.model_box.pack_forget()
        self.model_name.set(old[0] if old and old[0] in names else names[0])
        self.build(old)

    def pick_model(self):
        self.build(None)

    def build(self, old):
        name = self.model_name.get()
        which = None if name == ALL else self.models.index(name)
        try:
            self.scene = Scene(self.data, which)
        except Exception as e:
            self.scene = None
            self.clear(f'Cannot draw this model:\n{e}')
            return
        self.canvas.delete('hint')
        if old and old[1] is not None:
            self.cam = old[1]
        else:
            self.cam = self.scene.camera()
        counts = {len(self.scene.models[mi]['nodes']) for mi in self.scene.shown}
        try:
            self.actions, first = self.fetch(counts) if self.fetch else ([], 0)
        except Exception:
            self.actions, first = [], 0
        self.fill_actions()
        keep = next((i for i, a in enumerate(self.actions) if old and a.label == old[2]), None)
        self.start(self.actions[keep if keep is not None else first] if self.actions else None, old[3] if old and keep is not None else 0.0)

    # ----- animations

    def fill_actions(self):
        labels = [a.label for a in self.actions] or [NO_ACTION]
        self.action_box.configure(values=labels)
        state = 'readonly' if self.actions else 'disabled'
        self.action_box.configure(state=state)
        self.play_button.state(['!disabled'] if self.actions else ['disabled'])
        self.slider.state(['!disabled'] if self.actions else ['disabled'])
        if not self.actions:
            self.action_name.set(NO_ACTION)
            self.counter.set('')

    def pick_action(self):
        label = self.action_name.get()
        self.start(next((a for a in self.actions if a.label == label), None), 0.0)

    def start(self, action, frame=0.0):
        self.action = action
        if action is None:
            self.stop_timer()
            self.playing = False
            self.play_text.set('Play')
            self.refresh()
            return
        self.action_name.set(action.label)
        self.setting = True
        self.slider.configure(to=max(1, action.frames - 1))
        self.setting = False
        self.frame = frame % action.frames
        self.play(True)

    def play(self, yes):
        self.playing = yes
        self.play_text.set('Pause' if yes else 'Play')
        self.f_ref, self.t_ref = self.frame, time.perf_counter()
        self.stop_timer()
        self.refresh()
        if yes:
            self.timer = self.after(1, self.tick)

    def toggle(self):
        if self.action is not None:
            self.play(not self.playing)

    def stop_timer(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

    def tick(self):
        self.timer = None
        if not self.playing or self.action is None:
            return
        if self.winfo_ismapped():
            now = time.perf_counter()
            self.frame = (self.f_ref + (now - self.t_ref) * FPS) % self.action.frames
            start = time.perf_counter()
            self.draw()
            took = time.perf_counter() - start
        else:
            took = 0.2
        self.timer = self.after(max(1, int(1000 / FPS - took * 1000)), self.tick)

    def scrub(self, value):
        """The slider was moved (by the person, or by the animation: then self.setting is set)."""
        if self.setting or self.action is None:
            return
        self.frame = min(float(value), self.action.frames - 1)
        self.playing = False
        self.play_text.set('Play')
        self.stop_timer()
        self.refresh()

    # ----- the picture

    def refresh(self):
        """Draws soon (once for several requests)."""
        if not self.queued:
            self.queued = True
            self.after_idle(self.draw_queued)

    def draw_queued(self):
        self.queued = False
        self.draw()

    def draw(self):
        if self.scene is None:
            self.draw_text()
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 40 or h < 40:
            return
        scale = self.scale if (self.playing or self.drag) else 1
        rw, rh = max(32, w // scale), max(32, h // scale)
        state = self.action.state(self.scene, int(self.frame)) if self.action is not None else {}
        start = time.perf_counter()
        fb = render(self.scene, self.cam, rw, rh, state.get('poses'), state.get('srts'), BACKGROUND)
        self.src.configure(data=to_ppm(rw, rh, fb))
        image = self.src
        if scale > 1:
            self.tk.call(self.dst.name, 'copy', self.src.name, '-zoom', scale, scale)
            image = self.dst
        if self.item is None:
            self.item = self.canvas.create_image(0, 0, anchor='center', image=image)
        self.canvas.itemconfigure(self.item, image=image)
        self.canvas.coords(self.item, w // 2, h // 2)
        took = time.perf_counter() - start
        if took > SLOW and self.scale < 4:
            self.scale += 1
        elif took < FAST and self.scale > 1 and scale == self.scale:
            self.scale -= 1
        if self.action is not None:
            self.setting = True
            self.slider.set(self.frame)
            self.setting = False
            self.counter.set('%d / %d' % (int(self.frame) + 1, self.action.frames))
        if scale > 1 and not self.playing:
            self.settle()

    def settle(self):
        """After a drag drawn small, draws once at full size."""
        if self.settle_timer is not None:
            self.after_cancel(self.settle_timer)
        self.settle_timer = self.after(160, self.refresh)

    # ----- the mouse

    def press(self, event, mode):
        self.drag = (mode, event.x, event.y)
        self.canvas.focus_set()

    def motion(self, event):
        if self.drag is None or self.cam is None:
            return
        mode, x, y = self.drag
        dx, dy = event.x - x, event.y - y
        self.drag = (mode, event.x, event.y)
        if mode == 'turn':
            self.cam.orbit(-dx * 0.01, dy * 0.01)
        else:
            h = max(self.canvas.winfo_height(), 1)
            self.cam.pan(dx / h, dy / h)
        self.refresh()

    def release(self, event):
        self.drag = None
        if not self.playing:
            self.settle()

    def zoom(self, direction):
        if self.cam is not None:
            self.cam.zoom(0.9 ** direction)
            self.refresh()
            if not self.playing:
                self.settle()

    def wheel(self, event):
        step = event.delta / (1 if sys.platform == 'darwin' else 120)
        if self.cam is not None and step:
            self.cam.zoom(0.9 ** step)
            self.refresh()
            if not self.playing:
                self.settle()

    def reset_camera(self):
        if self.scene is not None:
            self.cam = self.scene.camera()
            self.refresh()
