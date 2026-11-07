"""WAV files and resampling, done by scipy. Sound travels as a list (or an array) of 16 bit mono samples."""
import io
import warnings
from fractions import Fraction

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly


def wav_write(rate, pcm):
    """A WAV file (16 bit mono) from a list or an array of samples."""
    out = io.BytesIO()
    wavfile.write(out, rate, np.asarray(pcm, np.int16))
    return out.getvalue()


def wav_read(b):
    """(rate, samples) of a WAV file of 8, 16, 24 or 32 bit PCM or of floats, with its channels mixed into one of 16 bits (a list)."""
    b = bytes(b)
    if b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        raise ValueError('Not a WAV file')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')                          # chunks of other kinds (markers, notes...) are left out
            rate, data = wavfile.read(io.BytesIO(b))
    except Exception as e:
        raise ValueError('Unsupported or broken WAV file (use 8, 16, 24 or 32 bit PCM): %s' % e) from None
    if data.dtype == np.uint8:
        data = (data.astype(np.int32) - 128) << 8
    elif data.dtype == np.int32:
        data = data >> 16
    elif data.dtype.kind == 'f':
        data = data * 32767
    elif data.dtype != np.int16:
        raise ValueError('Unsupported WAV format (use 8, 16, 24 or 32 bit PCM)')
    mono = data.astype(np.float64).mean(axis=1) if data.ndim > 1 else data
    return rate, np.clip(np.trunc(mono), -32768, 32767).astype(np.int16).tolist()


def resample_ratio(src, dst):
    """The new rate over the old one as a fraction of small numbers (the usual rates of sound come out exact)."""
    return Fraction(dst, src).limit_denominator(1000)


def resample_length(count, src, dst):
    """How many samples `count` samples make once resampled from the rate src to the rate dst."""
    ratio = resample_ratio(src, dst)
    return -(-count * ratio.numerator // ratio.denominator)


def resample(pcm, src, dst):
    """The samples at another rate. Going down, what the new rate cannot hold is filtered out first, or it would come back as noise."""
    if src == dst or len(pcm) < 2:
        return list(pcm)
    ratio = resample_ratio(src, dst)
    out = resample_poly(np.asarray(pcm, np.float64), ratio.numerator, ratio.denominator)
    return np.clip(np.rint(out), -32768, 32767).astype(np.int16).tolist()
