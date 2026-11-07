"""What the game codes and the effects of the speech lines stand for, in a few words, each with its own colour and icon.

A game code {08 01 TT 00 NN 00} is a blank that the game fills when it shows the message (the function at 0x0202E860 of the ARM9 of the FR
3.5.1 build puts the string number NN that the scene gave to the message there). The type does not say what the string is, the message does:
the words below are read from where each code stands in the lines (what the player sees around it)."""
import colorsys
import collections

CodeStyle = collections.namedtuple('CodeStyle', 'label short icon colour hint rank')
EffectStyle = collections.namedtuple('EffectStyle', 'label short icon colour hint')
Effect = collections.namedtuple('Effect', 'tag label short icon hint')


def colour(n):
    """The colour of the n-th item of the palettes: the hues are spread with the golden angle, so that two neighbours never look alike."""
    r, g, b = colorsys.hsv_to_rgb((n * 0.618034) % 1.0, 0.72, 0.66)
    return '#%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))


# the icon of each family of codes: the codes that are the same thing in a line share it, and their colours tell them apart
FAMILY_ICON = {'mii': '☺', 'name': '✎', 'syllable': '♪', 'nickname': '♡', 'word': '“', 'item': '◆', 'news': '#', 'phrase': '¶'}

# the game codes, in the order of the palette: the people, the names, the words, the items, the news and the phrases
# (type, number), label, short label for a block, family (its icon), what it stands for
CODES = (
    ((0x1f, 0), 'Mii', 'Mii', 'mii', 'the Mii who speaks: its name is said here'),
    ((0x1f, 1), 'Other Mii', 'Mii 2', 'mii', 'another Mii of the conversation: its name is said here'),
    ((0x01, 0), 'Name', 'Name', 'name', 'a name said in the line (a Mii or a person)'),
    ((0x01, 1), 'Name 2', 'Name 2', 'name', 'a second name said in the line'),
    ((0x01, 2), 'Syllable 3', 'Syl 3', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 3), 'Syllable 4', 'Syl 4', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 4), 'Syllable 5', 'Syl 5', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 5), 'Syllable 6', 'Syl 6', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 6), 'Syllable 7', 'Syl 7', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 7), 'Syllable 8', 'Syl 8', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x01, 8), 'Syllable 9', 'Syl 9', 'syllable', 'one syllable of a name, sung or spelled out'),
    ((0x03, 0), 'Nickname', 'Nick', 'nickname', 'the short name of a Mii (…cchi)'),
    ((0x0a, 0), 'Word', 'Word', 'word', 'a word or a saying of the speaker'),
    ((0x0a, 1), 'Word 2', 'Word 2', 'word', 'a second word or saying'),
    ((0x14, 0), 'Item', 'Item', 'item', 'a food or an item (a favourite, a gift)'),
    ((0x14, 1), 'Item 2', 'Item 2', 'item', 'a second food or item'),
    ((0x14, 2), 'Item 3', 'Item 3', 'item', 'a third food or item'),
    ((0x1e, 0), 'News 1', 'News 1', 'news', 'a blank of the news, filled by the game: a name, an hour or a day'),
    ((0x1e, 1), 'News 2', 'News 2', 'news', 'the next blank of the news: a name, minutes or a year'),
    ((0x1e, 2), 'News 3', 'News 3', 'news', 'a blank of the news, usually a name'),
    ((0x1e, 3), 'News 4', 'News 4', 'news', 'a blank of the news, usually a name'),
    ((0x1e, 4), 'News 5', 'News 5', 'news', 'a blank of the news: a number or a word'),
    ((0x1e, 5), 'News 6', 'News 6', 'news', 'a blank of the news: a word between quotes'),
    ((0xfa, 0), 'Phrase 1', 'Phrase', 'phrase', 'a ready-made piece of text (a month, a blood type, a colour...)'),
    ((0xfa, 1), 'Phrase 2', 'Phrase 2', 'phrase', 'the next ready-made piece (a day, an ending...)'),
)
CODE_RANK = {key: n for n, (key, *_) in enumerate(CODES)}


