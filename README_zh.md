# spss（纯中文）— 问卷宽表转长表 + LMM 分析流程

## 目录
- [1. 项目简介](#1-项目简介)
- [2. 仓库结构](#2-仓库结构)
- [3. 安装](#3-安装)
- [4. 快速开始](#4-快速开始)
- [5. Excel导出模式（文本版/编码版）](#5-excel导出模式文本版编码版)
- [6. 一键全流程](#6-一键全流程)
- [7. 输出文件说明](#7-输出文件说明)
- [8. Long格式字段](#8-long格式字段)
- [9. 质控规则](#9-质控规则)
- [10. 诊断说明](#10-诊断说明)
- [11. Colab 部署](#11-colab-部署)
- [12. 常见问题](#12-常见问题)

---

## 1. 项目简介
本项目用于替代 SPSS，完成：
1. 读取问卷 Excel 宽表（每位被试一行）
2. 转为 long-format（每位被试 12 行）
3. 自动 QC（结构与映射校验）
4. 输出 LMM 结果、诊断结果与可复用报告

---

## 2. 仓库结构
- `scripts/transform_wide_to_long.py`：宽表转长表 + QC
- `scripts/run_analysis.py`：基础 LMM + 论文结果表导出
- `scripts/analyze_research_questions.py`：分题扩展分析（角度1/角度2）
- `scripts/diagnostics_lmm.py`：诊断分析（交互来源/随机结构敏感性/Repetition）
- `scripts/pipeline.py`：一键全流程执行
- `scripts/build_report_md.py`：将结果目录汇总成一个 markdown

---

## 3. 安装
```bash
pip install -r requirements.txt
```
如缺少 pip/venv（Ubuntu/Debian）：
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

---

## 4. 快速开始
### 第一步：宽表转长表 + QC
```bash
python scripts/transform_wide_to_long.py \
  --excel "your_file.xlsx" \
  --out-dir results/long
```

### 第二步：基础模型
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

### 第三步：诊断分析（新增）
```bash
python scripts/diagnostics_lmm.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/diagnostics
```

### 第四步：分题扩展分析
```bash
python scripts/analyze_research_questions.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research
```

---

## 5. Excel导出模式（文本版/编码版）
支持两种导出格式：
- 文本版：`姓名`、`Q1.8_...` 等
- 编码版：`name`、`Q1.8`、`Q2.1_1` 等

默认自动识别：
```bash
python scripts/transform_wide_to_long.py \
  --excel "/path/to/your.xlsx" \
  --mode auto \
  --out-dir results/long
```

会输出：
- `results/long/column_resolution.json`（识别模式 + 列映射）

并生成分组字段：
- `ExperienceGroup`：Q1.4 的 1=Low，2/3/4=High
- `SportFreqGroup`：Q1.5 的 4=High，1/2/3=Low

量表说明：
- S1~S4：7分
- S5：9分（分题分析默认使用原始 S5）
- B1~B3：7分
- `S5_7` 仍会保留在 long 表中，仅用于需要同量尺展示时可选使用

---

## 6. 一键全流程
```bash
python scripts/pipeline.py \
  --excel "/path/to/your.xlsx" \
  --sheet 0 \
  --out-root results
```

> 文件名有空格请加引号。

---

## 7. 输出文件说明
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

- `results/research/table_fixed_effects_all_dv.csv`（分题：S1~S5）
- `results/research/table_angle1_main_interactions_all_dv.csv`
- `results/research/table_angle2_round_interactions_all_dv.csv`
- `results/research/groups/manifest.csv` 与 `results/research/groups/group_*.csv`（按 Experience×SportFreq 四类人群拆分数据）
- `results/research/group_comparisons_item_level.csv`（四类人群在 S1~S5 的组间对比）
- `results/research/b_items_long_c1.csv`、`b_items_condition_means.csv`、`b_items_group_comparisons.csv`（B1~B3 专项：主要针对 C1）
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

- `results/analysis_report_bundle.md`（将所有结果汇总成一个 markdown）

---

## 8. Long格式字段
`SubjectID, Order, Block, Repetition, RepetitionC, Position, WWR, Condition, Complexity, SportFreq, ExperienceGroup, SportFreqGroup, S1~S5, S5_7, B1~B3, Bmean, SceneID`

---

## 9. 质控规则
- 每位被试 12 行
- 每个 Block 6 行
- 每个 Block 内 C1/C0 各 3 行
- 每个 Block 内 WWR：15×2、45×2、75×2
- B1~B3 仅 C1 行可非空

---

## 10. 诊断说明
诊断脚本会自动做：
1. 交互来源排查（A/B/C/D）
2. 随机结构敏感性比较（3 种随机结构）
3. Repetition 深入排查（Round 均值 + 被试差值分布）
4. 自动生成 `results/diagnostics/analysis_report.md`

---

## 11. Colab 部署
- 详细指南：`docs/COLAB_GUIDE.md`
- 现成 Notebook：`notebooks/spss_colab.ipynb`
- 推荐直接跑 pipeline，再把 `results/analysis_report_bundle.md` 发给 Sam

---

## 12. 常见问题
1）`No module named pandas`：
```bash
pip install -r requirements.txt
```

2）QC 不通过：查看 `results/long/qc_issues.csv`

3）MixedLM 奇异矩阵：脚本内置 `lbfgs -> powell` 回退
