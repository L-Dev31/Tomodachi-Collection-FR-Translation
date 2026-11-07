"""The tabs of the window, in groups (a group is one page of the top notebook). To add a tab, write a subclass of Tab and list it here."""
from .audio import AudioTab
from .bgm import BgmTab
from .bmg import BmgTab
from .currency import CurrencyTab
from .fonts import FontsTab
from .images import ImagesTab
from .keyboard import KeyboardTab
from .meta import MetaTab
from .models import ModelsTab
from .rom import RomTab
from .voice import VoiceTab

GROUPS = (
    ('ROM', (RomTab, MetaTab)),
    ('Location', (CurrencyTab, KeyboardTab, FontsTab)),
    ('Dialog', (BmgTab, VoiceTab)),
    ('Graphics', (ImagesTab, ModelsTab)),
    ('Sound', (AudioTab, BgmTab)),
)
