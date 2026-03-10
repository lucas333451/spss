# spss（清爽主线版）— 问卷分析流程

- 英文结果阅读指南：`./docs/RESULTS_READING_GUIDE.md`
- 中文结果阅读指南：`./docs/RESULTS_READING_GUIDE.zh.md`

## 当前主旨
现在 `main` 分支只保留两大类输出：

1. **描述性分析**
2. **显著性分析**

并且当前只先保留两个分析入口：
- **overall**
- **experience**

原来更臃肿、更发散、更偏“全家桶”的版本，已经完整保存在：
- **`raw` 分支**

---

## 分支说明
- `main`：整理后的正式主线，结构更清楚，输出更少、更聚焦
- `raw`：原始大而全版本，保留旧结构和更多 exploratory 输出

---

## main 分支当前结构
### 1）数据整理
- `scripts/transform_wide_to_long.py`
  - Excel 宽表转 long
  - 进行基础结构整理与 QC 准备

### 2）描述性分析
- `scripts/descriptive_pipeline.py`
  - 只做：
    - `overall`
    - `experience`
  - 覆盖内容：
    - `S1–S5`
    - `B1–B3 / Bmean`
    - `IPQ`
  - 当前已包含：
    - 基础统计：`n / mean / sd / median / min / max`
    - 分布指标：`skewness / kurtosis`
    - `95% CI`
    - 正态性检验：`Shapiro p`
    - 分层描述：`WWR / Complexity / ExperienceGroup`
    - PNG：`箱线图 / 小提琴图`
    - 图版式：`主图 + 右侧统计摘要框`，避免数据结果彼此重叠影响观感

### 3）显著性分析
- `scripts/significance_pipeline.py`
  - 只做：
    - `overall`
    - `experience`
  - 当前重点包括：
    - `scripts/run_analysis.py` 的核心 LMM 模型（现已为模型比较、固定效应、交互、随机效应、简单效应等关键结果补对应 PNG）
    - `scripts/wwr_polynomial_significance.py` 的 WWR 三水平趋势显著性检验（可直接判断线性增加/减少，以及 45 时最高/最低；PNG 采用主图 + 右侧摘要框，减少标注重叠）
    - `scripts/item_level_significance.py` 的逐题显著性入口（覆盖 S / B / IPQ 的 experience 组间显著性，统一输出 csv/png/md/json）
  - 当前还会自动生成：
    - `significance_index.md`（先看哪些文件）
    - `research_questions_map.md`（每个研究问题对应看哪份结果）
    - `significance_guide.png`（导航信息的图形总览版）

### 4）结果总导航
- `scripts/build_results_guide.py`
  - 自动生成：
    - `RESULTS_GUIDE.md`
    - `RESULTS_GUIDE.png`
  - 用于串起 descriptive / significance / overall / experience / raw / qc 的阅读顺序

### 5）旧版流程仍保留
- `scripts/pipeline_raw_legacy.py`
  - 原来那套复杂 pipeline，先保留作参考，不删

---

## 输出目录
```text
results/
  long/
  descriptive/
    raw/
      overall/
        csv/
        png/
      experience/
        csv/
        png/
    qc/                # 仅在 --with-qc 时生成
      overall/
        csv/
        png/
      experience/
        csv/
        png/
  significance/
    raw/
      overall/
        core_model/
          csv/
          png/
          md/
          txt/
          json/
        wwr_polynomial/
          csv/
          png/
          md/
          json/
      experience/
        wwr_polynomial_group_only/
          csv/
          png/
          md/
          json/
        wwr_polynomial_group_round/
          csv/
          png/
          md/
          json/
    qc/                # 仅在 --with-qc 时生成
      overall/
        core_model/
          csv/
          png/
          md/
          txt/
          json/
        wwr_polynomial/
          csv/
          png/
          md/
          json/
      experience/
        wwr_polynomial_group_only/
          csv/
          png/
          md/
          json/
        wwr_polynomial_group_round/
          csv/
          png/
          md/
          json/
```

---

## 快速开始
### 跑完整清爽版主流程
```bash
python scripts/pipeline.py \
  --excel "your_file.xlsx" \
  --sheet 0 \
  --out-root results \
  --with-qc
```

### 只跑描述性分析
```bash
python scripts/descriptive_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/descriptive \
  --with-qc
```

### 只跑显著性分析
```bash
python scripts/significance_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/significance \
  --with-qc
```

---

## 维护提示
- 如果你修改了用户入口文档或 Colab notebook，建议顺手运行：
  - `python3 scripts/check_doc_consistency.py`
- 如果你想做更完整的 clean main 入口体检，再运行：
  - `python3 scripts/check_main_entrypoints.py`
- 这个检查不仅能防止结果入口漂回旧的 `results/model` / `results/research` 口径，也会检查关键入口文件和 README 链接是否还存在。

## 说明
- 现在 `main` 故意不再追求“能出特别多结果”，而是优先保证结构清楚、好用、好维护。
- 如果需要旧版那套更全的输出，直接切到 `raw` 分支。
- 当前 `main` 的原则是：**先收敛，再逐步加回真正必要的内容。**
