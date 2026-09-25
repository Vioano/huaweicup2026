# 短纯 V 区域：一次确定的静态证伪

假设：外围短 V fork/join 被旧 exclusive-chain 边界切开，可能引入比整块计算工作还长的跨核释放延迟。新规则将既有 Attention 行/FFN 外的最大 V-only 弱连通分量，在原正计算工作总量≤官方 cross delay 时作为同核放置区域。不是按编号分段，不进一步切分超过阈值的分量，阈值只来自固定配置500；原算子仍singleton，逐输入释放，完整商图必须无环。

受限定理：孤立弱连通计算子图、全为同一种单槽pipe、正时长总量W≤δ、所有外部输入在各核0时刻同等可得、核无其他工作且忽略容量和COPY服务时，整图同核按拓扑序串行可在W内完成；任一真正分核至少有一条内部跨核依赖，其源/目的正时长加δ>W，故不能更快。这个定理不覆盖外部释放差异、核竞争或官方全图，不能将新规则当无条件最优。tests/q3/test_short_vectors.py另有外部日历使整体同核变差的反例。

唯一构造变动是pack_short_vectors=True。固定pack_ffn=True、placement_mode=gap、final_order=placement；新旧均用这些参数，避免把最终词变化混成分组收益。样本事先固定原071/069五核，分别一次旧构造+一次新构造，共4次静态construct；每份仅一次pipe_bound。使用原同一源码完整HEAD，CLI要求--source匹配，拒绝脏算法文件。每份输入核官方manifest字节SHA；配置和官方源码逐件核定。

预算：0 solver、0 Task、0 Step1/2/3、0 E0/E1/E2、0 VM；静态derive/validate辅助调用单列。1进程，最多4份构造/4份静态bound，预计小于10秒，硬运行窗口60秒；首异常停止、无重试。禁止借失败改阈值/换图续跑。输出只证明新优先词可派生、原依赖/FIFO计算代理与覆盖；不证明官方COPY/容量合法、不报官方成绩。出现商图环拒绝该候选；若全图代理不改善就保留阴性，不为较小局部等待追加E0。

执行：固定源码提交后，`uv run --locked python results/a/q3-nikolastarx/short-vector-static-20260925/probe.py --source <完整SHA> --out <新目录>`，外层设60秒deadline。真正有潜力仍先核官方准备语义，且新的官方预算与资源排程独立审批；不复用已花完阶段，也不在等待partial预加载时擅自并跑。
