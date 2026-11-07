"""Changing the animations in place. sheets_of() describes what an animation holds as tables (a few numbers per key) whose values know how to
be written back. A file keeps its size, except when a rotation is changed: the new rotation is an entry added at the end of the table of rotations
(which is the end of the file), and the key points to it, so the other keys that shared the old entry do not move."""
import collections
import csv
import io
import math
import re
import struct

from ...core.binary import u16, u32
from .anim import Track, bca_animations
from .cells import Cell

Row = collections.namedtuple('Row', 'label items')
Group = collections.namedtuple('Group', 'title columns rows note edit_row')      # edit_row(data, row, changes): writes some values of one row
Sheet = collections.namedtuple('Sheet', 'name groups')


class Item:
    """A value of a table: the text shown; edit(data, text) gives the file with the value changed (None: it cannot be changed there); toggle: a
    double click turns it on or off, there is nothing to type."""
    __slots__ = ('text', 'edit', 'toggle')

    def __init__(self, text, edit=None, toggle=False):
        self.text, self.edit, self.toggle = text, edit, toggle


def number(text):
    try:
        return float(str(text).strip().strip('()').rstrip('*').strip().replace(',', '.'))
    except ValueError:
        raise ValueError('Type a number.') from None


def put(data, cell, value):
    buf = bytearray(data)
    cell.put(buf, value)
    return bytes(buf)


def writer(cell, whole=False):
    """The function that changes the number of a cell."""
    return (lambda data, text: put(data, cell, int(number(text)) if whole else number(text))) if cell else None


# ----- rotations

def euler_of(r):
    """The angles (degrees) about X, Y and Z of a rotation matrix (rows), turned in this order: R = Rz Ry Rx."""
    sy = max(-1.0, min(1.0, -r[2][0]))
    b = math.asin(sy)
    if abs(sy) < 0.999999:
        a, c = math.atan2(r[2][1], r[2][2]), math.atan2(r[1][0], r[0][0])
    else:
        a, c = math.atan2(-r[1][2], r[1][1]), 0.0
    return tuple(math.degrees(x) for x in (a, b, c))


def from_euler(a, b, c):
    a, b, c = math.radians(a), math.radians(b), math.radians(c)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return ((cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa),
            (sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa),
            (-sb, cb * sa, cb * ca))


def encode_rot5(r):
    """The 10 bytes of an entry of the table of rotations (anim.rot5_matrix reads them): the first column, then the first two numbers of
    the second, whose last number is kept apart in its sign bit."""
    c0, c1 = (r[0][0], r[1][0], r[2][0]), (r[0][1], r[1][1], r[2][1])

    def q(x):
        return max(-32768, min(32767, round(x * 32768)))
    v = [q(c0[0]), q(c0[1]), q(c0[2]), q(c1[0]), q(c1[1]) & ~7]
    norm = math.sqrt(sum((x / 32768) ** 2 for x in v[:3])) or 1.0
    d, e = v[3] / 32768, v[4] / 32768
    if abs(v[2] / 32768 / norm) <= math.sqrt(max(0.0, 1 - d * d - e * e)) and c1[2] < 0:
        v[4] |= 1
    return struct.pack('<5h', *v)


def sample_spans(b, table):
    """(where the first sample array after the table of rotations starts, where the last sample array ends) in a skeleton animation file."""
    first, last = len(b), 0
    for anim in bca_animations(b):
        for node in anim.nodes:
            for channel in node.values():
                for track in (channel if isinstance(channel, list) else [channel]):
                    if isinstance(track, Track):
                        for cell in track.cells:
                            if cell:
                                last = max(last, cell.end)
                                if cell.off >= table:
                                    first = min(first, cell.off)
    return first, last


