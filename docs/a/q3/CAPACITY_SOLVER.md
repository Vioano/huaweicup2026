# 容量感知共享输入流水线：统一在线入口

`src.q3.capacity_solve` 先在**同一次求解**中完整运行现有
`forest_solve.evaluate_candidates`，取得新鲜的官方 E0 incumbent；不读取历史赢家。
随后只调用一次 `shared_pipeline_capacity.construct(index, cores)`。构造沿用
`shared_pipeline._stage_structure` 的同签名作业识别，仅接受共有外部输入
全部在原始 L1 的结构。分段 DP 对每段共有输入 tensor ID 求并集，按原始
size 计容量，最小化最大段计算周期；不会按 case 编号或固定切点选择方案。
设位置数 `n≤512`、段数 `k≤5`、每位置平均共有输入引用数 `d`，区间并集
预计算为 `O(n²d)` 时间和 `O(n²)` 空间，DP 为 `O(kn²)` 时间、`O(kn)`
空间。无容量可行切分时明确拒绝；不试第二套切点或参数。

追加候选依次经过结构拒绝、与本次调用中已评价方案的字节级去重、
`pipe_bound.analyze` 的已证下界筛除。只有下界严格小于当前官方
Makespan，或当前结构不适用已证下界时，才允许一次新 E0。
`UnsupportedBound` 表示不能据此剪枝；其他异常照常暴露。
`EvaluationValidationError` 记为一次失败评价并保留 incumbent。
仅当新增结果的官方 Makespan **严格小于** incumbent 时选用容量方案；
搬运字节和命中率照实记录，可能退化，不被合成代理分数隐藏。平局保留
incumbent。此规则对 1–5 核一致，1 核只按实际结构守卫决定是否构造。

入口 `safe_solve.main(policy=evaluate_candidates, candidate_limit=4)` 强制单次
求解至多 4 次在线 E0：forest 最多 3 次，容量候选最多增加 1 次。评价前
计次和落盘的机制由 `safe_solve` 执行；构造、下界、评分、保存与收尾
均在求解过程内。`receipt.json` 的 `main_until_evidence_seconds` 不含最后
发布动作；**完整端到端求解墙钟以外层进程计时为准**，并将官方 E0 耗时
单独列出。离线编译或共享主机并发需另报，不得把单次评分时间当作求解时间。

候选记录的 `strategy` 为 `capacity_shared_pipeline`，跳过原因、下界、
未评分方案哈希、评价调用数及结果纳入证据。方案输出仍只含
`node_to_subgraph` 和 `core_schedules`。源码不修改官方图、COPY 操作、
配置或评价器。容量守卫只覆盖**每段共有原始 L1 输入同时容纳**，不保证
零 spill 或真实 Makespan 改善；官方 E0 才判断完整效果。

测试：

```sh
uv run --locked --no-sync python -m unittest tests.q3.test_capacity_solve -v
```

六项注入测试只验证策略与调用账，不运行官方模拟。当前尚无这个**固定统一
入口**在全部 100 图×1–5 核的逐格证据。任何单格或少量对照只是候选
研发证据，不能宣称全量成绩、达标或 Pareto 改善。正式批次须冻结完整
源码提交、统一入口、参数与评价预算，保留失败和超时格，并报告完整
求解墙钟及官方 Makespan/额外搬运/命中率。
