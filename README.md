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
- [10. LMM v2 Optimization Notes / LMM v2 优化说明](#10-lmm-v2-optimization-notes--lmm-v2-优化说明)
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
- `scripts/analyze_research_questions.py` — angle-1/angle-2 extended analyses
- `scripts/pipeline.py` — one-click end-to-end runner
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

### Step 2: Core paper tables
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

### Step 3: Extended research analysis
```bash
python scripts/analyze_research_questions.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research
```

---

## 5. Excel Export Modes (Text/Coded) / Excel导出模式（文本版/编码版）
`transform_wide_to_long.py` now supports both export styles:
- **text mode**: questionnaire text columns (e.g., `姓名`, `Q1.8_场景顺序编号`, `Q2.1_S1...`)
- **coded mode**: coded columns (e.g., `name`, `Q1.8`, `Q2.1_1`)

Default is auto-detection:
```bash
python scripts/transform_wide_to_long.py \
  --excel "/path/to/your.xlsx" \
  --mode auto \
  --out-dir results/long
```

You can force mode if needed:
```bash
# force coded export parsing
python scripts/transform_wide_to_long.py --excel "/path/to/coded.xlsx" --mode coded --out-dir results/long

# force text export parsing
python scripts/transform_wide_to_long.py --excel "/path/to/text.xlsx" --mode text --out-dir results/long
```

For traceability, the script writes:
- `results/long/column_resolution.json` (detected mode + resolved column mapping)

It also outputs grouped factors used in analysis:
- `ExperienceGroup` from Q1.4: `1 -> Low`, `2/3/4 -> High`
- `SportFreqGroup` from Q1.5: `4 -> High`, `1/2/3 -> Low`

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
- `results/model/model_comparison.csv` (A/B/C with AIC/BIC)
- `results/model/table_simple_effects_complexity_by_wwr.csv`
- `results/model/paper_tables.md`
- `results/model/results_draft_zh.md` (auto-generated Chinese draft paragraph)
- `results/research/table_fixed_effects_all_dv.csv` (currently item-level S1~S5 by default)
- `results/research/round_consistency_by_group.csv`
- `results/research/item_variance_by_group.csv` (within-group variance flags per item)
- `results/research/item_variance_summary_by_group.csv`
- `results/analysis_report_bundle.md` (one-file markdown bundle for easy sharing)

---

## 8. Data Schema (Long Format) / Long格式字段
`SubjectID, Order, Block, Repetition, RepetitionC, Position, WWR, Condition, Complexity, SportFreq, ExperienceGroup, SportFreqGroup, S1~S5, S5_7, Afford4, Afford5, Afford5_norm7, Pleasure, Pleasure_7, B1~B3, Bmean, SceneID`

---

## 9. QC Rules / 质控规则
- 12 rows per subject / 每被试12行
- 6 rows per block / 每Block 6行
- C1=3 and C0=3 per block / 每Block内C1与C0各3行
- WWR distribution: 15×2, 45×2, 75×2 per block
- B1~B3 only non-NA in C1 rows / B题仅C1行可非空

---

## 10. LMM v2 Optimization Notes / LMM v2 优化说明
Current recommended model (Afford5_norm7):

```text
Afford5_norm7 ~ C(Complexity) * C(WWR) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)
Random: (1 + Complexity | Subject), with automatic fallback to (1 | Subject) if singular/non-convergent.
```

Scale note and correction:
- S1~S4 are 7-point
- S5 (Pleasure) is 9-point
- B1~B3 are 7-point
- To avoid mixed-scale bias, script generates `S5_7` (linearly maps 1-9 to 1-7) and uses `Afford5_norm7` as the preferred composite.

What is newly added in v2:
- Repetition is explicitly modeled (`Repetition=1/2`, generated in long-format)
- Model comparison table (A/B/C) exported to `results/model/model_comparison.csv`
- Simple effects of Complexity within each WWR exported to `results/model/table_simple_effects_complexity_by_wwr.csv`
- `paper_tables.md` now includes model comparison + simple-effects section

---

## 11. Colab Usage / Colab 使用
- Full step-by-step guide (beginner-friendly): `docs/COLAB_GUIDE.md`
- Ready notebook: `notebooks/spss_colab.ipynb` (run cells top-down, only change `EXCEL_FILE`)

---

## 12. FAQ / 常见问题
1) `No module named pandas` → run `pip install -r requirements.txt`  
2) QC failed → check `results/long/qc_issues.csv` and `missing_rate.csv`  
3) Hard-to-read terms like `C(WWR)[T.45]` → use `APA_Term` column in exported tables  
4) `LinAlgError: Singular matrix` in MixedLM → script now auto-falls back from `lbfgs` to `powell`.
