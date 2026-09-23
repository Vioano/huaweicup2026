# 未完成、探索性与不纳入主性能表的运行

本文件保留失败边界，不把超时当方案非法，也不把部分重复包装成完整基准。

- `results/initial/`：首批功能和热点探索。001、003 有完整三问输出；025 的首次批处理未形成完整成组测量。这些结果不作为主表的重复样本。
- `results/initial/025_q1_E0_bounded.run.json`：带 cProfile 的 E0 探测达到预设 25 秒上限，状态为 `TimeoutError: research time cap`。部分 pstats 仅能诊断热点，不能作为完整耗时。
- `results/initial/025_q1_R2_bounded.*`：S 的带 profiler 探测完成。不得拿其 profiler 时间除以另外运行的无 profiler E0 时间。
- `results/initial/025_q1_E0_untimedprofile.run.json`：另一次无 profiler E0 完成；它是独立功能/耗时观察，不替代配对基准。
- `results/benchmark/025_q1_components/summary.json`：原计划 warmup 后做三次配对，当前只有 warmup，`runs` 为空。排除于主性能表。替代的是新身份 `025_isolated/rep0..2.json`，每对独立进程、无 warmup，已明确采用不同协议。
- `results/benchmark/003_q3_intervals/summary.json`：原计划三对，仅完成一对后工具调用预算用尽。保留该对真实结果，不报告三次中位数。
- `results/grid/`：有若干子批首次因容器调用时限中断；随后按落盘行恢复。最终十二池共80行全部完成，逐行结果独立保存。未将中断区间拼接成速度基准，表内时间只是单次诊断。
- `results/word_initial/`：早期词签名原型运行，随后将每核 rank 字典移到锚点循环外。当前版本重新运行的80对在 `results/word/`。两轮不相加成160个独立测试。
- `results/counterexamples/export/`：最初的导出时序反例把一个中间值也作为最终输出，输入域解释不如新构造清楚。正文用 `fork/` 的纯分叉反例，不用旧例证明题面域结论。
- `results/counterexamples/float_epochs/`：较早数值反例含无输入的常量根，E0为24006、变体24005。正文优先使用 `float_epochs_with_input/`：全部四条链均有普通 DDR 输入，E0为24007、变体24006。两者是不同输入，不是数值勘误。
- `results/word_ablation/080_q3/` 是额外独立四路消融，五轮全部完成。它使用同一人为等价细分池，不能被算成跨图封存性能验证。

未运行 CUDA、Metal、Mac、Windows、完整100例×核数×三问优化矩阵，未独立重跑 E2 校准误差实验。原缺295份历史结果仍缺；本轮新实验绝不标为找回旧记录。
