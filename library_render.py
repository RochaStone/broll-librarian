"""library.html: your clips as a browsable page, in three motif skins from one render path.

  analog     a contact sheet: polaroid frames, washi tape, a date stamp (paper you could hold)
  cyberpunk  the girly terminal: a plum CRT listing your clips like cartridges
  y2k-blog   a 2003 blog window with a sidebar, a hit counter and a guestbook
Motif is structure; style.json palette and fonts are colour and type, so every family re-tones.

  python3 library_render.py --library library                 writes library/library.html
  python3 library_render.py --library library --motif cyberpunk --png
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from style import find_style, line, load_style, resolve_motif, style_head, MOTIFS

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CSS_FILES = {"analog": ["library.css"], "cyberpunk": ["library.css", "motif-cyberpunk.css"],
             "y2k-blog": ["library.css", "motif-y2k.css"]}
CARD_W, CARD_H = 1080, 1350
CARD_CLIPS = {"analog": 8, "cyberpunk": 8, "y2k-blog": 6}
REPO_ISSUES = "https://github.com/RochaStone/broll-librarian/issues"

KIND_LABEL = {"broll": "b-roll", "talking_head": "talking head", "screen_recording": "screen recording", "unusable": "unusable"}
PEOPLE_LABEL = {"none": "nobody in shot", "me_only": "only me", "others": "other people", "children": "children in shot"}

PIXEL_HEART = ('<svg class="pix" viewBox="0 0 7 6" width="21" height="18" aria-hidden="true" shape-rendering="crispEdges">'
               '<path fill="currentColor" d="M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z"/></svg>')
PIXEL_STAR = ('<svg class="pix" viewBox="0 0 5 5" width="15" height="15" aria-hidden="true" shape-rendering="crispEdges">'
              '<path fill="currentColor" d="M2 0h1v2h2v1H3v2H2V3H0V2h2z"/></svg>')

FILTER_SCRIPT = """<script>
(function () {
  var groups = {}, cards = [].slice.call(document.querySelectorAll(".clip")), q = document.getElementById("find");
  function apply() {
    var text = q ? q.value.trim().toLowerCase() : "", shown = 0;
    cards.forEach(function (c) {
      var ok = Object.keys(groups).every(function (g) { return groups[g] === "all" || c.dataset[g] === groups[g]; });
      ok = ok && (!text || c.dataset.text.indexOf(text) > -1);
      c.hidden = !ok; if (ok) shown++;
    });
    var n = document.getElementById("shown"); if (n) n.textContent = shown + " shown";
  }
  [].forEach.call(document.querySelectorAll(".chips button"), function (b) {
    b.addEventListener("click", function () {
      var g = b.dataset.group; groups[g] = b.dataset.value;
      [].forEach.call(document.querySelectorAll('.chips button[data-group="' + g + '"]'), function (o) {
        o.setAttribute("aria-pressed", o === b ? "true" : "false");
      });
      apply();
    });
  });
  if (q) q.addEventListener("input", apply);
})();
</script>"""


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _short(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _label(value: object) -> str:
    return str(value or "").replace("_", " ")


def _length(seconds: object) -> str:
    s = int(float(seconds or 0))
    return f"{s // 60}:{s % 60:02d}"


def _blocks(n: object, total: int = 5) -> str:
    n = n if isinstance(n, int) else 0
    return "▮" * n + "▯" * (total - n)


def thumb_path(clip: dict) -> str:
    frames = clip.get("frames") or []
    return frames[len(frames) // 2] if frames else ""


def _card(c: dict, base: str, motif: str, number: int) -> str:
    tagged = c.get("tagged")
    yes = c.get("usable") == "yes"
    kind = KIND_LABEL.get(c.get("kind"), "not tagged")
    place, people = _label(c.get("place")) or "-", PEOPLE_LABEL.get(c.get("people_present"), "-")
    gate = c.get("gate") or ""
    src = thumb_path(c)
    img = (f'<img src="{_e(base + quote(src))}" alt="key frame from {_e(c.get("name") or c["id"])}" loading="lazy">'
           if src else '<span class="noframe">no frame</span>')
    deco = {"analog": '<span class="tape" aria-hidden="true"></span>',
            "cyberpunk": f'<span class="slot px">[{number:02d}]</span>',
            "y2k-blog": ""}[motif]
    text = " ".join(str(x) for x in (c.get("name"), kind, place, people, c.get("notes"), " ".join(c.get("mood") or [])) if x).lower()
    pill = ("ok to post" if yes else "keep private") if tagged else "not tagged"
    return f"""<article class="clip" data-usable="{"yes" if yes else "no"}" data-kind="{_e(c.get("kind") or "none")}" data-place="{_e(c.get("place") or "unknown")}" data-text="{_e(text)}">
  <figure class="thumb">{img}{deco}</figure>
  <div class="meta">
    <h3 class="cname">{_e(_short(c.get("name") or c["id"], 28))}</h3>
    <p class="row"><span class="kind">{_e(kind)}</span><span class="len">{_length(c.get("duration"))} · {_e(c.get("orientation") or "")}</span></p>
    <p class="where">{_e(place)} · {_e(people)}</p>
    <p class="rate" aria-label="quality {c.get("quality") or 0} of 5">{_blocks(c.get("quality"))}</p>
    <p class="note">{_e(_short(str(c.get("notes") or ""), 90))}</p>
    <p class="status"><span class="pill {"yes" if yes else "no"}">{pill}</span>{f'<small>{_e(gate)}</small>' if gate and not yes else ""}</p>
  </div>
