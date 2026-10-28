"""Write selects.md: the clips you said yes to, ranked, for the for-reels kit to pull from.

Only clips that are usable (after the privacy gate and your own overrides) can appear.
Best first: broll before anything else, then higher quality, then the longest clip.

  python3 selects.py --library library
  python3 selects.py --library library --mood calm --place beach_water --limit 12 --role opener
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from taxonomy import norm


def pick(clips: list[dict], mood: str | None = None, place: str | None = None, role: str | None = None,
         kind: str | None = None, min_quality: int = 1, limit: int | None = None) -> list[dict]:
    rows = [c for c in clips if c.get("usable") == "yes" and (c.get("quality") or 0) >= min_quality]
    if mood:
        rows = [c for c in rows if norm(mood) in (c.get("mood") or [])]
    if place:
        rows = [c for c in rows if c.get("place") == norm(place)]
    if role:
        rows = [c for c in rows if c.get("reel_role") == norm(role)]
    if kind:
        rows = [c for c in rows if c.get("kind") == norm(kind)]
    rows.sort(key=lambda c: (c.get("kind") != "broll", -(c.get("quality") or 0), -(c.get("duration") or 0), c["id"]))
    return rows[:limit] if limit else rows


def _cell(text: object) -> str:
    return str(text if text not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def render_selects(cat: dict, **filters) -> str:
    rows = pick(cat.get("clips", []), **filters)
    asked = ", ".join(f"{k} {v}" for k, v in filters.items() if v not in (None, "", 1))
    out = ["# Selects", "",
           f"Clips marked ok to post, best first. Made {cat.get('made', '')}" + (f". Filter: {asked}." if asked else "."),
           "", "Each path points at your own clip on your own computer. "
           "Look at a clip once before it goes public, and keep it private if anyone in it has not said yes.", ""]
    if not rows:
        out += ["No clips match yet. Tag more clips, or say yes to some in `overrides.json`, then run `selects.py` again.", ""]
        return "\n".join(out)
    out += ["| # | clip | path | length | shape | place | mood | role | quality | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, c in enumerate(rows, 1):
        length = f"{int(c.get('duration') or 0) // 60}:{int(c.get('duration') or 0) % 60:02d}"
        out.append("| " + " | ".join(_cell(x) for x in (
            n, c.get("name"), c.get("path"), length, c.get("orientation"), c.get("place"),
            ", ".join(c.get("mood") or []), c.get("reel_role"), f"{c.get('quality')}/5", c.get("notes"))) + " |")
    out += ["", f"{len(rows)} clips."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write selects.md from catalog.json.")
    ap.add_argument("--library", type=Path, default=Path("library"))
    ap.add_argument("--out", type=Path, help="where to write (default: <library>/selects.md)")
    ap.add_argument("--mood"), ap.add_argument("--place"), ap.add_argument("--role"), ap.add_argument("--kind")
    ap.add_argument("--min-quality", type=int, default=1)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    try:
        cat = json.loads((a.library / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Could not read {a.library / 'catalog.json'} ({exc}). Run catalog.py first.", file=sys.stderr)
        return 2
    text = render_selects(cat, mood=a.mood, place=a.place, role=a.role, kind=a.kind,
                          min_quality=a.min_quality, limit=a.limit)
    out = a.out or a.library / "selects.md"
    out.write_text(text, encoding="utf-8")
    print(f"Selects: {out} ({sum(1 for l in text.splitlines() if l.startswith('| ') and not l.startswith('| #'))} clips)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
