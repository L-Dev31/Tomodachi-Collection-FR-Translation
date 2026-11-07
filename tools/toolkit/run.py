"""Opens the Tomodachi Location Toolkit: python run.py

The program is the tomodachi_toolkit folder next to this file; this script only starts it, after checking that the Python packages it uses
(requirements.txt) are installed.
"""
import os
import re
import sys
from importlib import metadata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def missing_packages():
    """The lines of requirements.txt whose package is not installed."""
    missing = []
    with open(os.path.join(HERE, 'requirements.txt'), encoding='utf-8') as f:
        for line in f:
            line = line.split('#')[0].strip()
            if line:
                try:
                    metadata.version(re.split(r'[<>=!~;\[ ]', line)[0])
                except metadata.PackageNotFoundError:
                    missing.append(line)
    return missing


def explain(missing):
    """What to tell somebody who lacks packages: which, and how to get them."""
    names = [re.split(r'[<>=!~;\[ ]', line)[0] for line in missing]
    return ('These Python packages are missing: ' + ', '.join(missing) + '\n\n'
            'Install them with:\n    python -m pip install -r requirements.txt\n\n'
            'If pip refuses (Arch Linux and other systems that manage Python themselves), use a virtual environment:\n'
            '    python -m venv .venv\n    .venv/bin/python -m pip install -r requirements.txt\n    .venv/bin/python run.py\n\n'
            'or the packages of the system (Arch Linux):\n    sudo pacman -S ' + ' '.join('python-' + name.lower() for name in names))


def main():
    missing = missing_packages()
    if missing:
        text = explain(missing)
        try:                                        # started from a desktop, nobody reads the terminal
            import tkinter
            from tkinter import messagebox
            root = tkinter.Tk()
            root.withdraw()
            messagebox.showerror('Tomodachi Location Toolkit', text)
            root.destroy()
        except Exception:
            pass
        sys.exit(text)
    from tomodachi_toolkit.ui.app import App
    App().mainloop()


if __name__ == '__main__':
    main()
