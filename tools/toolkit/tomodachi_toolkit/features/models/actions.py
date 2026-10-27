"""The animations a model can play: the ones of its own archive and the shared ones of the Mii skeleton."""
import re

from .anim import bca_animations
from .texanim import pat_animations, srt_animations, vis_animations

SHARED_FOLDER = '/Mdl/Ica/'          # the animations of the Mii skeleton live apart from the models
PREFERRED = ('wait00', 'idle00')     # played first when a model has no animation of its own
READERS = ((b'BCA0', bca_animations), (b'BTA0', srt_animations), (b'BTP0', pat_animations), (b'BVA0', vis_animations))
AMBIENT = ('srt', 'vis')             # kinds that go on all the time (a water that flows, lights that blink) when nothing else shares their name


def fits(anim, scene):
    """Whether an animation changes anything in the models on show: the skeletons and the visibilities need as many nodes as
    the animation has, the textures need materials of the same names."""
    models = [scene.models[mi] for mi in scene.shown]
    if anim.kind == 'joint':
        return any(len(m['nodes']) == len(anim.nodes) for m in models)
    if anim.kind == 'vis':
        return any(len(m['nodes']) == anim.count for m in models)
    return any(mat['name'] in anim.tracks for m in models for mat in m['materials'])


def apply(anim, scene, frame, state):
    """Puts what an animation does at a frame into state (the lists of what render takes), for the models it fits."""
    for mi in scene.shown:
        model = scene.models[mi]
        if anim.kind == 'joint':
            if len(model['nodes']) == len(anim.nodes):
                state['poses'][mi] = anim.pose(model['nodes'], frame)
        elif anim.kind == 'vis':
            if len(model['nodes']) == anim.count:
                state['visible'][mi] = anim.at(frame)
        else:
            for k, mat in enumerate(model['materials']):
                if anim.kind == 'srt' and mat['name'] in anim.tracks:
                    state['srts'][mi, k] = anim.tracks[mat['name']].at(frame)
                elif anim.kind == 'pat':
                    picture = anim.at(mat['name'], frame)
                    if picture is not None:
                        state['patterns'][mi, k] = picture


class Action:
    """What plays together under one name: the animations of every kind that share it (a skeleton, textures, parts that show up).
    The ambient ones go on at the same time, whatever the action."""

    def __init__(self, layers, source, ambient=()):
        self.layers, self.ambient, self.source = list(layers), list(ambient), source
        self.name = self.layers[0].name
        self.frames = max(1, max(a.frames for a in self.layers))
        self.label = '%s   (%d frames)' % (self.name, self.frames)

    def state(self, scene, frame):
        """What to change in the scene at a frame: {'poses': ..., 'srts': ..., 'patterns': ..., 'visible': ...}, as render takes them."""
        out = {'poses': {}, 'srts': {}, 'patterns': {}, 'visible': {}}
        for a in self.layers + self.ambient:
            apply(a, scene, frame % max(1, a.frames), out)
        return out


def natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def archive_animations(subfiles):
    """Every animation of the sub files of an archive: skeletons, textures that move or change, parts that show up."""
    out = []
    for f in subfiles:
        for magic, read in READERS:
            if f[:4] == magic:
                try:
                    out += read(f)
                except Exception:
                    continue
    return out


def archive_actions(subfiles, source, counts):
    """The skeleton animations of the sub files of an archive that fit models with the given numbers of nodes."""
    return [Action([a], source) for a in archive_animations(f for f in subfiles if f[:4] == b'BCA0') if len(a.nodes) in counts]


def layered_actions(subfiles, source, scene):
    """The actions of an archive for the models of a scene. The animations that share a name play together, whatever their kind.
    A texture that moves or a part that shows up, when nothing else has its name, goes on under all the actions."""
    groups = {}
    for a in archive_animations(subfiles):
        if fits(a, scene):
            groups.setdefault(a.name, []).append(a)
    single = [g for g in groups.values() if len(g) == 1 and g[0].kind in AMBIENT]
    main = [g for g in groups.values() if not (len(g) == 1 and g[0].kind in AMBIENT)]
    if not main:
        return [Action(g, source) for g in groups.values()]
    return [Action(g, source, [x[0] for x in single]) for g in main]


def shared_actions(rom):
    """{number of nodes: [actions]} of the shared Mii animations, read once per ROM, without the copies that several files hold."""
    cache = getattr(rom, 'shared_actions', None)
    if cache is None:
        cache, seen = {}, set()
        for path in sorted(p for p in rom.files if p.startswith(SHARED_FOLDER)):
            try:
                subs = rom.subfiles(path)
            except Exception:
                continue
            for a in archive_actions(subs, path, set(range(2, 256))):
                skeleton = a.layers[0]
                key = (a.name, a.frames, len(skeleton.nodes))
                if key not in seen:
                    seen.add(key)
                    cache.setdefault(len(skeleton.nodes), []).append(a)
        for v in cache.values():
            v.sort(key=lambda a: natural(a.name))
        rom.shared_actions = cache
    return cache


def model_actions(rom, path, scene):
    """(actions, index of the one to play first). rom is the open ROM (its session), path the archive of the model,
    scene the models on show."""
    actions = layered_actions(rom.subfiles(path), path, scene)
    if not any(layer.kind == 'joint' for a in actions for layer in a.layers):
        table = shared_actions(rom)
        for n in sorted({len(scene.models[mi]['nodes']) for mi in scene.shown}):
            actions += table.get(n, [])
    first = next((i for n in PREFERRED for i, a in enumerate(actions) if a.name == n), 0)
    return actions, first
