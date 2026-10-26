"""The animations a model can play: the ones of its own file and the shared ones of the Mii skeleton."""
import re

from .anim import bca_animations

SHARED_FOLDER = '/Mdl/Ica/'          # the animations of the Mii skeleton live apart from the models
PREFERRED = ('wait00', 'idle00')     # played first when a model has no animation of its own


class JointAction:
    """A skeleton animation (BCA0): moves the nodes of the models that have as many nodes as the animation."""

    def __init__(self, anim, source):
        self.anim, self.source = anim, source
        self.name, self.frames = anim.name, max(1, anim.frames)
        self.label = '%s   (%d frames)' % (anim.name, anim.frames)

    def state(self, scene, frame):
        """What to change in the scene at a frame: {'poses': {model index: node matrices}}."""
        poses = {}
        for mi in scene.shown:
            nodes = scene.models[mi]['nodes']
            if len(nodes) == len(self.anim.nodes):
                poses[mi] = self.anim.pose(nodes, frame % self.frames)
        return {'poses': poses}


def natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def archive_actions(subfiles, source, counts):
    """The animations of the sub files of an archive that fit models with the given numbers of nodes."""
    out = []
    for f in subfiles:
        if f[:4] == b'BCA0':
            try:
                out += [JointAction(a, source) for a in bca_animations(f) if len(a.nodes) in counts]
            except Exception:
                continue
    return out


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
                key = (a.name, a.frames, len(a.anim.nodes))
                if key not in seen:
                    seen.add(key)
                    cache.setdefault(len(a.anim.nodes), []).append(a)
        for v in cache.values():
            v.sort(key=lambda a: natural(a.name))
        rom.shared_actions = cache
    return cache


def model_actions(rom, path, counts):
    """(actions, index of the one to play first). rom is the open ROM (its session), path the archive of the model,
    counts the numbers of nodes of the models on show."""
    own = archive_actions(rom.subfiles(path), path, counts)
    shared = []
    if not own:
        table = shared_actions(rom)
        for n in sorted(counts):
            shared += table.get(n, [])
    actions = own + shared
    first = next((i for n in PREFERRED for i, a in enumerate(actions) if a.name == n), 0)
    return actions, first
