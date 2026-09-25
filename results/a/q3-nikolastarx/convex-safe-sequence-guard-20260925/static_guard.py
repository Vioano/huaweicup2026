"""One static 194-op priority replay and five-core necessary-DAG check."""
import collections
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'results/a/q3-nikolastarx'
HERE = Path(__file__).resolve().parent
INPUTS = {
    'prepared': ('layered-one-shot-20260925/run/prepared.json.gz', '91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44'),
    'old': ('layered-one-shot-20260925/candidate/case_005_multicore_res.json', '2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
    'new': ('convex-safe-cut-20260925/CANDIDATE_UNVALIDATED.json', '549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615'),
    'old201': ('convex-pilot-cut-20260925/CANDIDATE_UNVALIDATED.json', 'f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2'),
    'step1_result': ('convex-pilot-step1-20260925/RESULT.json', '25e3148631efc5a4186a980a8669c00d9e06756541de1f2c38fafe55e790781f'),
}
SOURCES = {
    'step1_only': ('convex-pilot-step1-20260925/step1_only.py', 'ab029d2afc54d7ca415d2c2c835d987936a0fe9e049acc83d258fc4f314b675a'),
    'prior_guard': ('convex-sequence-guard-20260925/static_guard.py', '7c4116c6a076ccbba22725594a27a0c99aeed7cb08f27891985d1403ede80931'),
    'official_p2': ('../../data/raw/a/official/code/multicore_cut_evaluate_problem_2.py', '0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464'),
    'official_step1': ('../../data/raw/a/official/code/schedule_step1.py', 'd8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034'),
    'official_p3': ('../../data/raw/a/official/code/multicore_cut_evaluate_problem_3.py', 'eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0'),
}


def load_json(name):
    rel, expected = INPUTS[name]
    data = (BASE / rel).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'{name} input SHA differs')
    return json.loads(gzip.decompress(data) if rel.endswith('.gz') else data)


def load_source(name):
    rel, expected = SOURCES[name]
    path = (BASE / rel).resolve() if not rel.startswith('../../') else ROOT / rel[6:]
    data = path.read_bytes()
    if expected is not None and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'{name} source SHA differs')
    return path, data


