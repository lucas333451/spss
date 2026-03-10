# RESULTS_MAP.md

一页速查：当前 `main` 分支下，每类研究问题优先看哪些文件。

> 说明：
> - 当前 `main` 只强调两条主线：`overall` 与 `experience`
> - 正式汇报优先看 `qc`
> - 如果没跑 `--with-qc`，就把下面路径里的 `qc/` 改看 `raw/`

---

## 0. 总入口：先看哪里？
1. `results/RESULTS_GUIDE.md`
2. `results/RESULTS_GUIDE.png`
3. `results/significance/significance_index.md`
4. `results/significance/research_questions_map.md`
5. `results/significance/significance_guide.png`

---

## Q1. 全样本（overall）的描述性结果先看哪里？
1. `results/descriptive/qc/overall/png/`
2. `results/descriptive/qc/overall/csv/s1_s5_descriptives.csv`
3. `results/descriptive/qc/overall/csv/b1_b3_descriptives.csv`
4. `results/descriptive/qc/overall/csv/ipq_descriptives.csv`

---

## Q2. Experience 高低组的描述性差异先看哪里？
1. `results/descriptive/qc/experience/png/`
2. `results/descriptive/qc/experience/csv/s1_s5_descriptives_by_experience.csv`
3. `results/descriptive/qc/experience/csv/b1_b3_descriptives_by_experience.csv`
4. `results/descriptive/qc/experience/csv/ipq_descriptives_by_experience.csv`

---

## Q3. 全样本（overall）的核心显著性结果先看哪里？
1. `results/significance/qc/overall/core_model/md/results_draft_zh.md`
2. `results/significance/qc/overall/core_model/csv/table_main_interactions.csv`
3. `results/significance/qc/overall/core_model/csv/table_fixed_effects.csv`
4. `results/significance/qc/overall/core_model/png/`

---

## Q4. WWR 在线性 / 二次趋势上是否显著？
1. `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`
2. `results/significance/qc/overall/wwr_polynomial/png/`
3. `results/significance/qc/overall/wwr_polynomial/md/`

重点看：
- 是否显著
- 方向是 increase / decrease
- WWR=45 是否最高或最低

---

## Q5. Experience 高低组在显著性模式上是否不同？
1. `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`
2. `results/significance/qc/experience/wwr_polynomial_group_only/png/`
3. `results/significance/qc/experience/wwr_polynomial_group_only/md/`

---

## Q6. Experience 效应是否随 round 变化？
1. `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`
2. `results/significance/qc/experience/wwr_polynomial_group_round/png/`
3. `results/significance/qc/experience/wwr_polynomial_group_round/md/`

---

## Q7. S / B / IPQ 的逐题组间显著性看哪里？
1. `results/significance/qc/item_level/experience/s_items/csv/s_items_experience_welch.csv`
2. `results/significance/qc/item_level/experience/b_items/csv/b_items_experience_welch.csv`
3. `results/significance/qc/item_level/experience/ipq_items/csv/ipq_items_experience_welch.csv`
4. `results/significance/qc/item_level/experience/` 下对应 png / md / json

---

## Q8. 如果我要正式汇报，文件优先顺序是什么？
1. `results/RESULTS_GUIDE.md`
2. `results/descriptive/qc/overall/png/`
3. `results/descriptive/qc/experience/png/`
4. `results/significance/qc/overall/core_model/md/results_draft_zh.md`
5. `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`
6. `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`
7. `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`

---

## Q9. raw 和 qc 应该怎么选？
- 对外汇报 / 正式写作：优先 `qc`
- 内部核对 / 稳健性对照：再看 `raw`

一句话规则：
- `png` 先看模式
- `csv` 再核对数值
- `qc` 先用
- `raw` 后比对

---

## Q10. 如果我要旧版 research / analysis-2 那条线怎么办？
当前这个 `RESULTS_MAP.md` 只服务于 **clean main 主线**。

如果你明确要：
- 旧版 `results/research/*`
- 旧版 `results/model/*`
- analysis-2 / task1~task5
- 更 exploratory 的历史输出

请切到：
- `raw` 分支

不要把旧版 research 路径和当前 main 默认结果入口混在一起读。
