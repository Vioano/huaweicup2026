# L1 容量约束的连续分段原型

`shared_pipeline_capacity.py` 是只读调用项目 `Index`、官方结构推导及
`shared_pipeline._stage_structure` 的静态构造。输入为原始图的 `Index` 与
官方请求核数 1–5；返回只有 `node_to_subgraph`、`core_schedules` 两字段的方案及
静态元数据。它没有 runner、在线选优、评价器调用或自动回退。

守卫沿用 `_stage_structure`：所有弱分量须为具有真实相邻依赖边的同签名作业，
共有外部输入非空；并要求位置数 ≤512、作业数 ≥ 请求核数。额外要求每个共有
外部输入的原始 tensor `pos=L1`，拒绝 UB 或其他位置。容量从冻结官方
`data/raw/a/official/data/config.txt` 读取，本轮 L1 为 524288 B。算法不读取
case 编号或历史切点，也不更改原图、COPY 操作、tensor ID/size。

每个位置取第一个作业实际读取的共有外部输入 tensor 集合。对半开区间
`[l,r)` 求集合并集，按原始 tensor size 求和；同一个 tensor 在区间内被多个
位置读取只计一次。DP 在恰好 `min(cores, positions)` 个非空连续段、每段并集
字节 ≤ L1 容量的条件下，最小化各段计算周期和的最大值。计算周期来自
`Index.duration`，只作构造代理；同值时选较小前一切点。无可行切分则抛
`UnsupportedStructure`。每个作业采用同一切点，核内按作业顺序遍历，操作均为
singleton 子图。若位置少于核数，剩余核有空顺序。

设位置数为 `n`、段数为 `k`、每位置平均共有输入引用数为 `d`。区间并集预计算
时间 `O(n²d)`、空间 `O(n²)`；DP 时间 `O(kn²)`、空间 `O(kn)`，总计
`O(n²d + kn²)` 时间与 `O(n² + kn)` 空间。`n≤512` 是明确停止规模，
DP 只解一个静态构造，不试多套参数或分段。构造完成后调用既有
`derive_multicore_plan` 检查结构。

容量约束只说明**每段所有共有原始 L1 输入同时容纳**。它不覆盖各段其他
输入、激活、跨核传输、Task 重构或 Step2 换出与 Step3 地址复用，也不保证零 spill、
零 reload 或更低官方 Makespan。`ideal_flowshop_cycles` 只是假定无 COPY 的
串行服务器代理，不是官方结果边界。需单独授权的 E0 实验才能判断真实收益。

静态验证命令（在项目工作树根目录执行）：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --locked python -m unittest tests.q3.test_shared_pipeline_capacity -v
```

测试覆盖小型穷举下的受限 DP 最优、重复 tensor 去重、无解、L1 位置守卫、
原始 044/046 的五核合法覆盖和图不变。已在本工作树复核这组静态测试；尚未接入在线策略。

## 两个固定候选的机制验证

`src.q3.pipeline_capacity_probe` 分为 `prepare` 与 `run`。前者校验冻结官方图和
现有 forest500 原件，仅构造 044/046 各一个五核候选并做静态下界检查；后者要求
固定源码 HEAD、预先确定的 manifest 哈希及新的资源准入。最多 2 次 P3、0 次 P2、
0 次 solver、1 worker、0 重试，每次至多 60 秒，整批 120 秒，采样进程组 RSS
警戒 512 MiB。独占 evaluation 目录防止同一准备批次重复执行；第一处失败即停。
这份预算不是资源调度授权。调用官方评估前须按协调窗口读取实时主机状态；
没有完整求解程序运行时不把 prepare 或 E0 时间作为 solver_wall。

已有完整 forest500 提供固定控制，不重跑旧方案；计划下界已不可能严格改善时
跳过评分。所有负结果同样保留。这是两个已见结构样本的机制测试，不作新算法
全量成绩或泛化成绩。
