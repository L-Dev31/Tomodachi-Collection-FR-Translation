"""Opens the Tomodachi Location Toolkit: python run.py

The program is the tomodachi_toolkit folder next to this file; this script only starts it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tomodachi_toolkit.ui.app import App  # noqa: E402

if __name__ == '__main__':
    App().mainloop()
