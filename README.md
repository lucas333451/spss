# spss — Clean Questionnaire Analysis Pipeline / 问卷分析清爽版流程

[中文说明 / Chinese guide](./README_zh.md)

## Overview / 概述
This repository now keeps the **main branch** focused on two output families only:

1. **Descriptive analysis / 描述性分析**
2. **Significance analysis / 显著性分析**

Current scope on `main` is intentionally narrowed to:
- **overall**
- **experience**

The previous larger, more exploratory version is preserved in branch:
- **`raw`**

---

## Branch policy / 分支策略
- `main`: cleaned production branch, simpler structure, fewer outputs
- `raw`: archived full/legacy branch with broader and more crowded analysis layout

---

## Current pipeline structure / 当前主流程结构
### 1) Transform
- `scripts/transform_wide_to_long.py`
  - Excel wide table → long format
  - QC-related structural preparation

### 2) Descriptive pipeline
- `scripts/descriptive_pipeline.py`
  - `overall`
  - `experience`
  - covers:
    - `S1–S5`
    - `B1–B3` / `Bmean`
    - `IPQ`
  - now includes:
    - basic descriptives: `n / mean / sd / median / min / max`
    - distribution metrics: `skewness / kurtosis`
    - `95% CI`
    - normality check: `Shapiro p`
    - stratified descriptives by `WWR / Complexity / ExperienceGroup`
    - PNG figures: `boxplots / violin plots`
    - figure layout: `main panel + right-side statistical summary box`, to avoid overlapping annotations

### 3) Significance pipeline
- `scripts/significance_pipeline.py`
  - `overall`
  - `experience`
  - currently centered on:
    - core LMM model via `scripts/run_analysis.py` (now with corresponding PNG outputs for model comparison, fixed effects, interactions, random effects, and simple effects)
    - SPSS-aligned WWR polynomial contrast via `scripts/analysis2_task5_spss_polynomial.py` (including direct direction labels: linear increase/decrease and whether WWR=45 is the highest or lowest)
  - also auto-generates:
    - `significance_index.md` (what to read first)
    - `research_questions_map.md` (which result answers which question)

### 4) Legacy preserved
- `scripts/pipeline_raw_legacy.py`
  - old crowded pipeline kept for reference

---

## Output layout / 输出目录
```text
results/
  long/
  descriptive/
    raw/
      overall/
      experience/
    qc/                # only when --with-qc is used
      overall/
      experience/
  significance/
    overall/
      core_model/
    raw/
      overall/
        task5/
      experience/
        task5_group_only/
        task5_group_round/
    qc/                # only when --with-qc is used
      overall/
        task5/
      experience/
        task5_group_only/
        task5_group_round/
```

---

## Quick start / 快速开始
### Full clean pipeline
```bash
python scripts/pipeline.py \
  --excel "your_file.xlsx" \
  --sheet 0 \
  --out-root results \
  --with-qc
```

### Descriptive only
```bash
python scripts/descriptive_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/descriptive \
  --with-qc
```

### Significance only
```bash
python scripts/significance_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/significance \
  --with-qc
```

---

## Notes / 说明
- `main` intentionally avoids too many exploratory outputs.
- If you need the previous full workflow, use branch `raw`.
- Current `main` prioritizes readability and operational clarity over maximal breadth.
