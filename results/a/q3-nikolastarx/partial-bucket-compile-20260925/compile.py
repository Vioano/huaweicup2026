"""Offline, pure-Python compiler for one saved P3 pilot-subgraph split.

No official modules, Task construction, Step1/2/3, solver, or evaluator.
The result is a predicted pre-Step2 word, not an official validation.
"""
from __future__ import annotations

from collections import defaultdict
from collections import deque
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path


class Reject(ValueError):
    pass


def ports(graph):
    ops = {int(o['id']): o for o in graph['ops']}
    tensors = {int(t['id']): t for t in graph['tensors']}
    if len(ops) != len(graph['ops']) or len(tensors) != len(graph['tensors']):
        raise Reject('duplicate graph ID')
    prod, cons, ins, outs = (defaultdict(set) for _ in range(4))
    direct = []
    for e in graph['edges']:
        a, b = int(e['source']), int(e['target'])
        if a in ops and b in tensors:
            prod[b].add(a); outs[a].add(b)
        elif a in tensors and b in ops:
            cons[a].add(b); ins[b].add(a)
        elif a in ops and b in ops:
            direct.append((a, b))
        else:
            raise Reject('unsupported Task edge')
    return ops, tensors, prod, cons, ins, outs, direct


def check_topo(graph, word):
    ops, tensors, prod, cons, _, _, direct = ports(graph)
    if len(word) != len(ops) or set(word) != set(ops):
        raise Reject('Task operation coverage')
    rank = {u: i for i, u in enumerate(word)}
    if len(rank) != len(word):
        raise Reject('duplicate Task operation')
    for u, v in direct:
        if rank[u] >= rank[v]:
            raise Reject('direct dependency inverted')
    for tid in tensors:
        for u in prod[tid]:
            for v in cons[tid]:
                if rank[u] >= rank[v]:
                    raise Reject('tensor dependency inverted')


def interval_peaks(graph, word):
    check_topo(graph, word)
    _, tensors, prod, cons, _, _, _ = ports(graph)
    rank = {u: i for i, u in enumerate(word)}
    delta = {p: [0] * (len(word) + 1) for p in ('L1', 'UB')}
    for tid, t in tensors.items():
        pos = t['pos']
        if pos not in delta:
            continue
        uses = prod[tid] | cons[tid]
        if not uses:
            continue
        if not prod[tid]:
            raise Reject('on-chip tensor has no Task producer')
        first, last = min(rank[u] for u in uses), max(rank[u] for u in uses)
        delta[pos][first] += t['size']
        delta[pos][last + 1] -= t['size']
    peaks = {}
    for pos, events in delta.items():
        used = peak = 0
        for change in events:
            used += change
            peak = max(peak, used)
        peaks[pos] = peak
    return peaks


