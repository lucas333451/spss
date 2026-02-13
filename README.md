# spss (Python Replacement for Questionnaire Analysis)

用 Python + 开源库替代 SPSS，面向你这套 VR+EEG 问卷数据（N=32, 3×2 场景, 两轮重复）。

## Features
- Excel 问卷自动读取与字段映射
- 质控筛选（核查题）
- 量表得分与信度（Cronbach's alpha）
- 线性混合效应模型（LMM，替代 SPSS 重复测量）
- 自动导出结果表、模型摘要、交互图、Markdown 报告

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1) 先检查列名：
```bash
python scripts/inspect_excel.py "/home/wannaqueen66/VR+EEG实验问卷-原始数据-2026-02-04.xlsx"
```

2) 复制配置并修改列名：
```bash
cp config/config.example.yaml config/config.yaml
# edit config/config.yaml
```

3) 运行主分析：
```bash
python scripts/run_analysis.py --config config/config.yaml --out results/run1
```

## Output
`results/run1/` 下会生成：
- `data_scored.csv`
- `descriptives.csv`
- `cleaning_log.csv` / `cleaning_log.json`
- `lmm_summary.txt`
- `figures/wwr_complexity_interaction.png`
- `report.md`

## Notes
- 当前模型默认：
  `affordance_score ~ WWR * complexity * frequency + round + (1|subject)`
- 如果字段名不同，改 `config/config.yaml` 即可。

