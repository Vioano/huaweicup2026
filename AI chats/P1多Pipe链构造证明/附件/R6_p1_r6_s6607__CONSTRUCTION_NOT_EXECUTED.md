# 未执行构造规范：前驱闭合分支外援 + 独立汇合尾

这是一个确定的结构细化规则，不是已执行的新求解器。在线输入只有原图、核数、固定配置，以及**本次从原图构造**的基线分区/波次。不得读取本包旧result用于选切口。

## 输入域

- 基线来自 sink-exclusive 包及其向前波次；每核每波至多一个合并Task。
- 计算图同时保留 COPY 收缩的合法性图与直接非COPY数据依赖图。所选包内部若两图不一致，快路径拒绝。
- 所选包是连通、唯一sink的DAG；边界tensor均按原图检查。接受域采用唯一生产者。
- 只在有高于该波主导Pipe平均工作量的核、也有低于平均工作量的核时尝试。
- 原ID用于复核和确定性破同分，不修改ID。不按case、精确链数、精确节点数触发。

## 确定的选择规则

1. 对各包的无向计算图作桥分解，桥树以包sink所在块为根。树边上统计各Pipe子树工作量。
2. 找一个汇合点j，它的两个内部前驱边均为无向桥，因而各自上游是前驱闭合、彼此独立的完整DAG锥。分叉和内部归约保留在锥内。
3. 每个重核最多选一个j，优先最大化“两上游锥中较小的主导Pipe工作量”；同分取原j ID较小者。导出较小的上游锥；同大小取前驱ID较大者。另一个锥留本核。这样排除仅有一小标量支路的末端汇合，不逐参数试切。
4. 对被选原Task S，X为导出锥，J为j在所选包内的后继闭包，Y=S\(X∪J)。实际检查X/Y之间无边，J没有返回X/Y的边，X/Y的外部计算前驱都在更早原波。
5. 重核和外援核角色互斥。一波一次性处理所有选中重核，不能因其他并列重核尚未改变导致当前max不降，就逐个拒绝迁移。
6. 按导出锥的主导Pipe工作量降序，将其分给低负载核；每次选择增加锥后max-Pipe工作最小的外援核，再以总工作和核号破同分。
7. **整批**核工作向量的最大主导Pipe负载不下降，则拒绝本波细化。计算完整新增COPY、可用的Task资源下界和Task预算。它们用于拒绝及候选排序，不提供性能保证。可选严格拒绝：新边界服务已不小于当前输入上已验证上界，则不可能严格改善Makespan。
8. 每个重核执行Y再J；外援核先执行所分配的X Tasks，再执行自己原有的该波Task L。X不并入L，J不并入Y或任何早期工作。
9. 原波之间核序保持向前，但**不添加波间或微阶段间全局barrier**。J只等待自己的真实前驱及本核Y。
10. 所有合格波按同一规则一次性生成至多一个新候选。未经当前图完整编译/评分，不声称新FIFO、MEM、spill或时长与旧Task相同。

## 两键伪代码（本轮未执行）

```text
packets, waves, base_plan = BASE_FROM_THIS_INPUT(graph, K, config)
for wave in waves:
    workloads = raw_pipe_work(wave)
    donors, helpers = disjoint_above_below_mean_roles(workloads)
    for donor in donors:
        witness = ONE_BRIDGE_JOIN_WITNESS(donor, graph)
        if witness missing: skip donor
        X = source_side_of_selected_bridge
        J = descendants_of_join_within_packet
        Y = original_task_members - X - J
        verify local ideals, directions, original boundary predicates
        reserve at most one export for this donor
    assign exports to helpers once by pipe-vector greedy placement
    if no batch load improvement or budget failure: keep original wave
    otherwise:
        donor core: append Task(Y), Task(J)
        helper core: append each separate Task(X), then original Task(L)
        untouched core: append original Task
build node_to_subgraph from unchanged original compute op IDs
build core_schedules from the append order
check coverage and all actual task-data + adjacent-core-order edges by Kahn
return exactly {node_to_subgraph, core_schedules}
```

## 增广DAG证书

每个新Task赋证明秩 `(原波号, micro, 本核波内位置, 核号)`：早期Y、外援X和未拆L的micro为0，汇合J为1。原跨波边增加原波号；新增数据边只从X/Y到J；stage-0内部只有本核X队列到L的顺序边。全部边严格向前。micro是证明标签，不是提交字段或等待屏障。

唯一sink DAG中，指向sink一侧的无向桥的上游集合是前驱闭合的；所有上游节点必须经过该桥才到sink。J的后继闭包保证没有尾部返回边。若原图不满足这些检查，本规则拒绝，而不尝试用重新编号“修复”。

## 成本与复杂度

每拆一个S为X/Y/J，Task数净增2。每波最多K-1个donor，所以净增不超过2(K-1)。

按完整原图逐tensor核算新旧Task边界谓词；只有边界COPY差是精确静态量。新SPILL、实际DDR争用和MEM补边仍未知。

在已有计算邻接图与波次之后，桥分解和工作累计线性；每个选中汇合再扫描后继闭包与边界。增量可保守记O(K(n+m)+K²W)（确定性排序另计），K≤5。原二部图展开、COPY收缩和基线构造墙钟另计。审计脚本采用直接集合闭包验证特定见证，不是这个未执行的高效桥分解求解器。

## 失败边界

- 小计算锥仍需1000跨核门控，可能收益小于新增门控。
- 多Pipe原重叠可能因切分消失；max-Pipe负载不是Task时长。
- 原Task中的共享权重、K/V输入被多读，可能远大于单个导出tensor。
- 额外外部前驱或外援队列会让X迟到；即使数据图无环，也可能更慢。
- 新FIFO/MEM/SPILL必须由冻结编译器在原ID上生成；不移植旧时长，不用未证跨ID缓存。

研发阶段只比较当前输入的基线与这一个固定细化方案。若以后接入E1，以完整Makespan/字节字典序守卫；失败/超时回退基线、零重试。最多增加一次新候选评分，不在失败后扫描更多汇合点、外援位置或参数。
