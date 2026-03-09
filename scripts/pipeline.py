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
    ap = argparse.ArgumentParser(description="Clean pipeline: wide Excel -> long -> descriptive + significance (overall + experience)")
    ap.add_argument("--excel", required=True, type=Path)
    ap.add_argument("--sheet", default="0")
    ap.add_argument("--out-root", default=Path("results"), type=Path)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--skip-descriptive", action="store_true")
    ap.add_argument("--skip-significance", action="store_true")
    ap.add_argument("--with-qc", action="store_true", help="Also export QC-excluded descriptive/significance outputs")
    args = ap.parse_args()

    out_long = args.out_root / "long"
    out_desc = args.out_root / "descriptive"
    out_sig = args.out_root / "significance"

    run([
        args.python, "scripts/transform_wide_to_long.py",
        "--excel", str(args.excel),
        "--sheet", str(args.sheet),
        "--out-dir", str(out_long),
    ])

    if not args.skip_descriptive:
        cmd = [
            args.python, "scripts/descriptive_pipeline.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_desc),
        ]
        if args.with_qc:
            cmd.append("--with-qc")
        run(cmd)

    if not args.skip_significance:
        cmd = [
            args.python, "scripts/significance_pipeline.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_sig),
            "--python", args.python,
        ]
        if args.with_qc:
            cmd.append("--with-qc")
        run(cmd)

    run([
        args.python, "scripts/build_results_guide.py",
        "--out-root", str(args.out_root),
    ])


if __name__ == "__main__":
    main()
