"""Find clips, read their details with ffprobe, and pull key frames with ffmpeg.

The commands are built by small functions (probe_cmd, scene_cmd, uniform_cmd) so they can be
checked without ffmpeg installed. extract_clip() runs them: up to MAX_FRAMES frames at scene
changes, and for calm clips with few changes, three even frames (start, middle, end) instead.
Nothing here deletes or changes the original clips. It only reads them.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".hevc", ".3gp"}
MAX_FRAMES = 6
MIN_FRAMES = 3
SCENE_THRESHOLD = 0.3
FRAME_HEIGHT = 640
FFMPEG_HELP = ("ffmpeg is not installed, and the tool needs it to read your clips. "
               "On a Mac with Homebrew, type: brew install ffmpeg. On Windows: winget install ffmpeg. "
               "Then run this again.")


def find_tool(name: str) -> str | None:
    return shutil.which(name)


def find_clips(folder: Path) -> list[Path]:
    """Every video under folder, skipping hidden folders (like a Photos export database)."""
    folder = Path(folder)
    return sorted(p for p in folder.rglob("*")
                  if p.is_file() and p.suffix.lower() in VIDEO_EXT
                  and not any(part.startswith(".") for part in p.relative_to(folder).parts))


def clip_id(path: Path, root: Path) -> str:
    """A short, stable, filename-safe id: the name plus a hash of where it lives."""
    rel = str(Path(path).resolve().relative_to(Path(root).resolve()))
    stem = re.sub(r"[^a-z0-9]+", "-", Path(path).stem.lower()).strip("-")[:40] or "clip"
    return f"{stem}-{hashlib.sha1(rel.encode()).hexdigest()[:6]}"


def probe_cmd(path: Path, ffprobe: str = "ffprobe") -> list[str]:
    return [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)]


def scene_cmd(path: Path, out_dir: Path, ffmpeg: str = "ffmpeg", threshold: float = SCENE_THRESHOLD,
              max_frames: int = MAX_FRAMES, height: int = FRAME_HEIGHT, sync_flag: str = "-fps_mode") -> list[str]:
    """Frames where the picture changes a lot (scene changes), scaled to height, at most max_frames.
    sync_flag is -fps_mode on ffmpeg 5.1 and newer, and -vsync on older ones."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(path),
            "-vf", f"select='gt(scene,{threshold})',scale=-2:{height}",
            "-frames:v", str(max_frames), sync_flag, "vfr", "-q:v", "4",
            str(Path(out_dir) / "s%02d.jpg")]


def uniform_times(duration: float, n: int = MIN_FRAMES) -> list[float]:
    """Even points through the clip, away from the very first and last frame."""
    if duration <= 0:
        return []
    if n == 1:
        return [round(duration / 2, 2)]
    return [round(duration * (0.1 + 0.8 * i / (n - 1)), 2) for i in range(n)]


def uniform_cmd(path: Path, t: float, out_file: Path, ffmpeg: str = "ffmpeg",
                height: int = FRAME_HEIGHT) -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", f"{t:.2f}", "-i", str(path),
            "-vf", f"scale=-2:{height}", "-frames:v", "1", "-q:v", "4", str(out_file)]


def summarise_probe(meta: dict) -> dict:
    """Duration, size, orientation (vertical clips are reel-ready), fps and whether it has sound."""
    streams = meta.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    rot = 0
    for sd in video.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = int(float((video.get("tags") or {}).get("rotate", rot) or rot))
    if abs(rot) % 180 == 90:
        w, h = h, w
    fps = 0.0
    num, _, den = str(video.get("avg_frame_rate") or "0/1").partition("/")
    try:
        fps = round(float(num) / float(den or 1), 2)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float((meta.get("format") or {}).get("duration") or video.get("duration") or 0)
    orient = "vertical" if h > w else "horizontal" if w > h else "square"
    return {"duration": round(duration, 2), "width": w, "height": h, "orientation": orient if w and h else "unknown",
            "fps": fps, "has_audio": any(s.get("codec_type") == "audio" for s in streams)}


def probe(path: Path, ffprobe: str = "ffprobe", run=subprocess.run) -> dict:
    r = run(probe_cmd(path, ffprobe), capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        return {}
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}


def extract_clip(path: Path, out_dir: Path, duration: float, ffmpeg: str = "ffmpeg",
                 run=subprocess.run, max_frames: int = MAX_FRAMES) -> list[str]:
    """Key frames for one clip. Re-running is safe: a clip that already has frames is skipped."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    have = sorted(p.name for p in out_dir.glob("*.jpg"))
    if have:
        return have
    first = run(scene_cmd(path, out_dir, ffmpeg, max_frames=max_frames), capture_output=True, text=True)
    if "Unrecognized option" in str(getattr(first, "stderr", "") or ""):  # an older ffmpeg
        run(scene_cmd(path, out_dir, ffmpeg, max_frames=max_frames, sync_flag="-vsync"), capture_output=True, text=True)
    have = sorted(p.name for p in out_dir.glob("*.jpg"))
    if len(have) < MIN_FRAMES and duration > 0:
        for i, t in enumerate(uniform_times(duration)):
            run(uniform_cmd(path, t, out_dir / f"u{i:02d}.jpg", ffmpeg), capture_output=True, text=True)
        have = sorted(p.name for p in out_dir.glob("*.jpg"))
    return have


def scan(folder: Path, library: Path, limit: int | None = None, log=print) -> dict:
    """Read every clip in folder and pull its frames into library/frames/<id>/. Writes library/worklist.json."""
    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(FFMPEG_HELP)
    folder, library = Path(folder).resolve(), Path(library)
    clips = find_clips(folder)[:limit] if limit else find_clips(folder)
    worklist_path = library / "worklist.json"
    old = {}
    if worklist_path.exists():
        old = {c["id"]: c for c in json.loads(worklist_path.read_text(encoding="utf-8")).get("clips", [])}
    rows, failed = [], []
    for n, path in enumerate(clips, 1):
        cid = clip_id(path, folder)
        meta = summarise_probe(probe(path, ffprobe))
        if not meta["duration"]:
            failed.append(str(path.relative_to(folder)))
            log(f"[{n}/{len(clips)}] could not read {path.name}, skipped")
            continue
        frames = extract_clip(path, library / "frames" / cid, meta["duration"], ffmpeg)
        if not frames:
            failed.append(str(path.relative_to(folder)))
            log(f"[{n}/{len(clips)}] no frames from {path.name}, skipped")
            continue
        row = {"id": cid, "path": str(path), "name": path.name, **meta,
               "frames": [f"frames/{cid}/{f}" for f in frames]}
        old.pop(cid, None)
        rows.append(row)
        log(f"[{n}/{len(clips)}] {path.name}: {len(frames)} frames")
    rows += list(old.values())  # clips scanned before from another folder stay in the library
    library.mkdir(parents=True, exist_ok=True)
    worklist = {"source": str(folder), "clips": sorted(rows, key=lambda r: r["id"]), "failed": failed}
    worklist_path.write_text(json.dumps(worklist, indent=1), encoding="utf-8")
    return worklist
