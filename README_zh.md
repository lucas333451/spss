# spss（纯中文）— 问卷宽表转长表 + LMM 论文分析流程

## 目录
- [1. 项目简介](#1-项目简介)
- [2. 仓库结构](#2-仓库结构)
- [3. 安装](#3-安装)
- [4. 快速开始](#4-快速开始)
- [5. 一键全流程](#5-一键全流程)
- [6. 输出文件说明](#6-输出文件说明)
- [7. Long格式字段](#7-long格式字段)
- [8. 质控规则](#8-质控规则)
- [9. Colab 部署](#9-colab-部署)
- [10. 常见问题](#10-常见问题)

---

## 1. 项目简介
本项目用于替代 SPSS，完成以下流程：
1. 读取问卷系统导出的 Excel 宽表（每位被试一行）
2. 转为可建模 long-format（每位被试 12 行）
3. 自动执行 QC（结构与映射校验）
4. 输出线性混合模型（LMM）结果、论文可贴表格与图

---

## 2. 仓库结构
- `scripts/transform_wide_to_long.py`：宽表转长表 + QC
- `scripts/run_analysis.py`：基础 LMM + 论文结果表导出
- `scripts/analyze_research_questions.py`：扩展分析（角度1/角度2）
- `scripts/pipeline.py`：一键全流程执行
- `docs/PROJECT_OVERVIEW.md`：项目总览
- `docs/COLAB_GUIDE.md`：Colab 部署与使用
- `notebooks/spss_colab.ipynb`：现成可跑的 Colab Notebook

---

## 3. 安装
```bash
pip install -r requirements.txt
```
如果系统缺少 pip/venv（Ubuntu/Debian）：
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

---

## 4. 快速开始
### 第一步：宽表转长表 + QC
```bash
python scripts/transform_wide_to_long.py \
  --excel "/path/to/your.xlsx" \
  --out-dir results/long
```

### 第二步：基础论文结果表
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

### 第三步：扩展研究分析
```bash
python scripts/analyze_research_questions.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research
```

---

## 5. 一键全流程
```bash
python scripts/pipeline.py \
  --excel "/path/to/your.xlsx" \
  --out-root results
```

---

## 6. 输出文件说明
- `results/long/long_format.csv`：长格式主数据
- `results/long/qc_issues.csv`：QC问题明细
- `results/long/qc_summary.json`：QC总览
- `results/model/table_descriptives.csv`：描述统计
- `results/model/table_fixed_effects.csv`：固定效应系数表
- `results/model/table_main_interactions.csv`：主效应/交互项汇总
- `results/model/paper_tables.md`：可直接粘贴文稿的 Markdown 表
- `results/research/table_fixed_effects_all_dv.csv`：多因变量固定效应
- `results/research/round_consistency_by_group.csv`：重复一致性分组结果

---

## 7. Long格式字段
`SubjectID, Order, Block, Position, WWR, Condition, Complexity, SportFreq, S1~S5, Afford4, Afford5, Pleasure, B1~B3, Bmean, SceneID`

---

## 8. 质控规则
必须满足：
- 每位被试 12 行
- 每个 Block 6 行
- 每个 Block 中 C1 与 C0 各 3 行
- 每个 Block 中 WWR 分布为 15×2、45×2、75×2
- B1~B3 仅允许在 C1 行非空（C0 行必须 NA）

---

## 9. Colab 部署
- 超详细零基础指南：`docs/COLAB_GUIDE.md`
- 现成 Notebook：`notebooks/spss_colab.ipynb`（逐格运行，只改 `EXCEL_FILE`）
- 建议先看指南第 3 节“按顺序运行代码块”，再开始

---

## 10. 常见问题
1）报错 `No module named pandas`：
```bash
pip install -r requirements.txt
```

2）QC 不通过：
先查看 `results/long/qc_issues.csv` 与 `missing_rate.csv`。

3）模型项看不懂（如 `C(WWR)[T.45]`）：
查看导出表中的 `APA_Term` 列（已自动重命名）。
