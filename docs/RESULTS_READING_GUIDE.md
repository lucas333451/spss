# Results Reading Guide (main clean branch)

This file is the quickest reading entry for teachers, collaborators, or anyone who has received the `results/` folder but does not yet know where to start.

---

## One-sentence summary
The current `main` branch only emphasizes two visible result families:

1. **Descriptive analysis**
2. **Significance analysis**

And it only promotes two default entry branches:
- `overall`
- `experience`

If you encounter older paths such as `results/model/*`, `results/research/*`, or analysis-2/task1~task5, those are not the default reading surface of the current clean `main`. They belong to older / historical logic and should be checked in the `raw` branch instead.

---

## Recommended reading order

### Step 1 — Start with the global guide
1. `results/RESULTS_GUIDE.md`
2. `results/RESULTS_GUIDE.png`

Why:
- They give you the map of the whole result tree first.
- They prevent you from diving into CSV files too early without a clear storyline.

---

### Step 2 — Read descriptive results first

#### 2.1 Overall descriptive picture
Start with:
- `results/descriptive/qc/overall/png/`

Then confirm with:
- `results/descriptive/qc/overall/csv/s1_s5_descriptives.csv`
- `results/descriptive/qc/overall/csv/b1_b3_descriptives.csv`
- `results/descriptive/qc/overall/csv/ipq_descriptives.csv`

What this gives you:
- the overall distribution pattern
- which measures are higher / lower on average
- how dispersed the data are
- whether strong skewness or asymmetry is already visible

#### 2.2 Experience-group descriptive picture
Start with:
- `results/descriptive/qc/experience/png/`

Then confirm with:
- `results/descriptive/qc/experience/csv/s1_s5_descriptives_by_experience.csv`
- `results/descriptive/qc/experience/csv/b1_b3_descriptives_by_experience.csv`
- `results/descriptive/qc/experience/csv/ipq_descriptives_by_experience.csv`

What this gives you:
- the intuitive descriptive gap between high vs low Experience groups
- a first clue about which variables deserve closer inferential attention

---

### Step 3 — Read the main significance results

#### 3.1 Overall core model first
Highest priority:
- `results/significance/qc/overall/core_model/md/results_draft_zh.md`

Then:
- `results/significance/qc/overall/core_model/csv/table_main_interactions.csv`
- `results/significance/qc/overall/core_model/csv/table_fixed_effects.csv`
- `results/significance/qc/overall/core_model/png/`

This answers:
- whether the overall sample shows the main effects / interactions of interest
- which results are important enough to write into the main text

#### 3.2 Then inspect WWR trend significance
Start with:
- `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`

Then:
- `results/significance/qc/overall/wwr_polynomial/png/`
- `results/significance/qc/overall/wwr_polynomial/md/`

Focus on:
- whether the trend is significant
- whether it is linear increase or decrease
- whether WWR=45 is the highest or lowest point

---

### Step 4 — Read experience-group significance

#### 4.1 Experience group only
Start with:
- `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`

Then:
- `results/significance/qc/experience/wwr_polynomial_group_only/png/`
- `results/significance/qc/experience/wwr_polynomial_group_only/md/`

#### 4.2 Experience × Round follow-up
Start with:
- `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`

Then:
- `results/significance/qc/experience/wwr_polynomial_group_round/png/`
- `results/significance/qc/experience/wwr_polynomial_group_round/md/`

Together, these answer:
- whether high vs low Experience groups differ in significance pattern
- whether that difference changes across rounds

---

### Step 5 — If you need item-level detail
Go to:
- `results/significance/qc/item_level/s_items/`
- `results/significance/qc/item_level/b_items/`
- `results/significance/qc/item_level/ipq_items/`

Start with:
- `README.md`
- `csv/s_items_primary_main_interactions.csv`
- `csv/b_items_primary_main_interactions.csv`
- `csv/ipq_items_primary_main_interactions.csv`

Use this when:
- you need to identify which individual items drive the significance pattern
- you want S1–S5, B1–B3, and IPQ1–IPQ6 at the same modeling level as the Afford4 core branch

---

## Shortest route for formal reporting
If you need the shortest practical route for a report or supervisor update, read in this order:

1. `results/RESULTS_GUIDE.md`
2. `results/descriptive/qc/overall/png/`
3. `results/descriptive/qc/experience/png/`
4. `results/significance/qc/overall/core_model/md/results_draft_zh.md`
5. `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`
6. `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`
7. `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`

This is enough to cover:
- what the data look like
- whether the overall effects are significant
- whether Experience groups differ
- what direction the WWR trend takes

---

## How to choose between raw and qc

### For formal reporting
Prefer:
- `qc`

### For internal checking / robustness comparison
Then compare with:
- `raw`

Simple rule:
- `qc` = formal interpretation first
- `raw` = comparison / robustness layer

---

## How to split the job between PNG and CSV

### Read PNG first
Because PNG helps you quickly judge:
- whether the difference is visually large or small
- whether the direction matches expectation
- whether anything looks obviously strange

### Read CSV second
Because CSV is where you confirm:
- exact numbers
- values to cite in a report or manuscript
- tables for further downstream use

Simple rule:
- **PNG first for pattern**
- **CSV second for exact numbers**

---

## When should you go back to legacy outputs?
Only go back to older logic if you explicitly need:
- historical exploratory outputs
- analysis-2 / task1~task5
- old `results/research/*`
- old `results/model/*`

If so, do not force the current clean `main` reading order onto those outputs.
Switch to:
- `raw` branch

---

## Minimal summary
If you only remember four things, remember these:

1. Start with `results/RESULTS_GUIDE.md`
2. Read `descriptive/qc/.../png/` before CSV
3. Read `significance/qc/overall/core_model/` before `wwr_polynomial/`
4. Use `qc` first for formal reporting; use `raw` only as a comparison layer
