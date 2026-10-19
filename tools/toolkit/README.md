# Tomodachi Location Toolkit

`python toolkit.py`: Open ROM, pick a currency code (open.er-api.com, JPY base), Patch ROM, save a new `.nds`. Every code of the API is supported. Stdlib only. Needs the French/JP ROM with unmodified code (re-patching is refused).

## How it works

The conversion is real: the prices in the data are rewritten in the new currency, not only displayed.
- Prices: the price field of every row of `T1` (255 rows, low 24 bits) and `T2` (300 rows, low 23 bits, bit 23 kept) is replaced by `round(yen * scale)`, minimum 1 for non-zero prices. Values over the field maximum are capped and logged.
- Island income: the call to `0x2149E1C` in overlay 82 goes through a wrapper that converts its result (`thunk`).
- Scale: `rate` in whole mode, `rate * 100` with cents.
- Whole mode: `Round prices to whole units` is checked. It is forced on and locked for codes in `WHOLE` (ISO 4217 zero-decimal codes, plus IDR) and for codes where `rate * 100 * T2_MAX > T2_MASK`, which would overflow the field. The summary line states the mode.
- Cents mode: wallet and shop amounts show cents (`2.26`) through the cents thunk with rate `0.01`. Item lists show `round(cents / 100)` whole units because their cell is too narrow for a decimal.
- Not converted yet: the tutorial's start money, job wages, and any shop that does not read `T1`/`T2`. Existing saves are not supported. See "Verification status".

- ARM9 is stored uncompressed (`compressed_static_end = 0`, the field at `MARK - 8`, zeroed on purpose), overlay table and files that overlap are moved to the ROM end (`Rom.set_arm9`).
- Cents mode only: two number formatters draw money: `0x20364E0` (with commas, wallets, totals) and `0x20363A8` (plain digits, list prices; also used for counts). `SITES` lists only the money call sites (ARM9 + overlays 68/72/75/83/84/85/100). Each `BL` is redirected to a thunk in a zero-filled ARM9 cave (`CAVE`) that converts `r0` with a fixed-point multiply (`umull`) then tail-jumps to the formatter. Whole mode has no display hooks: the stored values are already whole units.
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

## Not converted

Numbers written inside the BMG texts (see "Verification status"), job wages, and untested screens: costume/interior/goods shops, sell price (`YEN_TEXT`). Tested in melonDS before the real conversion: island wallet, food shop list/catalog/purchase.

## Verification status

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

## Keyboard

Dragging the tabs with the arrows sets the tab order (applied only when it differs from the default) of the soft keyboard (`Japanese`, `QWERTY`, `Accents`, `Symbols`, `Emojis`). The tab icons are the game's own sprites, read from `Cmn/Kbd/SoftKeyboard_LZ.bin` (`kb_pixels`). The first tab is the one shown when the keyboard opens.
- Tab slot map: 5 words at `KB_MAP` (ARM9 0x20B7AD4), read by the tab setup code.
- Opening tab: `KB_START` (`mov r0, #kind`), kind = `KB_KIND[first]`.
- Icon blocks swapped in the keyboard sprite bank (`KB_ICON`).
- Preview colours come from the first palette of that NARC; they are approximate, the game's own tab state drives the real look.

## Meta

Edits the ROM banner (`u32` at header `0x68`): one title per language (`LANGS`, UTF-16, 3 lines), the 32x32 icon (`fit32`: any PNG/GIF size, nearest sampling, centred with transparent padding; then `quantize`: 15 colours + transparency), and the 12-character internal name in the header. Banner CRCs are recomputed in `meta`.

