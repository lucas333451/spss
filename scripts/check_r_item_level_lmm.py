#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

REQUIRED_R_PACKAGES = [
    "optparse",
    "readr",
    "dplyr",
    "tidyr",
    "stringr",
    "lme4",
    "lmerTest",
    "emmeans",
    "jsonlite",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Check whether Rscript and required R packages are available for item-level unified LMM.")
    ap.add_argument("--rscript", default="Rscript", help="Rscript executable name or absolute path")
    args = ap.parse_args()

    rscript = shutil.which(args.rscript) or (args.rscript if shutil.which(args.rscript) else None)
    if not rscript:
        payload = {
            "ok": False,
            "reason": "Rscript_not_found",
            "required_packages": REQUIRED_R_PACKAGES,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    r_expr = (
        "pkgs <- c(" + ",".join([f'\"{p}\"' for p in REQUIRED_R_PACKAGES]) + ");"
        "missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)];"
        "cat(jsonlite::toJSON(list(ok=length(missing)==0, missing=missing, required=pkgs), auto_unbox=TRUE))"
    )
    p = subprocess.run([rscript, "-e", r_expr], capture_output=True, text=True)
    if p.returncode != 0:
        payload = {
            "ok": False,
            "reason": "R_check_failed",
            "stderr": p.stderr.strip(),
            "stdout": p.stdout.strip(),
            "required_packages": REQUIRED_R_PACKAGES,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return p.returncode

    sys.stdout.write(p.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
