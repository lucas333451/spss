# Colab 超详细上手指南（零基础版）

> 目标：你不用配置本地 Python，直接在 Google Colab 跑完整项目。  
> 结果：得到 `results/` 文件夹（包含 long 数据、QC、LMM 表格、图）。

---

## 目录
- [0. 你将得到什么](#0-你将得到什么)
- [1. 打开 Colab](#1-打开-colab)
- [2. 新建 Notebook](#2-新建-notebook)
- [3. 复制并运行代码块（按顺序）](#3-复制并运行代码块按顺序)
- [4. 如何判断“运行成功”](#4-如何判断运行成功)
- [5. 下载结果到本地](#5-下载结果到本地)
- [6. 保存到 Google Drive（防止会话断开丢失）](#6-保存到-google-drive防止会话断开丢失)
- [7. 常见报错与解决](#7-常见报错与解决)
- [8. 给同学复现的最简说明](#8-给同学复现的最简说明)

---

## 0. 你将得到什么
运行完成后会生成：
- `results/long/long_format.csv`（宽转长后的主数据）
- `results/long/qc_issues.csv`（质控失败明细）
- `results/model/paper_tables.md`（论文可贴表）
- `results/research/table_main_interactions_all_dv.csv`（主效应/交互汇总）
- 多张图（交互图、热力图、Round 差值图）

---

## 1. 打开 Colab
1. 浏览器进入：<https://colab.research.google.com>
2. 使用你的 Google 账号登录

---

## 2. 新建 Notebook
1. 点击右下角或左上角 **New Notebook / 新建笔记本**
2. 打开后，你会看到一个代码单元（cell）

> 提示：Colab 每个代码块都要点左侧“播放按钮（▶）”执行。

---

## 3. 复制并运行代码块（按顺序）

## 3.1 环境准备：克隆仓库 + 安装依赖
把下面整段粘贴到第一个 cell，执行：

```python
!git clone https://github.com/wannaqueen66-create/spss.git
%cd spss
!pip -q install --upgrade pip
!pip -q install -r requirements.txt
print("✅ 环境准备完成")
```

执行时间：约 1~3 分钟。

---

## 3.2 上传 Excel 文件
新建第二个 cell，执行：

```python
from google.colab import files
uploaded = files.upload()  # 点按钮选择你的Excel
print("已上传文件：", list(uploaded.keys()))
```

执行后会弹出文件选择框，选你的 Excel（例如：`VR+EEG实验问卷-原始数据-2026-02-04.xlsx`）。

---

## 3.3 指定文件名（只改这一行）
新建第三个 cell，执行：

```python
EXCEL_FILE = "VR+EEG实验问卷-原始数据-2026-02-04.xlsx"  # 改成你实际上传后的文件名

import os
assert os.path.exists(EXCEL_FILE), f"❌ 找不到文件: {EXCEL_FILE}"
print("✅ 当前使用文件:", EXCEL_FILE)
```

如果断言报错，说明文件名不一致（常见于多空格或括号差异）。

---

## 3.4 一键跑完整流程
新建第四个 cell，执行：

```python
!python scripts/pipeline.py --excel "$EXCEL_FILE" --out-root results
```

这一步会自动做三件事：
1. 宽表 -> long + QC
2. 基础论文表导出
3. 扩展研究问题分析（角度1+角度2）

---

## 3.5 列出结果文件（确认产物）
新建第五个 cell，执行：

```python
!find results -maxdepth 3 -type f | sort
```

如果你看到 `results/long/`、`results/model/`、`results/research/` 下多文件，说明流程成功。

---

## 4. 如何判断“运行成功”
至少满足以下 3 条：
1. `results/long/long_format.csv` 存在
2. `results/model/paper_tables.md` 存在
3. `results/research/table_main_interactions_all_dv.csv` 存在

可用下面命令快速检查：

```python
!test -f results/long/long_format.csv && echo "✅ long_format.csv ok"
!test -f results/model/paper_tables.md && echo "✅ paper_tables.md ok"
!test -f results/research/table_main_interactions_all_dv.csv && echo "✅ interactions table ok"
```

---

## 5. 下载结果到本地

## 5.1 下载单个文件
```python
from google.colab import files
files.download('results/model/paper_tables.md')
```

## 5.2 打包下载全部结果（推荐）
```python
!zip -r results.zip results > /dev/null
from google.colab import files
files.download('results.zip')
```

---

## 6. 保存到 Google Drive（防止会话断开丢失）

```python
from google.colab import drive
drive.mount('/content/drive')

!mkdir -p "/content/drive/MyDrive/spss_results"
!cp -r results "/content/drive/MyDrive/spss_results/"
print("✅ 已保存到 Drive: MyDrive/spss_results")
```

> 注意：Colab 会话断开后，`/content` 下文件可能丢失；重要结果务必下载或复制到 Drive。

---

## 7. 常见报错与解决

## 报错 A：`File not found` / `找不到 Excel`
原因：`EXCEL_FILE` 与实际上传文件名不一致。  
处理：先运行
```python
import os
print(os.listdir('.'))
```
复制真实文件名替换 `EXCEL_FILE`。

## 报错 B：`No module named xxx`
原因：依赖没装完整。  
处理：重新执行安装单元：
```python
!pip -q install -r requirements.txt
```

## 报错 C：QC 失败
处理顺序：
1. 看 `results/long/qc_issues.csv`（具体哪位被试、哪条规则）
2. 看 `results/long/missing_rate.csv`（是否缺失过高）
3. 确认原始问卷导出是否有漏填或手工改列名

## 报错 D：运行很慢或中断
处理：
- 菜单 `Runtime -> Change runtime type` 选择更稳定环境（CPU 即可）
- 断开后重连再执行（建议直接用 `notebooks/spss_colab.ipynb`）

---

## 8. 给同学复现的最简说明
把这三句发给同学就够：
1. 打开 `notebooks/spss_colab.ipynb`
2. 逐格运行，只改 `EXCEL_FILE`
3. 跑完下载 `results.zip`

