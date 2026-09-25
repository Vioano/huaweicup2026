# 冻结源码关键摘录

仅为用户所给源码的带原始行号摘录；没有运行这些函数。全文件hash与实际阅读范围见SOURCE_AUDIT.md。

## `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`

原文件L51–L67
```python
0051  def _prioritize_task_seq(graph, raw_seq, op_subgraph, subgraph_order):
0052      """依照核内子图调度序分桶，桶内保留 Step1 顺序。
0053  
0054      Step1保证raw_seq覆盖完整且拓扑正确，稳定排序不改变覆盖。
0055      选手的子图顺序是新约束，可能破坏拓扑，故只检查重排后的依赖顺序。
0056      """
0057      rank = {subgraph_id: index
0058              for index, subgraph_id in enumerate(subgraph_order)}
0059      fallback = len(rank)
0060      seq = sorted(
0061          raw_seq,
0062          key=lambda op_id: rank.get(op_subgraph.get(op_id), fallback),
0063      )
0064      if not _check_topo(graph, seq):
0065          raise SceneBEvaluationError(
0066              'subgraph priority order violates an intra-core dependency')
0067      return seq
```

原文件L145–L215
```python
0145          eligible_consumers = sorted(op for op in consumers.get(tensor_id, ())
0146                                      if op in mapping)
0147          producer_cores = sorted({core_by_op[op] for op in eligible_producers})
0148          consumer_cores = sorted({core_by_op[op] for op in eligible_consumers})
0149          touched_cores = sorted(set(producer_cores) | set(consumer_cores))
0150          if not touched_cores:
0151              continue
0152          local_tensor = dict(tensor)
0153          if local_tensor.get('pos') == 'DDR':
0154              local_tensor['pos'] = 'UB'
0155          for core_id in touched_cores:
0156              _append_tensor(tasks_data[core_id], local_tensor)
0157              for op_id in eligible_producers:
0158                  if core_by_op[op_id] == core_id:
0159                      tasks_data[core_id]['edges'].append(
0160                          {'source': op_id, 'target': tensor_id})
0161              for op_id in eligible_consumers:
0162                  if core_by_op[op_id] == core_id:
0163                      tasks_data[core_id]['edges'].append(
0164                          {'source': tensor_id, 'target': op_id})
0165  
0166          # 图输入：每个消费核各自从 DDR 读入一次。
0167          if eligible_consumers and not eligible_producers:
0168              for dst_core in consumer_cores:
0169                  dst_ops = [op for op in eligible_consumers
0170                             if core_by_op[op] == dst_core]
0171                  dst_subgraph = min(
0172                      (mapping[op] for op in dst_ops),
0173                      key=lambda sg: core_orders[dst_core].index(sg))
0174                  add_copy_in(dst_core, tensor_id, tensor['size'], dst_subgraph)
0175  
0176          # 图输出：保留对 DDR 的最终写回。
0177          has_original_copy_out = any(
0178              op_by_id[op_id].get('op') == 'COPY_OUT'
0179              for op_id in consumers.get(tensor_id, ()) if op_id in op_by_id)
0180          if eligible_producers and (has_original_copy_out or not eligible_consumers):
0181              for src_core in producer_cores:
0182                  src_ops = [op for op in eligible_producers
0183                             if core_by_op[op] == src_core]
0184                  src_subgraph = max(
0185                      (mapping[op] for op in src_ops),
0186                      key=lambda sg: core_orders[src_core].index(sg))
0187                  add_copy_out(src_core, tensor_id, tensor['size'], src_subgraph)
0188  
0189          # 跨核 tensor：每个实际 source-core -> target-core 连接一对 COPY。
0190          for src_core in producer_cores:
0191              src_ops = [op for op in eligible_producers
0192                         if core_by_op[op] == src_core]
0193              src_subgraph = max(
0194                  (mapping[op] for op in src_ops),
0195                  key=lambda sg: core_orders[src_core].index(sg))
0196              for dst_core in consumer_cores:
0197                  if src_core == dst_core:
0198                      continue
0199                  dst_ops = [op for op in eligible_consumers
0200                             if core_by_op[op] == dst_core]
0201                  dst_subgraph = min(
0202                      (mapping[op] for op in dst_ops),
0203                      key=lambda sg: core_orders[dst_core].index(sg))
0204                  ddr_tid = new_id()
0205                  out_id, _ = add_copy_out(
0206                      src_core, tensor_id, tensor['size'], src_subgraph, ddr_tid)
0207                  in_id, _ = add_copy_in(
0208                      dst_core, tensor_id, tensor['size'], dst_subgraph, ddr_tid)
0209                  cross_links.append({
0210                      'tensor_id': tensor_id, 'size': tensor['size'],
0211                      'source_core': src_core, 'target_core': dst_core,
0212                      'source_copy_out_id': out_id,
0213                      'target_copy_in_id': in_id,
0214                  })
0215                  cross_task_traffic += tensor['size']
```

