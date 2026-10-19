# Handoff: Tomodachi Collection (DS) FR fan translation

Written so another AI or developer can continue without the previous chat. Everything here was either verified in the code, in git history, or in the ROM. Items marked **UNVERIFIED** or **OPEN** are not settled.

---

## 1. Where things are

| What | Path |
|---|---|
| Translation repo (main branch) | `C:\Users\gigabyte\Documents\GitHub\Tomodachi-Collection-FR-Translation` |
| Toolkit (GUI + patcher) | `tools/toolkit/toolkit.py`, `tools/toolkit/test_toolkit.py`, `tools/toolkit/README.md` |
| BMG notes (committed) | `BMGs/BMG.md` |
| BMG files in use | `BMGs/test/*_msg_JP.bmg` (7 files) |
| bmge project (BMG editor, `build-bmg.js`) | `C:\Users\gigabyte\Documents\GitHub\L-Dev31.github.io\projects\demos\bmge` |
| Scratchpad (analysis scripts, melonDS, RAM dumps) | `C:\Users\gigabyte\AppData\Local\Temp\claude\C--Users-gigabyte-Documents-GitHub-L-Dev31-github-io-projects-demos-bmge\2c651e32-8b24-4ebe-b9f3-e5bc6c836fa7\scratchpad` |
| Test ROM used by the scripts | `C:/Users/gigabyte/Downloads/tomodachi collection fr2_UN seul BGM modifié.nds` (path in `scratchpad/romlib.py`) |
| This handoff | `HANDOFF.md` at the root of the translation repo (**not committed**) |

Git state at the time of writing:
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

## 3. Toolkit ("Tomodachi Location Toolkit")

Run: `python toolkit.py`. Tkinter, stdlib only. Tests: `python test_toolkit.py` (prints `ok`). Renamed from `tools/prices/` in git.

### 3.1 Tabs (in order)
1. **ROM**: Open ROM (refuses non-Tomodachi ROMs), banner preview (32x32 from the ROM banner), file name/folder/size, a "Will be applied" summary (Currency, Keyboard), Patch ROM button. Other tabs are locked until a ROM is loaded.
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
- Verification done without the game: diff of the patched ROM (only intended bytes change), wrapper disassembly, cents thunk emulated at rate 0.01, thunk arithmetic at all scales, `pyflakes`, headless checkbox logic. Details: `tools/toolkit/README.md`, "Verification status".
- **Data is converted**: `T1` (255 rows, price = low 24 bits of word0) and `T2` (300 rows, price = low 23 bits, bit 23 kept) are rewritten with `convert_tables`. Overflow is capped and logged.
- **Island income** (ov82 call at 0x2149844 to `0x2149E1C`) goes through a wrapper in the ARM9 cave: `str lr` / `bl orig` / `ldr lr` / `b thunk` / `bx lr`.
- **Whole mode** (checkbox checked, forced for `WHOLE` codes and for `rate*100*T2_MAX > T2_MASK`): no display hooks, scale = rate. **Cents mode**: `FMT` sites use `cents_thunk` at rate 0.01, `PLAIN` sites use `thunk` at rate 0.01, scale = rate*100.
- Not converted: tutorial start money (source unknown), job wages, shops not reading T1/T2. Old display-only rules are gone.
- Earlier text (kept for reference, now superseded): game money stayed in yen internally, only the display was converted.
- Wallet and shop purchase amounts (formatter `FMT` 0x20364E0) **always** show cents (e.g. `2.26`) through the cents thunk (`CENTS`, `cents_thunk`).
- Item lists (formatter `PLAIN` 0x20363A8) show whole units `round(yen * rate)`, minimum 1, because their cell is too narrow for a decimal.
- The "Round to whole units" checkbox was **removed** by the user's request. Cents is the only mode.
- **Consequence:** cents needs `rate * 100 * 9999999 < 2**32`, else `cents_thunk` raises "cents not available for this currency". That refuses KRW, IDR, VND and other currencies where 1 JPY is more than about 4.29 units. There is no whole-unit fallback now. The user was told and has not yet decided otherwise.
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

### 4.6 Tutorial payouts (the start money) — NOT FOUND
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
- A beta tester crashed. Likely cause: an old copy of `etc`, `item` or `room` from before `4426fa0`. **Not confirmed** with the tester.

Validators (scratchpad): `bmgcheck.py` checks magic, file size, chain, alignment, INF1 offsets inside DAT1, terminators, tag size, MID1 count. Run with `python bmgcheck.py [files]`.

## 6. Open items and next steps (in priority order)

1. **Confirm the crash fix with the beta tester**: current `etc`, `item`, `room` files (from `4426fa0`).
2. **Play-test the real conversion in melonDS** (the user does the clicks; the assistant only reads RAM passively if asked). Check in this order: the start wallet (tutorial), one shop price in cents and in whole units, the island income after a day, a KRW patch (whole units, capped T2 item), a keyboard reorder, a custom icon, a title change. Static checks are done (see `tools/toolkit/README.md`, "Verification status"); nothing has run in the game yet.
3. **Real conversion status**: T1, T2 and the ov82 income are converted. Still open: the tutorial payouts (section 4.6), the helper `0x20AA88C` target object, and other readers of T1/T2 that might use the price as a yen constant. Decide after the play-test whether the remaining yen paths must be converted.
4. **Find the tutorial payout source** (section 4.6). Then trace the helper `0x20AA88C` target object and whether T1/T2 feed it.
4b. **BMG texts with yen** (4 messages, see 5 and `tools/toolkit/README.md`) keep "yen" and yen figures. They need a decision: rewrite them, or accept.
5. **Check the header CRC16 at `0x15E`** after banner/title edits (not confirmed by the toolkit).
6. Check `BMGs/done/` and `BMGs/todo/` with `bmgcheck.py`.
7. Review the `FF:000A` tag removed from `tmd_etc`.
8. Money not converted: job wages, costume/interior/goods shops if they do not read T1/T2, sell price, and the yen figures in BMG texts (4b).
9. Visual check of the GUI after the cents-only change, the Apply-to-all button and the symbol single-character entry (only Tk-level checks were run).

## 7. Known pitfalls from this work

- Local variable shadowing: a `code` variable shadowed the thunk bytes once and broke the symbol silently. Use distinct names.
- Edit scripts that write literal `\u25BC` vs `▼` mismatched; always assert before writing.
- Heredoc quoting breaks with long Python in bash; write scripts to files with the Write tool.
- Tk `PhotoImage.subsample` only takes integer factors; use nearest-neighbour fit for other sizes.
- `Entry` validation: a `validatecommand` with `%P` rejects keystrokes that make the value invalid, so a paste of several characters is also rejected.
- Banner title trace bug: insert titles before the internal name, or the trace overwrites them.
- The keyboard first attempt (swapping the A array) left the default on Japanese. The working fix remaps the kind table and NOPs the stores.
- The git rename of `tools/prices` required moving files individually (the directory was locked).
