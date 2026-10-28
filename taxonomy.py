"""The taxonomy: load it, check a tag line against it, and apply the privacy gate.

A tag line is one JSON object per clip, written by a tagger (Claude looking at the key frames).
check_tags() returns the problems; clean_tags() returns a safe record:
  - usable starts at "no"; a missing or odd value is "no"
  - a clip marked kind "unusable" can never be usable
  - the consent gate turns a yes on screen recordings, other people or children into "no"
  - only overrides.json (a person's decision, with a consent note) can lift the gate
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAXONOMY_PATH = HERE / "taxonomy.json"


def load_taxonomy(path: Path | None = None) -> dict:
    data = json.loads(Path(path or TAXONOMY_PATH).read_text(encoding="utf-8"))
    if not isinstance(data.get("fields"), dict) or not data["fields"]:
        raise ValueError("taxonomy has no fields")
    for name, spec in data["fields"].items():
        if spec.get("type") not in ("enum", "list", "bool", "int", "text"):
            raise ValueError(f"field {name}: unknown type {spec.get('type')!r}")
        if spec["type"] in ("enum", "list") and not spec.get("values"):
            raise ValueError(f"field {name}: needs values")
    if "usable" not in data["fields"]:
        raise ValueError("taxonomy must have a usable field (the privacy gate)")
    return data


def norm(v: object) -> str:
    return str(v).strip().lower().replace("-", "_").replace(" ", "_") if v is not None else ""


def check_tags(rec: dict, tax: dict) -> list[str]:
    """Every problem with one tag line, in plain words. An empty list means it is clean."""
    problems = []
    if not isinstance(rec, dict):
        return ["not a JSON object"]
    for key in tax.get("required", []):
        if rec.get(key) in (None, ""):
            problems.append(f"missing {key}")
    for name, spec in tax["fields"].items():
        if name not in rec or rec[name] is None:
            continue
        v, t = rec[name], spec["type"]
        if t == "enum" and norm(v) not in spec["values"]:
            problems.append(f"{name}: {v!r} is not one of {', '.join(spec['values'])}")
        elif t == "list":
            if not isinstance(v, list):
                problems.append(f"{name}: should be a list")
                continue
            bad = [x for x in v if norm(x) not in spec["values"]]
            if bad:
                problems.append(f"{name}: {', '.join(map(str, bad))} not in the list")
            if spec.get("max") and len(v) > spec["max"]:
                problems.append(f"{name}: at most {spec['max']}")
        elif t == "bool" and not isinstance(v, bool):
            problems.append(f"{name}: should be true or false")
        elif t == "int":
            if not isinstance(v, int) or isinstance(v, bool) or not spec.get("min", v) <= v <= spec.get("max", v):
                problems.append(f"{name}: should be a whole number {spec.get('min')} to {spec.get('max')}")
        elif t == "text" and not isinstance(v, str):
            problems.append(f"{name}: should be text")
    return problems


def needs_consent(rec: dict, tax: dict) -> bool:
    gate = tax.get("consent_gate") or {}
    return (norm(rec.get("kind")) in gate.get("kinds", [])
            or norm(rec.get("people_present")) in gate.get("people", []))


def clean_tags(rec: dict, tax: dict, override: dict | None = None) -> dict:
    """A safe catalog record. Bad enum values are dropped, usable is no unless earned."""
    out = {"id": str(rec.get("id", "")).strip()}
    for name, spec in tax["fields"].items():
        v, t = rec.get(name), spec["type"]
        if t == "enum":
            v = norm(v) if norm(v) in spec["values"] else spec.get("default")
        elif t == "list":
            v = [norm(x) for x in v if norm(x) in spec["values"]][: spec.get("max") or None] if isinstance(v, list) else []
        elif t == "bool":
            v = v if isinstance(v, bool) else False
        elif t == "int":
            ok = isinstance(v, int) and not isinstance(v, bool) and spec.get("min", v) <= v <= spec.get("max", v)
            v = v if ok else None
        elif t == "text":
            v = str(v or "").strip()[: spec.get("max_len", 500)]
        out[name] = v
    if out.get("usable") not in ("yes", "no"):
        out["usable"] = "no"
    out["consent_needed"] = needs_consent(out, tax)
    out["gate"] = ""
    if out["consent_needed"] and out["usable"] == "yes":
        out["usable"] = "no"
        out["gate"] = "consent needed"
    if out.get("kind") == "unusable" and out["usable"] == "yes":
        out["usable"], out["gate"] = "no", "marked unusable"
    if override:
        out = apply_override(out, override)
    return out


def apply_override(rec: dict, ov: dict) -> dict:
    """A person's decision. Narrowing is always allowed. Widening a consent clip needs a consent note."""
    rec = dict(rec)
    want = norm(ov.get("usable"))
    if want == "no":
        rec["usable"], rec["gate"] = "no", "you said no"
    elif want == "yes":
        consent = str(ov.get("consent") or "").strip()
        if rec.get("consent_needed") and not consent:
            rec["usable"], rec["gate"] = "no", "consent needed (override has no consent note)"
        else:
            rec["usable"], rec["gate"] = "yes", ""
            if consent:
                rec["consent"] = consent
    for k in ("notes", "reel_role", "quality"):
        if k in ov:
            rec[k] = ov[k]
    return rec


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            rows.append({"_error": f"{Path(path).name} line {n}: not JSON ({exc.msg})"})
    return rows


def main(argv: list[str] | None = None) -> int:
    """Check a tag file: python3 taxonomy.py library/tags/batch-001.jsonl"""
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python3 taxonomy.py <tags.jsonl> [more.jsonl]")
        return 2
    tax, bad, total = load_taxonomy(), 0, 0
    for name in args:
        try:
            rows = load_jsonl(Path(name))
        except OSError as exc:
            print(f"{name}: could not read ({exc})")
            return 2
        for n, rec in enumerate(rows, 1):
            total += 1
            problems = [rec["_error"]] if "_error" in rec else check_tags(rec, tax)
            if problems:
                bad += 1
                print(f"{Path(name).name} line {n} ({rec.get('id', '?')}): " + "; ".join(problems))
    print(f"{total} tag lines checked, {bad} with problems." if bad else f"{total} tag lines checked, all clean.")
    return 1 if bad else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