## `data/raw/a/official/code/schedule_step2.py`

原文件L224–L289
```python
0224          # 1. 处理本步 use 的 alloc / next_use 更新，但延迟 last-use free。
0225          #    物理语义必须是 alloc -> 容量检查/SPILL -> execute -> free；否则会漏掉
0226          #    “输出已经申请、末次输入尚未释放”的瞬态峰值。
0227          release_after_execute = []
0228          for tid, idx in uses_at_step[t]:
0229              info = tensor_lifecycle[tid]
0230              uses = info['uses']
0231              T = info['pos']
0232              if idx == 0:
0233                  # First use (producer) = 申请内存
0234                  next_nu = uses[1][0] if 1 < len(uses) else None
0235                  type_active[T][tid] = (next_nu, 1)
0236                  type_resid[T] += info['size']
0237              elif idx < len(uses) - 1:
0238                  # Mid use: update next_use。对已有 key 赋值不改变 dict 插入顺序。
0239                  new_nu = uses[idx + 1][0]
0240                  active_item = type_active[T].get(tid)
0241                  if active_item is not None:
0242                      _, used_count = active_item
0243                      type_active[T][tid] = (new_nu, used_count + 1)
0244              # k=1 的 tensor 同时是 first use 和 last use：先 alloc 参与瞬态容量
0245              # 检查，执行完成后再释放。普通末次输入同理延迟到容量检查之后释放。
0246              if idx == len(uses) - 1:
0247                  release_after_execute.append((T, tid))
0248  
0249          # 1.5 alloc 后、execute/free 前统一 Belady SPILL。
0250          #     trigger_one_spill 会排除当前 op 使用的所有 tensor，因此只会换出当前
0251          #     op 不需要的驻留项。最终生成的 SPILL_OUT 锚定在 victim 上次 use 之后，
0252          #     在扩展序列中物理发生于当前 op 之前。
0253          for T, C in capacity.items():
0254              while get_resid(T) > C:
0255                  resid_now = get_resid(T)
0256                  overflow_log.append({'step': t, 'type': T, 'resid': resid_now, 'capacity': C})
0257                  result = trigger_one_spill(t, T, current_step_tids[T])
0258                  if result is None:
0259                      current_tids = sorted(current_step_tids[T].intersection(type_active[T]))
0260                      active_desc = sorted(
0261                          (tid, tensor_lifecycle[tid]['size'], nu)
0262                          for tid, (nu, _) in type_active[T].items()
0263                      )
0264                      message = (
0265                          '[STEP2 ERROR] no spill victim: step={step} op={op} type={type_} '
0266                          'alloc_resid={resid} capacity={capacity} current_tids={current} '
0267                          'active(tid,size,next_use)={active}'
0268                      ).format(
0269                          step=t, op=op, type_=T, resid=resid_now, capacity=C,
0270                          current=current_tids, active=active_desc,
0271                      )
0272                      emit_error(message)
0273                      raise Step2SchedulingError(message)
0274  
0275              # 这是当前 op 真正的 alloc 后峰值；此时输入和输出都仍然驻留。
0276              resid_after_alloc = get_resid(T)
0277              if resid_after_alloc > C:
0278                  # while 的后置断言，防止未来修改重新引入静默超限。
0279                  message = (
0280                      '[STEP2 ERROR] alloc peak still exceeds capacity after spill: '
0281                      'step={step} op={op} type={type_} resid={resid} capacity={capacity}'
0282                  ).format(step=t, op=op, type_=T, resid=resid_after_alloc, capacity=C)
0283                  emit_error(message)
0284                  raise Step2SchedulingError(message)
0285  
0286          # 2. 当前 op 执行完成后，释放本步末次使用的输入/输出。
0287          for T, tid in release_after_execute:
0288              if type_active[T].pop(tid, None) is not None:
0289                  type_resid[T] -= tensor_lifecycle[tid]['size']
```

