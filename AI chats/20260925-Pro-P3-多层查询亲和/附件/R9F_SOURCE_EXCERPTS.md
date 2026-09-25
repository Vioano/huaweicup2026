# 固定提交已核字节的源码摘录

仅阅读，没有调用官方函数。Git blob身份见metadata.json。

## multicore_cut_evaluate_problem_3.py 原文件51–67行

```python
0051 def _prioritize_task_seq(graph, raw_seq, op_subgraph, subgraph_order):
0052     """依照核内子图调度序分桶，桶内保留 Step1 顺序。
0053 
0054     Step1保证raw_seq覆盖完整且拓扑正确，稳定排序不改变覆盖。
0055     选手的子图顺序是新约束，可能破坏拓扑，故只检查重排后的依赖顺序。
0056     """
0057     rank = {subgraph_id: index
0058             for index, subgraph_id in enumerate(subgraph_order)}
0059     fallback = len(rank)
0060     seq = sorted(
0061         raw_seq,
0062         key=lambda op_id: rank.get(op_subgraph.get(op_id), fallback),
0063     )
0064     if not _check_topo(graph, seq):
0065         raise SceneBEvaluationError(
0066             'subgraph priority order violates an intra-core dependency')
0067     return seq
```

## multicore_cut_evaluate_problem_3.py 原文件145–215行

```python
0145         eligible_consumers = sorted(op for op in consumers.get(tensor_id, ())
0146                                     if op in mapping)
0147         producer_cores = sorted({core_by_op[op] for op in eligible_producers})
0148         consumer_cores = sorted({core_by_op[op] for op in eligible_consumers})
0149         touched_cores = sorted(set(producer_cores) | set(consumer_cores))
0150         if not touched_cores:
0151             continue
0152         local_tensor = dict(tensor)
0153         if local_tensor.get('pos') == 'DDR':
0154             local_tensor['pos'] = 'UB'
0155         for core_id in touched_cores:
0156             _append_tensor(tasks_data[core_id], local_tensor)
0157             for op_id in eligible_producers:
0158                 if core_by_op[op_id] == core_id:
0159                     tasks_data[core_id]['edges'].append(
0160                         {'source': op_id, 'target': tensor_id})
0161             for op_id in eligible_consumers:
0162                 if core_by_op[op_id] == core_id:
0163                     tasks_data[core_id]['edges'].append(
0164                         {'source': tensor_id, 'target': op_id})
0165 
0166         # 图输入：每个消费核各自从 DDR 读入一次。
0167         if eligible_consumers and not eligible_producers:
0168             for dst_core in consumer_cores:
0169                 dst_ops = [op for op in eligible_consumers
0170                            if core_by_op[op] == dst_core]
0171                 dst_subgraph = min(
0172                     (mapping[op] for op in dst_ops),
0173                     key=lambda sg: core_orders[dst_core].index(sg))
0174                 add_copy_in(dst_core, tensor_id, tensor['size'], dst_subgraph)
0175 
0176         # 图输出：保留对 DDR 的最终写回。
0177         has_original_copy_out = any(
0178             op_by_id[op_id].get('op') == 'COPY_OUT'
0179             for op_id in consumers.get(tensor_id, ()) if op_id in op_by_id)
0180         if eligible_producers and (has_original_copy_out or not eligible_consumers):
0181             for src_core in producer_cores:
0182                 src_ops = [op for op in eligible_producers
0183                            if core_by_op[op] == src_core]
0184                 src_subgraph = max(
0185                     (mapping[op] for op in src_ops),
0186                     key=lambda sg: core_orders[src_core].index(sg))
0187                 add_copy_out(src_core, tensor_id, tensor['size'], src_subgraph)
0188 
0189         # 跨核 tensor：每个实际 source-core -> target-core 连接一对 COPY。
0190         for src_core in producer_cores:
0191             src_ops = [op for op in eligible_producers
0192                        if core_by_op[op] == src_core]
0193             src_subgraph = max(
0194                 (mapping[op] for op in src_ops),
0195                 key=lambda sg: core_orders[src_core].index(sg))
0196             for dst_core in consumer_cores:
0197                 if src_core == dst_core:
0198                     continue
0199                 dst_ops = [op for op in eligible_consumers
0200                            if core_by_op[op] == dst_core]
0201                 dst_subgraph = min(
0202                     (mapping[op] for op in dst_ops),
0203                     key=lambda sg: core_orders[dst_core].index(sg))
0204                 ddr_tid = new_id()
0205                 out_id, _ = add_copy_out(
0206                     src_core, tensor_id, tensor['size'], src_subgraph, ddr_tid)
0207                 in_id, _ = add_copy_in(
0208                     dst_core, tensor_id, tensor['size'], dst_subgraph, ddr_tid)
0209                 cross_links.append({
0210                     'tensor_id': tensor_id, 'size': tensor['size'],
0211                     'source_core': src_core, 'target_core': dst_core,
0212                     'source_copy_out_id': out_id,
0213                     'target_copy_in_id': in_id,
0214                 })
0215                 cross_task_traffic += tensor['size']
```

