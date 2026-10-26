"""The .tomods project file: every setting of the toolkit in one file."""
import base64
import json
import zlib

from .features.speech.apply import speech_parts
from .features.speech.lines import lines_ok
from .features.speech.presets import script_check
from .features.keyboard import KEYBOARDS
from .features.meta import LANGS
from .core.bmg import bmg_problems, bmg_raw


PROJECT_MARK = b'TOMODS1:'


def project_dump(cur, order, meta, bmg, images, models=None, audio=None, speech=None, source=None):
    m = dict(meta)
    if 'icon' in m:
        m['icon'] = [base64.b64encode(x).decode() for x in m['icon']]

    def b64(b):
        return base64.b64encode(zlib.compress(b)).decode()

    body = {'currency': cur, 'keyboard': order, 'meta': m, 'bmg': {n: b64(b) for n, b in bmg.items()},
            'images': {p: {str(i): b64(b) for i, b in subs.items()} for p, subs in images.items()},
            'models': {p: {str(i): b64(b) for i, b in subs.items()} for p, subs in (models or {}).items()},
            'audio': {str(i): {'rate': a['rate'], 'pcm': b64(a['pcm'])} for i, a in (audio or {}).items()},
            'speech': dict(speech or {}), 'source': dict(source or {}), 'version': 1}
    return PROJECT_MARK + zlib.compress(json.dumps(body).encode())


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


def project_load(blob):
    if not bytes(blob).startswith(PROJECT_MARK):
        raise ValueError('This file has no project data')
    raw = json.loads(zlib.decompress(bytes(blob)[len(PROJECT_MARK):]))
    cur = raw.get('currency') or {}
    if cur and not (isinstance(cur.get('code'), str) and isinstance(cur.get('symbol'), str) and len(cur['symbol']) == 1):
        raise ValueError('Bad currency settings')
    order = raw.get('keyboard') or list(KEYBOARDS)
    if sorted(order) != sorted(KEYBOARDS):
        raise ValueError('Bad keyboard order')
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
    source = raw.get('source') or {}
    if not isinstance(source, dict):
        raise ValueError('Bad project header')
    return {'currency': cur, 'keyboard': order, 'meta': meta, 'bmg': bmg, 'images': images, 'models': models, 'audio': audio, 'speech': speech, 'source': source}