原文件L300–L355
```python
0300      # 收集 insert 点
0301      insert_after = defaultdict(list)  # step -> list of real spill_out
0302      insert_before = defaultdict(list)
0303  
0304      backing_by_tid = dict(original_copy_in_backing)
0305      backing_origin = {
0306          tid: 'original_copy_in' for tid in original_copy_in_backing
0307      }
0308      current_incarnation = {
0309          tid: tid for tid in tensor_lifecycle
0310      }
0311      incarnation_version = defaultdict(int)
0312      spill_records_by_tid = defaultdict(list)
0313  
0314      for sp in pending_spills:
0315          logical_tid = sp['tid']
0316          from_tid = current_incarnation[logical_tid]
0317          spill_out_copies_data = sp['tid'] not in backing_by_tid
0318          spill_out_id = None
0319          if spill_out_copies_data:
0320              spill_out_id = next_id
0321              next_id += 1
0322          spill_in_id = next_id
0323          next_id += 1
0324          if spill_out_copies_data:
0325              backing_tid = next_id
0326              next_id += 1
0327              backing_by_tid[sp['tid']] = backing_tid
0328              backing_origin[sp['tid']] = 'spill_out'
0329              new_tensors_list.append({
0330                  'id': backing_tid,
0331                  'pos': 'DDR',
0332                  'size': sp['size'],
0333              })
0334              backing_source = 'new_spill_out'
0335          else:
0336              backing_tid = backing_by_tid[sp['tid']]
0337              backing_source = (
0338                  'original_copy_in'
0339                  if backing_origin[sp['tid']] == 'original_copy_in'
0340                  else 'reused_spill_out'
0341              )
0342  
0343          incarnation_version[logical_tid] += 1
0344          to_tid = next_id
0345          next_id += 1
0346          current_incarnation[logical_tid] = to_tid
0347          new_tensors_list.append({
0348              'id': to_tid,
0349              'logical_tid': logical_tid,
0350              'version': incarnation_version[logical_tid],
0351              'pos': sp['pos'],
0352              'size': sp['size'],
0353          })
0354  
0355          if spill_out_copies_data:
```

原文件L407–L437
```python
0407      # 把每条 logical tensor -> consumer 边改接到该 consumer 所属的 incarnation。
0408      # producer -> 原始 tensor 边保持不变；COPY_IN -> renamed tensor 边已在上面加入。
0409      op_step = {op_id: step for step, op_id in enumerate(seq)}
0410      consumer_incarnation = {}
0411      for logical_tid, records in spill_records_by_tid.items():
0412          record_index = 0
0413          physical_tid = logical_tid
0414          for step, consumer_op in tensor_uses[logical_tid]:
0415              while (record_index < len(records)
0416                     and step >= records[record_index]['next_use_step']):
0417                  physical_tid = records[record_index]['to_tid']
0418                  record_index += 1
0419              consumer_incarnation[(logical_tid, consumer_op)] = physical_tid
0420      rewired_edges = []
0421      for edge in graph_json['edges']:
0422          src, dst = edge['source'], edge['target']
0423          replacement = None
0424          if src in spill_records_by_tid and dst in op_step:
0425              physical_tid = consumer_incarnation.get((src, dst), src)
0426              if physical_tid != src:
0427                  replacement = (physical_tid, dst)
0428          if replacement is None:
0429              rewired_edges.append(dict(edge))
0430          else:
0431              removed_edges.append((src, dst))
0432              rewired_edges.append({
0433                  **edge,
0434                  'source': replacement[0],
0435                  'target': replacement[1],
0436              })
0437  
```

