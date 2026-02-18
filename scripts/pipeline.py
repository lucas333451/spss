#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main():
    ap = argparse.ArgumentParser(description="One-click pipeline: wide Excel -> long -> model -> research analysis")
    ap.add_argument("--excel", required=True, type=Path)
    ap.add_argument("--sheet", default="0")
    ap.add_argument("--out-root", default=Path("results"), type=Path)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    out_long = args.out_root / "long"
    out_model = args.out_root / "model"
    out_research = args.out_root / "research"
    out_diag = args.out_root / "diagnostics"

    run([
        args.python, "scripts/transform_wide_to_long.py",
        "--excel", str(args.excel),
        "--sheet", str(args.sheet),
        "--out-dir", str(out_long),
    ])

    # keep existing core model workflow
    run([
        args.python, "scripts/run_analysis.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out-dir", str(out_model),
    ])

    # keep existing research workflow
    run([
        args.python, "scripts/analyze_research_questions.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out-dir", str(out_research),
    ])

    # diagnostics workflow for model-source and robustness checks
    run([
        args.python, "scripts/diagnostics_lmm.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out-dir", str(out_diag),
    ])

    # build one markdown bundle for easy sharing/review
    run([
        args.python, "scripts/build_report_md.py",
        "--results-root", str(args.out_root),
        "--out", str(args.out_root / "analysis_report_bundle.md"),
    ])

    print("\nDone. Outputs:")
    print("-", out_long)
    print("-", out_model)
    print("-", out_research)
    print("-", out_diag)


if __name__ == "__main__":
    main()
