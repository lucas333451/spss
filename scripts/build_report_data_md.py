#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import pandas as pd


def csv_md(path: Path, max_rows: int) -> str:
    if not path.exists():
        return f"`Missing: {path}`"
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return f"`Failed to read CSV: {e}`"

    if df.empty:
        return "(empty table)"

    if len(df) > max_rows:
        return f"Rows: {len(df)} (showing first {max_rows})\n\n" + df.head(max_rows).to_markdown(index=False) + "\n\n... (truncated)"
    return f"Rows: {len(df)}\n\n" + df.to_markdown(index=False)


def text_block(path: Path, max_chars: int = 300000) -> str:
    if not path.exists():
        return f"`Missing: {path}`"
    s = path.read_text(encoding="utf-8", errors="ignore")
    if len(s) > max_chars:
        s = s[:max_chars] + "\n\n... (truncated)"
    return s


def build(results_root: Path, out: Path, max_rows: int) -> None:
    r = results_root
    lines: list[str] = []
    lines.append("# Analysis Data Pack (no-index, data-first)")
    lines.append("")
    lines.append("这个文件是‘直接可分析’版本：以具体结果表为主，不要求再去索引跳转。")
    lines.append("")

    # 1) Overall narrative
    lines.append("## 1) 总结结论（自动叙事）")
    lines.append("")
    lines.append(text_block(r / "research/analysis_narrative.md"))
    lines.append("\n---\n")

    # 2) Angle 1 main
    lines.append("## 2) 角度1主效应与交互（S1-S5）")
    lines.append("\n### 2.1 主交互汇总")
    lines.append(csv_md(r / "research/table_angle1_main_interactions_all_dv.csv", max_rows))
    lines.append("\n### 2.2 四类人群复杂度均值")
    lines.append(csv_md(r / "research/group_complexity_mean_table.csv", max_rows))
    lines.append("\n### 2.3 四类人群复杂度降幅显著性（C1-C0）")
    lines.append(csv_md(r / "research/group_complexity_delta_significance.csv", max_rows))
    lines.append("\n---\n")

    # 3) WWR stratified
    lines.append("## 3) WWR分层结果")
    lines.append("\n### 3.1 WWR分层均值")
    lines.append(csv_md(r / "research/group_complexity_mean_table_by_wwr.csv", max_rows))
    lines.append("\n### 3.2 WWR分层显著性")
    lines.append(csv_md(r / "research/group_complexity_delta_significance_by_wwr.csv", max_rows))
    lines.append("\n---\n")

    # 4) Repetition/round
    lines.append("## 4) Round/顺序效应")
    lines.append("\n### 4.1 Round交互")
    lines.append(csv_md(r / "research/table_angle2_round_interactions_all_dv.csv", max_rows))
    lines.append("\n### 4.2 按轮次的复杂度差值")
    lines.append(csv_md(r / "research/group_complexity_delta_by_round.csv", max_rows))
    lines.append("\n### 4.3 Round2-Round1变化")
    lines.append(csv_md(r / "research/group_complexity_delta_round_shift.csv", max_rows))
    lines.append("\n### 4.4 一致性ICC")
    lines.append(csv_md(r / "research/round_icc_by_group.csv", max_rows))
    lines.append("\n---\n")

    # 5) Groups
    lines.append("## 5) 人群差异（4类 + 两种二分）")
    lines.append("\n### 5.1 交叉四类对比")
    lines.append(csv_md(r / "research/group_comparisons_item_level.csv", max_rows))
    lines.append("\n### 5.2 二分：SportFreq")
    lines.append(csv_md(r / "research/group2_comparisons_item_level_sportfreqgroup.csv", max_rows))
    lines.append("\n### 5.3 二分：Experience")
    lines.append(csv_md(r / "research/group2_comparisons_item_level_experiencegroup.csv", max_rows))
    lines.append("\n### 5.4 二分复杂度均值（合并）")
    lines.append(csv_md(r / "research/group2_complexity_mean_table.csv", max_rows))
    lines.append("\n### 5.5 二分复杂度显著性（合并）")
    lines.append(csv_md(r / "research/group2_complexity_delta_significance.csv", max_rows))
    lines.append("\n---\n")

    # 6) B items
    lines.append("## 6) B题结果（C1）")
    lines.append("\n### 6.1 条件均值")
    lines.append(csv_md(r / "research/b_items_condition_means.csv", max_rows))
    lines.append("\n### 6.2 组间比较")
    lines.append(csv_md(r / "research/b_items_group_comparisons.csv", max_rows))
    lines.append("\n---\n")

    # 7) Diagnostics
    lines.append("## 7) 诊断稳健性")
    lines.append("\n### 7.1 诊断报告")
    lines.append(text_block(r / "diagnostics/analysis_report.md"))
    lines.append("\n### 7.2 交互模型比较")
    lines.append(csv_md(r / "diagnostics/model_comparison_interactions.csv", max_rows))
    lines.append("\n### 7.3 LRT比较")
    lines.append(csv_md(r / "diagnostics/lrt_comparison.csv", max_rows))
    lines.append("\n### 7.4 随机结构稳健性")
    lines.append(csv_md(r / "diagnostics/main_effect_stability_by_random_structure.csv", max_rows))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Build a data-first markdown report (no index)")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=Path("results/analysis_report_data.md"))
    ap.add_argument("--max-rows", type=int, default=5000)
    args = ap.parse_args()

    build(args.results_root, args.out, args.max_rows)
    print(json.dumps({"results_root": str(args.results_root), "out": str(args.out), "max_rows": args.max_rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