def import_frozen(name):
    path, _ = load_source(name)
    spec = importlib.util.spec_from_file_location('_frozen_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stable_priority(raw, labels, word):
    rank = {sg: i for i, sg in enumerate(word)}
    if len(rank) != len(word):
        raise ValueError('duplicate priority SG')
    return sorted(raw, key=lambda op: rank.get(labels.get(op), len(rank)))


def main():
    began = time.monotonic()
    for name in ('RESULT.json', 'candidate_seq.json'):
        if (HERE / name).exists():
            raise FileExistsError('one-pass output already exists')
    # Check official implementation text before using the exact documented rule.
    p2_path, p2_source = load_source('official_p2')
    if b'key=lambda op_id: rank.get(op_subgraph.get(op_id), fallback)' not in p2_source or b'seq = sorted(' not in p2_source:
        raise ValueError('official priority function is not the frozen stable sort')
    load_source('official_step1')
    load_source('official_p3')
    pilot = import_frozen('step1_only')
    prior = import_frozen('prior_guard')
    prepared = load_json('prepared')
    old, new, old201 = (load_json(n) for n in ('old', 'new', 'old201'))
    saved = load_json('step1_result')
    if saved['official_step1_calls'] != 1 or not saved['old_replay_exact'] or not saved['candidate_priority_topological']:
        raise ValueError('saved Step1 receipt incomplete')
    graph, task0, step20 = pilot.reconstruct(prepared)
    if len(graph['ops']) != 795 or len(graph['edges']) != 1992:
        raise ValueError('recovered core0 Task differs')
    raw = saved['raw_seq']
    op_ids = {op['id'] for op in graph['ops']}
    if len(raw) != len(op_ids) or set(raw) != op_ids:
        raise ValueError('raw Step1 sequence coverage differs')
    old_map = {int(k): v for k, v in old['node_to_subgraph'].items()}
    old_labels = {int(k): v for k, v in task0['op_subgraph'].items()}
    if task0['subgraph_ids'] != old['core_schedules'][0]:
        raise ValueError('old core0 SG word differs')
    if stable_priority(raw, old_labels, old['core_schedules'][0]) != task0['seq']:
        raise ValueError('old official prioritized sequence not exactly replayed')
    labels201 = pilot.copy_labels(graph, old_map,
        {int(k): v for k, v in old201['node_to_subgraph'].items()},
        old['core_schedules'][0], old201['core_schedules'][0], old_labels)
    if stable_priority(raw, labels201, old201['core_schedules'][0]) != saved['candidate_seq']:
        raise ValueError('201-op priority regression differs from sole official Step1 result')
    old_owner, old_words = prior.owner_words(old)
    new_owner, new_words = prior.owner_words(new)
    if old_owner != new_owner or old_words[1:] != new_words[1:]:
        raise ValueError('new candidate changed owner or other-core schedules')
    new_map = {int(k): v for k, v in new['node_to_subgraph'].items()}
    if set(new_map) != set(old_map):
        raise ValueError('new candidate compute coverage differs')
    labels = pilot.copy_labels(graph, old_map, new_map,
                               old_words[0], new_words[0], old_labels)
    seq = stable_priority(raw, labels, new_words[0])
    if len(seq) != len(op_ids) or len(set(seq)) != len(op_ids):
        raise ValueError('new sequence coverage differs')
    # Official _check_topo contracts tensor nodes to op predecessors. Check every
    # producer-to-consumer arc and direct op edge in the recovered original graph.
    local_arcs = collections.defaultdict(set)
    prior.add_graph(0, graph['ops'], graph['tensors'], graph['edges'], set(), local_arcs)
    pos = {u: i for i, u in enumerate(seq)}
    backward = [(a[1], b[1]) for a, b in local_arcs if pos[a[1]] >= pos[b[1]]]
    if backward:
        raise ValueError(f'new sequence violates local topology: {backward[0]}')
    capacity = prepared['capacity']
    if capacity != {'L1': 524288, 'UB': 131072}:
        raise ValueError('capacity differs')
    peak = prior.capacity_peak(task0, graph['edges'], seq, capacity)
    tasks, links = prepared['task_return'][:2]
    if len(tasks) != 5 or len(links) != 381:
        raise ValueError('saved task/cross-link coverage differs')
    arc_types = collections.defaultdict(set)
    vertices = set()
    local_counts = []
    pipe_counts = []
    for core in range(5):
        task = tasks[str(core)]
        edges = graph['edges'] if core == 0 else task['graph']['edges']
        memory = set() if core == 0 else {
            (e['source'], e['target']) for e in task['step3']['memory_dependencies']}
        ops, tids, prod, cons = prior.add_graph(
            core, task['graph']['ops'], task['graph']['tensors'], edges, memory, arc_types)
        vertices.update((core, u) for u in ops)
        word = seq if core == 0 else task['seq']
        if len(word) != len(ops) or set(word) != ops:
            raise ValueError(f'core{core} sequence coverage differs')
        by_id = {o['id']: o for o in task['graph']['ops']}
        pipes = collections.defaultdict(list)
        for u in word:
            pipes[by_id[u]['pipe']].append(u)
        if core and any(pipes[p] != task['pipe_ops'].get(p, []) for p in pipes):
            raise ValueError(f'core{core} saved FIFO changed')
        for pipe, ids in pipes.items():
            for a, b in zip(ids, ids[1:]):
                arc_types[((core, a), (core, b))].add('fifo:' + pipe)
        pipe_counts.append({p: len(ids) for p, ids in pipes.items()})
        local_counts.append({'core': core, 'ops': len(ops), 'tensors': len(tids),
                             'edges': len(edges), 'producer_tensor_keys': prod,
                             'consumer_tensor_keys': cons})
    for link in links:
        a = (link['source_core'], link['source_copy_out_id'])
        b = (link['target_core'], link['target_copy_in_id'])
        if a not in vertices or b not in vertices:
            raise ValueError('cross link endpoint missing')
        arc_types[(a, b)].add('cross_link')
    cycle = prior.cycle_witness(vertices, arc_types)
    copy_id = saved['pilot_copy_id']
    if copy_id != 1000004471:
        raise ValueError('pilot COPY id differs')
    mte2 = [u for u in seq if next(o for o in graph['ops'] if o['id'] == u)['pipe'] == 'PIPE_MTE2']
    seq_bytes = (json.dumps(seq, separators=(',', ':')) + '\n').encode()
    seq_hash = hashlib.sha256(seq_bytes).hexdigest()
    (HERE / 'candidate_seq.json').write_bytes(seq_bytes)
    result = {'schema': 'convex-safe-sequence-static-v1',
        'input_sha256': {k: v[1] for k, v in INPUTS.items()},
        'source_sha256': {k: hashlib.sha256(load_source(k)[1]).hexdigest() for k in SOURCES},
        'official_calls_this_process': {'Task': 0, 'Step1': 0, 'Step2': 0, 'Step3': 0, 'E0': 0, 'E1': 0, 'E2': 0},
        'old_seq_exact': True, 'old201_seq_exact': True,
        'new_local_topological': True, 'other_core_owner_schedule_fifo_unchanged': True,
        'new_core0_seq_ops': len(seq), 'new_core0_sg_count': len(new_words[0]),
        'candidate_seq_sha256': seq_hash, 'pilot_copy_id': copy_id,
        'pilot_copy_full_seq_pos': seq.index(copy_id),
        'pilot_copy_mte2_rank': mte2.index(copy_id), 'mte2_count': len(mte2),
        'capacity_interval_peak': peak,
        'capacity_sufficient_for_no_spill': all(v['within_capacity'] for v in peak.values()),
        'local_coverage': local_counts, 'pipe_counts': pipe_counts,
        'cross_links': len(links), 'joint_op_vertices': len(vertices),
        'joint_arcs': len(arc_types), 'joint_dag': cycle is None,
        'cycle_witness': cycle, 'elapsed_seconds': time.monotonic() - began,
        'limitation': 'Static necessary graph only; new core0 Step3 memory edges, issue time and official Makespan are unknown.'}
    (HERE / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'joint_dag': result['joint_dag'], 'joint_arcs': len(arc_types),
                      'pilot_copy_mte2_rank': result['pilot_copy_mte2_rank']}))


if __name__ == '__main__':
    main()