## schedule_step2.py 原文件224–289行

```python
0224         # 1. 处理本步 use 的 alloc / next_use 更新，但延迟 last-use free。
0225         #    物理语义必须是 alloc -> 容量检查/SPILL -> execute -> free；否则会漏掉
0226         #    “输出已经申请、末次输入尚未释放”的瞬态峰值。
0227         release_after_execute = []
0228         for tid, idx in uses_at_step[t]:
0229             info = tensor_lifecycle[tid]
0230             uses = info['uses']
0231             T = info['pos']
0232             if idx == 0:
0233                 # First use (producer) = 申请内存
0234                 next_nu = uses[1][0] if 1 < len(uses) else None
0235                 type_active[T][tid] = (next_nu, 1)
0236                 type_resid[T] += info['size']
0237             elif idx < len(uses) - 1:
0238                 # Mid use: update next_use。对已有 key 赋值不改变 dict 插入顺序。
0239                 new_nu = uses[idx + 1][0]
0240                 active_item = type_active[T].get(tid)
0241                 if active_item is not None:
0242                     _, used_count = active_item
0243                     type_active[T][tid] = (new_nu, used_count + 1)
0244             # k=1 的 tensor 同时是 first use 和 last use：先 alloc 参与瞬态容量
0245             # 检查，执行完成后再释放。普通末次输入同理延迟到容量检查之后释放。
0246             if idx == len(uses) - 1:
0247                 release_after_execute.append((T, tid))
0248 
0249         # 1.5 alloc 后、execute/free 前统一 Belady SPILL。
0250         #     trigger_one_spill 会排除当前 op 使用的所有 tensor，因此只会换出当前
0251         #     op 不需要的驻留项。最终生成的 SPILL_OUT 锚定在 victim 上次 use 之后，
0252         #     在扩展序列中物理发生于当前 op 之前。
0253         for T, C in capacity.items():
0254             while get_resid(T) > C:
0255                 resid_now = get_resid(T)
0256                 overflow_log.append({'step': t, 'type': T, 'resid': resid_now, 'capacity': C})
0257                 result = trigger_one_spill(t, T, current_step_tids[T])
0258                 if result is None:
0259                     current_tids = sorted(current_step_tids[T].intersection(type_active[T]))
0260                     active_desc = sorted(
0261                         (tid, tensor_lifecycle[tid]['size'], nu)
0262                         for tid, (nu, _) in type_active[T].items()
0263                     )
0264                     message = (
0265                         '[STEP2 ERROR] no spill victim: step={step} op={op} type={type_} '
0266                         'alloc_resid={resid} capacity={capacity} current_tids={current} '
0267                         'active(tid,size,next_use)={active}'
0268                     ).format(
0269                         step=t, op=op, type_=T, resid=resid_now, capacity=C,
0270                         current=current_tids, active=active_desc,
0271                     )
0272                     emit_error(message)
0273                     raise Step2SchedulingError(message)
0274 
0275             # 这是当前 op 真正的 alloc 后峰值；此时输入和输出都仍然驻留。
0276             resid_after_alloc = get_resid(T)
0277             if resid_after_alloc > C:
0278                 # while 的后置断言，防止未来修改重新引入静默超限。
0279                 message = (
0280                     '[STEP2 ERROR] alloc peak still exceeds capacity after spill: '
0281                     'step={step} op={op} type={type_} resid={resid} capacity={capacity}'
0282                 ).format(step=t, op=op, type_=T, resid=resid_after_alloc, capacity=C)
0283                 emit_error(message)
0284                 raise Step2SchedulingError(message)
0285 
0286         # 2. 当前 op 执行完成后，释放本步末次使用的输入/输出。
0287         for T, tid in release_after_execute:
0288             if type_active[T].pop(tid, None) is not None:
0289                 type_resid[T] -= tensor_lifecycle[tid]['size']
```

