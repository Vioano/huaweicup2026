# Pure prepared guard readback

入口：`src/q3/layered_prepared_guard.py::check_layered_prepared(graph, plan, captured, *, layers)`。输入 `captured` 为旧 `query_flow_probe.py` 保存的 `task_return`、`step2`、`capacity` 结构；普通字典的整数核 key 与 JSON 回读后的字符串 key 均可。成功返回可 JSON 序列化的 report；失败抛 `PreparedGuardError(ValueError)`，其 `code`、`details` 和 `as_dict()` 可用于失败收据。`layers` 是外部已证明的结构层数；guard 只独立计算 prepared 联合图的 crossing 并检查 `<=layers+1`，不识别 row/track，也不以 R9 metadata 作通过依据。

核验内容：计划 singleton 与原计算覆盖；原图每 compute 有片上输出；独立重算闭区间 F；Task 本地 tensor pool/size/唯一 producer/计算 consumers；COPY 形状、字节、数量、输入首消费与输出生产桶；Step2 无 spill/新 incarnation；Step3 核内准备 `memory_peak<=capacity`；四条实际 pipe FIFO 与 plan M/V 投影；每条 MEMORY_REUSE 严格前向桶；跨核 COPY 对；原 Task 数据边、内存边、四 pipe FIFO、cross_links 的完整联合 DAG 与最大跨核边数。机器 report 含各类实际边数和 unique 联合边数。

**内存峰值边界**：`step3_local_memory_peaks` 是官方 Step3 在单核 Task 准备时的模拟值，不是 P3 最终跨核事件模拟的实际驻留峰值。本 API 不接最终 P3 result/trace；若需要后者，必须另行设计结果检查，不得从本 report 推断。

本轮运行了 5 个纯 toy（包含零字节输出、反向内存边、缺跨核 link、闭区间超容量），命令与回读：

```text
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 tests/test_q3_layered_prepared_guard.py
PASS test_backward_memory_dependency_is_rejected
PASS test_closed_frontier_overflow_is_rejected
PASS test_complete_two_core_toy
PASS test_missing_remote_copy_link_is_rejected
PASS test_zero_byte_output_still_has_a_bucket
```

只读使用已存在的 071/K5 `results/a/q3-nikolastarx/query-flow-one-shot-20260925/run/prepared.json.gz` 核过 JSON 结构与 guard 兼容性；对应 plan 来自 `results/a/q3-nikolastarx/query-flow-static-repair-20260925/run/case_071_multicore_res.json`。回读：

```text
status=passed compute_ops=741 prepared_ops=1002 copy_ops=261
original_copy_bytes=121446 scheduled_copy_bytes=393630
cross_links=89 memory_dependencies=0
edge_counts={'data_raw': 1336, 'pipe_fifo': 982, 'cross_links': 89}
union_unique_edges=2233 max_crossing=2 crossing_limit=2
```

071 只是旧格式/已知无内存边案例的回归，不验证 R9 的 005/086，也未触发新官方 Task、Step、P2、P3 或 E0 调用。`pytest` 在该 worktree 中不可用，以上测试使用 Python 直接执行。没有把 toy 或旧 071 当作新官方成绩。
