"""The voice presets as the Voice tab offers them (voices, emotions, commands) and the edits made to them."""
from .presets import SCRIPT_KEYS, SPEECH_PROPS, script_join, script_parse
from .text import tag_text

CHANGED_MARK = '● '


class PresetCatalog:
    """Preset names by kind, their scripts with the edits applied, and what a command needs to be tried.

    presets      [(name, script)] as read from the ROM
    voices       names of the voice presets, emotions: names of the emotion presets, commands: the others
    tag_values   {command name: [values the game writes with it]} (see lines.tag_values)
    edits        {name: script} for the presets that are not as in the ROM
    """

    def __init__(self, presets, voices, emotions, tag_values=None):
        self.original = dict(presets)
        self.voices, self.emotions = list(voices), list(emotions)
        grouped = set(self.voices) | set(self.emotions)
        self.commands = [name for name, _ in presets if name not in grouped]
        self.tag_values = dict(tag_values or {})
        self.edits = {}

    # ----- scripts and edits

    @staticmethod
    def norm(script):
        """One item per line, as the engine reads it."""
        return script_join(script_parse(script))

    def script(self, name):
        """The script of a preset with the edits applied."""
        return self.edits[name] if name in self.edits else self.norm(self.original[name])

    def changed(self, name):
        return name in self.edits

    def set(self, name, script):
        """Keeps a new script for a preset (it must have passed presets.script_check)."""
        script = self.norm(script)
        if script == self.norm(self.original[name]):
            self.edits.pop(name, None)
        else:
            self.edits[name] = script

    def reset(self, name):
        self.edits.pop(name, None)

    def reset_all(self):
        self.edits.clear()

    def restore(self, edits):
        """Replaces the edits by those of a project. Returns notes for the presets this ROM does not have."""
        self.edits.clear()
        notes = []
        for name, script in edits.items():
            if name in self.original:
                self.set(name, script)
            else:
                notes.append(f'Voice preset {name[2:]} does not exist in this ROM: skipped.')
        return notes

    # ----- names shown in the lists

    @staticmethod
    def voice_label(name):
        return name[2:].replace('Spk_', '', 1)

    @staticmethod
    def label(name):
        return name[2:]

    def mark(self, name, label):
        """The label with a dot in front when the preset was changed."""
        return (CHANGED_MARK if self.changed(name) else '') + label

    def command_label(self, name):
        """'Spd   speed': the command and, when its script says so, the property its value sets."""
        found = self.placeholder(name)
        if found and found[0] in SCRIPT_KEYS:
            return f'{self.label(name)}   {SPEECH_PROPS[SCRIPT_KEYS[found[0]]][0].lower()}' + (', relative' if found[1] else '')
        return self.label(name)

    # ----- commands: tags written in a text

    def placeholder(self, name):
        """(letter, relative) of the script item whose value comes from the tag, or None when the command takes no value."""
        for key, value in script_parse(self.script(name)):
            if key not in 'QZ' and value in ('', '+'):
                return key, value == '+'
        return None

    def default_value(self, name):
        """The value to try first with a command: the one the game uses most, else a neutral one. None for no value."""
        found = self.placeholder(name)
        if found is None:
            return None
        used = self.tag_values.get(name[2:])
        if used:
            return used[0]
        key, relative = found
        return '0' if relative or key not in SCRIPT_KEYS else str(SPEECH_PROPS[SCRIPT_KEYS[key]][3])

    def try_values(self, name):
        """Values offered for a command: those the game writes with it, then the neutral one."""
        values = list(self.tag_values.get(name[2:], []))
        neutral = self.default_value(name)
        if neutral is not None and neutral not in values:
            values.append(neutral)
        return values

    def tag(self, name, value=None):
        """The command as written in a text, with its value when it takes one."""
        return tag_text(name[2:], value if self.placeholder(name) else None)
