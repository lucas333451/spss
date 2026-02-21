#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except Exception:
        return None


def _pkg_version(name: str) -> str | None:
    try:
        import importlib.metadata as md
        return md.version(name)
    except Exception:
        return None


def build_provenance(*, results_root: Path, excel: str | None, sheet: str | None, argv: list[str]) -> dict:
    py_packages = [
        "pandas",
        "numpy",
        "openpyxl",
        "statsmodels",
        "scipy",
        "pingouin",
        "seaborn",
        "matplotlib",
        "pyyaml",
        "tabulate",
    ]

    pkg_versions = {p: _pkg_version(p) for p in py_packages}

    git_commit = _run(["git", "rev-parse", "HEAD"])
    git_status = _run(["git", "status", "--porcelain"])  # empty means clean

    r_version = _run(["R", "--version"]) or _run(["Rscript", "--version"])

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "timestamp_utc": now_iso,
        "results_root": str(results_root),
        "inputs": {
            "excel": excel,
            "sheet": sheet,
        },
        "argv": argv,
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "git": {
            "commit": git_commit,
            "status_porcelain": git_status,
            "is_clean": (git_status == ""),
        },
        "python_packages": pkg_versions,
        "r": {
            "version": r_version,
            "note": "R packages are installed/managed via CRAN in Colab; see docs/COLAB_GUIDE.md",
        },
        "env": {
            "COLAB_RELEASE_TAG": os.environ.get("COLAB_RELEASE_TAG"),
            "KAGGLE_URL_BASE": os.environ.get("KAGGLE_URL_BASE"),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Write results/provenance.json for reproducibility")
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--excel", type=str, default=None)
    ap.add_argument("--sheet", type=str, default=None)
    ap.add_argument("--out", type=Path, default=None, help="Defaults to <results-root>/provenance.json")
    args, unknown = ap.parse_known_args()

    out = args.out or (args.results_root / "provenance.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    prov = build_provenance(results_root=args.results_root, excel=args.excel, sheet=args.sheet, argv=sys.argv)
    out.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
