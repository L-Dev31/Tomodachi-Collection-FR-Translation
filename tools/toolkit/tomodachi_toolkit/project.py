"""The .tomods project file: every setting of the toolkit in one file."""
import base64
import json
import zlib

from .features.bgm.sseq import SseqError, sseq_data
from .features.bgm.timeline import play
from .features.speech.apply import speech_parts
from .features.speech.lines import lines_ok
from .features.speech.presets import script_check
from .features.keyboard import KEYBOARDS, keyboard_config, layouts_problem
from .features.meta import LANGS
from .core.bmg import bmg_problems, bmg_raw


PROJECT_MARK = b'TOMODS1:'


def project_dump(cur, keyboard, meta, bmg, images, models=None, audio=None, speech=None, source=None, bgm=None, fonts=None):
    """keyboard: the part of the keyboard tab ({'order': [...], 'layouts': {...}}) or the order alone."""
    order, layouts = keyboard_config(keyboard)
    m = dict(meta)
    if 'icon' in m:
        m['icon'] = [base64.b64encode(x).decode() for x in m['icon']]

    def b64(b):
        return base64.b64encode(zlib.compress(b)).decode()

    body = {'currency': cur, 'keyboard': order or list(KEYBOARDS), 'layouts': layouts, 'meta': m, 'bmg': {n: b64(b) for n, b in bmg.items()},
            'images': {p: {str(i): b64(b) for i, b in subs.items()} for p, subs in images.items()},
            'models': {p: {str(i): b64(b) for i, b in subs.items()} for p, subs in (models or {}).items()},
            'audio': {str(i): {'rate': a['rate'], 'pcm': b64(a['pcm'])} for i, a in (audio or {}).items()},
            'bgm': {str(i): {'file': b64(e['file']) if e.get('file') else None, 'bank': e.get('bank'), 'volume': e.get('volume')}
                    for i, e in (bgm or {}).items()},
            'speech': dict(speech or {}), 'fonts': dict(fonts or {}), 'source': dict(source or {}), 'version': 1}
    return PROJECT_MARK + zlib.compress(json.dumps(body).encode())


def font_check(part):
    """The 'fonts' part of a project: {font file: {character code: [rows of 0 and 1]}}. Raises ValueError when it is not well formed."""
    if not isinstance(part, dict):
        raise ValueError('Bad fonts data')
    for path, glyphs in part.items():
        for code, rows in glyphs.items():
            if not str(code).isdigit() or not isinstance(rows, list) or not rows or any(not isinstance(r, str) or set(r) - {'0', '1'} for r in rows):
                raise ValueError('Bad font data')
    return part


def speech_check(part):
    """The 'speech' part of a project as {'presets': {...}, 'lines': {...}}. Raises ValueError when it is not well formed.
    Older projects hold the presets alone."""
    if part is not None and not isinstance(part, dict):
        raise ValueError('Bad speech settings')
    for key in ('presets', 'lines'):
        value = (part or {}).get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f'Bad speech {key}')
    presets, lines = speech_parts(part)
    for name, script in presets.items():
        if not (isinstance(name, str) and name.startswith('<\\') and isinstance(script, str)) or script_check(script):
            raise ValueError(f'Bad voice preset {name}')
    bad = lines_ok(lines)
    if bad:
        raise ValueError(bad)
    for group in lines.values():
        for key, (old, new) in group.items():
            try:
                bmg_raw(new)
            except ValueError as e:
                raise ValueError(f'Bad speech line {key}: {e}') from None
    return {'presets': presets, 'lines': lines} if presets or lines else {}


def bgm_check(edits):
    """The 'bgm' part of a project, {sequence number: {'file': SSEQ file or None, 'bank': number or None, 'volume': 0..127 or None}}, with the
    files decoded. Raises ValueError when it is not well formed."""
    if not isinstance(edits, dict):
        raise ValueError('Bad BGM settings')
    out = {}
    for key, edit in edits.items():
        if not (isinstance(edit, dict) and str(key).isdigit()):
            raise ValueError('Bad BGM settings')
        bank, volume, blob = edit.get('bank'), edit.get('volume'), edit.get('file')
        if bank is not None and not (isinstance(bank, int) and 0 <= bank < 65536):
            raise ValueError(f'Bad bank for sequence {key}')
        if volume is not None and not (isinstance(volume, int) and 0 <= volume < 128):
            raise ValueError(f'Bad volume for sequence {key}')
        data = None
        if blob:
            data = zlib.decompress(base64.b64decode(blob))
            try:
                play(sseq_data(data))
            except SseqError as e:
                raise ValueError(f'Sequence {key}: {e}') from None
        out[int(key)] = {'file': data, 'bank': bank, 'volume': volume}
    return out


def project_load(blob):
    if not bytes(blob).startswith(PROJECT_MARK):
        raise ValueError('This file has no project data')
    raw = json.loads(zlib.decompress(bytes(blob)[len(PROJECT_MARK):]))
    cur = raw.get('currency') or {}
    if cur and not (isinstance(cur.get('code'), str) and isinstance(cur.get('symbol'), str) and len(cur['symbol']) == 1):
        raise ValueError('Bad currency settings')
    order = raw.get('keyboard') or list(KEYBOARDS)
    if not isinstance(order, list) or sorted(order) != sorted(KEYBOARDS):
        raise ValueError('Bad keyboard order')
    layouts = raw.get('layouts') or {}
    problem = layouts_problem(layouts)
    if problem:
        raise ValueError(f'Bad keyboard layouts: {problem}')
    meta = dict(raw.get('meta') or {})
    if any(lang not in LANGS for lang in meta.get('titles', {})):
        raise ValueError('Unknown language in titles')
    if 'internal' in meta and (len(meta['internal']) > 12 or not meta['internal'].isascii()):
        raise ValueError('Internal name: 12 ASCII characters max.')
    if 'icon' in meta:
        meta['icon'] = tuple(base64.b64decode(x) for x in meta['icon'])
        if [len(x) for x in meta['icon']] != [512, 32]:
            raise ValueError('Bad icon data')

    def un(s):
        return zlib.decompress(base64.b64decode(s))

    bmg = {}
    for name, b in (raw.get('bmg') or {}).items():
        bmg[name] = un(b)
        bad = bmg_problems(bmg[name])
        if bad:
            raise ValueError(f'{name}: {bad[0]}')
    images = {p: {int(i): un(b) for i, b in subs.items()} for p, subs in (raw.get('images') or {}).items()}
    models = {p: {int(i): un(b) for i, b in subs.items()} for p, subs in (raw.get('models') or {}).items()}
    audio = {}
    for i, a in (raw.get('audio') or {}).items():
        pcm = un(a['pcm'])
        if len(pcm) % 2 or not isinstance(a['rate'], int) or not 1000 <= a['rate'] <= 200000:
            raise ValueError('Bad audio data')
        audio[int(i)] = {'rate': a['rate'], 'pcm': pcm}
    speech = speech_check(raw.get('speech'))
    bgm = bgm_check(raw.get('bgm') or {})
    fonts = font_check(raw.get('fonts') or {})
    source = raw.get('source') or {}
    if not isinstance(source, dict):
        raise ValueError('Bad project header')
    return {'currency': cur, 'keyboard': {'order': order, 'layouts': layouts}, 'meta': meta, 'bmg': bmg, 'images': images, 'models': models, 'audio': audio, 'bgm': bgm, 'speech': speech, 'fonts': fonts, 'source': source}
