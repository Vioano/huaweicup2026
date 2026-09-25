# 短 V 合组：第一次静态证伪为阴性

固定源码 `c7e026d5271ef4a8d707559d7cf0e542c799d4d1`，事前规则与预算见 [PROTOCOL.md](PROTOCOL.md)。071/K5 的新合组在完整商图拓扑检查中被拒绝，原因是商图成环；069 未开始。首异常停止，没有修改阈值、换样本或重试，没有产生新候选的合法计划，也没有官方分数。

## 实际执行

- 命令：`uv run --locked python results/a/q3-nikolastarx/short-vector-static-20260925/probe.py --source c7e026d5271ef4a8d707559d7cf0e542c799d4d1 --out results/a/q3-nikolastarx/short-vector-static-20260925/run`。外层独立进程组监督的硬窗口为 60 秒，无重试；实际子进程退出码 1。
- 只完成 071 control：静态计算/FIFO/跨核延迟下界为 5218 周期，构造墙钟 0.933935 秒。它是本次新建的 placement 词控制计划，**不能冒充此前官方 incumbent，也不是官方 Makespan**。
- 调用账：construct 2 次（包含失败候选）、pipe_bound 1 次、静态 derive_multicore_plan 2 次、validate_graph 4 次；Task、Step1/2/3、E0/E1/E2、solver、VM 均为 0。诊断内层墙钟 1.189597 秒，不作为端到端求解器成绩。
- [summary.json](run/summary.json)、[stdout](run/stdout.txt)、[stderr](run/stderr.txt) 和完成的控制计划/元数据/下界均保留；[原件清单](run-manifest.json)记录字节数与 SHA-256。失败候选没有完成计划文件，069 没有运行证据。

## 得到的结论与限制

短 V 弱连通分量不一定是 DAG 凸集；把它收为一个放置模块可能形成“离开模块后又进入”的依赖环。这个反例推翻的是直接用弱连通分量当调度模块的通用规则，**没有推翻短操作同核可能获益的假设**。现有 guard 正确拒绝了不支持的商图；默认求解器没有启用此候选。

[独立纸面审查](CYCLE_REVIEW.md)给出三节点反例和逐次检查收缩的安全规则。它不声称识别了 071 实际环的节点，因为本次失败记录未保存该见证。更深一层的区分是：同核约束允许不同模块之间交错执行，而当前模块拓扑放置法要求模块可一次排定。商图成环排除了后者，不能直接解释成原图或所有同核计划不合法。

此前 [前沿审计](../attention-frontier-audit-20260925/README.md)确认 071/069 若干关键路径跨核边很短，但候选区域的完整外部边界分别有 13/11 个张量，不能从一条路径上的单张量切口推断全图宽度为 1。下一步优先研究带逐输入释放的联合放置或可安全收缩的结构，不通过追加评分筛掉语义不成立的候选。

本次小审查采用复用的 Sol medium，软预算 2500 token/5 分钟，禁止真实图探测、构造和官方调用；交付仅 `CYCLE_REVIEW.md`，实际 token 不可用。原始构造的 5 项短 V 测试及 24 项 Attention 测试已通过；它们不代替这个实际图上的阴性结果。

同一算法全 500 格主成绩仍为 `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`，此次不改主成绩、Cache 相对加速比或求解墙钟。第八轮 Pro 问题已在此前发送，本结果没有触发重发或打断。
