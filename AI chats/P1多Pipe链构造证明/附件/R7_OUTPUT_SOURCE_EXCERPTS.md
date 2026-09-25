# 附件源码定位

原件来自本轮 ZIP，字节已按MANIFEST核对。下面是读取摘录，不是修改或执行源码。

## official/multicore_cut_evaluate_problem_1.py
```text
68:     return total
69: 
70: def _build_scene_a_tasks(graph_json, plan, bandwidth, capacity):
71:     """将每个子图封装为独立 Task，并为所有 Task 边界插入 DDR COPY。
72: 
73:     输入：原图/方案来自选手，故derive_multicore_plan负责入口校验；参数
74:     已由evaluate_scene_a校验。串行Task顺序是新增约束，需合并检查环。
75:     输出给Step1的局部图只保留原依赖、插入源/汇COPY，仍为DAG。
76:     """
77:     plan_view = derive_multicore_plan(graph_json, plan)
78:     validate_task_order(plan_view)
79:     op_by_id = {op['id']: op for op in graph_json['ops']}
80:     tensor_by_id = {tensor['id']: tensor for tensor in graph_json['tensors']}
81:     mapping = plan_view['mapping']
82:     producers, consumers, direct_edges = _original_tensor_views(graph_json)
83:     core_by_task = plan_view['core_by_subgraph']
84:     pred_tasks = plan_view['subgraph_preds']
85: 
86:     next_op_id = max([op['id'] for op in graph_json['ops']] + [0]) + 1
87:     next_tensor_id = max(
88:         [tensor['id'] for tensor in graph_json['tensors']] + [10000]) + 1
89:     used_ids = set(op_by_id) | set(tensor_by_id)
90: 
91:     def new_boundary_ids():
92:         # 原图两类ID已唯一；新ID同时避开两类已占用空间，不能只取各自max。
93:         nonlocal next_op_id, next_tensor_id
94:         while next_tensor_id in used_ids:
95:             next_tensor_id += 1
96:         ddr_id = next_tensor_id
97:         used_ids.add(ddr_id)
98:         next_tensor_id += 1
99:         while next_op_id in used_ids:
100:             next_op_id += 1
101:         copy_id = next_op_id
102:         used_ids.add(copy_id)
103:         next_op_id += 1
104:         return ddr_id, copy_id
105:     tasks = {}
106:     cross_task_traffic = 0
107:     task_graph_copy_traffic = 0
108:     spill_copy_traffic = 0
109: 
110:     for task_id in plan_view['subgraph_ids']:
111:         task_op_ids = set(plan_view['nodes_by_subgraph'][task_id])
112:         ops = [dict(op_by_id[op_id]) for op_id in sorted(task_op_ids)]
113:         tensors, edges = [], []
114:         local_tensor_ids = set()
115: 
116:         touched_tensors = sorted(
117:             tensor_id for tensor_id in tensor_by_id
118:             if producers.get(tensor_id, set()) & task_op_ids
119:             or consumers.get(tensor_id, set()) & task_op_ids)
120:         for tensor_id in touched_tensors:
121:             tensor = dict(tensor_by_id[tensor_id])
122:             local_producers = producers.get(tensor_id, set()) & task_op_ids
123:             local_consumers = consumers.get(tensor_id, set()) & task_op_ids
124:             eligible_producers = {op for op in producers.get(tensor_id, ()) if op in mapping}
125:             eligible_consumers = {op for op in consumers.get(tensor_id, ()) if op in mapping}
126:             has_original_copy_out = any(
127:                 op_by_id[op_id].get('op') == 'COPY_OUT'
128:                 for op_id in consumers.get(tensor_id, ())
129:                 if op_id in op_by_id)
130:             input_boundary = bool(local_consumers) and not bool(local_producers)
131:             output_boundary = bool(local_producers) and (
132:                 has_original_copy_out or not eligible_consumers
133:                 or bool(eligible_consumers - task_op_ids))
134: 
135:             # Task 内 Tensor 必须在私有缓存；原 DDR Tensor 仅作为边界副本。
136:             if tensor.get('pos') == 'DDR':
137:                 tensor['pos'] = 'UB'
138:             tensors.append(tensor)
139:             local_tensor_ids.add(tensor_id)
140:             for producer_id in sorted(local_producers):
141:                 edges.append({'source': producer_id, 'target': tensor_id})
142:             for consumer_id in sorted(local_consumers):
143:                 edges.append({'source': tensor_id, 'target': consumer_id})
144: 
145:             if input_boundary:
146:                 ddr_id, copy_id = new_boundary_ids()
147:                 tensors.append({'id': ddr_id, 'pos': 'DDR', 'size': tensor['size']})
148:                 ops.append({'id': copy_id, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2',
149:                             'cycles': max(1, math.ceil(tensor['size'] / bandwidth))})
150:                 edges.extend([
151:                     {'source': ddr_id, 'target': copy_id},
152:                     {'source': copy_id, 'target': tensor_id},
153:                 ])
154:             if output_boundary:
155:                 ddr_id, copy_id = new_boundary_ids()
156:                 tensors.append({'id': ddr_id, 'pos': 'DDR', 'size': tensor['size']})
157:                 ops.append({'id': copy_id, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3',
158:                             'cycles': max(1, math.ceil(tensor['size'] / bandwidth))})
159:                 edges.extend([
160:                     {'source': tensor_id, 'target': copy_id},
161:                     {'source': copy_id, 'target': ddr_id},
162:                 ])
163:                 remote_consumer_tasks = {
164:                     mapping[op_id] for op_id in eligible_consumers
165:                     if mapping[op_id] != task_id
166:                 }
167:                 cross_task_traffic += tensor['size'] * len(remote_consumer_tasks)
168: 
169:         for edge in direct_edges:
170:             if edge['source'] in task_op_ids and edge['target'] in task_op_ids:
171:                 edges.append(dict(edge))
172: 
173:         graph = {'ops': ops, 'tensors': tensors, 'edges': edges}
174:         task_graph_copy_traffic += _copy_traffic_bytes(graph)
175:         seq = step1_schedule(graph)
176:         result2 = step2_spill_insertion(graph, seq, capacity=capacity)
177:         spill_copy_traffic += sum(
178:             spill['size'] * (1 + int(spill['spill_out_copies_data']))
179:             for spill in result2['spill_records'])
180:         ext_graph = _build_extended_graph(graph, result2)
181:         prepared = prepare_step3_execution(
182:             ext_graph, capacity=capacity, bandwidth=bandwidth)
183:         prepared.update({
184:             'task_id': task_id,
185:             'core_id': core_by_task[task_id],
186:             'pred_tasks': pred_tasks[task_id],
187:         })
188:         tasks[task_id] = prepared
189:     original_copy_traffic = _copy_traffic_bytes(graph_json)
190:     partition_added_traffic = task_graph_copy_traffic - original_copy_traffic
191:     traffic = {
192:         'original_graph_copy_bytes': original_copy_traffic,
193:         'scheduled_copy_bytes': task_graph_copy_traffic + spill_copy_traffic,
194:         'added_copy_bytes': partition_added_traffic + spill_copy_traffic,
195:         'partition_added_copy_bytes': partition_added_traffic,
196:         'spill_added_copy_bytes': spill_copy_traffic,
197:     }
198:     return tasks, cross_task_traffic, traffic, plan_view
199: 
```
```text
314:         task['pipe_cursor'][pipe] += 1
315:         if cursor + 1 < len(order):
316:             queue_if_ready(task_id, order[cursor + 1])
317: 
318:     def task_release_time(task_id):
319:         task = tasks[task_id]
320:         core_id = task['core_id']
321:         if any(task_status[pred] != 'done' for pred in task['pred_tasks']):
322:             return None
323:         release = 0
324:         if core_previous_end[core_id] is not None:
325:             release = core_previous_end[core_id] + same_core_wait
326:         for pred in task['pred_tasks']:
327:             if tasks[pred]['core_id'] != core_id:
328:                 release = max(release, task_end[pred] + cross_core_wait)
329:         return release
330: 
331:     def activate_ready_tasks(now):
332:         changed = False
333:         for core_id in range(num_cores):
334:             if core_active_task[core_id] is not None:
335:                 continue
336:             order = core_orders.get(core_id, [])
337:             if core_index[core_id] >= len(order):
338:                 continue
339:             task_id = order[core_index[core_id]]
340:             release = task_release_time(task_id)
```
```text
382:         issued_in_pass = True
383:         while issued_in_pass:
384:             issued_in_pass = False
385:             for core_id in range(num_cores):
386:                 for pipe in PIPES:
387:                     executor_key = (core_id, pipe)
388:                     queue = issue_queues[executor_key]
389:                     while len(executors[executor_key]) < PIPE_SLOTS:
390:                         if not queue:
391:                             break
392:                         _, item = heapq.heappop(queue)
393:                         issued_in_pass = True
394:                         task_id, op_id = item
395:                         task = tasks[task_id]
396:                         op = task['op_by_id'][op_id]
397:                         duration = _op_duration(
398:                             op, task['in_tids'], task['out_tids'],
399:                             task['tensor_by_id'], bandwidth)
400:                         op_status[item] = 'running'
401:                         op_start[item] = now
402:                         op_end[item] = now + duration
403:                         executors[executor_key].append((item, op_end[item]))
404:                         if _uses_ddr_bandwidth(
405:                                 op, task['in_tids'], task['out_tids'],
406:                                 task['tensor_by_id']):
407:                             advance_ddr_work(now)
408:                             ddr_remaining_work[item] = float(duration)
409:                             projected = reschedule_ddr(now)
410:                             ddr_contention_log.append({
```
```text
463:             if tasks[task_id]['core_id'] != core_id:
464:                 continue
465:             op = tasks[task_id]['op_by_id'][op_id]
466:             op_entries.append({
467:                 'task_id': task_id, 'op_id': op_id, 'op': op['op'],
468:                 'pipe': op_pipe(op),
469:                 'start': start, 'end': op_end[item],
470:                 'duration': op_end[item] - start,
471:             })
472:         op_entries.sort(key=lambda entry: (entry['start'], entry['task_id'], entry['op_id']))
473:         subgraph_entries = []
474:         for task_id in core_orders.get(core_id, []):
475:             subgraph_ops = [entry for entry in op_entries
476:                             if entry['task_id'] == task_id]
477:             if not subgraph_ops:
478:                 raise SceneAEvaluationError(
479:                     'subgraph {} has no scheduled op'.format(task_id))
480:             start = min(entry['start'] for entry in subgraph_ops)
481:             end = max(entry['end'] for entry in subgraph_ops)
482:             subgraph_entries.append({
483:                 'subgraph_id': task_id,
484:                 'start': start, 'end': end, 'duration': end - start,
485:             })
486:         per_core_timeline.append({
487:             'core_id': core_id, 'tasks': task_entries,
488:             'subgraphs': subgraph_entries, 'ops': op_entries})
489: 
```

