"""Runs the speech engine in a thread, one sound at a time, and keeps the last sounds."""
import collections
import threading

from .armvm.errors import ArmCancelled
from .engine import SPEECH_SAMPLE_RATE


class Job:
    """A sound being made. result stays None until it is done, then it is ('ok', pcm), ('cancel', None) or ('error', text)."""

    def __init__(self, key):
        self.key = key
        self.result = None


class Synthesizer:
    KEPT = 8  # sounds kept for an instant replay

    def __init__(self, speaker):
        self.speaker = speaker
        self.sounds = collections.OrderedDict()
        self.job = None

    @staticmethod
    def key(text, voice, emotion, edits):
        """What a sound depends on: text (bytes), voice and emotion preset names, edited scripts."""
        return text, voice, emotion, tuple(sorted(edits.items()))

    def cached(self, key):
        """The sound already made for this key (PCM bytes) or None."""
        pcm = self.sounds.get(key)
        if pcm is not None:
            self.sounds.move_to_end(key)
        return pcm

    @property
    def busy(self):
        return self.job is not None and self.job.result is None

    @property
    def seconds(self):
        """Seconds of sound the running job has made so far."""
        return self.speaker.done / SPEECH_SAMPLE_RATE

    def start(self, text, voice, emotion, edits):
        """Makes a sound in a thread and returns its Job. Only one job runs at a time."""
        if self.busy:
            raise RuntimeError('A sound is already being made.')
        job = Job(self.key(text, voice, emotion, edits))
        self.speaker.cancel = False
        self.job = job
        threading.Thread(target=self._run, args=(job, text, voice, emotion, dict(edits)), daemon=True).start()
        return job

    def _run(self, job, text, voice, emotion, edits):
        try:
            pcm = self.speaker.speak(text, voice=voice, emotion=emotion, presets=edits)
        except ArmCancelled:
            job.result = ('cancel', None)
            return
        except Exception as e:
            job.result = ('error', str(e))
            return
        self.sounds[job.key] = pcm
        while len(self.sounds) > self.KEPT:
            self.sounds.popitem(last=False)
        job.result = ('ok', pcm)

    def cancel(self):
        if self.busy:
            self.speaker.cancel = True
