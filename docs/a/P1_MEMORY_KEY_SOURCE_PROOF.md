# 内存释放词缓存：源码充分条件审查

2026-09-25。来源：已归档 Pro R4 的 `reuse_prekey.py` 提议；本文补充本机对冻结官方编译路径的审查。它不是新算法成绩，也不宣布全部 P1 最优。

## 命题与范围

在同一进程、相同官方源码和 helper 字节、相同实际容量/带宽及 Pipe 配置下，考虑两个由官方 `_build_scene_a_tasks` 构造的 Task。要求原图合法、无原始 spill，管理 tensor 有唯一 producer，compute 成员和边界描述确实由 `Family.prekey` 完整表示。原始 tensor 附带的跟踪元数据不参加评分。定义

`K = (scope, Family.prekey(members), release_word(members))`。

`release_word` 按 compute ID 递增枚举操作，将该操作输入、输出的 **实际列表** 分别按官方 `set(list)` 的遍历顺序转换为 touched-tensor 的相对名次。只有已知实际列表等于原图关联 tensor ID 的递增列表时，才可用 `set(sorted(original_incidence))` 计算；不能把任意重新投影后的列表当作它。

若 K 相同，且代表 Task 的 Step2 成功且无 spill，则下述源码归纳给出两 Task 的 Step1 序列、无 spill 的 Step2 序列以及 Step3 FIFO/完整数据和 MEM 前驱的有序同构。因此 `PortOp` 的归一化签名相同。该结论不要求所有 tensor 大小之和小于容量。

这是一项限定路径的源码证明审查。独立复核和针对性反例检查仍应在启用生产缓存前完成；当前实现保守地在编译后检查实际关联列表，尚不能借此减少 Task 编译次数。

## 1. 全图与投影图的边界 ID

官方场景 A 构造器按 touched-tensor ID 递增顺序追加 tensor，并按其局部 producer/consumer 递增顺序生成关联边。每个 tensor 先处理 COPY_IN，再处理 COPY_OUT。prekey 已包含归一化内存位置、大小、局部生产/消费关系、两种边界标记、compute 类型/Pipe/cycles 及直接操作边。

合成 COPY 的全局 ID 初值大于全部原始操作 ID，之后只递增；与 tensor ID 冲突只会跳过数值，不改变 COPY 生成顺序。因此对应两 Task 内存在保持完整操作 ID 顺序的映射：compute 按名次对应，所有 COPY 排在 compute 后，再按相同边界生成顺序对应。其他 Task 先消耗了多少 ID 只改变间隙。

合成 DDR backing 每个仅连到其单个 COPY，不是管理内存；其绝对 ID 及其与原 tensor ID 的交错不参与信用释放队列。COPY 的管理端点只有一个，故不会引入未被释放词描述的多 tensor set 顺序。compute 的实际关联列表由 touched-tensor 的递增外层循环保证为递增列表（合法图的关联不重复）。

依据：`multicore_cut_evaluate_problem_1.py:86–172`。此论证针对官方边界构造器；人为修改 COPY 图、改变容量或允许 spill incarnation 后不能直接延用。

## 2. Step1 和首次 spill 之前的 Step2

Step1 的深度由图决定；DFS 前驱和起点均按 `(COPY 标志, depth, -op_id)` 排序再压栈。完整操作 ID 顺序同构保留这些比较，得到相同的序列名次。邻接 set 的枚举顺序不会绕过后续排序。

Step2 的管理 tensor 生命周期按 Task tensor 插入顺序登记；DDR backing 被跳过，剩余次序就是原 tensor 递增次序。使用位置、uses_at_step、active 插入次序、分配与释放大小因而逐步相同。假设某一侧先发生首次溢出，此前状态对应，所以另一侧同一时刻也溢出，矛盾于代表 Task 无 spill。故无 spill 成功性传递；无需证明 spill ID 的重命名等价。无 spill 时 seq_ext 和管理 tensor ID 不变。

依据：`schedule_step1.py:109–181`；`schedule_step2.py:43–67, 120–151, 203–286`。诊断文本或原始 trace 的绝对 ID 不要求逐字相同。

## 3. Step3 的事件与信用队列归纳

以“事件时间、各 Pipe 游标与在飞操作、前驱计数、allocation 游标、驻留集合、剩余消费者数、各位置 FIFO 信用列表及来源”为对应状态。

- 输出分配按 tensor ID 排序；分配总量的无序 set 仅进行整数加法和成员检查，不决定信用消费次序。
- compute 的输入释放和死输出释放按未排序 set；K 中的两个释放词恰好固定该顺序。边界 COPY 的管理端点只有一个。释放后信用按同序入队，分配按同序拆分、消费队首，产生对应的 MEM 来源。
- 退休按固定 Pipe/执行器顺序。后继 set 遍历只更新计数、向集合或以唯一 seq_pos 排序的 heap 入队，期间不发射操作；完成一次退休遍历后的状态与遍历次序无关。
- 发射按固定 Pipe 次序与 allocation 名次；DDR 加入、工作量更新和 `(work, op_id)` 排序的并列次序相同。固定运行时中，同一数值操作序列给出相同浮点分支和退休时刻。

初态对应；上述每一步保留对应状态。因而所有退休、分配和信用转移对应，最终执行图同构，归一化完整前驱签名相同。容量安全性另见 [信用链引理](P1_MEMORY_CREDIT_LEMMA.md)。

依据：`schedule_step3.py:145–212, 240–279, 285–305, 316–517`。这不是有理数响应与 E0 浮点模型的普遍等价证明；它只比较相同运行时内两次官方编译。

## 对研发的约束

1. cache scope 必须绑定实际容量/带宽；合成反例的 UB=80 不能冒充正式配置。
2. 不能只凭旧 prekey 命中，也不能把不同位置的 release_word 强行视为平移不变；同步组仍须满足真实的相同响应条件。
3. 先用本机已归档的两 Task 反例核对投影与原图编译结果。差异边可能冗余，签名差异不意味着 Makespan 差异。
4. 要减少编译次数，下一步需把实际关联和边界条件变为编译前可核的契约。当前编译后检查版只是证伪探针，不能宣称性能优化已经实现。
