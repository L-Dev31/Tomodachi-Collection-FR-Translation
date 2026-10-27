# Research notes: Tomodachi Collection (DS) FR fan translation

Written so another AI or developer can continue without the previous chat (renamed from HANDOFF.md on 2026-10-26; the toolkit README was removed and its unique content is in section 12). Everything here was either verified in the code, in git history, or in the ROM. Items marked **UNVERIFIED** or **OPEN** are not settled.

---

## 1. Where things are

| What | Path |
|---|---|
| Translation repo (main branch) | `C:\Users\gigabyte\Documents\GitHub\Tomodachi-Collection-FR-Translation` |
| Toolkit (GUI + patcher) | `tools/toolkit/toolkit.py`, `tools/toolkit/test_toolkit.py` |
| BMG injector and checker | `tools/bmgrom.py` (not committed) |
| BMG notes (committed) | `BMGs/BMG.md` |
| BMG files in use | `BMGs/test/*_msg_JP.bmg` (7 files) |
| bmge project (BMG editor, `build-bmg.js`) | `C:\Users\gigabyte\Documents\GitHub\L-Dev31.github.io\projects\demos\bmge` |
| Scratchpad (analysis scripts, melonDS, RAM dumps) | `C:\Users\gigabyte\AppData\Local\Temp\claude\C--Users-gigabyte-Documents-GitHub-L-Dev31-github-io-projects-demos-bmge\2c651e32-8b24-4ebe-b9f3-e5bc6c836fa7\scratchpad` |
| Test ROM used by the scripts | `C:/Users/gigabyte/Downloads/tomodachi collection fr2_UN seul BGM modifié.nds` (path in `scratchpad/romlib.py`) |
| This file | `tools/toolkit/RESEARCH.md` (**not committed**) |

Git state on 2026-10-26: `tools/toolkit/toolkit.py` and `test_toolkit.py` modified, `RESEARCH.md` new (renamed from `HANDOFF.md`), `README.md` of the toolkit deleted at the user's request, `tools/bmgrom.py` untracked, nothing committed. The `README.md` at the root of the repo belongs to the translation project and was not touched.

Git state at the time of the first writing (2026-10-25):
- Translation repo: `main`, clean after commit `c1263e7`.
- Recent commits: `c1263e7` toolkit update; `52d52ff` add `BMGs/BMG.md`; `4426fa0` realign etc/item/room BMGs (translation repo).
- `651980a` "bmge: fix BMG builder output rejected by the game" is in the L-Dev31.github.io repo, file `projects/demos/bmge/js/build-bmg.js`.
- The bmge repo's working tree had many unrelated modified `_backups` files at session start. Do not commit those.

## 2. Working rules set by the user (Léo TOSKU)

