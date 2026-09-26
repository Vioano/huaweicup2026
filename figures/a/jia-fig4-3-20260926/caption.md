# 图 4-3｜输入错峰前后的多核执行时间线（case051 / 3 核）

**图意**：比较同一算例 case051 在 3 核下 control（基线）与 paced（输入错峰）两种调度方案的
端到端执行时间线。上排 a = control，下排 b = paced；每排左图为全量绝对时间轴
（0 → makespan，单位 cycles），右图为首轮（0–12,000 cycles）放大。行序自上而下：
核1 / 核2 / 核3 × PIPE_MTE2（搬入）/ PIPE_MTE3（搬出）/ PIPE_V（计算与归约）；
灰色底条为 task（Subgraph）区间，彩色条为真实流水操作。

**样本与比较条件**：单一算例配对（case051 / 3 核），两方案链-核映射一致
（k3_same_chain_to_core_mapping=True），数据取自 stage-j 固定批次
（固定提交 059056ce1ee999e634049e5e5baf72566832effe）。
该批次为诊断单元（PREPARED.md 明示），**不是 P1 全量平均成绩**；
两方案的 solver/E0 墙钟时间（0.546→0.618 s / 1.223→1.290 s）见来源 comparison.csv，图内未展示。

**关键读数**（与 events.csv / results.csv / markers.csv 一致）：

- makespan（最晚事件结束，cycles）：control 291,222 → paced 278,618（Δ = −12,604，−4.33%）。
- 额外 DDR（extra_ddr，B）：9,045,304 → 9,045,350（+46 B）；两者 spill 均为 0。
- 首轮完全一致：大输入完成 6,570、首轮 Task 完成 10,028、远端部分结果返回 11,040 cycles——
  即输入错峰不改变首轮，改进自 task 4 起的后续阶段（paced 将大计算段拆为
  2,647 + 7,935 cycles 的交替短段，control 为 8,933 cycles 连续长段）。
- 归约尾（末条 task 收全量部分结果做最终归约）起点：control 291,076 / paced 278,472 cycles。

**局限**：

1. 单例配对，局部提前（首轮之后任务段变短）**不能**外推为所有指标改善；
   makespan 改善 4.33% 伴随额外 DDR 增加 46 B。
2. 远端返回标记定义为首轮跨核收集 task（task 3，12 条 COPY_IN）的最后一搬入完成时刻，
   是事件表可复核的派生量，非官方指标名。
3. 短操作（1–6 cycles 的小搬入/搬出）在全量轴上低于 1 px，仅在首轮放大图中部分可辨；
   完整起止见 events.csv（control 2,469 行 / paced 2,515 行，含全部 task 区间与 pipe 操作）。
4. 图例中标记线数值（6570 / 10028 / 11040）为两方案共享值。
