"""Currency tab: the money of the game in another currency (prices, symbol, display)."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ...features.currency.apply import T2_MASK, T2_MAX, cents_ok
from ...features.currency.data import NAMES, SYMBOL
from ...features.currency.rates import fetch_rates
from ..theme import DARK
from .base import Tab


class CurrencyTab(Tab):
    key = 'currency'
    title = 'Currency'
    heading = 'Currency'

    def build(self):
        self.choice = tk.StringVar()
        self.symbol = tk.StringVar()
        self.info = tk.StringVar()
        self.whole = tk.BooleanVar(value=False)
        self.rates, self.names, self.loaded, self.pending = {}, [], False, None
        box = ttk.Labelframe(self, text='Currency', padding=12)
        box.pack(fill='x', pady=(10, 0))
        self.combo = ttk.Combobox(box, textvariable=self.choice, values=self.names, state='readonly', width=40)
        self.combo.grid(row=0, column=0, columnspan=3, sticky='w')
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.pick())
        ttk.Label(box, text='Symbol').grid(row=1, column=0, sticky='w', pady=(10, 0))
        entry = ttk.Entry(box, textvariable=self.symbol, width=4, validate='key', validatecommand=(self.register(lambda s: len(s) <= 1), '%P'))
        entry.grid(row=1, column=1, sticky='w', pady=(10, 0))
        entry.bind('<FocusOut>', lambda e: self.symbol.get() or self.reset_symbol())
        self.reset_button = ttk.Button(box, text='Reset currency', style='Soft.TButton', command=self.reset)
        self.reset_button.grid(row=1, column=2, sticky='w', padx=(14, 0), pady=(10, 0))
        ttk.Label(box, textvariable=self.info, foreground=DARK).grid(row=2, column=0, columnspan=3, sticky='w', pady=(10, 0))
        self.round_box = ttk.Checkbutton(box, text='Round prices to whole units', variable=self.whole, command=self.changed)
        self.round_box.grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))
        self.symbol.trace_add('write', lambda *_: self.changed())
        self.info.set('Loading exchange rates...')
        self.job = {'rates': None, 'error': None}
        threading.Thread(target=self.download, daemon=True).start()
        self.after(100, self.poll)

    def download(self):
        try:
            self.job['rates'] = fetch_rates()
        except Exception as e:
            self.job['error'] = e

    def poll(self):
        if self.job['rates'] is None and self.job['error'] is None:
            self.after(100, self.poll)
            return
        self.loaded = True
        if self.job['error'] is not None:
            self.info.set('')
            messagebox.showerror('Rates', f'Rate API unavailable:\n{self.job["error"]}')
            self.changed()
            return
        self.rates = self.job['rates']
        self.names = [f'{c}  {NAMES.get(c, "")}' for c in sorted(self.rates) if c in SYMBOL]
        self.combo['values'] = self.names
        if not self.choice.get():
            self.choice.set(next((n for n in self.names if n.startswith('JPY ')), self.names[0] if self.names else ''))
        self.pick()
        if self.pending:
            part, self.pending = self.pending, None
            notes = self.restore(part)
            if notes:
                messagebox.showwarning('Currency', '\n'.join(notes))

    def code(self):
        return self.choice.get().split()[0] if self.choice.get() else ''

    def pick(self):
        code = self.code()
        if not code:
            return
        self.symbol.set(SYMBOL[code][0])
        rate = self.rates.get(code)
        self.info.set(f'1 {code} = {1 / rate:,.2f} JPY' if rate else '')
        self.sync_round()
        if rate:
            scale = rate if self.whole.get() else rate * 100
            if T2_MAX * scale > T2_MASK:
                self.info.set(self.info.get() + f'  ·  prices above {T2_MASK / scale:,.0f} JPY are capped')
        self.changed()

    def sync_round(self):
        code = self.code()
        rate = self.rates.get(code)
        free = bool(rate) and cents_ok(code, rate)
        if not free:
            self.whole.set(True)
        elif self.round_box.instate(['disabled']):
            self.whole.set(False)
        self.round_box.state(['!disabled'] if free else ['disabled'])

    def reset_symbol(self):
        """The symbol of the chosen currency, as the list gives it."""
        if self.code():
            self.symbol.set(SYMBOL[self.code()][0])

    def reset(self):
        """Back to the money the game has: yen, its symbol, prices as they are."""
        name = next((n for n in self.names if n.startswith('JPY ')), None)
        if name is not None:
            self.choice.set(name)
            self.pick()

    def is_original(self):
        """True when the game keeps its own money."""
        return self.code() == 'JPY' and self.symbol.get() == SYMBOL['JPY'][0]

    def changed(self):
        self.reset_button.state(['disabled'] if not self.loaded or self.is_original() or not self.names else ['!disabled'])
        super().changed()

    def patch_config(self):
        code = self.code()
        if not code:
            raise ValueError('Exchange rates are still loading.' if not self.loaded else 'No exchange rates: check the network.')
        return {'rate': self.rates[code], 'code': code, 'sym': self.symbol.get(), 'whole': self.whole.get()}

    def project_part(self):
        return {'code': self.code(), 'symbol': self.symbol.get(), 'whole': self.whole.get()} if self.code() else {}

    def restore(self, part):
        if not part:
            return []
        if not self.loaded:
            self.pending = part  # applied as soon as the rates are here
            return []
        name = next((n for n in self.names if n.split()[0] == part['code']), None)
        if not name:
            return [f"Currency {part['code']} is not available (no exchange rates)."]
        self.choice.set(name)
        self.pick()
        self.symbol.set(part['symbol'])
        if not self.round_box.instate(['disabled']):
            self.whole.set(bool(part['whole']))
        self.changed()
        return []

    def summary(self):
        code = self.code()
        if not code:
            return 'unavailable'
        mode = 'whole units' if self.whole.get() or not cents_ok(code, self.rates.get(code, 0)) else 'with cents'
        return f'{code}  {self.symbol.get()}  ·  {mode}'
