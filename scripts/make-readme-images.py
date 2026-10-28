#!/usr/bin/env python3
"""Generate every image the README uses, from the tool itself. Needs Chrome or Chromium for the PNGs.

  python3 scripts/make-readme-images.py

Makes a made-up sample library (twelve fictional clips, each with a drawn placeholder thumbnail), runs it
through the real catalog, library and selects code, then writes:
  examples/sample-library/    worklist.json, tags/sample.jsonl, catalog.json, library.html, selects.md, thumbs/*.svg
  docs/img/hero-y2k.png       the y2k-blog window with the sample library inside (1080x1350)
  docs/img/triptych.png       the same library in analog | cyberpunk | y2k-blog (1620x720)
  docs/img/step-01..05.svg    pixel step badges for "Start here"
  docs/img/divider.svg        a gold pixel hairline
  docs/img/heart.svg          a pixel heart
  docs/IMAGES.md              the list of all of the above
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import catalog  # noqa: E402
import library_render as lib  # noqa: E402
import selects  # noqa: E402
import style as styles  # noqa: E402

IMG = ROOT / "docs" / "img"
SAMPLE = ROOT / "examples" / "sample-library"
SAMPLE_DATE = "2026-10-28"
W, H = 180, 240
# 3x5 pixel digits, rows top to bottom
DIGITS = {"0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
          "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
          "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"]}


# ---------- pixel badges (same pattern as the other Rocha Coded tools) ----------

def _pixels(text: str, x0: int, y0: int) -> str:
    d = []
    for n, ch in enumerate(text):
        for r, row in enumerate(DIGITS[ch]):
            for c, bit in enumerate(row):
                if bit == "1":
                    d.append(f"M{x0 + n * 4 + c} {y0 + r}h1v1h-1z")
    return "".join(d)


def badge(num: str, ground: str, gold: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 11 9" width="33" height="27" '
            f'shape-rendering="crispEdges"><path fill="{ground}" d="M1 0h9v1h1v7h-1v1H1v-1H0V1h1z"/>'
            f'<path fill="{gold}" d="{_pixels(num, 2, 2)}"/></svg>\n')


def divider(gold: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="720" height="6" shape-rendering="crispEdges">'
            '<defs><pattern id="p" width="12" height="6" patternUnits="userSpaceOnUse">'
            f'<rect width="6" height="2" y="2" fill="{gold}"/><rect x="8" y="2" width="2" height="2" fill="{gold}"/>'
            '</pattern></defs><rect width="720" height="6" fill="url(#p)"/></svg>\n')


def heart(colour: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 7 6" width="21" height="18" shape-rendering="crispEdges">'
            f'<path fill="{colour}" d="M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z"/></svg>\n')


# ---------- placeholder thumbnails: flat drawn scenes, no photos, no real people ----------

def _r(x, y, w, h, fill, rx=0, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'


def _c(cx, cy, r, fill, extra=""):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" {extra}/>'


def _p(d, fill, extra=""):
    return f'<path d="{d}" fill="{fill}" {extra}/>'


def _figure(x, y, s, body, head):
    """The drawn stand-in figure: a round head on rounded shoulders."""
    return _c(x, y, 9 * s, head) + _p(f"M{x - 15 * s} {y + 34 * s}q0-{22 * s} {15 * s}-{22 * s}t{15 * s} {22 * s}z", body)


def scene(key: str, c: dict) -> str:
    g, wine, plum, ink, cream, blush, candy, gold = (c[k] for k in ("hero", "wine", "plum", "ink", "paper", "paper_pink", "accent", "gold"))
    s = {
        "sunrise": _r(0, 0, W, 140, candy) + _r(0, 0, W, 70, gold, extra='opacity=".55"') + _c(90, 128, 34, cream)
                   + _r(0, 128, W, 112, wine) + _r(0, 150, W, 6, plum) + _r(10, 172, 70, 4, cream, 2) + _r(100, 190, 60, 4, cream, 2)
                   + _r(30, 208, 90, 4, plum, 2),
        "desk": _r(0, 0, W, H, blush) + _r(104, 20, 60, 80, cream, 2) + _r(104, 20, 60, 80, "none", 2, f'stroke="{gold}" stroke-width="4"')
                + _r(0, 168, W, 72, wine) + _r(32, 124, 92, 56, plum, 3) + _r(38, 130, 80, 42, ink, 2)
                + "".join(_r(46, 138 + i * 9, 40 + (i % 2) * 22, 3, cream, 1) for i in range(4)) + _r(22, 180, 112, 7, ink, 3)
                + _r(142, 150, 20, 22, candy, 3) + _p("M160 156q12 4 0 14", "none", f'stroke="{candy}" stroke-width="3"')
                + _r(18, 140, 14, 28, wine) + _p("M25 140q-16-12-8-30 14 8 8 30zM25 140q16-10 10-28-14 6-10 28z", plum),
        "phone": _r(0, 0, W, H, ink) + _r(48, 22, 84, 196, cream, 14) + _r(54, 34, 72, 172, blush, 8)
                 + "".join(_r(60, 44 + i * 36, 60, 26, candy if i % 2 == 0 else wine, 4) for i in range(4)) + _r(78, 26, 24, 4, ink, 2),
        "coffee": _r(0, 0, W, H, cream) + "".join(_p(f"M{70 + i * 20} 70q-12-16 0-30t0-30", "none", f'stroke="{gold}" stroke-width="4" stroke-linecap="round"') for i in range(3))
                  + f'<ellipse cx="90" cy="176" rx="64" ry="14" fill="{wine}"/>' + _r(50, 104, 80, 70, wine, 10)
                  + f'<ellipse cx="90" cy="106" rx="40" ry="9" fill="{ink}"/>' + _p("M130 120q30 0 30 24t-30 22", "none", f'stroke="{wine}" stroke-width="9"'),
        "market": _r(0, 0, W, H, blush) + _r(0, 190, W, 50, plum) + _r(8, 60, 50, 134, wine) + _r(62, 30, 56, 164, plum) + _r(122, 80, 52, 114, wine)
                  + "".join(_r(14 + (i % 2) * 22, 70 + (i // 2) * 24, 12, 14, gold) for i in range(10))
                  + "".join(_r(70 + (i % 3) * 16, 42 + (i // 3) * 24, 10, 14, gold) for i in range(15))
                  + _figure(70, 168, .8, ink, ink) + _figure(112, 170, .8, wine, ink),
        "jar": _r(0, 0, W, H, wine) + _r(0, 150, W, 8, gold) + _r(0, 158, W, 82, plum) + _r(58, 70, 64, 80, cream, 10) + _r(66, 52, 48, 20, gold, 3)
               + _r(66, 90, 48, 36, candy, 3) + _r(74, 100, 32, 4, ink, 1) + _r(74, 110, 24, 4, ink, 1),
        "forest": _r(0, 0, W, H, plum) + _c(130, 50, 16, gold)
                  + "".join(_p(f"M{x} {y}l{w}-{h}l{w} {h}z", col) for x, y, w, h, col in
                            ((10, 190, 30, 110, wine), (50, 200, 34, 130, ink), (108, 196, 32, 118, wine), (140, 204, 30, 100, ink)))
                  + _p("M70 240L90 150L110 240z", blush),
        "kids": _r(0, 0, W, 130, candy) + _r(0, 130, W, 110, cream) + _r(0, 120, W, 16, wine) + _figure(60, 160, .7, ink, ink) + _figure(118, 168, .6, wine, ink)
                + _r(140, 200, 22, 18, gold, 3),
        "talking": _r(0, 0, W, H, plum) + _c(90, 98, 58, "none", f'stroke="{gold}" stroke-width="5"') + _figure(90, 108, 2.1, candy, blush)
                   + _r(0, 214, W, 26, wine),
        "candle": _r(0, 0, W, H, ink) + _c(90, 130, 70, plum) + _r(76, 120, 28, 90, cream, 3) + _p("M90 84q-16 20-10 34h20q6-14-10-34z", gold)
                  + _r(0, 210, W, 30, wine),
        "blur": _r(0, 0, W, H, ink) + f'<ellipse cx="60" cy="90" rx="50" ry="30" fill="{wine}" opacity=".5"/>'
                + f'<ellipse cx="120" cy="170" rx="56" ry="26" fill="{plum}" opacity=".7"/>' + _r(0, 0, W, 40, ink, 0, 'opacity=".6"'),
        "venue": _r(0, 0, W, H, ink) + "".join(_c(24 + i * 33, 34, 9, gold) for i in range(5)) + _p("M30 44L10 150H60zM150 44L170 150H120z", plum, 'opacity=".5"')
                 + "".join(_c(14 + i * 26, 206 - (i % 2) * 8, 13, plum) for i in range(7)),
    }[key]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="placeholder thumbnail: {key}">{s}</svg>\n')


# id, file name, scene, seconds, orientation, tags (the fields a tagger fills)
SAMPLE_CLIPS = [
    ("sunrise-swim-3f9a1c", "IMG_0412.MOV", "sunrise", 14.2, "vertical",
     dict(kind="broll", product=False, place="beach_water", people_present="none", mood=["calm", "golden_hour"], motion="static",
          reel_role="opener", usable="yes", quality=5, notes="Sunrise over flat water, no one in shot.")),
    ("desk-morning-8b21d0", "IMG_0413.MOV", "desk", 9.8, "vertical",
     dict(kind="broll", product=False, place="workspace", people_present="none", mood=["focused", "cozy"], motion="static",
          reel_role="proof_of_work", usable="yes", quality=4, notes="Laptop, mug and plant on a morning desk.")),
    ("phone-scroll-c07e44", "RPReplay_Final1.MOV", "phone", 21.0, "vertical",
     dict(kind="screen_recording", product=False, place="unknown", people_present="none", mood=["focused"], motion="static",
          reel_role="texture", usable="yes", quality=3, notes="A phone screen with messages open.")),
    ("coffee-pour-5d10aa", "IMG_0419.MOV", "coffee", 7.1, "vertical",
     dict(kind="broll", product=False, place="cafe", people_present="none", mood=["cozy", "bright_clean"], motion="static",
          reel_role="texture", usable="yes", quality=5, notes="Coffee and steam in a white cup.")),
    ("market-walk-e4417b", "IMG_0431.MOV", "market", 18.6, "horizontal",
     dict(kind="broll", product=False, place="city_street", people_present="others", mood=["playful"], motion="walking",
          reel_role="transition", usable="yes", quality=4, notes="Busy street, other people walking past.")),
    ("jar-on-shelf-a93c02", "IMG_0440.MOV", "jar", 6.4, "vertical",
     dict(kind="broll", product=True, place="home", people_present="none", mood=["luxe", "bright_clean"], motion="static",
          reel_role="proof_of_work", usable="yes", quality=4, notes="Product jar on a shelf, label facing out.")),
    ("forest-path-12ce9d", "IMG_0446.MOV", "forest", 16.3, "vertical",
     dict(kind="broll", product=False, place="outdoors_nature", people_present="none", mood=["calm", "moody"], motion="walking",
          reel_role="lifestyle", usable="yes", quality=4, notes="A path through trees at dusk.")),
    ("beach-kids-77bd3e", "IMG_0452.MOV", "kids", 11.9, "horizontal",
     dict(kind="broll", product=False, place="beach_water", people_present="children", mood=["playful", "bright_clean"], motion="handheld",
          reel_role="lifestyle", usable="yes", quality=4, notes="Two children playing on the sand.")),
    ("talking-head-2a8f66", "IMG_0458.MOV", "talking", 48.0, "vertical",
     dict(kind="talking_head", product=False, place="home", people_present="me_only", mood=["focused"], motion="static",
          reel_role="opener", usable="yes", quality=4, notes="Me talking to camera, good light.")),
    ("candle-evening-d5e09b", "IMG_0463.MOV", "candle", 12.5, "vertical",
     dict(kind="broll", product=False, place="home", people_present="none", mood=["cozy", "night", "calm"], motion="static",
          reel_role="end_moment", usable="yes", quality=5, notes="A single candle, evening light.")),
    ("venue-lights-9c34f1", "IMG_0470.MOV", "venue", 25.7, "horizontal",
     dict(kind="broll", product=False, place="venue_event", people_present="others", mood=["celebratory", "night"], motion="handheld",
          reel_role="texture", usable="yes", quality=3, notes="Stage lights and a crowd.")),
    ("pocket-blur-60aa7d", "IMG_0475.MOV", "blur", 3.2, "vertical",
     dict(kind="unusable", product=False, place="unknown", people_present="none", mood=[], motion="handheld",
          reel_role="texture", usable="yes", quality=1, notes="Pocket footage, nothing in frame.")),
]
# The sample tag lines say "yes" for several clips on purpose: the privacy gate turns the screen, the
# other people and the children into "no" when the catalog is built, and the unusable clip too.


def write_sample(style: dict) -> dict:
    pal = style["palette"]
    thumbs = SAMPLE / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    (SAMPLE / "tags").mkdir(exist_ok=True)
    clips, tag_lines = [], []
    for cid, name, key, secs, orient, tags in SAMPLE_CLIPS:
        (thumbs / f"{cid}.svg").write_text(scene(key, pal), encoding="utf-8")
        w, h = (1080, 1920) if orient == "vertical" else (1920, 1080)
        clips.append({"id": cid, "path": f"sample-clips/{name}", "name": name, "duration": secs, "width": w, "height": h,
                      "orientation": orient, "fps": 30.0, "has_audio": True, "frames": [f"thumbs/{cid}.svg"]})
        tag_lines.append(json.dumps({"id": cid, **tags}))
    (SAMPLE / "worklist.json").write_text(json.dumps({"source": "sample-clips", "clips": clips, "failed": []}, indent=1), encoding="utf-8")
    (SAMPLE / "tags" / "sample.jsonl").write_text("\n".join(tag_lines) + "\n", encoding="utf-8")
    _, cat = catalog.write_catalog(SAMPLE, today=SAMPLE_DATE)
    (SAMPLE / "selects.md").write_text(selects.render_selects(cat), encoding="utf-8")
    return cat


def triptych_html(pngs: dict[str, Path], ground: str, gold: str, cream: str) -> str:
    cells = "".join(f'<figure><img src="{p.as_uri()}" alt=""><figcaption>{m}</figcaption></figure>' for m, p in pngs.items())
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Silkscreen&display=swap">
<style>
* {{ margin: 0; box-sizing: border-box; }}
body {{ width: 1620px; height: 720px; background: {ground}; display: flex; gap: 30px; padding: 24px 36px; }}
figure {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 12px; min-height: 0; }}
img {{ width: 100%; min-height: 0; height: auto; border: 2px solid {gold}; }}
figcaption {{ font-family: "Silkscreen", monospace; color: {cream}; font-size: 22px; letter-spacing: .06em; }}
</style></head><body>{cells}</body></html>"""


