# 已编译内存依赖响应输入（研究支路）

`src/q1/compiled_memory_response.py` 调用冻结官方 P1 的 `_build_scene_a_tasks`，只接受 Step3 已标记 `execution_contract_validated=True` 的 Task。它从 Step3 `execution_graph` 的 `op_preds` 和逐 Pipe FIFO 编译四个完成前缀需求；所有 `MEMORY_REUSE` 前驱逐边复核。证书记载管理内存的总 tensor 足迹、Step3 实际峰值、内存依赖和官方源码哈希。

本支路仍拒绝原图/Step2 spill、单 tensor 超容量、非唯一管理内存 producer 和跨核 Task 依赖；允许经官方 Step3 验证的内存复用及总足迹超过容量。最终多核阶段按固定图依赖调度，不重新分配内存。本模型使用有理数 DDR 工作量，不能据此宣称与官方 E0 的浮点事件时间零差分，也没有证明任一求解器的质量或全量适用性。

合成测试只检查一例有 MEM 前驱的前缀覆盖和一例原保守入口已接受 Task 的签名一致。独立源码复核未发现上述限定域的遗漏发射条件；`memory_peak` 是 Step3 编译时峰值，不是有理数回放重新测得的峰值。

真实 008/K5 的三个小 Task 投影编译见 [固定三次探针](../../results/a/p1-memory-response-probe-20260925/README.md)。三者均被旧总足迹条件拒绝，均经官方 Step3 合法编译并显式包含 MEM 前驱；这证实保守筛选排除了可执行 Task，不证明它们能改善完整方案。未修改旧 DP 的接受域、缓存等价定理或正式统一算法，未新增真实 E0/E1/E2 评价。
