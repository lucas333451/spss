#!/usr/bin/env python3
from __future__ import annotations

"""Orchestrator for research analyses.

Refactored structure:
- analysis_s_items.py  : S1-S5, Angle1/Angle2, 4-group split, group comparison, figures
- analysis_b_items.py  : B1-B3/Bmean focused analyses (mainly C1)
- report_summary.py    : narrative summary for quick interpretation

This file is kept as a compatibility entrypoint.
"""

from pathlib import Path
import argparse
import json
import subprocess
import sys


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main():
    ap = argparse.ArgumentParser(description="Research analysis orchestrator (compatible entrypoint)")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    run([
        args.python, "scripts/analysis_s_items.py",
        "--long-csv", str(args.long_csv),
        "--out-dir", str(out),
    ])

    run([
        args.python, "scripts/analysis_b_items.py",
        "--long-csv", str(args.long_csv),
        "--out-dir", str(out),
    ])

    run([
        args.python, "scripts/report_summary.py",
        "--long-csv", str(args.long_csv),
        "--research-dir", str(out),
        "--out", str(out / "analysis_narrative.md"),
    ])

    payload = {
        "entrypoint": "scripts/analyze_research_questions.py",
        "modules": [
            "scripts/analysis_s_items.py",
            "scripts/analysis_b_items.py",
            "scripts/report_summary.py",
        ],
        "out_dir": str(out),
        "outputs_hint": [
            "table_fixed_effects_all_dv.csv",
            "group_comparisons_item_level.csv",
            "groups/manifest.csv",
            "b_items_group_comparisons.csv",
            "analysis_narrative.md",
        ],
    }
    (out / "research_orchestrator_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
