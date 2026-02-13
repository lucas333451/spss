# spss

用于将问卷系统导出的宽表 Excel 转为可直接用于 LMM 的 long-format，并完成基础模型分析。

## 1) 宽表转长表（核心）
```bash
python scripts/transform_wide_to_long.py \
  --excel "/home/wannaqueen66/VR+EEG实验问卷-原始数据-2026-02-04.xlsx" \
  --out-dir results/long
```

### 已硬编码映射
`mapping[Order][Block][Position] = (WWR, Condition)`，完全按项目规范：
- Order=1/2
- Block1(Q2~Q7), Block2(Q9~Q14)
- Position1~6
- WWR∈{15,45,75}, Condition∈{C0,C1}

并派生：
- `Complexity`（C1=1, C0=0）
- `SceneID`（例如 `WWR45_C1`）

### B题写入规则（做法A）
- Block1 使用 Q8.1~Q8.3
- Block2 使用 Q15.1~Q15.3
- 仅 C1 行写入 B1~B3，C0 行强制 NA

### long-format 输出字段
`SubjectID, Order, Block, Position, WWR, Condition, Complexity, SportFreq, S1~S5, Afford4, Afford5, Pleasure, B1~B3, Bmean, SceneID`

## 2) 自动 QC
转长表时自动输出：
- `qc_issues.csv`
- `missing_rate.csv`
- `qc_summary.json`

校验项：
- 每被试 12 行
- 每 Block 6 行
- 每 Block 内 C1/C0 各 3 行
- 每 Block 内 WWR: 15×2, 45×2, 75×2
- B1~B3 仅 C1 非空

## 3) LMM 分析
```bash
python scripts/run_analysis.py \
  --long-csv results/long/long_format.csv \
  --out-dir results/model
```

默认模型：
`Afford5 ~ C(WWR) * C(Complexity) * C(SportFreq) + C(Block) + C(Position) + (1|SubjectID)`



## 4) 论文结果表一键导出
`run_analysis.py` 会额外导出：
- `table_descriptives.csv`
- `table_fixed_effects.csv`
- `table_main_interactions.csv`
- `paper_tables.md`（可直接粘贴文稿的 Markdown 表格）
