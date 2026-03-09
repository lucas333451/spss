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


def _write_index(out: Path, branches: list[str]) -> None:
    lines = []
    lines.append("# Significance module index")
    lines.append("")
    lines.append("## Read this order first")
    lines.append("")
    for branch in branches:
        lines.append(f"### {branch}")
        lines.append(f"1. `./{branch}/overall/core_model/results_draft_zh.md` — overall core model narrative")
        lines.append(f"2. `./{branch}/overall/task5/analysis2_task5_spss_polynomial_contrasts.csv` — overall WWR linear/quadratic significance")
        lines.append(f"3. `./{branch}/experience/task5_group_only/analysis2_task5_spss_polynomial_contrasts.csv` — experience-group significance")
        lines.append(f"4. `./{branch}/experience/task5_group_round/analysis2_task5_spss_polynomial_contrasts.csv` — experience × round follow-up")
        lines.append("")
    (out / "significance_index.md").write_text("\n".join(lines), encoding="utf-8")


def _write_research_map(out: Path, branches: list[str]) -> None:
    lines = []
    lines.append("# Research questions map — significance")
    lines.append("")
    lines.append("## Q1. Does WWR show significant linear or quadratic trends overall?")
    for branch in branches:
        lines.append(f"- {branch}: `./{branch}/overall/task5/analysis2_task5_spss_polynomial_contrasts.csv`")
    lines.append("")
    lines.append("## Q2. What is the direction of those trends?")
    for branch in branches:
        lines.append(f"- {branch}: `./{branch}/overall/task5/analysis2_task5_spss_polynomial_contrasts.csv` (Direction column) + `./{branch}/overall/task5/task5_spss_polynomial_figures/*.png`")
    lines.append("")
    lines.append("## Q3. Is there an overall WWR / Complexity effect in the core model?")
    for branch in branches:
        lines.append(f"- {branch}: `./{branch}/overall/core_model/table_main_interactions.csv` + `./{branch}/overall/core_model/table_fixed_effects.csv`")
    lines.append("")
    lines.append("## Q4. Do high/low experience groups differ in significance patterns?")
    for branch in branches:
        lines.append(f"- {branch}: `./{branch}/experience/task5_group_only/analysis2_task5_spss_polynomial_contrasts.csv`")
    lines.append("")
    lines.append("## Q5. Do experience effects change by round?")
    for branch in branches:
        lines.append(f"- {branch}: `./{branch}/experience/task5_group_round/analysis2_task5_spss_polynomial_contrasts.csv`")
    (out / "research_questions_map.md").write_text("\n".join(lines), encoding="utf-8")


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

    for branch, exclude in branches:
        base = out / branch

        # overall core model
        run([
            args.python, "scripts/run_analysis.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "overall" / "core_model"),
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "overall" / "core_model").relative_to(out)))

        # overall task5
        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "overall" / "task5"),
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "overall" / "task5").relative_to(out)))

        # experience group only
        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "experience" / "task5_group_only"),
            "--split-by", "ExperienceGroup",
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "experience" / "task5_group_only").relative_to(out)))

        # experience x round
        run([
            args.python, "scripts/analysis2_task5_spss_polynomial.py",
            "--long-csv", str(args.long_csv),
            "--out-dir", str(base / "experience" / "task5_group_round"),
            "--split-by", "Repetition,ExperienceGroup",
            "--exclude-subjects", exclude,
        ])
        outputs.append(str((base / "experience" / "task5_group_round").relative_to(out)))

    _write_index(out, [b for b, _ in branches])
    _write_research_map(out, [b for b, _ in branches])

    payload = {
        "task": "significance pipeline",
        "scope": ["overall", "experience"],
        "branches": [b for b, _ in branches],
        "outputs": outputs + ["significance_index.md", "research_questions_map.md"],
    }
    (out / "significance_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
