"""PNG pictures, read and written with the Pillow library. The pixels travel as RGBA bytes (4 bytes per pixel, row after row)."""
import io

from PIL import Image, UnidentifiedImageError


def png_write(w, h, rgba):
    """A PNG file of w x h pixels from RGBA bytes."""
    out = io.BytesIO()
    Image.frombytes('RGBA', (w, h), bytes(rgba)).save(out, 'PNG', optimize=True)
    return out.getvalue()


def png_read(data):
    """(width, height, RGBA bytes) of a PNG file of any kind (palette, grey, 16 bits, interlaced...)."""
    try:
        with Image.open(io.BytesIO(bytes(data))) as image:
            if image.format != 'PNG':
                raise ValueError('Not a PNG file')
            if image.mode.startswith('I'):                      # grey of 16 bits: its high byte (the conversion would cut it at 255)
                image = image.point(lambda v: v / 256)
            image = image.convert('RGBA')
    except ValueError:
        raise
    except UnidentifiedImageError:
        raise ValueError('Not a PNG file') from None
    except Exception as e:                  # whatever the library finds wrong with the file (truncated, corrupt, too big...)
        raise ValueError('This PNG file cannot be read (%s)' % e) from None
    return image.width, image.height, image.tobytes()


def png_write_indexed(w, h, idx, pal, depth):
    """A PNG file of w x h pixels given as numbers of colours of pal ((r, g, b) triples), the colour 0 being transparent.
    depth: 4 or 8 bits per pixel (4 only when every number is below 16)."""
    image = Image.frombytes('P', (w, h), bytes(idx))
    image.putpalette([value for colour in pal for value in colour[:3]])
    out = io.BytesIO()
    image.save(out, 'PNG', bits=depth, transparency=0, optimize=True)
    return out.getvalue()
