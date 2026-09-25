"""Pure audit of a saved P3 Task/Step2/Step3 capture.

Default mode certifies singleton buckets. Explicit ``allow_multi=True`` checks
multi-compute buckets against actual prepared Task order and full local tensor
intervals; it does not extend the legacy raw direct-op-edge scope.

This module never imports or invokes the official evaluator. It accepts the
``captured`` dictionary saved by query_flow_probe (native or JSON-decoded),
and independently reconstructs the relevant graph and bucket invariants.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque


PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')
COPY = {'COPY_IN', 'COPY_OUT'}
_DEFAULT_CROSSING = object()


class PreparedGuardError(ValueError):
    """A falsified prepared invariant with a stable machine-readable code."""

    def __init__(self, code: str, **details):
        self.code = code
        self.details = details
        super().__init__(f'{code}: {details}')

    def as_dict(self):
        return {'status': 'failed', 'code': self.code, 'details': self.details}


def require(condition, code, **details):
    if not condition:
        raise PreparedGuardError(code, **details)


def ids(value):
    return {int(k): v for k, v in value.items()}


def _graph_ports(graph):
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    require(len(ops) == len(graph['ops']) and len(tensors) == len(graph['tensors'])
            and not (ops.keys() & tensors.keys()), 'graph_ids')
    producer = {}
    consumers = defaultdict(set)
    in_tids = defaultdict(set)
    out_tids = defaultdict(set)
    direct = set()
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in ops and b in tensors:
            require(b not in producer or producer[b] == a, 'multiple_producers', tid=b)
            producer[b] = a
            out_tids[a].add(b)
        elif a in tensors and b in ops:
            consumers[a].add(b)
            in_tids[b].add(a)
        elif a in ops and b in ops:
            direct.add((a, b, e.get('dependency')))
        else:
            raise PreparedGuardError('graph_edge_endpoint', source=a, target=b)
    return ops, tensors, producer, consumers, in_tids, out_tids, direct


def check_layered_prepared(graph, plan, captured, *, layers: int,
                           allow_multi: bool = False, crossing_limit=_DEFAULT_CROSSING):
    """Return a checked report or raise :class:`PreparedGuardError`.

    ``layers`` is the already established structural layer count. This guard
    verifies the prepared crossing limit against ``layers+1`` by default.
    ``crossing_limit=None`` reports the observed crossing without that bound.
    It does not re-recognize rows, certify a raw layer decomposition, or
    accept original direct op-op edges.
    """
    require(type(layers) is int and layers >= 0, 'invalid_layers', layers=layers)
    require(type(allow_multi) is bool, 'invalid_allow_multi')
    if crossing_limit is _DEFAULT_CROSSING:
        crossing_limit = layers + 1
    require(crossing_limit is None or (type(crossing_limit) is int and crossing_limit >= 0),
            'invalid_crossing_limit', crossing_limit=crossing_limit)
    require(set(plan) == {'node_to_subgraph', 'core_schedules'}, 'plan_fields')
    raw_ops, raw_tensors, raw_prod, raw_cons, _, raw_out, raw_direct = _graph_ports(graph)
    require(not raw_direct, 'raw_direct_edge')
    compute = {u for u, op in raw_ops.items() if op['op'] not in COPY}
    require(all(raw_out[u] for u in compute), 'compute_without_output')
    mapping = ids(plan['node_to_subgraph'])
    require(set(mapping) == compute and (allow_multi or len(set(mapping.values())) == len(mapping)),
            'compute_mapping' if allow_multi else 'singleton_mapping',
            expected=len(compute), actual=len(mapping))
    schedules = plan['core_schedules']
    require(isinstance(schedules, list) and schedules, 'core_schedules')
    flat = [sg for order in schedules for sg in order]
    require(len(flat) == len(set(flat)) == len(mapping.values() if not allow_multi else set(mapping.values()))
            and set(flat) == set(mapping.values()),
            'multi_schedule' if allow_multi else 'singleton_schedule',
            scheduled=len(flat), expected=len(set(mapping.values())))
    core_of_sg = {sg: c for c, order in enumerate(schedules) for sg in order}
    op_of_sg = {sg: u for u, sg in mapping.items()} if not allow_multi else None
    core_of = {u: core_of_sg[sg] for u, sg in mapping.items()}
    bucket = {u: (core_of[u], schedules[core_of[u]].index(mapping[u])) for u in compute}
    count_cores = len(schedules)

    # Raw tensor ends determine Task local copies, COPY count, and closed-frontier.
    touched = [set() for _ in schedules]
    expected_copies = Counter()
    expected_links = set()
    diff = [{p: [0] * (len(order) + 1) for p in ('L1', 'UB')} for order in schedules]
    original_copy_out_inputs = {tid for tid, users in raw_cons.items()
                                if any(raw_ops[u]['op'] == 'COPY_OUT' for u in users)}
    for tid, t in raw_tensors.items():
        src = raw_prod.get(tid)
        src_c = core_of.get(src)
        users = {u for u in raw_cons[tid] if u in compute}
        dst_cores = {core_of[u] for u in users}
        touch = defaultdict(list)
        if src_c is not None:
            touch[src_c].append(bucket[src][1])
        for u in users:
            touch[core_of[u]].append(bucket[u][1])
        pool = 'UB' if t['pos'] == 'DDR' else t['pos']
        require(pool in ('L1', 'UB') and type(t['size']) is int and t['size'] >= 0,
                'tensor_pool_size', tid=tid, pool=pool, size=t['size'])
        for c, points in touch.items():
            touched[c].add(tid)
            first, last = min(points), max(points)
            diff[c][pool][first] += t['size']
            diff[c][pool][last + 1] -= t['size']
        if users and src_c is None:
            for c in dst_cores:
                expected_copies[('COPY_IN', c, tid)] += 1
        if src_c is not None:
            if tid in original_copy_out_inputs or not users:
                expected_copies[('COPY_OUT', src_c, tid)] += 1
            for c in dst_cores - {src_c}:
                expected_copies[('COPY_OUT', src_c, tid)] += 1
                expected_copies[('COPY_IN', c, tid)] += 1
                expected_links.add((src_c, c, tid))

    require(set(captured) >= {'task_return', 'step2', 'capacity'}, 'capture_fields')
    task_return = captured['task_return']
    require(isinstance(task_return, (list, tuple)) and len(task_return) == 5,
            'task_return_shape')
    tasks_raw, links, _, traffic, _ = task_return
    tasks = ids(tasks_raw)
    steps = captured['step2']
    capacity = captured['capacity']
    require(set(tasks) == set(range(count_cores)) and len(steps) == count_cores,
            'task_core_coverage', cores=count_cores, tasks=sorted(tasks), steps=len(steps))
    require(set(capacity) == {'L1', 'UB'}, 'capacity_pools')
    peaks = []
    frontier_rows = [] if allow_multi else diff
    for c, row in enumerate(frontier_rows):
        result = {}
        for pool, deltas in row.items():
            amount = maximum = 0
            for delta in deltas[:-1]:
                amount += delta
                maximum = max(maximum, amount)
            result[pool] = maximum
            require(maximum <= capacity[pool], 'frontier_capacity', core=c,
                    pool=pool, peak=maximum, capacity=capacity[pool])
        peaks.append(result)

    closed_peaks = []
    nodes = set()
    edges = defaultdict(dict)
    edge_counts = Counter()
    observed_copies = Counter()
    copy_by_id = {}
    op_bucket = {}
    local_data_pairs = set()
    memory_pairs = set()
    for c in range(count_cores):
        step = steps[c]
        require(not step.get('spill_records') and not step.get('overflow_log')
                and not step.get('new_ops') and not step.get('new_tensors')
                and not step.get('new_edges') and not step.get('removed_edges'),
                'step2_spill', core=c,
                spills=len(step.get('spill_records', [])),
                overflows=len(step.get('overflow_log', [])))
        task = tasks[c]
        task_graph = task['graph']
        ops, tensors, prod, cons, in_tids, out_tids, direct = _graph_ports(task_graph)
        seq = task['seq']
        require(len(seq) == len(set(seq)) == len(ops) and set(seq) == set(ops)
                and step['seq_ext'] == seq, 'task_seq', core=c)
        require(set(ids(task['op_by_id'])) == set(ops), 'task_op_index', core=c)
        require(set(ids(task['tensor_by_id'])) == set(tensors), 'task_tensor_index', core=c)
        actual_compute = {u for u in ops if u in compute}
        expected_compute = {u for u in compute if core_of[u] == c}
        require(actual_compute == expected_compute, 'task_compute_coverage', core=c,
                expected=len(expected_compute), actual=len(actual_compute))
        require(all(u in compute or ops[u]['op'] in COPY for u in ops),
                'unexpected_task_op', core=c)
        found = {tid: (t['pos'], t['size']) for tid, t in tensors.items()
                 if t['pos'] != 'DDR'}
        wanted = {tid: ('UB' if raw_tensors[tid]['pos'] == 'DDR'
                        else raw_tensors[tid]['pos'], raw_tensors[tid]['size'])
                  for tid in touched[c]}
        require(found == wanted, 'local_tensor_identity', core=c,
                expected=len(wanted), actual=len(found),
                missing=sorted(set(wanted)-set(found))[:10],
                extra=sorted(set(found)-set(wanted))[:10])
        # _graph_ports already rejects multiple producers for each tensor.
        require(all(tid in prod for tid in found), 'local_tensor_producer', core=c)
        seq_rank = {u: i for i, u in enumerate(seq)}
        if allow_multi:
            require(all(out_tids[u] & set(found) for u in actual_compute),
                    'compute_managed_output', core=c,
                    missing=sorted(u for u in actual_compute if not out_tids[u] & set(found))[:10])
            # Step2's ext_edges are the pre-Step3 graph when no spill/rewrite
            # fields exist. Step3 may only add MEMORY_REUSE op arcs.
            def edge_key(e):
                return (e['source'], e['target'], e.get('dependency'))
            graph_edges = Counter(map(edge_key, task_graph['edges']))
            ext_edges = Counter(map(edge_key, step['ext_edges']))
            extra = graph_edges - ext_edges
            require(not (ext_edges - graph_edges)
                    and all(kind == 'MEMORY_REUSE' for _, _, kind in extra),
                    'step3_graph_extension', core=c)
            for tid in found:
                uses = {prod[tid]} | cons[tid]
                require(uses <= set(seq_rank), 'closed_interval_coverage', core=c, tid=tid)
            delta = {pool: [0] * (len(seq) + 1) for pool in capacity}
            for tid, (pool, size) in found.items():
                uses = {prod[tid]} | cons[tid]
                first = min(seq_rank[u] for u in uses)
                last = max(seq_rank[u] for u in uses)
                delta[pool][first] += size
                delta[pool][last + 1] -= size
            local_peak = {}
            for pool, row in delta.items():
                used = peak = 0
                for d in row[:-1]:
                    used += d
                    peak = max(peak, used)
                require(peak <= capacity[pool], 'closed_interval_capacity',
                        core=c, pool=pool, peak=peak, capacity=capacity[pool])
                local_peak[pool] = peak
            closed_peaks.append(local_peak)
            for tid, source in prod.items():
                for target in cons[tid]:
                    require(seq_rank[source] < seq_rank[target],
                            'task_data_topology', core=c, source=source, target=target)
        step3 = task['step3']
        # This is the local Step3 preparation simulation, not the final
        # multicore event trace's peak. The latter needs a separate P3 result.
        require(all(step3['memory_peak'][pool] <= capacity[pool] for pool in capacity),
                'step3_local_capacity', core=c,
                peak=step3['memory_peak'], capacity=capacity)
        require(set(task['pipe_ops']) == set(PIPES), 'pipe_set', core=c)
        projected = {p: [u for u in seq if ops[u]['pipe'] == p] for p in PIPES}
        require(all(task['pipe_ops'][p] == projected[p]
                    and step3['pipe_orders'][p] == projected[p] for p in PIPES),
                'pipe_fifo', core=c)
        require(sum(map(len, projected.values())) == len(seq), 'pipe_coverage', core=c)
        if not allow_multi:
            for p in ('PIPE_M', 'PIPE_V'):
                word = [op_of_sg[sg] for sg in schedules[c] if raw_ops[op_of_sg[sg]]['pipe'] == p]
                require([u for u in projected[p] if u in compute] == word,
                        'original_pipe_fifo', core=c, pipe=p)
        sg_index = {sg: i for i, sg in enumerate(schedules[c])}
        op_sg = ids(task['op_subgraph'])
        require(set(op_sg) == set(ops) and set(op_sg.values()) <= set(sg_index),
                'op_subgraph_coverage', core=c)
        positions = [sg_index[op_sg[u]] for u in seq]
        require(positions == sorted(positions), 'bucket_order', core=c)
        for u in seq:
            b = sg_index[op_sg[u]]
            op_bucket[(c, u)] = b
            nodes.add((c, u))
            if u in compute:
                require(b == bucket[u][1], 'compute_bucket', core=c, op=u)
                continue
            kind = ops[u]['op']
            local = (out_tids[u] if kind == 'COPY_IN' else in_tids[u]) & set(found)
            require(len(local) == 1, 'copy_local_tensor', core=c, op=u,
                    kind=kind, local=sorted(local))
            tid = next(iter(local))
            require(len(in_tids[u]) == 1 and len(out_tids[u]) == 1
                    and (all(tensors[x]['pos'] == 'DDR' for x in in_tids[u])
                         if kind == 'COPY_IN'
                         else all(tensors[x]['pos'] == 'DDR' for x in out_tids[u])),
                    'copy_shape', core=c, op=u, kind=kind)
            ddr_tid = next(iter(in_tids[u] if kind == 'COPY_IN' else out_tids[u]))
            require(tensors[ddr_tid]['size'] == tensors[tid]['size'],
                    'copy_size', core=c, op=u, local_tid=tid, ddr_tid=ddr_tid)
            if kind == 'COPY_IN':
                first_users = [bucket[v][1] for v in raw_cons[tid]
                               if v in compute and core_of[v] == c]
                require(bool(first_users), 'copy_without_consumer', core=c, op=u, tid=tid)
                expected_b = min(first_users)
            else:
                source = raw_prod.get(tid)
                require(source in bucket and core_of[source] == c,
                        'copy_without_local_producer', core=c, op=u, tid=tid)
                expected_b = bucket[source][1]
            require(b == expected_b, 'copy_bucket', core=c, op=u,
                    kind=kind, tid=tid, expected=expected_b, actual=b)
            observed_copies[(kind, c, tid)] += 1
            copy_by_id[(c, u)] = (kind, tid)
        bucket_compute_counts = Counter(op_bucket[(c, u)] for u in seq if u in compute)
        require(all(bucket_compute_counts[i] >= 1 if allow_multi
                    else bucket_compute_counts[i] == 1
                    for i in range(len(schedules[c]))),
                'bucket_compute_count', core=c)
        seq_rank = {u: i for i,u in enumerate(seq)}
        for u in seq:
            if (c,u) not in copy_by_id:
                continue
            kind, _ = copy_by_id[(c,u)]
            b = op_bucket[(c,u)]
            if allow_multi:
                tid = copy_by_id[(c,u)][1]
                neighbors = ([v for v in cons[tid] if v in compute]
                             if kind == 'COPY_IN' else
                             [v for v in ops if v in compute and tid in out_tids[v]])
                require(bool(neighbors) and
                        all((seq_rank[u] < seq_rank[v] if kind == 'COPY_IN'
                             else seq_rank[v] < seq_rank[u]) for v in neighbors),
                        'copy_all_endpoint_order', core=c, op=u, tid=tid, kind=kind)
            else:
                anchor = op_of_sg[schedules[c][b]]
                require((seq_rank[u] < seq_rank[anchor] if kind == 'COPY_IN'
                         else seq_rank[anchor] < seq_rank[u]),
                        'copy_within_bucket_order', core=c, op=u, anchor=anchor, kind=kind)
        for tid in touched[c]:
            actual_compute_users = cons[tid] & compute
            expected_compute_users = {u for u in raw_cons[tid]
                                      if u in compute and core_of[u] == c}
            require(actual_compute_users == expected_compute_users,
                    'local_tensor_consumers', core=c, tid=tid)
            source = prod.get(tid)
            original_source = raw_prod.get(tid)
            source_ok = (source == original_source if original_source in expected_compute
                         else source in ops and ops[source]['op'] == 'COPY_IN')
            require(source_ok,
                    'local_tensor_source', core=c, tid=tid, source=source)
        for tid, source in prod.items():
            for target in cons[tid]:
                pair = ((c, source), (c, target))
                local_data_pairs.add(pair)
                edges[pair[0]][pair[1]] = 0
                edge_counts['data_raw'] += 1
        reported_mem = {(d['source'], d['target']) for d in step3['memory_dependencies']}
        graph_mem = {(u,v) for u,v,kind in direct if kind == 'MEMORY_REUSE'}
        require(all(kind == 'MEMORY_REUSE' for _,_,kind in direct)
                and graph_mem <= reported_mem
                and reported_mem <= graph_mem | {(u,v) for (cc,u),(dd,v) in local_data_pairs
                                                  if cc == c and dd == c},
                'memory_graph_mismatch', core=c)
        for u, v in reported_mem:
            require(u in ops and v in ops, 'memory_endpoint', core=c, source=u, target=v)
            bu, bv = op_bucket[(c,u)], op_bucket[(c,v)]
            require(bu <= bv if allow_multi else bu < bv, 'memory_backward_bucket', core=c,
                    source=u, target=v, source_bucket=bu, target_bucket=bv)
            memory_pairs.add(((c,u),(c,v)))
            edges[(c,u)][(c,v)] = 0
            edge_counts['memory_reported'] += 1
        for p in PIPES:
            for u,v in zip(projected[p], projected[p][1:]):
                edges[(c,u)][(c,v)] = 0
                edge_counts['pipe_fifo'] += 1
    require(observed_copies == expected_copies, 'copy_count',
            expected=sum(expected_copies.values()), actual=sum(observed_copies.values()),
            missing=list((expected_copies-observed_copies).items())[:10],
            extra=list((observed_copies-expected_copies).items())[:10])
    require(traffic['spill_added_copy_bytes'] == 0, 'spill_traffic')
    original_copy_bytes = sum(raw_tensors[tid]['size']
                              for op_id, op in raw_ops.items() if op['op'] in COPY
                              for tid in (raw_out[op_id] if op['op'] == 'COPY_IN'
                                          else {t for t, users in raw_cons.items()
                                                if op_id in users}))
    task_copy_bytes = sum(raw_tensors[tid]['size'] * number
                          for (_, _, tid), number in observed_copies.items())
    require(traffic['original_graph_copy_bytes'] == original_copy_bytes
            and traffic['scheduled_copy_bytes'] == task_copy_bytes
            and traffic['added_copy_bytes'] == task_copy_bytes - original_copy_bytes,
            'copy_traffic', original=original_copy_bytes, scheduled=task_copy_bytes,
            traffic=traffic)
    observed_links = set()
    for link in links:
        sc, dc, tid = link['source_core'], link['target_core'], link['tensor_id']
        source = (sc, link['source_copy_out_id'])
        target = (dc, link['target_copy_in_id'])
        require(source in nodes and target in nodes and sc != dc
                and copy_by_id.get(source) == ('COPY_OUT', tid)
                and copy_by_id.get(target) == ('COPY_IN', tid)
                and link['size'] == raw_tensors[tid]['size'],
                'cross_link_endpoint', link=link)
        observed_links.add((sc, dc, tid))
        edges[source][target] = 1
        edge_counts['cross_links'] += 1
    require(len(links) == len(observed_links) and observed_links == expected_links,
            'cross_link_coverage', expected=len(expected_links), actual=len(links),
            missing=sorted(expected_links-observed_links)[:10],
            extra=sorted(observed_links-expected_links)[:10])

    indegree = {u: 0 for u in nodes}
    for u, row in edges.items():
        for v in row:
            require(v in indegree, 'union_edge_endpoint', source=u, target=v)
            indegree[v] += 1
    ready = deque(sorted(u for u,d in indegree.items() if d == 0))
    crossing = {u: 0 for u in nodes}
    processed = 0
    while ready:
        u = ready.popleft()
        processed += 1
        for v, remote in edges[u].items():
            crossing[v] = max(crossing[v], crossing[u] + remote)
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    require(processed == len(nodes), 'union_cycle', nodes=len(nodes), processed=processed,
            edge_counts=dict(edge_counts))
    max_crossing = max(crossing.values(), default=0)
    if crossing_limit is not None:
        require(max_crossing <= crossing_limit, 'crossing_bound',
                actual=max_crossing, limit=crossing_limit, edge_counts=dict(edge_counts))
    return {'schema': 'q3-layered-prepared-guard-v1', 'status': 'passed',
            'scope': 'captured official Task/Step2/Step3 bytes; no evaluator invoked',
            'cores': count_cores, 'compute_ops': len(compute), 'prepared_ops': len(nodes),
            'frontier_peaks': peaks if not allow_multi else None,
            'step3_local_memory_peaks': [tasks[c]['step3']['memory_peak']
                                         for c in range(count_cores)],
            'copy_ops': sum(observed_copies.values()), 'cross_links': len(links),
            'original_copy_bytes': original_copy_bytes,
            'scheduled_copy_bytes': task_copy_bytes,
            'memory_dependencies': len(memory_pairs), 'edge_counts': dict(edge_counts),
            'union_unique_edges': sum(map(len, edges.values())),
            'max_crossing': max_crossing, 'crossing_limit': crossing_limit,
            'crossing_bound_certified': crossing_limit is not None,
            'allow_multi': allow_multi,
            'complete_seq_closed_interval_peaks': closed_peaks if allow_multi else None}
