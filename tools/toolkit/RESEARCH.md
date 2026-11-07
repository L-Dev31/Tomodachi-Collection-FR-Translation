# Research notes: Tomodachi Collection (DS) FR fan translation

Written so another AI or developer can continue without the previous chat. History: written 2026-10-25 as HANDOFF.md, renamed RESEARCH.md on 2026-10-26, rewritten on 2026-11-03 after the toolkit became a package, got the BGM, Voice and keyboard work and moved to external Python packages. Everything here was verified in the code, in git history, in the tests or in the ROM. Items marked **UNVERIFIED** or **OPEN** are not settled. Sections 13 and 14 (second session of 2026-11-03: the UI rework, and the research on other languages for the speech engine) come last and win where they differ from sections 3.3, 3.6, 3.8, 3.10 and 3.13. "Not played" means that nobody has run it in a console or an emulator.

---

## 1. Where things are

| What | Where |
|---|---|
| Translation repo | `/home/Leo/Documents/GitHub/Tomodachi-Collection-FR-Translation` (Léo's Arch Linux machine; until 2026-10 the work was done on a Windows machine) |
| Toolkit | `tools/toolkit/`: `run.py`, `requirements.txt`, `tomodachi_toolkit/` (the program), `tests/`, this file, and `.venv/` (Léo's virtual environment, not part of the delivery) |
| BMG injector and checker | `tools/bmgrom.py` (not committed, in `.gitignore`) |
| BMG notes | `BMGs/BMG.md` (committed) |
| BMG files in use | `BMGs/test/*_msg_JP.bmg` (7 files) |
| bmge (BMG editor, `build-bmg.js`) | repo L-Dev31.github.io, `projects/demos/bmge` |
| Test ROM | FR build 3.5.1, `Tomodachi_Collection_FR-BUILD3_5_1.nds`: 67,108,864 bytes (64 MiB), CRC32 `f52f57af`, game code `CCUJ` |
| This file | `tools/toolkit/RESEARCH.md` (listed in `.gitignore`, but git has tracked it since commit `2390d48`, so edits show as modified) |

Git state on 2026-11-03: Léo's last commits are `4c12db1` (ui: add credits to footer, fix ListenBar, add nclr_set to nitro), `ec124cf`, `9757b79`, `2390d48` and `7cd2f64` (GUI Upload). Léo makes the commits himself. What is newer than them (new modules such as `features/keyboard/`, `features/bgm/`, `features/speech/files.py`, `ui/tabs/voice/text.py`, `requirements.txt`, changed modules, this file) was written into the working tree from tarballs and is **not committed**. `.gitignore` carries uncommitted changes and lists `/tools/toolkit/tests`, `tools/bmgrom.py`, `tools/toolkit/RESEARCH.md` and some `__pycache__` folders one by one. The tests and `bmgrom.py` have never been committed (0 tracked files); `RESEARCH.md` was committed in `2390d48` in spite of its ignore line, so git tracks it and shows its rewrites as modifications. Git still tracks 10 `.pyc` files from older commits (a `__pycache__/` line in `.gitignore` plus `git rm -r --cached` on them would clear the noise; Léo was told, nothing was done).

The `README.md` at the root of the repo belongs to the translation project and was not touched. The repo has no LICENSE file (see 3.1).

Scripts used for analysis lived in a scratchpad of the earlier (Windows) machine and are not in the repo; what they found is written in this file. For the record: `romlib.py` (`load_rom()`, `blobs(rom)` -> `{'ARM9': (0x2000000, data), 'ovNN': (0x21495E0, data, fid)}`), capstone disassembly helpers (around an address, n instructions), a scan for `str ..., [rX, #offset]` stores across all blobs, a scan for direct `BL 0x202D1EC` callers, `kbstate.py` / `ramdump.py` (passive RAM dump of melonDS; live RAM is the **second** match in `ram_fresh.bin`), the BMG validators, `vm_fuzz.py` (ARM interpreter against Unicorn) and a portable melonDS with test ROMs and save files. `ui.ps1` and `kbrun.ps1` automated the melonDS window: **do not use** (Léo rejected them).

## 2. Working rules set by the user (Léo TOSKU)

- Chat with Léo in French. Code, comments, docs and commit messages are in English. Keep status messages short.
- Never use the em dash in anything written (chat, code, docs).
- Do not verify work by looking at screenshots or rendered images: Léo reports visual problems.
- No heavy test round until Léo says so (the final round is open item 1 in section 6). Static checks (pyflakes), headless Tk checks and `python -m tests` are fine in the meantime.
- Do not commit unless asked. The 2026-11 sessions wrote into the working tree only: a tarball extracted into `tools/toolkit`, checked against a SHA-256 manifest and a combined hash of all `.py` files, then removed. An older note says commit messages were "ultra-concise English, no Co-Authored-By line" at Léo's request (2026-10-26); the reminder of the 2026-11-03 session asks for attribution lines. Ask Léo if a commit is requested.
- Update the repo progressively, not in one big drop at the end.
- Design rules: a simplified UX without losing capabilities; modular code, with `run.py` as the bridge that starts it; data faithful to the original game; "keep the process as simple codewise as possible" (2026-11-03).
- Raw data (2026-11-03): text that goes to or from the game is handed over with the least alteration. No romaji or French to katakana conversion, and the export and import write and read exactly what the ROM holds. Where a person has to write katakana, they write it.
- Dependencies (2026-11-03): use external Python packages whenever they exist, so the toolkit carries fewer lines of code without losing quality. Permissive licenses are preferred. ndspy (GPL-3+) and unicorn (GPL-2) would replace own code (ROM, NARC, SDAT, BMG and LZ handling; the ARM interpreter) but are **held** until Léo chooses a license for the repo (asked, no answer yet).
- Do not automate melonDS (no clicking, no killing the instance). Several attempts were rejected. Use passive RAM reads only. Léo does the in-game tests.
- Be honest about what is verified. Report failures plainly.

## 3. Toolkit ("Tomodachi Location Toolkit")

### 3.1 Running it, packages, tests

- `python run.py` from `tools/toolkit`. Tkinter is required. The code was built and tested on Python 3.12 and 3.13 and runs on Léo's Python 3.14.8.
- Packages (`requirements.txt`, checked by `run.py` with `importlib.metadata`): **mido** >= 1.3 (MIDI files), **numpy** >= 1.26 (sound synthesis, picture work), **pillow** >= 10 (PNG), **scipy** >= 1.10 (WAV files, resampling). All have permissive licenses. When one is missing, `run.py` shows the list, the pip command, a virtual environment recipe and the pacman package names (message box and stderr). Arch Linux refuses a plain `pip install`: `python -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt`, then `.venv/bin/python run.py`. On 2026-11-03 Léo's `.venv` had only mido, pip and packaging; he was told to install the file.
- License: the repo has none. Léo was asked which one to use because the answer decides about ndspy and unicorn. **OPEN.**
- Tests are stdlib `unittest`, run from `tools/toolkit`: `python -m tests` (`-v` lists them; `python -m unittest tests.test_speech` runs one file). `TOMODACHI_ROM=/path/game.nds` adds the tests on the real ROM (3D models, voice engine, fonts, the patcher) and, when a window can open, the whole application driven like a person (`tests/test_ui.py`; `tests/ui_stubs.py` stands in for the file dialogs, message boxes, colour chooser and the sound player). Without a display use `xvfb-run -a python -m tests`. Result on 2026-11-03 with the FR 3.5.1 ROM: 500 tests OK with a window; without Tk the only skipped test is `test_ui`. Tests per file: audio 14, bgm 53, bmg 13, core 24, currency 10, images 13, keyboard 65, meta 6, models 81, project 16, rom 27, soundfont 29, speech 56, synth 58, texanim 34, ui 1 (one test that runs about twenty steps in a row).
- Static check: `python -m pyflakes tests tomodachi_toolkit run.py` (pyflakes is not in `requirements.txt`).
- Size on 2026-11-03: 142 `.py` files, about 21,600 lines with the tests.

### 3.2 Package layout

| Part | What it holds |
|---|---|
| `run.py` | Starts the program after checking `requirements.txt`. |
| `tomodachi_toolkit/core/` | Formats, no game knowledge: `binary` (little endian readers, CRC16), `compression` (`lz10` read, `lz10c` write with displacement >= 2, `blz` for the ARM9 and overlays), `rom` (`Rom`: FAT, files, ARM9, overlays, `append`, `put_file`, `grow_file`, `save`), `narc`, `nitro` (NCGR, NCLR, NSCR), `nftr` (fonts), `bmg` (MESGbmg1, codes written as `{hex}`), `bps`, `png` (Pillow). |
| `tomodachi_toolkit/features/` | One module or folder per thing the toolkit changes, no Tk: `bmg`, `meta`, `subfiles`, `currency/`, `keyboard/`, `images/`, `models/`, `audio/`, `bgm/`, `speech/` (with `armvm/`). Each has an `apply_*` that writes into a `Rom`. |
| `tomodachi_toolkit/patcher.py` | `patch(data, cfg, log)`. |
| `tomodachi_toolkit/project.py` | The `.tomods` file: dump, load, validation (9.1). |
| `tomodachi_toolkit/ui/` | Tk: `app`, `pages`, `session`, `theme`, `widgets`, `charpalette`, `glyphs`, `modelview`, `player`, and `tabs/` (one module or folder per tab). |
| `tests/` | One `test_<part>.py` per part, `helpers.py` (builders of small synthetic files, `need_rom`), `ui_stubs.py`. |

To add a tab: write a subclass of `Tab` (`ui/tabs/base.py`) and list it in `GROUPS` in `ui/tabs/__init__.py`. The contract: `key` (name of its part in the patch config and the project; `''` for none), `title`, `heading` (its line in the ROM tab summary), `build`, `on_rom`, `on_show`, `on_hide`, `patch_config` (a dict, or None when nothing changed; may raise ValueError), `project_part`, `restore(part)` (returns notes), `summary`, `changed`.

### 3.3 The window

- Title "Tomodachi Location Toolkit", 920x720, footer "2026 by L-DEV31 - TomoDS Team". Colours: warm orange and cream (`ui/theme.py`).
- **Tabs of tabs** (`ui/pages.py`): the top notebook holds groups; a group with one tab shows it directly, a group with several shows a second row of tabs. Groups: ROM [ROM, Meta], Location [Currency, Keyboard, Fonts], Text [BMG], Graphics [Images, Models], Sound & Speech [Audio, BGM, Voice]. A group opens on its first tab, then remembers the last tab visited. Only the ROM tab works until a ROM is open (the other tabs are disabled, and a group whose tabs are all disabled is disabled).
- `Session` (`ui/session.py`) is the open ROM, read only. Every tab keeps its own edits; the patch is built from them (`App.build_cfg`).
- Listing tabs (Images, Models, Audio, BGM, Voice) share `ListingTab.build_listing`: search bar (Ctrl+F goes to it), "Modified only", count, a list on the left and the detail on the right, and the batch buttons at the right of the bar.
- **Batch buttons** (`widgets.batch_buttons`): `Batch export`, `Batch import`, `Revert all`, always in this order and as buttons, not a menu. BMG and Keyboard put them in their own bar. Currency, Meta and ROM have none.

| Tab | Batch export | Batch import |
|---|---|---|
| BMG | every message file, named as the game names it (the replacement where there is one) | files named like a game file (any case) replace it |
| Keyboard | `QWERTY.txt`, `Japanese.txt`, `Accents.txt`, `Symbols.txt`, `Emojis.txt` (layouts) and `Order.txt` (order of the tabs) | the files a folder has; an unreadable file is skipped and listed |
| Images | the listed images as PNG | PNG named like the export; one that looks like the ROM's picture is no change |
| Models | the listed models as OBJ, MTL and PNG, in folders of the ROM (`Mdl`, `Job`...) | OBJ files and the PNG beside them; what looks like the ROM's is no change |
| Audio | the listed sounds as `wave_012.wav` | WAV named like the export; a sound equal to the current one is skipped |
| BGM | the listed sequences as `.mid` and `.sseq`, a folder per bank; the instruments sit in the folder of the bank (`.sf2` for the `.mid` files, `.sbnk` for the `.sseq` files) and the waves (`.swar`) once at the top | `.sseq` and `.mid` named like the export (also in folders inside); music equal to the current is skipped |
| Voice | a folder per bank with `NNNN title.txt` per line, and a folder `Voice presets` with `Name.txt` per preset | the same files (3.13.1) |

- File dialogs and message boxes are always called through their module (`filedialog.asksaveasfilename(...)`, `messagebox.showerror(...)`) so that `tests/ui_stubs.py` can replace them.

### 3.4 ROM tab, patching, BPS and projects

- **ROM**: Open ROM (refuses a file that is not Tomodachi Collection), banner preview, name, folder, size, a "WILL BE APPLIED" summary (one line per tab that has a heading), **Patch ROM**, **Export BPS patch (for Flips)**, **Save project (.tomods)** and **Open project (.tomods)**. Apply BPS was removed at Léo's request: Flips applies patches.
- `patch(data, cfg, log)` applies, in this order: currency, keyboard, meta, bmg, images, models, audio, bgm, speech (the presets into the ARM9 copy, the lines into the message files), then `rom.set_arm9` and `rom.save()`. `cfg` keys and shapes: `currency` `{'rate', 'code', 'sym', 'whole'}`; `keyboard` `{'order': [...], 'layouts': {keyboard: {layer: characters}}}` (either may be left out; an older config is the order alone); `meta` `{'titles': {lang: text}, 'icon': (tiles, palette), 'internal': str}` (changed fields only); `bmg` `{inner file name: bytes}`; `images` and `models` `{path of a NARC: {sub file index: bytes}}`; `audio` `{wave index: {'rate', 'pcm'}}`; `bgm` `{sequence number: {'file', 'bank', 'volume'}}`; `speech` `{'presets': {name: script}, 'lines': {path: {index: [old, new]}}}`.
- `Rom.save()` writes the used size at header `0x80`, raises the capacity byte at `0x14` when the image grew and recomputes the header CRC16 at `0x15E`.
- The currency step refuses a ROM whose cave is already filled ("already patched or unsupported ROM"). Patch an untouched ROM, never a patched one.
- **BPS** (`core/bps.py`): Export builds the same patch as Patch ROM on the opened ROM, writes a BPS file (Flips format, spec by byuu) and applies it again in memory to check it. The encoder is simple (equal runs as SourceRead, the rest as TargetRead, no SourceCopy or TargetCopy), so a patch with moved data is large: a full patch (BMGs, currency, keyboard, meta) on the 3.5.1 ROM was about 2.2 MB. Verified with the real Flips 198 CLI on Léo's machine: it applies the patch and the output is byte identical to the toolkit's. No ROM is distributed; anyone applies the patch to their own copy. The exported patch carries no metadata (9.1).

### 3.5 Currency tab

- Rates come live from `https://open.er-api.com/v6/latest/JPY` (needs the network; without it the tab says "Rate API unavailable"). The list holds the currencies of the rates that have an entry in `SYMBOL` (`features/currency/data.py`). The info line says `1 CODE = x JPY`. **Reset currency** goes back to yen with its symbol. Default is JPY.
- **Prices are converted**, not only displayed: `T1` (255 rows, price = low 24 bits of word0) and `T2` (300 rows, price = low 23 bits, bit 23 kept) are rewritten with `convert(price, scale) = max(1, floor(price * scale + 0.5))`; a result above the field is capped and logged. Scale is the rate in whole units, or rate x 100 in cents mode.
- **Island income** (ov82, call at `0x2149844` to `0x2149E1C`) goes through a wrapper in the ARM9 cave: `push {r3, lr}`, `bl orig`, `pop {r3, lr}`, `b thunk`, `bx lr`. It is always installed, also for JPY (scale 1).
- **Cents mode**: money is displayed with cents through `CENTS`, a 248 byte ARM thunk (fixed point 2^-23, magic divide by 100) hooked on the money display call sites `SITES` (ARM9 and overlays 68, 72, 75, 83, 84, 85, 100). Lists show whole units, rounded, minimum 1 (the plain thunk). Cents are possible when the code is not in `WHOLE` and `rate * 100 * T2_MAX <= 0x7FFFFF` (`T2_MAX` = 990,000 yen is used as the dearest T2 price), so about rate <= 0.0847. Otherwise whole units are forced and the checkbox "Round prices to whole units" is disabled. No whole-unit fallback exists beyond that: KRW, IDR, VND and similar are whole units.
- The info line adds "prices above N JPY are capped" when `T2_MAX * scale` exceeds the 23 bit field.
- **Symbol rules** (audited 2026-11): the symbol is a single character that **all three fonts** draw (`FontLD08x`, `FontLD10x`, `FontLD12x` in `/Cmn/Font/`), because its glyph is copied over the glyph of the fullwidth yen `U+FFE5` in each of them. The fonts have the dollar, the fullwidth pound `U+FFE1` and the fullwidth yen `U+FFE5` but no euro, won, rupee, ruble... sign. `SYMBOL[code]` therefore gives: `$` for the dollar family, `U+FFE1` for GBP and the pound family (EGP, FKP, GIP, SHP, GGP, IMP, JEP, LBP, SYP, SSP, SDG), `U+FFE5` for JPY, CNY and CNH, `E` for EUR, and the letter that stands for the money for the rest (KRW `W`, INR `R`, RUB and PHP `P`...). **No fallback and no hint**: a character the fonts lack stops the patch before anything changes (`draw_symbol` raises "The fonts of the game cannot draw ..."). `tests/test_currency.py` and `tests/test_rom.py` check every money of the table against the fonts of a ROM.
- The symbol is chosen in a palette (`ui/charpalette.py`, the same widget as the Keyboard tab) that lists exactly the characters all three fonts draw (`Session.symbols()`), with the preview drawn as the game draws it, `Default symbol` and search by character, code or name.
- Where the symbol lands: the `FFE5` glyph of the three fonts; the literal `円` (bytes `86 51`) at `YEN_TEXT` (`0x2114FD0`), rewritten to `FFE5` (bytes `E5 FF`) so the sell price shows the glyph; and the baked 7x7 yen pictures of 16 `/Scn` files (`GLYPHS`, redrawn with the 7x7 glyph of the small font; skipped for the yen itself).
- Patch internals (verified in the earlier sessions): ARM9 is stored uncompressed (`compressed_static_end = 0`); the overlay table and overlays that overlap are moved to the ROM tail (`Rom.set_arm9`); new files are LZ10 (`lz10c`, displacement >= 2). Thunks live in the zero-filled ARM9 `CAVE` (`0x20ECD18`). Thunk = fixed point multiply (`umull`) then tail jump to the formatter. The game draws an amount through two number formatters: `FMT` (`0x20364E0`, hooked with the cents thunk) and `PLAIN` (`0x20363A8`, hooked with the plain thunk: whole units, rounded, minimum 1). **All overlays load at `0x21495E0`** (shared region, one at a time): use that base when disassembling an overlay. A patched overlay gets its "compressed" flag cleared in the overlay table (`ent + 28`).
- Verification and open points are in section 12. Nothing has run in the game yet.

### 3.6 Keyboard tab

- The five on-screen keyboards (Japanese, QWERTY, Accents, Symbols, Emojis) can be **reordered** with arrows (the first becomes the opening tab; icons are the game's own sprites) and their **keys** can be changed in a settings window per keyboard (`ui/tabs/keyboard/editor.py`): the keyboard is drawn on a canvas with each key at its place on the touch screen, a character palette (`charpalette`, characters the game's fonts draw) puts a character on the selected key, with undo (`features/keyboard/edit.py`, `LayoutEditor`), ready made layouts for the Latin alphabet (`presets.py`: QWERTY of the game, AZERTY, QWERTZ, Dvorak, Colemak, alphabetical; the Caps and Shift layers follow from the lowercase layer), and a layout as a **text file** (`textfile.py`): header `Tomodachi Collection keyboard: NAME`, a `[Label]` section per layer, one line per row of keys, one word per key (the character, or `U+XXXX`; `U+0020` is a key that types nothing; `#` and `[` at the start of a line are written as `U+`).
- Where the keys are (FR build 3.5.1, `layout.py` `SPECS`): the game keeps one table of characters per layer in the ARM9 (UTF-16, one entry per key after a byte order mark). A key is drawn with the character of the table and types it, so changing a table changes both. The rectangles of the keys are separate data and are **not** changed (the pictures of the keyboards are made for them): keys swap characters, the keyboards keep their shape.

| Keyboard | Descriptor | Typing keys (keys per row) | Layers (table address) |
|---|---|---|---|
| QWERTY | `0x021129DC` | 45 (12, 10, 9, 10, 4) | Lowercase `0x02111E5C`, Caps `0x02111E00`, Shift `0x02111EB8` |
| Japanese | `0x021129EC` | 51 (11, 10, 10, 10, 10) | Hiragana `0x02111F84`, Katakana `0x02111FEC` |
| Accents | `0x021129FC` | 52 (11, 11, 11, 11, 8) | Accents `0x02111F14` |
| Symbols | `0x02112A0C` | 51 (10, 11, 11, 11, 8) | Symbols `0x021120C4` |
| Emojis | `0x02112A1C` | 55 (11, 11, 11, 11, 11) | Emojis `0x02112054` |

- A ROM that does not keep the tables there makes `Session.keyboards()` return None; the tab then only reorders (`LayoutError` says why).
- **Order internals** (verified in the earlier session, confirmed working by Léo): tab slot array at ARM9 `KB_MAP = 0x20B7AD4` (5 words, `[0,1,2,3,4]` originally). The kind map is built by `str` instructions at `KB_STORES = (0x2081BF4, 0x2081BF8, 0x2081BFC)`; the patch replaces them with NOPs (`0xE1A00000`). Opening tab: `KB_START = 0x2081AA4`, `mov r0,#1` becomes `mov r0,#KB_KIND[first]` (`0xE3A00000 | kind`). `KB_KIND = {Japanese:1, QWERTY:0, Accents:2, Symbols:3, Emojis:4}`, `KB_ICON = {Japanese:5, QWERTY:0, Accents:6, Symbols:7, Emojis:8}` (icon blocks swapped in `/Cmn/Kbd/SoftKeyboard_LZ.bin`, NARC sub 2, 128 byte blocks). Default-kind callers pass kind 0 (`0x2082E54(kbd, 0, 0)`), so remapping the kind table is enough. The first attempt (swapping the A array) left the default on Japanese.
- Key layout editing is verified offline (tests, tables read back from a patched ROM) and **not played**.

### 3.7 Meta tab

- Language list `LANGS = ['Japanese','English','French','German','Italian','Spanish']`, a title box, **Apply to all languages** (copies the title to every language), Change icon / Reset icon, and the internal name (12 ASCII characters max).
- Icon import: Tk `PhotoImage` reads PNG or GIF (no JPG); an image larger than 32 px is subsampled by `ceil(max/32)` first (speed); `fit32` fits it into 32x32 by nearest neighbour, centred with transparent padding; `quantize` keeps the 15 most common colours (5 bits per channel, BGR555) plus index 0 as transparent (alpha < 128 is transparent) and returns 512 bytes of 4bpp tiles (8x8 tiles, 4x4 grid) and a 16 entry palette.
- Banner (verified in code): offset is the `u32` at header `0x68`; icon tiles at banner `+0x20` (512 bytes), palette at `+0x220` (16 BGR555 entries); titles at `+0x240 + 0x100 * language`, UTF-16LE, 0x100 bytes max each; banner CRC16s at `+2` over `0x20..0x840`, `+4` over `..0x940` (version >= 2) and `+6` over `..0xA40` (version >= 3), recomputed in `apply_meta`. The internal name is the 12 bytes at offset 0. The header CRC16 at `0x15E` is recomputed by `Rom.save()`.

### 3.8 BMG tab

- Lists the 24 message files of the game by their inner name (`/Msg/TmdXxxMsgJP_LZ.bin`) in a scrolling panel (no search bar), with the state of the ROM copy ("ROM copy: ok" or the first problem). Per file: Replace (opens a `.bmg`, refuses an invalid one with the reason) and Cancel; Batch export, Batch import and Revert all (3.3). The summary says "N replaced".
- The patch step (`apply_bmg`, `bmg_put`) follows the injection rules of 8.3. Validation is `core/bmg.bmg_problems` (the checks of section 5).

### 3.9 Images tab

- Lists the editable pictures of `/Cmn/Kbd/`, `/Cmn/Nin/`, `/Job/`, `/News/`, `/Pht/` and `/Scn/` (`IMG_DIRS`), as tile sheets or, with a screen (NSCR), as the screen. A **palette** panel shows the palette of the picture as rows of 16 colours; a click picks a colour, a double click opens the colour chooser and the change is written into the NCLR file of the archive (`nclr_set`, the console keeps 5 bits per channel). Palette edits are part of the same `images` patch part (an `RLCN` file).
- PNG export and import; pixels that are not in the palette are snapped to the closest colour with a warning ("N pixel(s) were not in the palette ..."). Formats and rules: section 9.

### 3.10 Models tab

- Lists the BMD0 models of the folders `/Mdl`, `/Job`, `/News`, `/Scn/Affn` and `/Scn/Mrg` (`MODEL_FOLDERS`; `/Mdl` alone holds 1278 in the 3.5.1 ROM). Each can be viewed (a software render, pure Python, orbit camera: drag turns, wheel zooms, right drag moves, double click resets; `ui/modelview.py`, `features/models/render.py`), animated, exported and imported.
- **Animations** play together by name (`actions.py`): joint animations (BCA0, `anim.py`), texture matrices (BTA0), material pictures (BTP0) and node visibility (BVA0) (`texanim.py`), the ones of the model's own archive plus the shared Mii skeleton animations (read once per ROM, found by number of nodes).
- **Textures** go through PNG (decode and encode of every NDS texture format, same size, `textures.py`). **Shapes** go through OBJ, MTL and PNG for Blender (3.11). Replaced models change size: `apply_subfiles` rebuilds the NARC at the new size and keeps its compression (LZ10 stays LZ10).

### 3.11 Audio tab

- Lists the 592 waves of the sound archive with the banks that use them (no bank gets special treatment). Play (system player), export and import as WAV (16 bit mono; `scipy` reads any PCM or float WAV, mixes channels and resamples). A replacement is IMA ADPCM encoded keeping the wave's encoding and loop flag. The sound archive may now **grow**: `Rom.grow_file` moves the files that follow it to the end of the image (the log says "Sound archive: N bytes bigger"), so the cartridge no longer needs the old "patch in place only" rule. A wave that fits the old room is zero padded to the old size, so offsets do not move and the BPS patch stays small.

### 3.12 BGM tab

- Lists the sequences (SEQ) of the sound archive with duration, number of tracks and size; the detail has the bank ("Instruments (bank)") and the volume (0 to 127) of the sequence, both editable. **Play** uses a small software synthesizer (`features/bgm/synth.py`, numpy): the notes of the sequence (`timeline.py`) are played with the instruments of its bank (SBNK) and the waves of the wave archive (SWAR) the way the console does it (each note is a wave played faster or slower, under the engine envelope worked out 192 times a second), mixed to 16 bit mono. It is for listening: no stereo, no vibrato, no portamento, and volume and pitch bend count at the start of a note.
- **Export** (one sequence): the type chosen in the save dialog says the format, `.mid` or `.sseq`; the instruments come out beside it with the same name: a **SoundFont** (`soundfont.py`: every instrument of the bank becomes the preset with its program number, every key part a zone, engine envelopes converted; bank 128 holds the same presets for drums) for a MIDI file, the **bank** (`.sbnk`) and the **waves** (`.swar`) for an SSEQ file.
- **Import** a `.mid` or `.sseq` per sequence; the bank and the volume of a sequence can be changed too. A project keeps `{'file', 'bank', 'volume'}` per sequence number. Replaced sequences may be bigger (`apply_bgm` rebuilds the SDAT).
- Facts: SSEQ times count in ticks, 48 per quarter note; a sequence is a header and a stream of commands that every track reads at its own pace (notes, rests, volume, tempo, jumps, calls, loops, variables, conditions). In the MIDI file track n is channel n + 1, tempo and loop sit on a first track; supported: notes, program changes (bank select above 127), pitch bend with its range (RPN 0), tempo, controllers 7 volume, 10 pan, 11 expression, 1 modulation depth, 76 speed, 78 delay, 5 portamento time, 65 portamento on, 84 portamento key, 73 attack, 75 decay, 102 sustain, 72 release, 103 priority, 104 modulation type, 105 range, 106 master volume; loops as markers `loopStart` and `loopEnd` (or controller 111 for the start); game variables as text events like `var0 = 100`. `convert.fingerprint` compares what two timelines play, so a round trip can be checked.
- SEQ INFO record in the SDAT: file id in the low 24 bits of the first word, bank `u16` at `+4`, volume `u8` at `+6`.
- Not played in the game: a replaced sequence, a changed bank.

### 3.13 Voice tab (the Miis' speech)

Details of the engine are in 10.2. The tab (`ui/tabs/voice/`, `features/speech/`):
- **Left**: the speech lines grouped by bank (11 banks, 4388 lines in the 3.5.1 ROM: Miitouch, MiniContents, News, Select, Song, TalkCool, TalkDry, Talk, TalkNagomi, TalkNori, Trouble), searchable. A line is a message of the files `/Msg/Tmd{Talk*,Select,Trouble,Miitouch,MiniContents,News,Song}MsgJP_LZ.bin` that the engine can read (katakana, marks, commands and game codes only; in the Song files only the melodies count: lines made of game codes for the syllables with commands or long marks). The game keeps each line twice, the text the player sees and, right after it, the katakana text the engine reads; the twin is matched by message number (seen text ends in 0, spoken in 1) or by the header of the speech bubble, and gives the line its name in the list.
- **Right, top: Listen** (a test, nothing is written to the ROM): voice list, `Voice settings`, **Play** (the line as it is now; typed text on the Text page is applied first), **Original** (the line as in the ROM), Stop, Save WAV.
- **Right, below**: pages **Sounds** (the sounds of the line as blocks and a palette of sounds and marks to click), **Rhythm** (a graph of pitch, length or volume per sound, Flatten, +/- for all sounds, the mood of the line, Add effect), **Text** (the line as plain text, 3.13.1) and **Voices** (the presets of the engine: voices, moods, commands as sliders, `Add a setting`, Reset, Reset all, and a raw `Script` box). A dot marks what was changed.
- Pitch, length and volume are not stored per sound: the game moves them with the relative commands `<\RPit=n>`, `<\RSpd=n>`, `<\RVol=n>`, which add up from where they stand to the end of the line. `LineModel` reads the running total in front of each sound and writes the commands again when a sound gets another value, without moving the sounds after it. Units: `RPit` 59 per semitone (range +-12), `RSpd` 1 per point (-50 to 150, step 10), `RVol` 10 per dB (-30 to 10). Absolute `Pit`, `Spd`, `Vol` stop the compensation. A line nobody touched is written back byte for byte.
- `LIMIT = 255` 16 bit characters (game codes count for their size): it is the length of the longest speech message in the game's own data, not a limit proven in the engine.
- Every change to a line is one step of undo (`Undo`); `Revert` puts the line back to its ROM text and `Revert all` does it for every line and preset.

#### 3.13.1 Text page and files (raw data)

- The Text page is a plain `tk.Text` with the line as the game holds it: katakana, marks, `<\Name=value>` commands, `{hex}` game codes (a real brace is written twice). **Nothing is converted.** `Apply` (or Ctrl+Enter) makes the typed text the text of the line; a counter shows `n / 255 characters` and "Press Apply to use this text"; a text the game cannot hold (a bad game code or brace, too long) is refused with the reason in red and the line stays as it was. `Insert` offers `Game code` (the codes found in the lines with the number of lines that use them; `08011f..` is the name of the Mii, `080101..` a syllable of a song) and `Mood or command`. `Export line` / `Import line` write and read one UTF-8 `.txt` file (name `NNNN title.txt`).
- `kana.py` (katakana with romaji, marks) only feeds the buttons of the palette; it is never used to convert what a person writes.
- Files (`features/speech/files.py`): exports are UTF-8, byte for byte the text of the line (changes included); import identifies a line by the **number at the start of the file name**, ignores the rest of the name, reports a second file for the same number, validates with `problem()` and skips what equals the current text. Presets: `Voice presets/Name.txt` (name without the `<\`), validated by `script_check` and by a check that the script is only items like `#B4800`, one per line. Wrong files are left out and told ("N line(s) and M voice preset(s) changed", plus up to 12 skipped).
- The only touch on reading: editors add a final line break and CRLF, so CRLF becomes LF and one final line break is dropped unless the line itself ends with one. Everything else is read as it is. Checked on the ROM: all 4388 lines and every preset go to files and come back with 0 changes.

## 4. Money research (the open problem)

Goal Léo set: make the currency conversion **real** (convert stored prices and money), not display-only. It is implemented for T1, T2 and the island income (3.5); the rest is below. Nothing has been played yet.

### 4.1 Wallet
- The wallet is a `u32` at money struct `+0x50`. Runtime address **0x2329CE4**, struct base 0x2329C94.
- Reached through a global holder pointer in ARM9 at **0x2122FF4** (`ldr r0, [pc,#...]` then `[r0, #0x50]`).
- All writes go through `SetMoney` at **0x202D1EC** (clamps the value; the cap is 9999999, read from the ROM).
- Wallet value after the intro on a fresh save: **6800** (read from RAM).

### 4.2 Wallet write paths found
- **Shop screen (ov83)**: copies the wallet into a working field at `[r4 + 0x19000 + 0x4A4]` (store at 0x21496BC). Buy: subtract a price (0x214A6E4). Add: add an amount (0x214A7F8). Clamp to 0. Write back with `SetMoney` at 0x214B610 (reads `[r0+0x4A4]`).
- **Mii gift (ov75)**: copies the wallet into `[r4 + 0x30000 + 0x9B4]` (0x2149DBC). `SetMoney` at 0x214B8D0 reads the same field.
- **Income (ov82)**: `r0 = 0x2149E1C(r6)` (amount), then `wallet = holder+0x50 + amount`, `SetMoney` at 0x2149858.
- A direct-`BL` scan found only these three `SetMoney` callers (ov75, ov82, ov83). An earlier session mentioned 8 sites; that figure is not confirmed. Indirect calls were not scanned.
- Possible extra write: ov6 stores `[sl + 0x5000 + 0x9B4]` (0x2149C0C). Not traced. **UNVERIFIED**.

### 4.3 Price helper
- `0x20AA88C`: a dispatcher that calls a method of an object through its vtable. Mode word at `[r0 + 0xA000 + 0xFA4]` (0 -> vtable slot +8, 1 -> slot +0xC). Arguments from `[+0xFAC]` and `[+0xFB0]`. Used for the amount in ov83. **The target object is not traced.** Likely where prices are computed from tables, but UNVERIFIED.

### 4.4 Price tables
- **T1** at ARM9 **0x20F5AD8**: 255 rows, stride 20 bytes, price = `word0 & 0xFFFFFF`.
- **T2** at ARM9 **0x20F3BBC**: 300 rows, stride 20 bytes, price = `word0 & 0x7FFFFF`, bit 23 is a flag. Category not confirmed.
- Not yet checked whether the helper reads T1/T2.

### 4.5 Not money
- ov96 `0x214A43C`: a 12-bit field x 60 added to 64-bit counters (`+0x95C/+0x960` and `+0x4A0/+0x4A4`). Time, not money.

### 4.6 Tutorial payouts (the start money): NOT FOUND
- The 6800 is not a boot value. Léo explained: money is given during the tutorial as you go through it.
- Searched and not found: a `u32` 6800 literal in ARM9 and overlays, a 6800 literal in NitroFS data (decompressed, 0 hits), an `mov #0x1a00 / add #0x90` pair, an init store of 6800.
- ov109 `0x214AEAC`: a store of r2 (0) into `[r1+0x50]`. It zeroes, it is not the wallet.
- Probable path: the intro script or an event calls the ov83 add path (helper 0x20AA88C with a positive value) or the ov82 income path. **OPEN.**

### 4.7 Other money not converted
- Numbers written inside BMG texts ("2100 yens", the `[1401:..] yen(s)` tag).
- Job wages, costume/interior/goods shops (if they do not read T1/T2), sell price (`YEN_TEXT` only changes the sign).
- Untested in melonDS: costume/interior/goods shops, Mii gift, sell price. Tested before the real conversion: island wallet, food shop list/catalog/purchase.

## 5. BMG knowledge

Full notes are in `BMGs/BMG.md` (committed). Summary:

- Container `MESGbmg1`: header 0x20 bytes. `u32` file size at 0x08, `u32` section count at 0x0C, encoding byte at 0x10 (`2` = UTF-16 in all files).
- Sections chain from 0x20 to EOF: 4-byte tag, `u32` size (includes its 8-byte header). Required: `INF1`, `DAT1`, `MID1`. MID1 count = INF1 count.
- `INF1`: `u16` count at +8, `u16` entry size at +0xA (12). Entry = `u32` offset into DAT1 data (message at `DAT1 + 8 + offset`).
- `DAT1`: UTF-16LE strings ending with `0x0000`.
- **Alignment rule**: every section start and size must be a multiple of 4. A `DAT1` size not multiple of 4 misaligns `MID1` -> ARM9 data abort (melonDS, DS). This crashed the game.
- Tag (UTF-16 file): `1A 00` | size (1, total length incl. escape, 8 in these files) | group (1 byte) | type (2 bytes LE) | args. The encoder is in `build-bmg.js` (`encodeToken`). `core/bmg.py` reads a text code by code (a code may hold zero words) and writes codes as `{hex}`, the bytes after the word `0x001A`; `BmgFile` gives a file back byte for byte when nobody changed it.
- Fixes: `651980a` (bmge: DAT1 padding, regex `]`, tag size byte = args+3 -> total length) in the L-Dev31.github.io repo, file `projects/demos/bmge/js/build-bmg.js`; `4426fa0` (+2 zero bytes on `etc`, `item`, `room`) in the translation repo.
- Status of the 7 files in `BMGs/test/` (2026-10-25): alignment and structure OK (all checks pass).
- Oddities from original data, not regressions: `tmd_etc` has 20 duplicated INF1 offsets and 21 overlaps (empty messages pointing at offset 0); `tmd_contents` 1 overlap. Same in the first committed version.
- `tmd_etc`: tag group `FF`, type `000A` existed in the first committed version and is gone now. **Check if intended.**
- Longest message per file is unchanged vs the first version except small differences in `costume`, `etc`, `explain`, `item`, `room` from translation edits.
- Not checked: the `BMGs/done/` and `BMGs/todo/` folders.
- A beta tester crashed. First guess was an old copy of `etc`, `item` or `room`. **Superseded by section 8**: the BMGs inside the tester's ROM are truncated.

Validator: `core/bmg.bmg_problems` (and `tools/bmgrom.py check`) test magic, file size, chain, alignment, INF1 offsets inside DAT1, terminators, tag size, MID1 count.

## 6. Open items and next steps (in priority order)

1. **Final test round** (Léo will say when): `python -m tests` with the ROM, with and without a window, then a GUI pass of every tab, then in the game (Léo clicks): replaced images and palettes, sounds, music, models, key layouts, edited speech lines and presets, a currency patch.
2. **Crash**: see section 8. Confirm with the tester using a ROM built by `tools/bmgrom.py` or the toolkit BMG tab, after `bmgrom.py check` says all 7 are OK.
3. **License** of the repo (asked, no answer): decides about ndspy (ROM, NARC, SDAT, BMG, LZ) and unicorn (replace `features/speech/armvm`).
4. **Play-test the real conversion in melonDS** (Léo does the clicks). Order: the start wallet (tutorial), one shop price in cents and in whole units, the island income after a day, a KRW patch (whole units, capped T2 item), a keyboard reorder and a layout, a custom icon, a title change.
5. **Real conversion status**: T1, T2 and the ov82 income are converted. Open: the tutorial payouts (4.6), the helper `0x20AA88C` target object, other readers of T1/T2 that might use the price as a yen constant. Decide after the play-test whether the remaining yen paths must be converted.
6. **BMG texts with yen** (4 messages, see 12) keep "yen" and yen figures. They need a decision: rewrite them, or accept.
7. Check `BMGs/done/` and `BMGs/todo/` with the checker; review the `FF:000A` tag removed from `tmd_etc`.
8. Money not converted: job wages, costume/interior/goods shops if they do not read T1/T2, sell price (4.7).
9. **Speech**: check in the game that an edited preset and an edited line change what the Miis say; trace how the game picks a voice, an emotion and tags from a Mii's `voice` setting (10.2); run `speech_check` on the JP original; the effect of the letters Z, E, D, C, k.
10. **Music**: check in the game a replaced sequence (own `.mid`, own `.sseq`), a changed bank and volume. Possible nicety: pack a mini `.sdat` for SSEQ exports; preview a sequence with replaced Audio-tab sounds.
11. Images stored outside `/Cmn /Job /News /Pht /Scn` (Mdl, Msg) are not listed; NCER/NANR sprites are shown only as tile sheets. 4x4 compressed texture import and models with raw palette sub files are untested.
12. Identify which tool truncates the NARC of the BMGs (NSMBe, Tinke or the build step used for 3.5.1), and make BMGE alone enough (a NARC + LZ10 export following 8.3) or keep the toolkit as the injector.

## 7. Known pitfalls from this work

- Local variable shadowing: a `code` variable once shadowed the thunk bytes and broke the symbol silently. Use distinct names.
- Edit scripts that write literal `▼` vs `▼` mismatched; always assert before writing.
- Heredoc quoting breaks with long Python in bash; write scripts to files.
- Tk `PhotoImage.subsample` only takes integer factors; use a nearest-neighbour fit for other sizes.
- `Entry` validation: a `validatecommand` with `%P` rejects keystrokes that make the value invalid, so a paste of several characters is also rejected.
- Banner title trace bug: insert titles before the internal name, or the trace overwrites them.
- A `( ... ) &` inside a harness shell call makes it report "completed" at once; use a log file and a loop that waits for its last line.
- f-strings with a backslash inside the expression break on Python < 3.12; compute the piece outside.
- Python 3.14 / Arch: `pip install` outside a virtual environment is refused (3.1).
- The git rename of `tools/prices` required moving files individually (the directory was locked).
- Shipping files: extract a tarball into `tools/toolkit`, check `sha256sum -c` of the manifest, check that no host file is missing from the manifest (excluding `.venv`), compare a combined hash of all `.py` files on both sides, then delete the manifest and the tarball. The tarball has no deletion handling: a removed module has to be deleted by hand.

---

## 8. Beta tester crash investigation (2026-10-25), verified

Context: the beta tester still crashed with build 3.5.1 although the BMG files in the repo pass every check of `BMGs/BMG.md`. He sent two melonDS savestates (`.ml1`, magic `MELN`, version 13). Findings below were measured on the savestates, on the 3.5.1 ROM and on the original Japanese ROM. Test folder on Léo's machine: `~/Documents/Tomodachi Collection FR/ROM` (JP ROM, build 3.5.1, `-fixed` ROM).

### 8.1 Root cause: the BMGs inside the ROM are truncated
- In the ROM each message file is a NARC compressed with LZ10: `/Msg/TmdXxxMsgJP_LZ.bin` (24 files, 7 are ours). The NARC holds one file, named by its BTNF table (`tmd_common_msg_JP.bmg`). The game opens it **by that name**.
- In the 3.5.1 ROM, 6 of our 7 BMGs are cut. The NARC table (BTAF) and the BMG header say the full size, but the NARC header size and the LZ stream are the old Japanese sizes (+16). Example `contents`: header 23296, real 13616, so DAT1 is cut and MID1 is missing. `etc` is the only intact one (it was moved to the ROM tail at `0x112DA28`; the others stayed in their old slots).

| BMG | real size in 3.5.1 | header size | JP ROM size |
|---|---|---|---|
| common | 2832 | 2896 | 2816 |
| contents | 13616 | 23296 | 13600 |
| costume | 23772 | 33208 | 20992 |
| etc | 37368 | 37368 | 21952 |
| explain | 47634 | 47698 | 46400 |
| item | 18352 | 20858 | 14336 |
| room | 3408 | 4006 | 3392 |

- The 3.5.1 ROM also has old copies of `item`, `room` (header 20858, 4006) and `explain` (47698), all with a DAT1 size that is not a multiple of 4. They predate `4426fa0`.
- The JP ROM passes the same check (header size = real size for all 7), so the checker has no false positives.
- Which tool truncated the files is **not proven**. The tester reports the same result with NSMBe and with Tinke, and the damage is not in the BMG files (BMGE output is valid). Always run the check on any ROM before sending it.

### 8.2 What the savestates show (how to read a melonDS state)
- Layout: header `MELN`, then sections with 16 byte headers (4 char tag, u32 length, 8 zero bytes). `NDSG` starts at `0x10`; main RAM (4 MB, ARM9 address `0x02000000`) starts at file offset `0x24`. Find the CPU with the last `ARM9` + length `0xBC` section before `CP15`; the data is 47 words: word 0 and 1 header, R0..R15 = words 2..17, CPSR = word 18. Banked registers follow (FIQ 8 words, then SVC, ABT, IRQ, UND as SP, LR, SPSR).
- Both states are already crashed: CPSR mode `0x17` (abort), PC `0xFFFF0108` (BIOS handler), LR `0x202E1EC`. The faulting instruction is `ldrh r2, [r2]` at `0x202E1E4` in the message lookup function (it multiplies the id by 12, the INF1 entry size).
- r2 was loaded from `[r0 + 0x14]` of the BMG object: the pointer to MID1. It is NULL because MID1 is not in the (truncated) file.
- BMG objects live in an array of 0x18 byte entries (stride) near `0x2310874`: `[data, data, INF1, DAT1, ?, MID1]`. In the crashed state `item` and `explain` had MID1 = 0, `etc` and `common` had it filled. A healthy object has a non zero word 5.
- Old checks like "alignment crashed the game" were real for the unpadded files, but they are not what crashed 3.5.1.

### 8.3 Injection pitfalls found while fixing it (each one makes the game abort at boot)
1. The NARC **must keep its BTNF filename table** (copy the one from the original NARC). A NARC without names is not found by the loader (`narc_replace` keeps the names block).
2. LZ10 **must not use displacement 1** (runs of one byte). The game decompresses with a 16 bit write callback. `lz10c` in `core/compression.py` uses displacement >= 2.
3. Header size, BTAF end, GMIF size and the LZ size field must all describe the real, full BMG.
- Evidence: a ROM injected with the first version of the injector (no names, displacement 1) aborted at boot even with a single BMG (`common`). After fixing both, all 7 BMGs injected boots in melonDS and no abort is reached. Which of the two fixes was the decisive one was not isolated (both were changed at once).

### 8.4 Tools
- `tools/bmgrom.py` (stdlib only): `python bmgrom.py check ROM.nds [BMGs/test]` prints, for each of the 7 BMGs, the problems found in the ROM copy (and in the folder files), exit code 1 when something is wrong. `python bmgrom.py inject ROM.nds BMGs/test OUT.nds` rebuilds the 7 NARCs (names kept, LZ10 displacement >= 2), writes them at the ROM tail, updates the FAT, the used size at `0x80` and the header CRC at `0x15E`, then runs `check`. Verified: all 7 inner files equal the repo files and every other file of the ROM is byte identical.
- The toolkit BMG tab does the same through `apply_bmg` (3.8); `tests/test_bmg.py` checks the structure rules and `tests/test_rom.py` replaces a message file in the real ROM and reads it back.
- The toolkit always applies its currency step when patching (JPY default). Patching a ROM twice is refused ("already patched"), so keep an unpatched ROM as the input.

### 8.5 How to test a ROM without a GUI (what was done on 2026-10-25)
- `melonDS` and `desmume` are installed on Léo's Arch machine. The termigent shell needs `DISPLAY=:0` and `XAUTHORITY=/tmp/xauth_*` (find the file in `/tmp`).
- Start `melonDS ROM.nds`, wait about 40 seconds, send `shift+F1` to the window (savestate slot 1 is written next to the ROM as `NAME.ml1`), kill with `pkill -9 -x melonDS` (never `pkill -f melonDS`, it kills the shell itself; always kill the previous instance, extra windows steal the key press).
- Parse the `.ml1` as in 8.2. Healthy: CPSR mode `0x1F` (system), PC in main RAM. Crashed: mode `0x17`, PC `0xFFFF0108`.
- At 40 seconds the game only loads `msg`, `etc` and `common`. The other BMGs are loaded later, so a boot test does **not** prove `item`, `contents`, `costume`, `room` and `explain` are read correctly.
- The standing rule (section 2) forbids driving melonDS. This recipe is what was done once; ask Léo before repeating it.

### 8.6 Open items from this session
1. Play in melonDS and DeSmuME through the screens that read `item`, `contents`, `costume`, `room`, `explain` (shops, the item lists, the explanation screens) on a ROM built with `bmgrom.py inject` or the toolkit BMG tab. Passive check after each screen: take a savestate and verify that no BMG object has word 5 equal to 0.
2. Identify which tool truncates the NARC (see 6.12).
3. `BMGs/BMG.md` section "Beta testers" is superseded by 8.1: the old copies were not the whole story.

## 9. Images and projects

- Formats: NCGR RAHC tw/th int16 at +8/+10 (-1 = OBJ, use 16 per row), depth u32 at +12 (3 = 4bpp, 4 = 8bpp), size at +24, data at +32. NCLR colours BGR555 from +24, expanded with `<<3` (matches Tinke). NSCR cell = tile 10 bits, hflip 10, vflip 11, bank 12..15. A replaced NCGR keeps its length; the NARC is rebuilt in place and LZ10-compressed (`lz10c`, displacement >= 2). Code: `core/nitro.py` (`ncgr_info`, `nclr_colors`, `nclr_set`, `nscr_info`), `features/images/render.py` (`render_sheet`, `render_screen`, `encode_sheet`, `encode_screen`, `nearest`), `features/images/catalog.py` (`img_items`).
- Index 0: opaque pixels avoid index 0 on ties (`nearest`), because palettes often duplicate colour 0 (SoftKeyboard has index 8 = index 0). Import compares rendered pixels with the original, so re-importing an unchanged export is not marked modified.
- Verified on the 3.5.1 ROM: 743 images found (scan about 6 s), sheet and screen round trips render identically for the first 200 (only 3 News screens reuse tiles with different pictures and are reported as clashes), a patched image reads back correctly. The window tests run scan, select, export, replace, hover, modified filter, palette edit, export BPS and open project.
- Not played: the in-game look of a replaced image or palette; 8bpp images.

### 9.1 Projects (.tomods) and clean BPS patches
- Why: projects used to be stored in the BPS metadata field, and Flips shows that field. Léo wanted patches free of tool data and a separate file to come back to. **Export BPS patch writes a clean patch** (`bps_make(src, tgt)`, empty metadata) and the work in progress is a **`.tomods`** file: ROM tab, Save project and Open project.
- Format (`project.project_dump`, `project_load`): the 8 bytes `TOMODS1:` followed by a zlib compressed JSON with `version` (1), `currency` (code, symbol, whole; the rate is the live one at restore time), `keyboard` (order), `layouts` (changed keyboard layers), `meta` (titles, icon, internal name), `bmg` (by inner file name), `images`, `models` (`{path: {sub file index: bytes}}`), `audio` (`{wave: {rate, pcm}}`), `bgm` (`{sequence: {file, bank, volume}}`), `speech` (`{presets: {name: script}, lines: {path: {index: [old, new]}}}`; older projects hold the presets alone) and `source` (`crc32` and `name` of the ROM it was made from). Binary parts are zlib plus base64. Every part is validated on load (`speech_check`, `bgm_check`, `layouts_problem`, `bmg_problems`...).
- Restore (`App.restore_project`): Open warns when the open ROM has another CRC32. Each stored item is checked against the open ROM (image: same file, same size and same header; model: same file and sub file number, BMD0 magic; sound: the number exists; preset: the name exists; BMG: the inner name exists; a line is written only if the ROM text is still the one it was edited from). Items that do not fit are skipped and listed in one warning.
- Older BPS files with a project in their metadata still open: Open project also accepts `*.bps` (`bps_meta`; the source CRC32 comes from the BPS footer). A BPS without project data says so.

## 10. Audio, speech and 3D models

### 10.1 SDAT facts (verified on the ROM)
- `/sound_data.sdat` is a standard SDAT, 25,360,864 bytes: 135 SEQ, 52 SEQARC slots (26 archives, only SE_* sub-sequences), 141 BANK, ONE wave archive `WAVE_STATIC` (SWAR, file id 305, 592 waves, 7.4 MB, all IMA ADPCM, mostly 44100 Hz), 15 PLAYER, 119 GROUP, 3 STRM (`STRM_MINIGAME_SUCCEED`, `STRM_MINIGAME_FAILED`, `STRM_STAFF`).
- INFO records hold the file id in the low 24 bits (the high byte is a flag). SEQARC symbols are stored as pairs (name offset, sub-table offset).
- Every wave is referenced by at least one bank. SWAV header: type u8, loop u8, rate u16, time u16 (16756991 / rate), loop offset u16 (words), non-loop length u32 (words). For ADPCM the first word of the data is the predictor/index header and counts in the loop offset.
- The cartridge is 64 MiB with about 7 MB free. `sdat_rebuild` repacks the archive when something grew; `Rom.grow_file` stores it where it was and moves the files in the way to the end of the image.
- The Audio tab gives no bank any special treatment. (A "Mii voice banks" filter existed for a day and was removed at Léo's request; the Mii speech is a separate engine, 10.2. The BANK_MII_* banks, BANK_DIVITALK and BANK_SAIMIN are ordinary sound effects.)
- Proof that SWAR edits reach the game: a JP ROM with all 592 waves zeroed gives a constant DC level in melonDS (RMS about 260) instead of the title music (RMS 3300 to 5700). A recording method that works: `parec -d <default sink>.monitor` while melonDS runs; melonDS' own stream volume was 0 and had to be raised with `pactl set-sink-input-volume`.
- SBNK and SWAR facts used by the BGM synth and the SoundFont export are in the docstrings of `features/bgm/synth.py` and `soundfont.py` (envelopes in the engine's units, regions of kinds 1 wave, 2 pulse wave, 3 noise).

### 10.2 Mii speech (Voice tab)

**What it is.** The Miis do not play recorded voices. The ARM9 holds Sharp's text to speech library, signature `[SDK+SHARP:SHTTS-1_2_0]` (SHTTS 1.2.0), which turns katakana text into 16 bit PCM at run time.
- Sources that name Sharp's engine for this game: Siliconera, Nintendo's Iwata seminar page, Yahoo Chiebukuro. Open projects that reuse the engine: github.com/Lqm1/shtts-rust (its `tests/data` holds `cases.tsv` and 1248 reference recordings `ref/*.pcm`, used as the reference below), github.com/26d0/shtts-web, github.com/dylanpdx/talkmodachi.
- ARM9 also has the Mii parameter key `voice` (next to `character` and `motto`). How the game turns a Mii's voice setting and its texts into an engine voice, emotion and tags is **not traced** (OPEN).

**Engine entry points** (ARM9 RAM addresses, ARM9 base 0x02000000). Checked on the FR build 3.5.1 only; the JP original was not checked (OPEN). `speech_check` compares a CRC32 of each function with the branch offsets masked (`SPEECH_SIGS`), so another build is refused with a reason instead of crashing.

| Function | Address | Use |
|---|---|---|
| InitContext | 0x0208D4C8 | r0 = context (0x16000 bytes, zeroed first) |
| SetProperty | 0x0208D6F8 | r0 = context, r1 = property id, r2 = value; returns 0 when the value is accepted |
| Speak | 0x0208D0CC | r0 = context, r1 = text, r2 = mode (1), r3 = priority (0), [sp] = audio callback, [sp+4] = user pointer |
| sync word | 0x0208D248 | replaced by `mov r4, #1` (0xE3A04001) to force the synchronous path |
| OS_LockMutex, OS_UnlockMutex, OS_Sleep | 0x02007E1C, 0x02007EA0, 0x02007964 | replaced by `mov r0, #0` and `bx lr` (0xE3A00000, 0xE12FFF1E) |

- The last two rows are applied to a copy of the ARM9 in `Speaker.image()`, never to the ROM. Layout used by `Speaker`: context 0x02200000, text 0x02300000, callback trap address 0x02400000 (the VM calls Python instead of running code there), stack top 0x027E3F00.
- The callback gets r0 = number of halfwords and r1 = buffer of interleaved halfwords, 22050 per second. The toolkit keeps every second halfword (`[1::2]`), which is the 11025 Hz mono signal that matches the reference recordings (`SPEECH_SAMPLE_RATE`).
- Text: Shift-JIS bytes, katakana, NUL terminated (`speech_bytes`, which refuses with a message any character the engine cannot read and converts nothing). Marks: `＿ ． ！ ？ ／ ｜ ’` and their ASCII twins `_ . ! ? / | '`; a line break acts as `／`. Digits, the percent sign and spaces are skipped by the engine. Inline commands look like `<\Name>` or `<\Name=value>` (one game text has the backslash twice). Game codes are written `{hex}` (a code stands for a Mii name, a syllable of a song...); `listening_text` replaces each by a word to try a line.

**Properties** (SetProperty ids; the ranges are the engine's own limits: a value outside them makes SetProperty return non zero and the tab says "The engine refuses ...").

| id | Meaning | Range | Neutral | Script letter |
|---|---|---|---|---|
| 1 | voice | 0x101 + n, n = 0..11 (order of the `<\Spk_` presets) | | |
| 2 | emotion | 0x201 + n, n = 0..15 (order of the emotion presets) | | |
| 3 | Speed (duration, percent) | 20 to 2200 | 100 | S |
| 4 | Pitch | 3500 to 7000 | 5058 | B |
| 5 | Volume | -10000 to 360 | 0 | V |
| 6 | Voice quality (spectral) | 80 to 130 | 100 | X |
| 7 | Ring | 0 to 5000 | 0 | r |
| 8 | Echo delay | 0 to 3000 | 0 | I |
| 9 | Echo gain | 0 to 100 | 0 | J |
| 10 | FIR delay | 0 to 1000 | 0 | R |
| 11 | FIR gain | 0 to 100 | 0 | G |
| 14 | Accent | 0 to 400 | 100 | A |
| 15 | Phrase accent | 0 to 400 | 100 | P |

- Ids 12 (0 to 3), 13 (0 to 100) and 16 (0 to 1000) are accepted by the engine, have no script letter and are not exposed in the tab.
- The labels of 7 to 11 come from the preset names that use those letters (`Ring`, `Echo`, `Fir`). The reference test data calls ids 7, 8, 9, 10, 11 ring, fdelay, fdepth, edelay, edepth. The first id mapping tried here was wrong (48 effect cases differed from the reference); the ids above were found by brute force against the reference recordings and the effect cases then matched.

**Preset table** (the engine's named scripts, the part the Voices page edits).
- 53 entries of 0x78 bytes: a 20 byte NUL padded name, then a 100 byte NUL padded script. Two identical copies in the ARM9, at file offsets 0xB7B94 and 0xF22D4 on the FR build (RAM 0x020B7B94 and 0x020F22D4), found by searching for `<\Emp` followed by NUL (`preset_tables`). `preset_write` writes into every copy. Whether the game reads both or only one is unknown, so both are patched.
- Entries 0 to 21 are text commands (`<\Emp`, `Dem`, `Spd`, `Pit`, `Vol`, `RPit`, `RPrm`, `RSpd`, `Pau`, `Lwp`, `Ring`, `Ecl`, `Ecg`, `Firl`, `Firg`, `Hsp`, `Cho`, `Echo`, `Fir`, `Acc`, `Prm`, `RVol`), 22 to 37 emotions (angry, business, calm, depressed, excited, falsetto, happy, loud, monotone, perky, quiet, sarcastic, scared, shout, tence, whisper), 38 to 49 voices (`<\Spk_` male, female, admale, adfemale, emale, efemale, chmale, chfemale, sisters, meimu, space, giant), 50 to 52 `Rst`, `Ptr`, `sing`.
- A script is lines that start with `#` and a letter: `#B4800` sets the pitch, `#S90` the speed. Letters are in the table above, plus `Q` (reset), `Z`, `E`, `D`, `p` (pause), `C`, `k` and `T` (transpose); the exact effect of Z, E, D, C and k was not studied. A value written `+n` or `+-n` is relative (letters B S V A P only). `script_check` enforces the ranges and the 99 byte limit.
- Tags in a text: `<\Name>` for voices, emotions and commands without a value, `<\Name=value>` when the script has an item with an empty or `+` value other than Q and Z (`tag_values` in the catalog). The Insert menu of the Text page builds them.

**Running the engine without a console.** `ArmVm` (`features/speech/armvm/`: `machine` interpreter, `translator` basic blocks to Python source, `analysis` flags and block ends, `arithmetic`, `constants`, `errors`) is a pure Python ARMv5 interpreter: basic blocks are translated to Python source and cached, flags are evaluated lazily, and addresses can be hooked (the audio callback). It is not a general emulator: it has what this engine uses and raises `Unsupported` otherwise. It runs at about 0.7x real time (slower than playback), so `Synthesizer` (`synth.py`) computes in a thread, keeps the last sounds and the tab plays the sound when done; Stop sets `Speaker.cancel` and the callback raises `ArmCancelled`; opening another ROM drops the job. `Speaker.speak(text, voice, emotion, props, presets)` resets the VM memory on each call, sets the voice (id 1), the emotion (id 2) and `props`, runs Speak and returns 11025 Hz mono int16 PCM. `presets` applies edited scripts to the copy of the ARM9 first, so the preview uses the same bytes the patch writes. The engine is created the first time the Voice tab needs it.

**In the toolkit.** `cfg['speech'] = {'presets': {name: script}, 'lines': {path: {index: [old, new]}}}`; `patch()` calls `apply_speech(arm9, presets)` before `rom.set_arm9` and `apply_lines(rom, lines)` for the message files; `apply_lines` writes a line only if the ROM text is still the one it was edited from. The ROM tab summary says how many lines and presets changed.

**Validation: what was and was not checked.**
- Instruction level: random instruction sequences ran on `ArmVm` and on Unicorn (another ARM emulator) and registers, flags and memory were compared: 0 differences (scripts of the earlier machine, not in the repo).
- Output level: the 1248 reference recordings of shtts-rust (`cases.tsv`: text, pitch, accent, phrase accent, volume, speed, fdepth, fdelay, edelay, spectral, edepth, ring) against `Speaker.speak(..., props=...)`. The 1102 cases without effects were bit exact; after the property id fix the effect cases tried (45) were exact; a full re-run was at 600 of 1248 cases, all exact, when last noted.
- Tests: `tests/test_rom.py` makes the real engine speak, checks that a preset edit changes the sound, that lines come from the message files, that every line and preset goes to files and back unchanged, and that a changed line reaches the message file and nothing else does.
- NOT checked: the JP original ROM (fingerprints), and above all **the game itself**: no melonDS or DeSmuME run has shown that an edited preset or line changes what a Mii says. Both table copies are patched on the assumption that the game uses them. Nobody has listened to the sound on a real machine except through Léo's own use of the Listen bar.

### 10.3 Models
- Every file in `/Mdl` is an LZ10 NARC. 1278 BMD0 files, 3717 textures, formats seen: 16 colours (2703), 256 colours (559), A5I3 (371), A3I5 (69), 4 colours (9), 16 bit (6), no 4x4 compressed in this ROM. Other sub-files are BCA0, BTP0, BTA0, BMA0, APS and raw palettes (`e0 7f ff 03`, not decoded).
- TEX0 (offsets relative to the block): texture data size/8 at +0x0C, texture info dictionary at +0x0E, texture data at +0x14, compressed data +0x24, compressed info +0x28, palette size/8 at +0x30, palette dictionary +0x34, palette data +0x38. Dictionary: rev, count, size, then header (8), a (count+1) x 4 byte tree, unit size and total, entries, 16 byte names. Texture entry: offset/8 u16, param u16 (width = 8 << (p>>4 & 7), height = 8 << (p>>7 & 7), format = p>>10 & 7, colour 0 transparent = bit 13). Palette entry: offset/8 u16. Palette of texture `x` is named `x_pl`.
- Checked: render then encode then render is identical for all 3717 textures. Texture replacement keeps the file length.
- Not exercised: how a replaced texture looks in the game, 4x4 compressed import, models with raw palette sub-files.

## 11. 3D models: export and import for Blender (implemented)

Decision of Léo (2026-10-26): the toolkit does not edit geometry itself. The Models tab exports a model to a format Blender opens (OBJ, MTL, PNG textures) and imports the modified file back into the patch. Implemented in `features/models/`:
- **Container**: every file of `/Mdl` is an LZ10 NARC; a BMD0 has the blocks MDL0 (geometry) and TEX0 (textures, `bmd.py`, `textures.py`).
- **MDL0** (`geometry.py`): a dictionary of models; each model has an info block (SBC offset, material and shape offsets, position and scale parameters, vertex, polygon, triangle and quad counts, bounding box), node transforms (SRT with flags), materials (texture and palette references, polygon attributes), shapes (GX display lists) and the SBC command stream that draws shapes with matrix stack operations. `mdl_walk` runs the SBC stream and tracks the matrix stack; `gx_parse`/`gx_draw` run the display lists (BEGIN_VTXS, VTX_16, VTX_10, VTX_XY, VTX_XZ, VTX_YZ, VTX_DIFF, NORMAL, TEXCOORD, COLOR, MTX commands). Every model of the game draws each shape once (`mdl_draws`).
- **Export** (`obj_export.py`, `shapes.py`): triangles and quads in model space (Y up) with UVs and normals, one OBJ object per shape, MTL and PNG textures.
- **Import** (`obj_import.py`, `dlencode.py`, `bmd_edit.py`): the OBJ is matched to the original shapes; a polygon that did not change snaps to the original data (so an unchanged export imports as "no change"); changed polygons are re-encoded into display lists (strips and the shortest vertex commands), MDL0 and BMD0 are rebuilt (the size may change) and the NARC is rebuilt at the new size (`narc_replace`, names kept, compression kept). Nodes and materials are kept as they are, since the animations (BCA0, BTA0, BTP0, BMA0) refer to them by index or name: import replaces shape geometry only.
- **Checks**: `tests/test_rom.py` round trips every 40th model of the ROM (more than 1000 models in the list) and expects "no change"; moving all vertices in the OBJ moves them in the model within 0.01; 81 tests in `tests/test_models.py` cover the parser, encoder, animations and render. **Not played** in the game.
- **Blender, checked 2026-11-04** (Blender 5.2.3 in background mode, `bpy` scripts in the scratchpad, not in the repo): the winding of every polygon agrees with its stored normal, so the face orientation and the normals match; Blender's OBJ import turns each object 90° about X (Y up becomes Z up, the feet stay at the origin); the pictures load at their sizes; Base Color is linked to the picture and Alpha to `map_d`; the body of the ROM written back by Blender with its default options imports as "no change" (2 shapes, no warning). Blender reads the MTL with no option: the text after `map_Kd` is taken as the file name, so no option (such as `-clamp`) is written. The game's wrapping is not expressible: of the 4621 materials of the ROM, 2019 repeat their picture plainly, 2488 repeat it mirrored (the flip bits of TEXIMAGE_PARAM) and the other 114 (66 of them with no picture) clamp or repeat on one axis only; Blender repeats plainly, so the export says so when a polygon goes beyond the picture of such a texture. Every material culls its back faces in the game (only the front is drawn); Blender draws both sides and the MTL cannot say otherwise. Three materials are see-through in the game (polygon alpha 26, 8 and 16 of 31: the fountain, the wave shadow of the beach, `lambert65` of rm50): they get a `d` line (Blender reads it as the transparency), or, when their texture has its own alpha, the export says that Blender shows only the texture's.

## 12. Currency work: money map and verification (moved from the deleted toolkit README, written 2026-10-25)

Parts overlap sections 3.5 and 4.

### Finding more sites

Disassemble the ARM9/overlays, list `BL 0x20364E0` / `BL 0x20363A8` callers, add the money ones to `SITES`. Find baked yen pictures by scanning NCGR tiles for the `YEN` bitmap.

### Money map

The wallet is a u32 at money struct `+0x50` (runtime `0x2329CE4`, struct base `0x2329C94`), reached through the global holder pointer at ARM9 `0x2122FF4`. Every wallet write goes through `SetMoney` (`0x202D1EC`), which clamps the value. Overlays share one RAM address (`0x21495E0`) and are loaded one at a time.

| Where | What | Status |
|---|---|---|
| ARM9 `0x20F5AD8` (T1) | Item price table, 255 rows of 20 bytes (rows 0..254), price = word0 & 0xFFFFFF | converted by `convert_tables` |
| ARM9 `0x20F3BBC` (T2) | 300 rows of 20 bytes (rows 0..299), price = word0 & 0x7FFFFF, bit 23 is a flag | converted by `convert_tables`; category not confirmed |
| ov83 `0x21496BC` | Copies the wallet into a working field (struct `+0x19000+0x4A4`) when a shop screen opens | verified |
| ov83 `0x214A6E4`, `0x214A7F8` | Subtracts a price / adds an amount to that field, clamps at 0 | verified |
| ov83 `0x214B610` | `SetMoney` from that field | verified |
| ov75 `0x2149DBC`, `0x214B8D0` | Copies the wallet into `+0x30000+0x9B4`, then `SetMoney` from the same field (Mii gift) | verified |
| ov82 `0x2149844` to `0x2149858` | Income: wallet + amount from `0x2149E1C`, then `SetMoney` | verified; amount source not traced |
| ARM9 `0x20AA88C` | Price/amount helper: calls an object's vtable (slot +8 or +0xC, chosen by mode at `+0xA000+0xFA4`) | dispatcher verified; target object not traced |
| Tutorial payouts (6800 after the intro) | Money given during the intro | not found: no 6800 literal, no init store, no NitroFS hit. Probably added through the ov83 add path via `0x20AA88C`, unconfirmed |
| ov96 `0x214A43C` | 12-bit field x 60 added to 64-bit counters (`+0x95C`/`+0x960`, `+0x4A0`/`+0x4A4`) | time, not money |

Open questions:
- Where the tutorial amounts come from (the intro script or a helper result).
- Whether T1 and T2 are both read by `0x20AA88C`, and what T2 holds.
- Whether ov82's amount (`0x2149E1C`) is an income formula or a table.

Done: T1, T2 and the ov82 income. Still open: the tutorial payouts, the helper's target object, and the other readers of T1/T2. All wallet writes pass through `SetMoney`, so it is the one place to check every change.

### Verification status

Checked without the game (static, offline, or headless):
- Patch output diffed against the original ROM. Only the intended bytes change: T1/T2 price fields, the cave (cents thunks in cents mode, income wrapper always), the 4 ARM9 display sites and the overlay display sites (cents mode only), the `YEN_TEXT` glyph, the overlay 82 call at `0x2149844`, the fonts and baked pictures for the symbol, and the `compressed_static_end` field.
- Income wrapper disassembled: `push {r3, lr}`, `bl 0x2149E1C`, `pop {r3, lr}`, `b` thunk, `bx lr`. The 8-byte stack push keeps alignment. `0x2149E1C` has one caller in overlay 82 (`0x2149844`). Overlay 24 calls the same address, but it runs its own code there.
- Cents display thunk at rate `0.01`: emulated (unicorn), exact for stored values 0..9999999, including the cap value.
- Fixed-point thunk arithmetic for scales 0.01 to 920: within 1 of the reference rounding.
- Table rows: T1 0..254 and T2 0..299 are the valid rows; the bytes after them are unrelated data.
- Blob lengths and thunk addresses are 4-byte aligned (CENTS = 248 bytes).
- Wallet cap: `SetMoney` clamps to 9999999 (literal read from the ROM).
- Python: `pyflakes` clean; the test suite passes; the currency tab's rounding checkbox and symbol palette are driven by `tests/test_ui.py`.

Not verified (needs the game):
- Tutorial start money: the source is unknown and not converted. If it is a yen constant, the start wallet is in the wrong unit.
- Other readers of T1/T2: about 40 overlay and ARM9 functions read the table. They are assumed to read only the price. A reader that compares the price with a yen constant would break.
- Shops that do not read T1/T2 (costume, interior, goods), job wages, and sell price.
- List display (whole units, rounded, minimum 1) against purchase display (cents) on each screen.
- Symbol glyphs in-game.
- Save compatibility: old saves hold yen values and are not supported.

Known consequences:
- Whole-unit currencies: the wallet cap of 9,999,999 is about 1.09 M yen for KRW, far below the yen cap.
- T2 prices above the field maximum (8,388,607) are capped. For a whole-unit currency with rate above about 8.47 this affects the most expensive T2 items. The patch logs the count, and the currency tab shows the yen threshold above which prices are capped.
- BMG texts keep their yen figures. Four messages in `BMGs/test` say yen: `tmd_contents` 69 ("10 yens"), `tmd_etc` 123 ("２１００ yens" moving cost), `tmd_etc` 169 ("Collecter au moins 20 000 yen"), `tmd_etc` 302 (`[TAG] yen(s)` today's income). They will disagree with the converted amounts and always say "yen".
- Lists round to whole units and purchases show cents, so the same item can show two numbers.

## 13. UI rework of 2026-11-03 (second session, several rounds)

What was checked: `compileall`, an import of the whole application, a scan for undefined global names and unused imports, and two scripts (in the scratchpad of the session, not in the repo) that open the FR 3.5.1 ROM and drive the window like a person: every tab, selecting rows, the entries of the right click menus, export and replace with the dialogs stubbed (`tests/ui_stubs.py`), undo and redo, the engine speaking a line. They ended with no exception. **Not done**: looking at the window (Léo reports visual problems), clicks with a real mouse, updating the old tests (`tests/test_ui.py` and part of `tests/test_keyboard.py` still use widgets that are gone). `features/keyboard/textfile.py` is no longer used by the window (kept, it can go).

- **Groups** (`ui/tabs/__init__.py`): ROM [ROM, Meta], Location [Currency, Keyboard, Fonts], Dialog [Text, Voice], Graphics [Images, Models], Sound [Audio, BGM]. Text is the old BMG tab (key `bmg`), Voice keeps the key `speech`; the patch configuration and the `.tomods` file did not change.
- **One layout for the list tabs** (Images, Models, Audio, BGM, Text, Voice; `ListingTab`): bar at the top (search, Modified only, count, Batch export, Batch import, Revert all); on the left the list of every element; on the right, in this order, the **summary as a table** (`widgets.InfoTable`, rows of name and value; a row with a function is a link), the actions that are not export or replace (Play), the main view; a note under it when needed. **No Replace, Export or Revert buttons**: the right click on a row of the list (`ListingTab.build_menu`) gives Play, Export, Replace and Revert. **Revert changes** (`widgets.RevertButton`) is a button of the layout: `build_listing` packs it at the bottom right of the right pane before the content, so it keeps its place and covers nothing. It is greyed out unless the selected item has changes (`item_changed()`; `sync_revert()` is called from `changed()` and from the selection handlers). Currency, Keyboard and Meta pack it at the bottom of the tab in the same way and take back everything the tab changed.
- **Audio**: the table has Wave, Length, Rate, Encoding and one `Used by` row per bank; **Play** starts a sound from its point and **Pause** keeps the point (Play goes on from there); a click on the wave sets the point; a line moves over the wave while the sound plays and stays where it was paused (`ui/transport.py`, class `Transport`, the same logic as the BGM tab); a new sound longer than the one it replaces is shrunk or kept after one question at the import (`Audio.shrink_asked`, one question for a folder; the checkbox is gone); a bank that plays music is a link: `App.open_bank` goes to the BGM tab, whose search box then holds the bank and the first of those sequences is selected (`BgmTab.show_bank`). A bank of sound effects only is plain text.
- **BGM**: the table has Sequence, Number, Length, Tracks, Notes, Tempo, Loop, File; Play, the bank and the volume stay as controls. **Play** starts the music from its point and **Pause** keeps it: the button reads Pause while the music plays and Cancel while it is prepared. A click on the piano roll sets the point where the listening starts. The line follows the music every 40 ms and stays at the point when paused (`BgmTab.after_play`, `Transport`). Leaving the tab pauses; choosing another sequence or changing its bank or volume starts over.
- **Text** (`ui/tabs/bmg.py`): made for people who translate. Left, the 24 message files (name, number of messages, state; the ROM copies that the build 3.5.1 truncated show their problem, section 8). Right, the messages of the selected file in a list (number, ID, text with the game codes shown as a lozenge and the line breaks as arrows; a changed message has a dot), and under it the message as the ROM has it next to the message as it will be, with the game codes marked. What is typed is the message at once (a bad code is refused with the reason), Ctrl+Down and Ctrl+Up go to the next and the previous message, the size in characters is shown next to the ROM's. The search box searches the names of the files and the text of the messages; a right click on a message copies it or takes it back; the Revert changes button takes back the message on show, else the file. A right click on a file: Export, Replace, Revert.
- **Models**: left, the archives as in the Images tab; right, the model on top; below, the files of the selected archive as a table-like tree (File, Type, Size) and what the selected row looks like. A file is named by its magic: Model (BMD0), Skeleton animations (BCA0), Texture scroll animations (BTA0), Texture swap animations (BTP0), Part visibility animations (BVA0), Material colour animations (BMA0, no reader), Palette, Tile graphics, Screen (NCLR, NCGR, NSCR), Raw data. A model without skeleton animations of its own (the Miis) has a `Shared animations` row: the animations of `/Mdl/Ica` that fit its skeleton. A texture or a palette has its picture; a shape is drawn alone; a file with no other view shows its first bytes. **An animation is edited** (`ui/animview.py`, `features/models/animedit.py`): the tracks (bones, materials, parts) on the left, the keys of the selected one on the right in a table. A value changes by a double click (Enter keeps it, Escape leaves it) and the model plays the change at once. Skeleton animations: Move, Turn (angles in degrees about X, Y, Z) and Size per bone; texture scroll: Scale and Move; texture swap: frame, texture, palette of every key; visibility: a grid of parts and frames that a double click turns on or off. A value in brackets lies between two keys and follows them; a star is read by other animations too (3.5 % of the samples of the skeleton animations are shared) and changes them too. Numbers are written in place; a rotation is a new entry of the table of rotations, put at the end of the file (an entry is only a place at ten bytes times its number from the start of the table, the sample arrays follow the table, and every BCA0 file has one JNT0 block that runs to its end), so the other keys that used the old entry do not move: the file grows by 12 bytes per new rotation. Tested on the 3.5.1 ROM: a rotation written back reads the same within 0.002, the other keys and the other animations of the file stay as they were. **Export table** and **Import table** (in the editor, and on an animation row of the tree) write and read the whole table as a CSV file (`animedit.table_csv`, `read_table`, `apply_table`). The cells are separated by `;` (what French spreadsheets expect, `,` is also read), the decimals are written with a comma. Each group starts with a row whose first cell is `#` and gives its column titles; the other rows are sheet number, sheet name, group, frame, then the values. An import writes only the values that differ, through the same code as a double click (a skeleton turn is written as its three angles at once, so two axes changed in one table are both kept); a value between two keys is reported, not written. Blender was not chosen: a skeleton animation is per bone keys in the game's own format (BCA0, the table of rotations, sample arrays shared between tracks), and a Blender route needs a glTF or FBX export and an import that maps the bones and rebuilds the keys. That is a separate piece of work; the CSV is the editable form for now. Not done: adding or removing a key, changing the number of frames, Material colour animations. Counts in the 3.5.1 ROM: 1674 models, 157 skeleton, 24 texture scroll, 18 texture swap, 6 material colour and 5 visibility animation files, 294 raw files, 341 sets of NCLR, NCGR and NSCR (in `/Job`).
- **Voice** (`ui/tabs/voice/`): the tree holds the banks with their lines, then the voices. The panel of a line has the toolbar (Play, which becomes Stop while the sound is made; Voice and Emotion side by side; the length of the sound; the size of the text) and two views: **Visual** (the blocks, the choice of Pitch, Length or Volume with `-`, `+` and Flatten, the graph, then the palettes in their own tabs: Sounds with the marks, Game codes, Effects; an effect that is selected shows its value) and **Text** (the line as the game holds it, live). A right click on a block or a cell: Copy (and Insert before the block, Replace the block). The codes that are the same thing in a line share an icon by family (`FAMILY_ICON` in `features/speech/about.py`: ☺ Mii, ✎ names, ♪ syllables, ♡ nickname, “ words, ◆ items, # news, ¶ phrases), and each code has its own colour, so Name and Name 2 have the same icon in two colours. Each effect has its own icon and colour (`code_info`, `effect_style`; checked 2026-11-04: 25 codes with 25 colours, 22 effects with 22 icons and 22 colours, no effect icon used by a family), also on its block in the strip. The codes are in the order of their role (Mii, names, syllables, nickname, words, items, news, phrases), the effects in the order of their use. Under a palette, the cell under the pointer says in a few words what it makes the Mii say (`Palette.hint`). The lines are read from the message files as the Text tab will patch them: when a file was replaced there, the lines of that bank are read again the next time the Voice tab is shown and the changes made to them are dropped (`VoiceTab.read_again`).
- **Keyboard**: no Undo button, no Layout frame, no key inspector, no text file; `Start from` is a menu; a changed key has the page colour and an orange dot; a right click on a key: Copy, Blank, Restore.
- **Undo for the whole tool** (`ui/history.py`): Ctrl+Z and Ctrl+Shift+Z act on the tab on show (`App.step`), per tab, with the states that `Tab.snapshot()` gives (`project_part()`); changes less than 0.7 s apart make one step; a text field keeps its own undo; the footer says what happened. The keyboard window has its own pair and selects the key that changed.
- **Right click and Copy** (`widgets.popup`, `copy_text`): the grids of characters (Currency, Keyboard window), the cells of the palettes and the blocks of a line. The pointer over a character of a character palette (`ui/charpalette.py`, Currency and the keyboard editor) writes its character, its code and its name at the bottom right of the palette (`CharPalette.point`); it is cleared when the pointer leaves.

## 14. Can the speech engine speak other languages? (research of 2026-11-03)

Question from Léo: the engine is perfect for Japanese; how did Tomodachi Life (3DS) make other languages work, and is it possible here?

What was found (Léo asked for no change to the engine, so nothing was done in the code):
- **The DS engine is Japanese only.** Wikipedia (Tomodachi Collection, Tomodachi Life) says the Western release of the DS game was dropped because the voice synthesis program, "built natively for Japanese", could not reproduce the phonetics of English (cited there to Nintendojo, "Tomodachi Beginnings", 2014; not read). Section 10.2 says the same from the ROM: the engine reads katakana as Shift-JIS and has 12 Japanese voices.
- **The 3DS game did not stretch the Japanese engine; it changed engine.** The reverse engineering notes of dylanpdx (github.com/dylanpdx/talkmodachi, `docs/internals.md`, the author's own claims, no code or offsets given) say: Mii voices of Tomodachi Life and Miitomo are Nuance "Vocalizer for Automotive", extended by Nintendo into a layer called NTTSMiiVoice (singing, per Mii voice settings, effects such as echo; text tags change the Nuance output). The Japanese Tomodachi Life "uses an older TTS called SharpTTS, that only supports Japanese", which is this DS engine family. So a Western 3DS build has a real multilingual engine with a front end (text to phonemes) and a voice database per language; Nintendo's layer works on the audio after it.
- **Switch game** (Tomodachi Life: Living the Dream): talkmodachi says Nuance was replaced by NeoSpeech VoiceText; tlmodding.com (`documentation/living-the-dream/text-to-speech`, "work in progress") says ReadSpeaker, with files `tts_single_db(D32-{Voice}).vtdb2` in the `VoiceText` folder of the romfs, one voice per language (HIKARI Japanese, ASHLEY American English, GLORIA and LOLA Spanish, CHLOE and ROXANE French, BRIDGET British English, LENA German, ELISA Italian, ANNE Dutch, HYERYUN Korean; two Chinese voices built by Nintendo in 2025), models of 16 kHz in spite of "D32". Both names may be the same product family; not settled.
- **Short answer for this project**: feasible only as an approximation. A French voice would need what the 3DS had (a multilingual engine with its dictionaries and voices); SHTTS in this ROM has none of it and its voice data is Japanese, so the engine cannot be taught French by editing presets, lines or the ARM9 tables. Porting Nuance or ReadSpeaker is not possible (closed, large). The honest way is the one the toolkit already has: write the French sounds as katakana (raw data rule), tune them with the sounds, pitch, length and the voice presets. A better pronunciation helper (a French to katakana suggestion shown beside the text box) would be a tool feature, not an engine change, and still only an approximation. **Verdict: a native French pronunciation engine is not feasible in this ROM; drop it, keep katakana.**
- **Not checked** (the session limit was reached): the Iwata Asks interviews (nintendo.co.jp/3ds/interview/ec6j/vol1 and nintendo.co.jp/ds/interview/ccuj/vol1), the Nintendojo and 1Up articles, the pages `docs/singing.md` content, `gamePatch/` and `api/` of talkmodachi, and tlmodding's Tomodachi Life (3DS) page `documentation/tomodachi-life-3ds/text-to-speech/`. A search result said the 3DS game speaks seven languages (English, French, Italian, German, Spanish, Japanese, Korean); that line came from a search summary, not from a page that was read.

### 14.1 Game codes and effects of the speech lines (2026-11-03, `features/speech/about.py`)

**Game codes, read in the program.** The function at ARM9 `0x0202E860` (FR 3.5.1) expands a message. A tag is `1A 00`, a size byte, a group byte, a type (16 bits) and the argument (16 bits). For the group 1 it puts a string there: the string number NN (the low byte of the argument) that the scene gave to the message, in a table that starts at 0x160 bytes into the context. The types 0x01, 0x02, 0x03, 0x0a, 0x1e and 0x1f put it whole; 0x14 and 0x15 cut it to 12 characters; 0x28 to 20; 0xfa puts a whole message (number NN, a table at 0x1b0, expanded with the same function, so it may hold codes); every other type shows nothing. The group 0xff type 0 (look of the text) is copied through; other groups are skipped. So **the type does not say what the string is**: `{08011f000000}` and `{080101000000}` print the same string number 0. What the string is depends on the scene that shows the message: from the lines, the conversations (`1f`) put the Mii names (0 the one who speaks, 1 another), the news (`1e`) numbers, hours and names that change from one message to the next, the mini contents names, items and sayings, the songs (`01`, up to 9 codes) one syllable of the sung name each, the profile messages of the `etc` file (`01`) the parts of a date. The palette therefore names a code by the role it has in the lines, in a few words (`features/speech/about.py`): `1f` Mii name (0) and Other Mii (1); `1e` the news, Name/time 1 and 2 (a name before "san", or an hour, a day, a year, minutes), Name 3 and 4, Word/number, Quoted word; `01` Name/syllable 1 and 2, Syllable 3 to 9 (the name sung or spelled out, one syllable per code); `03` Nickname ("...cchi"); `0a` Word and Said word; `14` Food/item 1 to 3; `fa` Phrase 1 and 2 (a ready made message, such as the month and the day of "It is ... "). These roles are read from the text around the codes; the scenes themselves (overlays) were not read.
**Effects.** What each command does was measured by making the engine say a sentence with and without it (duration, loudness, pitch, tone): Pit, Spd and Vol set the pitch, the speed and the volume; RPit, RSpd and RVol move them from there on (the graph writes these); Pau a pause (in thousandths of a second); Emp makes the speech louder, quicker and higher, Dem softer, slower and lower; Acc and Prm (RPrm moves it) the strength of the accent and of the phrase accent; Lwp the tone (brighter or duller); Ring a metallic voice; Ecl and Ecg the delay and the level of an echo, Echo both at once; Firl, Firg and Fir the same for a filter; Cho (k) changes the voice without changing its length, probably a chorus; Ptr (T) transposes, sing is a preset for singing, Rst takes every effect back. Hsp (C) changes the speed and the pitch of the voice with its first values and not with the others: not understood. The lines of the game write only RPit, Vol, Spd, RVol and Ring (and the mood monotone); the Effects palette lists every command in the order above.

**Update of 2026-11-04.** The palette shows these labels (`about.CODES`, in the order of the palette): Mii (`1f` 0), Other Mii (`1f` 1), Name and Name 2 (`01` 0 and 1, a name said in the line), Syllable 3 to Syllable 9 (`01` 2 to 8, one sung or spelled-out syllable each), Nickname (`03`), Word and Word 2 (`0a`), Item to Item 3 (`14`), News 1 to News 6 (`1e`, the blanks of the news: a name, an hour, a day, minutes, a number, a quoted word, as the scene fills them), Phrase 1 and 2 (`fa`, ready-made pieces of text). The labels that were written before this update were guesses from the lines; these name the same roles after what the game puts in them. The icon follows the family of the code (section 13), so the codes of one family look alike and their colours tell them apart.

## 15. Round of 2026-11-04: playheads, Revert in the layout, codes and effects, animation tables

Done (`ui/widgets.py`, `ui/tabs/*`, `ui/tabs/voice/*`, `ui/animview.py`, `features/speech/about.py`, `features/models/animedit.py`):
- Groups: Dialog (Text, Voice) right after Location.
- Revert changes is part of the layout (section 13): greyed out when there is nothing to take back, never drawn over other widgets.
- Audio and BGM: Play and Pause keep the point (`ui/transport.py`); a click on the wave or on the piano roll sets it; a line shows where the sound is (it follows the music every 40 ms while it plays).
- Voice: codes that are the same thing share an icon (their family) with their own colours; each effect has its colour and icon; codes in the order of their role; the cell under the pointer explains itself under the palette.
- Models: the export checked in Blender and the see-through and wrapping notes (section 11, "Blender, checked 2026-11-04").
- Animations: Export table and Import table (CSV, see section 13). Blender was not chosen, the reason is in section 13.

Checked: a script drove the window on the FR 3.5.1 ROM (`compileall`, names, unused imports, then the window). Group order, Revert present and greyed out in every tab, codes in the expected order with their hover text, the playhead appears while a sound plays and goes when the tab is left, a longer sound asks the question, the visibility table of an animation is exported, one flag is edited in the CSV and imported, a skeleton turn is edited in the CSV (two axes of one key at once) and imported with the other values unchanged. Playback checked 2026-11-04 headless on the FR 3.5.1 ROM with the test player: Play, Pause, resume from the point, a click on the wave (Audio) and on the piano roll (BGM) while paused and while playing, Cancel while the music is prepared, the stop when the tab is left, and a new sequence or sound starting over. `tests/test_ui.py` steps `step_audio` and `step_music` were updated to the new buttons and pass; `tests/test_rom.py` (27 tests, the OBJ round trip included) passes.
Not checked: how it looks (Léo reports visual problems). The window tests pass now (section 16 lists what they cover).

## 16. Fonts tab, keyboard presets and the test suite (2026-11-04)

**Fonts (Location group, `ui/tabs/fonts.py`).** The game draws its text with two NFTR fonts, one bit a pixel, UTF-16 codes (`/Cmn/Font/FontLD12x_LZ.bin`: messages, 11 x 15, 1229 glyphs, no Cyrillic and every glyph cell used; `/Cmn/Font/FontLD10x_LZ.bin`: keys, 9 x 12, 3824 glyphs, 66 Cyrillic codes already). Both are LZ10 archives holding one font. Checked in the code and on the ROM:
- Adding characters (`features/fonts/grow.py`, `add_glyphs`): a new glyph is a new cell at the end of the glyph block (the cell count is `(size - 16) // cell_size`, so the padding stays under one cell), the widths of the new glyphs go into a new HDWC block (the font's default widths), and their codes into a new PAMC block of kind 2 (a list of code and glyph pairs). The header gets the new file size and block count. The cells, widths and codes of the game are not touched. Tested: the font reads back, the glyphs of the old codes are identical, the ROM written with `apply_subfiles` reads back the new characters.
- Pictures: PIL renders the character from a TrueType font of the system (DejaVuSans, Noto Sans or Liberation Sans are looked for; the tab has a Browse button), the largest size that fits the cell, centred. `ttf_draws` says whether the font has the character (a font that lacks it draws the same box as a private-use code).
- A letter is added to each font that lacks it. The keyboard and the text use the characters both fonts draw (`Characters`), so after the add they accept the letter; the session keeps the changed characters (`Session.set_font_changes`) and the ROM changes only at the patch (`patcher`, key `fonts`).
- Project: the `fonts` part is `{font file: {code: [rows of 0 and 1]}}` (`project.font_check`).
- Limits: no PNG import of glyphs yet; the picture is one bit and crude at 9 x 12 and 11 x 15; **not played**: the game's own font loader was not run with the new blocks (no emulator here), the blocks are the standard NITRO ones.

**Keyboard presets (`features/keyboard/presets.py`).** Accents offers seven "Start from" layouts (French accents first, German umlauts, Spanish signs, Italian, Portuguese, Nordic letters, currency signs), each with the game's keys in the game's rows. QWERTY gains Turkish (with ş ğ ı ç) and Polish (with ą ę ś ł), which fit the four keys round the space bar (a layout must have as many keys as the game: a longer list is dropped without a message, which is how the first try went unnoticed). They need letters the game font does not draw: the Fonts tab has buttons "+ Turkish letters" and "+ Polish letters" that fill the box, then Add; the layouts then appear in the Start from menu. A Greek layout was tried and removed: a name must keep the Latin letters (`tests/test_keyboard.py` enforces it). Ö and Ü of Turkish stay on the Accents keyboard. Symbols, Emojis and Japanese have no presets (their key geometry was not read).

**Test suite (`python -m tests`, with the ROM, 2026-11-04): 500 tests, OK.** `tests/test_ui.py` was brought up to date: tab titles and groups (Fonts, Dialog, Sound), the tab state counts, the currency revert button, the keyboard settings through the Start from menu (the batch and text file parts were removed, they are not in the tab any more), the BMG file replace (an identical file is no change), the Fonts step, the models rows (archive rows are `a:` + path), the model view, the voice step (sounds, blocks with undo, game codes, text view, rhythm and the pitch graph, effects, voices, listen and save, revert, batch, project) and the project step (the BMG summary is "1 changed"). `tests/test_models.py` got the `only` attribute its render stub lacked.

**Fonts tab, second round (2026-11-04): view and edit first, adding letters last.** The ROM has three fonts (`features/fonts/grow.py`, `ALL_FONTS`): `/Cmn/Font/FontLD08x_LZ.bin` (7 x 7, 312 glyphs), `FontLD10x` (9 x 12, the keys) and `FontLD12x` (11 x 15, the messages), all one bit a pixel, UTF-16 codes. The tab lists them; a glyph is found by a character or a code (U+XXXX), the grid shows 128 glyphs per page with the changed ones in orange, and the editor changes the pixels of the selected glyph (click or drag, release to keep). A glyph is written in its own cell (`replace_glyph`), so the font keeps its size; characters that the messages and the keys fonts lack are added at the end of the tab (`add_glyphs`, unchanged). One dictionary `changes` ({font: {code: rows}}) holds both kinds: `apply_changes` writes the codes the font draws in place and adds the others. The project keeps the same `fonts` part, now with edited glyphs too. Tested: a pixel changed and taken back in the window sequence, the patched font reads back, the full suite passes (500 tests). Verification: the tests and a self-review of the tab against the Keyboard and Currency tabs (the same Tab base, RevertButton and summary); a separate verifying pass was not run.

**Short texts and pickers (2026-11-04, third round).** The long explanations of the Fonts tab and the note of the Keyboard tab are cut to a line. In the keyboard settings window the "Start from" menu is a dropdown labelled "Presets" (`KeyboardEditor.preset_box`). On the Fonts tab "Pictures from" is a "Base font" dropdown listing the TrueType and OpenType fonts installed on the computer (`grow.installed_fonts`, scanned in the usual folders of Linux, macOS and Windows), with "No base font" for empty cells; the default is DejaVu Sans when it is installed.

