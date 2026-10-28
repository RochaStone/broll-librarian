"""Frames, ingest, taxonomy, catalog and selects. Run from the repo root: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import catalog  # noqa: E402
import frames  # noqa: E402
import ingest  # noqa: E402
import library_render as lib  # noqa: E402
import selects  # noqa: E402
import taxonomy  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
SAMPLE = ROOT / "examples" / "sample-library"
TAX = taxonomy.load_taxonomy()


def quiet(fn, *a, **k):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*a, **k)
    return code, out.getvalue(), err.getvalue()


def sample_catalog():
    return json.loads((SAMPLE / "catalog.json").read_text(encoding="utf-8"))


class TestFrameCommands(unittest.TestCase):
    """Command construction is tested without ffmpeg installed."""

    def test_probe_command(self):
        cmd = frames.probe_cmd(Path("a b.mov"))
        self.assertEqual(cmd[0], "ffprobe")
        self.assertIn("-show_streams", cmd)
        self.assertEqual(cmd[-1], "a b.mov")

    def test_scene_command(self):
        cmd = frames.scene_cmd(Path("a.mov"), Path("out"))
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("select='gt(scene,0.3)',scale=-2:640", cmd)
        self.assertEqual(cmd[cmd.index("-frames:v") + 1], str(frames.MAX_FRAMES))
        self.assertIn("-fps_mode", cmd)
        self.assertEqual(cmd[-1], str(Path("out") / "s%02d.jpg"))
        self.assertIn("-vsync", frames.scene_cmd(Path("a.mov"), Path("out"), sync_flag="-vsync"))

    def test_uniform_command_and_times(self):
        cmd = frames.uniform_cmd(Path("a.mov"), 4.5, Path("out/u00.jpg"))
        self.assertEqual(cmd[cmd.index("-ss") + 1], "4.50")
        self.assertEqual(cmd[cmd.index("-frames:v") + 1], "1")
        t = frames.uniform_times(10)
        self.assertEqual(len(t), 3)
        self.assertEqual(t, sorted(t))
        self.assertGreater(t[0], 0)
        self.assertLess(t[-1], 10)
        self.assertEqual(frames.uniform_times(0), [])

    def test_nothing_is_ever_written_to_the_clip(self):
        for cmd in (frames.scene_cmd(Path("clip.mov"), Path("o")), frames.uniform_cmd(Path("clip.mov"), 1, Path("o/u.jpg"))):
            self.assertEqual(cmd.count("clip.mov"), 1)
            self.assertEqual(cmd.index("clip.mov"), cmd.index("-i") + 1)

    def test_summarise_probe_orientation_and_rotation(self):
        meta = {"format": {"duration": "12.5"}, "streams": [
            {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001",
             "side_data_list": [{"rotation": -90}]}, {"codec_type": "audio"}]}
        s = frames.summarise_probe(meta)
        self.assertEqual((s["width"], s["height"], s["orientation"]), (1080, 1920, "vertical"))
        self.assertEqual(s["duration"], 12.5)
        self.assertAlmostEqual(s["fps"], 29.97)
        self.assertTrue(s["has_audio"])
        self.assertEqual(frames.summarise_probe({})["orientation"], "unknown")

    def test_find_clips_skips_hidden_folders_and_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for rel in ("a.mov", "trip/b.MP4", "notes.txt", ".photoslibrary/c.mov", "trip/pic.jpg"):
                (d / rel).parent.mkdir(parents=True, exist_ok=True)
                (d / rel).write_bytes(b"x")
            found = [p.relative_to(d).as_posix() for p in frames.find_clips(d)]
            self.assertEqual(found, ["a.mov", "trip/b.MP4"])

    def test_clip_id_is_stable_and_filename_safe(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "x").mkdir()
            a, b = d / "IMG 0412 (1).MOV", d / "x" / "IMG 0412 (1).MOV"
            for p in (a, b):
                p.write_bytes(b"x")
            self.assertEqual(frames.clip_id(a, d), frames.clip_id(a, d))
            self.assertNotEqual(frames.clip_id(a, d), frames.clip_id(b, d))
            self.assertRegex(frames.clip_id(a, d), r"^[a-z0-9-]+-[0-9a-f]{6}$")

    def test_extract_clip_with_a_fake_runner(self):
        """Scene frames first; a calm clip with too few changes gets three even frames instead."""
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            out = Path(cmd[-1])
            if cmd[-1].endswith("s%02d.jpg"):
                (out.parent / "s01.jpg").write_bytes(b"j")
            else:
                out.write_bytes(b"j")
            return mock.Mock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as d:
            got = frames.extract_clip(Path("c.mov"), Path(d) / "id1", 9.0, run=fake)
            self.assertEqual(len(got), 4)  # one scene frame plus three even frames
            self.assertEqual(len(calls), 4)
            calls.clear()
            self.assertEqual(frames.extract_clip(Path("c.mov"), Path(d) / "id1", 9.0, run=fake), got)  # re-run is safe
            self.assertEqual(calls, [])

    def test_older_ffmpeg_gets_a_second_try_with_vsync(self):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if "-fps_mode" in cmd:
                return mock.Mock(returncode=1, stderr="Unrecognized option 'fps_mode'.")
            if cmd[-1].endswith("s%02d.jpg"):
                for i in (1, 2, 3):
                    (Path(cmd[-1]).parent / f"s{i:02d}.jpg").write_bytes(b"j")
            return mock.Mock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(frames.extract_clip(Path("c.mov"), Path(d) / "x", 9.0, run=fake)), 3)
        self.assertIn("-vsync", calls[1])

    def test_scan_says_how_to_install_ffmpeg(self):
        with mock.patch.object(frames, "find_tool", return_value=None):
            with self.assertRaises(RuntimeError) as cm:
                frames.scan(Path("."), Path("lib"))
        self.assertIn("brew install ffmpeg", str(cm.exception))


class TestIngest(unittest.TestCase):
    def test_dry_run_shows_commands_without_ffmpeg(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.mov").write_bytes(b"x")
            lines = []
            with mock.patch.object(frames, "find_tool", return_value=None):
                self.assertEqual(ingest.dry_run(Path(d), None, log=lines.append), 0)
            text = "\n".join(lines)
            self.assertIn("ffprobe -v quiet", text)
            self.assertIn("select=", text)
            self.assertIn("Nothing was read or written", text)

    def test_dry_run_on_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as d:
            lines = []
            self.assertEqual(ingest.dry_run(Path(d), None, log=lines.append), 1)
            self.assertIn("No video clips found", lines[0])

    def test_cli_dry_run_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.mov").write_bytes(b"x")
            code, out, _ = quiet(ingest.main, [d, "--dry-run"])
            self.assertEqual(code, 0)
            self.assertFalse((Path.cwd() / "library" / "worklist.json").exists() and "Dry run" not in out)
        code, _, err = quiet(ingest.main, ["/no/such/folder"])
        self.assertEqual(code, 2)
        self.assertIn("is not a folder", err)

    def test_batches_skip_clips_that_already_have_tags(self):
        with tempfile.TemporaryDirectory() as d:
            lib_dir = Path(d)
            clips = [{"id": f"c{i}", "name": f"{i}.mov", "duration": 5, "orientation": "vertical", "has_audio": True,
                      "frames": [f"frames/c{i}/s01.jpg"]} for i in range(25)]
            (lib_dir / "worklist.json").write_text(json.dumps({"clips": clips}), encoding="utf-8")
            (lib_dir / "tags").mkdir()
            (lib_dir / "tags" / "batch-001.jsonl").write_text(json.dumps({"id": "c0", "kind": "broll"}) + "\n", encoding="utf-8")
            written = ingest.write_batches(lib_dir, size=10)
            self.assertEqual([p.name for p in written], ["batch-001.json", "batch-002.json", "batch-003.json"])
            first = json.loads(written[0].read_text(encoding="utf-8"))
            self.assertEqual(len(first["clips"]), 10)
            self.assertNotIn("c0", [c["id"] for c in first["clips"]])
            self.assertEqual(first["tag_file"], "tags/batch-001.jsonl")
            self.assertEqual(len(json.loads(written[2].read_text(encoding="utf-8"))["clips"]), 4)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is not installed")
    def test_real_ffmpeg_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            clips = d / "clips"
            clips.mkdir()
            cut = clips / "three-cuts.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=216x384:rate=15:duration=1",
                            "-f", "lavfi", "-i", "color=c=red:size=216x384:rate=15:duration=1", "-f", "lavfi", "-i",
                            "color=c=blue:size=216x384:rate=15:duration=1", "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0",
                            "-pix_fmt", "yuv420p", str(cut)], check=True)
            work = frames.scan(clips, d / "library", log=lambda *_: None)
            self.assertEqual(len(work["clips"]), 1)
            row = work["clips"][0]
            self.assertEqual(row["orientation"], "vertical")
            self.assertGreaterEqual(len(row["frames"]), 3)
            self.assertTrue((d / "library" / row["frames"][0]).is_file())
            self.assertTrue(cut.is_file())  # the original is untouched


class TestTaxonomy(unittest.TestCase):
    def test_taxonomy_has_every_field_the_brief_asks_for(self):
        for name in ("kind", "product", "place", "people_present", "mood", "usable"):
            self.assertIn(name, TAX["fields"])
        self.assertEqual(TAX["fields"]["usable"]["default"], "no")
        for kind in ("broll", "talking_head", "screen_recording"):
            self.assertIn(kind, TAX["fields"]["kind"]["values"])

    def test_usable_defaults_to_no(self):
        for rec in ({"id": "a", "kind": "broll"}, {"id": "a", "usable": "maybe"}, {"id": "a", "usable": None}):
            self.assertEqual(taxonomy.clean_tags(rec, TAX)["usable"], "no")

    def test_clean_clip_can_be_yes(self):
        rec = {"id": "a", "kind": "broll", "place": "home", "people_present": "none", "usable": "yes", "quality": 4}
        self.assertEqual(taxonomy.clean_tags(rec, TAX)["usable"], "yes")

    def test_privacy_gate_turns_yes_into_no(self):
        for extra in ({"kind": "screen_recording"}, {"people_present": "others"}, {"people_present": "children"}):
            rec = {"id": "a", "kind": "broll", "place": "home", "people_present": "none", "usable": "yes", "quality": 4, **extra}
            out = taxonomy.clean_tags(rec, TAX)
            self.assertEqual(out["usable"], "no", extra)
            self.assertTrue(out["consent_needed"])
            self.assertEqual(out["gate"], "consent needed")

    def test_unusable_kind_is_never_usable(self):
        out = taxonomy.clean_tags({"id": "a", "kind": "unusable", "usable": "yes", "people_present": "none"}, TAX)
        self.assertEqual((out["usable"], out["gate"]), ("no", "marked unusable"))

    def test_override_rules(self):
        gated = {"id": "a", "kind": "broll", "place": "home", "people_present": "others", "usable": "yes", "quality": 4}
        self.assertEqual(taxonomy.clean_tags(gated, TAX, {"usable": "yes"})["usable"], "no")
        self.assertIn("no consent note", taxonomy.clean_tags(gated, TAX, {"usable": "yes"})["gate"])
        ok = taxonomy.clean_tags(gated, TAX, {"usable": "yes", "consent": "said yes in writing"})
        self.assertEqual((ok["usable"], ok["consent"]), ("yes", "said yes in writing"))
        clean = {**gated, "people_present": "none"}
        self.assertEqual(taxonomy.clean_tags(clean, TAX, {"usable": "no"})["usable"], "no")

    def test_bad_values_are_dropped_and_reported(self):
        rec = {"id": "a", "kind": "film", "place": "mars", "people_present": "none", "usable": "yes", "quality": 9,
               "mood": ["calm", "angry", "cozy", "moody", "night"]}
        problems = " | ".join(taxonomy.check_tags(rec, TAX))
        for word in ("kind", "place", "quality", "mood"):
            self.assertIn(word, problems)
        out = taxonomy.clean_tags(rec, TAX)
        self.assertIsNone(out["kind"])
        self.assertIsNone(out["quality"])
        self.assertEqual(out["mood"], ["calm", "cozy", "moody"])

    def test_check_file_command(self):
        code, out, _ = quiet(taxonomy.main, [str(FIX / "director.jsonl")])
        self.assertEqual((code, out.strip()), (0, "12 tag lines checked, all clean."))
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.jsonl"
            bad.write_text('{"id": "a", "kind": "film"}\nnot json\n', encoding="utf-8")
            code, out, _ = quiet(taxonomy.main, [str(bad)])
            self.assertEqual(code, 1)
            self.assertIn("2 with problems", out)


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        shutil.copytree(SAMPLE, self.d / "lib")
        self.lib = self.d / "lib"

    def test_sample_catalog(self):
        cat = catalog.build_catalog(self.lib, today="2026-10-28")
        self.assertEqual(cat["summary"]["clips"], 12)
        self.assertEqual(cat["summary"]["usable_yes"], 7)
        self.assertEqual(cat["summary"]["consent_needed"], 4)
        by = {c["id"]: c for c in cat["clips"]}
        self.assertEqual(by["phone-scroll-c07e44"]["usable"], "no")
        self.assertEqual(by["beach-kids-77bd3e"]["gate"], "consent needed")
        self.assertEqual(by["pocket-blur-60aa7d"]["gate"], "marked unusable")
        self.assertEqual(by["sunrise-swim-3f9a1c"]["usable"], "yes")

    def test_untagged_clip_is_in_the_catalog_and_never_usable(self):
        (self.lib / "tags" / "sample.jsonl").write_text("", encoding="utf-8")
        cat = catalog.build_catalog(self.lib)
        self.assertEqual(cat["summary"]["not_tagged"], 12)
        self.assertEqual(cat["summary"]["usable_yes"], 0)
        self.assertEqual(cat["clips"][0]["gate"], "not tagged yet")

    def test_a_tag_line_with_problems_is_kept_private(self):
        line = {"id": "sunrise-swim-3f9a1c", "kind": "broll", "place": "mars", "people_present": "none", "usable": "yes", "quality": 5}
        (self.lib / "tags" / "sample.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
        clip = next(c for c in catalog.build_catalog(self.lib)["clips"] if c["id"] == line["id"])
        self.assertEqual((clip["usable"], clip["gate"]), ("no", "tag line has problems"))
        self.assertTrue(clip["problems"])

    def test_later_tag_line_wins_and_orphans_and_bad_lines_are_reported(self):
        first = {"id": "sunrise-swim-3f9a1c", "kind": "broll", "place": "home", "people_present": "none", "usable": "no", "quality": 2}
        second = {**first, "usable": "yes", "quality": 5}
        (self.lib / "tags" / "sample.jsonl").write_text(
            json.dumps(first) + "\n" + json.dumps(second) + "\n" + json.dumps({"id": "ghost", "kind": "broll"}) + "\nnope\n", encoding="utf-8")
        cat = catalog.build_catalog(self.lib)
        clip = next(c for c in cat["clips"] if c["id"] == first["id"])
        self.assertEqual((clip["usable"], clip["quality"]), ("yes", 5))
        self.assertEqual(cat["orphans"], ["ghost"])
        self.assertEqual(len(cat["tag_file_errors"]), 1)

    def test_overrides_narrow_freely_and_widen_only_with_consent(self):
        (self.lib / "overrides.json").write_text(json.dumps({
            "_about": "notes are ignored",
            "sunrise-swim-3f9a1c": {"usable": "no"},
            "market-walk-e4417b": {"usable": "yes"},
            "beach-kids-77bd3e": {"usable": "yes", "consent": "parent agreed by message"}}), encoding="utf-8")
        by = {c["id"]: c for c in catalog.build_catalog(self.lib)["clips"]}
        self.assertEqual(by["sunrise-swim-3f9a1c"]["usable"], "no")
        self.assertEqual(by["market-walk-e4417b"]["usable"], "no")
        self.assertEqual(by["beach-kids-77bd3e"]["usable"], "yes")

    def test_missing_worklist_gives_a_friendly_error(self):
        code, _, err = quiet(catalog.main, ["--library", str(self.d / "nowhere")])
        self.assertEqual(code, 2)
        self.assertIn("Run ingest.py", err)

    def test_cli_writes_catalog_json(self):
        code, out, _ = quiet(catalog.main, ["--library", str(self.lib)])
        self.assertEqual(code, 0)
        self.assertIn("12 clips in the library", out)
        self.assertEqual(json.loads((self.lib / "catalog.json").read_text(encoding="utf-8"))["summary"]["clips"], 12)


class TestSelects(unittest.TestCase):
    def test_only_usable_yes_clips_appear(self):
        cat = sample_catalog()
        md = selects.render_selects(cat)
        for c in cat["clips"]:
            self.assertEqual(c["name"] in md, c["usable"] == "yes", c["name"])
        self.assertIn("7 clips.", md)

    def test_ranked_broll_first_then_quality(self):
        rows = selects.pick(sample_catalog()["clips"])
        kinds = [c["kind"] for c in rows]
        self.assertEqual(kinds, sorted(kinds, key=lambda k: k != "broll"))
        broll_q = [c["quality"] for c in rows if c["kind"] == "broll"]
        self.assertEqual(broll_q, sorted(broll_q, reverse=True))
        self.assertEqual(rows[-1]["kind"], "talking_head")

    def test_filters(self):
        clips = sample_catalog()["clips"]
        self.assertTrue(all("calm" in c["mood"] for c in selects.pick(clips, mood="calm")))
        self.assertEqual([c["place"] for c in selects.pick(clips, place="beach_water")], ["beach_water"])
        self.assertEqual(len(selects.pick(clips, limit=3)), 3)
        self.assertTrue(all(c["quality"] >= 5 for c in selects.pick(clips, min_quality=5)))
        self.assertEqual(selects.pick(clips, role="opener")[0]["reel_role"], "opener")

    def test_empty_selects_says_what_to_do(self):
        md = selects.render_selects({"clips": [], "made": "2026-10-28"})
        self.assertIn("No clips match yet", md)

    def test_cli_and_no_em_dashes(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(SAMPLE, Path(d) / "lib")
            code, out, _ = quiet(selects.main, ["--library", str(Path(d) / "lib"), "--limit", "2"])
            self.assertEqual(code, 0)
            self.assertIn("(2 clips)", out)
            self.assertNotIn("—", (Path(d) / "lib" / "selects.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
