#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse

import matplotlib.pyplot as plt

from plot_style import apply_bae_style


def _write_md(out_root: Path) -> Path:
    p = out_root / "RESULTS_GUIDE.md"
    lines = []
    lines.append("# RESULTS GUIDE")
    lines.append("")
    lines.append("## 1. First reading order / 首先阅读顺序")
    lines.append("")
    lines.append("### Descriptive")
    lines.append("1. `descriptive/qc/overall/png/` — first visual scan of cleaned overall distributions")
    lines.append("2. `descriptive/qc/overall/csv/` — confirm exact descriptive values")
    lines.append("3. `descriptive/qc/experience/png/` — compare high/low experience groups visually")
    lines.append("4. `descriptive/qc/experience/csv/` — confirm grouped descriptives")
    lines.append("")
    lines.append("### Significance")
    lines.append("1. `significance/significance_guide.png` — visual navigation overview")
    lines.append("2. `significance/qc/overall/core_model/md/results_draft_zh.md` — overall LMM narrative")
    lines.append("3. `significance/qc/overall/core_model/png/` — overall LMM figures")
    lines.append("4. `significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv` — overall WWR trend significance")
    lines.append("5. `significance/qc/overall/wwr_polynomial/png/` — overall WWR trend figures")
    lines.append("6. `significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv` — experience grouped significance")
    lines.append("7. `significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv` — round follow-up")
    lines.append("8. `significance/qc/item_level_lmm/md/item_level_lmm_report_zh.md` — item-level / dimension-level unified LMM summary")
    lines.append("9. `significance/qc/item_level_lmm/csv/item_level_lmm_type3_fixed_effects_fdr.csv` — item-level fixed effects after multiplicity control")
    lines.append("")
    lines.append("## 2. If you want formal reporting / 如果要正式写结果")
    lines.append("")
    lines.append("- Prefer `qc` over `raw` for formal interpretation.")
    lines.append("- Use `raw` mainly for robustness comparison.")
    lines.append("- Read `png/` first for pattern, then `csv/` for exact numbers.")
    lines.append("")
    lines.append("## 3. Which folder answers which question / 研究问题对应文件夹")
    lines.append("")
    lines.append("- Overall descriptive picture → `descriptive/qc/overall/`")
    lines.append("- Experience-group descriptive picture → `descriptive/qc/experience/`")
    lines.append("- Overall LMM significance → `significance/qc/overall/core_model/`")
    lines.append("- Overall WWR linear/quadratic trend → `significance/qc/overall/wwr_polynomial/`")
    lines.append("- Experience-group WWR significance → `significance/qc/experience/wwr_polynomial_group_only/`")
    lines.append("- Experience × Round follow-up → `significance/qc/experience/wwr_polynomial_group_round/`")
    lines.append("- Item-level / dimension-level unified LMM → `significance/qc/item_level_lmm/`")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _summary_box(ax, title: str, lines: list[str]):
    ax.axis("off")
    ax.set_facecolor("#F7FAF8")
    ax.text(0.03, 0.97, title, va="top", ha="left", fontsize=10.2, fontweight="bold", color="#40534C")
    ax.text(
        0.03, 0.90, "\n".join(lines), va="top", ha="left", fontsize=8.8, color="#50615A", linespacing=1.36,
        bbox=dict(boxstyle="round,pad=0.45", fc="#F4F8F6", ec="#D5DFD9", lw=0.8)
    )


def _write_png(out_root: Path) -> Path:
    apply_bae_style()
    p = out_root / "RESULTS_GUIDE.png"
    fig = plt.figure(figsize=(11.2, 6.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1.2], wspace=0.16)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    _summary_box(ax1, "Read in this order", [
        "[Descriptive]",
        "1. descriptive/qc/overall/png/",
        "2. descriptive/qc/overall/csv/",
        "3. descriptive/qc/experience/png/",
        "4. descriptive/qc/experience/csv/",
        "",
        "[Significance]",
        "1. significance/significance_guide.png",
        "2. significance/qc/overall/core_model/md/results_draft_zh.md",
        "3. significance/qc/overall/core_model/png/",
        "4. significance/qc/overall/wwr_polynomial/csv/",
        "5. significance/qc/experience/wwr_polynomial_group_only/csv/",
        "6. significance/qc/item_level_lmm/md/item_level_lmm_report_zh.md",
    ])

    _summary_box(ax2, "Question → folder", [
        "Overall descriptive → descriptive/qc/overall/",
        "Experience descriptive → descriptive/qc/experience/",
        "Overall LMM → significance/qc/overall/core_model/",
        "WWR trend overall → significance/qc/overall/wwr_polynomial/",
        "Experience-group significance → significance/qc/experience/wwr_polynomial_group_only/",
        "Experience × Round → significance/qc/experience/wwr_polynomial_group_round/",
        "Item-level unified LMM → significance/qc/item_level_lmm/",
        "",
        "Rule: png first, csv second.",
        "Rule: qc first, raw second.",
    ])

    fig.savefig(p, dpi=230)
    plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser(description="Build top-level results guide (md + png)")
    ap.add_argument("--out-root", type=Path, default=Path("results"))
    args = ap.parse_args()

    args.out_root.mkdir(parents=True, exist_ok=True)
    md = _write_md(args.out_root)
    png = _write_png(args.out_root)
    print(str(md))
    print(str(png))


if __name__ == "__main__":
    main()