## official/schedule_step2.py
```text
119:             continue
120:         if tid not in tensor_uses:
121:             continue
122:         uses = tensor_uses[tid]
123:         tensor_lifecycle[tid] = {
124:             'pos': pos,
125:             'size': t['size'],
126:             'uses': uses,
127:             'first': uses[0][0],
128:             'last': uses[-1][0],
129:         }
130: 
131:     # 把“每个 step 扫描所有 tensor lifecycle”改为一次性事件索引。
132:     # 按 tensor_lifecycle 的插入顺序建表，以保持原算法在同一 step 内的处理顺序。
133:     uses_at_step = [[] for _ in range(n)]
134:     for tid, info in tensor_lifecycle.items():
135:         for use_idx, (step, _) in enumerate(info['uses']):
136:             uses_at_step[step].append((tid, use_idx))
137: 
138:     # id 分配
139:     max_id = max(o['id'] for o in graph_json['ops'])
140:     max_tid = max((t['id'] for t in graph_json['tensors']), default=0)
141:     next_id = max(max_id, max_tid) + 1
142: 
143:     # 模拟状态
144:     # active[T][tid] = (next_use_step, used_count)
145:     # dict 同时提供 O(1) 查找/删除，并保留与原 list 一致的插入顺序。
146:     type_active = {T: {} for T in capacity}
147:     type_resid = {T: 0 for T in capacity}
148:     # pending_spills: list of (out_after_step, in_before_step, tid, T, size, prev_use_op, next_use_op)
149:     pending_spills = []
150:     spill_in_at_step = defaultdict(list)
151:     overflow_log = []
152:     debug_over_count = []
```
```text
240:                 active_item = type_active[T].get(tid)
241:                 if active_item is not None:
242:                     _, used_count = active_item
243:                     type_active[T][tid] = (new_nu, used_count + 1)
244:             # k=1 的 tensor 同时是 first use 和 last use：先 alloc 参与瞬态容量
245:             # 检查，执行完成后再释放。普通末次输入同理延迟到容量检查之后释放。
246:             if idx == len(uses) - 1:
247:                 release_after_execute.append((T, tid))
248: 
249:         # 1.5 alloc 后、execute/free 前统一 Belady SPILL。
250:         #     trigger_one_spill 会排除当前 op 使用的所有 tensor，因此只会换出当前
251:         #     op 不需要的驻留项。最终生成的 SPILL_OUT 锚定在 victim 上次 use 之后，
252:         #     在扩展序列中物理发生于当前 op 之前。
253:         for T, C in capacity.items():
254:             while get_resid(T) > C:
255:                 resid_now = get_resid(T)
256:                 overflow_log.append({'step': t, 'type': T, 'resid': resid_now, 'capacity': C})
257:                 result = trigger_one_spill(t, T, current_step_tids[T])
258:                 if result is None:
259:                     current_tids = sorted(current_step_tids[T].intersection(type_active[T]))
260:                     active_desc = sorted(
261:                         (tid, tensor_lifecycle[tid]['size'], nu)
262:                         for tid, (nu, _) in type_active[T].items()
263:                     )
264:                     message = (
265:                         '[STEP2 ERROR] no spill victim: step={step} op={op} type={type_} '
266:                         'alloc_resid={resid} capacity={capacity} current_tids={current} '
267:                         'active(tid,size,next_use)={active}'
268:                     ).format(
269:                         step=t, op=op, type_=T, resid=resid_now, capacity=C,
270:                         current=current_tids, active=active_desc,
271:                     )
272:                     emit_error(message)
273:                     raise Step2SchedulingError(message)
274: 
275:             # 这是当前 op 真正的 alloc 后峰值；此时输入和输出都仍然驻留。
276:             resid_after_alloc = get_resid(T)
277:             if resid_after_alloc > C:
278:                 # while 的后置断言，防止未来修改重新引入静默超限。
279:                 message = (
280:                     '[STEP2 ERROR] alloc peak still exceeds capacity after spill: '
281:                     'step={step} op={op} type={type_} resid={resid} capacity={capacity}'
282:                 ).format(step=t, op=op, type_=T, resid=resid_after_alloc, capacity=C)
283:                 emit_error(message)
284:                 raise Step2SchedulingError(message)
285: 
286:         # 2. 当前 op 执行完成后，释放本步末次使用的输入/输出。
287:         for T, tid in release_after_execute:
288:             if type_active[T].pop(tid, None) is not None:
289:                 type_resid[T] -= tensor_lifecycle[tid]['size']
290: 
291:     # 3. 构建重命名后的扩展图。
292:     # 每次 COPY_IN 产生一个新的片上 tensor incarnation；它本身就是一段物理
293:     # 驻留生命周期。release-only COPY_OUT 不再创建，真实 DDR 写回仍保留。
294:     new_ops_list = []
295:     new_tensors_list = []
296:     new_edges = []
297:     removed_edges = []
298:     spill_records = []
299: 
300:     # 收集 insert 点
301:     insert_after = defaultdict(list)  # step -> list of real spill_out
302:     insert_before = defaultdict(list)
303: 
304:     backing_by_tid = dict(original_copy_in_backing)
305:     backing_origin = {
306:         tid: 'original_copy_in' for tid in original_copy_in_backing
307:     }
308:     current_incarnation = {
309:         tid: tid for tid in tensor_lifecycle
310:     }
311:     incarnation_version = defaultdict(int)
312:     spill_records_by_tid = defaultdict(list)
313: 
314:     for sp in pending_spills:
315:         logical_tid = sp['tid']
316:         from_tid = current_incarnation[logical_tid]
317:         spill_out_copies_data = sp['tid'] not in backing_by_tid
318:         spill_out_id = None
319:         if spill_out_copies_data:
320:             spill_out_id = next_id
321:             next_id += 1
322:         spill_in_id = next_id
323:         next_id += 1
324:         if spill_out_copies_data:
325:             backing_tid = next_id
326:             next_id += 1
327:             backing_by_tid[sp['tid']] = backing_tid
```
```text
345:         next_id += 1
346:         current_incarnation[logical_tid] = to_tid
347:         new_tensors_list.append({
348:             'id': to_tid,
349:             'logical_tid': logical_tid,
350:             'version': incarnation_version[logical_tid],
351:             'pos': sp['pos'],
352:             'size': sp['size'],
353:         })
354: 
355:         if spill_out_copies_data:
356:             new_ops_list.append({
357:                 'id': spill_out_id,
358:                 'op': 'COPY_OUT',
359:                 'pipe': 'PIPE_MTE3',
360:                 'cycles': max(1, sp['size'] // 64),
361:                 'transfer_bytes': sp['size'],
362:                 'spill_logical_tid': logical_tid,
363:             })
364:         new_ops_list.append({
365:             'id': spill_in_id,
366:             'op': 'COPY_IN',
367:             'pipe': 'PIPE_MTE2',
368:             'cycles': max(1, sp['size'] // 64),
369:             'transfer_bytes': sp['size'],
370:             'spill_logical_tid': logical_tid,
371:         })
372: 
373:         # 数据边直接表达物理 incarnation 的生产与消费。COPY_OUT 也是 from_tid
374:         # 的一个消费者；Step3 的引用计数会等所有消费者结束后再释放 from_tid。
375:         if spill_out_copies_data:
376:             new_edges.append((from_tid, spill_out_id))
377:             new_edges.append((spill_out_id, backing_tid))
378:         new_edges.append((backing_tid, spill_in_id))
379:         new_edges.append((spill_in_id, to_tid))
380: 
381:         if spill_out_id is not None:
382:             insert_after[sp['out_after_step']].append(spill_out_id)
383:         insert_before[sp['in_before_step']].append(spill_in_id)
384: 
385:         record = {
386:             'spill_out_id': spill_out_id,
387:             'spill_in_id': spill_in_id,
388:             'swap_tid': backing_tid,
389:             'backing_tid': backing_tid,
390:             'backing_source': backing_source,
391:             'spill_out_copies_data': spill_out_copies_data,
392:             'tid': logical_tid,
393:             'logical_tid': logical_tid,
394:             'from_tid': from_tid,
395:             'to_tid': to_tid,
396:             'version': incarnation_version[logical_tid],
397:             'pos': sp['pos'],
398:             'size': sp['size'],
399:             'prev_use_op': sp['prev_use_op'],
400:             'next_use_op': sp['next_use_op'],
401:             'prev_use_step': sp['out_after_step'],
402:             'next_use_step': sp['in_before_step'],
403:         }
404:         spill_records.append(record)
405:         spill_records_by_tid[logical_tid].append(record)
406: 
407:     # 把每条 logical tensor -> consumer 边改接到该 consumer 所属的 incarnation。
408:     # producer -> 原始 tensor 边保持不变；COPY_IN -> renamed tensor 边已在上面加入。
409:     op_step = {op_id: step for step, op_id in enumerate(seq)}
410:     consumer_incarnation = {}
```

