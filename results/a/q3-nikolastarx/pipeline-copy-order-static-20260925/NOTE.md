# Shared-input pipeline 的 COPY_IN 顺序：冻结源码静态审计

范围：当前 worktree `7133ee80a`；只读冻结官方源码、原图和现有构造源码。未调用 Task/Step2/Step3/E0，也未验证新的分组计划。下面的“可改变”是条件性机制结论，不是 044 成绩预测。

1. 当前 `src/q3/shared_pipeline_capacity.py:94-123` 为每个非 COPY op 建一个 singleton 子图，并按“job 外层、该 job 的段内位置内层”写入各核 `core_schedules`。选手方案只映射非 COPY op；官方校验要求每子图只出现一次、收缩子图 DAG 无环且同核依赖顺序合法（`data/raw/a/official/code/stub_multicore_cut_and_schedule.py:114-154,168-230`）。此处无通用“每子图只能一节点”的约束。
2. Scene B 每核合成**一个 Task**（`multicore_cut_evaluate_problem_3.py:69-94`）。原图外部共享输入没有 eligible producer，Task 为每个消费核生成一次 DDR→片上 COPY_IN，并把它归到本核**最早消费者子图**（`:166-174`）；跨核 activation 的生产核 COPY_OUT 与消费核 COPY_IN 也按各自最末生产者/最早消费者子图归属（`:189-208`）。两个 COPY_IN 都是 `PIPE_MTE2`（`:111-123`）。
3. Task 中先运行 Step1 reverse DFS，其无环拓扑序受 COPY_IN 标记、深度、op ID 与 LIFO 影响（`schedule_step1.py:105-114,128-181,187-198`）。然后官方按 `core_schedules` 的子图 rank **稳定分桶**；不同桶严格按 rank，同桶保留 Step1 相对顺序；若重排破坏本核拓扑即拒绝（`multicore_cut_evaluate_problem_3.py:51-67,253-259`）。
4. Step2 的 `seq_ext` 在该序列对应访问点插入 spill 操作（`schedule_step2.py:443-459`），不自行交换两条已有 COPY_IN。当前 044 零 spill 只是该保存计划的观察；新分组可能改变容量生命周期与 spill，不能沿用“零 spill”结论。
5. Step3 将 `seq_ext` 在每条 Pipe 上的投影定为固定顺序（`schedule_step3.py:281-296`），随后可添加片上内存复用边并检查是否成环（`:583-639`）。多核阶段装载此顺序（`multicore_cut_evaluate_problem_3.py:339-350`），仅当前 MTE2 游标对应 op 才能进入 ready 队列（`:443-464,466-474`）；跨核 COPY_IN 还需等生产 COPY_OUT 完成再加固定延迟（`:436-460`）。因此排在前面的 activation 未释放时，后面虽可独立读取的共享输入也不能越过同一 MTE2 游标。
6. **分组能改序的充要操作条件：** 保持每个 op 的核归属不变时，Task 数据边和 Step1 原始序不变；只有子图 rank 的稳定分桶会变。若两 COPY_IN 原来不同桶、合并后同桶，且 Step1 原始序把共享输入排在 activation 前，分组才会交换二者在 MTE2 的顺序；还必须通过子图 DAG、重排拓扑、Step2/Step3 容量与无环校验。若原始 Step1 已是 activation 在前，合桶不会使共享输入反超。
7. **最小可改构型：** 两条独立下游支路，同核 Q 消费来自另核 P 的 activation，R 消费原图 COPY_IN 的共享输入；Q、R 无依赖，且原图 op ID/深度使 Step1 从 R 支路先回溯（例如同深度的两个终点中 R 的 ID 较小；`schedule_step1.py:141-154`）。singleton 强排 Q 子图→R 子图，故 activation COPY_IN 在前；合并 Q、R 后同桶稳定保留 Step1 的共享输入 COPY_IN 在前。合法性仍需检查其他边、容量和最终校验。这说明“分组永远不能改”是假的。
8. **链式反例：** 下游 Q 先消费跨核 activation，随后 Q→R，R 才消费共享输入，且 R 是该局部 Task 唯一终点。即使把 Q、R 合一桶，Step1 回溯 R 时面对非 COPY 前驱 Q 与共享 COPY_IN，会按 key 压栈、LIFO 先遍历 Q，再遍历 Q 的 activation COPY_IN（`schedule_step1.py:141-181`）；合桶仍是 activation 在前。044 的 core2 首段在原图恰有 `RELU 103 → CONV 104`，shared L1 tensor `1000000045` 在 104 读取；singleton 中两者分属相邻子图。这个局部模式提示合并 103/104 未必有效，但 044 的共享 tensor 跨 11 条作业，完整 raw Step1 顺序还受其余出口与消费者影响，不能仅凭此局部反例断言实际合并后的全 Task 顺序。
9. 若共享输入与 activation 本就由**同一**下游 op 消费，Task 两条 COPY_IN 已归同一最早消费者桶；再合并相邻计算节点不会赋予新的 COPY_IN 排序自由。此时顺序由原始 Step1 决定，受生成 COPY op ID/深度影响，而选手不能直接把 COPY op 写进 `node_to_subgraph`（`stub_multicore_cut_and_schedule.py:122-152`）。
10. 可证伪的下一步仅是**静态候选筛选**：保留原有分核，逐段找“activation 首消费者之后的共享输入首消费者”，检查合桶前后 rank 与原始 Step1 相对序，并先用收缩 DAG/拓扑条件淘汰无效候选；只有原始 Step1 的共享输入确实在前者才值得申请后续正式验证。不能把图中允许合桶、或输入可独立 DDR 读取，直接等同于全局时间线提前或 Makespan 改善。