def code_info(code):
    """What a game code (as the lines hold it, '08011f000100') stands for: label, short label, icon, colour, what it is, and its place in the
    palette (its rank). A code the list does not know is said so."""
    try:
        key = (int(code[4:6], 16), int(code[8:10], 16))
    except ValueError:
        key = None
    if key in CODE_RANK:
        n = CODE_RANK[key]
        _, label, short, family, hint = CODES[n]
        return CodeStyle(label, short, FAMILY_ICON[family], colour(n), hint, n)
    return CodeStyle(f'Code {code[4:6]} {code[8:10]}', '?', '?', colour(99), 'a blank that the game fills: this code is not known', 999)


# the commands of the engine (presets), in the order of the palette: the values, the manner of speaking, the echo, the filter, the rest
EFFECTS = (
    Effect('Pit', 'Pitch', 'Pitch', '↕', 'sets the pitch of the voice from here on: higher or lower'),
    Effect('Spd', 'Speed', 'Speed', '»', 'sets how fast the next sounds are said'),
    Effect('Vol', 'Volume', 'Volume', '◐', 'sets how loud the next sounds are'),
    Effect('Pau', 'Pause', 'Pause', '‖', 'a silence, for the time given'),
    Effect('Emp', 'Emphasis', 'Emph.', '✱', 'the next sounds are louder, quicker and higher'),
    Effect('Dem', 'Soften', 'Soft.', '≈', 'the next sounds are quieter, slower and lower'),
    Effect('Acc', 'Accent', 'Accent', '▲', 'stresses the words'),
    Effect('Prm', 'Phrase', 'Phrase', '≡', 'stresses the phrases'),
    Effect('RPrm', 'Phrase +/-', 'Phr. +/-', '±', 'moves the stress of the phrases up or down'),
    Effect('Lwp', 'Tone', 'Tone', '○', 'a brighter (high) or a duller (low) voice'),
    Effect('Ring', 'Metallic', 'Metal.', '◇', 'a ringing, metallic voice'),
    Effect('Echo', 'Echo', 'Echo', '≋', 'an echo: its delay and its level together'),
    Effect('Ecl', 'Echo delay', 'Echo dly', '→', 'the time between two echoes'),
    Effect('Ecg', 'Echo level', 'Echo lvl', '↑', 'how loud the echo is'),
    Effect('Fir', 'Filter', 'Filter', '∩', 'a filtered voice: its delay and its level together'),
    Effect('Firl', 'Filter delay', 'Flt dly', '⇒', 'the delay of the filter'),
    Effect('Firg', 'Filter level', 'Flt lvl', '⇑', 'the level of the filter'),
    Effect('Cho', 'Chorus', 'Chorus', '∞', 'a fuller voice, as if several voices sang (not fully understood)'),
    Effect('Ptr', 'Transpose', 'Transp.', '⇄', 'moves the whole line up or down'),
    Effect('sing', 'Singing', 'Sing', '~', 'a singing voice: pitch, accents and transposition together'),
    Effect('Rst', 'Normal', 'Normal', '↺', 'takes back every effect: the normal voice again'),
    Effect('Hsp', 'Unknown', 'Unknown', '?', 'changes the speed and the pitch of the voice (not understood)'),
)
EFFECT_RANK = {e.tag: n for n, e in enumerate(EFFECTS)}


def effect_style(tag):
    """What a command of the engine does, in a few words, with its colour and icon (the tag is the name without the backslash, 'Spd').
    A command the list does not know is grey."""
    n = EFFECT_RANK.get(tag)
    if n is None:
        return EffectStyle(tag, tag, '?', '#888888', 'a command of the engine that is not known')
    e = EFFECTS[n]
    return EffectStyle(e.label, e.short, e.icon, colour(30 + n), e.hint)
