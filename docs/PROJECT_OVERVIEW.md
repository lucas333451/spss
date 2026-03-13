# 项目总览（给第一次接触本项目的人）

## 这个项目现在解决什么问题？
把问卷系统导出的 **Excel 宽表**（每个被试一行）转换为可建模的 **long-format**，并在当前 `main` 分支上输出两类更清爽的结果：

1. **描述性分析**
2. **显著性分析**

当前 `main` 的默认可见范围只保留：
- `overall`
- `experience`

更大、更旧、更 exploratory 的流程与输出，保留在：
- `raw` 分支

---

## 当前 main 的数据流

### 1）原始 Excel（宽表）
输入来源是问卷平台导出的 Excel 宽表。

### 2）宽转长
`scripts/transform_wide_to_long.py`

产出：
- `results/long/long_format.csv`
- 宽转长相关的 QC / 结构检查文件

这是后续全部分析的共同入口。

### 3）描述性分析
`scripts/descriptive_pipeline.py`

当前 `main` 默认输出：
- `results/descriptive/raw/overall/`
- `results/descriptive/raw/experience/`
- `results/descriptive/qc/overall/`（仅 `--with-qc`）
- `results/descriptive/qc/experience/`（仅 `--with-qc`）

主要内容：
- S1–S5
- B1–B3 / Bmean
- IPQ
- 基础统计：`n / mean / sd / median / min / max`
- 分布指标：`skewness / kurtosis`
- `95% CI`
- 正态性检查：`Shapiro p`
- 分层描述：`WWR / Complexity / ExperienceGroup`
- PNG：箱线图 / 小提琴图

### 4）显著性分析
`scripts/significance_pipeline.py`

当前 `main` 默认输出：
- `results/significance/raw/overall/core_model/`
- `results/significance/raw/overall/wwr_polynomial/`
- `results/significance/raw/experience/wwr_polynomial_group_only/`
- `results/significance/raw/experience/wwr_polynomial_group_round/`
- 对应的 `qc/` 分支（仅 `--with-qc`）

主要内容：
- `scripts/run_analysis.py`：整体核心模型（LMM 主体）
- `scripts/wwr_polynomial_significance.py`：WWR 三水平线性 / 二次趋势显著性
- `scripts/run_item_level_lmm.py` + `scripts/run_item_level_lmm_R.R`：S1–S5、B1–B3、IPQ 各题或维度的统一结构逐题 LMM（WWR、Complexity、ExperienceGroup 及其交互保持一致），并导出 Type III、固定效应估计、EMMs、pairwise、多重校正、拟合指标、随机部分结果
- 自动导航文件：
  - `significance_index.md`
  - `research_questions_map.md`
  - `significance_guide.png`
- 面向当前 clean main 的正文辅助入口：
  - `scripts/build_main_branch_figure_pack.py`（整理 main 分支正文优先图清单）
  - `scripts/build_main_branch_writing_guide.py`（生成 main 分支正文写作提纲）

### 5）结果总导航
`scripts/build_results_guide.py`

产出：
- `results/RESULTS_GUIDE.md`
- `results/RESULTS_GUIDE.png`

作用：
- 把 descriptive / significance / overall / experience / raw / qc 串成统一阅读顺序

---

## 你最常用的 3 个命令

### 1）跑完整 clean main 流程
```bash
python scripts/pipeline.py \
  --excel "your_file.xlsx" \
  --sheet 0 \
  --out-root results \
  --with-qc
```

### 2）只跑描述性分析
```bash
python scripts/descriptive_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/descriptive \
  --with-qc
```

### 3）只跑显著性分析
```bash
python scripts/significance_pipeline.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/significance \
  --with-qc
```

---

## 现在最推荐先看哪里？

如果你是第一次读结果，优先顺序建议是：

1. `results/RESULTS_GUIDE.md`
2. `results/descriptive/qc/overall/png/`
3. `results/descriptive/qc/experience/png/`
4. `results/significance/significance_guide.png`
5. `results/significance/qc/overall/core_model/md/results_draft_zh.md`
6. `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`
7. `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`

如果没有跑 `--with-qc`，就把上述路径里的 `qc/` 改看 `raw/`。

---

## 什么时候看 raw？什么时候看 qc？

- **正式报告 / 对外汇报 / 写论文**：优先看 `qc`
- **对照原始情况 / 做稳健性比较**：再看 `raw`

一句话：
- `qc` = 正式口径优先
- `raw` = 对照与补充

---

## 什么时候才需要旧版 research / analysis-2 那套？
如果你明确要：
- 旧版更发散的 exploratory 输出
- analysis-2 / task1~task5 那套历史结构
- 旧 research/model 口径文件

那就不要默认看当前 `main`，而是转去：
- `raw` 分支

也就是说：
**当前 main 的目的不是保留所有旧结果，而是先把主线读法收敛清楚。**
