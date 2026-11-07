"""Ready made layouts to start from (QWERTY, AZERTY, QWERTZ, Dvorak ...). Each one is written as the rows of the lowercase layer of the
keyboard on the screen; the Caps and Shift layers follow from it."""

# the QWERTY keyboard of the game, row by row: digits, letters (10, 9 and 7 keys with three signs after them), the four keys around the
# space bar (two on the left of it, two on the right)
QWERTY = ['1234567890-=', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm,./', ';`[]']
# the other layouts of the Latin alphabet, with the keys of the original that do not fit moved to the keys around the space bar
AZERTY = ['1234567890-=', 'azertyuiop', 'qsdfghjkl', 'wxcvbnm,./', ';`[]']          # the M stays next to the N: the third row has one key less
QWERTZ = ['1234567890-=', 'qwertzuiop', 'asdfghjkl', 'yxcvbnm,./', ';`[]']
DVORAK = ['1234567890[]', "',.pyfgcrl", 'aoeuidhtn', ';qjkxbmwvz', 's-/=']
COLEMAK = ['1234567890-=', 'qwfpgjluy;', 'arstdhnei', 'zxcvbkm,./', 'o`[]']
ALPHABETICAL = ['1234567890-=', 'abcdefghij', 'klmnopqrs', 'tuvwxyz,./', ';`[]']

# what the Shift key types on a key that is not a letter
SHIFTED = dict(zip('1234567890-=,./;`[]\'', '!@#$%^&*()_+<>?:~{}"'))


def capital(ch):
    """The capital of a letter; the letter itself when it has none or when its capital takes two letters (the German ß)."""
    up = ch.upper()
    return up if len(up) == 1 else ch


def layers(rows):
    """{layer: rows} of the QWERTY keyboard from the rows of its lowercase layer: Caps types capitals and keeps the other keys, Shift
    types capitals and the sign of the Shift key."""
    return {'lower': rows,
            'caps': [''.join(map(capital, row)) for row in rows],
            'shift': [''.join(SHIFTED.get(ch) or capital(ch) for ch in row) for row in rows]}


def national(rows, keys):
    """rows with the four keys around the space bar typing `keys` (the letters a language adds to the Latin alphabet)."""
    return rows[:4] + [keys]


# keyboard: [(title, {layer: rows})]; the one the game has comes first
PRESETS = {
    'QWERTY': [(title, layers(rows)) for title, rows in (
        ('QWERTY', QWERTY),
        ('AZERTY', AZERTY),
        ('AZERTY with é è à ç', national(AZERTY, 'éèàç')),
        ('QWERTZ', QWERTZ),
        ('QWERTZ with ä ö ü ß', national(QWERTZ, 'äöüß')),
        ('Dvorak', DVORAK),
        ('Colemak', COLEMAK),
        ('Spanish with ñ ¿ ¡', national(QWERTY, ';ñ¿¡')),
        ('Portuguese with ç ã õ é', national(QWERTY, 'çãõé')),
        ('Italian with è à ò ù', national(QWERTY, 'èàòù')),
        ('Swedish, Finnish with å ä ö', national(QWERTY, ';åäö')),
        ('Danish, Norwegian with æ ø å', national(QWERTY, ';æøå')),
        ('Turkish with ş ğ ı ç', national(QWERTY, 'şğıç')),          # the four keys round the space bar: ö and ü stay on the accents
        ('Polish with ą ę ś ł', national(QWERTY, 'ąęśł')),
        ('Alphabetical', ALPHABETICAL),
    )],
}

# the French accents first, then every other accented letter the original keyboard has
ACCENTS = 'éèêëàâäîïôö' + 'ùûüçœÉÈÊËÀÂ' + 'ÄÎÏÔÖÙÛÜÇŒá' + 'íóúìòñßÁÍÓÚ' + 'ÌÒÑ¡¿€¢£'


def accent_rows(first):
    """The five rows of the Accents keyboard with the letters `first` at the start (they keep the rows of the game: 11, 11, 11, 11, and the rest)."""
    order = (first + ''.join(ch for ch in ACCENTS if ch not in first))[:len(ACCENTS)]     # the same number of keys as the game's
    return [order[:11], order[11:22], order[22:33], order[33:44], order[44:]]


PRESETS['Accents'] = [
    ('French accents first', {'accents': accent_rows('')}),
    ('German umlauts first', {'accents': accent_rows('äöüßÄÖÜ')}),
    ('Spanish signs first', {'accents': accent_rows('ñÑ¿¡áéíóú')}),
    ('Italian accents first', {'accents': accent_rows('àèéìíòóù')}),
    ('Portuguese accents first', {'accents': accent_rows('ãõçáéíóúâêô')}),
    ('Nordic letters first', {'accents': accent_rows('åäöæøÅÄÖÆØ')}),
    ('Currency signs first', {'accents': accent_rows('€¢£¡¿')}),
]


def presets_for(keyboard, usable=None):
    """[(title, {layer: string})] the ready made layouts that fit a Keyboard (see layout.py). usable: tells whether the game can draw a
    character; the layouts that need one it cannot are left out."""
    out = []
    for title, rows in PRESETS.get(keyboard.name, []):
        try:
            text = {layer: keyboard.join(lines) for layer, lines in rows.items()}
        except ValueError:
            continue
        if usable is None or all(usable(ch) for chars in text.values() for ch in chars):
            out.append((title, text))
    return out
