#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import json


def _candidates(results_root: Path, branch: str) -> list[tuple[str, str, str]]:
    """(label, relative source path, purpose) candidates in priority order."""
    b = branch
    return [
        (
            "Fig01_afford4_main",
            "model/figures/wwr_complexity_afford4.png",
            "Primary interaction overview on Afford4 (WWR × Complexity).",
        ),
        (
            "Fig02_task2_s_factor_overview",
            f"research/analysis-2/task2/experience/{b}/task2_core_imm_suite_figures/task2_s_factor_overview_heatmap.png",
            "Task2 S-items factor overview heatmap (WWR/Complexity/Group + interactions; p-tier encoded).",
        ),
        (
            "Fig03_task2_s_effects_forest",
            f"research/analysis-2/task2/experience/{b}/task2_core_imm_suite_figures/task2_s_top_effects_forest.png",
            "Key fixed-effect directions and confidence intervals (S-items).",
        ),
        (
            "Fig04_task2_b_factor_overview",
            f"research/analysis-2/task2/experience/{b}/task2_core_imm_suite_figures/task2_b_factor_overview_heatmap.png",
            "Task2 B-items factor overview heatmap (C1-only; WWR/Group and interaction).",
        ),
        (
            "Fig05_task2_b_effects_forest",
            f"research/analysis-2/task2/experience/{b}/task2_core_imm_suite_figures/task2_b_top_effects_forest.png",
            "Key fixed-effect directions and confidence intervals (B-items).",
        ),
        (
            "Fig06_group_complexity_delta_S1",
            "research/figures/group_complexity_delta_S1.png",
            "Complexity effect magnitude by people group (S1).",
        ),
        (
            "Fig07_round_diff_S1",
            "research/figures/round_diff_S1_by_sportfreqgroup.png",
            "Round/stage shift by frequency groups (S1).",
        ),
        (
            "Fig08_task1_scene_example",
            f"research/analysis-2/task1/experience/{b}/task1_scene_stage_gap_figures/scene_S01.png",
            "Within-scene stage-gap matrix (if SceneID naming includes S01).",
        ),
    ]


def _build_one_branch(root: Path, out: Path, branch: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    missing = []

    for label, rel, purpose in _candidates(root, branch=branch):
        src = root / rel
        if not src.exists():
            # fallback for scene figure: pick first scene_*.png
            if label == "Fig08_task1_scene_example":
                pool = sorted((root / f"research/analysis-2/task1/experience/{branch}/task1_scene_stage_gap_figures").glob("scene_*.png"))
                if pool:
                    src = pool[0]
                else:
                    missing.append(rel)
                    continue
            else:
                missing.append(rel)
                continue

        dst = out / f"{label}{src.suffix.lower()}"
        shutil.copy2(src, dst)
        rows.append({
            "label": label,
            "file": dst.name,
            "source": str(src.relative_to(root)),
            "purpose": purpose,
        })

    md = [
        f"# Main Paper Figures (6-8) - {branch}",
        "",
        "Auto-packed figures for manuscript main text.",
        "",
        "| Label | File | Source | Suggested caption focus |",
        "|---|---|---|---|",
    ]
    for r in rows:
        md.append(f"| {r['label']} | `{r['file']}` | `{r['source']}` | {r['purpose']} |")
    (out / "FIGURES_MAIN_INDEX.md").write_text("\n".join(md), encoding="utf-8")

    payload = {
        "branch": branch,
        "out_dir": str(out),
        "n_selected": len(rows),
        "selected": rows,
        "missing": missing,
    }
    (out / "figures_main_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main():
    ap = argparse.ArgumentParser(description="Select and package 6-8 main-paper figures")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/figures_main_paper"))
    args = ap.parse_args()

    root = args.results_root
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "raw": _build_one_branch(root, out / "raw", branch="raw"),
        "qc": _build_one_branch(root, out / "qc", branch="qc"),
    }

    (out / "figures_main_manifest_all.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out), "branches": ["raw", "qc"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
