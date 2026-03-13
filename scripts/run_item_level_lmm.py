#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Python wrapper for the item-level / dimension-level unified LMM R pipeline "
            "(S1-S5, B1-B3, IPQ items/dimensions; fixed effects kept consistent across DVs)."
        )
    )
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/significance/item_level_lmm"))
    ap.add_argument("--exclude-subjects", default="")
    ap.add_argument("--p-adjust", default="fdr")
    ap.add_argument("--df-method", default="Satterthwaite")
    ap.add_argument("--rscript", default="Rscript", help="Rscript executable name or absolute path")
    args = ap.parse_args()

    rscript = shutil.which(args.rscript) if not Path(args.rscript).exists() else args.rscript
    if not rscript:
        raise SystemExit(
            "Rscript not found. Please install R or provide --rscript <path>. "
            "This unified item-level LMM branch depends on the R stack: lme4, lmerTest, emmeans, readr, dplyr, tidyr, stringr, jsonlite."
        )

    script_path = Path(__file__).with_name("run_item_level_lmm_R.R")
    cmd = [
        str(rscript),
        str(script_path),
        "--long-csv", str(args.long_csv),
        "--out-dir", str(args.out_dir),
        "--exclude-subjects", str(args.exclude_subjects),
        "--p-adjust", str(args.p_adjust),
        "--df-method", str(args.df_method),
    ]
    p = subprocess.run(cmd)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
