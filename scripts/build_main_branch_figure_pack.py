#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import json


def _candidates(branch: str) -> list[tuple[str, str, str, str]]:
    b = branch
    return [
        (
            "Fig01_afford4_condition_profile",
            f"significance/{b}/overall/core_model/png/wwr_complexity_afford4.png",
            "Primary Afford4 condition profile",
            "Overall Afford4 pattern across WWR and Complexity; suitable as the opening main-text figure.",
        ),
        (
            "Fig02_afford4_fixed_effects",
            f"significance/{b}/overall/core_model/png/fixed_effects_forest.png",
            "Fixed-effects forest plot",
            "Direction and confidence intervals of the key fixed effects in the Afford4 core model.",
        ),
        (
            "Fig03_afford4_effect_size",
            f"significance/{b}/overall/core_model/png/effect_size_summary.png",
            "Effect-size summary",
            "Compact comparison of partial eta squared across core fixed terms.",
        ),
        (
            "Fig04_wwr_trend_overall_S1_example",
            f"significance/{b}/overall/wwr_polynomial/png/task5_trend_profile_S1.png",
            "Example overall WWR trend profile",
            "Example line-profile figure showing how one questionnaire item varies across the three WWR levels.",
        ),
        (
            "Fig05_wwr_linear_significance_overall",
            f"significance/{b}/overall/wwr_polynomial/png/task5_linear_contrast_heatmap.png",
            "Overall linear significance strip/map",
            "Compact overview of which S-items show significant linear WWR trends overall.",
        ),
        (
            "Fig06_wwr_group_profile_S1_example",
            f"significance/{b}/experience/wwr_polynomial_group_only/png/task5_trend_profile_S1.png",
            "Experience-group WWR profile example",
            "Example profile figure comparing high- and low-experience groups across WWR levels.",
        ),
        (
            "Fig07_wwr_group_linear_significance",
            f"significance/{b}/experience/wwr_polynomial_group_only/png/task5_linear_contrast_heatmap.png",
            "Experience-group linear significance strip/map",
            "Compact overview of group-specific linear WWR effects.",
        ),
        (
            "Fig08_wwr_round_group_linear_significance",
            f"significance/{b}/experience/wwr_polynomial_group_round/png/task5_linear_contrast_heatmap.png",
            "Experience × round linear significance strip/map",
            "Compact overview of whether linear WWR effects differ by experience group and repetition round.",
        ),
    ]


def _build_branch(results_root: Path, out_dir: Path, branch: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    missing = []
    for label, rel, short_title, purpose in _candidates(branch):
        src = results_root / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = out_dir / f"{label}{src.suffix.lower()}"
        shutil.copy2(src, dst)
        rows.append(
            {
                "label": label,
                "file": dst.name,
                "source": str(src.relative_to(results_root)),
                "short_title": short_title,
                "purpose": purpose,
            }
        )

    md = [
        f"# Main-branch figure pack — {branch}",
        "",
        "Suggested main-text figures for the clean `main` branch.",
        "",
        "| Label | File | Source | Use in manuscript |",
        "|---|---|---|---|",
    ]
    for r in rows:
        md.append(f"| {r['label']} | `{r['file']}` | `{r['source']}` | {r['purpose']} |")
    (out_dir / "FIGURE_PACK_INDEX.md").write_text("\n".join(md), encoding="utf-8")

    payload = {
        "branch": branch,
        "out_dir": str(out_dir),
        "n_selected": len(rows),
        "selected": rows,
        "missing": missing,
    }
    (out_dir / "figure_pack_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a main-text figure pack for the clean main branch outputs")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/figure_pack_main_branch"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "raw": _build_branch(args.results_root, args.out_dir / "raw", "raw"),
        "qc": _build_branch(args.results_root, args.out_dir / "qc", "qc"),
    }
    (args.out_dir / "figure_pack_manifest_all.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(args.out_dir), "branches": ["raw", "qc"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
