# R8 query-flow affinity 独立实现交接（2026-09-25）

**任务与范围。** 新增 `src/q3/query_flow.py` 的 `construct(index, cores, cross_delay=500, *, capacity=None)`；只返回原 compute op singleton 方案及静态 `info`，没有接入 solver/runner。`capacity` 可显式传入 L1/UB 字节；省略时只读冻结 `data/raw/a/official/data/config.txt`。`UnsupportedStructure` 表示本受限族不适用，不把拒绝转成成绩。

**机制。** 复用 `attention_rows._ports/_recognize` 审核真实原 tensor 端口和闭合 row。每个 row 的 Q 投影必须有唯一的原输入 tensor 同时出现于 K、V 投影，并按 Q 投影使用次数排除更广泛共享的参数；无法唯一识别则拒绝。K/V 投影再按此输入映射到源流，保留跨流广播。共同祖先作为共享 S，row 为 A，投影祖先为 P，row 后继为 O；余下仅能唯一附着一个私有流。每条原计算边验证阶段不回退，跨流只能是实际 K/V→row，S 弱连通分量同核。`_ports` 同时拒绝直接 op-op 桥、多 producer 和无法与原张量边一致的 COPY 收缩。未分类、重复覆盖、串行多层 row 或不明 join 均拒绝。

当 `r<=k` 时每流独占一核；当 `r=k+1` 时仅枚举一个规范化合并对；更多流拒绝。共享 S 分量用不同输出 tensor→目的核字节的固定规则选核。四阶段只限定每核 M/V pipe 的构造词；各核时间轴没有全局阶段 barrier。每个候选以原计算边、实际每 pipe FIFO 与 `cross_delay` 重算静态最长路，先按含延迟界、再按结构跨核 tensor 字节、最后按规范化合并对排序。

本版 `_stage_word` 为清楚起见每次扫描本阶段全部 ready op 并重算其前驱释放；最坏时间约为 `O(B(r,k)·(N²·d + E + kN))`（`d` 为单节点最大前驱数，粗保守上界），**没有**实现 R8 文本的堆式 `O(B(r,k)·((N+E)log N+kN))`。实际冷 solver 耗时尚未测。容量元数据按全部 `cores` 输出，空核的 L1/UB 支持量补零。

**容量证书。** 在 `_ports` 的无直接边前提下，按 P3 每核 Task 的 `touched_cores` 规则枚举每个原物理 tensor ID 的本地副本；原 DDR 本地视图计入 UB，新增 backing 留 DDR。每 Task/每池按物理 ID 去重求全支持字节，超容量的候选跳过。没有直接 op-op 桥，因此不会漏计其新 UB tensor。唯一原 producer 加无 spill 的全支持充分条件对应 `REVIEW.md` 中 Step2/Step3 的条件证明。此处**没有运行** Task、Step2、Step3，`info.physical_support_certificate` 仅陈述满足这些静态充分 guard，并非官方运行结果。

**交付与验证。** 新增 `tests/test_q3_query_flow.py`，以不调用官方函数的内存 toy 图和注入的已识别 row 检查规范合并对、singleton 覆盖、阶段 pipe 单调、同图两跨核上界、容量拒绝及直接边拒绝。`python3 -m unittest discover -s tests -p test_q3_query_flow.py -v` 在一次断言修正后 2/2 通过。随后将查询键候选从“出现于 K 或 V”收紧为“同时出现于 K 与 V”；按本 toy 的构造该改动不改变路径，但依约没有增加第三次测试。`python` 命令在此环境不存在，测试使用 `python3`。

**未验证与停止条件。** 没有运行真实 071/069、官方 E0/E2、Task/Step1/2/3、VM、网络或 Pro ZIP；没有任何实测 Makespan、spill、`MEMORY_REUSE` 或速度结论。真实图若无法唯一识别查询原输入、容量全支持超界或静态图不满足 guard，应保留拒绝原因，不放宽 guard 或做样本 ID 特判。这是 R8 当前轮静态实现；本交接不启动 R9。

## 父会话复审与最小修正

在最终静态实验冻结前，父会话修正了两个未触发官方调用的实现问题：共享分量的候选核应枚举 `flow_owner.values()` 而非流编号键；冻结配置是空白分隔而非标准 INI 键值，用项目已冻结的只读 `read_evaluation_config` 读取，不能用默认 ConfigParser。对这两处修正及子代理最后的查询键收紧，父会话另执行一次上述 2 项 toy 测试，全部通过（0.001秒）；并一次只读默认容量入口，核回 L1 524288/UB 131072 B。新检查0 Task/Step/E0/VM，不是增加真实实验预算。