def rotation_index(buf, anim, r):
    """The number of the entry of the table of rotations that holds the rotation r (a bytearray, which may grow). The table is not the end of
    the file (sample arrays follow it) but an entry is only a place at ten bytes times its number from the start of the table: a rotation
    that is not there yet is put at the end of the file, and its number says so."""
    entry = encode_rot5(r)
    table = anim.rot5
    first, last = sample_spans(bytes(buf), table)
    for lo, hi in ((table, first), (last, len(buf))):
        i = buf.find(entry, lo, hi)
        while i != -1 and (i - table) % 10:
            i = buf.find(entry, i + 1, hi)
        if i != -1 and (i - table) // 10 < 0x8000:
            return (i - table) // 10
    jnt = u32(buf, 16)
    index = -(-(len(buf) - table) // 10)
    if index >= 0x8000 or u16(buf, 14) != 1 or u32(buf, jnt + 4) != len(buf) - jnt:
        raise ValueError('The file has no room for a new rotation.')
    buf += b'\0' * (table + 10 * index - len(buf))
    buf += entry
    buf += b'\0' * (-len(buf) % 4)
    struct.pack_into('<I', buf, 8, len(buf))
    struct.pack_into('<I', buf, jnt + 4, len(buf) - jnt)
    return index


def set_angle(data, anim, track, i, axis, text):
    angles = list(euler_of(anim.rotation(track.data[i])))
    angles[axis] = number(text)
    buf = bytearray(data)
    track.cells[i].put(buf, rotation_index(buf, anim, from_euler(*angles)))
    return bytes(buf)


# ----- the tables

def shared_cells(b):
    """The places of the samples that more than one track of a skeleton animation file reads: changing one changes them all."""
    users = collections.Counter()
    for anim in bca_animations(b):
        for node in anim.nodes:
            for channel in node.values():
                for track in (channel if isinstance(channel, list) else [channel]):
                    if isinstance(track, Track):
                        users.update(cell.off for cell in track.cells if cell)
    return {off for off, n in users.items() if n > 1}


def mark(text, cell, shared):
    return text + ' *' if cell and cell.off in shared else text


def wanted(text):
    """Whether a value written in a table turns a flag on (the parts that show up)."""
    return text.strip() in ('✓', '1', 'x', 'X', 'oui', 'yes', 'true', 'True')


def same(new, shown):
    """Whether a value of a table is the one shown: a star or brackets do not count, a comma is a point."""
    def clean(text):
        return text.strip().strip('()').rstrip(' *').strip().replace(',', '.')
    a, b = clean(new), clean(shown)
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def rows_writer(rows):
    """edit_row(data, row, changes) of a group: writes some values of one row, changes being {value index: text} and row the number of the row
    in the group. A flag is turned on or off. A value between two keys cannot be written: it follows the keys."""
    def edit_row(data, row, changes):
        for j, text in changes.items():
            item = rows[row].items[j]
            if item.toggle:
                if wanted(text) != (item.text.strip() == '✓'):
                    data = item.edit(data, '')
            elif item.edit is None:
                raise ValueError(f'frame {rows[row].label}: a value between two keys cannot be written, it follows the keys')
            else:
                data = item.edit(data, text)
        return data
    return edit_row


def turn_writer(anim, track):
    """edit_row of the turns of a bone: the angles of one key are written together, so that two axes changed in one table are both kept."""
    def edit_row(data, row, changes):
        if track.cells[row] is None:
            raise ValueError(f'frame {row}: this turn cannot be written')
        angles = list(euler_of(anim.rotation(track.data[row])))
        for axis, text in changes.items():
            angles[axis] = number(text)
        buf = bytearray(data)
        track.cells[row].put(buf, rotation_index(buf, anim, from_euler(*angles)))
        return bytes(buf)
    return edit_row


def number_group(title, columns, tracks, shared=()):
    """A row for every frame where one of the tracks (one per column) has a key; between two keys a value is in brackets: it follows them. A
    value with a star is read by other animations too."""
    keys = [dict(zip(t.frames(), range(len(t.data)))) for t in tracks]
    rows = []
    for frame in sorted(set().union(*keys)):
        items = [Item(mark(f'{t.data[k[frame]]:.3f}', t.cells[k[frame]], shared), writer(t.cells[k[frame]])) if frame in k else Item(f'({t.value(frame):.3f})')
                 for t, k in zip(tracks, keys)]
        rows.append(Row(str(frame), items))
    return Group(title, columns, rows, '', rows_writer(rows))


def turn_group(anim, track, shared=()):
    rows = []
    for i, frame in enumerate(track.frames()):
        angles = euler_of(anim.rotation(track.data[i]))
        rows.append(Row(str(frame), [Item(mark(f'{angles[axis]:.1f}', track.cells[i], shared), (lambda data, text, i=i, axis=axis: set_angle(data, anim, track, i, axis, text))
                                          if track.cells[i] else None) for axis in range(3)]))
    return Group('Turn', ('X °', 'Y °', 'Z °'), rows, '', turn_writer(anim, track))


def kept(title, value):
    return Group(title, (), [], 'Not animated: the model keeps its own.' if value == 'base' else 'Not animated.', None)


def joint_sheets(anim, names=()):
    out, shared = [], shared_cells(anim.b)
    for node in anim.nodes:
        k, t, r, s = node['index'], node['t'], node['r'], node['s']
        out.append(Sheet(names[k] if k < len(names) else f'node {k}', [
            number_group('Move', ('X', 'Y', 'Z'), t, shared) if isinstance(t, list) else kept('Move', t),
            turn_group(anim, r, shared) if isinstance(r, Track) else kept('Turn', r),
            number_group('Size', ('X', 'Y', 'Z'), s, shared) if isinstance(s, list) else kept('Size', s)]))
    return out


def srt_sheets(anim):
    return [Sheet(name, [number_group('Scale', ('S', 'T'), t.scale), number_group('Move', ('S', 'T'), t.trans)]) for name, t in anim.tracks.items()]


def choose(names, text):
    text = text.strip()
    if text in names:
        return names.index(text)
    if text.isdigit() and int(text) < len(names):
        return int(text)
    raise ValueError('Type one of: ' + ', '.join(names))


def pat_sheets(anim):
    out = []
    for name, keys in anim.tracks.items():
        rows = []
        for n, ((frame, tex, pal), (cf, ct, cp)) in enumerate(zip(keys, anim.cells[name]), 1):
            rows.append(Row(f'key {n}', [Item(str(frame), writer(cf, True)), Item(anim.textures[tex], lambda d, t, c=ct: put(d, c, choose(anim.textures, t))),
                                         Item(anim.palettes[pal], lambda d, t, c=cp: put(d, c, choose(anim.palettes, t)))]))
        out.append(Sheet(name, [Group('Pictures', ('Frame', 'Texture', 'Palette'), rows, '', rows_writer(rows))]))
    return out


def flip(data, cell):
    buf = bytearray(data)
    cell.put(buf, 0 if cell.get(buf) else 1)
    return bytes(buf)


def vis_sheets(anim, names=()):
    columns = tuple(names[k] if k < len(names) else str(k) for k in range(anim.count))
    rows = []
    for frame in range(anim.frames):
        shown = anim.at(frame)
        rows.append(Row(str(frame), [Item('✓' if shown[k] else '·', (lambda data, text, c=Cell(anim.a + 12 + ((frame * anim.count + k) >> 3), 'B', bit=(frame * anim.count + k) & 7):
                                                                      flip(data, c)), toggle=True) for k in range(anim.count)]))
    return [Sheet('Parts shown', [Group('Frames', columns, rows, '', rows_writer(rows))])]


def sheets_of(anim, names=()):
    """The tables of an animation: [Sheet(name, [Group(title, columns, rows, note)])]. names: the names of the nodes of the model."""
    return {'joint': joint_sheets, 'vis': vis_sheets}.get(anim.kind, lambda a, n: srt_sheets(a) if a.kind == 'srt' else pat_sheets(a))(anim, names)


# ----- the tables as files

CSV_DELIMITER = ';'           # what French spreadsheets expect; reading also takes ','


def decimal(text):
    """A number as a French spreadsheet writes it (1,25); any other text as it is, without the star of a shared value."""
    plain = text.rstrip(' *')
    return plain.replace('.', ',') if re.fullmatch(r'\(?[-+]?\d+\.\d+\)?', plain) else plain


def table_csv(sheets):
    """The tables of an animation as text (CSV). Each group starts with a row whose first cell is '#' and that gives the titles of its columns;
    the other rows are the values: the number and the name of the sheet, the group, the frame, then the values in the order of the titles. A
    value between two keys is in brackets: an import does not change it."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=CSV_DELIMITER, lineterminator='\n')
    for number_of_sheet, sheet in enumerate(sheets):
        for group in sheet.groups:
            if not group.rows:
                continue
            writer.writerow(['#', number_of_sheet, sheet.name, group.title, 'Frame', *group.columns])
            for row in group.rows:
                writer.writerow([number_of_sheet, sheet.name, group.title, row.label, *(decimal(item.text) for item in row.items)])
    return out.getvalue()


def read_table(text):
    """The values of a table written by table_csv, or edited in a spreadsheet: [(number of the sheet, group, frame, [values])]. The cells are
    separated by ';' (or by ',' when the first row has no ';'). A row that is no row of a table raises ValueError."""
    delimiter = CSV_DELIMITER if CSV_DELIMITER in text.split('\n', 1)[0] else ','
    out = []
    for cells in csv.reader(io.StringIO(text), delimiter=delimiter):
        if not any(cell.strip() for cell in cells) or cells[0].strip() == '#':
            continue
        if len(cells) < 4 or not cells[0].strip().isdigit():
            raise ValueError(f'the row {cells[:4]} is not a row of the table (its first cell is the number of a sheet)')
        out.append((int(cells[0]), cells[2].strip(), cells[3].strip(), [cell.strip() for cell in cells[4:]]))
    return out


def apply_table(data, sheets, text):
    """Writes the values of a table (read_table) into the animation, row by row. Only the values that differ from the ones shown are written; an
    empty cell is no value. Returns (the new file, how many values changed, what could not be written and why). The caller makes the animation
    again from the new file."""
    changed, problems = 0, []
    for number_of_sheet, title, frame, values in read_table(text):
        if not 0 <= number_of_sheet < len(sheets):
            problems.append(f'sheet {number_of_sheet} is not in this animation')
            continue
        sheet = sheets[number_of_sheet]
        group = next((g for g in sheet.groups if g.title == title), None)
        row = next((r for r, line in enumerate(group.rows) if line.label == frame), None) if group else None
        if group is None or row is None or group.edit_row is None:
            problems.append(f'{sheet.name} {title} {frame}: not in this animation')
            continue
        items, changes = group.rows[row].items, {}
        for j, value in enumerate(values[:len(items)]):
            item = items[j]
            if not value:
                continue
            if item.toggle:
                if wanted(value) != (item.text.strip() == '✓'):
                    changes[j] = value
            elif item.edit is None:
                if not same(value, item.text):
                    problems.append(f'{sheet.name} {title} {frame}: a value between two keys cannot be written, it follows the keys')
            elif not same(value, item.text):
                changes[j] = value
        if not changes:
            continue
        try:
            data = group.edit_row(data, row, changes)
        except ValueError as e:
            problems.append(f'{sheet.name} {title} {frame}: {e}')
            continue
        changed += len(changes)
    return data, changed, problems
