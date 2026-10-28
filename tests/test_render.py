"""The three motifs, and the style file. Run from the repo root: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import catalog  # noqa: E402
import frames  # noqa: E402
import library_render as lib  # noqa: E402
import style  # noqa: E402
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


class TestMotifs(unittest.TestCase):
    """One render path, three skins. Each has its signature marker."""

    @classmethod
    def setUpClass(cls):
        cls.cat = sample_catalog()
        cls.style = style.load_style(style.STYLE_EXAMPLE)
        cls.pages = {m: lib.render_library(cls.cat, cls.style, m) for m in lib.MOTIFS}

    def test_analog_marker(self):
        p = self.pages["analog"]
        self.assertIn("CONTACT SHEET", p)
        self.assertIn("m-analog", p)
        self.assertIn('class="tape"', p)
        self.assertNotIn("rocheverse:~$", p)
        self.assertNotIn("000,777", p)

    def test_cyberpunk_marker(self):
        p = self.pages["cyberpunk"]
        self.assertIn("rocheverse:~$", p)
        self.assertIn('class="cursor"', p)
        self.assertIn("Silkscreen", p)
        self.assertIn("[01]", p)
        self.assertNotIn("CONTACT SHEET", p)

    def test_y2k_marker(self):
        p = self.pages["y2k-blog"]
        self.assertIn("broll-librarian.exe", p)
        self.assertIn("000,777", p)
        self.assertIn("sign my guestbook", p)
        self.assertIn("github.com/RochaStone/broll-librarian/issues", p)
        self.assertIn("mood", p)
        self.assertIn("Silkscreen", p)

    def test_same_clips_in_every_motif(self):
        for motif, page in self.pages.items():
            self.assertEqual(page.count('class="clip"'), 12, motif)
            for c in self.cat["clips"]:
                self.assertIn(c["name"], page, motif)
            self.assertEqual(page.count('class="pill yes"'), 7, motif)
            self.assertEqual(page.count('class="pill no"'), 5, motif)

    def test_privacy_states_are_shown(self):
        page = self.pages["analog"]
        self.assertIn("keep private", page)
        self.assertIn("consent needed", page)
        self.assertIn("ok to post", page)

    def test_motif_choice_order_and_aliases(self):
        s = {"motif": "cyberpunk"}
        self.assertEqual(style.resolve_motif("y2k-blog", s), "y2k-blog")
        self.assertEqual(style.resolve_motif(None, s), "cyberpunk")
        self.assertEqual(style.resolve_motif(None, {}), "analog")
        self.assertEqual(style.resolve_motif("nonsense", {}), "analog")
        for old, new in (("guest-check", "analog"), ("retro-tv", "cyberpunk"), ("sticker-collage", "y2k-blog")):
            self.assertEqual(style.resolve_motif(old, {}), new)

    def test_card_is_fixed_size_and_limited(self):
        for motif, n in lib.CARD_CLIPS.items():
            page = lib.render_library(self.cat, self.style, motif, card=True)
            self.assertIn("body class=\"card", page)
            self.assertEqual(page.count('class="clip"'), n, motif)
            self.assertNotIn("<script>", page)

    def test_page_has_filters_and_script_and_phone_width_rules(self):
        for motif, page in self.pages.items():
            self.assertIn('data-group="usable"', page)
            self.assertIn('id="find"', page)
            self.assertIn("<script>", page)
            self.assertIn("@media (max-width", page)
            self.assertIn('name="viewport"', page)

    def test_everything_user_supplied_is_escaped(self):
        cat = json.loads(json.dumps(self.cat))
        cat["clips"][0]["name"] = '<script>alert("x")</script>.mov'
        cat["clips"][0]["notes"] = '"><img src=x onerror=alert(1)>'
        st = {**self.style, "owner": "<b>Me</b>", "lines": {"scrawl": "<i>hi</i>"}}
        for motif in lib.MOTIFS:
            page = lib.render_library(cat, st, motif)
            self.assertNotIn('<script>alert("x")', page)
            self.assertNotIn("<img src=x", page)
            self.assertNotIn("<b>Me</b>", page)
            self.assertNotIn("<i>hi</i>", page)

    def test_untagged_clips_render(self):
        cat = {"made": "2026-10-28", "summary": {"clips": 1, "tagged": 0, "usable_yes": 0, "consent_needed": 0},
               "clips": [{"id": "x", "name": "x.mov", "frames": [], "tagged": False, "usable": "no", "gate": "not tagged yet", "duration": 4.0}]}
        for motif in lib.MOTIFS:
            page = lib.render_library(cat, self.style, motif)
            self.assertIn("not tagged", page)
            self.assertIn("no frame", page)

    def test_empty_library_renders(self):
        for motif in lib.MOTIFS:
            self.assertIn("No clips yet", lib.render_library({"clips": []}, self.style, motif))

    def test_thumbnail_paths_are_relative_and_quoted(self):
        clip = {"id": "x", "name": "x.mov", "frames": ["frames/a b/s01.jpg", "frames/a b/s02.jpg", "frames/a b/s03.jpg"]}
        self.assertEqual(lib.thumb_path(clip), "frames/a b/s02.jpg")
        page = lib.render_library({"clips": [clip]}, self.style, "analog")
        self.assertIn('src="frames/a%20b/s02.jpg"', page)

    def test_no_glow_or_coloured_shadow_in_any_stylesheet(self):
        for css in (ROOT / "assets").glob("*.css"):
            text = css.read_text(encoding="utf-8")
            self.assertNotIn("text-shadow", text, css.name)
            self.assertNotIn("drop-shadow", text, css.name)
            for shadow in re.findall(r"box-shadow:([^;]+);", text):
                self.assertNotRegex(shadow, r"#[0-9A-Fa-f]{3,6}\b(?!.*inset)", f"{css.name}: coloured shadow {shadow}")

    def test_cli_motif_flag_and_alias(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(SAMPLE, Path(d) / "lib")
            for flag, marker in (("analog", "CONTACT SHEET"), ("cyberpunk", "rocheverse:~$"), ("y2k-blog", "000,777"), ("retro-tv", "rocheverse:~$")):
                code, out, _ = quiet(lib.main, ["--library", str(Path(d) / "lib"), "--motif", flag])
                self.assertEqual(code, 0)
                self.assertIn(marker, (Path(d) / "lib" / "library.html").read_text(encoding="utf-8"), flag)

    def test_no_chrome_degrades_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(SAMPLE, Path(d) / "lib")
            with mock.patch.object(lib, "find_chrome", return_value=None):
                code, out, _ = quiet(lib.main, ["--library", str(Path(d) / "lib"), "--png"])
            self.assertEqual(code, 1)
            self.assertIn("No Chrome or Chromium found", out)
            self.assertTrue((Path(d) / "lib" / "library.html").is_file())


class TestStyle(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.example = json.loads(style.STYLE_EXAMPLE.read_text(encoding="utf-8"))

    def test_bundled_files_share_keys(self):
        blank = json.loads((ROOT / "style.example.json").read_text(encoding="utf-8"))
        for key in self.example:
            self.assertIn(key, blank)
        self.assertEqual(set(self.example["palette"]), set(blank["palette"]))
        self.assertEqual(set(self.example["fonts"]), set(blank["fonts"]))
        self.assertEqual(self.example["motif"], "analog")

    def test_example_matches_the_collection_tokens(self):
        self.assertEqual(self.example["palette"]["hero"], "#50163C")
        self.assertEqual(self.example["palette"]["accent"], "#FE9DCA")
        self.assertEqual(self.example["fonts"]["masthead"], "Fraunces")

    def test_fallback_order(self):
        cwd, home = self.d / "cwd", self.d / "home"
        (home / ".rocha-coded").mkdir(parents=True)
        cwd.mkdir()
        self.assertEqual(style.find_style(None, cwd, home), style.STYLE_EXAMPLE)
        (home / ".rocha-coded" / "style.json").write_text("{}", encoding="utf-8")
        self.assertEqual(style.find_style(None, cwd, home), home / ".rocha-coded" / "style.json")
        (cwd / "style.json").write_text("{}", encoding="utf-8")
        self.assertEqual(style.find_style(None, cwd, home), cwd / "style.json")
        mine = self.d / "mine.json"
        mine.write_text("{}", encoding="utf-8")
        self.assertEqual(style.find_style(mine, cwd, home), mine)

    def test_inheritance_rule(self):
        mine = {"name": "Sea Studio", "owner": "Mina", "handle": "@sea", "palette": {"hero": "#102030", "accent": ""},
                "fonts": {"masthead": "Bodoni Moda"}, "lines": {}, "notes": "", "references": []}
        p = self.d / "style.json"
        p.write_text(json.dumps(mine), encoding="utf-8")
        got = style.load_style(p)
        self.assertEqual(got["palette"]["hero"], "#102030")                      # hers
        self.assertEqual(got["palette"]["accent"], self.example["palette"]["accent"])  # borrowed palette
        self.assertEqual(got["fonts"]["masthead"], "Bodoni Moda")
        self.assertEqual(got["fonts"]["label"], self.example["fonts"]["label"])    # borrowed font
        self.assertEqual((got["owner"], got["handle"], got["name"]), ("Mina", "@sea", "Sea Studio"))
        self.assertEqual(got["lines"], {})            # lines never fall back to Rocha's
        self.assertEqual(got["notes"], "")
        self.assertEqual(got["references"], [])
        sparse = {"palette": {}, "fonts": {}}
        p.write_text(json.dumps(sparse), encoding="utf-8")
        got = style.load_style(p)
        for key in ("owner", "handle", "name", "lines", "references", "notes"):
            self.assertNotIn(key, got, key)

    def test_her_words_never_reach_the_page_unless_the_whole_example_is_used(self):
        cat = sample_catalog()
        p = self.d / "style.json"
        p.write_text(json.dumps({"owner": "Mina", "palette": {}, "fonts": {}}), encoding="utf-8")
        mine = lib.render_library(cat, style.load_style(p), "analog")
        self.assertNotIn("BUILD YOUR FOUNDER WORLD", mine.upper())
        self.assertNotIn("@rocheverse", mine)
        self.assertIn("Mina", mine)
        theirs = lib.render_library(cat, style.load_style(style.STYLE_EXAMPLE), "analog")
        self.assertIn("build your founder world", theirs.lower())

    def test_second_palette_and_fonts_retone_all_motifs(self):
        cat = sample_catalog()
        st = style.inherit_style({"palette": {"hero": "#0A2540", "accent": "#00B3A4"}, "fonts": {"masthead": "Bodoni Moda", "mono": "IBM Plex Mono"}})
        for motif in lib.MOTIFS:
            page = lib.render_library(cat, st, motif)
            self.assertIn("--ground: #0A2540;", page, motif)
            self.assertIn("--candy: #00B3A4;", page, motif)
            self.assertIn('--serif: "Bodoni Moda"', page, motif)
            self.assertIn("family=Bodoni+Moda", page, motif)

    def test_bad_colour_and_font_values_are_not_injected(self):
        st = style.inherit_style({"palette": {"hero": "red; } body { display:none", "accent": "javascript:1"},
                                  "fonts": {"masthead": "x\"/><script>alert(1)</script>"}})
        page = lib.render_library(sample_catalog(), st, "analog")
        self.assertNotIn("display:none", page)
        self.assertNotIn("javascript:1", page)
        self.assertNotIn("<script>alert(1)", page)

    def test_unreadable_style_file_falls_back_kindly(self):
        p = self.d / "style.json"
        p.write_text("{not json", encoding="utf-8")
        code_err = io.StringIO()
        with contextlib.redirect_stderr(code_err):
            got = style.load_style(p)
        self.assertIn("Could not read style file", code_err.getvalue())
        self.assertEqual(got["palette"]["hero"], "#50163C")

if __name__ == "__main__":
    unittest.main()
