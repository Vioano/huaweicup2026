# K5 静态差距优先级

数据来自固定提交 `5c5789bc7985ee98086160f75770da0018f4898b` 的 [`results/a/q1-yuanzhifang/pro-r4-bound-pairing-20260925/local-audit-20260925T082007Z/paired-500.csv`](https://github.com/huaweibei123/huaweicup2026/blob/5c5789bc7985ee98086160f75770da0018f4898b/results/a/q1-yuanzhifang/pro-r4-bound-pairing-20260925/local-audit-20260925T082007Z/paired-500.csv)。只读取 `cores=5` 的 100 行，先核对 `current_speedup` 均值为 **4.025907473836023**，与给定统一基线一致。

每图上包络按 `B / L` 计算，差距为 `B/L - current_speedup`。上包络均值 **6.068017**，平均差距 **2.042110**。差距最大的 15 图占全体差距和的 **36.38%**。Top 15 排序位于 `priority.json` 的 `top15_by_gap`；完整 100 图排序位于 `all_cases_by_gap`。按 `selected` 汇总也在该 JSON 中。

要使 100 图均值相对提高 5%，目标均值为 **4.227202847527824**，须增加 **0.201295373691801**；按 100 图均值口径，等价于所有格子的绝对加速比增量合计 **20.1295373691801**。

建议先诊断 shared-input 的 case 044、heavy-or-sink 标签组，以及 bounded 组中差距较大的代表图。标签可能是回退或选择结果，不能当作结构族证明。`B/L` 大差距也不是可回收收益预测；本分析仅用于挑选机制诊断，不运行新图、不增加成绩或实验结论。
