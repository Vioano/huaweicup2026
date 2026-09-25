# R8 两条条件命题的独立静态审阅（2026-09-25）

范围：只读 `FINAL-r08-bc5e4db8.rendered.txt`、其 `supplement.json`、冻结 P3/Step2/Step3 源码及 `config.txt`。没有运行构造器、求解器、官方评价函数或附件；071/069 的数值均是 Pro 报告，**不是本机复现**。

## 1. 计算增强 DAG 的两次跨核界：**需收紧后成立**

在同一固定 owner、同一原计算图和同一逐 M/V pipe FIFO 上，令 `L0` 为跨核边权设零的最长路，`Lδ` 为每条跨核原计算依赖增加同一个非负 `δ` 后的最长路。若每条**原计算边和 FIFO 边**都不降低 `S < P < A < O` 阶段，所有私有流完整同核，S 的每个原计算弱连通分量完整同核，且仅有 `S → 私有` 与跨流 `P(K/V) → A` 两类跨核原计算边，那么路径至多经过一次 `S → 私有`、一次 `P → A`；故跨核边数 ≤2，逐路径加权并取最大值得 `Lδ ≤ L0 + 2δ`。同阶段 S 内边因弱连通分量同核而不跨核，私有流内部边也不跨核。这是严格的**计算图**界。

R8 的“四阶段 FIFO 单调”只约束排出的 M/V 顺序；还必须静态检查**每条原计算依赖**也阶段不回退、无未分类原计算 op、无额外跨流/跨核直接 op-op 边，并且加入两条 pipe FIFO 后全图仍是 DAG。缺少原边阶段检查时，可有 `S₀→P₁→A₂→P₂→A₃` 路径，其中三个跨核边依次是 `S₀→P₁`、`P₁→A₂`、`P₂→A₃`，`A₂→P₂` 为同流同核的阶段回退边。让 `A₂` 与 `P₂` 分属 M/V pipe 即可避免单 pipe FIFO 自动封住这个例子。若“单次共享前沿”已被实现为严格的全原边阶段检查，则此反例会被拒绝；仅凭文字中的跨流边型不能拒绝。

还应限定 `L0` 与 `Lδ` 取**同一增强 DAG**；原图 FIFO/owner 改变后不能把旧方案的 `L0` 代入。P3 实际在 `_build_scene_b_tasks` 建每核 Task 与跨核 COPY（`multicore_cut_evaluate_problem_3.py:69-74,189-215,217-241`），再在 `evaluate_problem_3` 加 COPY 外部前驱和 Cache/DDR 资源（同文件 `:307-349`）。所以该界不约束官方 Makespan，不能把 δ 简单当成 COPY 完整耗时。

## 2. 全支持容量证书：**按 Task 物理支持集收紧后成立；按“原计算 touched tensor”字面不成立**

Step2 对每个 Task 的**全部非 DDR tensor ID**从所有 op-tensor 边生成 lifecycle（`schedule_step2.py:39-67,109-129`）；先分配本步输出、暂不释放末次输入，然后检查超容才 spill（`:224-257`），因此若该 Task 每池所有会出现于 lifecycle 的不同物理 ID 大小总和 ≤ 对应容量，任一瞬间驻留量都是此全集的子集，Step2 无 spill。这也覆盖 alloc-before-free 瞬态。无 spill 时，Step2 不生成新的片上 incarnation（`:314-353`）。

“原计算 touched”必须在**P3 重建之后**转成上述全集：P3 每核建一个 Task，原 DDR tensor 的本地视图改为 UB（`multicore_cut_evaluate_problem_3.py:69-94,141-156`）；图输入、跨核 tensor 边和图输出会添 COPY 与 DDR backing（`:166-215`）；跨核直接 op-op 边另造一个新的 UB 桥 tensor（`:217-241`）。若只累计原图 tensor，这个桥不在集合里：例如原 UB touched 总量恰等于容量，另有一条正大小跨核直接边，P3 加桥后即超容。故 guard 要求无这种直接跨核边，或把桥也逐 Task/逐池计入。原图 COPY op 所接的本地片上 tensor、图输入/输出与每核副本也需计入；“compute”若仅指 M/V op，不能保证覆盖它们。DDR backing 不占 L1/UB，但原 DDR 视图改成的 UB 要计。每个 Task 及同名 logical tensor 的每份物理副本分别计，不能跨 Task 以 logical ID 去重。当前固定配置为 `L1=524288, UB=131072` B（`data/raw/a/official/data/config.txt`）；R8 报的静态数值仍需按此映射独立核对。

Step3 的无 `MEMORY_REUSE` 结论还需要：每个片上物理 ID 在本 Task 最多分配一次（唯一 producer，且不由重复写/再生导致二次分配），Step2 确实无 spill，以及总支持集覆盖 Step3 管理的全部会分配 ID。Step3 先把无 producer 的已消费 tensor 作为初始驻留（`schedule_step3.py:217-230`），把剩余容量作为队首 `VIRGIN` credit（`:231-237`）；释放的 WAR/WAW credit 只追加队尾（`:144-156`），分配从队首取，只有取到带 source 的 credit 才记录依赖（`:158-178`）。在“所有物理 ID 首次分配大小总和 ≤ 容量”下，初始 `VIRGIN` 足以覆盖其余 ID 的全部首次分配，所以不会读到回收 credit；`memory_dependencies` 为空，因而不会添 `MEMORY_REUSE` 边（`:583-609`）。若仅以同 logical ID 去重，或 spill 产生多个 incarnation，这一推论失效。Step3 本身以 `tid`/`pos` 管理容量，不按 logical ID 合并（`:124-133,185-215`）。

## 下一最小零 E0 guard

1. 对每条原计算边与 M/V FIFO 边核对阶段不下降；校验全部原 op/边只落入四阶段和准许的跨流类型、S 分量及每条私有流 owner 一致、计算增强图无环。用同一图独立计算最长路与逐路径跨核边上界。
2. 只运行 P3 的 Task 构造前静态映射或等价纯构造检查：逐 Task 枚举**实际**本地非 DDR tensor ID、池与大小，包括 UB 桥、原 DDR→UB、本地 COPY 端点；按 ID 去重求和并核对容量。不得把 `logical_tid` 当物理去重键。
3. 核对每个被分配 ID 唯一 producer/一次分配，且无 Step2 spill/重命名；若以后做正式验证，再比对 `spill_records`、`memory_dependencies` 和准备后的 Task tensor 清单。静态 guard 通过仅支持进入有界机制验证，不代表官方 Makespan 改善。
