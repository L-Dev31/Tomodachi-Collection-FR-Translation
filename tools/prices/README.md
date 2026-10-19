# Yen -> currency patcher

`python prices.py`: Open ROM, pick a currency code (open.er-api.com, JPY base), Patch ROM, save a new `.nds`. Every code of the API is supported. Stdlib only. Needs the French/JP ROM with unmodified code (re-patching is refused).

## How it works

Game money stays in yen internally. Only the display is converted: `round(yen * rate)`, minimum 1 for non-zero amounts (no cents, the game has none).

- ARM9 is stored uncompressed (`compressed_static_end = 0`), overlay table and files that overlap are moved to the ROM end (`Rom.set_arm9`).
- Two number formatters draw money: `0x20364E0` (with commas, wallets, totals) and `0x20363A8` (plain digits, list prices; also used for counts). `SITES` lists only the money call sites (ARM9 + overlays 68/72/75/83/84/85/100). Each `BL` is redirected to a thunk in a zero-filled ARM9 cave (`CAVE`) that converts `r0` with a fixed-point multiply (`umull`) then tail-jumps to the formatter.
- Patched overlays are stored uncompressed, FAT re-pointed to the ROM end.
- Symbol: `SYMBOL[code]` = font glyph (`$ £ ¥ € ƒ`), else a font letter with bars (`₩ ₹ ₽ ₺ ₫ ₱ ₦ ₡ ₲ ₭ ₮ ₸ ₵`, approximate), else generic `¤`. It replaces the `FFE5` glyph in the 3 fonts, the `円` literal at `YEN_TEXT`, and the baked 7x7 `円` pictures in `GLYPHS`.
- New files are LZ10 (`lz10c`, displacement >= 2 for VRAM).

## Finding more sites

Disassemble the ARM9/overlays, list `BL 0x20364E0` / `BL 0x20363A8` callers, add the money ones to `SITES`. Find baked yen pictures by scanning NCGR tiles for the `YEN` bitmap.

## Not converted

Numbers written inside the BMG texts (e.g. "2100 yens", `[1401:..] yen(s)` tag), job wages, and untested screens: costume/interior/goods shops, Mii gift (overlay 75), sell price (`YEN_TEXT`). Tested in melonDS: island wallet, food shop list/catalog/purchase.
