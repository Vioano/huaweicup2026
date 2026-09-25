# 044/K5：固定归属的优先序消融准备

运行 `python3 -B scripts/q2_stationary_order_ablation.py` 生成两份完整单例方案：`job-major-plan.json` 是已有共享输入驻留＋作业优先方案；`stage-major-same-owner-plan.json` 保持**完全相同的每个操作归核与子图映射**，仅把每核优先词改成阶段优先。两个计划均通过官方结构推导；[`summary.json`](summary.json) 留存原图、配置、计划 SHA-256，以及 `zero_spill_intervals.certify` 的有条件零 spill 证书。新生成的 job-major 计划与[先前已官方评分的 ZIP](../shared-stationary-pipeline-044-pilot-20260926/run/colab-results.zip)中 `output/plan.json` 解析后逐项相同，规范化 JSON SHA-256 同为 `2496af22ab6966f73900f48bbca6646c7c2dd060338386381c913e39db1c2ca8`。本次运行未调用 E0/E1/E2，因而没有新工期或 DDR 成绩。

之前 72,955 周期的 `shared_stationary_wave` 同时采用不同的阶段划分归属和阶段优先顺序；它不能单独证明“阶段优先”造成退化。这个同归属消融提供可评分的唯一变量对照，但必须在共享资源正式准入后用官方 E0 独立验证；零 spill 证书与静态字节不能替代工期。
