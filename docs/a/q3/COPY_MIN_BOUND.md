# P3 真实跨核 COPY 对的服务下界

`src/q3/copy_bound.py` 是独立的静态拒绝证书，不调用 E0，不改已有 `pipe_bound` 或求解器。输入是原始图、singleton 方案及本次**冻结 P3** 的 `delay`、DDR 带宽、Cache 读取带宽。当前配置见 `data/raw/a/official/data/config.txt`：分别为 500 cycles、60 和 250 bytes/cycle。若这些值不是实际执行配置，结果不适用于该执行。

入口先调用 `pipe_bound.analyze`，继承其 singleton M/V、整数计算时长、COPY 收缩歧义、增强图有环等全部 guard。首版还要求 tensor 的 `size` 为非负整数、`pos` 为 DDR/L1/UB、至多一个原 producer；直接 op-op 边的 `data_size` 必须为非负整数（缺省按官方的 0）。DDR 和 Cache 带宽为正整数。超出范围抛 `UnsupportedBound`。

冻结 `multicore_cut_evaluate_problem_3.py:141-215,217-241` 对跨核原 tensor 连接和跨核直接边按源核/目标核创建真实 COPY_OUT/COPY_IN 对；直接边的大小取 `data_size`。源 COPY_OUT 读取该 tensor，须在源计算完成之后；目标 COPY_IN 完成之后，目标计算才能启动。该文件 `:346-350,436-464` 从**源 COPY_OUT 完成**起再等 `delay`，而不是从源计算完成起等。`schedule_step3.py:74-82` 按 COPY_OUT 输入 tensor 或 COPY_IN 输出 tensor 的大小算最短服务，至少 1 cycle；P3 `:539-580` 仅允许 COPY_IN 命中只读 Cache，COPY_OUT 必走 DDR。因此，对一条确定生成该 COPY 对、大小为 `s` 的跨核计算边，必要间隔为

```text
start(v) >= end(u) + max(1, ceil(s / DDR_bandwidth))
                       + delay + max(1, ceil(s / Cache_bandwidth))
```

只用最快 Cache 服务计算 COPY_IN，忽略 DDR/Cache 竞争及其他阻塞，故是下界。多个 tensor 或直接边约束同一 `(u,v)` 时取 **max**，不相加。每核同 Pipe 的原计算 FIFO 沿用旧证明：P3 按 singleton 子图次序组织序列，Step2 只插入 spill、不重排原操作，Step3 的 Pipe 投影固定。增强 DAG 最长路因此不超过任何成功执行的官方 Makespan。

图输入没有原计算 producer；P3 `:166-175` 只为每个消费核加入 COPY_IN，本模块不对它收费。Step2 `schedule_step2.py:304-379` 可复用已有 DDR backing，此时 spill 只有 COPY_IN；不能把任意 spill 当作上述完整跨核 COPY 对。Step2 的 `:407-435` 会重命名物理 incarnation，但不删除跨核建图时插入的 COPY 对；这些额外等待只会使实际执行更晚。多原 producer 在首版直接拒绝，避免从单一 producer 推断整条 tensor 的物理来源。

返回 `legacy_bound`、`copy_min_bound`、关键路径及逐连接 `charged_connections` 证据。`charged_path_edges` 指明关键路径中达到该边最大 lag 的连接。标记 `execution_legality_proved=false`、`official_optimality_proved=false`、`official_evaluations=0`。若 `copy_min_bound.lower_bound_cycles >= anchor` 的已知官方 Makespan，只能证明该具体候选**不能严格改善 Makespan**；较小下界不能证明候选合法或优于 anchor。

小型合成单测仅核对上述数学和危险边界，没有运行官方 evaluator：

```sh
uv run python -m unittest tests.q3.test_copy_bound -v
```

Implementation read minimum uses the faster of the supplied DDR and Cache rates, preserving a necessary bound even if Cache is slower. Charged path evidence is indexed by operation pair, avoiding a full scan of all charged edges per path edge.