## official/schedule_step3.py
```text
130:     remaining_consumers = {
131:         tid: len(tensor_consumers.get(tid, ())) for tid in managed_tensors
132:     }
133:     resident_tensors = set()
134:     memory_used = {pos: 0 for pos in capacity}
135:     memory_peak = {pos: 0 for pos in capacity}
136:     memory_events = []
137:     # free_credits 是“可复用容量”，只有字节数和上一个 tensor 的同步来源，
138:     # 没有 offset。额度允许拆分/合并，因此等价于执行前可做一次无代价内存整理，
139:     # 不会引入地址碎片问题。
140:     free_credits = {pos: [] for pos in capacity}
141:     memory_dependency_parts = defaultdict(lambda: {
142:         'bytes': 0, 'tensor_ids': set(), 'kinds': set(), 'positions': set()})
143: 
144:     def add_free_credit(tid):
145:         tensor = tensor_by_id[tid]
146:         consumers = sorted(tensor_consumers.get(tid, ()))
147:         producers = sorted(tensor_producers.get(tid, ()))
148:         # 有读者时必须等全部读者结束（WAR）；无读者的死输出至少要等旧写完成
149:         # 才能复用同一额度（WAW）。
150:         sources = consumers if consumers else producers
151:         free_credits[tensor['pos']].append({
152:             'bytes': tensor['size'],
153:             'sources': tuple(sources),
154:             'tid': tid,
155:             'kind': 'WAR' if consumers else 'WAW',
156:         })
157: 
158:     def consume_free_credit(tid, producer_op):
159:         tensor = tensor_by_id[tid]
160:         pos = tensor['pos']
161:         remaining = tensor['size']
162:         credits = free_credits[pos]
163:         while remaining > 0 and credits:
164:             credit = credits[0]
165:             taken = min(remaining, credit['bytes'])
166:             if credit['sources']:
167:                 for source_op in credit['sources']:
168:                     if source_op == producer_op:
169:                         continue
170:                     part = memory_dependency_parts[(source_op, producer_op)]
171:                     part['bytes'] += taken
172:                     part['tensor_ids'].add(credit['tid'])
173:                     part['kinds'].add(credit['kind'])
174:                     part['positions'].add(pos)
175:             credit['bytes'] -= taken
176:             remaining -= taken
177:             if credit['bytes'] == 0:
178:                 credits.pop(0)
179:         if remaining:
180:             message = '[STEP3 ERROR] virtual capacity credits exhausted: tid={} missing={}'.format(
181:                 tid, remaining)
182:             emit_error(message)
183:             raise Step3SchedulingError(message)
184: 
185:     def allocate_tensor(tid, now, producer_op=None, kind='alloc'):
186:         if tid not in managed_tensors or tid in resident_tensors:
187:             return
188:         tensor = tensor_by_id[tid]
189:         pos, size = tensor['pos'], tensor['size']
190:         if producer_op is not None:
191:             consume_free_credit(tid, producer_op)
192:         memory_used[pos] += size
193:         resident_tensors.add(tid)
194:         memory_peak[pos] = max(memory_peak[pos], memory_used[pos])
195:         memory_events.append({
196:             'time': now, 'kind': kind, 'tid': tid,
197:             'logical_tid': tensor.get('logical_tid', tid),
198:             'pos': pos, 'size': size, 'op_id': producer_op,
199:             'used_after': memory_used[pos],
200:         })
201: 
202:     def release_tensor(tid, now, consumer_op=None):
203:         if tid not in resident_tensors:
204:             return
205:         tensor = tensor_by_id[tid]
206:         pos, size = tensor['pos'], tensor['size']
207:         resident_tensors.remove(tid)
208:         memory_used[pos] -= size
209:         add_free_credit(tid)
210:         memory_events.append({
211:             'time': now, 'kind': 'free', 'tid': tid,
212:             'logical_tid': tensor.get('logical_tid', tid),
213:             'pos': pos, 'size': size, 'op_id': consumer_op,
214:             'used_after': memory_used[pos],
215:         })
216: 
217:     # 没有片上 producer 的 tensor 视为图开始前已驻留。
218:     for tid in sorted(managed_tensors):
219:         if not tensor_producers.get(tid) and tensor_consumers.get(tid):
220:             allocate_tensor(tid, 0, kind='initial_alloc')
221:     initial_overflow = {
222:         pos: memory_used[pos] for pos in capacity
223:         if memory_used[pos] > capacity[pos]
224:     }
225:     if initial_overflow:
226:         message = (
227:             '[STEP3 ERROR] initial resident tensors exceed capacity: used={} capacity={}'
228:         ).format(initial_overflow, capacity)
229:         emit_error(message)
230:         raise Step3SchedulingError(message)
231:     for pos in capacity:
232:         unused = capacity[pos] - memory_used[pos]
233:         if unused:
234:             free_credits[pos].append({
235:                 'bytes': unused, 'sources': (), 'tid': None,
```
```text
280: 
281:     seq_pos = {op_id: i for i, op_id in enumerate(seq)}
282:     # seq_ext 是 Step2 已验证的确定性拓扑序。Step3 在每条 Pipe 上使用它的
283:     # 投影作为固定发射顺序；这样多核阶段加入跨核 COPY 等待后，仍与核内
284:     # 调度结果保持同序，不会因局部 ready 时刻不同而重新排列 Pipe。
285:     planned_pipe_orders = {pipe: [] for pipe in PIPES}
286:     for op_id in seq:
287:         planned_pipe_orders[op_pipe(op_by_id[op_id])].append(op_id)
288:     pipe_cursor = {pipe: 0 for pipe in PIPES}
289:     allocation_order = [
290:         op_id for op_id in seq
291:         if any(tid in managed_tensors for tid in out_tids[op_id])
292:     ]
293:     allocation_rank = {
294:         op_id: rank for rank, op_id in enumerate(allocation_order)
295:     }
296:     next_allocation_rank = 0
297:     op_status = {op_id: 'pending' for op_id in op_by_id}
298:     pred_remaining = {op_id: len(preds[op_id]) for op_id in op_by_id}
299:     op_start, op_end = {}, {}
300:     issue_queues = {pipe: [] for pipe in PIPES}
301:     allocation_ready = set()
302:     executors = {pipe: [] for pipe in PIPES}
303:     ddr_transfer = {
304:         op_id: _uses_ddr_bandwidth(op, in_tids, out_tids, tensor_by_id)
305:         for op_id, op in op_by_id.items()
306:     }
307: 
308:     # DDR 公平共享状态。remaining_work 的单位是“独占全部 DDR 带宽时还需多少 cycle”。
309:     # 新的第 n 个搬运加入后，既有搬运的带宽份额从 1/(n-1) 降为 1/n，
310:     # 对应剩余时间按 n/(n-1) 拉长。下面按 remaining_work 排序、逐次移除
311:     # 最早完成项，等价实现用户指定的递推，也自然支持未来多核的 2N 条 MTE pipe。
312:     ddr_remaining_work = {}
313:     ddr_last_update = 0.0
314:     ddr_contention_log = []
315: 
316:     def advance_ddr_work(now):
317:         nonlocal ddr_last_update
318:         elapsed = now - ddr_last_update
319:         # projected end 会向上取整到 cycle。若某搬运在一个 cycle 内部已经
320:         # 完成，则余下的分数时间应立即由其他搬运共享，不能让已完成项继续占带宽。
321:         while elapsed > 1e-9:
322:             active = [
323:                 op_id for op_id, work in ddr_remaining_work.items()
324:                 if work > 1e-9
325:             ]
326:             if not active:
327:                 break
```
```text
486:                     op_status[op_id] = 'running'
487:                     allocate_outputs(op_id, t_now)
488:                     duration = _op_duration(
489:                         op_by_id[op_id], in_tids, out_tids,
490:                         tensor_by_id, bandwidth)
491:                     op_start[op_id] = t_now
492:                     op_end[op_id] = t_now + duration
493:                     executors[pipe].append((op_id, op_end[op_id]))
494:                     if ddr_transfer[op_id]:
495:                         advance_ddr_work(t_now)
496:                         previous_count = len(ddr_remaining_work)
497:                         ddr_remaining_work[op_id] = float(duration)
498:                         active_count = len(ddr_remaining_work)
499:                         slowdown_factor = (
500:                             active_count / previous_count if previous_count else 1.0
501:                         )
502:                         projected, provisional, stages = reschedule_ddr_ends(t_now)
503:                         ddr_contention_log.append({
504:                             'time': t_now,
505:                             'issued_op': op_id,
506:                             'issue_order': len(ddr_contention_log) + 1,
507:                             'exclusive_end': t_now + duration,
508:                             'provisional_end': provisional[op_id],
509:                             'slowdown_factor': slowdown_factor,
510:                             'active_ops': sorted(ddr_remaining_work),
511:                             'stages': stages,
512:                             'projected_ends': {
513:                                 active_id: projected[active_id]
514:                                 for active_id in sorted(projected)
515:                             },
516:                         })
517: 
518:     def raise_deadlock(reason):
519:         status_count = Counter(op_status.values())
520:         queue_snapshot = {
521:             pipe: [op_id for _, op_id in sorted(queue)]
522:             for pipe, queue in issue_queues.items()
523:         }
524:         executor_snapshot = {
525:             pipe: sorted(running, key=lambda item: item[1])
526:             for pipe, running in executors.items()
527:         }
528:         lines = [
529:             '[STEP3 ERROR] scheduler deadlock: reason={} time={} iteration={} status={}'.format(
530:                 reason, t_now, iteration, dict(status_count)),
531:             'queues={}'.format(queue_snapshot),
532:             'executors={}'.format(executor_snapshot),
533:             'ddr_remaining_work={}'.format(dict(sorted(ddr_remaining_work.items()))),
534:             'memory_used={} capacity={} resident_tensors={}'.format(
535:                 memory_used, capacity, sorted(resident_tensors)),
536:             'allocation_front={} allocation_ready={}'.format(
537:                 allocation_order[next_allocation_rank]
538:                 if next_allocation_rank < len(allocation_order) else None,
539:                 sorted(allocation_ready)),
540:         ]
541:         for op_id in seq:
542:             if op_status[op_id] == 'done':
543:                 continue
544:             unresolved = sorted(
545:                 pred for pred in preds[op_id] if op_status.get(pred) != 'done')
```

