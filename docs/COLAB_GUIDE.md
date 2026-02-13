# Colab 部署与运行指南（spss 项目）

本指南用于在 **Google Colab** 上完整跑通本项目：
- 宽表 Excel → long-format
- QC 检查
- LMM 结果表
- 研究问题扩展分析（角度1+角度2）

> 适合：本地环境缺 pip/venv、想快速复现结果、想分享给同学一键运行。

---

## 1) 打开 Colab 并准备运行环境

新建 Notebook 后，先执行：

```python
!python --version
!pip -q install --upgrade pip
```

克隆仓库并安装依赖：

```python
!git clone https://github.com/wannaqueen66-create/spss.git
%cd spss
!pip -q install -r requirements.txt
```

---

## 2) 上传 Excel 数据

方式A（推荐新手）：直接上传文件到当前 Colab 会话。

```python
from google.colab import files
uploaded = files.upload()  # 选择你的 Excel 文件
```

上传后，文件会出现在当前目录（通常是 `/content/spss/`）。

查看文件名：

```python
import os
print(os.listdir('.'))
```

假设上传后的文件名为：
`VR+EEG实验问卷-原始数据-2026-02-04.xlsx`

---

## 3) 一键全流程运行（推荐）

```python
!python scripts/pipeline.py \
  --excel "VR+EEG实验问卷-原始数据-2026-02-04.xlsx" \
  --out-root results
```

运行成功后，你会得到：
- `results/long/`（long格式+QC）
- `results/model/`（基础论文结果表）
- `results/research/`（角度1+角度2扩展分析）

---

## 4) 分步运行（便于排错）

### Step 1: 宽转长 + QC
```python
!python scripts/transform_wide_to_long.py \
  --excel "VR+EEG实验问卷-原始数据-2026-02-04.xlsx" \
  --out-dir results/long
```

### Step 2: 基础论文结果表
```python
!python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

### Step 3: 研究问题扩展分析
```python
!python scripts/analyze_research_questions.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/research
```

---

## 5) 查看关键输出

```python
!find results -maxdepth 3 -type f | sort
```

重点文件：
- `results/long/qc_summary.json`
- `results/long/qc_issues.csv`
- `results/model/paper_tables.md`
- `results/model/table_fixed_effects.csv`
- `results/research/table_main_interactions_all_dv.csv`
- `results/research/round_consistency_by_group.csv`

---

## 6) 下载结果到本地

### 下载单个文件
```python
from google.colab import files
files.download('results/model/paper_tables.md')
```

### 打包全部 results 再下载
```python
!zip -r results.zip results
from google.colab import files
files.download('results.zip')
```

---

## 7) 可选：挂载 Google Drive 持久化

Colab 会话断开后本地文件会丢失，建议挂载 Drive：

```python
from google.colab import drive
drive.mount('/content/drive')
```

把结果复制到 Drive：

```python
!mkdir -p "/content/drive/MyDrive/spss_results"
!cp -r results "/content/drive/MyDrive/spss_results/"
```

---

## 8) 常见问题

### Q1. 报错：找不到 Excel 文件
检查文件是否上传成功：
```python
!ls -lah
```
并确认 `--excel` 路径与文件名完全一致。

### Q2. 报错：`No module named ...`
重新安装依赖：
```python
!pip -q install -r requirements.txt
```

### Q3. QC 没通过怎么办？
先看：
- `results/long/qc_issues.csv`（具体哪个被试、哪项失败）
- `results/long/missing_rate.csv`（缺失率）

### Q4. 如何给同学复现？
把本文件 + Notebook 链接发给同学，让其只改 `--excel` 文件名即可。

