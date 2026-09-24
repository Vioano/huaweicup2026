# 079-k5 时序差异只读审计

来源：`results/a/q3-nikolastarx/band-mechanism-20260925/run.json`（源码 `ae5a67ed55b2a983d8a6d609ece06c1a99278355`），该目录的 `079-k5-{component_id,pair_cache_model}/p{2,3}.json.gz`；旧方案按 `results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json` 中 079-k5 的 `receipt_path` 找到同一 evidence 目录的 `result.json.gz`。时间线均是官方 E0 的 `per_core_timeline[*].ops`。本审计未调用 solver/E0。`gap-core-audit.json` 存全部逐核计算。

## 直接观察

| 方案 | P2 M | P3 M | P3 scheduled COPY B | P3 miss B | P3 hit B |
|---|---:|---:|---:|---:|---:|
| 新 component_id | 6,198,009 | 6,194,353 | 41,385,984 | 27,791,360 | 10,055,680 |
| 新 pair_cache_model | 6,168,568 | 6,165,618 | 37,928,960 | 25,292,800 | 9,097,216 |
| 旧 forest_memory_order | 未在本次新批次内 | 6,075,472 | 57,028,608 | 40,429,568 | 13,060,096 |

新方案同一个 ownership，`coverage_bytes=13,246,464`，是构造器的受限覆盖指标，不能当官方 DDR 搬运。pair 相比 component_id 减少 scheduled COPY 3,457,024 B，P3 M 缩短 28,735；相比旧 forest，scheduled COPY 少 19,099,648 B、miss B 少 15,136,768 B，P3 M 却长 90,146。

P3 关键末端：新 pair 核 0 最后一个 PIPE_M 在 6,165,005 结束，最后操作在 6,165,618 结束；旧 forest 核 2 最后一个 PIPE_M 在 6,074,852 结束，最后操作在 6,075,472 结束。两者首个 PIPE_M 都在 860 开始，关键核 PIPE_M 总忙时都是 5,925,744，尾部各为 613/620。因此 Makespan 差额 **90,146 = 内部 PIPE_M 间隙差 90,153（238,401 对 148,248）- 尾部差 7**。新 component_id 关键核 0 的相应内部间隙为 267,136，pair 缩短 28,735，恰等于两者 P3 M 差额。三个方案各核首算皆 860；新 pair 的核 0/2 最后 PIPE_M 只差 340 周期，旧 forest 的核 0/1/2 最后 PIPE_M 跨度 555 周期。

这段间隙是 PIPE_M 未忙的墙钟，**不是已确证的依赖等待**。对上述两个关键核做时间区间交集，新 pair 的 238,401 间隙中有 232,521 与 PIPE_V 操作重叠、14,510 与 PIPE_MTE2 重叠；旧 forest 的 148,248 中分别有 144,246、11,766 重叠（不同 pipe 可以互相重叠，不能相加作分摊）。两个关键核 PIPE_V 总忙时都为 757,248，PIPE_MTE2 总忙时新 pair 为 162,777、旧 forest 为 251,862。`task_dependencies` 和 `cross_core_transfers` 均为空列表；这不能排除子图内部数据依赖。COPY 数量、字节更少却更慢，因此“COPY 总量直接导致 90,146”不受数据支持；COPY 时机通过局部依赖改变流水重叠仍是待检验假说。

## 下一最小动作

仅对 079-k5 的新 pair 关键核 0 与旧 forest 关键核 2，按各自树内位置/子图关联 PIPE_M 与紧邻前序 PIPE_V、COPY_IN，输出造成累计额外约 90k 间隙的具体区段及依赖边，再考虑单一顺序改动的 E0 复评。当前先做只读对齐；不要凭总 COPY 或 Cache 命中统计更换策略。此局部差异不能外推为 100 图固定算法成绩。
