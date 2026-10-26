"""Runs the Sharp speech engine found in the ARM9 and returns PCM."""
import struct
import zlib

from .armvm.machine import ArmVm
from .armvm.errors import ArmCancelled
from .presets import SPEECH_PROPS, preset_read, preset_tables, preset_write


SPEECH_TAG = b'[SDK+SHARP:SHTTS'


SPEECH_SIGS = {
    'init': (0x0208D4C8, 12, 0x597E1DF6),
    'setprop': (0x0208D6F8, 12, 0x8E16D3D4),
    'speak': (0x0208D0CC, 24, 0x523D5379),
    'sync': (0x0208D230, 12, 0x7FF60824),
    'lock': (0x02007E1C, 10, 0x158796E6),
    'unlock': (0x02007EA0, 10, 0x17DEF719),
    'sleep': (0x02007964, 10, 0x1CBEEBC4),
}


SPEECH_SYNC = 0x0208D248


SPEECH_CTX, SPEECH_TEXT, SPEECH_HOOK = 0x02200000, 0x02300000, 0x02400000


SPEECH_SAMPLE_RATE = 11025


def speech_sig(arm9, addr, n):
    o = addr - 0x02000000
    if o < 0 or o + 4 * n > len(arm9):
        return None
    ws = [w & 0xFF000000 if w & 0x0E000000 == 0x0A000000 else w for w in struct.unpack_from('<%dI' % n, arm9, o)]
    return zlib.crc32(struct.pack('<%dI' % n, *ws))


def speech_check(arm9):
    """None when the ROM holds the engine this code knows, else the reason it cannot be used."""
    i = bytes(arm9).find(SPEECH_TAG)
    if i < 0:
        return 'This ROM has no Sharp speech engine.'
    for name, (addr, n, crc) in SPEECH_SIGS.items():
        if speech_sig(arm9, addr, n) != crc:
            tag = bytes(arm9[i:i + 40]).split(b'\0')[0].decode('latin1')
            return f'Unknown build of the speech engine ({tag}): {name} not found.'
    return None


class Speaker:
    """Runs the speech engine found in an ARM9 image and returns 11025 Hz mono 16 bit PCM."""

    def __init__(self, arm9):
        why = speech_check(arm9)
        if why:
            raise ValueError(why)
        self.arm9 = bytes(arm9)
        self.bases = preset_tables(self.arm9)
        if not self.bases:
            raise ValueError('Voice presets not found in this ROM.')
        self.presets = preset_read(self.arm9, self.bases[0])
        names = [n for n, _ in self.presets]
        self.voices = [n for n in names if n.startswith('<\\Spk_')]
        self.emotions = names[names.index('<\\angry'):names.index('<\\whisper') + 1] if '<\\angry' in names and '<\\whisper' in names else []
        tag = self.arm9[self.arm9.find(SPEECH_TAG):][:40].split(b'\0')[0].decode('latin1')
        self.tag = tag.strip('[]')
        self.vm = None
        self.cancel = False
        self.done = 0

    def image(self, presets=None):
        img = bytearray(self.arm9)
        for name, script in (presets or {}).items():
            preset_write(img, self.bases, name, script)
        struct.pack_into('<I', img, SPEECH_SYNC - 0x02000000, 0xE3A04001)
        stub = struct.pack('<II', 0xE3A00000, 0xE12FFF1E)
        for k in ('lock', 'unlock', 'sleep'):
            o = SPEECH_SIGS[k][0] - 0x02000000
            img[o:o + 8] = stub
        return bytes(img)

    def speak(self, text, voice=None, emotion=None, props=None, presets=None):
        """text: bytes (Shift-JIS katakana). voice/emotion: preset names. props: {property id: value}.
        presets: {name: script} edits to apply first. Returns PCM bytes; raises ArmCancelled when cancelled."""
        img = self.image(presets)
        if self.vm is None:
            self.vm = ArmVm(img)
        vm = self.vm
        vm.mem[:len(img)] = img
        vm.mem[len(img):] = bytes(len(vm.mem) - len(img))
        vm.R[:] = [0] * 16
        out = []
        self.done = 0

        def pcm(R):
            out.append(vm.read(R[1], 2 * R[0]))
            self.done += R[0] // 2
            if self.cancel:
                raise ArmCancelled()
            return R[14]

        vm.hook(SPEECH_HOOK, pcm)
        ctx = SPEECH_CTX
        vm.call(SPEECH_SIGS['init'][0], [ctx])

        def setp(pid, val):
            if vm.call(SPEECH_SIGS['setprop'][0], [ctx, pid, val & 0xFFFFFFFF]) != 0:
                raise ValueError(f'The engine refuses {val} for {SPEECH_PROPS.get(pid, (pid,))[0]}.')

        if voice:
            setp(1, 0x101 + self.voices.index(voice))
        if emotion:
            setp(2, 0x201 + self.emotions.index(emotion))
        for pid, val in (props or {}).items():
            setp(pid, val)
        vm.write(SPEECH_TEXT, bytes(text) + b'\0\0')
        vm.call(SPEECH_SIGS['speak'][0], [ctx, SPEECH_TEXT, 1, 0], [SPEECH_HOOK, 0])
        raw = b''.join(out)
        if not raw:
            raise ValueError('The engine has nothing to say for this text (check the characters).')
        mono = struct.unpack('<%dh' % (len(raw) // 2), raw)[1::2]
        return struct.pack('<%dh' % len(mono), *mono)