def main() -> int:
    style = lib.load_style(styles.STYLE_EXAMPLE)  # the README images always use the bundled example look
    pal = style["palette"]
    ground, gold, cream, candy = pal["hero"], pal["gold"], pal["paper"], pal["accent"]
    IMG.mkdir(parents=True, exist_ok=True)
    for i in range(1, 6):
        (IMG / f"step-{i:02d}.svg").write_text(badge(f"{i:02d}", ground, gold), encoding="utf-8")
    (IMG / "divider.svg").write_text(divider(gold), encoding="utf-8")
    (IMG / "heart.svg").write_text(heart(candy), encoding="utf-8")
    print("SVGs: step-01..05, divider, heart")

    cat = write_sample(style)
    print(catalog.describe(cat))
    base = (SAMPLE.resolve().as_uri() + "/")
    ok_all = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pngs = {}
        for motif in lib.MOTIFS:
            page = tmp / f"{motif}.html"
            page.write_text(lib.render_library(cat, style, motif, card=True, thumb_base=base), encoding="utf-8")
            png = tmp / f"{motif}.png"
            ok, msg = lib.render_png(page, png)
            ok_all &= ok
            if not ok:
                print(msg)
                break
            pngs[motif] = png
        if ok_all:
            (IMG / "hero-y2k.png").write_bytes(pngs["y2k-blog"].read_bytes())
            strip = tmp / "triptych.html"
            strip.write_text(triptych_html(pngs, ground, gold, cream), encoding="utf-8")
            ok_all, msg = lib.render_png(strip, IMG / "triptych.png", 1620, 720)
            print(msg.replace("Picture", "Triptych"))
    (SAMPLE / "library.html").write_text(lib.render_library(cat, style, "analog"), encoding="utf-8")

    thumbs = "\n".join(f"| `examples/sample-library/thumbs/{cid}.svg` | drawn placeholder for the made-up clip {name} |"
                       for cid, name, *_ in SAMPLE_CLIPS)
    (ROOT / "docs" / "IMAGES.md").write_text(f"""# Images

Every image here is generated by `scripts/make-readme-images.py`. No photos, no video, no real people, no real places.
The sample library is made up: twelve fictional clips, each with a flat drawn placeholder in place of a real key frame.

| File | What it is |
|---|---|
| `docs/img/hero-y2k.png` | the sample library in the y2k-blog motif, used as the README hero |
| `docs/img/triptych.png` | the same library in analog, cyberpunk and y2k-blog, side by side |
| `docs/img/step-01.svg` to `step-05.svg` | pixel step badges for "Start here" |
| `docs/img/divider.svg` | a gold pixel hairline between README sections |
| `docs/img/heart.svg` | the pixel heart beside "If it goes wrong" |
{thumbs}
""", encoding="utf-8")
    print("docs/IMAGES.md written" + ("" if ok_all else " (PNGs skipped: no Chrome)"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
