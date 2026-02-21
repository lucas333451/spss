# 项目总览（给第一次接触本项目的人）

## 这个项目解决什么问题？
把问卷系统导出的 **Excel 宽表**（每个被试一行）转换为可建模的 **long-format**，并完成：
1. 质量检查（QC）
2. 线性混合模型（LMM）
3. 论文可贴表格与图

## 数据流
1. 原始 Excel（宽表）
2. `transform_wide_to_long.py` → `results/long/long_format.csv` + QC（`qc_summary.json` 等）
3. `build_group_manifest.py` → `results/group_manifest.csv`（含 Order/Round/Pos/trial_key，用于眼动/EEG 对齐）
4. `run_analysis.py` → `results/model/*`（Afford4 主模型、simple effects、论文表、图）
5. `analysis_s_items.py` + `analysis_b_items.py` + `report_summary.py` → `results/research/*`（角度1/角度2 + 分组 + 场景级输出）
6. `diagnostics_lmm.py` → `results/diagnostics/*`（交互筛查/随机结构敏感性/轮次诊断；带审计日志）
7. `write_provenance.py` → `results/provenance.json`（git commit/包版本/参数，审稿可复现指纹）
8. （可选）`run_analysis_R.R` → `results/r_model/*`（R: lme4/lmerTest/emmeans 投稿口径）

## 你最常用的两个命令
- 先转长表：`transform_wide_to_long.py`
- 再出论文表：`run_analysis.py`

## 什么时候用扩展脚本？
当你要报告“重复两遍是否收敛”“高频组是否更稳定”时，使用：
- `analysis_s_items.py`
- `analysis_b_items.py`
- `report_summary.py`
（或直接跑 `pipeline.py` 自动编排）
