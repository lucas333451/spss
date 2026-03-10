# spss — Clean Questionnaire Analysis Pipeline / 问卷分析清爽版流程

[中文说明 / Chinese guide](./README_zh.md)

[Results reading guide](./docs/RESULTS_READING_GUIDE.md)

[Chinese results reading guide / 中文结果阅读指南](./docs/RESULTS_READING_GUIDE.zh.md)

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
    - SPSS-aligned WWR polynomial significance via `scripts/wwr_polynomial_significance.py` (including direct direction labels: linear increase/decrease and whether WWR=45 is the highest or lowest; PNG uses main-panel + side-summary layout to reduce overlap)
    - `scripts/item_level_significance.py` as the item-level significance entry for S / B / IPQ experience-group inference with unified csv/png/md/json outputs
  - also auto-generates:
    - `significance_index.md` (what to read first)
    - `research_questions_map.md` (which result answers which question)
    - `significance_guide.png` (visual overview of the navigation)

### 4) Results top-level guide
- `scripts/build_results_guide.py`
  - auto-generates:
    - `RESULTS_GUIDE.md`
    - `RESULTS_GUIDE.png`
  - connects descriptive / significance / overall / experience / raw / qc into one reading path

### 5) Legacy preserved
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
        csv/
        png/
      experience/
        csv/
        png/
    qc/                # only when --with-qc is used
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
    qc/                # only when --with-qc is used
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

## Maintenance note / 维护提示
- After editing user-facing docs or notebooks, run:
  - `python3 scripts/check_doc_consistency.py`
- For a broader clean-main entrypoint health check, run:
  - `python3 scripts/check_main_entrypoints.py`
- For a lightweight executable smoke suite, run:
  - `python3 scripts/run_smoke_checks.py`
- This helps keep the clean `main` reading surface from drifting back to legacy `results/model` / `results/research` wording, checks that key entry files and README links still exist, and verifies that the top-level results guide can still be generated in a temporary output folder.

## Notes / 说明
- `main` intentionally avoids too many exploratory outputs.
- If you need the previous full workflow, use branch `raw`.
- Current `main` prioritizes readability and operational clarity over maximal breadth.
