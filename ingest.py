"""Ingest a folder of clips: read each one, pull key frames at scene changes, write batches for tagging.

  python3 ingest.py ~/Movies/camera-roll --library library
  python3 ingest.py ~/Movies/camera-roll --library library --limit 10     (a small first try)
  python3 ingest.py ~/Movies/camera-roll --dry-run                         (shows the commands, runs nothing)

Your clips are only read, never moved, changed or deleted. Everything it makes goes in the library folder.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import frames
from catalog import load_tags

BATCH_SIZE = 10


def write_batches(library: Path, size: int = BATCH_SIZE) -> list[Path]:
    """Split the clips that have no tags yet into batch files, so tagging can resume and run in parallel."""
    library = Path(library)
    work = json.loads((library / "worklist.json").read_text(encoding="utf-8")).get("clips", [])
    tagged, _ = load_tags(library)
    todo = [c for c in work if c["id"] not in tagged]
    out_dir = library / "batches"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("batch-*.json"):
        old.unlink()
    written = []
    for n in range(0, len(todo), size):
        chunk = todo[n:n + size]
        number = n // size + 1
        data = {"batch": number, "frames_are_relative_to": "the library folder",
                "tag_file": f"tags/batch-{number:03d}.jsonl",
                "clips": [{"id": c["id"], "name": c["name"], "duration": c["duration"],
                           "orientation": c["orientation"], "has_audio": c["has_audio"], "frames": c["frames"]}
                          for c in chunk]}
        path = out_dir / f"batch-{number:03d}.json"
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        written.append(path)
    return written


def dry_run(folder: Path, limit: int | None, log=print) -> int:
    clips = frames.find_clips(folder)
    if not clips:
        log(f"No video clips found in {folder}. It looks for: {', '.join(sorted(frames.VIDEO_EXT))}")
        return 1
    shown = clips[:limit] if limit else clips
    log(f"Found {len(clips)} clips in {folder}" + (f", showing the plan for the first {len(shown)}" if limit else "") + ".")
    sample = shown[0]
    cid = frames.clip_id(sample, folder)
    out_dir = Path("library") / "frames" / cid
    log(f"For each clip it runs these (shown for {sample.name}):")
    log("  read details:   " + shlex.join(frames.probe_cmd(sample)))
    log("  scene changes:  " + shlex.join(frames.scene_cmd(sample, out_dir)))
    log("  calm clip:      " + shlex.join(frames.uniform_cmd(sample, 1.0, out_dir / "u00.jpg")))
    for p in shown[:5]:
        log(f"  {frames.clip_id(p, folder)}  {p.name}")
    if len(shown) > 5:
        log(f"  ... and {len(shown) - 5} more")
    log("Dry run only. Nothing was read or written.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read a folder of clips and pull key frames for tagging.")
    ap.add_argument("folder", type=Path, help="the folder that holds your clips (subfolders are included)")
    ap.add_argument("--library", type=Path, default=Path("library"), help="where to write frames and lists (default: library)")
    ap.add_argument("--limit", type=int, help="only the first N clips, for a small first try")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"clips per tagging batch (default {BATCH_SIZE})")
    ap.add_argument("--dry-run", action="store_true", help="show what would run and stop")
    a = ap.parse_args(argv)
    if not a.folder.is_dir():
        print(f"{a.folder} is not a folder. Check the path and try again.", file=sys.stderr)
        return 2
    if a.dry_run:
        return dry_run(a.folder, a.limit)
    try:
        work = frames.scan(a.folder, a.library, a.limit)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    batches = write_batches(a.library, a.batch_size)
    print(f"Read {len(work['clips'])} clips" + (f", {len(work['failed'])} could not be read" if work["failed"] else "") + ".")
    for f in work["failed"]:
        print(f"  skipped: {f}")
    print(f"Wrote {len(batches)} batch file(s) of up to {a.batch_size} clips in {a.library / 'batches'}.")
    return 0 if work["clips"] else 1


if __name__ == "__main__":
    sys.exit(main())
