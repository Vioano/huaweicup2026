# 合并真实整链 reserve 的错相提案（尚未评分）

前一次 R5 对照证明，同分区重排可降低该模型方案的 Makespan，但 53 个 Task 的错相方案仍比旧整链 A 慢 637 周期。观察路径上的计算节省被 DDR 持续时间与门控增加抵消，详见 [R5 实测报告](../p1-r5-phase-colab-20260925/README.md)。

本提案只改变 reserve 的组织方式：每核把相位前的 h 条完整链合为一个 Task，把相位后的 H-h 条完整链合为另一个 Task，空段不生成 Task。两次 body 和 drain 不变，余数 tail 保留。控制方案将两段都放在 body 前；错相方案将后一段放在 body 后。每个控制对保持相同分区、Task ID 与核归属，只改变合法 Task 顺序。它适用于已经证明独立、无 COPY 桥的私人真链，不能直接扩展到一般 DAG。

对已冻结的 008/K5 原图，固定 q=7、s=3、参考周期 35405、链计算量 4512 时，结构检查得到 **27 个 Task**（各核 5/6/6/5/5），原提案为 53。两份计划均通过官方结构及 Task 顺序校验，5 项纯计划测试通过；没有运行真实 Task 编译、模型或官方评分。证据见 [structural-preflight.json](structural-preflight.json)。

代码：[构造](../../../src/review/p1_coalesced_phase_plan.py)、[研究 runner](../../../src/review/p1_coalesced_phase_probe.py)。研究 runner 复用既有完整 MEM 编译及两次有时限 Fraction 响应守卫，不改生产统一算法。相位参数来自明确的当前输入参考值，代码没有 case-ID 分支或包宽/相位扫描。

合并改变局部 FIFO、MEM 前驱、缓存生命周期和实际相位。减少 Task 数不保证 Makespan 改善，不能用原 trace 推算新分区的成绩。若安排下一次资源窗口，只验证这一固定控制对；其执行、E0 和全量 Benchmark 均尚未获本提案授权。
