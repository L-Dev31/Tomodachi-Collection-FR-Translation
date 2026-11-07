"""Undo and redo of a tab: it keeps the states the tab had, as Tab.snapshot() gives them."""
import time

BURST = 0.7         # seconds: changes closer together than this (typing, dragging) make one step


class History:
    def __init__(self, tab):
        self.tab = tab
        self.past, self.future, self.now, self.stamp, self.busy = [], [], None, 0.0, False

    def reset(self):
        """A ROM was opened: forget the steps; the state now is the first one."""
        self.past, self.future, self.stamp = [], [], 0.0
        self.now = self.read()

    def read(self):
        try:
            return self.tab.snapshot()
        except Exception:
            return self.now

    def record(self):
        """The tab changed: the state before becomes a step to go back to (changes in quick succession are one step)."""
        if self.busy or self.now is None:
            return
        state, t = self.read(), time.monotonic()
        if state == self.now:
            return
        if not self.past or t - self.stamp >= BURST:
            self.past.append(self.now)
        self.future.clear()
        self.now, self.stamp = state, t

    def step(self, redo=False):
        """Goes one step back (or forward again). Returns False when there is none."""
        src, dst = (self.future, self.past) if redo else (self.past, self.future)
        if not src:
            return False
        dst.append(self.now)
        self.busy = True
        try:
            self.tab.rollback(src.pop())
        finally:
            self.busy = False
        self.now, self.stamp = self.read(), 0.0
        return True
