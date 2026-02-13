# spss（问卷宽表 -> Long格式 -> LMM论文结果）

这个项目用 **Python 开源方案**替代 SPSS，专门服务你的 VR+EEG 问卷流程：
- Excel 宽表（每位被试一行）
- 自动转换为 long-format（每位被试 12 行）
- 自动做 QC
- 自动导出论文可用表格与图

---

## 1. 适用数据（已按你的问卷结构适配）

- Block1：Q2~Q7（每个 Q 含 S1~S5）
- Block2：Q9~Q14（每个 Q 含 S1~S5）
- 顺序变量：`Q1.8_场景顺序编号`（Order=1/2）
- 频率变量：`Q1.5_近 6 个月平均运动频率：`
- C1汇总题：
  - Block1: Q8.1~Q8.3
  - Block2: Q15.1~Q15.3

映射 `Order × Block × Position -> (WWR, Condition)` 已硬编码到脚本中。

---

## 2. 目录结构（新手先看）

- `scripts/transform_wide_to_long.py`：核心转换 + QC
- `scripts/run_analysis.py`：基础 LMM + 论文结果表导出
- `scripts/analyze_research_questions.py`：扩展分析（角度1/角度2）
- `scripts/pipeline.py`：一键全流程
- `docs/PROJECT_OVERVIEW.md`：项目总览
- `requirements.txt`：依赖

---

## 3. 安装

### 3.1 推荐（有 venv）
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.2 如果系统没有 venv/pip（Ubuntu/Debian）
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. 最快上手（一步一步）

### Step 1: 宽表转长表 + QC
```bash
python scripts/transform_wide_to_long.py \
  --excel "/home/wannaqueen66/VR+EEG实验问卷-原始数据-2026-02-04.xlsx" \
  --out-dir results/long
```

输出重点：
- `results/long/long_format.csv`
- `results/long/qc_issues.csv`
- `results/long/qc_summary.json`
- `results/long/missing_rate.csv`

### Step 2: 出论文基础结果表
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

输出重点：
- `table_descriptives.csv`
- `table_fixed_effects.csv`
- `table_main_interactions.csv`
- `paper_tables.md`（可直接贴文稿）
- `figures/wwr_complexity_afford5.png`

### Step 3: 跑“角度1+角度2”扩展分析
```bash
python scripts/analyze_research_questions.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research
```

输出重点：
- `table_fixed_effects_all_dv.csv`
- `table_main_interactions_all_dv.csv`
- `round_consistency_by_subject.csv`
- `round_consistency_by_group.csv`
- `figures/heatmap_afford5_*.png`
- `figures/interaction_afford5_by_freqgroup.png`
- `figures/round_diff_afford5_by_freqgroup.png`

---

## 5. 一键全流程（推荐）

```bash
python scripts/pipeline.py \
  --excel "/home/wannaqueen66/VR+EEG实验问卷-原始数据-2026-02-04.xlsx" \
  --out-root results
```

会自动按顺序执行：
1) 转长表 2) 基础论文表 3) 扩展研究问题分析

---

## 6. Long-format 字段说明

每行是“被试 × Block × Position”一条记录，核心字段：
- `SubjectID, Order, Block, Position`
- `WWR, Condition(C0/C1), Complexity(0/1), SceneID`
- `SportFreq`
- `S1~S5`
- `Afford4`（S1~S4均值）
- `Afford5`（S1~S5均值）
- `Pleasure`（S5）
- `B1~B3, Bmean`（仅 C1 行有值，C0 必须 NA）

---

## 7. QC 通过标准

必须同时满足：
- 每位被试 12 行
- 每个 Block 6 行
- 每个 Block 内 C1=3, C0=3
- 每个 Block 内 WWR: 15×2, 45×2, 75×2
- C0 行 B1~B3 全为空；C1 行 B1~B3 非空且同一 Block 内一致

---

## 8. 常见问题

### Q1: 报错 `No module named pandas`
没装依赖，先执行：
```bash
pip install -r requirements.txt
```

### Q2: QC 出现异常被试怎么办？
先看：
- `qc_issues.csv`（哪个被试、哪条规则没过）
- `missing_rate.csv`（是否缺失过高）

### Q3: 表里 `C(WWR)[T.45]` 看不懂
`run_analysis.py` 已加 `APA_Term` 自动重命名，可直接看人类可读术语。

---

## 9. 给新同学的建议流程（30分钟内跑通）

1. 先跑 `transform_wide_to_long.py`，确认 QC 全过
2. 再跑 `run_analysis.py`，拿到可贴论文的表
3. 最后跑 `analyze_research_questions.py`，补“重复收敛/经验塑形”亮点


## 10. Colab 部署（免本地环境）

如果你想直接在云端跑，见：
- `docs/COLAB_GUIDE.md`

最短命令（在 Colab 中）：
```bash
!git clone https://github.com/wannaqueen66-create/spss.git
%cd spss
!pip -q install -r requirements.txt
!python scripts/pipeline.py --excel "你的Excel文件名.xlsx" --out-root results
```
