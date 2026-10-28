# Testing

Everything below was run on 28 Oct 2026, on macOS with Python 3.12.8, ffmpeg 8.0.1 and Google Chrome installed.

## 1. Tests
```sh
python3 -m unittest discover -s tests -v
```
Result: **71 tests, all OK.** They cover:
- **Command construction without ffmpeg:** the ffprobe, scene-change and even-frame commands, that the clip appears only as an input and is never written to, the older-ffmpeg retry with `-vsync`, the even-frame fallback for calm clips, safe re-runs, orientation and rotation from probe data, hidden folders skipped, stable filename-safe clip ids, and the friendly install message when ffmpeg is missing.
- **Ingest:** a dry run that prints the commands and touches nothing (with ffmpeg hidden), a missing folder, and tagging batches that skip clips already tagged.
- **One real ffmpeg run** (skipped when ffmpeg is not installed): a generated three-cut clip is read, frames are written, orientation is vertical, and the original is untouched.
- **Taxonomy and the privacy gate:** usable defaults to no; a yes on screen recordings, other people or children becomes no; an unusable clip is never usable; overrides narrow freely and widen only with a consent note; bad values are reported and dropped; the tag-file checker.
- **Catalog:** untagged clips stay in and are never usable, a tag line with problems is kept private, the later tag line wins, orphan ids and unreadable lines are reported, overrides, and the command line.
- **Selects:** only usable clips appear, b-roll first then by quality, filters, an empty result that says what to do, no em dashes.
- **Three motifs from one render path:** each signature marker (analog CONTACT SHEET and tape; cyberpunk `rocheverse:~$`, cursor, Silkscreen; y2k-blog `broll-librarian.exe`, hit counter `000,777`, guestbook link); the same 12 clips and the same 7 yes and 5 no pills in every motif; card sizes and clip counts; filters and phone-width rules present; user text escaped; untagged and empty libraries; quoted thumbnail paths; no glow or coloured shadow in any stylesheet; the `--motif` flag and old names; the no-Chrome message.
- **style.json:** the fallback order, the inheritance rule (a user file borrows only palette and fonts, never lines, owner, handle, name, references or notes), Rocha's lines appear only with the whole bundled example, a second palette and fonts re-tone all three motifs, bad colour and font values are not injected, an unreadable file falls back kindly, and both bundled files share keys.
- **Scorer:** two model tiers against the director's tags in `tests/fixtures/`. The small tier fails (one child clip marked usable, one clip skipped, low people agreement), the mid tier passes, the pick is the cheapest pass, advisory fields never gate, and the exit codes.
- **House rules on shipped text:** no em dashes, no banned words, no home paths, the README footer is exact, SKILL.md front matter, no video or photos shipped, every PNG listed in `docs/IMAGES.md`.

## 2. The README images
```sh
python3 scripts/make-readme-images.py
```
Output: 12 clips, 7 marked ok to post, 4 kept for consent (the twelfth is unusable), the hero and triptych written, `docs/IMAGES.md` written.
Both PNGs were opened and checked by eye at full size: nothing cut off, no glow, the sidebar and hit counter in place, the pills right.

## 3. Phone width, by eye and by measurement
The three library pages were loaded in a 390px wide browser: page width stayed 390 in analog, cyberpunk and y2k-blog, so no sideways scroll. In y2k-blog the "keep private" filter was clicked and showed 5 clips with the count "5 shown".

## 4. Security gate
```sh
./scripts/security-check.sh
```
Result in the report that came with this build: **SAFE TO PUBLISH**.

## Not tested
- **Real camera-roll clips.** The one real ffmpeg run used a generated clip. HEVC iPhone files, very long clips and odd containers were not tried.
- **Tagging by Claude.** The tagging prompt was written and its output shape is checked by the tests, but no model was run on real frames for this build. The scorer fixture is made up, so its pass and fail show the scorer works, not how any real model performs.
- **Parallel tagging with helper agents**, and **Claude Cowork** (upload of the zip, and whether its sandbox has ffmpeg or Chrome). Without Chrome the tool prints a clear message and still writes the page (code-reviewed and unit tested with Chrome hidden).
- **Windows**, and the Photos library export steps on your Mac.