## `data/raw/a/official/code/schedule_step3.py`

原文件L123–L180
```python
0123  
0124      # 每个重命名后的片上 tensor 就是一段物理驻留生命周期。输出 op 发射前
0125      # alloc，全部消费者完成后 free；真实 COPY_OUT 也是普通消费者。
0126      managed_tensors = {
0127          tid for tid, tensor in tensor_by_id.items()
0128          if tensor.get('pos') in capacity
0129      }
0130      remaining_consumers = {
0131          tid: len(tensor_consumers.get(tid, ())) for tid in managed_tensors
0132      }
0133      resident_tensors = set()
0134      memory_used = {pos: 0 for pos in capacity}
0135      memory_peak = {pos: 0 for pos in capacity}
0136      memory_events = []
0137      # free_credits 是“可复用容量”，只有字节数和上一个 tensor 的同步来源，
0138      # 没有 offset。额度允许拆分/合并，因此等价于执行前可做一次无代价内存整理，
0139      # 不会引入地址碎片问题。
0140      free_credits = {pos: [] for pos in capacity}
0141      memory_dependency_parts = defaultdict(lambda: {
0142          'bytes': 0, 'tensor_ids': set(), 'kinds': set(), 'positions': set()})
0143  
0144      def add_free_credit(tid):
0145          tensor = tensor_by_id[tid]
0146          consumers = sorted(tensor_consumers.get(tid, ()))
0147          producers = sorted(tensor_producers.get(tid, ()))
0148          # 有读者时必须等全部读者结束（WAR）；无读者的死输出至少要等旧写完成
0149          # 才能复用同一额度（WAW）。
0150          sources = consumers if consumers else producers
0151          free_credits[tensor['pos']].append({
0152              'bytes': tensor['size'],
0153              'sources': tuple(sources),
0154              'tid': tid,
0155              'kind': 'WAR' if consumers else 'WAW',
0156          })
0157  
0158      def consume_free_credit(tid, producer_op):
0159          tensor = tensor_by_id[tid]
0160          pos = tensor['pos']
0161          remaining = tensor['size']
0162          credits = free_credits[pos]
0163          while remaining > 0 and credits:
0164              credit = credits[0]
0165              taken = min(remaining, credit['bytes'])
0166              if credit['sources']:
0167                  for source_op in credit['sources']:
0168                      if source_op == producer_op:
0169                          continue
0170                      part = memory_dependency_parts[(source_op, producer_op)]
0171                      part['bytes'] += taken
0172                      part['tensor_ids'].add(credit['tid'])
0173                      part['kinds'].add(credit['kind'])
0174                      part['positions'].add(pos)
0175              credit['bytes'] -= taken
0176              remaining -= taken
0177              if credit['bytes'] == 0:
0178                  credits.pop(0)
0179          if remaining:
0180              message = '[STEP3 ERROR] virtual capacity credits exhausted: tid={} missing={}'.format(
```

原文件L280–L300
```python
0280  
0281      seq_pos = {op_id: i for i, op_id in enumerate(seq)}
0282      # seq_ext 是 Step2 已验证的确定性拓扑序。Step3 在每条 Pipe 上使用它的
0283      # 投影作为固定发射顺序；这样多核阶段加入跨核 COPY 等待后，仍与核内
0284      # 调度结果保持同序，不会因局部 ready 时刻不同而重新排列 Pipe。
0285      planned_pipe_orders = {pipe: [] for pipe in PIPES}
0286      for op_id in seq:
0287          planned_pipe_orders[op_pipe(op_by_id[op_id])].append(op_id)
0288      pipe_cursor = {pipe: 0 for pipe in PIPES}
0289      allocation_order = [
0290          op_id for op_id in seq
0291          if any(tid in managed_tensors for tid in out_tids[op_id])
0292      ]
0293      allocation_rank = {
0294          op_id: rank for rank, op_id in enumerate(allocation_order)
0295      }
0296      next_allocation_rank = 0
0297      op_status = {op_id: 'pending' for op_id in op_by_id}
0298      pred_remaining = {op_id: len(preds[op_id]) for op_id in op_by_id}
0299      op_start, op_end = {}, {}
0300      issue_queues = {pipe: [] for pipe in PIPES}
```

