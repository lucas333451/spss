# 项目总览（给第一次接触本项目的人）

## 这个项目解决什么问题？
把问卷系统导出的 **Excel 宽表**（每个被试一行）转换为可建模的 **long-format**，并完成：
1. 质量检查（QC）
2. 线性混合模型（LMM）
3. 论文可贴表格与图

## 数据流
1. 原始 Excel（宽表）
2. `transform_wide_to_long.py` → `long_format.csv`
3. `run_analysis.py` → 基础论文结果表
4. `analyze_research_questions.py` → 针对研究问题（角度1+角度2）的扩展分析

## 你最常用的两个命令
- 先转长表：`transform_wide_to_long.py`
- 再出论文表：`run_analysis.py`

## 什么时候用扩展脚本？
当你要报告“重复两遍是否收敛”“高频组是否更稳定”时，使用 `analyze_research_questions.py`。
