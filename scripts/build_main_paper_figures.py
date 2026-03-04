#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import json


def _candidates(results_root: Path) -> list[tuple[str, str, str]]:
    """(label, relative source path, purpose) candidates in priority order."""
    return [
        (
            "Fig01_afford4_main",
            "model/figures/wwr_complexity_afford4.png",
            "Primary interaction overview on Afford4 (WWR × Complexity).",
        ),
        (
            "Fig02_task2_s_model_aic",
            "research/task2_core_imm_suite/task2_core_imm_suite_figures/task2_s_model_aic.png",
            "Model selection evidence for S-items (AIC).",
        ),
        (
            "Fig03_task2_s_effects_forest",
            "research/task2_core_imm_suite/task2_core_imm_suite_figures/task2_s_top_effects_forest.png",
            "Key fixed-effect directions and confidence intervals (S-items).",
        ),
        (
            "Fig04_task2_b_model_aic",
            "research/task2_core_imm_suite/task2_core_imm_suite_figures/task2_b_model_aic.png",
            "Model selection evidence for B-items (C1-only).",
        ),
        (
            "Fig05_task2_b_effects_forest",
            "research/task2_core_imm_suite/task2_core_imm_suite_figures/task2_b_top_effects_forest.png",
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
            "research/task1_stage_gap/task1_scene_stage_gap_figures/scene_S01.png",
            "Within-scene stage-gap matrix (if SceneID naming includes S01).",
        ),
    ]


def main():
    ap = argparse.ArgumentParser(description="Select and package 6-8 main-paper figures")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/figures_main_paper"))
    args = ap.parse_args()

    root = args.results_root
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    missing = []

    for label, rel, purpose in _candidates(root):
        src = root / rel
        if not src.exists():
            # fallback for scene figure: pick first scene_*.png
            if label == "Fig08_task1_scene_example":
                pool = sorted((root / "research/task1_stage_gap/task1_scene_stage_gap_figures").glob("scene_*.png"))
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

    # markdown index + caption draft
    md = [
        "# Main Paper Figures (6-8)",
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
        "out_dir": str(out),
        "n_selected": len(rows),
        "selected": rows,
        "missing": missing,
    }
    (out / "figures_main_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
