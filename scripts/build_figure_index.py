#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse


def infer_topic(p: Path) -> str:
    s = str(p).lower()
    if "task1_stage_gap" in s and "scene_" in p.name.lower():
        return "Analysis-2 Task1: within-scene Round2-Round1 gap (S-items)"
    if "task1_stage_gap" in s and p.name.lower().startswith("b"):
        return "Analysis-2 Task1b: Round2-Round1 gap (B-items, C1-only)"
    if "task2_core_imm_suite" in s:
        return "Analysis-2 Task2: core_imm_suite LMM"
    if "diagnostics" in s:
        return "Diagnostics / robustness"
    if "group_complexity" in p.name.lower():
        return "Angle1: complexity effects by people group"
    if "round_diff" in p.name.lower() or "scene_delta" in p.name.lower():
        return "Angle2: round/stage effects"
    return "Other"


def main():
    ap = argparse.ArgumentParser(description="Build markdown index for all PNG figures")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=Path("results/FIGURE_INDEX.md"))
    args = ap.parse_args()

    root = args.results_root
    pngs = sorted(root.rglob("*.png"))

    lines = ["# Figure Index", "", "Auto-generated figure map for quick reporting.", ""]
    lines.append("| Figure | Topic | Relative Path |")
    lines.append("|---|---|---|")

    for p in pngs:
        rel = p.relative_to(root)
        topic = infer_topic(rel)
        lines.append(f"| {p.name} | {topic} | `{rel}` |")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
