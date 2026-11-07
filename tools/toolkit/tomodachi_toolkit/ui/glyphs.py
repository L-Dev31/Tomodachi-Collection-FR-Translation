"""Pictures of the characters of a game font, drawn the way the game draws them."""
import tkinter as tk


class Glyphs:
    """Turns the characters of a Font (core/nftr.py) into tk images, kept for the next time they are asked for.

    The picture of a character is as high as a line of the font and as wide as the character, so that the game's rule (the
    character is centred in the key) is a matter of placing it."""

    def __init__(self, master, font):
        self.master, self.font = master, font
        self.cache = {}

    @property
    def height(self):
        return self.font.height

    def width(self, ch):
        """How wide the picture of a character is (pixels, before the zoom)."""
        return max(1, min(self.font.box(ch)[1], self.font.width))

    def image(self, ch, fg, bg, zoom=1):
        """The picture of a character in the colours fg on bg (hex strings), zoomed. A character the font does not have is blank."""
        key = (ch, fg, bg, zoom)
        if key not in self.cache:
            rows = self.font.glyph(ch) or [[0] * self.font.width for _ in range(self.font.height)]
            w = self.width(ch)
            img = tk.PhotoImage(master=self.master, width=w, height=len(rows))
            for y, row in enumerate(rows):
                img.put('{' + ' '.join(fg if v else bg for v in row[:w]) + '}', to=(0, y))
            self.cache[key] = img.zoom(zoom) if zoom > 1 else img
        return self.cache[key]
