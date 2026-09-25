"""One frozen, read-only static analysis of the 201-op convex pilot sequence."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'results/a/q3-nikolastarx'
OUT = Path(__file__).resolve().parent / 'RESULT.json'
INPUTS = {
    'prepared': ('layered-one-shot-20260925/run/prepared.json.gz', '91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44'),
    'old_plan': ('layered-one-shot-20260925/candidate/case_005_multicore_res.json', '2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
    'new_plan': ('convex-pilot-cut-20260925/CANDIDATE_UNVALIDATED.json', 'f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2'),
    'step1_result': ('convex-pilot-step1-20260925/RESULT.json', '25e3148631efc5a4186a980a8669c00d9e06756541de1f2c38fafe55e790781f'),
}


def checked(name):
    rel, expected = INPUTS[name]
    path = BASE / rel
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f'{name} SHA-256 differs: {actual}')
    return data


def owner_words(plan):
    words = plan['core_schedules']
    if len(words) != 5:
        raise ValueError('five-core plan required')
    sg_owner = {}
    for core, word in enumerate(words):
        for sg in word:
            if sg in sg_owner:
                raise ValueError('duplicate scheduled subgraph')
            sg_owner[sg] = core
    mapping = {int(op): sg for op, sg in plan['node_to_subgraph'].items()}
    if set(mapping.values()) != set(sg_owner):
        raise ValueError('plan SG coverage differs')
    return {op: sg_owner[sg] for op, sg in mapping.items()}, words


def capacity_peak(task, ext_edges, seq, capacity):
    ops = {o['id']: o for o in task['graph']['ops']}
    tensors = {t['id']: t for t in task['graph']['tensors']}
    positions = {op: i for i, op in enumerate(seq)}
    if len(seq) != len(ops) or len(positions) != len(ops) or set(seq) != set(ops):
        raise ValueError('candidate sequence is not exact core0 op coverage')
    uses = collections.defaultdict(set)
    for edge in ext_edges:
        a, b = edge['source'], edge['target']
        if a in ops and b in tensors:
            uses[b].add(a)
        elif a in tensors and b in ops:
            uses[a].add(b)
        elif a in ops and b in ops:
            pass
        else:
            raise ValueError('unrecognized recovered edge')
    peak = {}
    counted = {}
    for pool in ('L1', 'UB'):
        delta = [0] * (len(seq) + 1)
        counted[pool] = 0
        for tid, t in tensors.items():
            if t['pos'] != pool:
                continue
            if not uses[tid]:
                raise ValueError(f'on-chip tensor {tid} lacks producer and consumer uses')
            first = min(positions[u] for u in uses[tid])
            last = max(positions[u] for u in uses[tid])
            delta[first] += t['size']
            delta[last + 1] -= t['size']
            counted[pool] += 1
        running = 0
        values = []
        for i in range(len(seq)):
            running += delta[i]
            values.append(running)
        peak[pool] = {'bytes': max(values, default=0), 'capacity_bytes': capacity[pool],
                      'within_capacity': max(values, default=0) <= capacity[pool],
                      'at_seq_pos': values.index(max(values)) if values else None,
                      'tensor_count': counted[pool]}
    return peak


def add_graph(core, ops, tensors, edges, memory_pairs, arc_types):
    op_ids = {o['id'] for o in ops}
    tid_ids = {t['id'] for t in tensors}
    producers = collections.defaultdict(set)
    consumers = collections.defaultdict(set)
    for edge in edges:
        a, b = edge['source'], edge['target']
        if a in op_ids and b in tid_ids:
            producers[(core, b)].add((core, a))
        elif a in tid_ids and b in op_ids:
            consumers[(core, a)].add((core, b))
        elif a in op_ids and b in op_ids:
            arc_types[((core, a), (core, b))].add(
                'saved_memory' if (a, b) in memory_pairs else 'local_direct')
        else:
            raise ValueError(f'core {core} graph edge endpoints missing: {a}->{b}')
    for key in set(producers) | set(consumers):
        for source in producers[key]:
            for target in consumers[key]:
                arc_types[(source, target)].add('tensor_contract')
    return op_ids, tid_ids, len(producers), len(consumers)


def cycle_witness(vertices, arc_types):
    adjacent = collections.defaultdict(list)
    for a, b in arc_types:
        adjacent[a].append(b)
    color = {}
    for start in vertices:
        if color.get(start):
            continue
        color[start] = 1
        path = [start]
        stack = [(start, iter(adjacent[start]))]
        while stack:
            u, it = stack[-1]
            try:
                v = next(it)
            except StopIteration:
                color[u] = 2
                stack.pop()
                path.pop()
                continue
            if color.get(v) == 1:
                i = path.index(v)
                nodes = path[i:] + [v]
                return [{'source': list(a), 'target': list(b),
                         'types': sorted(arc_types[(a, b)])}
                        for a, b in zip(nodes, nodes[1:])]
            if not color.get(v):
                color[v] = 1
                path.append(v)
                stack.append((v, iter(adjacent[v])))
    return None


def main():
    started = time.monotonic()
    if OUT.exists():
        raise FileExistsError('one-pass result already exists')
    raw = {key: checked(key) for key in INPUTS}
    prepared = json.loads(gzip.decompress(raw['prepared']))
    old = json.loads(raw['old_plan'])
    new = json.loads(raw['new_plan'])
    step1 = json.loads(raw['step1_result'])
    if step1['input_sha256'] != {key: expected for key, (_, expected) in INPUTS.items() if key != 'step1_result'} | {'step1_source': 'd8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034', 'p3_source': 'eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0'}:
        raise ValueError('Step1 result input identity differs')
    if step1['official_step1_calls'] != 1 or not step1['old_replay_exact'] or not step1['candidate_priority_topological']:
        raise ValueError('Step1 one-shot receipt is incomplete')
    if len(prepared['step2']) != 5 or len(prepared['task_return'][0]) != 5:
        raise ValueError('prepared five-core coverage differs')
    old_owner, old_words = owner_words(old)
    new_owner, new_words = owner_words(new)
    if old_owner != new_owner or any(old_words[c] != new_words[c] for c in range(1, 5)):
        raise ValueError('candidate changed ownership or other-core schedules')
    tasks, links = prepared['task_return'][:2]
    if len(links) != 381:
        raise ValueError('cross-link count differs')
    task0 = tasks['0']
    step20 = prepared['step2'][0]
    for key in ('new_ops', 'new_tensors', 'new_edges', 'removed_edges', 'spill_records'):
        if step20[key]:
            raise ValueError(f'core0 Step2 {key} nonempty')
    ext_edges = step20['ext_edges']
    if len(ext_edges) != 1992:
        raise ValueError('core0 recovered original edge count differs')
    memory_pairs = collections.Counter((e['source'], e['target']) for e in task0['step3']['memory_dependencies'])
    observed_extra = collections.Counter((e['source'], e['target']) for e in task0['graph']['edges']) - collections.Counter((e['source'], e['target']) for e in ext_edges)
    if len(list(memory_pairs.elements())) != 730 or observed_extra != memory_pairs:
        raise ValueError('core0 old graph does not differ by exactly saved memory edges')
    seq0 = step1['candidate_seq']
    if len(seq0) != 795 or len(task0['seq']) != 795 or step1['pilot_copy_id'] != 1000004471 or seq0.index(1000004471) != 240:
        raise ValueError('frozen Step1 candidate sequence differs')
    if prepared['capacity'] != {'L1': 524288, 'UB': 131072}:
        raise ValueError('prepared capacity differs')
    config = (ROOT / 'data/raw/a/official/data/config.txt').read_text()
    if 'L1 524288' not in config or 'UB 131072' not in config:
        raise ValueError('current official config capacity differs')
    peak = capacity_peak(task0, ext_edges, seq0, prepared['capacity'])
    arc_types = collections.defaultdict(set)
    vertices = set()
    local = []
    pipe_counts = []
    for core in range(5):
        task = tasks[str(core)]
        edges = ext_edges if core == 0 else task['graph']['edges']
        memory = set() if core == 0 else {
            (e['source'], e['target']) for e in task['step3']['memory_dependencies']}
        op_ids, tid_ids, prod_count, cons_count = add_graph(
            core, task['graph']['ops'], task['graph']['tensors'], edges,
            memory, arc_types)
        vertices.update((core, u) for u in op_ids)
        seq = seq0 if core == 0 else task['seq']
        if len(seq) != len(op_ids) or set(seq) != op_ids:
            raise ValueError(f'core{core} seq/op coverage differs')
        by_pipe = collections.defaultdict(list)
        by_id = {o['id']: o for o in task['graph']['ops']}
        for u in seq:
            by_pipe[by_id[u]['pipe']].append(u)
        for pipe, word in by_pipe.items():
            for a, b in zip(word, word[1:]):
                arc_types[((core, a), (core, b))].add('fifo:' + pipe)
        if core > 0 and any(by_pipe[pipe] != task['pipe_ops'].get(pipe, []) for pipe in by_pipe):
            raise ValueError(f'core{core} saved pipe FIFO differs')
        pipe_counts.append({pipe: len(word) for pipe, word in by_pipe.items()})
        local.append({'core': core, 'ops': len(op_ids), 'tensors': len(tid_ids),
                      'graph_edges': len(edges), 'tensor_keys_with_producers': prod_count,
                      'tensor_keys_with_consumers': cons_count})
    for link in links:
        a = (link['source_core'], link['source_copy_out_id'])
        b = (link['target_core'], link['target_copy_in_id'])
        if a not in vertices or b not in vertices:
            raise ValueError('cross link copy endpoint absent')
        arc_types[(a, b)].add('cross_link')
    witness = cycle_witness(vertices, arc_types)
    result = {'schema': 'convex-sequence-static-guard-v1', 'input_sha256':
              {key: expected for key, (_, expected) in INPUTS.items()},
              'official_calls_this_process': {'Task': 0, 'Step': 0, 'E0': 0, 'E1': 0, 'E2': 0},
              'other_core_owner_and_schedule_unchanged': True,
              'core0_recovered_original_edges': 1992,
              'core0_excluded_old_memory_edges': 730,
              'core0_candidate_seq_ops': len(seq0),
              'capacity_interval_peak': peak,
              'capacity_sufficient_for_no_spill': all(x['within_capacity'] for x in peak.values()),
              'local_coverage': local, 'pipe_counts': pipe_counts,
              'cross_links': len(links), 'joint_op_vertices': len(vertices),
              'joint_arcs': len(arc_types), 'joint_dag': witness is None,
              'cycle_witness': witness, 'elapsed_seconds': time.monotonic() - started,
              'interpretation': ('Cycle plus no-spill capacity rules out the candidate under this necessary union graph; DAG only leaves new core0 Step3 memory dependencies unresolved. Interval peak is not runtime memory peak.')}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'joint_dag': result['joint_dag'], 'joint_arcs': len(arc_types),
                      'capacity_sufficient_for_no_spill': result['capacity_sufficient_for_no_spill']}))


if __name__ == '__main__':
    main()
