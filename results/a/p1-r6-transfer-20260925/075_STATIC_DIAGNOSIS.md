# 075 R6 静态波次诊断

仅读取 `official-transfer4/cells/075-k5` 中原图、旧/新 raw plan 和候选诊断；[analyze_075_static.py](analyze_075_static.py) 用标准库独立还原 COPY 收缩后的原 op 邻接、旧 Task DAG height、各 Task Pipe 工作及双入桥候选；[075-static-derived.json](075-static-derived.json) 记有逐波数据与四输入 SHA-256。未 import 作者模块，未构造或评价新方案；Task 编译、response、E0/E1/E2 调用均为 0。

**实改范围。** 旧方案有 107 Task、22 个 height 波；候选仅把旧 Task 6 的四个 op 移至新 Task 107/108，core 4 上保留 `Y=6,J=107`，core 0 前插 `X=108`。旧 Task 6 的原始工作是 M176/V567；新 X 为 M88/V28，Y 为 M88/V427，J 为 V112。作者诊断只列 height 0 的 V 波：最大单核 Pipe 工作 567→539，新增边界 2,688 B、51 个归一服务周期；这些是静态量，不是 Makespan 收益。

**为何主 M 波未改。** 偶数 height 2,4,…,20 的 M 波最大工作 4,192，五核各 Task 均无“双入边皆为桥”的汇合候选，故不满足 `_witness` 的必要条件。奇数 height 3,5,…,19 的 M 波有四个 donor 各 M21,616、一个 helper M6,136。每个重 Task 的平衡桥两侧各 M6,688/V4,640；另一个桥候选的小侧仅 V28。`_witness` 先最大化两侧较小的最大 Pipe 工作，故按现有规则选 M6,688 分支。若少于四个 donor 导出，未动 donor 仍为 M21,616；若四个均导给唯一 helper，helper M 至少 `6,136+4×6,688=32,888`，高于旧最大值。两种情况均过不了 `new_max < old_max`，即使其余结构守卫全通过。末波 height 21 的四个重 Task 同样有 M6,688 两侧桥，结论相同。height 1 是 V 波且无低于均值的现有 Task helper。于是唯一留在候选诊断中的正改动是 height 0。

这解释的是**当前 R6 选择与批量负载守卫**，不是证明 075 的重波无可行跨核切分。独立脚本只复核必要的双入桥及负载算术，未复现 `_witness` 的唯一内部 sink、direct/COPY 一致、祖先闭合等全部守卫；如需定位个别 donor 的精确拒绝点，应给作者诊断增加逐波 `no_bridge_join / witness_guard / no_helper / new_max` 计数，但本次没有运行作者构造器。参考规则：[branch_aid.py](../../../src/q1/branch_aid.py) 的 `_witness` 选择与 `construct` 波内负载判定；真实路径以项目根目录 `src/q1/branch_aid.py` 为准。模型实际 token 用量不可见。

## 下一步的工作量目标

仅看这个重M波的计算工作，五核均匀目标为 `(4×21616+6136)/5=18520`；每个donor向helper转移3096个M周期即可达到这一算术平衡。现有整分支每份6688太粗。3096是拆分目标，未证明图中有合适合法切口，也没有计入V工作、DDR、FIFO和Task门控，不代表可达到的Makespan。后续应研究较细的祖先闭合桥侧或前缀构造，而不是继续直接搬运整个6688分支。
