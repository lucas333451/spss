# spss

Python 开源流程替代 SPSS（面向 VR+EEG 问卷）。

## 当前已适配你的列结构
- 人口学与背景：`姓名`, `Q1.5_近 6 个月平均运动频率：`, `Q1.8_场景顺序编号`
- 场景题块：`Q2~Q7` + `Q9~Q14`（每块 `S1~S5`）
- 自动识别列名模式：`Qx.y_Sy.` 开头

## 安装
```bash
pip install -r requirements.txt
```

## 运行
```bash
cp config/config.example.yaml config/config.yaml
python scripts/run_analysis.py --config config/config.yaml --out results/run1
```

## 输出
- `long_data.csv`（宽表转长表）
- `reliability.csv`（S1~S5 信度 alpha）
- `descriptives_by_scene.csv`
- `lmm_summary.txt`
- `figures/interaction.png`
- `report.json`

## 关键说明
现在脚本已经可跑，但 **WWR×信息复杂度** 需要你补 `scene_condition_map`（scene_index 1~6 到条件标签映射）。
补完后模型会自动切换为：

`affordance_score ~ C(wwr) * C(complexity) * C(frequency) + C(round) + (1|subject)`

未补映射时，会先用 `scene_index` 做占位分析。
