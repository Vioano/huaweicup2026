# C02 只产候选适配层（2026-09-25）

新增 `src/q2_nikolastarx/exit_sealed_kernel.py` 与 `exit_sealed_candidate.py`，未修改旧构造器、runner、native 或官方评价器。kernel 从浏览器附件预览恢复的公开源码文本复制；源文本 17595 字节，SHA-256 `f5321a3a76b03b765cadac393489b624bbe27eb6336744d0e45d5ef37779f16e`。原 ZIP 字节尚未取得，因此这不是 ZIP 原件核验；复制后的 kernel 仅在开头加入来源注释。

适配入口为 `propose(graph, plan, config, critical_links, original_finish_times, *, incumbent_makespan, max_seeds=8, max_candidates=2)`，返回 `(候选完整 singleton 计划列表, diagnostics)`。它从原始 tensor 表重建每个 seed 的**全部 eligible consumers**，不信任诊断中的消费者子集；拒绝逻辑别名、多 eligible producer、未表示的排除操作消费者、`D_val != D_exec`、旧计划/时刻/配置不全与原计划零 spill 未获证的输入。固定 500-cycle 异核延迟配置，区域至多 64 操作/1000 compute cycles，最多 8 个结构种子、2 个完整候选。新优先词仅使用一个入口提示：外部生产者旧完成时刻，异核时加 500 与两次孤立 COPY 工作；图输入加一次孤立 COPY 工作。提示不读取区域内旧开始时刻，也不是官方时刻预测。

原型 `propose` 返回二元组，适配层已明确解包。候选逐一做官方结构推导、既有 `zero_spill_intervals.certify` 和 `fixed_fifo_lower_bound` 的安全拒绝。返回项带 `plan/detail`，并标记 native 分数与独立 E0 验收待做。只对原型预选的至多两个候选执行上述较贵的全图 guard；失败不继续生成第 3 个候选。baseline 的 DAGIndex/官方计划推导与零 spill 证书、候选的全图 FIFO 下界可能是主要在线成本；本轮没有端到端计时或真实图运行，不能据此承诺满足求解墙钟目标。

验证：`python3 -m unittest tests.test_q2_exit_sealed_candidate -v`，4 项合成测试通过（macOS arm64，Python 3.14.5）。覆盖双 Pipe 完整汇合与 singleton ID/字段/覆盖保持，隐藏外部消费者的完整 tensor 视图拒绝，逻辑别名拒绝，以及有必需 DDR 输出时该支路不被错误吸收。这是结构与接口验证；没有真实图候选、native/E0、Makespan 或全量成绩。旧五格窗口与正式算法均未改变。

停点：在线包装器尚未接入。下一步需固定该 adapter 所接收的保存诊断与 `original_finish_times` 来源、预算和停止条件；用真实受保护图检查候选，再在另一个已授权窗口依次做 native 与独立 E0，并保留失败原件。不能把 `status=candidates` 当作官方可运行或 M 改善。

## Parent review

2026-09-25: reviewed guarded original incidence, mandatory-output escapes, complete saved finish-time requirement, tuple return, frozen single hint and maximum candidate budget. Re-ran the four synthetic adapter tests using the project Python 3.12 venv; all passed. This is not a real-graph/official performance test. Existing reverse and hypergap sources remain unchanged.

## External input correction

The original adapter incorrectly rejected ordinary graph-input DDR → COPY_IN → local tensor edges. The guarded correction accepts only producer-free DDR inputs with one equal-size local output, no direct op edges, a unique COPY_IN producer and exclusively eligible consumers. Relay COPY_IN and hidden consumers remain rejected. Six regression tests cover acceptance and five rejection boundaries. An isolated copy generated two unscored 069/K5 plans from the previously archived native trace (48/45 regional operations; construction 0.096 s); structural validity and the existing zero-spill certificate passed. This is saved-evidence-assisted construction, not an online full solver or a measured improvement.
