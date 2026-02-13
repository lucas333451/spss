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

    run([
        args.python, "scripts/transform_wide_to_long.py",
        "--excel", str(args.excel),
        "--sheet", str(args.sheet),
        "--out-dir", str(out_long),
    ])

    run([
        args.python, "scripts/run_analysis.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out-dir", str(out_model),
    ])

    run([
        args.python, "scripts/analyze_research_questions.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out-dir", str(out_research),
    ])

    print("\nDone. Outputs:")
    print("-", out_long)
    print("-", out_model)
    print("-", out_research)


if __name__ == "__main__":
    main()