## schedule_step3.py 原文件125–178行

```python
0125     # alloc，全部消费者完成后 free；真实 COPY_OUT 也是普通消费者。
0126     managed_tensors = {
0127         tid for tid, tensor in tensor_by_id.items()
0128         if tensor.get('pos') in capacity
0129     }
0130     remaining_consumers = {
0131         tid: len(tensor_consumers.get(tid, ())) for tid in managed_tensors
0132     }
0133     resident_tensors = set()
0134     memory_used = {pos: 0 for pos in capacity}
0135     memory_peak = {pos: 0 for pos in capacity}
0136     memory_events = []
0137     # free_credits 是“可复用容量”，只有字节数和上一个 tensor 的同步来源，
0138     # 没有 offset。额度允许拆分/合并，因此等价于执行前可做一次无代价内存整理，
0139     # 不会引入地址碎片问题。
0140     free_credits = {pos: [] for pos in capacity}
0141     memory_dependency_parts = defaultdict(lambda: {
0142         'bytes': 0, 'tensor_ids': set(), 'kinds': set(), 'positions': set()})
0143 
0144     def add_free_credit(tid):
0145         tensor = tensor_by_id[tid]
0146         consumers = sorted(tensor_consumers.get(tid, ()))
0147         producers = sorted(tensor_producers.get(tid, ()))
0148         # 有读者时必须等全部读者结束（WAR）；无读者的死输出至少要等旧写完成
0149         # 才能复用同一额度（WAW）。
0150         sources = consumers if consumers else producers
0151         free_credits[tensor['pos']].append({
0152             'bytes': tensor['size'],
0153             'sources': tuple(sources),
0154             'tid': tid,
0155             'kind': 'WAR' if consumers else 'WAW',
0156         })
0157 
0158     def consume_free_credit(tid, producer_op):
0159         tensor = tensor_by_id[tid]
0160         pos = tensor['pos']
0161         remaining = tensor['size']
0162         credits = free_credits[pos]
0163         while remaining > 0 and credits:
0164             credit = credits[0]
0165             taken = min(remaining, credit['bytes'])
0166             if credit['sources']:
0167                 for source_op in credit['sources']:
0168                     if source_op == producer_op:
0169                         continue
0170                     part = memory_dependency_parts[(source_op, producer_op)]
0171                     part['bytes'] += taken
0172                     part['tensor_ids'].add(credit['tid'])
0173                     part['kinds'].add(credit['kind'])
0174                     part['positions'].add(pos)
0175             credit['bytes'] -= taken
0176             remaining -= taken
0177             if credit['bytes'] == 0:
0178                 credits.pop(0)
```

## schedule_step3.py 原文件285–296行

```python
0285     planned_pipe_orders = {pipe: [] for pipe in PIPES}
0286     for op_id in seq:
0287         planned_pipe_orders[op_pipe(op_by_id[op_id])].append(op_id)
0288     pipe_cursor = {pipe: 0 for pipe in PIPES}
0289     allocation_order = [
0290         op_id for op_id in seq
0291         if any(tid in managed_tensors for tid in out_tids[op_id])
0292     ]
0293     allocation_rank = {
0294         op_id: rank for rank, op_id in enumerate(allocation_order)
0295     }
0296     next_allocation_rank = 0
```

