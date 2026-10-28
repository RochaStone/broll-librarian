"""The model-eval scorer, and the house rules for shipped text. Run from the repo root: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import catalog  # noqa: E402
import scorer  # noqa: E402
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


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.res = scorer.compare(FIX / "director.jsonl", [FIX / "crew-small.jsonl", FIX / "crew-mid.jsonl"])
        self.small, self.mid = self.res["candidates"]

    def test_two_tiers_against_the_director(self):
        self.assertFalse(self.small["pass"])
        self.assertTrue(self.mid["pass"])
        self.assertEqual(self.res["pick"], "crew-mid")

    def test_per_field_agreement(self):
        f = self.mid["result"]["fields"]
        self.assertEqual(f["kind"]["agree"], 1.0)
        self.assertEqual(f["place"]["hits"], 11)
        self.assertEqual(f["quality"]["agree"], round(11 / 12, 3))
        self.assertEqual(self.mid["result"]["quality_within_one"], 1.0)
        self.assertEqual(self.small["result"]["fields"]["people_present"]["hits"], 9)
        self.assertNotIn("notes", f)

    def test_a_leak_past_the_privacy_gate_fails_a_model(self):
        leaks = self.small["result"]["permissive_usable_errors"]
        self.assertEqual([x["id"] for x in leaks], ["beach-kids-77bd3e"])
        self.assertTrue(any("kept private" in w for w in self.small["why"]))
        self.assertEqual(self.mid["result"]["permissive_usable_errors"], [])

    def test_coverage_counts_clips_the_model_skipped(self):
        self.assertEqual(self.small["result"]["labelled"], 11)
        self.assertEqual(len(self.small["result"]["missing"]), 1)
        self.assertTrue(any("11 of 12" in w for w in self.small["why"]))

    def test_advisory_fields_never_gate(self):
        self.assertLess(self.mid["result"]["fields"]["reel_role"]["agree"], 1.0)
        self.assertLess(self.mid["result"]["mood_overlap"], 1.0)
        self.assertTrue(self.mid["pass"])

    def test_the_strict_side_of_usable_only(self):
        truth = {"a": {"id": "a", "usable": "yes"}}
        cand = {"a": {"id": "a", "usable": "no"}}
        self.assertEqual(scorer.score(truth, cand, TAX)["permissive_usable_errors"], [])

    def test_cli_exit_codes_and_report(self):
        code, out, _ = quiet(scorer.main, ["--truth", str(FIX / "director.jsonl"), str(FIX / "crew-small.jsonl"), str(FIX / "crew-mid.jsonl")])
        self.assertEqual(code, 0)
        self.assertIn("crew-small: FAIL", out)
        self.assertIn("crew-mid: PASS", out)
        self.assertIn("would leak past the gate", out)
        self.assertIn("Use for the fleet: crew-mid", out)
        code, out, _ = quiet(scorer.main, ["--truth", str(FIX / "director.jsonl"), str(FIX / "crew-small.jsonl")])
        self.assertEqual(code, 1)
        self.assertIn("No crew model passed", out)
        code, _, err = quiet(scorer.main, ["--truth", str(FIX / "missing.jsonl"), str(FIX / "crew-mid.jsonl")])
        self.assertEqual(code, 2)
        self.assertIn("Could not score", err)

    def test_fixture_tag_lines_are_all_valid(self):
        for name in ("director", "crew-small", "crew-mid"):
            for rec in taxonomy.load_jsonl(FIX / f"{name}.jsonl"):
                self.assertEqual(taxonomy.check_tags(rec, TAX), [], f"{name}: {rec.get('id')}")


class TestShippedText(unittest.TestCase):
    """House rules that apply to every file we ship."""

    FILES = ["README.md", "SKILL.md", "STYLE.md", "prompts/tag-clips.md", "docs/IMAGES.md", "tests/TESTING.md"]

    def texts(self):
        for rel in self.FILES + [p.relative_to(ROOT).as_posix() for p in ROOT.glob("*.py")]:
            path = ROOT / rel
            if path.is_file():
                yield rel, path.read_text(encoding="utf-8")

    def test_no_em_dashes_no_banned_words(self):
        for rel, text in self.texts():
            self.assertNotIn("—", text, f"em dash in {rel}")
            self.assertIsNone(re.search(r"\b(simply|just)\b", text, re.I), f"banned word in {rel}")
            self.assertNotIn("/Users/", text, rel)

    def test_readme_footer_is_exact(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        brand = ("## Made by Rocha\n\nRocha \\\nBrand Alchemist & AI Architect \\\nAuthor of *Brand Alchemy in the Thriving Era* \\\n"
                 "Creator of [Conscious Founder Operating System](https://founders.thrivingera.com) \\\nFounder, [Thriving Era Studio](https://thrivingera.com)\n\n"
                 "I help female founders build their founder world, and I build what they need next. \\\nStart with the audit: [thrivingera.com/audit](https://thrivingera.com/audit). \\\n"
                 "Or book an exploratory call: [calendly.com/rochelle-thrivingera/exploratory-call](https://calendly.com/rochelle-thrivingera/exploratory-call). "
                 "It is where we decide if we work together.\n\n"
                 "[Instagram @rocheverse](https://instagram.com/rocheverse) · [Substack](https://rochastone.substack.com) · "
                 "[LinkedIn](https://www.linkedin.com/in/rochellelivingstonecosmic) · [More free tools](https://thrivingera.com/free) · "
                 "[All tools on GitHub](https://github.com/RochaStone)")
        self.assertTrue(readme.rstrip().endswith(brand))
        self.assertIn("[Sign my guestbook](https://github.com/RochaStone/broll-librarian/issues)", readme)

    def test_style_example_is_identical_to_the_collection_copy(self):
        ref = ROOT.parent / "ai-recommends-you" / "examples" / "style.rocha-coded.json"
        if ref.is_file():
            self.assertEqual(style.STYLE_EXAMPLE.read_bytes(), ref.read_bytes())

    def test_skill_md_has_the_front_matter_and_the_privacy_gate(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: broll-librarian\ndescription: "))
        self.assertIn("privacy gate", skill.lower())
        self.assertIn("one question at a time", skill.lower())

    def test_no_media_is_shipped(self):
        listed = (ROOT / "docs" / "IMAGES.md").read_text(encoding="utf-8")
        for p in ROOT.rglob("*"):
            if p.is_file() and ".git" not in p.parts and "dist" not in p.parts:
                self.assertNotIn(p.suffix.lower(), {".mov", ".mp4", ".m4v", ".jpg", ".jpeg", ".heic", ".webm"}, str(p))
                if p.suffix.lower() == ".png":
                    self.assertIn(p.relative_to(ROOT).as_posix(), listed, str(p))

if __name__ == "__main__":
    unittest.main()