</article>"""


def _filters(clips: list[dict]) -> str:
    kinds = sorted({c.get("kind") for c in clips if c.get("kind")})
    places = sorted({c.get("place") for c in clips if c.get("place")})

    def group(name: str, label: str, values: list[tuple[str, str]]) -> str:
        buttons = '<button type="button" data-group="%s" data-value="all" aria-pressed="true">all</button>' % name
        buttons += "".join(f'<button type="button" data-group="{name}" data-value="{_e(v)}" aria-pressed="false">{_e(t)}</button>'
                           for v, t in values)
        return f'<div class="chips" role="group" aria-label="{label}"><span class="chiplabel">{label}</span>{buttons}</div>'

    return (f'<div class="filters">'
            + group("usable", "show", [("yes", "ok to post"), ("no", "keep private")])
            + group("kind", "kind", [(k, KIND_LABEL.get(k, _label(k))) for k in kinds])
            + group("place", "place", [(p, _label(p)) for p in places])
            + '<label class="find"><span class="chiplabel">find</span><input id="find" type="search" placeholder="beach, desk, calm" autocomplete="off"></label>'
            + '<span id="shown" class="chiplabel" role="status"></span></div>')


def _data(cat: dict, style: dict, card: bool, motif: str) -> dict:
    clips = cat.get("clips", [])
    shown = clips[: CARD_CLIPS[motif]] if card else clips
    s = cat.get("summary") or {}
    owner = str(style.get("owner") or "").strip()
    return {
        "clips": shown, "all": clips, "date": cat.get("made") or dt.date.today().isoformat(),
        "owner": owner, "scrawl": line(style, "scrawl"),
        "credit": " · ".join(str(x).strip() for x in (owner, style.get("handle"), "made with Rocha Coded") if x and str(x).strip()),
        "n": s.get("clips", len(clips)), "tagged": s.get("tagged", 0), "yes": s.get("usable_yes", 0),
        "consent": s.get("consent_needed", 0),
        "check_no": int(hashlib.sha1(str(cat.get("made")).encode()).hexdigest()[:6], 16) % 900000 + 100000,
    }


def _stats(d: dict) -> str:
    return (f'<b>{d["n"]}</b> clips · <b>{d["tagged"]}</b> tagged · <b>{d["yes"]}</b> ok to post · '
            f'<b>{d["consent"]}</b> need consent')


def _analog(d: dict, grid: str, filters: str) -> str:
    try:
        stamp = dt.date.fromisoformat(d["date"]).strftime("%d %b %Y").upper()
    except ValueError:
        stamp = str(d["date"])
    scrawl = f'<p class="scrawl">{_e(d["scrawl"])}</p>' if d["scrawl"] else ""
    owner = f'<div class="for">for <b>{_e(d["owner"])}</b></div>' if d["owner"] else ""
    return f"""<main class="sheet frame" aria-label="b-roll library">
  <header class="mast">
    <div class="kicker">CONTACT SHEET · EVERY CLIP, TAGGED FOR REELS</div>
    <h1>B-ROLL LIBRARY</h1>{owner}
    <div class="stamp" aria-hidden="true">TAGGED<br>{_e(stamp)}</div>
  </header>
  <p class="stats">{_stats(d)}</p>
  {filters}
  <div class="grid">{grid}</div>
  <footer class="foot">{scrawl}<div class="credit">{_e(d["credit"])}</div></footer>
</main>"""


def _cyberpunk(d: dict, grid: str, filters: str) -> str:
    echo = f' echo "{_e(d["scrawl"])}"' if d["scrawl"] else ""
    return f"""<main class="crt frame" aria-label="b-roll library">
  <div class="bezel"><span class="led candy"></span><span class="led gold"></span>
    <span class="px">broll-librarian · rocheverse</span><span class="screws"><i></i><i></i></span></div>
  <div class="screen">
    <p class="prompt"><span class="ps">rocheverse:~$</span> library --list --tagged</p>
    <p class="sys">› {_stats(d)} · job {d["check_no"]}</p>
    {filters}
    <div class="grid">{grid}</div>
    <p class="prompt last"><span class="ps">rocheverse:~$</span>{echo}<span class="cursor" aria-hidden="true"></span></p>
    <p class="credit px">{_e(d["credit"])}</p>
  </div>
