"""The lines the Miis say: speech messages of the game, found in its message files and grouped by file (a bank).

A speech message is a message that the engine can read (katakana, marks, commands and game codes only). The game keeps
each line twice: the text the player sees (kanji, kana, French...) and, right after it, the katakana text the engine
reads. The twin is found by its number (the seen text ends in 0, the spoken one in 1) or by the header of the speech
bubble, and gives the name a line has in the list."""
import collections
import re

from ...core.bmg import BmgFile
from ...core.narc import narc_files
from ..bmg import bmg_archive, bmg_put
from .kana import normal_sound
from .line import reading
from .text import TAG_RE, is_speakable, pieces

# The message files that hold lines the Miis say (the start of the file name, after /Msg/).
FAMILIES = ('TmdTalk', 'TmdSelect', 'TmdTrouble', 'TmdMiitouch', 'TmdMiniContents', 'TmdNews', 'TmdSong')
MELODIES = ('TmdSong',)      # in these files only the melodies are speech: lines with codes for the syllables and commands
FORMATTING = '08ff'          # the codes that start with this are about the look of the text, not about what is said


def is_speech_file(path):
    name = path.rsplit('/', 1)[-1]
    return path.startswith('/Msg/') and path.endswith('_LZ.bin') and name.startswith(FAMILIES)


def bank_name(path):
    """'/Msg/TmdTalkCoolMsgJP_LZ.bin' -> 'TalkCool'"""
    m = re.match(r'Tmd(.*?)Msg', path.rsplit('/', 1)[-1])
    return m.group(1) if m else path.rsplit('/', 1)[-1]


def is_melody(text):
    """A line made of game codes (the syllables to sing) with commands or long marks between them."""
    return '{' in text.replace('{{', '') and (bool(TAG_RE.search(text)) or 'ー' in text)


def plain(text):
    """What the player sees in a message, for a list: the formatting codes dropped, the other codes shown as ◇."""
    out = []
    for piece in pieces(text):
        if piece[0] == 'code':
            if not piece[1].startswith(FORMATTING):
                out.append('◇')
        elif piece[0] == 'char':
            out.append(' ' if piece[1] in '\r\n' else piece[1])
    return ' '.join(''.join(out).split())


class Line:
    """One speech message: where it is in the ROM, the text the engine reads, and the text the player sees with it."""
    __slots__ = ('path', 'index', 'id', 'text', 'display', 'reading')

    def __init__(self, path, index, mid, text, display):
        self.path, self.index, self.id, self.text, self.display = path, index, mid, text, display
        self.reading = reading(text)

    @property
    def key(self):
        return self.path, self.index

    @property
    def label(self):
        """The name of the line in a list: what the player sees with it, or else what it says."""
        return self.display or self.reading


class Bank:
    """The speech lines of one message file."""

    def __init__(self, path, lines):
        self.path, self.name, self.lines = path, bank_name(path), lines

    def __len__(self):
        return len(self.lines)


def file_lines(path, bmg):
    """The speech lines of a message file (a core.bmg.BmgFile)."""
    texts = [bmg.text(i) for i in range(bmg.count)]
    ids = bmg.ids or [None] * len(texts)
    ok = [is_speakable(t) for t in texts]
    melodies = path.rsplit('/', 1)[-1].startswith(MELODIES)
    out = []
    for i, text in enumerate(texts):
        if not ok[i] or (melodies and not is_melody(text)):
            continue
        n = i + 1
        if n < len(texts) and ok[n] and ids[i] is not None and ids[n] == ids[i] + 1 and ids[i] % 2 == 0 \
                and normal_sound(text) == normal_sound(texts[n]):
            continue                      # this is the katakana copy of the text the player sees; the next one is the speech
        j, display = i - 1, ''
        if melodies:
            display = f'Melody {ids[i] if ids[i] is not None else i}'
        elif j >= 0 and ((ids[i] is not None and ids[j] == ids[i] - 1) or texts[j].startswith('{' + FORMATTING)):
            if not ok[j] or normal_sound(texts[j]) == normal_sound(text):
                display = plain(texts[j])
        out.append(Line(path, i, ids[i], text, display))
    return out


