#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys
import json

QC_EXCLUDE = "孙校聪,康少勇,张钰鹏,杨可,洪婷婷,陈韬,高梓楠,赵国宏"


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main():
    ap = argparse.ArgumentParser(description="Significance-only pipeline: overall + experience")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/significance"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--with-qc", action="store_true", help="Also export QC-excluded outputs")
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    outputs: list[str] = []
    branches = [("raw", "")]
    if args.with_qc:
        branches.append(("qc", QC_EXCLUDE))

    # overall main model once (not branch split here; uses long CSV directly)
    overall_dir = out / "overall"
    overall_dir.mkdir(parents=True, exist_ok=True)
    run([
        args.python, "scripts/run_analysis.py",
        "--long-csv", str(args.long_csv),
        "--out-dir", str(overall_dir / "core_model"),
    ])
    outputs.append(str((overall_dir / "core_model").relative_to(out)))

    for branch, exclude in branches:
        base = out / branch
        (base / "overall").mkdir(parents=True, exist_ok=True)
        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "overall" / "task5"),
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "overall" / "task5").relative_to(out)))

        (base / "experience").mkdir(parents=True, exist_ok=True)
        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "experience" / "task5_group_only"),
            "--split-by", "ExperienceGroup",
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "experience" / "task5_group_only").relative_to(out)))

        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "experience" / "task5_group_round"),
            "--split-by", "Repetition,ExperienceGroup",
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "experience" / "task5_group_round").relative_to(out)))

    payload = {
        "task": "significance pipeline",
        "scope": ["overall", "experience"],
        "branches": [b for b, _ in branches],
        "outputs": outputs,
    }
    (out / "significance_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