</main>"""


def _y2k(d: dict, grid: str, filters: str) -> str:
    about = _e(d["owner"]) if d["owner"] else "my b-roll"
    scrawl = f'<p class="scrawl">{_e(d["scrawl"])}</p>' if d["scrawl"] else ""
    return f"""<main class="win frame" aria-label="b-roll library">
  <div class="titlebar"><span class="btns"><i></i><i></i><i></i></span><span class="title px">broll-librarian.exe</span></div>
  <div class="marquee"><span>{PIXEL_STAR} {d["n"]} clips {PIXEL_STAR} {d["yes"]} ok to post {PIXEL_STAR} last updated {_e(d["date"])} {PIXEL_STAR}</span></div>
  <div class="winbody">
    <div class="post">
      <h1>B-ROLL LIBRARY</h1>
      <p class="stats">{_stats(d)}</p>
      {filters}
      <div class="grid">{grid}</div>
      {scrawl}
    </div>
    <aside class="side">
      <section><h3 class="px">about me</h3><p>{about}<br>{d["n"]} clips</p></section>
      <section><h3 class="px">mood</h3><p>collecting ✧</p></section>
      <section><h3 class="px">currently reading</h3><p>my selects, the clips I said yes to</p></section>
      <section class="counter"><h3 class="px">hit counter</h3><p>you are visitor no.<br><b>000,777</b></p></section>
      <section class="guest"><h3 class="px">guestbook</h3><p><a href="{REPO_ISSUES}">sign my guestbook</a> {PIXEL_HEART}</p></section>
      <p class="sparkle">{PIXEL_HEART}{PIXEL_STAR}{PIXEL_HEART}</p>
      <p class="updated">last updated {_e(d["date"])}</p>
      <p class="credit px">{_e(d["credit"])}</p>
    </aside>
  </div>
</main>"""


def render_library(cat: dict, style: dict | None = None, motif: str | None = None,
                   card: bool = False, thumb_base: str = "") -> str:
    """The whole page. thumb_base is put in front of every frame path (a file:// folder, for the PNG card)."""
    style = load_style() if style is None else style
    motif = resolve_motif(motif, style)
    d = _data(cat, style, card, motif)
    grid = "".join(_card(c, thumb_base, motif, n) for n, c in enumerate(d["clips"], 1)) or \
        '<p class="empty">No clips yet. Run ingest.py on a folder of clips, then tag them.</p>'
    filters = "" if card else _filters(d["all"])
    body = {"analog": _analog, "cyberpunk": _cyberpunk, "y2k-blog": _y2k}[motif](d, grid, filters)
    css = "\n".join((ASSETS / f).read_text(encoding="utf-8") for f in CSS_FILES[motif] if (ASSETS / f).exists())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>B-roll library</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>{css}</style>
{style_head(style, motif)}</head>
<body class="{"card" if card else "page"} m-{motif}">
{body}{"" if card else FILTER_SCRIPT}</body></html>"""


# ---------- PNG ----------

def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge"):
        p = shutil.which(cmd)
        if p:
            return p
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if Path(p).exists():
            return p
    return None


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


def render_png(page_html: Path, png: Path, width: int = CARD_W, height: int = CARD_H) -> tuple[bool, str]:
    chrome = find_chrome()
    if not chrome:
        return False, ("No Chrome or Chromium found, so no picture this time. library.html is ready. "
                       "Install Chrome, or set CHROME_PATH, then run again for the picture.")
    with tempfile.TemporaryDirectory() as profile:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--no-default-browser-check", f"--user-data-dir={profile}", f"--window-size={width},{height}",
               "--force-device-scale-factor=1", "--virtual-time-budget=6000",
               f"--screenshot={png}", Path(page_html).resolve().as_uri()]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        try:
            subprocess.run(cmd, capture_output=True, timeout=90, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"Chrome could not render the picture ({exc}). library.html is ready."
    if not Path(png).exists():
        return False, "Chrome ran but wrote no picture. library.html is ready."
    w, h = png_size(Path(png))
    return True, f"Picture: {png} ({w}x{h})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write library.html from catalog.json.")
    ap.add_argument("--library", type=Path, default=Path("library"))
    ap.add_argument("--motif", choices=list(MOTIFS) + ["guest-check", "retro-tv", "y2k"], help="analog, cyberpunk or y2k-blog")
    ap.add_argument("--style", type=Path, help="a style.json (default: ./style.json, then ~/.rocha-coded/style.json, then the bundled example)")
    ap.add_argument("--png", action="store_true", help="also write a 1080x1350 picture (needs Chrome)")
    a = ap.parse_args(argv)
    try:
        cat = json.loads((a.library / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Could not read {a.library / 'catalog.json'} ({exc}). Run catalog.py first.", file=sys.stderr)
        return 2
    style_path = find_style(a.style)
    style = load_style(style_path)
    motif = resolve_motif(a.motif, style)
    out = a.library / "library.html"
    out.write_text(render_library(cat, style, motif), encoding="utf-8")
    print(f"Library: {out} ({motif}, style from {style_path.name})")
    if a.png:
        card = a.library / ".library-card.html"
        card.write_text(render_library(cat, style, motif, card=True), encoding="utf-8")
        ok, msg = render_png(card, a.library / "library.png")
        card.unlink(missing_ok=True)
        print(msg)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
