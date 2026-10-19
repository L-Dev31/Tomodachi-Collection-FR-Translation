# BMG notes

Message files of Tomodachi Collection (`MESGbmg1`). Read this before editing or rebuilding a `.bmg`.

## Files

- `BMGs/test/` holds the 7 files in use: `tmd_common`, `tmd_contents`, `tmd_costume`, `tmd_etc`, `tmd_explain`, `tmd_item`, `tmd_room` (`_msg_JP.bmg`).
- `BMGs/done/` and `BMGs/todo/` exist but were not checked in this note.
- Files are rebuilt with `projects/demos/bmge` (`js/build-bmg.js`). Always check the output before shipping it.

## Container layout

All integers are little-endian.

| Offset | Size | Content |
|---|---|---|
| `0x00` | 8 | Magic `MESGbmg1` |
| `0x08` | 4 | File size (must equal the real file length) |
| `0x0C` | 4 | Section count |
| `0x10` | 1 | Encoding (`2` = UTF-16 in every file here) |
| `0x20` | | First section |

Sections follow each other from `0x20`. Each one is a 4-byte tag, a `u32` size (includes its own 8-byte header), then data. The last section must end exactly at the end of the file.

Required sections: `INF1`, `DAT1`, `MID1`. The `MID1` count must equal the `INF1` count.

- `INF1`: `u16` message count at `+8`, `u16` entry size at `+0xA` (12 here). Each entry starts with a `u32` offset into `DAT1` data. A message starts at `DAT1 + 8 + offset`.
- `DAT1`: the message strings, UTF-16LE, each ended by `0x0000`.
- `MID1`: message ids.

## Alignment rule (this is what crashed the game)

Every section start and every section size must be a multiple of 4.

- A `DAT1` size that is not a multiple of 4 moves `MID1` off alignment. The game then faults in ARM9 (data abort, seen in melonDS and on DS).
- Original Nintendo files pad to 32 bytes. These files do not, so 4 is the real requirement.

## Tags (inside messages)

A tag is 8 bytes in UTF-16 files:

| Bytes | Content |
|---|---|
| `1A 00` | Escape |
| `size` (1) | Total tag length in bytes, escape included (8 for every tag here) |
| `group` (1) | Tag group |
| `type` (2, LE) | Tag type |
| args | `size - 6` bytes |

Tag kinds found in the 7 files: group `01` with types `0001`, `0002`, `0003`, `000A`, `0014`, `0015`, `00FA`, and group `FF` with types `0000` and `0003`. The toolkit README names the yen tag `[1401:..]`; its exact group/type split is not confirmed here.

Tag size bug fixed in `651980a`: the size byte was args + 3. It must be the total length.

## Known history

- `651980a` (build-bmg.js): pad `DAT1` so `MID1` is aligned; fix token regex (missing `]`); fix the tag size byte.
- `4426fa0`: re-save `etc`, `item`, `room` with +2 zero bytes each. These three had `DAT1` sizes that were not multiples of 4, which crashed the game.
- Every other file already passes the alignment rule.

## Checks to run before committing a BMG

1. Magic is `MESGbmg1`, file size field equals the file length, section count matches.
2. Sections chain from `0x20` to EOF, with start and size multiples of 4.
3. `INF1` count equals `MID1` count.
4. Every `INF1` offset points inside `DAT1`, and every message reaches a `0x0000` terminator before the `DAT1` end.
5. Tag `size` is at least 4 and stays inside the message.

Current status (all 7 files): checks 1 to 5 pass.

## Known oddities (not crashes, from the original data)

- `tmd_etc`: 20 `INF1` offsets are duplicated and 21 messages overlap, mostly empty messages pointing at offset 0. Same pattern in the first committed version, so it is an existing convention.
- `tmd_contents`: 1 empty message pointing at offset 0, same as above.
- `tmd_etc`: tag `FF:000A` existed in the first committed version and is gone now. Check whether removing it was intended.

## Yen figures in texts (money)

The currency toolkit converts prices in the data, not the text. Messages that still say yen (checked by scanning the 7 files for "yen" / "円"; "Âge moyen" is a false match):

| File | Msg | Text | Note |
|---|---|---|---|
| `tmd_contents` | 69 | "Il y avait une pièce de 10 yens ici" | coin reward, amount in text |
| `tmd_etc` | 123 | "Le coût du déménagement sera de ２１００ yens" | moving cost, amount in text |
| `tmd_etc` | 169 | "Critères : Collecter au moins 20 000 yen" | goal, amount in text |
| `tmd_etc` | 302 | "Vous avez collecté [TAG] yen(s) aujourd'hui !" | `[TAG]` shows a game amount (daily income) |

Any change to these numbers or to the word "yen" must follow the currency choice. Not done yet.

## Beta testers

A tester who still has `etc`, `item` or `room` from before `4426fa0` will get the crash. Make sure they use the current files.
