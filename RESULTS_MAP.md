# RESULTS_MAP.md

一页速查：每个研究问题先看哪 3 个文件（按优先级）。

---

## Q1. WWR×复杂度是否影响 S1-S4（感知可供性主构念）？（角度1主问题）
1. `results/research/table_angle1_main_interactions_all_dv.csv`
2. `results/research/group_complexity_mean_table.csv`
3. `results/research/analysis_narrative.md`

---

## Q2. 高复杂度 C1 是否普遍更低？不同人群降幅是否不同？
1. `results/research/angle1_c1_minus_c0_by_group.csv`
2. `results/research/group_complexity_delta_significance.csv`
3. `results/research/figures/group_complexity_delta_S*.png`

---

## Q3. 在不同 WWR 下，上述复杂度差异是否变化？
1. `results/research/group_complexity_mean_table_by_wwr.csv`
2. `results/research/group_complexity_delta_significance_by_wwr.csv`
3. `results/research/figures/interaction_S*_by_sportfreqgroup.png`

---

## Q4. 两遍观看（Round1/2）是否出现收敛/学习？
1. `results/research/table_angle2_round_interactions_all_dv.csv`
2. `results/research/angle2_round_diff_by_group.csv`
3. `results/research/round_icc_by_group.csv`

---

## Q5. 顺序（组1/组2）是否改变复杂度差值？
1. `results/research/group_complexity_delta_by_round.csv`
2. `results/research/group_complexity_delta_round_shift.csv`
3. `results/research/round_consistency_by_group.csv`

---

## Q6. 四类交叉人群（Experience×SportFreq）具体差异是什么？
1. `results/research/group_comparisons_item_level.csv`
2. `results/research/groups/manifest.csv`
3. `results/research/groups/group_*.csv`

---

## Q7. 只按 SportFreq 二分（高/低）看差异
1. `results/research/group2_comparisons_item_level_sportfreqgroup.csv`
2. `results/research/group2_complexity_mean_table_sportfreqgroup.csv`
3. `results/research/group2_complexity_delta_significance_sportfreqgroup.csv`

---

## Q8. 只按 Experience 二分（高/低）看差异
1. `results/research/group2_comparisons_item_level_experiencegroup.csv`
2. `results/research/group2_complexity_mean_table_experiencegroup.csv`
3. `results/research/group2_complexity_delta_significance_experiencegroup.csv`

---

## Q9. B题（B1-B3 / Bmean）在 C1 下的人群差异（操纵检验/补充）
1. `results/research/b_items_group_comparisons.csv`
2. `results/research/b_items_condition_means.csv`
3. `results/research/b_items_long_c1.csv`

---

## Q10. 诊断与稳健性：结果是否受模型设定影响？
1. `results/diagnostics/analysis_report.md`
2. `results/diagnostics/model_comparison_interactions.csv`
3. `results/diagnostics/main_effect_stability_by_random_structure.csv`

---

## Q11. Analysis-2/task1：同一场景两阶段（Round1/2）评分差距（S1–S5）在人群间是否不同？
1. `results/research/task1_stage_gap/analysis2_scene_stage_gap_long.csv`
2. `results/research/task1_stage_gap/analysis2_scene_stage_gap_wide_<SceneID>.csv`
3. `results/research/task1_stage_gap/analysis2_scene_stage_gap_figures/scene_<SceneID>.png`

## Q12. Analysis-2/task1b：B1–B3（C1-only）两阶段（Round1/2）评分差距在人群间是否不同？
1. `results/research/task1_stage_gap/analysis2_b_stage_gap_long.csv`
2. `results/research/task1_stage_gap/analysis2_b_stage_gap_figures/B1.png`
3. `results/research/task1_stage_gap/analysis2_b_stage_gap_figures/B2.png`
4. `results/research/task1_stage_gap/analysis2_b_stage_gap_figures/B3.png`

## Q13. Analysis-2/task3 core_lmm_suite：围绕 WWR（及 Complexity、Group）的问卷评分核心 LMM 主效应/交互结果
1. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_s_models.csv`
2. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_s_effects.csv`
3. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_b_models.csv`
4. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_b_effects.csv`
5. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_figures/task3_s_model_aic.png`
6. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_figures/task3_s_top_effects_forest.png`
7. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_figures/task3_b_model_aic.png`
8. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_figures/task3_b_top_effects_forest.png`
9. `results/research/task3_core_lmm_suite/analysis2_core_imm_suite_figures/task3_b_means_B1.png`（B2/B3 同路径）

---

## 最快交付（给导师/合作者）
- 首选：`results/analysis_report_bundle.md`
- 再补：`results/research/analysis_narrative.md`
- 如需图：`results/research/figures/`
