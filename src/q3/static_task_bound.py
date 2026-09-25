"""Conditional fixed-plan lower bound from complete pre-Step2 Task snapshots.

No Task builder, Step1/2/3 or evaluator is executed. Full closed intervals must
prove no spill; success of official preparation/execution is not asserted.
"""
from collections import Counter, defaultdict, deque

from .pipeline_prefix import GuardFailure, _interval_peaks, _ports


def analyze(tasks, links, *, capacity, ddr_bandwidth, cache_bandwidth,
            cross_core_delay_cycles):
    """Tasks map core IDs to {graph, pre_step2_word}; all Tasks are required.

Scope: plain integer tensor identities, tensor-mediated edges, M/V compute,
one-port DDR COPYs. The caller must bind these snapshots to its actual plan and
frozen official source. The bound does not validate that provenance itself.
"""
    if (not tasks or any(type(c) is not int or c < 0 for c in tasks)
            or set(tasks) != set(range(len(tasks)))):
        raise GuardFailure('all contiguous core Task snapshots required')
    if (set(capacity) != {'L1', 'UB'}
            or any(type(x) is not int or x <= 0 for x in capacity.values())):
        raise GuardFailure('positive explicit capacities required')
    if any(type(x) is not int or not 0 < x <= 2**20
           for x in (ddr_bandwidth, cache_bandwidth)):
        raise GuardFailure('bounded positive integer bandwidths required')
    if type(cross_core_delay_cycles) is not int or cross_core_delay_cycles < 0:
        raise GuardFailure('nonnegative integer cross-core delay required')
    nodes, views, peaks, copies = {}, {}, {}, {}
    edges = defaultdict(dict)
    keys = Counter()

    def add(u, v, delay=0):
        edges[u][v] = max(edges[u].get(v, 0), delay)

    for core, task in tasks.items():
        graph, word = task['graph'], task['pre_step2_word']
        ports = _ports(graph)
        ops, tensors, producers, consumers, inputs, outputs = ports
        if any(set(t) != {'id', 'pos', 'size'} or type(t['id']) is not int
               or type(t['size']) is not int or not 0 <= t['size'] <= 2**40
               or t['pos'] not in {'DDR', 'L1', 'UB'} for t in tensors.values()):
            raise GuardFailure('requires plain integer tensor IDs and bounded sizes')
        if any(len(ps) > 1 for ps in producers.values()):
            raise GuardFailure('multiple tensor producers outside this bound')
        peaks[core] = _interval_peaks(graph, word, capacity)
        views[core] = ports
        previous = {}
        for opid in word:
            op = ops[opid]
            if type(opid) is not int:
                raise GuardFailure('integer operation IDs required')
            node = (core, opid)
            kind, pipe = op['op'], op['pipe']
            data = {'core': core, 'op_id': opid, 'kind': kind, 'pipe': pipe}
            if kind in {'COPY_IN', 'COPY_OUT'}:
                if len(inputs[opid]) != 1 or len(outputs[opid]) != 1:
                    raise GuardFailure('COPY must have one input and one output')
                ti, to = next(iter(inputs[opid])), next(iter(outputs[opid]))
                local, remote = (to, ti) if kind == 'COPY_IN' else (ti, to)
                expected_pipe = 'PIPE_MTE2' if kind == 'COPY_IN' else 'PIPE_MTE3'
                if (pipe != expected_pipe or tensors[remote]['pos'] != 'DDR'
                        or tensors[local]['pos'] not in capacity
                        or tensors[local]['size'] != tensors[remote]['size']):
                    raise GuardFailure('COPY port/pipe/size shape outside proof')
                data.update(bytes=tensors[local]['size'], cache_key=local)
                copies[node] = data
                if kind == 'COPY_IN':
                    keys[local] += 1
            else:
                if (pipe not in {'PIPE_M', 'PIPE_V'} or type(op.get('cycles')) is not int
                        or not 0 <= op['cycles'] <= 2**40):
                    raise GuardFailure('integer M/V compute duration required')
                data['duration_lower_bound'] = max(1, op['cycles'])
            nodes[node] = data
            if pipe in previous:
                add((core, previous[pipe]), node)
            previous[pipe] = opid
        for tid in tensors:
            for u in producers[tid]:
                for v in consumers[tid]:
                    add((core, u), (core, v))

    for node, data in copies.items():
        cold = data['kind'] == 'COPY_IN' and keys[data['cache_key']] == 1
        speed = (ddr_bandwidth if cold or data['kind'] == 'COPY_OUT'
                 else max(ddr_bandwidth, cache_bandwidth))
        data['sole_copy_in_key_proved_cold'] = cold
        data['duration_lower_bound'] = max(1, (data['bytes'] + speed - 1) // speed)
    for link in links:
        source = (link['source_core'], link['source_copy_out_id'])
        target = (link['target_core'], link['target_copy_in_id'])
        if (source not in nodes or target not in nodes or source[0] == target[0]
                or nodes[source]['kind'] != 'COPY_OUT' or nodes[target]['kind'] != 'COPY_IN'):
            raise GuardFailure('invalid cross-core COPY link')
        add(source, target, cross_core_delay_cycles)
    indegree = dict.fromkeys(nodes, 0)
    for targets in edges.values():
        for target in targets:
            indegree[target] += 1
    ready = deque(sorted(u for u in nodes if not indegree[u]))
    starts, parents = dict.fromkeys(nodes, 0), {}
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v, delay in edges.get(u, {}).items():
            value = starts[u] + nodes[u]['duration_lower_bound'] + delay
            if value > starts[v]:
                starts[v], parents[v] = value, u
            indegree[v] -= 1
            if not indegree[v]:
                ready.append(v)
    if visited != len(nodes):
        raise GuardFailure('data/FIFO/cross-copy relaxation contains a cycle')
    last = max(nodes, key=lambda u: (starts[u] + nodes[u]['duration_lower_bound'], u))
    lower = starts[last] + nodes[last]['duration_lower_bound']
    path = []
    while last is not None:
        path.append({**nodes[last], 'earliest_start': starts[last]})
        last = parents.get(last)
    path.reverse()
    return {'schema': 'q3-no-spill-static-task-bound-v1',
            'lower_bound_cycles': lower,
            'scope': 'successful execution of this exact no-spill Task word; not all-plan optimum',
            'official_execution_legality_proved': False,
            'interval_peaks': peaks,
            'op_count': len(nodes), 'edge_count': sum(map(len, edges.values())),
            'copy_count': len(copies),
            'sole_copy_in_key_count': sum(d['sole_copy_in_key_proved_cold'] for d in copies.values()),
            'settings': {'capacity': capacity, 'ddr_bandwidth': ddr_bandwidth,
                         'cache_bandwidth': cache_bandwidth,
                         'cross_core_delay_cycles': cross_core_delay_cycles},
            'copy_nodes': list(copies.values()), 'critical_path': path,
            'calls': {'Task_builder': 0, 'Step1': 0, 'Step2': 0, 'Step3': 0, 'E0': 0}}
