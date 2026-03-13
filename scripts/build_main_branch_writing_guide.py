#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json


def _guide_text(branch: str) -> str:
    prefix = f"results/significance/{branch}"
    lines: list[str] = []
    lines.append(f"# Main-branch Results Writing Guide — {branch}")
    lines.append("")
    lines.append("这份提纲只服务于当前 `main` 分支的正文结果写作，不走旧 research / analysis-2 线。")
    lines.append("")
    lines.append("## 一、正文图的推荐顺序")
    lines.append("")
    lines.append(f"1. `{prefix}/overall/core_model/png/wwr_complexity_afford4.png`")
    lines.append("   - 用途：先给出 Afford4 的总体条件模式。")
    lines.append(f"2. `{prefix}/overall/core_model/png/fixed_effects_forest.png`")
    lines.append("   - 用途：再交代固定效应方向与区间。")
    lines.append(f"3. `{prefix}/overall/core_model/png/effect_size_summary.png`")
    lines.append("   - 用途：补强哪些效应更重要。")
    lines.append(f"4. `{prefix}/overall/wwr_polynomial/png/task5_linear_contrast_heatmap.png`")
    lines.append("   - 用途：概括哪些题目存在整体线性 WWR 趋势。")
    lines.append(f"5. `{prefix}/experience/wwr_polynomial_group_only/png/task5_linear_contrast_heatmap.png`")
    lines.append("   - 用途：概括 Experience 高低组的 WWR 显著性差异。")
    lines.append(f"6. `{prefix}/experience/wwr_polynomial_group_round/png/task5_linear_contrast_heatmap.png`")
    lines.append("   - 用途：概括这种差异是否还受 round 影响。")
    lines.append("")
    lines.append("## 二、正文写作建议顺序")
    lines.append("")
    lines.append("### 1. 先写整体核心模型（Afford4）")
    lines.append(f"优先引用：`{prefix}/overall/core_model/md/results_draft_zh.md`、`table_main_interactions.csv`、`table_fixed_effects.csv`")
    lines.append("可按这个句式写：")
    lines.append("- 先说明模型设定与层级结构。")
    lines.append("- 再报告 WWR、Complexity、ExperienceGroup 的主效应是否显著。")
    lines.append("- 若有显著交互，再说明哪个交互显著、方向如何。")
    lines.append("")
    lines.append("### 2. 再写 WWR 三水平趋势")
    lines.append(f"优先引用：`{prefix}/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`")
    lines.append("可按这个句式写：")
    lines.append("- 哪些题目呈现显著线性趋势。")
    lines.append("- 哪些题目呈现二次趋势。")
    lines.append("- 方向是 increase / decrease / inverted-U / U-shape。")
    lines.append("")
    lines.append("### 3. 再写 Experience 分组差异")
    lines.append(f"优先引用：`{prefix}/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv` 和 `{prefix}/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`")
    lines.append("可按这个句式写：")
    lines.append("- 哪些题目在高低经验组中表现出不同的 WWR 显著性模式。")
    lines.append("- 这种差异是否在不同 round 中保持稳定。")
    lines.append("")
    lines.append("### 4. 最后写 item-level unified LMM（如果正文需要逐题展开）")
    lines.append(f"优先引用：`{prefix}/item_level_lmm/md/item_level_lmm_report_zh.md` 及对应 csv")
    lines.append("可按这个句式写：")
    lines.append("- 对每个因变量分别说明哪个主效应或交互显著。")
    lines.append("- 对显著项再写 estimated marginal means / pairwise comparisons。")
    lines.append("- 对 warning 标记的题目加一句谨慎解释。")
    lines.append("")
    lines.append("## 三、图和表如何分工")
    lines.append("")
    lines.append("- 图：先说明模式、方向、相对大小。")
    lines.append("- 表：再给出 F、df、p、估计值、CI、EMMs、pairwise。")
    lines.append("- 如果一个信息已经在图里说清楚，正文不要再机械重复所有数字。")
    lines.append("")
    lines.append("## 四、建议的正文结果段结构")
    lines.append("")
    lines.append("1. 样本与模型设定")
    lines.append("2. Afford4 核心模型结果")
    lines.append("3. 整体 WWR 趋势结果")
    lines.append("4. Experience 分组趋势结果")
    lines.append("5. item-level / dimension-level LMM 结果（如需逐题展开）")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a main-branch manuscript writing guide")
    ap.add_argument("--out-dir", type=Path, default=Path("docs"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for branch in ["raw", "qc"]:
        p = args.out_dir / f"MAIN_BRANCH_WRITING_GUIDE_{branch.upper()}.md"
        p.write_text(_guide_text(branch), encoding="utf-8")
        paths.append(str(p))
    print(json.dumps({"generated": paths}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