def speech_banks(paths, read):
    """The banks of speech lines of a ROM. paths: the files of the ROM; read(path) gives the message file."""
    out = []
    for path in sorted(p for p in paths if is_speech_file(p)):
        try:
            lines = file_lines(path, BmgFile(read(path)))
        except Exception:
            continue
        if lines:
            out.append(Bank(path, lines))
    return out


def tag_values(banks):
    """{command name: [values the lines use with it, the most common first]}"""
    seen = collections.defaultdict(collections.Counter)
    for bank in banks:
        for line in bank.lines:
            for m in TAG_RE.finditer(line.text):
                if m.group(2) is not None:
                    seen[m.group(1)][str(int(m.group(2)))] += 1
    return {name: [v for v, _ in count.most_common()] for name, count in seen.items()}


class LineEdits:
    """The lines that were changed: {path: {index: (the text in the ROM, the new text)}}."""

    def __init__(self):
        self.data = {}

    def __len__(self):
        return sum(len(v) for v in self.data.values())

    def new_text(self, path, index):
        """The new text of a line, or None when it was not changed."""
        pair = self.data.get(path, {}).get(index)
        return None if pair is None else pair[1]

    def count(self, path):
        return len(self.data.get(path, ()))

    def set(self, path, index, old, new):
        """Keeps a new text for a line (forgets the change when it is the text of the ROM)."""
        if new == old:
            self.reset(path, index)
        else:
            self.data.setdefault(path, {})[index] = (old, new)

    def reset(self, path, index):
        group = self.data.get(path)
        if group is not None:
            group.pop(index, None)
            if not group:
                del self.data[path]

    def clear(self):
        self.data.clear()

    def config(self):
        """The changes as plain data, for the patch and the project file: {path: {'12': [old, new]}}."""
        return {path: {str(i): list(pair) for i, pair in sorted(group.items())} for path, group in sorted(self.data.items())}

    def restore(self, config, banks):
        """Replaces the changes by those of a project. Returns notes for the lines that are not in this ROM as they were."""
        self.clear()
        notes, by_key = [], {line.key: line for bank in banks for line in bank.lines}
        for path, group in config.items():
            for key, (old, new) in group.items():
                line = by_key.get((path, int(key)))
                if line is None or line.text != old:
                    notes.append(f'Speech line {key} of {bank_name(path)} is not the one this project was made from: skipped.')
                else:
                    self.set(path, int(key), old, new)
        return notes


def lines_ok(config):
    """Returns an error text when the lines of a project are not well formed, else None."""
    if not isinstance(config, dict):
        return 'Bad speech lines'
    for path, group in config.items():
        if not (isinstance(path, str) and path.startswith('/Msg/') and isinstance(group, dict)):
            return f'Bad speech lines of {path}'
        for key, pair in group.items():
            if not (isinstance(key, str) and key.isdigit() and isinstance(pair, list) and len(pair) == 2
                    and all(isinstance(t, str) for t in pair)):
                return f'Bad speech line {key} of {path}'
    return None


def apply_lines(rom, config, log=print):
    """Writes the changed lines ({path: {'12': [old, new]}}) into the message files of the ROM. A line is only changed
    when it still has the text it had when it was edited."""
    files, done = rom.files(), 0
    for path, group in config.items():
        if path not in files:
            log(f'Speech: {path} is not in this ROM, skipped')
            continue
        archive = bmg_archive(rom, files, path)
        bmg, changed = BmgFile(narc_files(archive)[0]), 0
        for key, (old, new) in group.items():
            i = int(key)
            if i >= bmg.count or bmg.text(i) != old:
                log(f'Speech: line {i} of {bank_name(path)} is not the one that was edited, skipped')
                continue
            bmg.set_text(i, new)
            changed += 1
        if changed:
            bmg_put(rom, files, path, archive, bmg.to_bytes())
            done += changed
    log(f'Speech: {done} line(s)')
