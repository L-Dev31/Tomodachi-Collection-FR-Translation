"""Plays 16 bit mono sound through what the system offers (no sound library needed)."""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile

from ..features.audio.wav import wav_write

PLAYERS = (['afplay'], ['paplay'], ['aplay', '-q'], ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet'])


class AudioPlayer:
    def __init__(self):
        self.folder = None
        self.proc = None
        atexit.register(self.close)

    def play(self, rate, pcm):
        """Starts playing. Returns None, or the reason why nothing plays."""
        if not self.folder:
            self.folder = tempfile.mkdtemp(prefix='tomodachi_')
        path = os.path.join(self.folder, 'play.wav')
        self.stop()
        with open(path, 'wb') as f:
            f.write(wav_write(rate, pcm))
        try:
            if sys.platform.startswith('win'):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return None
            for cmd in PLAYERS:
                if shutil.which(cmd[0]):
                    self.proc = subprocess.Popen(cmd + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return None
            return 'No audio player found (install pulseaudio-utils or alsa-utils).'
        except Exception as e:
            return f'Cannot play: {e}'

    def stop(self):
        if sys.platform.startswith('win'):
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        elif self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None

    def close(self):
        self.stop()
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.folder = None