## official/config.txt
```text
1: # 竞赛结果统一采用以下固定评估值，不得修改。
2: 
3: [capacity]
4: L1 524288
5: UB 131072
6: 
7: [bandwidth]
8: bandwidth 60
9: 
10: [multicore_scene_a]
11: task_cross_core_wait_cycles 1000
12: task_same_core_wait_cycles 100
13: 
14: [multicore_scene_b]
15: cross_core_copy_delay_cycles 500
16: 
17: [problem_3]
18: cache_capacity_bytes 1048576
19: cache_bandwidth_bytes_per_cycle 250
```

## analysis/shared_input_budget.py
```text
104: 
105: 
106: def _windows(nodes, view, budget, max_phases):
107:     """Metadata only: ordered subsets of one old Task, never combines old Tasks."""
108:     levels = defaultdict(list)
109:     for u in nodes:
110:         levels[view["depth"][u]].append(u)
111:     phases, current, inputs, current_bytes = [], [], set(), 0
112:     for _, level in sorted(levels.items()):
113:         needed = {t for u in level for t in view["reads"][u]}
114:         fresh_bytes = _size(needed - inputs, view)
115:         if current and inputs and fresh_bytes and current_bytes + fresh_bytes > budget:
116:             phases.append(current)
117:             current, inputs, current_bytes = [], set(), 0
118:             fresh_bytes = _size(needed, view)
119:         current.extend(level)
120:         inputs.update(needed)
121:         current_bytes += fresh_bytes
122:     if current:
123:         phases.append(current)
124:     limited = len(phases) > max_phases
125:     if limited:
126:         phases = [list(nodes)]
127:     return phases, limited
128: 
129: 
130: def _configuration(view, cores, budget, max_phases, bandwidth, same_wait):
131:     """Load/input metadata, not a submission plan; mirrors frozen base packing."""
132:     loads, counts = [Counter() for _ in range(cores)], [0] * cores
133:     grouped = [[] for _ in range(cores)]
134:     for nodes, work, _ in view["components"]:
135:         choices = []
```
```text
258:               activation_bytes=524288, max_phases=32):
259:     if type(cores) is not int or not 1 <= cores <= 5:
260:         raise ValueError("cores must be an integer in 1..5")
261:     for value in (input_budget_bytes, activation_bytes, max_phases):
262:         if type(value) is not int or value < 1:
263:             raise ValueError("Require positive integer construction budgets")
264:     view = _view(graph)
265:     external_bytes = _size(view["external"], view)
266:     info = dict(algorithm_id="q1-shared-input-budget", variant="active-core-then-local-windows",
267:                 requested_cores=cores, input_budget_bytes=input_budget_bytes,
268:                 activation_bytes=activation_bytes, max_phases=max_phases,
269:                 external_input_bytes=external_bytes, components=len(view["components"]),
270:                 scope="Static proxies are neither lower bounds, E0 predictions, nor capacity certificates")
271:     if len(view["components"]) < cores or external_bytes <= activation_bytes:
272:         result, base = bounded_construct(graph, cores)
273:         info.update(selected="bounded04", reason="not enough components or external inputs below activation",
274:                     active_cores=cores, configurations=[], base=base)
275:         return result, info
276:     bandwidth = read_bandwidth_config(CONFIG)
277:     waits = read_required_settings(CONFIG, "multicore_scene_a",
278:                                    ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"))
279:     configs = [_configuration(view, a, input_budget_bytes, max_phases, bandwidth,
280:                               waits["task_same_core_wait_cycles"]) for a in range(1, cores + 1)]
281:     chosen = min(configs, key=lambda x: (x["cost_proxy_cycles"], x["total_copy_proxy_bytes"], -x["active_cores"]))
282:     active = chosen["active_cores"]
283:     # Exactly once, with the selected a; original K-boundaries are not preserved.
284:     base_plan, base_info = bounded_construct(graph, active)
285:     result, details = _refine(base_plan, view, input_budget_bytes, max_phases, cores)
286:     after = derive_multicore_plan(graph, result)
287:     validate_task_order(after)
288:     actual_counts = [len(order) for order in result["core_schedules"][:active]]
289:     if actual_counts != chosen["task_counts_by_core"]:
290:         raise AssertionError("Static packing/window metadata drifted from selected bounded base")
291:     # Whole components remain on their selected core; all new dependencies are local.
292:     if any(after["core_by_subgraph"][a] != after["core_by_subgraph"][b]
293:            for a, b in after["dependency_pairs"]):
294:         raise AssertionError("Component-preserving windows introduced a remote dependency")
```
