"""Build catalog.json: every clip, its details from the scan, and its checked tags.

Reads three things from the library folder:
  worklist.json       what ingest.py found (details and key frames for each clip)
  tags/*.jsonl        one tag line per clip, written by the tagger (Claude looking at the key frames)
  overrides.json      your own decisions, keyed by clip id (optional)
and writes catalog.json. A clip with no tag line yet stays in the catalog as "not tagged",
and is never usable. The privacy gate lives in taxonomy.clean_tags().

  python3 catalog.py --library library
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from taxonomy import check_tags, clean_tags, load_jsonl, load_taxonomy

DETAIL_KEYS = ("name", "path", "duration", "width", "height", "orientation", "fps", "has_audio", "frames")


def load_worklist(library: Path) -> list[dict]:
    path = Path(library) / "worklist.json"
    if not path.is_file():
        raise FileNotFoundError(f"No worklist.json in {library}. Run ingest.py on your folder of clips first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [c for c in data.get("clips", []) if isinstance(c, dict) and c.get("id")]


def load_tags(library: Path) -> tuple[dict, list[str]]:
    """All tag lines from tags/*.jsonl, by clip id. A later line for the same clip replaces an earlier one."""
    rows, errors = {}, []
    for f in sorted((Path(library) / "tags").glob("*.jsonl")):
        for rec in load_jsonl(f):
            if "_error" in rec:
                errors.append(rec["_error"])
            elif isinstance(rec, dict) and rec.get("id"):
                rows[str(rec["id"]).strip()] = rec
    return rows, errors


def load_overrides(library: Path) -> dict:
    path = Path(library) / "overrides.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): v for k, v in data.items() if isinstance(v, dict) and not str(k).startswith("_")}


def build_catalog(library: Path, tax: dict | None = None, today: str | None = None) -> dict:
    tax = tax or load_taxonomy()
    work = load_worklist(library)
    tags, errors = load_tags(library)
    overrides = load_overrides(library)
    known = {c["id"] for c in work}
    clips = []
    for c in work:
        base = {"id": c["id"], **{k: c.get(k) for k in DETAIL_KEYS}}
        raw = tags.get(c["id"])
        if raw is None:
            clips.append({**base, "tagged": False, "usable": "no", "gate": "not tagged yet", "problems": []})
            continue
        problems = check_tags(raw, tax)
        rec = clean_tags(raw, tax, overrides.get(c["id"]))
        if problems and rec["usable"] == "yes" and c["id"] not in overrides:
            rec["usable"], rec["gate"] = "no", "tag line has problems"
        clips.append({**base, **rec, "tagged": True, "problems": problems})
    return {"made": today or dt.date.today().isoformat(), "taxonomy_version": tax.get("version"),
            "clips": clips, "orphans": sorted(set(tags) - known), "tag_file_errors": errors,
            "summary": summarise(clips)}


def summarise(clips: list[dict]) -> dict:
    tagged = [c for c in clips if c.get("tagged")]
    kinds: dict[str, int] = {}
    for c in tagged:
        kinds[str(c.get("kind"))] = kinds.get(str(c.get("kind")), 0) + 1
    return {"clips": len(clips), "tagged": len(tagged), "not_tagged": len(clips) - len(tagged),
            "usable_yes": sum(1 for c in clips if c.get("usable") == "yes"),
            "consent_needed": sum(1 for c in tagged if c.get("consent_needed")),
            "with_problems": sum(1 for c in tagged if c.get("problems")), "kinds": kinds}


def write_catalog(library: Path, tax: dict | None = None, today: str | None = None) -> tuple[Path, dict]:
    cat = build_catalog(library, tax, today)
    out = Path(library) / "catalog.json"
    out.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    return out, cat


def describe(cat: dict) -> str:
    s = cat["summary"]
    lines = [f"{s['clips']} clips in the library, {s['tagged']} tagged, {s['not_tagged']} waiting for tags.",
             f"{s['usable_yes']} marked ok to post. {s['consent_needed']} need consent before public use (kept private).",
             ]
    if s["with_problems"]:
        lines.append(f"{s['with_problems']} tag lines had problems and were kept private until they are fixed.")
    if cat["orphans"]:
        lines.append(f"{len(cat['orphans'])} tag lines belong to clips that are not in the library: {', '.join(cat['orphans'][:5])}")
    lines += [f"Tag file problem: {e}" for e in cat["tag_file_errors"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge scan details and tag lines into catalog.json.")
    ap.add_argument("--library", type=Path, default=Path("library"), help="the library folder (default: library)")
    a = ap.parse_args(argv)
    try:
        out, cat = write_catalog(a.library)
    except (OSError, ValueError) as exc:
        print(f"Could not build the catalog: {exc}", file=sys.stderr)
        return 2
    print(describe(cat))
    print(f"Catalog: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