- Chat with Léo in French. Code, comments, commit messages and Python are in English.
- Commit **only when asked**. Commit messages: ultra-concise English, **no Co-Authored-By line** (the user's rule overrides the default attribution reminders).
- Python: stdlib only, ultra short, **no code comments**, no `.mjs`.
- Keep the GUI polished (warm orange/cream theme). No visual regressions.
- **Do not automate melonDS** (no clicking, no killing the instance). Several attempts were rejected by the user. Use passive RAM reads only (`ramdump.py` / `kbstate.py`).
- Be honest about what is verified. Report failures plainly.
- Prefer lazy, minimal changes (the session ran the "ponytail" lazy-developer mode).
- When the user asks to verify without testing: use static checks, offline emulation of pure code, headless Tk checks and reasoning. Do not drive melonDS. The user does the game tests.
- (2026-10-26) Do not run tests while building: the user will say when it is time for the final tests. When asked to update a file in the repo, do that first and report.
- Never use the em dash in anything written for the user. Do not verify work by looking at screenshots or rendered images; the user reports visual problems.

## 3. Toolkit ("Tomodachi Location Toolkit")

Run: `python toolkit.py`. Tkinter, stdlib only. Tests: `python test_toolkit.py` (prints `ok`). Renamed from `tools/prices/` in git.

### 3.1 Tabs (in order)
Nine tabs: ROM, Meta, Currency, Keyboard, BMG (8.4), Images (9), Models (10.3), Audio (10.1), Speech (10.2). The user asked for Images and Models side by side and for Audio and Speech last. The first four are described here.

**Batch actions (listing tabs):** Images, Audio, BGM, Models and Keyboard now use the unified `Batch export` / `Batch import` / `Revert all` buttons in the search bar via `ui/widgets.batch_buttons`. 
- **Images:** export listed images to a folder as PNGs; import PNGs from a folder (matched by filename).
- **Audio:** export listed sounds as WAV; replace from a folder.
- **BGM:** export listed sequences as `.mid` + `.sseq`; replace from a folder.
- **Models:** export models as OBJ/MTL + textures per model folder; import OBJ files back.
- **Keyboard:** export/import keyboard layouts and tab order.
- **BMG:** keeps its own `Replace from folder` / `Cancel all` UI.
1. **ROM**: Open ROM (refuses non-Tomodachi ROMs), banner preview (32x32 from the ROM banner), file name/folder/size, a "Will be applied" summary (Currency, Keyboard, Meta, BMG, Images, Models, Audio, Speech), Patch ROM, Export BPS patch, Apply BPS patch, Save project (.tomods) and Open project (.tomods) (9.1). Other tabs are locked until a ROM is loaded.
2. **Meta**: edit game title per language, icon, internal name.
   - Language dropdown (`LANGS = ['Japanese','English','French','German','Italian','Spanish']`), title text box.
   - **Apply to all languages** button copies the current text to every language (replaced the old "same title" checkbox).
   - Change icon / Reset icon. Requirements text on the right (`REQUIREMENTS` constant): PNG or GIF (no JPG), any size fitted to 32x32, 15 colours + transparent (more are reduced).
   - Internal name: 12 ASCII characters max.
3. **Currency**: dropdown of all open.er-api codes (default JPY), Symbol entry (single character, validated on each keystroke; an emptied field resets to the default on focus-out), Reset button, info line `1 CODE = x JPY`.
   - No display option any more (see 3.3).
4. **Keyboard**: reorder the 5 soft-keyboard tabs with arrows (Japanese, QWERTY, Accents, Symbols, Emojis); the first becomes the default. Icons are the game's own sprites.

Footer text in the GUI: "2026 by L-DEV31" and "TomoDS Team" (set by the user).

### 3.2 Patch config (`patch(data, cfg, log)`)
- `cfg['currency'] = {'rate', 'code', 'sym', 'whole'}` (`whole` = rounding checkbox; forced True for `WHOLE` codes and for codes where `cents_ok` is false)
- `cfg['keyboard'] = [order]` (only when different from default)
- `cfg['meta'] = {'titles': {lang: text}, 'icon': (tiles, palette), 'internal': str}` (only changed fields)
- `patch` refuses a ROM that already has the cave filled ("already patched or unsupported ROM").

### 3.3 Currency conversion (current behaviour, real conversion; statically verified, not played)
- Currency tab: the info line gives the yen threshold above which T2 prices are capped (`T2_MAX * scale > T2_MASK`).
- Verification done without the game: diff of the patched ROM (only intended bytes change), wrapper disassembly, cents thunk emulated at rate 0.01, thunk arithmetic at all scales, `pyflakes`, headless checkbox logic. Details: section 12.
- **Data is converted**: `T1` (255 rows, price = low 24 bits of word0) and `T2` (300 rows, price = low 23 bits, bit 23 kept) are rewritten with `convert_tables`. Overflow is capped and logged.
- **Island income** (ov82 call at 0x2149844 to `0x2149E1C`) goes through a wrapper in the ARM9 cave: `str lr` / `bl orig` / `ldr lr` / `b thunk` / `bx lr`.
- **Display modes:** The "Round to whole units" checkbox was removed; cents mode is the only behavior. Wallet/shop amounts show cents via the cents thunk (`CENTS`), item lists show whole units rounded. `whole` remains in project config for compatibility.
- **Cents availability:** cents needs `rate * 100 * 9999999 < 2**32`, else `cents_thunk` raises "cents not available for this currency". That refuses KRW, IDR, VND and other currencies where 1 JPY is more than about 4.29 units. No whole-unit fallback.
- **Symbol selection:** Uses the shared character palette (same widget as Keyboard) with group "Symbols" opened first, search by character/code/name, preview rendered as the game draws it, and a "Default symbol" button. The symbol entry was replaced by the palette search. The list of currencies is filtered to those present in `SYMBOL`.
- **Font fallback:** For symbols not present in all three game fonts, the patch draws them using `symbol_spec` (letter + bar pattern) via the glyph substitution logic. Each currency is assigned a symbol that the fonts can handle; accented letters fall back to base letters where needed.
- Symbol: `SYMBOL[code]` = font glyph, else a font letter with bars, else a font letter. Replaces the `FFE5` glyph in 3 NFTR fonts, the `円` literal at `YEN_TEXT` (0x2114FD0 → FFE5), and the baked 7x7 `円` pictures in `GLYPHS` (skipped for yen).

### 3.4 Icon import (current behaviour)
- `read_pixels`: loads PNG/GIF via Tk PhotoImage. If larger than 32px it is subsampled by `ceil(max/32)` first (speed). Then `fit32(w, h, pixels)`: nearest-neighbour fit into 32x32, centred, transparent padding.
- `quantize(pixels)`: 15 most common colours (5 bits per channel, BGR555 packing) + index 0 = transparent. Pixels with alpha < 128 are transparent. Returns 512 bytes of tiles (4bpp, 8x8 tiles, 4x4 grid) and a 16-entry palette.
- Verified in Tk with PPM files of 48x24 and 400x300.

### 3.5 Meta/banner details (verified in code)
- Banner offset: `u32` at header `0x68`.
- Icon tiles at banner `+0x20` (512 bytes); palette at `+0x220` (16 BGR555 entries).
- Titles at `+0x240 + 0x100 * lang_index`, UTF-16LE, max 0x100 bytes each.
- Banner CRC16s: `+2` over `0x20..0x840`; `+4` over `..0x940` (version ≥ 2); `+6` over `..0xA40` (version ≥ 3). Recomputed in `meta()`.
- Header title 12 bytes at offset 0 (internal name). Header CRC16 at `0x15E` (not recomputed by the toolkit as far as the notes show; **check this** if the game rejects the ROM).
- Load order bug fixed: `load_meta` inserts titles before the internal-name trace fires.

### 3.6 Keyboard internals (verified in the earlier session, user-confirmed working)
- Tab slot array at ARM9 `KB_MAP = 0x20B7AD4` (5 words; `[0,1,2,3,4]` originally).
- Kind map is built by `str` at `KB_STORES = (0x2081BF4, 0x2081BF8, 0x2081BFC)`; the patch replaces those with NOPs (`0xE1A00000`).
- Opening tab: `KB_START = 0x2081AA4`, `mov r0,#1` → `mov r0,#KB_KIND[first]` (`0xE3A00000 | kind`).
- `KB_KIND = {Japanese:1, QWERTY:0, Accents:2, Symbols:3, Emojis:4}`; `KB_ICON = {Japanese:5, QWERTY:0, Accents:6, Symbols:7, Emojis:8}` (icon blocks swapped in `Cmn/Kbd/SoftKeyboard_LZ.bin`, NARC sub 2, 128-byte blocks).
- Default-kind callers pass kind 0 (`0x2082E54(kbd, 0, 0)`), so the remap works at the kind-table level.

### 3.7 Currency code internals (verified)
- ARM9 is stored uncompressed (`compressed_static_end = 0`). Overlay table and overlays that overlap are moved to the ROM tail (`Rom.set_arm9`). New files are LZ10 (`lz10c`, displacement ≥ 2).
- Money display call sites are in `SITES` (ARM9 + overlays 68, 72, 75, 83, 84, 85, 100). Each `BL` is redirected to a thunk in the ARM9 zero-filled `CAVE`.
- Thunk = fixed-point multiply (`umull`), then tail-jump to the formatter. Cents thunk = embedded machine code (`CENTS`, checked by unicorn emulation and melonDS), fixed-point 2^-23 rate, magic /100, writes `I.FF`.
- Overlay ID → ARM9 overlay RAM address: **all overlays load at 0x21495E0** (shared region, loaded one at a time). Use that base when disassembling overlays.

### 3.8 Tools in scratchpad (not in the repo)
- `romlib.py`: `load_rom()`, `blobs(rom)` → `{'ARM9': (0x2000000, data), 'ovNN': (0x21495E0, data, fid)}`. Imports `blz`, `lz10`, `u16`, `u32` from the toolkit.
- `ctx.py <name> <addr_hex> <before> <after>`: disassemble around an address (capstone).
- `fn.py <name> <addr_hex> <n>`: disassemble n instructions.
- `writers.py <offset_hex>`: list stores `str ..., [rX, #offset]` across all blobs.
- `setmoney_sites.py`: list direct `BL 0x202D1EC` callers.
- `st50.py`: stores to offset 0x50 (wallet candidate scan).
- `bmgcheck.py`, `bmgdeep.py`: BMG validators (see section 5).
- `kbstate.py` / `ramdump.py`: passive RAM dump. Live RAM is the **second** match in `ram_fresh.bin`.
- `melon-run/`: portable melonDS, ROMs `kx1..kx6`, `fresh.nds`, save files, RAM dumps (`ram_fresh.bin`).
- Note: `ui.ps1` / `kbrun.ps1` are melonDS UI automation. **Do not use** (the user rejected them).

## 4. Money research (the open problem)

Goal the user set: make the currency conversion **real** (convert stored prices and money), not display-only. The user first said "convert real prices and money in the data; existing saves are not supported". After seeing the cents limit they accepted display-only with cents. **Decide with the user** whether to pursue real conversion. Until then, the code is display-only.

### 4.1 Wallet
- Wallet is a `u32` at money struct `+0x50`. Runtime address **0x2329CE4**, struct base 0x2329C94.
- Reached through a global holder pointer in ARM9 at **0x2122FF4** (`ldr r0, [pc,#...]` then `[r0, #0x50]`).
- All writes go through `SetMoney` at **0x202D1EC** (clamps the value).
- Wallet value after the intro on a fresh save: **6800** (read from RAM).

### 4.2 Wallet write paths found
- **Shop screen (ov83)**: copies the wallet into a working field at `[r4 + 0x19000 + 0x4A4]` (store at 0x21496BC). Buy: subtract a price (0x214A6E4). Add: add an amount (0x214A7F8). Clamp to 0. Write back with `SetMoney` at 0x214B610 (reads `[r0+0x4A4]`).
- **Mii gift (ov75)**: copies the wallet into `[r4 + 0x30000 + 0x9B4]` (0x2149DBC). `SetMoney` at 0x214B8D0 reads the same field.
- **Income (ov82)**: `r0 = 0x2149E1C(r6)` (amount), then `wallet = holder+0x50 + amount`, `SetMoney` at 0x2149858.
- A direct-`BL` scan found only these three `SetMoney` callers (ov75, ov82, ov83). An earlier session mentioned 8 sites; that figure is not confirmed here. Indirect calls were not scanned.
- Possible extra write: ov6 stores `[sl + 0x5000 + 0x9B4]` (0x2149C0C). Not traced. **UNVERIFIED**.

### 4.3 Price helper
- `0x20AA88C`: a dispatcher that calls a method of an object through its vtable. Mode word at `[r0 + 0xA000 + 0xFA4]` (0 → vtable slot +8, 1 → slot +0xC). Arguments from `[+0xFAC]` and `[+0xFB0]`. Used for the amount in ov83. **The target object is not traced.** Likely where prices are computed from tables, but UNVERIFIED.

### 4.4 Price tables
- **T1** at ARM9 **0x20F5AD8**: 255 rows, stride 20 bytes, price = `word0 & 0xFFFFFF`.
- **T2** at ARM9 **0x20F3BBC**: about 300 rows, stride 20 bytes, price = `word0 & 0x7FFFFF`. Category not confirmed.
- Not yet checked whether the helper reads T1/T2.

### 4.5 Not money
- ov96 `0x214A43C`: a 12-bit field × 60 added to 64-bit counters (`+0x95C/+0x960` and `+0x4A0/+0x4A4`). Time, not money.

### 4.6 Tutorial payouts (the start money): NOT FOUND
- The 6800 is not a boot value. The user explained: money is given during the tutorial as you go through it.
- Searched and not found: a `u32` 6800 literal in ARM9 and overlays, a 6800 literal in NitroFS data (decompressed, 0 hits), an `mov #0x1a00 / add #0x90` pair, an init store of 6800.
- ov109 `0x214AEAC`: a store of r2 (0) into `[r1+0x50]`. It zeroes, it is not the wallet.
- Probable path: the intro script or an event calls the ov83 add path (helper 0x20AA88C with a positive value) or the ov82 income path. **OPEN.**

### 4.7 Other money not converted
- Numbers written inside BMG texts ("2100 yens", the `[1401:..] yen(s)` tag).
- Job wages, costume/interior/goods shops, sell price (`YEN_TEXT`).
- Untested in melonDS: costume/interior/goods shops, Mii gift, sell price. Tested: island wallet, food shop list/catalog/purchase.

## 5. BMG knowledge

Full notes are in `BMGs/BMG.md` (committed). Summary:

- Container `MESGbmg1`: header 0x20 bytes. `u32` file size at 0x08, `u32` section count at 0x0C, encoding byte at 0x10 (`2` = UTF-16 in all files).
- Sections chain from 0x20 to EOF: 4-byte tag, `u32` size (includes its 8-byte header). Required: `INF1`, `DAT1`, `MID1`. MID1 count = INF1 count.
- `INF1`: `u16` count at +8, `u16` entry size at +0xA (12). Entry = `u32` offset into DAT1 data (message at `DAT1 + 8 + offset`).
- `DAT1`: UTF-16LE strings ending with `0x0000`.
- **Alignment rule**: every section start and size must be a multiple of 4. A `DAT1` size not multiple of 4 misaligns `MID1` → ARM9 data abort (melonDS, DS). This crashed the game.
- Tag (UTF-16 file): `1A 00` | size (1, total length incl. escape, 8 in these files) | group (1 byte) | type (2 bytes LE) | args. The encoder is in `build-bmg.js` (`encodeToken`).
- Fixes: `651980a` (bmge: DAT1 padding, regex `]`, tag size byte = args+3 → total length). `4426fa0` (+2 zero bytes on `etc`, `item`, `room`).
- Current status of the 7 files in `BMGs/test/`: alignment and structure OK (all checks pass).
- Oddities from original data, not regressions: `tmd_etc` has 20 duplicated INF1 offsets and 21 overlaps (empty messages pointing at offset 0); `tmd_contents` 1 overlap. Same in the first committed version.
- `tmd_etc`: tag group `FF`, type `000A` existed in the first committed version and is gone now. **Check if intended.**
- Longest message per file is unchanged vs the first version except small differences in `costume`, `etc`, `explain`, `item`, `room` from translation edits.
- Not checked in this pass: the `BMGs/done/` and `BMGs/todo/` folders.
- A beta tester crashed. First guess was an old copy of `etc`, `item` or `room`. **Superseded by section 8**: the BMGs inside the tester's ROM are truncated.

Validators (scratchpad): `bmgcheck.py` checks magic, file size, chain, alignment, INF1 offsets inside DAT1, terminators, tag size, MID1 count. Run with `python bmgcheck.py [files]`.

## 6. Open items and next steps (in priority order)

1. **Crash**: see section 8. Confirm with the tester using a ROM built by `tools/bmgrom.py` or the toolkit BMG tab, after `bmgrom.py check` says all 7 are OK.
2. **Play-test the real conversion in melonDS** (the user does the clicks; the assistant only reads RAM passively if asked). Check in this order: the start wallet (tutorial), one shop price in cents and in whole units, the island income after a day, a KRW patch (whole units, capped T2 item), a keyboard reorder, a custom icon, a title change. Static checks are done (see section 12); nothing has run in the game yet.
3. **Real conversion status**: T1, T2 and the ov82 income are converted. Still open: the tutorial payouts (section 4.6), the helper `0x20AA88C` target object, and other readers of T1/T2 that might use the price as a yen constant. Decide after the play-test whether the remaining yen paths must be converted.
4. **Find the tutorial payout source** (section 4.6). Then trace the helper `0x20AA88C` target object and whether T1/T2 feed it.
4b. **BMG texts with yen** (4 messages, see 5 and section 12) keep "yen" and yen figures. They need a decision: rewrite them, or accept.
5. **Check the header CRC16 at `0x15E`** after banner/title edits (not confirmed by the toolkit).
6. Check `BMGs/done/` and `BMGs/todo/` with `bmgcheck.py`.
7. Review the `FF:000A` tag removed from `tmd_etc`.
8. Money not converted: job wages, costume/interior/goods shops if they do not read T1/T2, sell price, and the yen figures in BMG texts (4b).
9. Visual check of the GUI after the cents-only change, the Apply-to-all button and the symbol single-character entry (only Tk-level checks were run).
10. **Final test round** (the user will say when): `test_toolkit.py` was not re-run after the speech and project changes and has no test yet for the new code (speech helpers `kana_text`, `speech_bytes`, `script_*`; `preset_read` and `preset_write` round trip; `project_dump` and `project_load` with `speech` and `source`; `bps_make(src, tgt)` with empty metadata). Then a GUI pass of every tab, the JP original ROM through `speech_check`, and in the game (the user clicks): replaced images, sounds, models and edited speech presets.
11. **3D models**: export and import for Blender, section 11, not implemented yet.
12. **Speech**: check in the game that an edited preset changes what the Miis say, and trace how the game picks a voice, an emotion and tags (10.2).

## 7. Known pitfalls from this work

- Local variable shadowing: a `code` variable shadowed the thunk bytes once and broke the symbol silently. Use distinct names.
- Edit scripts that write literal `\u25BC` vs `▼` mismatched; always assert before writing.
- Heredoc quoting breaks with long Python in bash; write scripts to files with the Write tool.
- Tk `PhotoImage.subsample` only takes integer factors; use nearest-neighbour fit for other sizes.
- `Entry` validation: a `validatecommand` with `%P` rejects keystrokes that make the value invalid, so a paste of several characters is also rejected.
- Banner title trace bug: insert titles before the internal name, or the trace overwrites them.
- The keyboard first attempt (swapping the A array) left the default on Japanese. The working fix remaps the kind table and NOPs the stores.
- The git rename of `tools/prices` required moving files individually (the directory was locked).

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
- Which tool truncated the files is **not proven**. The tester reports the same result with NSMBe and with Tinke, and the damage is not in the BMG files (BMGE output is valid). Always run the check below on any ROM before sending it.

### 8.2 What the savestates show (how to read a melonDS state)
- Layout: header `MELN`, then sections with 16 byte headers (4 char tag, u32 length, 8 zero bytes). `NDSG` starts at `0x10`; main RAM (4 MB, ARM9 address `0x02000000`) starts at file offset `0x24`. Find the CPU with the last `ARM9` + length `0xBC` section before `CP15`; the data is 47 words: word 0 and 1 header, R0..R15 = words 2..17, CPSR = word 18. Banked registers follow (FIQ 8 words, then SVC, ABT, IRQ, UND as SP, LR, SPSR).
- Both states are already crashed: CPSR mode `0x17` (abort), PC `0xFFFF0108` (BIOS handler), LR `0x202E1EC`. The faulting instruction is `ldrh r2, [r2]` at `0x202E1E4` in the message lookup function (it multiplies the id by 12, the INF1 entry size).
- r2 was loaded from `[r0 + 0x14]` of the BMG object: the pointer to MID1. It is NULL because MID1 is not in the (truncated) file.
- BMG objects live in an array of 0x18 byte entries (stride) near `0x2310874`: `[data, data, INF1, DAT1, ?, MID1]`. In the crashed state `item` and `explain` had MID1 = 0, `etc` and `common` had it filled. A healthy object has a non zero word 5.
- Old checks like "alignment crashed the game" were real for the unpadded files, but they are not what crashed 3.5.1.

### 8.3 Injection pitfalls found while fixing it (each one makes the game abort at boot)
1. The NARC **must keep its BTNF filename table** (copy the one from the original NARC). A NARC without names is not found by the loader.
2. LZ10 **must not use displacement 1** (runs of one byte). The game decompresses with a 16 bit write callback. `lz10c` in `toolkit.py` already uses displacement >= 2.
3. Header size, BTAF end, GMIF size and the LZ size field must all describe the real, full BMG.
- Evidence: a ROM injected with the first version of the injector (no names, displacement 1) aborted at boot even with a single BMG (`common`). After fixing both, all 7 BMGs injected boots in melonDS and no abort is reached. Which of the two fixes was the decisive one was not isolated (both were changed at once).

### 8.4 Tools added
- `tools/bmgrom.py` (stdlib only):
  - `python bmgrom.py check ROM.nds [BMGs/test]` prints, for each of the 7 BMGs, the problems found in the ROM copy (and in the folder files). Exit code 1 when something is wrong.
  - `python bmgrom.py inject ROM.nds BMGs/test OUT.nds` rebuilds the 7 NARCs (names kept, LZ10 displacement >= 2), writes them at the ROM tail, updates the FAT, the used size at `0x80` and the header CRC at `0x15E`, then runs `check`. Verified: all 7 inner files equal the repo files and every other file of the ROM is byte identical.
- `toolkit.py`, new **BMG tab** (all 24 game BMGs listed by their inner name): per file a Replace button (opens a .bmg, refuses invalid files) and a Cancel button, plus Replace from folder (matches by file name) and Cancel all. The ROM tab summary shows "BMG: N replaced". The patch step uses `bmg_replace` (same rules as 8.3). Functions: `bmg_problems`, `bmg_list`, `bmg_narc`, `bmg_replace`, `narc_files`, `narc_name`. Tests added in `test_toolkit.py`. The GUI itself was not exercised, only the functions on the real ROM (tkinter is not installed in the analysis sandbox).
- `toolkit.py`, **Export BPS patch / Apply BPS patch** buttons on the ROM tab (enabled once a ROM is open). Export runs the same patch as the Patch ROM button on the opened ROM, then writes a BPS patch (Flips format, spec by byuu) between the opened ROM and the result, and checks it by applying it again in memory. Anyone can then apply it with Flips on their own copy of the ROM, and no ROM is distributed. Apply takes a .bps, checks the source CRC32 and size, and saves the patched .nds. Functions `bps_make`, `bps_apply`, `vint`; test `test_bps`. The encoder is simple (equal runs as SourceRead, everything else as TargetRead, no SourceCopy/TargetCopy), so a patch with moved data is larger: a full patch (BMGs, currency, keyboard, meta) on the 3.5.1 ROM is about 2.2 MB. Verified with the real Flips 198 CLI on Léo's machine: it applies the patch and the output is byte identical to the toolkit output. The GUI buttons themselves were not exercised (no Tk in the sandbox). Since 2026-10-26 the exported patch carries no project data (9.1).
- Note: the toolkit always applies its currency step when patching (JPY default). Patching a ROM twice is refused ("already patched"), so keep an unpatched ROM as the input.

### 8.5 How to test a ROM without a GUI (what was done)
- `melonDS` and `desmume` are installed on Léo's Arch machine. The termigent shell needs `DISPLAY=:0` and `XAUTHORITY=/tmp/xauth_*` (find the file in `/tmp`).
- Start `melonDS ROM.nds`, wait about 40 seconds, send `shift+F1` to the window (savestate slot 1 is written next to the ROM as `NAME.ml1`), kill with `pkill -9 -x melonDS` (never `pkill -f melonDS`, it kills the shell itself; and always kill the previous instance, extra windows steal the key press).
- Parse the `.ml1` as in 8.2. Healthy: CPSR mode `0x1F` (system), PC in main RAM. Crashed: mode `0x17`, PC `0xFFFF0108`.
- At 40 seconds the game only loads `msg`, `etc` and `common`. The other BMGs are loaded later, so a boot test does **not** prove `item`, `contents`, `costume`, `room` and `explain` are read correctly.

### 8.6 Open items from this session
1. Play in melonDS and DeSmuME through the screens that read `item`, `contents`, `costume`, `room`, `explain` (shops, the item lists, the explanation screens) on a ROM built with `bmgrom.py inject` or the toolkit BMG tab. Passive check after each screen: take a savestate and verify that no BMG object has word 5 equal to 0.
2. Identify which tool truncates the NARC (NSMBe, Tinke or the build step used for 3.5.1). Until then, ship ROMs built with `bmgrom.py` or the toolkit and run `check`.
3. Make BMGE alone enough (Léo's goal): BMGE already writes valid BMGs. Option: add a NARC + LZ10 export to BMGE (rules in 8.3) so no external injector is needed, or keep the toolkit as the injector.
4. Run the GUI of the new BMG tab once on Léo's machine (layout, scrolling, Replace/Cancel).
5. `BMGs/BMG.md` section "Beta testers" is superseded by 8.1: the old copies were not the whole story.

## 9. Images tab and projects (2026-10-25, projects reworked 2026-10-26)

- Core (toolkit.py, before `symbol_pictures`): `png_read/png_write/png_write_indexed` (stdlib, indexed 1/2/4/8 and tRNS), `ncgr_info/nclr_colors/nscr_info`, `render_sheet`, `render_screen`, `encode_sheet`, `encode_screen`, `nearest`, `narc_set`, `img_items`, `images_apply`, `project_dump/project_load` (the `.tomods` format, 9.1), `bps_meta`. `bps_make(src, tgt, meta=b'')` still has a metadata argument, but the toolkit exports clean patches (9.1).
- Formats: NCGR RAHC tw/th int16 at +8/+10 (-1 = OBJ, use 16 per row), depth u32 at +12 (3 = 4bpp, 4 = 8bpp), size at +24, data at +32. NCLR colours BGR555 from +24, expanded with `<<3` (matches Tinke). NSCR cell = tile 10 bits, hflip 10, vflip 11, bank 12..15. Replaced NCGR keeps its length; the NARC is rebuilt in place and LZ10-compressed (`lz10c`, displacement >= 2).
- Index 0: opaque pixels avoid index 0 on ties (`nearest`), because palettes often duplicate colour 0 (SoftKeyboard has index 8 = index 0). Import compares rendered pixels with the original, so re-importing an unchanged export is not marked modified.
- Verified on the 3.5.1 ROM: 743 images found (scan about 6 s), sheet and screen round trips render identically for the first 200 (only 3 News screens reuse tiles with different pictures and are reported as clashes), a patched image reads back correctly, BPS with project metadata applies and its metadata reads back. GUI exercised on the host with real Tk: scan, select, export, replace, hover, modified filter, export BPS, open project.
- Not exercised: export/replace-folder, in-game look of a replaced image (no melonDS run yet), 8bpp images, Windows/macOS.
- Open: images stored in the ROM outside /Cmn /Job /News /Pht /Scn (Mdl, Msg) are not listed; NCER/NANR sprites are shown only as tile sheets.

### 9.1 Projects (.tomods) and clean BPS patches (2026-10-26)
- Why: projects used to be stored in the BPS metadata field, and Flips shows that field. The user wanted patches free of tool data and a separate file to come back to. Now **Export BPS patch writes a clean patch** (`bps_make(src, tgt)`, empty metadata) and the work in progress is a **`.tomods`** file: ROM tab, Save project (.tomods) and Open project (.tomods).
- Format (`project_dump`, `project_load`): the 8 bytes `TOMODS1:` followed by a zlib compressed JSON: `version` (1), `currency` (code, symbol, whole; the rate is the live one at restore time), `keyboard` (order), `meta` (titles, icon, internal name), `bmg` (by inner file name), `images`, `models`, `audio`, `speech` (preset name to script, see 10.2) and `source` (`crc32` and `name` of the ROM it was made from). Binary parts are zlib plus base64.
- Restore (`restore_project`): Open warns when the open ROM has another CRC32. Each stored item is checked against the open ROM (image: same file, same size and same header; model: same file and sub-file number, BMD0 magic; sound: the number exists; preset: the name exists; BMG: the inner name exists). Items that do not fit are skipped and listed in one warning.
- Older BPS files with a project in their metadata still open: Open project also accepts `*.bps` (`bps_meta`; the source CRC32 comes from the BPS footer). A BPS without project data offers to be applied as a plain patch.
- Exercised on 2026-10-26 with real Tk (Xvfb, Python 3.12, Tk 8.6) on the FR build 3.5.1: Save project, then Open project after Revert all, with the speech presets and the source CRC32 read back correctly. NOT exercised: Export BPS from the GUI after this change (the empty metadata is from reading the code), opening an older `.bps` project, opening a project made on another ROM, a project that holds images, models or audio.

## 10. Audio, speech and 3D models (2026-10-25; speech 2026-10-26)

Added to toolkit.py: Audio, Models and Speech tabs, `cfg['audio']`, `cfg['models']`, `cfg['speech']`, all stored in the `.tomods` project (9.1).

### 10.1 SDAT facts (verified on the ROM)
- `/sound_data.sdat` is a standard SDAT, 25,360,864 bytes: 135 SEQ, 52 SEQARC slots (26 archives, only SE_* sub-sequences), 141 BANK, ONE wave archive `WAVE_STATIC` (SWAR, file id 305, 592 waves, 7.4 MB, all IMA ADPCM, mostly 44100 Hz), 15 PLAYER, 119 GROUP, 3 STRM (`STRM_MINIGAME_SUCCEED`, `STRM_MINIGAME_FAILED`, `STRM_STAFF`).
- INFO records hold the file id in the low 24 bits (the high byte is a flag). SEQARC symbols are stored as pairs (name offset, sub-table offset).
- Every wave is referenced by at least one bank. SWAV header: type u8, loop u8, rate u16, time u16 (16756991 / rate), loop offset u16 (words), non-loop length u32 (words). For ADPCM the first word of the data is the predictor/index header and counts in the loop offset.
- The ROM has no spare room for the 25 MB SDAT (cartridge size 64 MiB, 7 MB free), so audio is patched in place and the SDAT may not grow. `wave_encode` output is zero padded to the old wave size when smaller, so no offset moves and the BPS patch stays tiny (about 7 KB differ for one wave). `sdat_rebuild` repacks only when something grew.
- The Audio tab lists every sample with the banks that use it and gives no bank any special treatment (a "Mii voice banks" filter existed for a day and was removed at the user's request; the Mii speech is a separate engine, 10.2).
- Proof that SWAR edits reach the game: a JP ROM with all 592 waves zeroed gives a constant DC level in melonDS (RMS about 260) instead of the title music (RMS 3300 to 5700). A recording method that works: `parec -d <default sink>.monitor` while melonDS runs; melonDS' own stream volume was 0 and had to be raised with `pactl set-sink-input-volume`.

### 10.2 Mii speech (Speech tab, 2026-10-26)

**What it is.** The Miis do not play recorded voices. The ARM9 holds Sharp's text to speech library, signature `[SDK+SHARP:SHTTS-1_2_0]` (SHTTS 1.2.0), which turns katakana text into 16 bit PCM at run time. An earlier version of this section concluded that the speech was code driven playback of samples from the SDAT, and the Audio tab got a "Mii voice banks" filter: that was wrong and the filter is gone. The BANK_MII_* banks (BASIC, TALK, STATUS, TOOL, DOOR, POSITION, POSE, EMOTION, MEAL, PHYSIOLOGIC, TOY, TRAINING, GAME, RELATION) and BANK_DIVITALK / BANK_SAIMIN are ordinary sound effects, and the Audio tab gives no bank any special treatment.
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
- Text: Shift-JIS bytes, katakana only, NUL terminated. Allowed marks: ＿ ／ ｜ ’ ． ！ ？ and the digits ２ ０ and ％ (prosody and numbers). Inline tags look like `<\Name>` or `<\Name=value>`. `speech_bytes` turns romaji and hiragana into katakana (`kana_text`, table `ROMAJI`) and refuses kanji and Latin text with a message; the tab shows the katakana it really sends.

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

**Preset table** (the engine's named scripts, the part the tab edits).
- 53 entries of 0x78 bytes: a 20 byte NUL padded name, then a 100 byte NUL padded script. Two identical copies in the ARM9, at file offsets 0xB7B94 and 0xF22D4 on the FR build (RAM 0x020B7B94 and 0x020F22D4), found by searching for `<\Emp` followed by NUL (`preset_tables`). `preset_write` writes into every copy. Whether the game reads both or only one is unknown, so both are patched.
- Entries 0 to 21 are text commands (`<\Emp`, `Dem`, `Spd`, `Pit`, `Vol`, `RPit`, `RPrm`, `RSpd`, `Pau`, `Lwp`, `Ring`, `Ecl`, `Ecg`, `Firl`, `Firg`, `Hsp`, `Cho`, `Echo`, `Fir`, `Acc`, `Prm`, `RVol`), 22 to 37 emotions (angry, business, calm, depressed, excited, falsetto, happy, loud, monotone, perky, quiet, sarcastic, scared, shout, tence, whisper), 38 to 49 voices (`<\Spk_` male, female, admale, adfemale, emale, efemale, chmale, chfemale, sisters, meimu, space, giant), 50 to 52 `Rst`, `Ptr`, `sing`.
- A script is lines that start with `#` and a letter: `#B4800` sets the pitch, `#S90` the speed. Letters are in the table above, plus `Q` (reset), `Z`, `E`, `D`, `p` (pause), `C`, `k` and `T` (transpose); the exact effect of Z, E, D, C and k was not studied. A value written `+n` or `+-n` is relative (letters B S V A P only). `script_check` enforces the ranges and the 99 byte limit.
- Tags in a text: `<\Name>` for voices, emotions and commands without a value, `<\Name=value>` when the script has an item with an empty or `+` value other than Q and Z (`speech_tags`). The Insert menu of the tab builds them.

**Running the engine without a console.** `ArmVm` (embedded in `toolkit.py` between `# ---- ARM interpreter (BEGIN)` and `(END)`; the engine code is the block after it) is a pure Python ARMv5 interpreter: basic blocks are translated to Python source and cached, flags are evaluated lazily, and addresses can be hooked (the audio callback). It is not a general emulator: it has what this engine uses and raises `Unsupported` otherwise. It runs at about 0.7x real time (slower than playback), so the tab computes in a thread, shows the seconds produced so far and plays the sound when done (`sp_speak`, `sp_poll`; Stop sets `Speaker.cancel` and the callback raises `ArmCancelled`; opening another ROM cancels and drops the job). `Speaker.speak(text, voice, emotion, props, presets)` resets the VM memory on each call, sets the voice (id 1), the emotion (id 2) and `props`, runs Speak and returns 11025 Hz mono int16 PCM. `presets` applies edited scripts to the copy of the ARM9 first, so the preview uses the same bytes the patch writes.

**In the toolkit.** `cfg['speech'] = {preset name: script}` (changed presets only); `patch()` calls `speech(arm9, cfg['speech'], log)` before `rom.set_arm9`; the ROM tab summary says "N preset(s) changed". `Speaker` is created the first time the Speech tab opens (`sp_load`). The tree groups are Voices, Emotions, Commands and Other, a dot marks a changed preset, Revert and Revert all undo. Fields: Pitch (B), Speed (S), Voice quality (X), Volume (V), Accent (A), Phrase accent (P), Echo delay (I), Echo gain (J), FIR delay (R), FIR gain (G), Ring (r), plus the raw script box; editing one updates the other. Speak takes the text box, the Voice and Emotion lists and the edited presets; Save WAV writes the last sound.

**Validation: what was and was not checked.**
- Instruction level: `vm_fuzz.py` and `vm_fuzz2.py` ran random instruction sequences on `ArmVm` and on Unicorn (another ARM emulator) and compared registers, flags and memory: 0 differences.
- Output level: the 1248 reference recordings of shtts-rust (`cases.tsv`: text, pitch, accent, phrase accent, volume, speed, fdepth, fdelay, edelay, spectral, edepth, ring) against `Speaker.speak(..., props=...)`. Earlier run: the 1102 cases without effects were bit exact. After the property id fix, the effect cases tried first (45) were exact, and the full re-run (`ref_full.py`, slow) was at 600 of 1248 cases, all exact, when this was written.
- GUI: the Speech tab was run with real Tk under Xvfb on the FR build: the engine loads (53 presets, 12 voices, 16 emotions), field and raw script editing, range refusal, Speak (thread, busy state, result), Stop, the message for unreadable text, Revert, Save project and Open project. Two bugs found that way were fixed (the Insert menu object, the thread result of a stale job). Playback was replaced by a stub in that test (it needs `afplay`, `paplay`, `aplay` or `ffplay`; `winsound` on Windows), and nobody listened to the sound.
- NOT checked: the JP original ROM (fingerprints), the table of a patched ROM in a GUI run, and above all **the game itself**: no melonDS or DeSmuME run has shown that an edited preset changes what a Mii says. Both table copies are patched on the assumption that the game uses them.

**OPEN for speech**: run `speech_check` on the JP original; listen on a real machine; patch one preset and check in melonDS that the Miis change; find where the Mii `voice` setting selects the engine voice and which tags and emotions the game really sends (BMG texts may hold `<\...>` tags, not searched); the effect of the letters Z, E, D, C, k.

### 10.3 Models
- Every file in `/Mdl` is an LZ10 NARC. 1278 BMD0 files, 3717 textures, formats seen: 16 colours (2703), 256 colours (559), A5I3 (371), A3I5 (69), 4 colours (9), 16 bit (6), no 4x4 compressed in this ROM. Other sub-files are BCA0, BTP0, BTA0, BMA0, APS and raw palettes (`e0 7f ff 03`, not decoded).
- TEX0 (offsets relative to the block): texture data size/8 at +0x0C, texture info dictionary at +0x0E, texture data at +0x14, compressed data +0x24, compressed info +0x28, palette size/8 at +0x30, palette dictionary +0x34, palette data +0x38. Dictionary: rev, count, size, then header (8), a (count+1) x 4 byte tree, unit size and total, entries, 16 byte names. Texture entry: offset/8 u16, param u16 (width = 8 << (p>>4 & 7), height = 8 << (p>>7 & 7), format = p>>10 & 7, colour 0 transparent = bit 13). Palette entry: offset/8 u16. Palette of texture `x` is named `x_pl`.
- Checked: render then encode then render is identical for all 3717 textures. Texture replacement keeps the file length. Geometry (MDL0) is not parsed yet: the plan is in section 11.
- Not exercised: how a replaced texture or sound looks or sounds in game, 4x4 compressed import, models with raw palette sub-files.

## 11. 3D models: export and import for Blender (decided 2026-10-26, NOT implemented yet)

Decision of the user: the toolkit does not edit geometry itself. The Models tab must export a model to a format Blender opens (OBJ, MTL and PNG textures) and import the modified file back into the patch. Facts and plan to build on:
- Container: every file of `/Mdl` is an LZ10 NARC; 1278 BMD0 files (10.3). A BMD0 has the blocks MDL0 (geometry) and TEX0 (textures, already read and written by `bmd_textures`, `tex_render`, `tex_encode`).
- MDL0 (NitroSystem) holds a dictionary of models; each model has an info block (SBC offset, material and shape offsets, position and scale parameters, vertex, polygon, triangle and quad counts, bounding box), node transforms (SRT with flags), materials (texture and palette references, polygon attributes), shapes (GX display lists) and the SBC command stream that draws shapes with matrix stack operations. Export has to walk the SBC stream, track the matrix stack, run each display list (BEGIN_VTXS, VTX_16, VTX_10, VTX_XY, VTX_XZ, VTX_YZ, VTX_DIFF, NORMAL, TEXCOORD, COLOR, MTX commands) and write triangles, quads and strips in model space with UVs and normals.
- Import: rebuild the display lists, update the counts and the bounding box in the model info, rebuild MDL0 and BMD0 and store the model in the NARC. The size changes, so the NARC must be rebuilt at a new size: `narc_set` currently forces the old size, and `Rom.put_file` appends to the ROM tail, so growth is possible (the cartridge has about 7 MB free).
- Animations (BCA0, BTA0, BTP0, BMA0) refer to nodes and materials by index or name. Import therefore keeps nodes and materials as they are and only replaces the shape geometry.
- To check before trusting it: parse all 1278 BMD0 of the ROM (the SBC stream ends with a return, indices are in range, display list vertex counts equal the header counts, node rotations are orthonormal), then export, import and export again and compare the geometry within the GX quantisation. After that the user looks at it in Blender and in the game.

## 12. Currency work: money map and verification status (moved from the deleted toolkit README, written 2026-10-25)

The text below was the "Finding more sites", "Money map", "Not converted" and "Verification status" parts of `tools/toolkit/README.md`. Parts of it overlap sections 3 and 4.

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

### Not converted

Numbers written inside the BMG texts (see "Verification status"), job wages, and untested screens: costume/interior/goods shops, sell price (`YEN_TEXT`). Tested in melonDS before the real conversion: island wallet, food shop list/catalog/purchase.

### Verification status

Checked without the game (static, offline, or headless):
- Patch output diffed against the original ROM. Only the intended bytes change: T1/T2 price fields, the cave (cents thunks in cents mode, income wrapper always), the 4 ARM9 display sites and the overlay display sites (cents mode only), the `YEN_TEXT` glyph, the overlay 82 call at `0x2149844`, and the `compressed_static_end` field.
- Income wrapper disassembled: `push {r3, lr}`, `bl 0x2149E1C`, `pop {r3, lr}`, `b` thunk, `bx lr`. The 8-byte stack push keeps alignment. `0x2149E1C` has one caller in overlay 82 (`0x2149844`). Overlay 24 calls the same address, but it runs its own code there.
- Cents display thunk at rate `0.01`: emulated (unicorn), exact for stored values 0..9999999, including the cap value.
- Fixed-point thunk arithmetic for scales 0.01 to 920: within 1 of the reference rounding.
- Table rows: T1 0..254 and T2 0..299 are the valid rows; the bytes after them are unrelated data.
- Blob lengths and thunk addresses are 4-byte aligned (CENTS = 248 bytes).
- Wallet cap: `SetMoney` clamps to 9999999 (literal read from the ROM).
- Python: `pyflakes` clean; `test_toolkit.py` passes; the currency tab's rounding checkbox checked headlessly for JPY, EUR, KRW, ARS, USD.

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
