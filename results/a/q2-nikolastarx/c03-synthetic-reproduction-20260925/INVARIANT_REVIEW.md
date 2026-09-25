# C03 / P2 COPY 字节不变量：只读源码审阅

**结论。** 对同一份冻结原图、同一 P2 配置，若两份合法方案给每个 eligible 原操作分配的核完全相同，而且两次官方 Step2 均确认为零 spill，则 `scheduled_copy_bytes`、`added_copy_bytes`（这里的 addedDDR）及其 `partition_added_copy_bytes` 必然相同。原计算的优先顺序、singleton 子图 ID、COPY 锚点可以变化；它们不改变这些字节数。C03 第 5 节与第 8 节的断言在这些条件下成立，但“零 spill”必须指**两份方案的官方 Step2 实际结果**，不能只依赖静态证书或固定服务模型。此结论不保证官方 Makespan、COPY 完成时刻或共享 DDR 的非干扰。

**源码依据。** P2 的 `_build_scene_b_tasks` 用 `derive_multicore_plan` 得到 `mapping/core_by_op/core_orders`，并固定创建 `num_cores` 个 Task（`data/raw/a/official/code/multicore_cut_evaluate_problem_2.py:61-86`）；返回值也把 `task_count` 设为 `num_cores`（`:593-597`）。因此仅重排 `core_schedules` 不会导致 Task 分裂/合并。对每个原 tensor，它只按 eligible 生产核、消费核的集合重建图输入 COPY_IN、图输出 COPY_OUT、每个不同 source-core→target-core 的一对 COPY（`:133-207`）。直接 op→op 边在跨核时生成一对、同核时不生成（`:209-234`）。这些分支的次数、size 只依赖原图和 `core_by_op`，与先后顺序无关。`min`/`max` 选择首消费者或末生产者的子图作为 COPY 锚点（`:161-166,174-179,183-200`），所以锚点确实可随重排变化，但每个分支仍只调用一次对应的 `add_copy_*`。COPY 字节按各 COPY 的 tensor size 累加（`multicore_cut_evaluate_problem_1.py:51-66`）；P2 只额外加入 Step2 的 `spill_records` 字节，并以 `task_graph_copy_traffic - original_copy_traffic + spill_copy_traffic` 计算 added（`multicore_cut_evaluate_problem_2.py:236-280`）。原图相同且两次 spill 为零，就得到相同的 scheduled 和 added 字节。

**适配器核对。** C02 `emit_plan` 原样复制 `node_to_subgraph`，只由行顺序重建 `core_schedules`，且拒绝非 singleton 映射（`src/q2_nikolastarx/exit_sealed_kernel.py:371-380`）。现有 `recover` 会保留区域外核内子序列，但本身可把区域操作改派给出口核（`:255-284`）；所以比较“同一 C02 候选的两种 recover”时，必须显式逐操作比较 `core_by_op`，不能只凭区域、内部词固定作推断。`exit_sealed_candidate.py:209-213` 对候选调用入口校验和 `certify`；它给出的零 spill 证书仍应和官方生成的 `spill_added_copy_bytes == 0` 对照。

最小核对字段：原图哈希及核数/带宽/容量；两份 `node_to_subgraph` 覆盖和每个 eligible op 的 `core_by_op`；`core_schedules` 完整且各子图恰好一次；官方 `task_count`、`spill_added_copy_bytes`、`partition_added_copy_bytes`、`scheduled_copy_bytes`、`added_copy_bytes`。若两次字节不同，先查图/配置/分核/Step2 spill 与输出字段含义，再查适配器。即使数值相同，也不能推出 COPY 锚点、Step3 内存补边或共享 DDR 时序相同；官方 DDR 在途请求会重算完成时间（`multicore_cut_evaluate_problem_2.py:329-372`）。

固定服务模型中“旧时刻与最晚时刻统一中点并向下取整”的整数差分证明（C03 `:79-108`）就**其声明的整数服务时间、整数滞后和固定有向边**而言，没有明显的取整漏洞：若 `x_v >= x_u+c` 且 `c` 为整数，则 `floor(x_v) >= floor(x_u)+c`。真正的适用边界是模型未纳入自动 COPY、MTE FIFO、内存补边和共享 DDR；不能把该证明升级为真实 P2 不退化保证。

本审阅未运行官方图、solver 或 E0/E1/E2；仅检查冻结源码和 C03 文本。
