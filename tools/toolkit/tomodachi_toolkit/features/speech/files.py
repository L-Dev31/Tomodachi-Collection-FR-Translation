"""The lines and the voice presets as plain text files, written and read as they are: UTF-8, the game codes as {hex}, nothing added and
nothing converted.

Batch export makes a folder per bank with a file per line, 'NNNN what the player sees.txt' (NNNN is the number of the message in its
file: only that number counts when the files are read again), and a folder 'Voice presets' with a file per preset, 'Name.txt', that
holds its script."""
import os
import re

from .line import problem
from .presets import script_check, script_join, script_parse

PRESETS = 'Voice presets'


def write(path, text):
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


def read_file(path, old):
    """The text of a file, for a line whose text is now `old`. It is read as it is, except for the line breaks that editors add by
    themselves: CR LF becomes LF, and one line break at the end goes unless the line itself ends with one. Raises OSError or
    ValueError (the file is not UTF-8 text)."""
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8-sig').replace('\r\n', '\n')
    return text[:-1] if text.endswith('\n') and not old.endswith('\n') else text


def file_name(line):
    """'0012 what the player sees.txt'"""
    title = ' '.join(re.sub(r'[^\w ]+', ' ', line.label).split())[:40].strip()
    return f'{line.index:04d} {title}.txt' if title else f'{line.index:04d}.txt'


def export_files(folder, banks, edits, catalog=None):
    """Writes every line (as it is now, the changes included) and every voice preset into a folder. Returns the number of files."""
    count = 0
    for bank in banks:
        os.makedirs(os.path.join(folder, bank.name), exist_ok=True)
        for line in bank.lines:
            new = edits.new_text(bank.path, line.index)
            write(os.path.join(folder, bank.name, file_name(line)), line.text if new is None else new)
            count += 1
    if catalog is not None:
        os.makedirs(os.path.join(folder, PRESETS), exist_ok=True)
        for name in catalog.original:
            write(os.path.join(folder, PRESETS, name[2:] + '.txt'), catalog.script(name))
            count += 1
    return count


def text_files(folder):
    """[(name, path)] of the .txt files of a folder (none when there is no such folder)."""
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith('.txt')) if os.path.isdir(folder) else []
    return [(n, os.path.join(folder, n)) for n in names]


def import_files(folder, banks, edits, catalog=None):
    """Reads what export_files wrote: a line gets the text of the file whose name starts with its number, a preset the script of the
    file that has its name. What is wrong is left out and told. Returns (lines changed, presets changed, problems)."""
    lines, presets, problems = 0, 0, []
    for bank in banks:
        by_number, seen = {line.index: line for line in bank.lines}, {}
        for name, path in text_files(os.path.join(folder, bank.name)):
            number = re.match(r'\d+', name)
            line = by_number.get(int(number.group())) if number else None
            try:
                if line is None:
                    raise ValueError('not the file of a line of this bank')
                if line.index in seen:
                    raise ValueError(f'line {line.index} is also given by {seen[line.index]}')
                seen[line.index] = name
                now = edits.new_text(bank.path, line.index)
                now = line.text if now is None else now
                text = read_file(path, now)
                bad = problem(text)
                if bad:
                    raise ValueError(bad)
            except (OSError, ValueError) as e:
                problems.append(f'{bank.name}/{name}: {e}')
                continue
            if text != now:
                edits.set(bank.path, line.index, line.text, text)
                lines += 1
    if catalog is not None:
        by_name = {name[2:]: name for name in catalog.original}
        for name, path in text_files(os.path.join(folder, PRESETS)):
            preset = by_name.get(name[:-4])
            try:
                if preset is None:
                    raise ValueError('no voice preset has this name')
                script = read_file(path, catalog.script(preset))
                bad = script_check(script)
                if bad or script_join(script_parse(script)).split() != script.split():
                    raise ValueError(bad or 'a script is made of items like #B4800, one per line')
            except (OSError, ValueError) as e:
                problems.append(f'{PRESETS}/{name}: {e}')
                continue
            if catalog.norm(script) != catalog.script(preset):
                catalog.set(preset, script)
                presets += 1
    return lines, presets, problems