原文件L450–L495
```python
0450                          pred_remaining[succ_id] -= 1
0451                          queue_if_ready(succ_id)
0452                  else:
0453                      still_running.append((op_id, end))
0454              executors[pipe] = still_running
0455          if retired_ddr:
0456              reschedule_ddr_ends(t_now)
0457  
0458      def issue_step():
0459          nonlocal next_allocation_rank
0460          # 发射严格逐个处理。即使多个 op 的 t_now 相同，也先完成当前 op 的
0461          # 加入、临时 end 计算和全体 end 更新，再弹出下一个 op；不存在批量同时加入。
0462          issued_in_pass = True
0463          while issued_in_pass:
0464              issued_in_pass = False
0465              for pipe in PIPES:
0466                  while len(executors[pipe]) < PIPE_SLOTS:
0467                      # 所有片上 allocation 严格沿用 Step2 的 seq_ext 顺序；执行仍可
0468                      # 跨 pipe 重叠。这样不会让后序分支提前占满内存并形成资源死锁。
0469                      op_id = None
0470                      if next_allocation_rank < len(allocation_order):
0471                          candidate = allocation_order[next_allocation_rank]
0472                          candidate_pipe = op_pipe(op_by_id[candidate])
0473                          if (candidate in allocation_ready
0474                                  and candidate_pipe == pipe
0475                                  and can_allocate_outputs(candidate)):
0476                              allocation_ready.remove(candidate)
0477                              op_id = candidate
0478                      if op_id is None and issue_queues[pipe]:
0479                          _, op_id = heapq.heappop(issue_queues[pipe])
0480                      if op_id is None:
0481                          break
0482                      issued_in_pass = True
0483                      rank = allocation_rank.get(op_id)
0484                      if rank is not None:
0485                          next_allocation_rank += 1
0486                      op_status[op_id] = 'running'
0487                      allocate_outputs(op_id, t_now)
0488                      duration = _op_duration(
0489                          op_by_id[op_id], in_tids, out_tids,
0490                          tensor_by_id, bandwidth)
0491                      op_start[op_id] = t_now
0492                      op_end[op_id] = t_now + duration
0493                      executors[pipe].append((op_id, op_end[op_id]))
0494                      if ddr_transfer[op_id]:
0495                          advance_ddr_work(t_now)
```

原文件L579–L609
```python
0579      pipe_orders = {
0580          pipe: list(order) for pipe, order in planned_pipe_orders.items()
0581      }
0582  
0583      memory_dependencies = []
0584      for (source, target), part in sorted(memory_dependency_parts.items()):
0585          memory_dependencies.append({
0586              'source': source,
0587              'target': target,
0588              'kind': '+'.join(sorted(part['kinds'])),
0589              'positions': sorted(part['positions']),
0590              'reused_bytes': part['bytes'],
0591              'previous_tensor_ids': sorted(
0592                  tid for tid in part['tensor_ids'] if tid is not None),
0593          })
0594  
0595      # 多核模拟只认图依赖。把虚拟额度复用关系写成直接 op->op 边，并保留
0596      # metadata 便于复核；_build_graph_views 会与普通数据依赖统一解析。
0597      execution_graph = deepcopy(ext_graph)
0598      existing_edges = {
0599          (edge['source'], edge['target']) for edge in execution_graph['edges']
0600      }
0601      for dep in memory_dependencies:
0602          pair = (dep['source'], dep['target'])
0603          if pair in existing_edges:
0604              continue
0605          execution_graph['edges'].append({
0606              'source': dep['source'], 'target': dep['target'],
0607              'dependency': 'MEMORY_REUSE',
0608          })
0609          existing_edges.add(pair)
```