## schedule_step3.py 原文件459–489行

```python
0459         nonlocal next_allocation_rank
0460         # 发射严格逐个处理。即使多个 op 的 t_now 相同，也先完成当前 op 的
0461         # 加入、临时 end 计算和全体 end 更新，再弹出下一个 op；不存在批量同时加入。
0462         issued_in_pass = True
0463         while issued_in_pass:
0464             issued_in_pass = False
0465             for pipe in PIPES:
0466                 while len(executors[pipe]) < PIPE_SLOTS:
0467                     # 所有片上 allocation 严格沿用 Step2 的 seq_ext 顺序；执行仍可
0468                     # 跨 pipe 重叠。这样不会让后序分支提前占满内存并形成资源死锁。
0469                     op_id = None
0470                     if next_allocation_rank < len(allocation_order):
0471                         candidate = allocation_order[next_allocation_rank]
0472                         candidate_pipe = op_pipe(op_by_id[candidate])
0473                         if (candidate in allocation_ready
0474                                 and candidate_pipe == pipe
0475                                 and can_allocate_outputs(candidate)):
0476                             allocation_ready.remove(candidate)
0477                             op_id = candidate
0478                     if op_id is None and issue_queues[pipe]:
0479                         _, op_id = heapq.heappop(issue_queues[pipe])
0480                     if op_id is None:
0481                         break
0482                     issued_in_pass = True
0483                     rank = allocation_rank.get(op_id)
0484                     if rank is not None:
0485                         next_allocation_rank += 1
0486                     op_status[op_id] = 'running'
0487                     allocate_outputs(op_id, t_now)
0488                     duration = _op_duration(
0489                         op_by_id[op_id], in_tids, out_tids,
```

## schedule_step3.py 原文件591–611行

```python
0591             'previous_tensor_ids': sorted(
0592                 tid for tid in part['tensor_ids'] if tid is not None),
0593         })
0594 
0595     # 多核模拟只认图依赖。把虚拟额度复用关系写成直接 op->op 边，并保留
0596     # metadata 便于复核；_build_graph_views 会与普通数据依赖统一解析。
0597     execution_graph = deepcopy(ext_graph)
0598     existing_edges = {
0599         (edge['source'], edge['target']) for edge in execution_graph['edges']
0600     }
0601     for dep in memory_dependencies:
0602         pair = (dep['source'], dep['target'])
0603         if pair in existing_edges:
0604             continue
0605         execution_graph['edges'].append({
0606             'source': dep['source'], 'target': dep['target'],
0607             'dependency': 'MEMORY_REUSE',
0608         })
0609         existing_edges.add(pair)
0610 
0611     # 在把结果交给多核模拟前一次性验证契约。这里验证的是生成结果本身，
```

## multicore_cut_evaluate_problem_3.py 原文件690–716行

```python
0690         'bandwidth_bytes_per_cycle': bandwidth,
0691         'cache_capacity_bytes': cache_capacity_bytes,
0692         'cache_bandwidth_bytes_per_cycle': cache_bandwidth_bytes_per_cycle,
0693         'cache_stats': cache_stats,
0694         'cache_events': cache_events,
0695         'cache_final_entries': [
0696             {'tensor_id': cache_key, 'size_bytes': size}
0697             for cache_key, size in cache_entries.items()
0698         ],
0699         'cache_used_bytes_final': cache_used_bytes,
0700         'capacity_bytes': dict(capacity),
0701         'memory_peak_by_core': {
0702             core_id: dict(task['step3']['memory_peak'])
0703             for core_id, task in tasks.items()
0704         },
0705         'step3_by_core': {
0706             core_id: {
0707                 'local_makespan': task['step3']['makespan'],
0708                 'memory_dependency_count': len(
0709                     task['step3']['memory_dependencies']),
0710                 'pipe_op_counts': {
0711                     pipe: len(order) for pipe, order in task['pipe_ops'].items()
0712                 },
0713             }
0714             for core_id, task in tasks.items()
0715         },
0716         'cross_core_copy_delay_cycles': cross_core_copy_delay,
```
