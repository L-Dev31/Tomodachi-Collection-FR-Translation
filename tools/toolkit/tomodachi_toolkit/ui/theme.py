"""Colours, fonts and ttk styles of the toolkit."""
from tkinter import ttk

BG = '#FFF3D9'
PANEL = '#FFFFFF'
ORANGE = '#F7822B'
DARK = '#D96A14'
BROWN = '#5B3A1C'
WARM = '#A39382'
MUTED = '#9A7B5B'
SAND = '#F6DDB0'
CANVAS = '#EDE3D0'
ERROR = '#B3261E'
FAMILY = 'Segoe UI'


def font(size=9, bold=False):
    return (FAMILY, size, 'bold') if bold else (FAMILY, size)


def apply_theme(root):
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('TFrame', background=BG)
    s.configure('TLabel', background=BG, foreground=BROWN)
    s.configure('TCheckbutton', background=BG, foreground=BROWN)
    s.map('TCheckbutton', background=[('active', BG)])
    s.configure('TRadiobutton', background=BG, foreground=BROWN)
    s.map('TRadiobutton', background=[('active', BG)])
    s.configure('TLabelframe', background=BG, bordercolor=SAND)
    s.configure('TLabelframe.Label', background=BG, foreground=DARK, font=font(9, True))
    s.configure('TNotebook', background=BG, borderwidth=0)
    s.configure('TNotebook.Tab', background=SAND, foreground=BROWN, padding=(14, 6), font=font(10))
    s.map('TNotebook.Tab', background=[('selected', ORANGE)], foreground=[('selected', 'white')])
    # the second row of tabs, inside a group: lighter and smaller than the groups
    s.configure('Sub.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 6, 0, 0))
    s.configure('Sub.TNotebook.Tab', background=BG, foreground=MUTED, padding=(12, 4), font=font(9), bordercolor=SAND, lightcolor=BG, darkcolor=BG)
    s.map('Sub.TNotebook.Tab', background=[('selected', SAND), ('active', '#FBE8C6')], foreground=[('selected', BROWN)])
    s.configure('TCombobox', fieldbackground=PANEL, background=SAND)
    s.configure('TScale', background=BG, troughcolor=SAND)
    s.configure('Accent.TButton', background=ORANGE, foreground='white', padding=(18, 6), font=font(10, True), borderwidth=0)
    s.map('Accent.TButton', background=[('active', DARK), ('disabled', SAND)], foreground=[('disabled', '#B9A07A')])
    s.configure('Big.TButton', background=ORANGE, foreground='white', padding=(18, 11), font=font(11, True), borderwidth=0)
    s.map('Big.TButton', background=[('active', DARK), ('disabled', SAND)], foreground=[('disabled', '#B9A07A')])
    s.configure('Soft.TButton', background=SAND, foreground=BROWN, padding=(14, 6), borderwidth=0)
    s.map('Soft.TButton', background=[('active', '#EFCB8F')])
    s.configure('Small.TButton', background=SAND, foreground=BROWN, padding=(6, 1), borderwidth=0)
    s.map('Small.TButton', background=[('active', '#EFCB8F')])
    # buttons as wide as their text (the clam theme makes every other button at least 11 characters wide)
    s.configure('Mini.TButton', background=SAND, foreground=BROWN, padding=(10, 3), borderwidth=0, width=0)
    s.map('Mini.TButton', background=[('active', '#EFCB8F')], foreground=[('disabled', '#B9A07A')])
    s.configure('MiniAccent.TButton', background=ORANGE, foreground='white', padding=(14, 3), font=font(9, True), borderwidth=0, width=0)
    s.map('MiniAccent.TButton', background=[('active', DARK), ('disabled', SAND)], foreground=[('disabled', '#B9A07A')])
    s.configure('Toolbutton', background=SAND, foreground=BROWN, padding=(9, 3), borderwidth=0)
    s.map('Toolbutton', background=[('selected', ORANGE), ('active', '#EFCB8F')], foreground=[('selected', 'white')])
