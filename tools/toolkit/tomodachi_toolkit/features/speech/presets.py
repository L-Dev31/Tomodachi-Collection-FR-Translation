"""Voice presets of the engine: property table, preset table in the ARM9, scripts."""
import re


PRESET_FIRST = b'<\\Emp\0'


PRESET_SIZE, PRESET_NAME, PRESET_SCRIPT = 0x78, 20, 100


SPEECH_PROPS = {
    4: ('Pitch', 3500, 7000, 5058), 3: ('Speed', 20, 2200, 100), 5: ('Volume', -10000, 360, 0),
    6: ('Voice quality', 80, 130, 100), 14: ('Accent', 0, 400, 100), 15: ('Phrase accent', 0, 400, 100),
    8: ('Echo delay', 0, 3000, 0), 9: ('Echo gain', 0, 100, 0), 10: ('FIR delay', 0, 1000, 0),
    11: ('FIR gain', 0, 100, 0), 7: ('Ring', 0, 5000, 0)}


SCRIPT_KEYS = {'B': 4, 'S': 3, 'V': 5, 'X': 6, 'A': 14, 'P': 15, 'I': 8, 'J': 9, 'R': 10, 'G': 11, 'r': 7}


SCRIPT_REL = 'BSVAP'


def preset_tables(arm9):
    """Offsets of every copy of the named preset table (the game keeps two identical ones)."""
    arm9, out = bytes(arm9), []
    p = arm9.find(PRESET_FIRST)
    while p >= 0:
        out.append(p)
        p = arm9.find(PRESET_FIRST, p + 1)
    return out


def preset_read(arm9, base):
    out, o = [], base
    while o + PRESET_SIZE <= len(arm9):
        name = bytes(arm9[o:o + PRESET_NAME]).split(b'\0')[0]
        if not name.startswith(b'<\\') or len(name) < 3:
            break
        out.append((name.decode('latin1'), bytes(arm9[o + PRESET_NAME:o + PRESET_SIZE]).split(b'\0')[0].decode('latin1')))
        o += PRESET_SIZE
    return out


def preset_write(arm9, bases, name, script):
    """Writes one preset script into every copy of the table (arm9 is a bytearray)."""
    data = script.replace('\r', '').encode('latin1', 'ignore')
    if len(data) >= PRESET_SCRIPT:
        raise ValueError(f'{name}: script is {len(data)} bytes, the limit is {PRESET_SCRIPT - 1}.')
    done = 0
    for base in bases:
        o = base
        while o + PRESET_SIZE <= len(arm9):
            nm = bytes(arm9[o:o + PRESET_NAME]).split(b'\0')[0]
            if not nm.startswith(b'<\\'):
                break
            if nm.decode('latin1') == name:
                arm9[o + PRESET_NAME:o + PRESET_SIZE] = data + b'\0' * (PRESET_SCRIPT - len(data))
                done += 1
                break
            o += PRESET_SIZE
    if not done:
        raise ValueError(f'Preset {name} not found.')


def script_parse(script):
    """'#B4800\\n#S90' -> [('B', '4800'), ('S', '90')]"""
    out = []
    for part in script.replace('\r', '').replace('#', '\n#').split('\n'):
        part = part.strip()
        if part.startswith('#') and len(part) > 1:
            out.append((part[1], part[2:].strip()))
    return out


def script_join(items):
    return '\n'.join('#' + k + v for k, v in items)


def script_value(items, key):
    """Value text of the first item with this letter, or None."""
    return next((v for k, v in items if k == key), None)


def script_set(items, key, value):
    """Sets (or removes when value is empty) the item of that letter, keeping the others in order."""
    out, done = [], False
    for k, v in items:
        if k == key:
            if value and not done:
                out.append((k, value))
            done = True
        else:
            out.append((k, v))
    if value and not done:
        out.append((key, value))
    return out


def script_check(script):
    """Returns an error text when the script cannot be right, else None."""
    if len(script.replace('\r', '').encode('latin1', 'ignore')) >= PRESET_SCRIPT:
        return f'The script must be shorter than {PRESET_SCRIPT} bytes.'
    for k, v in script_parse(script):
        if k in SCRIPT_KEYS:
            pid = SCRIPT_KEYS[k]
            lo, hi = SPEECH_PROPS[pid][1], SPEECH_PROPS[pid][2]
            if v == '' or (v == '+' and k in SCRIPT_REL):
                continue  # a command whose value comes from the tag in the text, like <\\Spd=150>
            if v.startswith('+') and k in SCRIPT_REL:
                if not re.fullmatch(r'\+-?\d+', v):
                    return f'#{k}{v}: a relative value looks like +200 or +-60.'
            elif not re.fullmatch(r'-?\d+', v):
                return f'#{k}{v}: not a number.'
            elif not lo <= int(v) <= hi:
                return f'#{k}{v}: {SPEECH_PROPS[pid][0]} goes from {lo} to {hi}.'
    return None
