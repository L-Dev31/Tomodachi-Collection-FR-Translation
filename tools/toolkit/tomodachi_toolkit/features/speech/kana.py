"""The sounds of the speech engine: katakana with their romaji, the marks that shape the rhythm, and how a text is cut into sounds.

The engine only reads katakana. A sound (a mora) is one katakana, or one katakana followed by a small one (キャ, ファ, ウォ).
Nothing here is typed by the person: the Voice tab offers these tables as buttons."""

# ----- the marks the engine understands
# mark -> (name, what it does). The ASCII twins (_ . ! ? / | ') sound exactly the same and are found in some game lines.
# A line break inside a text also acts as ／ (it is how some game lines are written).
MARKS = {
    '＿': ('short pause', 'A short pause, about 0.2 s.'),
    '．': ('long pause', 'A long pause, like the end of a sentence (about 0.9 s).'),
    '！': ('exclamation', 'A long pause. The part before it is said a little higher.'),
    '？': ('question', 'A long pause with a question tone.'),
    '／': ('new melody', 'No pause. The melody starts again from here, lower. A line break does the same.'),
    '｜': ('new group', 'No pause. A new group of sounds starts here.'),
    '’': ('soft break', 'No pause. A light break in the melody.'),
}
ASCII_MARKS = {'_': '＿', '.': '．', '!': '！', '?': '？', '/': '／', '|': '｜', "'": '’', '\n': '／', '\r': '／'}
LENGTHEN = 'ー'
LONG_PAUSE = '．！？'


def mark_name(c):
    """Name of a mark (fullwidth or ASCII), or '' when c is not a mark."""
    return MARKS.get(ASCII_MARKS.get(c, c), ('',))[0]


def mark_info(c):
    return MARKS.get(ASCII_MARKS.get(c, c), ('', ''))[1]


# ----- katakana tables: (katakana, romaji)

def _row(text):
    """'ア a イ i' -> [('ア', 'a'), ('イ', 'i')]"""
    words = text.split()
    return list(zip(words[0::2], words[1::2]))


BASIC = [
    _row('ア a イ i ウ u エ e オ o'),
    _row('カ ka キ ki ク ku ケ ke コ ko'),
    _row('サ sa シ shi ス su セ se ソ so'),
    _row('タ ta チ chi ツ tsu テ te ト to'),
    _row('ナ na ニ ni ヌ nu ネ ne ノ no'),
    _row('ハ ha ヒ hi フ fu ヘ he ホ ho'),
    _row('マ ma ミ mi ム mu メ me モ mo'),
    _row('ヤ ya ユ yu ヨ yo'),
    _row('ラ ra リ ri ル ru レ re ロ ro'),
    _row('ワ wa ヲ wo ン n ッ (stop) ー (long)'),
]

VOICED = [
    _row('ガ ga ギ gi グ gu ゲ ge ゴ go'),
    _row('ザ za ジ ji ズ zu ゼ ze ゾ zo'),
    _row('ダ da ヂ ji ヅ zu デ de ド do'),
    _row('バ ba ビ bi ブ bu ベ be ボ bo'),
    _row('パ pa ピ pi プ pu ペ pe ポ po'),
    _row('ヴ vu'),
]

COMBINED = [
    _row('キャ kya キュ kyu キョ kyo ギャ gya ギュ gyu ギョ gyo'),
    _row('シャ sha シュ shu ショ sho ジャ ja ジュ ju ジョ jo'),
    _row('チャ cha チュ chu チョ cho ニャ nya ニュ nyu ニョ nyo'),
    _row('ヒャ hya ヒュ hyu ヒョ hyo ビャ bya ビュ byu ビョ byo'),
    _row('ピャ pya ピュ pyu ピョ pyo ミャ mya ミュ myu ミョ myo'),
    _row('リャ rya リュ ryu リョ ryo'),
]

FOREIGN = [
    _row('ファ fa フィ fi フェ fe フォ fo フュ fyu'),
    _row('ティ ti ディ di トゥ tu ドゥ du テュ tyu デュ dyu'),
    _row('ウィ wi ウェ we ウォ wo イェ ye'),
    _row('シェ she ジェ je チェ che'),
    _row('ツァ tsa ツィ tsi ツェ tse ツォ tso'),
    _row('ヴァ va ヴィ vi ヴェ ve ヴォ vo'),
    _row('クァ kwa クィ kwi クェ kwe クォ kwo'),
    _row('グァ gwa グィ gwi グェ gwe グォ gwo'),
]

SMALL_ONLY = _row('ァ a ィ i ゥ u ェ e ォ o ャ ya ュ yu ョ yo')

ROMAJI = {kana: romaji for table in (BASIC, VOICED, COMBINED, FOREIGN, [SMALL_ONLY]) for row in table for kana, romaji in row}
ROMAJI.update({'ッ': 'stop', 'ー': 'long'})

# ----- cutting a text into sounds

SMALL = 'ァィゥェォャュョヮ'
KANA_FIRST, KANA_LAST = 'ァ', 'ヺ'


def is_kana(c):
    """A katakana the engine reads (the long mark included)."""
    return KANA_FIRST <= c <= KANA_LAST or c == LENGTHEN


def is_base(c):
    """A katakana that may be followed by a small one: not a stop, a long mark, an N or a small kana itself."""
    return is_kana(c) and c not in SMALL + 'ッンー'


def sounds(text):
    """The katakana of a text as sounds: 'キャット' -> ['キャ', 'ッ', 'ト']. Other characters are not expected."""
    out = []
    for c in text:
        if c in SMALL and out and len(out[-1]) == 1 and is_base(out[-1]):
            out[-1] += c
        else:
            out.append(c)
    return out


def romaji(sound):
    """Romaji of a sound (a few letters), or '' when unknown."""
    return ROMAJI.get(sound, '')


def sound_kind(sound):
    """'stop' for ッ, 'long' for ー, else 'sound'."""
    return {'ッ': 'stop', 'ー': 'long'}.get(sound, 'sound')


def normal_sound(text):
    """The katakana of a text without the long marks, the marks and anything else: two spellings with the same
    letters sound the same way up to rhythm. Used to match a line with its twin."""
    return ''.join(c for c in text if is_kana(c) and c != LENGTHEN)
