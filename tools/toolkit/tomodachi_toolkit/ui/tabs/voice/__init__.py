"""Voice tab: the lines the Miis say, their pronunciation and rhythm, and the voice presets.

tab.py      the tab: a tree of the banks, their lines and the voices; the right click; the patch and the project
line.py     the panel of a line: listen, the visual and the text views
voices.py   the panel of a voice, a mood or an effect (the presets of the speech engine)
strip.py    the sounds of a line as blocks, with the graph of their pitch, length or volume
palette.py  the sounds, the marks, the game codes and the effects to click
editor.py   the line being edited and the selected block
"""
from .tab import VoiceTab

__all__ = ['VoiceTab']
