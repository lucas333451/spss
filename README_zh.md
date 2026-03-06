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
- `scripts/analysis_s_items.py`：S1~S4（可供性主构念）+ S5（情感补充）分题分析，含角度1/角度2 + 人群拆分/对比
- `scripts/analysis_b_items.py`：B1~B3/Bmean 专项分析（主要 C1）
- `scripts/analysis_groups.py`：四类人群拆分/对比的公共模块
- `scripts/report_summary.py`：自动生成角度1/角度2叙事总结
- `scripts/diagnostics_lmm.py`：诊断分析（交互来源/随机结构敏感性/Repetition）
- `scripts/pipeline.py`：一键全流程执行（支持 skip 参数；可选 `--with-r` 自动复算 R 版主模型并输出到 `results/r_model/`）
- `scripts/build_report_md.py`：将结果目录汇总成一个 markdown（全量索引型）
- `scripts/build_report_key_md.py`：生成关键结果详版 markdown（更适合直接发给我做解读）
- `scripts/build_report_data_md.py`：生成“数据直写型”markdown（关键表格直接展开，不依赖索引跳转）
- `RESULTS_MAP.md`：一页速查（每个研究问题优先看哪3个文件）
- `scripts/run_analysis_R.R`：可选：用 R（lme4/lmerTest/emmeans）复算主模型，生成投稿更常见口径的结果表

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

### 第四步：研究分析（模块化）
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
- S1~S4：7分，构成“感知可供性”主构念
- Afford4：由 S1–S4 合成，带缺失条目规则（默认要求 ≥3/4 条目有效才计算；见 `--afford4-min-items`）
- S5：9分，作为“情感体验”补充指标（不并入 S1~S4 主构念；在 long 表中也会输出为 `SAM_Valence` 以避免与 7 分条目混淆）
- B1~B3：7分

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

