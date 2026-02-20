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
    ap.add_argument("--skip-model", action="store_true", help="Skip scripts/run_analysis.py")
    ap.add_argument("--skip-research", action="store_true", help="Skip research modules")
    ap.add_argument("--skip-diagnostics", action="store_true", help="Skip scripts/diagnostics_lmm.py")
    ap.add_argument("--skip-bundle", action="store_true", help="Skip scripts/build_report_md.py")
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

    if not args.skip_model:
        # keep existing core model workflow
        run([
            args.python, "scripts/run_analysis.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_model),
        ])

    if not args.skip_research:
        # research workflow (modular)
        run([
            args.python, "scripts/analysis_s_items.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_research),
        ])
        run([
            args.python, "scripts/analysis_b_items.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_research),
        ])
        run([
            args.python, "scripts/report_summary.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--research-dir", str(out_research),
            "--out", str(out_research / "analysis_narrative.md"),
        ])

    if not args.skip_diagnostics:
        # diagnostics workflow for model-source and robustness checks
        run([
            args.python, "scripts/diagnostics_lmm.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_diag),
        ])

    if not args.skip_bundle:
        # build one markdown bundle for easy sharing/review
        run([
            args.python, "scripts/build_report_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_bundle.md"),
        ])

        # build a detailed key-results bundle (more focused + richer detail)
        run([
            args.python, "scripts/build_report_key_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_key.md"),
            "--max-rows", "5000",
        ])

        # build data-first report (tables embedded directly, minimal index dependency)
        run([
            args.python, "scripts/build_report_data_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_data.md"),
            "--max-rows", "5000",
        ])

    print("\nDone. Outputs:")
    print("-", out_long)
    print("-", out_model)
    print("-", out_research)
    print("-", out_diag)


if __name__ == "__main__":
    main()
