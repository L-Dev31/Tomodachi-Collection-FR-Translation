"""What the Models tab draws besides textures: the swatches of a palette."""
from ...core.binary import u16

SWATCH, ACROSS = 14, 16         # pixels of a colour of a palette picture, colours in a row


def palette_picture(b, pal):
    """(width, height, RGBA bytes) of a palette of a model file (a dict of bmd_textures) as rows of 16 swatches."""
    count = max(0, min(pal['size'], len(b) - pal['off'])) // 2
    rows = max(1, (count + ACROSS - 1) // ACROSS)
    w, h = ACROSS * SWATCH, rows * SWATCH
    out = bytearray(w * h * 4)
    for i in range(count):
        v = u16(b, pal['off'] + 2 * i)
        px = bytes(((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 255)) * (SWATCH - 1)
        x, y = i % ACROSS * SWATCH, i // ACROSS * SWATCH
        for dy in range(SWATCH - 1):
            start = ((y + dy) * w + x) * 4
            out[start:start + len(px)] = px
    return w, h, bytes(out)
