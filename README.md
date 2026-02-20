# spss — Questionnaire Wide-to-Long + LMM Pipeline / 问卷宽表转长表与LMM分析流程

[中文纯文档 / Chinese-only guide](./README_zh.md)

## Table of Contents / 目录
- [1. Project Overview / 项目概述](#1-project-overview--项目概述)
- [2. Repository Structure / 仓库结构](#2-repository-structure--仓库结构)
- [3. Installation / 安装](#3-installation--安装)
- [4. Quick Start / 快速开始](#4-quick-start--快速开始)
- [5. Excel Export Modes (Text/Coded) / Excel导出模式（文本版/编码版）](#5-excel-export-modes-textcoded--excel导出模式文本版编码版)
- [6. One-Click Pipeline / 一键全流程](#6-one-click-pipeline--一键全流程)
- [7. Output Files / 输出文件](#7-output-files--输出文件)
- [8. Data Schema (Long Format) / Long格式字段](#8-data-schema-long-format--long格式字段)
- [9. QC Rules / 质控规则](#9-qc-rules--质控规则)
- [10. Diagnostics / 诊断说明](#10-diagnostics--诊断说明)
- [11. Colab Usage / Colab 使用](#11-colab-usage--colab-使用)
- [12. FAQ / 常见问题](#12-faq--常见问题)

---

## 1. Project Overview / 项目概述
**EN:** This project replaces SPSS with a Python open-source pipeline for your VR+EEG questionnaire workflow: wide Excel → long-format dataset → QC → LMM tables/figures for manuscript use.  
**中文：** 本项目用 Python 开源流程替代 SPSS，面向你的 VR+EEG 问卷：宽表 Excel → long-format → 质控(QC) → 论文可用统计表和图。

---

## 2. Repository Structure / 仓库结构
- `scripts/transform_wide_to_long.py` — wide → long + QC
- `scripts/run_analysis.py` — core LMM + paper-ready tables
- `scripts/analysis_s_items.py` — S1~S5 angle-1/angle-2 analyses + 4-group split/comparison
- `scripts/analysis_b_items.py` — B1~B3/Bmean focused analyses (mainly C1)
- `scripts/analysis_groups.py` — shared people-group split/comparison utilities
- `scripts/report_summary.py` — narrative summary for angle-1/angle-2 conclusions
- `scripts/diagnostics_lmm.py` — diagnostics (interaction screening / random-structure sensitivity / repetition deep-dive)
- `scripts/pipeline.py` — one-click end-to-end runner (supports skip flags)
- `scripts/build_report_md.py` — build one-file markdown bundle from `results/`
- `docs/PROJECT_OVERVIEW.md` — concise orientation
- `docs/COLAB_GUIDE.md` — Colab deployment guide
- `notebooks/spss_colab.ipynb` — ready-to-run Colab notebook

---

## 3. Installation / 安装
```bash
pip install -r requirements.txt
```
If your system misses `pip/venv` (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

---

## 4. Quick Start / 快速开始
### Step 1: Put Excel in repo root, then Wide to Long + QC
Put your Excel file in the repository root (same level as `scripts/`, `docs/`, `README.md`), then run:
```bash
python scripts/transform_wide_to_long.py \
  --excel "your_file.xlsx" \
  --out-dir results/long
```

### Step 2: Core model
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

### Step 3: Diagnostics (new)
```bash
python scripts/diagnostics_lmm.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/diagnostics
```

### Step 4: Research analysis (modular)
```bash
python scripts/analysis_s_items.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research

python scripts/analysis_b_items.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research

python scripts/report_summary.py \
  --long-csv results/long/long_format.csv \
  --research-dir results/research \
  --out results/research/analysis_narrative.md
```

---

## 5. Excel Export Modes (Text/Coded) / Excel导出模式（文本版/编码版）
`transform_wide_to_long.py` supports both export styles:
- **text mode**: questionnaire text columns (e.g., `姓名`, `Q1.8_场景顺序编号`, `Q2.1_S1...`)
- **coded mode**: coded columns (e.g., `name`, `Q1.8`, `Q2.1_1`)

Default is auto-detection:
```bash
python scripts/transform_wide_to_long.py \
  --excel "/path/to/your.xlsx" \
  --mode auto \
  --out-dir results/long
```

For traceability, the script writes:
- `results/long/column_resolution.json` (detected mode + resolved column mapping)

It also outputs grouped factors used in analysis:
- `ExperienceGroup` from Q1.4: `1 -> Low`, `2/3/4 -> High`
- `SportFreqGroup` from Q1.5: `4 -> High`, `1/2/3 -> Low`

Scale note:
- S1~S4 are 7-point
- S5 is 9-point (item-level analysis uses raw S5 by default)
- Script still keeps optional `S5_7` for aligned-scale display when needed

---

## 6. One-Click Pipeline / 一键全流程
```bash
python scripts/pipeline.py \
  --excel "/path/to/your.xlsx" \
  --sheet 0 \
  --out-root results
```

> If the Excel filename contains spaces, wrap the full filename in quotes.

---

## 7. Output Files / 输出文件
**Core outputs / 核心输出：**
- `results/long/long_format.csv`
- `results/long/qc_issues.csv`
- `results/long/qc_summary.json`

- `results/model/table_descriptives.csv`
- `results/model/table_fixed_effects.csv`
- `results/model/table_main_interactions.csv`
- `results/model/model_comparison.csv`
- `results/model/table_simple_effects_complexity_by_wwr.csv`
- `results/model/paper_tables.md`
- `results/model/results_draft_zh.md`

- `results/research/table_fixed_effects_all_dv.csv` (item-level S1~S5)
- `results/research/table_angle1_main_interactions_all_dv.csv`
- `results/research/table_angle2_round_interactions_all_dv.csv`
- `results/research/groups/manifest.csv` + `results/research/groups/group_*.csv` (split by 4 people groups: Experience×SportFreq)
- `results/research/group_comparisons_item_level.csv` (between-group comparisons on S1~S5)
- `results/research/group2_comparisons_item_level.csv` (merged two-way splits: SportFreqGroup + ExperienceGroup)
- `results/research/group2_complexity_mean_table.csv` (merged two-way complexity means)
- `results/research/group2_complexity_delta_significance.csv` (merged two-way C1-C0 significance)
- `results/research/group2_comparisons_item_level_sportfreqgroup.csv` / `_experiencegroup.csv` (per-source)
- `results/research/group2_complexity_mean_table_sportfreqgroup.csv` / `_experiencegroup.csv` (per-source)
- `results/research/group2_complexity_delta_significance_sportfreqgroup.csv` / `_experiencegroup.csv` (per-source)
- `results/research/group_complexity_mean_table.csv` (intuitive 2D table: DV × [PeopleGroup4 × Complexity means])
- `results/research/group_complexity_delta_significance.csv` (between-group significance on complexity deltas: C1-C0)
- `results/research/group_complexity_mean_table_by_wwr.csv` (WWR-stratified people-group × complexity means)
- `results/research/group_complexity_delta_significance_by_wwr.csv` (WWR-stratified significance on C1-C0 deltas)
- `results/research/group_complexity_delta_by_round.csv` (C1-C0 split by round)
- `results/research/group_complexity_delta_round_shift.csv` (Round2-Round1 shift on complexity deltas)
- `results/research/figures/group_complexity_heatmap_S*.png` (PeopleGroup4 × Complexity heatmaps)
- `results/research/figures/group_complexity_delta_S*.png` (bar charts of C1-C0 by group)
- `results/research/b_items_long_c1.csv`, `b_items_condition_means.csv`, `b_items_group_comparisons.csv` (B1~B3 focused outputs, mainly C1)
- `results/research/analysis_narrative.md` (auto narrative summary for Angle1/Angle2)
- `results/research/angle1_c1_minus_c0_by_group.csv` (directly answers “all groups lower in C1?” and “same or different drop magnitudes?”)
- `results/research/angle2_round_diff_by_group.csv` (Round2-Round1 by group)
- `results/research/round_icc_by_group.csv` (Round agreement ICC(A,1) by group)
- `results/research/item_variance_by_group.csv`
- `results/research/item_variance_summary_by_group.csv`

- `results/diagnostics/analysis_report.md`
- `results/diagnostics/model_comparison_interactions.csv`
- `results/diagnostics/lrt_comparison.csv`
- `results/diagnostics/interaction_coefficients.csv`
- `results/diagnostics/random_effect_variance.csv`
- `results/diagnostics/main_effect_stability_by_random_structure.csv`
- `results/diagnostics/round_condition_means.csv`
- `results/diagnostics/subject_round_diff_distribution.csv`
- `results/diagnostics/repetition_complexity_interaction_terms.csv`

- `results/analysis_report_bundle.md` (one-file markdown bundle for easy sharing)

---

## 8. Data Schema (Long Format) / Long格式字段
`SubjectID, Order, Block, Repetition, RepetitionC, Position, WWR, Condition, Complexity, SportFreq, ExperienceGroup, SportFreqGroup, S1~S5, S5_7, B1~B3, Bmean, SceneID`

---

## 9. QC Rules / 质控规则
- 12 rows per subject / 每被试12行
- 6 rows per block / 每Block 6行
- C1=3 and C0=3 per block / 每Block内C1与C0各3行
- WWR distribution: 15×2, 45×2, 75×2 per block
- B1~B3 only non-NA in C1 rows / B题仅C1行可非空

---

## 10. Diagnostics / 诊断说明
Diagnostics script evaluates:
1. Interaction source screening (A/B/C/D models)
2. Random-structure sensitivity (`(1|Subject)`, `(1+Complexity|Subject)`, `(1+Complexity+WWR|Subject)`)
3. Repetition deep-dive (`Repetition×Complexity`, round means, subject-level diffs)
4. Auto markdown report in `results/diagnostics/analysis_report.md`

---

## 11. Colab Usage / Colab 使用
- Full guide: `docs/COLAB_GUIDE.md`
- Ready notebook: `notebooks/spss_colab.ipynb`
- Recommended: run pipeline once, then send `results/analysis_report_bundle.md`

---

## 12. FAQ / 常见问题
1) `No module named pandas` → run `pip install -r requirements.txt`  
2) QC failed → check `results/long/qc_issues.csv` and `missing_rate.csv`  
3) MixedLM singular matrix → script auto-fallback from `lbfgs` to `powell` in diagnostics.
