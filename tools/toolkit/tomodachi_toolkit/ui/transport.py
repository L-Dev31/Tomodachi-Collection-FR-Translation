"""Listening to a sound: play it from a point, pause it (the point is kept) and play it again from there, or move the point. The audio player of
the window plays a sound only from its start, so the part from the point is handed to it."""
import time


class Transport:
    """A sound that is played, paused and moved. player: a function that gives the audio player of the window (looked up each time, so
    that the one in use is the one that plays). rate: samples a second of the sound; pcm: its samples.

    playing     whether the sound is going on now
    duration    the length of the sound, in seconds
    position()  the seconds reached in the sound (it stops counting at its end)
    """

    def __init__(self, player):
        self.player = player
        self.pcm, self.rate, self.offset, self.began = None, 1, 0.0, None

    @property
    def playing(self):
        return self.began is not None

    @property
    def duration(self):
        return 0.0 if self.pcm is None else len(self.pcm) / self.rate

    def position(self):
        if self.began is None:
            return self.offset
        return min(self.duration, self.offset + time.monotonic() - self.began)

    def load(self, pcm, rate, offset=0.0):
        """Takes another sound, paused at offset seconds from its start (what was playing stops)."""
        self.pause()
        self.pcm, self.rate = pcm, rate
        self.offset = min(max(offset, 0.0), self.duration)

    def play(self):
        """Plays from the point (from the start when the point is at the end). Returns an error text, or None."""
        if self.pcm is None or self.playing:
            return None
        if self.offset >= self.duration - 0.02:
            self.offset = 0.0
        error = self.player().play(self.rate, self.pcm[int(self.offset * self.rate):])
        if error is None:
            self.began = time.monotonic()
        return error

    def pause(self):
        """Stops the sound and keeps the point it is at."""
        if self.began is not None:
            self.offset = self.position()
            self.began = None
            self.player().stop()

    def seek(self, seconds):
        """Moves the point; a sound that plays goes on from the new point. Returns an error text, or None."""
        was = self.playing
        self.pause()
        self.offset = min(max(seconds, 0.0), self.duration)
        return self.play() if was else None

    def stop(self):
        """Stops the sound and goes back to its start."""
        self.pause()
        self.offset = 0.0