def check_global_pre_step2(snapshots, words):
    """Check local data + per-Pipe FIFO + cross-COPY precedence has no cycle."""
    successor = defaultdict(set)
    indegree = {}
    for core_str, saved in snapshots['candidate'].items():
        core = int(core_str)
        graph = saved['graph']
        word = words[core_str]
        check_topo(graph, word)
        ops, tensors, prod, cons, _, _, direct = ports(graph)
        for u in ops:
            indegree[(core, u)] = 0
        for u, v in direct:
            successor[(core, u)].add((core, v))
        for tid in tensors:
            for u in prod[tid]:
                for v in cons[tid]:
                    successor[(core, u)].add((core, v))
        pipe_last = {}
        for u in word:
            pipe = ops[u]['pipe']
            if pipe in pipe_last:
                successor[(core, pipe_last[pipe])].add((core, u))
            pipe_last[pipe] = u
    for link in snapshots['cross_links']:
        a = (link['source_core'], link['source_copy_out_id'])
        b = (link['target_core'], link['target_copy_in_id'])
        if a not in indegree or b not in indegree:
            raise Reject('cross-COPY link target missing')
        successor[a].add(b)
    for targets in successor.values():
        for v in targets:
            indegree[v] += 1
    ready = deque(u for u, count in indegree.items() if count == 0)
    seen = 0
    while ready:
        u = ready.popleft(); seen += 1
        for v in successor[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if seen != len(indegree):
        raise Reject('global pre-Step2 data/Pipe/COPY precedence cycle')
    return {'ops': seen, 'edges': sum(len(v) for v in successor.values())}


def annotate(graph, raw, mapping, order):
    ops, tensors, prod, cons, ins, outs, _ = ports(graph)
    rank = {sg: i for i, sg in enumerate(order)}
    if len(rank) != len(order):
        raise Reject('duplicate subgraph in core order')
    ann = {}
    for u in raw:
        if u in mapping:
            sg = mapping[u]
        elif ops[u]['op'] == 'COPY_IN':
            readers = {v for t in outs[u] if tensors[t]['pos'] != 'DDR'
                       for v in cons[t] if v in mapping}
            if not readers:
                raise Reject('COPY_IN lacks compute reader')
            sg = min((mapping[v] for v in readers), key=rank.__getitem__)
        elif ops[u]['op'] == 'COPY_OUT':
            writers = {v for t in ins[u] if tensors[t]['pos'] != 'DDR'
                       for v in prod[t] if v in mapping}
            if not writers:
                raise Reject('COPY_OUT lacks compute writer')
            sg = max((mapping[v] for v in writers), key=rank.__getitem__)
        else:
            raise Reject('unexpected noncompute Task operation')
        if sg not in rank:
            raise Reject('operation assigned outside core order')
        ann[u] = sg
    return ann


def bucket(raw, ann, order):
    rank = {sg: i for i, sg in enumerate(order)}
    buckets = [[] for _ in order]
    for u in raw:
        buckets[rank[ann[u]]].append(u)
    return [u for row in buckets for u in row]


def compile_split(plan, snapshots, certificate, core, head_count):
    """Split one first pilot bucket; return (two-field plan, predicted words, facts)."""
    if set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise Reject('plan top-level schema')
    supplied = plan['node_to_subgraph']
    if (not isinstance(supplied, dict)
            or any(not isinstance(u, str) or not u.isdecimal()
                   or str(int(u)) != u or type(sg) is not int
                   for u, sg in supplied.items())):
        raise Reject('mapping must use canonical integer keys and integer subgraphs')
    original = {int(u): sg for u, sg in supplied.items()}
    orders = plan['core_schedules']
    if not (1 <= core < len(orders)):
        raise Reject('requires a downstream nonempty core')
    saved = snapshots['candidate'][str(core)]
    raw = list(saved['raw_seq_reused'])
    graph = saved['graph']
    old_order = orders[core]
    if saved['subgraph_order'] != old_order or not old_order:
        raise Reject('snapshot/plan order differs')
    pilot_sg = old_order[0]
    pilot = [u for u in saved['pre_step2_word'] if original.get(u) == pilot_sg]
    if not (1 <= head_count < len(pilot)):
        raise Reject('head_count must leave nonempty head and tail')
    _, _, prod, cons, inputs, _, direct = ports(graph)
    direct = set(direct)
    for u, v in zip(pilot, pilot[1:]):
        if (u, v) not in direct and not any(u in prod[t] for t in inputs[v]):
            raise Reject('pilot is not a direct tensor-mediated chain')
    old_ann = annotate(graph, raw, original, old_order)
    if (old_ann != {int(u): sg for u, sg in saved['op_subgraph'].items()}
            or bucket(raw, old_ann, old_order) != saved['pre_step2_word']):
        raise Reject('saved baseline bucket reconstruction differs')
    check_topo(graph, saved['pre_step2_word'])

    new_sg = max(original.values()) + 1
    mapping = dict(original)
    for u in pilot[head_count:]:
        mapping[u] = new_sg
    new_orders = deepcopy(orders)
    new_orders[core] = [pilot_sg, new_sg, *old_order[1:]]
    if (len(mapping) != len(original) or set(mapping) != set(original)
            or sum(map(len, new_orders)) != len(set(mapping.values()))
            or set(sg for row in new_orders for sg in row) != set(mapping.values())):
        raise Reject('two-field plan coverage')
    predicted = {}
    target_peaks = None
    for c in range(len(orders)):
        saved_c = snapshots['candidate'][str(c)]
        if c == core:
            ann = annotate(graph, raw, mapping, new_orders[c])
            word = bucket(raw, ann, new_orders[c])
            if [u for u in word if u in mapping] != [u for u in saved_c['pre_step2_word'] if u in mapping]:
                raise Reject('compute FIFO changed')
            check_topo(graph, word)
            peaks = interval_peaks(graph, word)
            ceiling = certificate['cores'][c]['interval_peaks']
            if any(peaks[p] > ceiling[p] for p in peaks):
                raise Reject(f'closed-interval peak exceeds saved certified peak: {peaks}>{ceiling}')
            target_peaks = peaks
        else:
            base_raw = saved_c['raw_seq_reused']
            base_ann = annotate(saved_c['graph'], base_raw, original, orders[c])
            if (base_ann != {int(u): sg for u, sg in saved_c['op_subgraph'].items()}
                    or bucket(base_raw, base_ann, orders[c]) != saved_c['pre_step2_word']):
                raise Reject('unchanged core baseline bucket reconstruction differs')
            word = saved_c['pre_step2_word']
            peaks = certificate['cores'][c]['interval_peaks']
        predicted[str(c)] = word
    global_check = check_global_pre_step2(snapshots, predicted)
    new_plan = {'node_to_subgraph': {str(u): mapping[u] for u in original},
                'core_schedules': new_orders}
    ops, _, _, _, _, _, _ = ports(graph)
    mte2 = [u for u in predicted[str(core)] if ops[u]['pipe'] == 'PIPE_MTE2']
    links = [l for l in snapshots['cross_links'] if l['target_core'] == core]
    gates = {l['target_copy_in_id'] for l in links}
    _, _, _, local_cons, _, outputs, _ = ports(graph)
    pilot_set = set(pilot)
    pilot_gates = {u for u in gates if any(v in pilot_set for t in outputs[u]
                                            for v in local_cons[t])}
    facts = {'core': core, 'pilot_sg': pilot_sg, 'tail_sg': new_sg,
             'pilot_compute_count': len(pilot), 'head_count': head_count,
             'interval_peaks': target_peaks, 'mte2': mte2,
             'global_pre_step2': global_check,
             'activation_copy_positions': [i for i, u in enumerate(mte2) if u in gates],
             'pilot_activation_positions': [i for i, u in enumerate(mte2) if u in pilot_gates],
             'original_prefix_copy_ids': certificate['cores'][core]['prefix_copy_ids'],
             'head_prefix_cold_count': sum(ann[u] == pilot_sg for u in certificate['cores'][core]['prefix_copy_ids'])}
    return new_plan, predicted, facts


def snapshot_demo():
    """Compile every real consumer boundary structurally; save just one plan."""
    out = Path(__file__).resolve().parent
    saved = out.parent / 'pipeline-prefix-static-20260925'
    paths = {'plan': saved / 'case_044_multicore_res.json',
             'snapshots': saved / 'snapshots.json.gz',
             'certificate': saved / 'certificate.json'}
    plan = json.loads(paths['plan'].read_text())
    with gzip.open(paths['snapshots'], 'rt') as stream:
        snapshots = json.load(stream)
    certificate = json.loads(paths['certificate'].read_text())
    core = 2  # structural example only; no score-based core or h selection
    first = snapshots['candidate'][str(core)]['subgraph_order'][0]
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    saved_core = snapshots['candidate'][str(core)]
    pilot = [u for u in saved_core['pre_step2_word'] if mapping.get(u) == first]
    n = len(pilot)
    _, _, _, consumers, _, outputs, _ = ports(saved_core['graph'])
    position = {u: i for i, u in enumerate(pilot)}
    first_uses = []
    for copy_id in certificate['cores'][core]['prefix_copy_ids']:
        readers = [position[v] for t in outputs[copy_id] for v in consumers[t]
                   if v in position]
        if not readers:
            raise Reject('saved prefix COPY lacks pilot consumer')
        first_uses.append(min(readers))
    # Cold-input breakpoint restricted family only. Intermediate activation
    # and COPY_OUT bucket changes may make other h structurally different.
    # Do not describe these as all legal h or all possible FIFO words.
    breakpoints = []
    previous_q = None
    for h in range(1, n):
        q = sum(i < h for i in first_uses)
        if q != previous_q:
            breakpoints.append((h, q))
            previous_q = q
    rows = []
    example = None
    for h, expected_q in breakpoints:
        try:
            candidate, words, facts = compile_split(plan, snapshots, certificate, core, h)
            if facts['head_prefix_cold_count'] != expected_q:
                raise Reject('structural first-use count disagrees with Task annotation')
            rows.append({'h': h, 'status': 'static_pass',
                         'head_cold_count': facts['head_prefix_cold_count'],
                         'pilot_activation_positions': facts['pilot_activation_positions'],
                         'closed_interval_peaks': facts['interval_peaks']})
            if h == 10:
                example = (candidate, words, facts)
        except Reject as error:
            rows.append({'h': h, 'status': 'static_reject', 'reason': str(error)})
    if example is not None:
        candidate, words, facts = example
        (out / 'example-plan.json').write_text(json.dumps(candidate, indent=2) + '\n')
        (out / 'example-predicted-word.json').write_text(json.dumps({
            'core': core, 'head_count': 10, 'predicted_pre_step2_word': words[str(core)],
            'mte2': facts['mte2'], 'pilot_activation_positions': facts['pilot_activation_positions'],
        }, indent=2) + '\n')
    result = {'schema': 'partial-bucket-static-v1',
              'family': 'cold-input breakpoint restricted family',
              'source_sha256': {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
        'core': core, 'pilot_compute_count': n, 'first_use_positions': first_uses,
        'breakpoints': rows,
        'example_h': 10 if example is not None else None,
        'calls': {'Task': 0, 'Step1': 0, 'Step2': 0, 'Step3': 0,
                  'E0': 0, 'solver': 0, 'VM': 0}}
    (out / 'structure-table.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    result = snapshot_demo()
    print(json.dumps({'breakpoints': len(result['breakpoints']),
                      'passed': sum(r['status'] == 'static_pass'
                                    for r in result['breakpoints']),
                      'example_h': result['example_h']}))
