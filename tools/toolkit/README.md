# Tomodachi Location Toolkit

`python toolkit.py`: Open ROM, pick a currency code (open.er-api.com, JPY base), Patch ROM, save a new `.nds`. Every code of the API is supported. Stdlib only. Needs the French/JP ROM with unmodified code (re-patching is refused).

## How it works

Game money stays in yen internally. Only the display is converted. Wallet and shop purchase amounts always show cents (`2.26`). Item lists stay in whole units (`round(yen * rate)`, minimum 1) because their cell is too narrow for a decimal.
Cents need `rate * 100 * 9999999 < 2**32`, otherwise the tool refuses the currency (e.g. KRW, IDR, VND). There is no whole-unit fallback.

- ARM9 is stored uncompressed (`compressed_static_end = 0`), overlay table and files that overlap are moved to the ROM end (`Rom.set_arm9`).
- Two number formatters draw money: `0x20364E0` (with commas, wallets, totals) and `0x20363A8` (plain digits, list prices; also used for counts). `SITES` lists only the money call sites (ARM9 + overlays 68/72/75/83/84/85/100). Each `BL` is redirected to a thunk in a zero-filled ARM9 cave (`CAVE`) that converts `r0` with a fixed-point multiply (`umull`) then tail-jumps to the formatter.
- Patched overlays are stored uncompressed, FAT re-pointed to the ROM end.
- Dropdown: `CODE  Name`. Symbol field: default from `SYMBOL[code]`, any single character overrides it (`Reset` restores the default; a character missing from a font falls back to the letter).
- Symbol: `SYMBOL[code]` = font glyph (`$ £ ¥ € ƒ`), else a font letter with bars (`₩ ₹ ₽ ₺ ₫ ₱ ₦ ₡ ₲ ₭ ₮ ₸ ₵ ₼ ₾ ₪ ₴`, approximate), else a font letter (`K`, `F`, ...). Every API code has one. It replaces the `FFE5` glyph in the 3 fonts, the `円` literal at `YEN_TEXT`, and the baked 7x7 `円` pictures in `GLYPHS` (skipped for yen).
- New files are LZ10 (`lz10c`, displacement >= 2 for VRAM).
- Cents thunk (`CENTS`, fixed-point 2^-23 rate, magic-number /100): calls the formatter with the integer part, then rewrites the buffer to `I.FF` (+ yen). Machine code is embedded; it was checked by emulation (unicorn) and in melonDS.

## Finding more sites

Disassemble the ARM9/overlays, list `BL 0x20364E0` / `BL 0x20363A8` callers, add the money ones to `SITES`. Find baked yen pictures by scanning NCGR tiles for the `YEN` bitmap.

## Money map

The wallet is a u32 at money struct `+0x50` (runtime `0x2329CE4`, struct base `0x2329C94`), reached through the global holder pointer at ARM9 `0x2122FF4`. Every wallet write goes through `SetMoney` (`0x202D1EC`), which clamps the value. Overlays share one RAM address (`0x21495E0`) and are loaded one at a time.

| Where | What | Status |
|---|---|---|
| ARM9 `0x20F5AD8` (T1) | Item price table, 255 rows of 20 bytes, price = word0 & 0xFFFFFF | located, not converted |
| ARM9 `0x20F3BBC` (T2) | ~300 rows of 20 bytes, price = word0 & 0x7FFFFF | located, category not confirmed |
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

Converting for real means changing the stored values (price fields, the amounts in the helper and ov82, the tutorial payouts) instead of only the display. All wallet writes pass through `SetMoney`, so it is the one place to check every change.

## Not converted

Numbers written inside the BMG texts (e.g. "2100 yens", `[1401:..] yen(s)` tag), job wages, and untested screens: costume/interior/goods shops, sell price (`YEN_TEXT`). Tested in melonDS: island wallet, food shop list/catalog/purchase.

## Keyboard

Dragging the tabs with the arrows sets the tab order (applied only when it differs from the default) of the soft keyboard (`Japanese`, `QWERTY`, `Accents`, `Symbols`, `Emojis`). The tab icons are the game's own sprites, read from `Cmn/Kbd/SoftKeyboard_LZ.bin` (`kb_pixels`). The first tab is the one shown when the keyboard opens.
- Tab slot map: 5 words at `KB_MAP` (ARM9 0x20B7AD4), read by the tab setup code.
- Opening tab: `KB_START` (`mov r0, #kind`), kind = `KB_KIND[first]`.
- Icon blocks swapped in the keyboard sprite bank (`KB_ICON`).
- Preview colours come from the first palette of that NARC; they are approximate, the game's own tab state drives the real look.

## Meta

Edits the ROM banner (`u32` at header `0x68`): one title per language (`LANGS`, UTF-16, 3 lines), the 32x32 icon (`fit32`: any PNG/GIF size, nearest sampling, centred with transparent padding; then `quantize`: 15 colours + transparency), and the 12-character internal name in the header. Banner CRCs are recomputed in `meta`.

