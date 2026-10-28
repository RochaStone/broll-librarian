"""Model-eval scorer: compare a crew model's tags with the director's, field by field.

The director (your most capable model) tags a sample. Each crew model (cheaper) tags the same
sample blind. This scores per-field agreement and gives each crew model a PASS or FAIL against
the eval_gate in taxonomy.json. The usable field is held strictest: a crew model that says yes
where the director said no would leak a clip past the privacy gate, so even one fails it.

  python3 scorer.py --truth director.jsonl crew-a.jsonl crew-b.jsonl

List crew files cheapest first. The recommendation is the cheapest one that passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from taxonomy import load_jsonl, load_taxonomy, norm

STRICT = {"yes": 0, "no": 1}


def _by_id(rows: list[dict]) -> dict:
    return {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id") and "_error" not in r}


def score(truth: dict, cand: dict, tax: dict) -> dict:
    """Agreement per field, mood overlap, and the dangerous usable disagreements."""
    ids = [i for i in truth if i in cand]
    n = len(ids) or 1
    fields = {}
    for name, spec in tax["fields"].items():
        if spec["type"] in ("text",) or name == "mood":
            continue
        hits, diffs = 0, []
        for i in ids:
            g, c = truth[i].get(name), cand[i].get(name)
            same = (g == c) if spec["type"] in ("bool", "int") else norm(g) == norm(c)
            if same:
                hits += 1
            else:
                diffs.append({"id": i, "director": g, "crew": c})
        fields[name] = {"agree": round(hits / n, 3), "hits": hits, "diffs": diffs}
    near = sum(1 for i in ids if isinstance(truth[i].get("quality"), int) and isinstance(cand[i].get("quality"), int)
               and abs(truth[i]["quality"] - cand[i]["quality"]) <= 1)
    jacc = []
    for i in ids:
        g = {norm(x) for x in truth[i].get("mood") or []}
        c = {norm(x) for x in cand[i].get("mood") or []}
        jacc.append(len(g & c) / len(g | c) if g | c else 1.0)
    permissive = [{"id": i, "director": truth[i].get("usable"), "crew": cand[i].get("usable")} for i in ids
                  if STRICT.get(norm(cand[i].get("usable")), 1) < STRICT.get(norm(truth[i].get("usable")), 1)]
    return {"labelled": len(ids), "total": len(truth), "coverage": round(len(ids) / (len(truth) or 1), 3),
            "missing": [i for i in truth if i not in cand], "fields": fields,
            "quality_within_one": round(near / n, 3), "mood_overlap": round(sum(jacc) / (len(jacc) or 1), 3),
            "permissive_usable_errors": permissive}


def verdict(result: dict, gate: dict) -> tuple[bool, list[str]]:
    """PASS only if every line of the gate holds. Returns the reasons it failed."""
    why = []
    if result["coverage"] < gate.get("coverage", 1.0):
        why.append(f"tagged {result['labelled']} of {result['total']} clips")
    for f in ("kind", "people_present", "place", "usable"):
        if f in gate and result["fields"].get(f, {}).get("agree", 0) < gate[f]:
            why.append(f"{f} agreement {result['fields'][f]['agree']:.0%} is under {gate[f]:.0%}")
    if "quality_within_one" in gate and result["quality_within_one"] < gate["quality_within_one"]:
        why.append(f"quality within one point {result['quality_within_one']:.0%} is under {gate['quality_within_one']:.0%}")
    if len(result["permissive_usable_errors"]) > gate.get("permissive_usable_errors", 0):
        why.append(f"{len(result['permissive_usable_errors'])} clip(s) marked usable that the director kept private")
    return not why, why


def report(label: str, result: dict, ok: bool, why: list[str]) -> str:
    lines = [f"{label}: {'PASS' if ok else 'FAIL'} ({result['labelled']}/{result['total']} clips tagged)"]
    for name, f in result["fields"].items():
        lines.append(f"  {name:<15} {f['hits']}/{result['labelled']}  ({f['agree']:.0%})")
    lines.append(f"  {'quality ±1':<15} {result['quality_within_one']:.0%}")
    lines.append(f"  {'mood overlap':<15} {result['mood_overlap']:.2f} (advisory)")
    lines.append(f"  usable leaks     {len(result['permissive_usable_errors'])}")
    for d in result["permissive_usable_errors"]:
        lines.append(f"      {d['id']}: director={d['director']} crew={d['crew']}  <- would leak past the gate")
    for w in why:
        lines.append(f"  why it failed: {w}")
    return "\n".join(lines)


def compare(truth_path: Path, cand_paths: list[Path], tax: dict | None = None) -> dict:
    tax = tax or load_taxonomy()
    truth = _by_id(load_jsonl(truth_path))
    if not truth:
        raise ValueError(f"{truth_path} has no tagged clips")
    out = {"truth": str(truth_path), "candidates": [], "pick": None}
    for p in cand_paths:
        res = score(truth, _by_id(load_jsonl(p)), tax)
        ok, why = verdict(res, tax.get("eval_gate", {}))
        out["candidates"].append({"file": str(p), "label": Path(p).stem, "pass": ok, "why": why, "result": res})
        if ok and out["pick"] is None:
            out["pick"] = Path(p).stem
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score crew-model tags against the director's tags.")
    ap.add_argument("--truth", required=True, type=Path, help="the director's tags (jsonl)")
    ap.add_argument("candidates", nargs="+", type=Path, help="crew tags (jsonl), cheapest first")
    ap.add_argument("--json", type=Path, help="also write the full result here")
    a = ap.parse_args(argv)
    try:
        res = compare(a.truth, a.candidates)
    except (OSError, ValueError) as exc:
        print(f"Could not score: {exc}", file=sys.stderr)
        return 2
    for c in res["candidates"]:
        print(report(c["label"], c["result"], c["pass"], c["why"]) + "\n")
    print(f"Use for the fleet: {res['pick']}" if res["pick"] else
          "No crew model passed. Keep the director tagging, or tighten the prompt and try again.")
    if a.json:
        a.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0 if res["pick"] else 1


if __name__ == "__main__":
    sys.exit(main())