原文件L675–L703
```python
0675  def prepare_step3_execution(ext_graph, capacity, bandwidth):
0676      """运行 Step3，并返回多核评估器可直接装载的 Task 描述。
0677  
0678      多核阶段可以改变操作的绝对开始/结束时间，但必须保持这里给出的每条
0679      Pipe 顺序，并把 execution_graph 中的内存复用边当作普通完成依赖。
0680      输入约束及来源同step3_simulation；返回值直接引用其已验证的图和
0681      Pipe顺序，不做二次覆盖/局部DAG校验。跨核COPY引入的新环由评估入口检查。
0682      容量与带宽由调用方从 config.txt 读出后传入。
0683      """
0684      result = step3_simulation(
0685          ext_graph, capacity=capacity, bandwidth=bandwidth)
0686      graph = result['execution_graph']
0687      in_tids, out_tids, op_preds, op_succs = _build_graph_views(
0688          graph['ops'], graph['edges'])
0689      return {
0690          'graph': graph,
0691          'seq': graph['seq_ext'],
0692          'seq_pos': {op_id: index
0693                      for index, op_id in enumerate(graph['seq_ext'])},
0694          'op_by_id': {op['id']: op for op in graph['ops']},
0695          'tensor_by_id': {tensor['id']: tensor for tensor in graph['tensors']},
0696          'in_tids': in_tids,
0697          'out_tids': out_tids,
0698          'op_preds': op_preds,
0699          'op_succs': op_succs,
0700          'pipe_ops': {pipe: list(order)
0701                       for pipe, order in result['pipe_orders'].items()},
0702          'step3': result,
0703      }
```

## `src/q3/query_flow_probe.py`

原文件L105–L135
```python
0105              actual = [u for u in task['pipe_ops'].get(pipe, []) if u in original]
0106              if actual != expected:
0107                  raise ValueError(f'core {c} original pipe sequence differs: {pipe}')
0108          found = {tid: (t['pos'], t['size']) for tid, t in task['tensor_by_id'].items()
0109                   if t['pos'] != 'DDR'}
0110          expected = {tid: ('UB' if tensors[tid]['pos'] == 'DDR' else tensors[tid]['pos'],
0111                            tensors[tid]['size']) for tid in touched[c]}
0112          if found != expected:
0113              raise ValueError(f'core {c} local tensor ID/position/size differs')
0114          if task['step3']['memory_dependencies']:
0115              raise ValueError(f'core {c} Step3 memory dependencies present')
0116          for bank in ('L1', 'UB'):
0117              if sum(size for pos, size in found.values() if pos == bank) > captured['capacity'][bank]:
0118                  raise ValueError(f'core {c} {bank} static capacity exceeded')
0119          producer = {}
0120          ids = set(task['op_by_id'])
0121          for edge in task['graph']['edges']:
0122              if edge['target'] in task['tensor_by_id'] and edge['source'] in ids:
0123                  producer.setdefault(edge['target'], set()).add(edge['source'])
0124          if any(len(producer.get(tid, ())) != 1 for tid in found):
0125              raise ValueError(f'core {c} local tensor producer is not unique')
0126      if len(observed_original) != len(mapping) or set(observed_original) != set(mapping):
0127          raise ValueError('all-core original operation coverage differs')
0128      raw_copy = copy_bytes(graph)
0129      task_copy = sum(copy_bytes(t['graph']) for t in tasks.values())
0130      if (raw_copy != traffic['original_graph_copy_bytes']
0131              or expected_task_copy != task_copy
0132              or task_copy != traffic['scheduled_copy_bytes']
0133              or task_copy - raw_copy != traffic['added_copy_bytes']):
0134          raise ValueError('independent COPY byte accounting differs')
0135      return {'original_copy_bytes': raw_copy, 'scheduled_copy_bytes': task_copy,
```
