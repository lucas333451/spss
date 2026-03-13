# R 环境安装说明：item-level 统一结构 LMM

这份说明只服务于 `main` 分支中的这条新主线：
- `scripts/run_item_level_lmm.py`
- `scripts/run_item_level_lmm_R.R`

目标：保证 `results/significance/.../item_level_lmm/` 可以真实跑出结果。

---

## 1. 先检查环境是否就绪
先运行：

```bash
python3 scripts/check_r_item_level_lmm.py
```

如果返回：
- `ok: true` → 可以直接跑
- `Rscript_not_found` → 先安装 R
- `missing: [...]` → 先安装缺失的 R 包

---

## 2. Linux / Ubuntu / Debian 安装 R

```bash
sudo apt-get update
sudo apt-get install -y r-base r-base-dev
```

安装完后确认：

```bash
Rscript --version
```

---

## 3. 安装 item-level LMM 所需 R 包

```bash
Rscript -e "install.packages(c('optparse','readr','dplyr','tidyr','stringr','lme4','lmerTest','emmeans','jsonlite'), repos='https://cloud.r-project.org')"
```

安装完成后再次检查：

```bash
python3 scripts/check_r_item_level_lmm.py
```

---

## 4. 运行 unified item-level LMM
如果 long-format 已经存在：

```bash
python3 scripts/run_item_level_lmm.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/significance/qc/item_level_lmm
```

如果你是从完整主流程触发：

```bash
python3 scripts/significance_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/significance \
  --with-qc
```

---

## 5. 主要输出文件
跑完后重点看：

- `md/item_level_lmm_report_zh.md`
- `csv/item_level_lmm_type3_fixed_effects.csv`
- `csv/item_level_lmm_type3_fixed_effects_fdr.csv`
- `csv/item_level_lmm_fixed_effect_estimates.csv`
- `csv/item_level_lmm_emmeans.csv`
- `csv/item_level_lmm_pairwise.csv`
- `csv/item_level_lmm_fit_indices.csv`
- `csv/item_level_lmm_random_effects.csv`

---

## 6. 常见问题

### Q1. 提示 `Rscript not found`
说明机器没有安装 R，先执行第 2 步。

### Q2. 提示缺少 `lme4 / lmerTest / emmeans`
说明 R 已安装，但包不全，执行第 3 步。

### Q3. mixed model 拟合失败怎么办？
当前脚本会自动尝试：
1. `(1 + Complexity | SubjectID)`
2. 回退到 `(1 | SubjectID)`

如果还失败，优先检查：
- 某些题目是否缺失太多
- 某些因变量是否几乎没有方差
- 某些组别是否样本过少

### Q4. 为什么这里用 R 而不是只用 Python？
因为当前这条主线需要更贴近期刊写法的输出：
- Type III fixed effects
- lmerTest 的 df / F / p
- emmeans 与 pairwise comparisons

这套在 R 里更直接，也更方便和论文报告口径对齐。