- `results/research/table_fixed_effects_all_dv.csv`（分题：S1~S4主构念 + S5补充）
- `results/research/table_angle1_main_interactions_all_dv.csv`
- `results/research/table_angle2_round_interactions_all_dv.csv`
- `results/research/groups/manifest.csv` 与 `results/research/groups/group_*.csv`（按 Experience×SportFreq 四类人群拆分数据）
- `results/research/group2_comparisons_item_level.csv`（两种二分法合并：SportFreqGroup + ExperienceGroup，建议优先查看）
- `results/research/group2_complexity_mean_table.csv`（两种二分法合并的复杂度均值）
- `results/research/group2_complexity_delta_significance.csv`（两种二分法合并的 C1-C0 显著性）
- `results/research/group2_complexity_mean_table_by_wwr.csv`（两种二分法合并的 WWR 分层复杂度均值）
- `results/research/group2_complexity_delta_significance_by_wwr.csv`（两种二分法合并的 WWR 分层 C1-C0 显著性）
- `results/research/group_comparisons_item_level.csv`（四类人群在分题指标上的组间对比，建议作为补充）
- `results/research/affordance_s1_s4_dimension_map.csv`（S1-S4 细分维度映射）
- `results/research/affordance_s1_s4_group2_comparisons.csv`（仅 S1-S4 的 2+2 人群比较）
- `results/research/affordance_s1_s4_group4_comparisons.csv`（仅 S1-S4 的 4类人群比较）
- `results/research/group2_comparisons_item_level_sportfreqgroup.csv` / `_experiencegroup.csv`（分开文件）
- `results/research/group2_complexity_mean_table_sportfreqgroup.csv` / `_experiencegroup.csv`（分开文件）
- `results/research/group2_complexity_delta_significance_sportfreqgroup.csv` / `_experiencegroup.csv`（分开文件）
- `results/research/group2_complexity_mean_table_by_wwr_sportfreqgroup.csv` / `_experiencegroup.csv`（分开文件：WWR分层均值）
- `results/research/group2_complexity_delta_significance_by_wwr_sportfreqgroup.csv` / `_experiencegroup.csv`（分开文件：WWR分层显著性）
- `results/research/group_complexity_mean_table.csv`（直观二维表：每个DV在人群×复杂度下的均值）
- `results/research/group_complexity_delta_significance.csv`（组间复杂度差异显著性：比较各组 C1-C0）
- `results/research/group_complexity_mean_table_by_wwr.csv`（按 WWR 分层的人群×复杂度均值）
- `results/research/group_complexity_delta_significance_by_wwr.csv`（按 WWR 分层的人群复杂度差异显著性）
- `results/research/group_complexity_delta_by_round.csv`（按轮次细分的 C1-C0）
- `results/research/group_complexity_delta_round_shift.csv`（Round2-Round1 的复杂度差值变化）
- `results/research/scene_level_means.csv`（单场景单元均值：Block×Position / WWR / Repetition）
- `results/research/scene_level_deltas.csv`（单场景 C1-C0 差值）
- `results/research/scene_group_comparisons_by_condition.csv`（单场景组间比较：按 C0/C1 分开）
- `results/research/scene_group_comparisons_c0.csv`（仅 C0 的单场景组间比较）
- `results/research/scene_group_comparisons_c1.csv`（仅 C1 的单场景组间比较）
- `results/research/figures/scene_delta_heatmap_S*_R*.png`（单场景差值热图）
- `results/research/figures/group_complexity_heatmap_S*.png`（人群×复杂度热图）
- `results/research/figures/group_complexity_delta_S*.png`（各人群 C1-C0 条形图）
- `results/research/b_items_long_c1.csv`、`b_items_condition_means.csv`、`b_items_group_comparisons.csv`（B1~B3 专项：主要针对 C1）
- `results/research/analysis-2/task1/<experience|sportfreq>/<raw|qc>/analysis2_scene_stage_gap_long.csv` + `analysis2_scene_stage_gap_wide_<SceneID>.csv` + `task1_scene_stage_gap_figures/scene_<SceneID>.png`（analysis-2/task1：同场景 Round2-Round1 差异；S1–S5 每题都有；输出 p、sr、dz；按人群分层；每个场景一张图，共约 6 张）
- `results/research/analysis-2/task1/<experience|sportfreq>/<raw|qc>/analysis2_b_stage_gap_long.csv` + `task1b_b_stage_gap_figures/B1.png|B2.png|B3.png`（analysis-2/task1b：B1–B3 Round2-Round1 差异；输出 p、sr、dz；按人群分层；总共 3 张图）
- `results/research/analysis-2/task2/<experience|sportfreq>/<raw|qc>/analysis2_core_imm_suite_s_effects.csv` + `analysis2_core_imm_suite_s_models.csv` + `analysis2_core_imm_suite_b_effects.csv` + `analysis2_core_imm_suite_b_models.csv` + `analysis2_core_imm_suite_group_focus.csv` + `analysis2_core_imm_suite_posthoc_s_wwr_by_group.csv` + `analysis2_measurement_reliability_s1_s4.csv` + `task2_core_imm_suite_figures/*.png`（analysis-2/task2 core_Imm_suite：围绕 WWR/Complexity/Group 的问卷评分分层 LMM；补充人群相关项汇总、S题 WWR 事后比较、S1-S4 信度指标，并输出可视化 PNG）
- `raw`=全样本；`qc`=排除以下 8 人：孙校聪、康少勇、张钰鹏、杨可、洪婷婷、陈韬、高梓楠、赵国宏。
- `results/research/analysis_narrative.md`（角度1/角度2自动叙事总结）
- `results/research/angle1_c1_minus_c0_by_group.csv`（直接回答“C1是否普遍更低、降幅是否一致”）
- `results/research/angle2_round_diff_by_group.csv`（各人群 Round2-Round1）
- `results/research/round_icc_by_group.csv`（各人群 Round 一致性 ICC(A,1)）
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

- `results/FIGURE_INDEX.md`（PNG优先图索引：图名→问题→路径）
- `results/figures_main_paper/raw/` 与 `results/figures_main_paper/qc/`（主文 6-8 张核心图两套输出，各自含索引 + 双语caption草稿 + manifest）
- `results/analysis_report_bundle.md`（将所有结果汇总成一个 markdown）
- `results/r_model/anova_type3_afford4.csv`（lmerTest 的 Type III ANOVA 表；partial η² 的基础表）
- `results/r_model/effectsize_eta_squared_partial_afford4.csv`（partial η² 主表；回答 WWR / Complexity / 分组效应量时优先查看）
- `results/r_model/effectsize_eta_squared_partial_summary_afford4.csv`（简化汇总：term、partial η²、量级）
- `results/r_model/effectsize_eta_squared_partial_afford4.png`（partial η² 论文风格 PNG，总览各固定项效应量；风格朝 Building and Environment 靠拢）
- `results/r_model/effectsize_eta_squared_partial_status.txt`（仅在 partial η² 未成功导出时生成，说明失败原因）

---

## 8. Long格式字段
`SubjectID, Order, Block, Repetition, RepetitionC, Position, WWR, Condition, Complexity, SportFreq, ExperienceGroup, SportFreqGroup, S1~S5,（可选 S5_7）, B1~B3, Bmean, SceneID`

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

- 推荐使用：`notebooks/colab_setup.ipynb`
- 若你在 Colab 安装了 R，可在 pipeline 后加 `--with-r`，自动生成 `results/r_model/`（lme4/lmerTest/emmeans 口径）。
- 投稿稳健性建议：使用 `--with-r-robustness` 一次性跑 Satterthwaite + Kenward–Roger，并生成 p 值对比表。
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
