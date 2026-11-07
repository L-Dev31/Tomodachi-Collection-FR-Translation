"""Currency tab: the money of the game in another currency (prices, symbol, display)."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ...features.currency.apply import T2_MASK, T2_MAX, cents_ok
from ...features.currency.data import NAMES, SYMBOL
from ...features.currency.rates import fetch_rates
from ...features.keyboard.charset import name as character_name
from ..charpalette import CharPalette
from ..glyphs import Glyphs
from ..theme import BROWN, DARK, ERROR, MUTED, PANEL, font
from ..widgets import RevertButton
from .base import Tab


class CurrencyTab(Tab):
    key = 'currency'
    title = 'Currency'
    heading = 'Currency'

    def build(self):
        self.revert_button = RevertButton(self, self.reset)
        self.revert_button.pack(side='bottom', anchor='e', pady=(10, 0))       # packed first: it keeps its place at the bottom
        self.choice = tk.StringVar()
        self.symbol = tk.StringVar()
        self.info = tk.StringVar()
        self.whole = tk.BooleanVar(value=False)
        self.rates, self.names, self.loaded, self.pending = {}, [], False, None
        self.palette = self.pictures = None         # the characters to pick the symbol from (made when the tab is first shown)
        self.palette_tried = False
        box = ttk.Labelframe(self, text='Currency', padding=12)
        box.pack(fill='x', pady=(10, 0))
        box.columnconfigure(2, weight=1)
        self.combo = ttk.Combobox(box, textvariable=self.choice, values=self.names, state='readonly', width=40)
        self.combo.grid(row=0, column=0, columnspan=4, sticky='w')
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.pick())
        ttk.Label(box, text='Symbol').grid(row=1, column=0, sticky='w', pady=(10, 0))
        holder = tk.Frame(box, width=50, height=46, bg=PANEL, bd=1, relief='solid')
        holder.pack_propagate(False)
        holder.grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(10, 0))
        self.preview = tk.Label(holder, bg=PANEL, fg=BROWN, bd=0, font=font(15, True))
        self.preview.place(relx=0.5, rely=0.5, anchor='center')
        self.symbol_info = ttk.Label(box, foreground=MUTED, wraplength=330, justify='left')
        self.symbol_info.grid(row=1, column=2, sticky='w', padx=(10, 0), pady=(10, 0))
        ttk.Label(box, textvariable=self.info, foreground=DARK).grid(row=2, column=0, columnspan=4, sticky='w', pady=(10, 0))
        self.round_box = ttk.Checkbutton(box, text='Round prices to whole units', variable=self.whole, command=self.changed)
        self.round_box.grid(row=3, column=0, columnspan=4, sticky='w', pady=(10, 0))
        self.pick_box = ttk.Labelframe(self, text='Symbols the game can draw', padding=8)
        self.pick_box.pack(fill='both', expand=True, pady=(10, 0))
        self.default_button = ttk.Button(self.pick_box, text='Default symbol', style='Mini.TButton', command=self.reset_symbol)
        self.default_button.pack(side='bottom', anchor='e', pady=(6, 0))
        self.symbol.trace_add('write', lambda *_: self.symbol_changed())
        self.show_symbol()
        self.info.set('Loading exchange rates...')
        self.job = {'rates': None, 'error': None}
        threading.Thread(target=self.download, daemon=True).start()
        self.after(100, self.poll)

    # ----- the ROM and the characters

    def on_rom(self):
        if self.palette is not None:
            self.palette.destroy()
        self.palette = self.pictures = None
        self.palette_tried = False
        self.show_symbol()

    def on_show(self):
        if self.palette is None and not self.palette_tried and self.session is not None:
            self.make_palette()

    def make_palette(self):
        """Lists the characters that every font of the game draws (the symbol is copied into each of them) to pick the symbol from."""
        self.palette_tried = True
        try:
            characters = self.session.symbols()
        except Exception as e:                       # a ROM whose fonts are not where the toolkit looks: the symbol is the list's
            ttk.Label(self.pick_box, text=f'The characters of the game cannot be listed: {e}', foreground=ERROR).pack(side='top', anchor='w')
            return
        self.pictures = Glyphs(self, characters.font)
        self.palette = CharPalette(self.pick_box, self.pictures, characters, self.symbol.set)
        self.palette.pack(fill='both', expand=True)
        self.show_symbol()

    def symbol_changed(self):
        self.show_symbol()
        self.changed()

    def show_symbol(self):
        """The symbol as the game draws it, its code and name, its place in the palette."""
        ch = self.symbol.get()
        if self.palette is not None and self.session.symbols().has(ch):
            self.preview.configure(image=self.pictures.image(ch, BROWN, PANEL, 3), text='')
        else:
            self.preview.configure(image='', text=ch)
        self.symbol_info.configure(text=f'U+{ord(ch):04X}   {character_name(ch)}' if len(ch) == 1 else '')
        if self.palette is not None:
            self.palette.mark(ch)

    # ----- the rates

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
        self.symbol.set(SYMBOL[code])
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
            self.symbol.set(SYMBOL[self.code()])

    def reset(self):
        """Back to the money the game has: yen, its symbol, prices as they are."""
        name = next((n for n in self.names if n.startswith('JPY ')), None)
        if name is not None:
            self.choice.set(name)
            self.pick()

    def is_original(self):
        """True when the game keeps its own money."""
        return self.code() == 'JPY' and self.symbol.get() == SYMBOL['JPY']

    def changed(self):
        code = self.code()
        self.revert_button.show(self.loaded and bool(self.names) and not self.is_original())
        self.default_button.state(['disabled'] if not code or self.symbol.get() == SYMBOL[code] else ['!disabled'])
        super().changed()

    # ----- the patch and the project

    def patch_config(self):
        code = self.code()
        if not code:
            raise ValueError('Exchange rates are still loading.' if not self.loaded else 'No exchange rates: check the network.')
        symbol = self.symbol.get()
        if len(symbol) != 1:
            raise ValueError('Choose the symbol of the money: one character.')
        if self.session is not None and not self.session.symbols().has(symbol):
            raise ValueError(f'The game cannot draw {symbol!r}: choose the symbol of the money in the list.')
        return {'rate': self.rates[code], 'code': code, 'sym': symbol, 'whole': self.whole.get()}

    def project_part(self):
        return {'code': self.code(), 'symbol': self.symbol.get(), 'whole': self.whole.get()} if self.code() else {}

    def restore(self, part):
        if not part:                                # no currency in the project: the money of the game
            self.reset()
            return []
        if not self.loaded:
            self.pending = part  # applied as soon as the rates are here
            return []
        name = next((n for n in self.names if n.split()[0] == part['code']), None)
        if not name:
            return [f"Currency {part['code']} is not available (no exchange rates)."]
        self.choice.set(name)
        self.pick()
        notes = []
        if self.session is None or self.session.symbols().has(part['symbol']):
            self.symbol.set(part['symbol'])
        else:                                   # a project made with a longer list of symbols: the symbol of the money stays the one picked
            notes.append(f"The game cannot draw {part['symbol']!r}: the symbol of {part['code']} is {self.symbol.get()!r}.")
        if not self.round_box.instate(['disabled']):
            self.whole.set(bool(part['whole']))
        self.changed()
        return notes

    def summary(self):
        code = self.code()
        if not code:
            return 'unavailable'
        mode = 'whole units' if self.whole.get() or not cents_ok(code, self.rates.get(code, 0)) else 'with cents'
        return f'{code}  {self.symbol.get()}  ·  {mode}'
