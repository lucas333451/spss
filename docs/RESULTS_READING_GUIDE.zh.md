# 结果阅读指南（中文主入口）

这份文件是给老师、合作者、第一次接触本项目的人看的：
**如果你已经拿到了 `results/` 文件夹，但不知道先看什么，就从这里开始。**

---

## 一句话先说清
当前 `main` 分支的结果只强调两条主线：

1. **描述性分析（descriptive）**
2. **显著性分析（significance）**

并且默认只突出两个入口：
- `overall`
- `experience`

如果你看到更旧的 `results/model/*`、`results/research/*`、analysis-2/task1~task5 这类路径，
那不是当前 `main` 的默认主阅读面，而是旧版 / 历史结构，应该去 `raw` 分支看。

---

## 一、拿到结果后，最推荐的阅读顺序

### 第一步：先看总导航
1. `results/RESULTS_GUIDE.md`
2. `results/RESULTS_GUIDE.png`

作用：
- 先建立“整个结果文件夹怎么走”的地图感
- 避免一上来埋进很多 csv 看不清主线

---

### 第二步：看描述性结果（先看图，再看表）

#### 2.1 看全样本 overall
先看：
- `results/descriptive/qc/overall/png/`

再看：
- `results/descriptive/qc/overall/csv/s1_s5_descriptives.csv`
- `results/descriptive/qc/overall/csv/b1_b3_descriptives.csv`
- `results/descriptive/qc/overall/csv/ipq_descriptives.csv`

你会得到：
- 整体分布长什么样
- 哪些指标均值高/低
- 离散程度如何
- 数据是否大致对称、是否偏态明显

#### 2.2 看 Experience 分组
先看：
- `results/descriptive/qc/experience/png/`

再看：
- `results/descriptive/qc/experience/csv/s1_s5_descriptives_by_experience.csv`
- `results/descriptive/qc/experience/csv/b1_b3_descriptives_by_experience.csv`
- `results/descriptive/qc/experience/csv/ipq_descriptives_by_experience.csv`

你会得到：
- Experience 高低组在描述性层面的直观差异
- 哪些变量可能值得后面重点看显著性分析

---

### 第三步：看显著性主结果

#### 3.1 先看 overall 核心模型
最优先：
- `results/significance/qc/overall/core_model/md/results_draft_zh.md`

然后：
- `results/significance/qc/overall/core_model/csv/table_main_interactions.csv`
- `results/significance/qc/overall/core_model/csv/table_fixed_effects.csv`
- `results/significance/qc/overall/core_model/png/`

这部分回答的是：
- overall 层面有没有关键主效应 / 交互效应
- 哪些结果值得写进正文

#### 3.2 再看 WWR 趋势显著性
优先看：
- `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`

再看：
- `results/significance/qc/overall/wwr_polynomial/png/`
- `results/significance/qc/overall/wwr_polynomial/md/`

这部分重点看：
- 是否显著
- 是线性增加还是线性减少
- WWR=45 是否最高或最低

---

### 第四步：看 Experience 组间显著性

#### 4.1 Experience group only
优先看：
- `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`

再看：
- `results/significance/qc/experience/wwr_polynomial_group_only/png/`
- `results/significance/qc/experience/wwr_polynomial_group_only/md/`

#### 4.2 Experience × Round follow-up
优先看：
- `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`

再看：
- `results/significance/qc/experience/wwr_polynomial_group_round/png/`
- `results/significance/qc/experience/wwr_polynomial_group_round/md/`

这两块一起回答：
- Experience 高低组显著性模式是否不同
- 这种差异是否会随 round 改变

---

### 第五步：如果你要逐题看
看这里：
- `results/significance/qc/item_level/s_items/`
- `results/significance/qc/item_level/b_items/`
- `results/significance/qc/item_level/ipq_items/`

优先看：
- `README.md`
- `csv/s_items_primary_main_interactions.csv`
- `csv/b_items_primary_main_interactions.csv`
- `csv/ipq_items_primary_main_interactions.csv`

作用：
- 判断具体题目层面哪些效应在显著性上更关键
- 让 S1–S5、B1–B3、IPQ1–IPQ6 与 Afford4 core branch 处于同一建模层级来阅读

---

## 二、如果我要写汇报 / 给导师发结果，最短路线是什么？
直接按这个顺序：

1. `results/RESULTS_GUIDE.md`
2. `results/descriptive/qc/overall/png/`
3. `results/descriptive/qc/experience/png/`
4. `results/significance/qc/overall/core_model/md/results_draft_zh.md`
5. `results/significance/qc/overall/wwr_polynomial/csv/wwr_polynomial_contrasts.csv`
6. `results/significance/qc/experience/wwr_polynomial_group_only/csv/wwr_polynomial_contrasts.csv`
7. `results/significance/qc/experience/wwr_polynomial_group_round/csv/wwr_polynomial_contrasts.csv`

这个顺序够覆盖：
- 结果长什么样
- 整体显著不显著
- Experience 分组有没有差异
- WWR 趋势是什么方向

---

## 三、raw 和 qc 到底怎么选？

### 正式使用
优先看：
- `qc`

### 内部核对 / 稳健性比较
再补看：
- `raw`

简单记：
- `qc` = 正式口径
- `raw` = 对照口径

---

## 四、png 和 csv 怎么分工？

### 先看 png
因为它能让你先知道：
- 差异大不大
- 方向对不对
- 有没有一眼看上去就奇怪的结果

### 再看 csv
因为它负责：
- 确认精确数值
- 引用结果到论文或汇报
- 做进一步整理

简单记：
- **png 先看模式**
- **csv 再核对数值**

---

## 五、什么时候才需要看旧版 research / model / analysis-2？
只有在你明确需要下面这些时，才回到旧版逻辑：
- 更 exploratory 的历史输出
- analysis-2 / task1~task5
- 旧的 `results/research/*`
- 旧的 `results/model/*`

这时不要继续拿当前 `main` 的阅读顺序硬套，
而应该切到：
- `raw` 分支

---

## 六、最简总结
如果时间很少，只记住这 4 句话：

1. 先看 `results/RESULTS_GUIDE.md`
2. 先看 `descriptive/qc/.../png/`，再看 csv
3. 先看 `significance/qc/overall/core_model/`，再看 `wwr_polynomial/`
4. 正式汇报优先 `qc`，旧版 exploratory 内容去 `raw` 分支
