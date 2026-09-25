"""One-shot official preparation observer for frozen 044/K5 partial preload.

Run only under the admitted supervisor. No P2, P3 or E0 scoring occurs here.
Tracing adds diagnostic overhead and is not solver timing.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import copy
import gzip
import json
from pathlib import Path
import re
import sys
import time

from .feedback_benchmark import digest, read, utc, verify_source, write

ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = (ROOT / 'results/a/q3-nikolastarx').resolve()
ARTIFACTS = {'case_044_multicore_res.json', 'predicted-words.json',
             'expected-prefixes.json', 'facts.json'}
REFERENCES = {'case_044_multicore_res.json', 'snapshots.json.gz',
              'certificate.json', 'summary.json'}
BUDGET = {'workers': 1, 'max_prepare': 1, 'max_P3': 1, 'max_P2': 2,
          'max_E0': 3, 'per_phase_seconds': 90, 'total_seconds': 600,
          'memory_limit_bytes': 536870912, 'retries': 0}
HEX = re.compile(r'[0-9a-f]{64}\Z')


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if isinstance(value, set):
        return [serializable(v) for v in sorted(value)]
    return value


def _safe_reference(name):
    if (not isinstance(name, str) or not name.startswith('results/a/q3-nikolastarx/')
            or '\\' in name or ':' in name or '..' in name.split('/')):
        raise ValueError('unsafe reference path')
    path = (ROOT / name).resolve(strict=True)
    path.relative_to(RESULT_ROOT)
    return path


def load_candidate(directory, manifest_sha256):
    """Check all bytes before importing or calling frozen official code."""
    source = Path(directory).resolve(strict=True)
    source.relative_to(RESULT_ROOT)
    manifest_path = source / 'manifest.json'
    if not HEX.fullmatch(manifest_sha256) or digest(manifest_path) != manifest_sha256:
        raise ValueError('manifest byte identity differs')
    m = read(manifest_path)
    required = {'schema', 'case_id', 'cores', 'changed_core', 'head_count',
                'budget', 'artifacts', 'references', 'source_input_sha256'}
    if (type(m) is not dict or set(m) != required
            or m['schema'] != 'q3-partial-preload-v1' or m['case_id'] != '044'
            or type(m['cores']) is not int or m['cores'] != 5
            or type(m['changed_core']) is not int or m['changed_core'] != 2
            or type(m['head_count']) is not int or m['head_count'] != 15
            or type(m['budget']) is not dict or m['budget'] != BUDGET
            or any(type(m['budget'][name]) is not int for name in BUDGET)):
        raise ValueError('partial candidate contract differs')
    if type(m['artifacts']) is not dict or set(m['artifacts']) != ARTIFACTS:
        raise ValueError('candidate artifact set differs')
    for name, expected in m['artifacts'].items():
        if not isinstance(expected, str) or not HEX.fullmatch(expected) or digest(source / name) != expected:
            raise ValueError('candidate artifact byte identity differs: ' + name)
    refs = m['references']
    if type(refs) is not dict or {Path(n).name for n in refs} != REFERENCES or len(refs) != 4:
        raise ValueError('reference artifact set differs')
    ref_paths = {}
    for name, expected in refs.items():
        path = _safe_reference(name)
        if not isinstance(expected, str) or not HEX.fullmatch(expected) or digest(path) != expected:
            raise ValueError('reference byte identity differs: ' + name)
        ref_paths[path.name] = path
    if len({path.parent for path in ref_paths.values()}) != 1:
        raise ValueError('references span more than one static directory')
    static = read(ref_paths['summary.json'])
    if static.get('status') != 'complete':
        raise ValueError('static summary or input identities differ')
    if any(static.get('artifacts', {}).get(name) != refs[str(path.relative_to(ROOT))]
           for name, path in ref_paths.items() if name != 'summary.json'):
        raise ValueError('static artifact identities differ')
    for name, expected in m['source_input_sha256'].items():
        if (not isinstance(name, str) or not name.startswith('data/raw/a/official/')
                or '..' in name.split('/') or '\\' in name or ':' in name
                or not isinstance(expected, str) or not HEX.fullmatch(expected)
                or digest(ROOT / name) != expected):
            raise ValueError('official input byte identity differs: ' + str(name))
    frozen = {name: sha for name, sha in static.get('source_input_sha256', {}).items()
              if name.startswith('data/raw/a/official/')}
    if m['source_input_sha256'] != frozen:
        raise ValueError('candidate and static frozen input identities differ')
    plan = read(source / 'case_044_multicore_res.json')
    if set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('candidate plan fields differ')
    predicted = read(source / 'predicted-words.json')
    prefixes = read(source / 'expected-prefixes.json')
    with gzip.open(ref_paths['snapshots.json.gz'], 'rt') as stream:
        snapshots = json.load(stream)
    certificate = read(ref_paths['certificate.json'])
    return m, plan, predicted, prefixes, snapshots, certificate


def audit_prepared(tasks, links, intermediates, predicted, prefixes, snapshots, certificate, traffic):
    """Pure audit over captured official results; raises on any failed guard."""
    if (not isinstance(tasks, dict) or set(tasks) != set(range(5))
            or set(predicted) != {str(c) for c in range(5)} or set(prefixes) != set(predicted)):
        raise ValueError('core coverage differs')
    if len(intermediates['Step1']) != 5 or len(intermediates['Step2']) != 5 or len(intermediates['Step3']) != 5:
        raise ValueError('intermediate coverage differs')
    if traffic['spill_added_copy_bytes']:
        raise ValueError('official preparation introduced spill bytes')
    original = {str(r['core']): r['prefix_copy_ids'] for r in certificate['cores']}
    if any(prefixes[str(c)] != (original[str(c)][:6] if c == 2 else original[str(c)])
           for c in range(5)):
        raise ValueError('prefix contract differs from original')
    nodes = set()
    successors = defaultdict(set)
    rows = []
    old_projection = []
    new_projection = []
    for c in range(5):
        task = tasks[c]
        key = str(c)
        base = snapshots['candidate'][key]['graph']
        step1_graph = intermediates['Step1'][c]['graph']
        if any(step1_graph[k] != base[k] for k in ('ops', 'tensors', 'edges')):
            raise ValueError(f'core {c} original Task/COPY graph differs')
        old_projection.extend((c, u['id']) for u in base['ops'] if u['op'] not in {'COPY_IN', 'COPY_OUT'})
        new_projection.extend((c, u['id']) for u in step1_graph['ops'] if u['op'] not in {'COPY_IN', 'COPY_OUT'})
        result2 = intermediates['Step2'][c]
        if (result2['seq'] != predicted[key] or result2['result']['spill_records']
                or task['seq'] != predicted[key]):
            raise ValueError(f'core {c} predicted pre-Step2, no-spill or extended sequence differs')
        ids = set(task['op_by_id'])
        if ids != set(task['seq']) or len(ids) != len(task['seq']):
            raise ValueError(f'core {c} prepared operation coverage differs')
        nodes.update((c, u) for u in ids)
        prefix = prefixes[key]
        prefix_set = set(prefix)
        mte2 = task['pipe_ops']['PIPE_MTE2']
        if mte2[:len(prefix)] != prefix or len(prefix) != len(prefix_set):
            raise ValueError(f'core {c} cold prefix changed')
        for u in prefix:
            if u not in ids or task['op_by_id'][u]['op'] != 'COPY_IN':
                raise ValueError(f'core {c} prefix is not original COPY_IN')
            if not set(task['op_preds'][u]) <= prefix_set:
                raise ValueError(f'core {c} outside local predecessor reaches cold prefix')
        if any(d['target'] in prefix_set for d in task['step3']['memory_dependencies']):
            raise ValueError(f'core {c} memory reuse enters cold prefix')
        if c == 2:
            activations = {l['target_copy_in_id'] for l in links if l['target_core'] == c}
            position = min((mte2.index(u) for u in activations if u in mte2), default=len(mte2))
            if position < 6:
                raise ValueError('core 2 activation precedes six original cold reads')
        for target, preds in task['op_preds'].items():
            for source in preds:
                successors[(c, source)].add((c, target))
        for order in task['pipe_ops'].values():
            for source, target in zip(order, order[1:]):
                successors[(c, source)].add((c, target))
        for dep in task['step3']['memory_dependencies']:
            successors[(c, dep['source'])].add((c, dep['target']))
        rows.append({'core': c, 'operations': len(ids), 'prefix': prefix,
                     'memory_dependencies': len(task['step3']['memory_dependencies'])})
    if old_projection != new_projection:
        raise ValueError('all-core compute projection differs')
    for link in links:
        source = (link['source_core'], link['source_copy_out_id'])
        target = (link['target_core'], link['target_copy_in_id'])
        if link['target_copy_in_id'] in prefixes[str(link['target_core'])]:
            raise ValueError('crosslink enters cold prefix')
        successors[source].add(target)
    indegree = dict.fromkeys(nodes, 0)
    for source, targets in successors.items():
        if source not in nodes or not targets <= nodes:
            raise ValueError('prepared graph edge endpoint missing')
        for target in targets:
            indegree[target] += 1
    queue = deque(u for u, degree in indegree.items() if degree == 0)
    seen = 0
    while queue:
        source = queue.popleft()
        seen += 1
        for target in successors[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if seen != len(nodes):
        raise ValueError('full prepared union DAG has a cycle')
    return {'cores': rows, 'union_dag': {'ops': seen, 'edges': sum(map(len, successors.values()))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    m, plan, predicted, prefixes, snapshots, certificate = load_candidate(
        args.candidate, args.manifest_sha256)
    official, inputs = verify_source(args.source, {'044'})
    if {name: sha for name, sha in inputs.items()
        if name.startswith('data/raw/a/official/')} != m['source_input_sha256']:
        raise ValueError('official source inputs differ from manifest')
    out = args.output.resolve()
    out.relative_to(RESULT_ROOT)
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config, validate_execution
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    from schedule_step1 import step1_schedule
    from schedule_step2 import step2_spill_insertion
    from schedule_step3 import prepare_step3_execution
    watched = {step1_schedule.__code__: 'Step1',
               step2_spill_insertion.__code__: 'Step2',
               prepare_step3_execution.__code__: 'Step3',
               _build_scene_b_tasks.__code__: 'Task'}
    counts = dict.fromkeys(watched.values(), 0)
    intermediates = {name: [] for name in ('Step1', 'Step2', 'Step3')}
    state = {'status': 'running', 'started_at': utc(), 'source_commit': args.source,
             'official_code_sha256': official, 'source_input_sha256': inputs,
             'manifest_sha256': args.manifest_sha256, 'counts_started': counts,
             'new_P2': 0, 'new_P3': 0, 'new_E0': 0}
    write(out / 'run.json', state)

    def observer(frame, event, value):
        name = watched.get(frame.f_code)
        if name is None:
            return
        if event == 'call':
            counts[name] += 1
            write(out / 'run.json', state)
            if counts[name] > (1 if name == 'Task' else 5):
                raise RuntimeError('official preparation invocation limit exceeded')
        elif event == 'return' and name in intermediates:
            record = {'result': copy.deepcopy(value)}
            if name == 'Step1':
                record['graph'] = copy.deepcopy(frame.f_locals['graph_json'])
            elif name == 'Step2':
                record['seq'] = list(frame.f_locals['seq'])
            intermediates[name].append(record)

    start = time.perf_counter()
    try:
        graph = read(ROOT / 'data/raw/a/official/data/case_044.json')
        cfg = read_evaluation_config(ROOT / 'data/raw/a/official/data/config.txt')
        old_profile = sys.getprofile()
        if old_profile is not None:
            raise RuntimeError('unexpected existing profiler')
        try:
            sys.setprofile(observer)
            tasks, links, cross_bytes, traffic, plan_view = _build_scene_b_tasks(graph, plan, **cfg)
        finally:
            sys.setprofile(old_profile)
        if counts != {'Step1': 5, 'Step2': 5, 'Step3': 5, 'Task': 1}:
            raise ValueError('unexpected official preparation count')
        payload = serializable({'tasks': tasks, 'cross_links': links,
                                'cross_task_traffic': cross_bytes, 'traffic': traffic,
                                'plan_view': plan_view, 'intermediates': intermediates})
        (out / 'prepared.json.gz').write_bytes(gzip.compress(
            json.dumps(payload, separators=(',', ':')).encode(), mtime=0))
        state['prepared_sha256'] = digest(out / 'prepared.json.gz')
        validate_execution(tasks, links)
        state['audit'] = audit_prepared(tasks, links, intermediates, predicted,
                                        prefixes, snapshots, certificate, traffic)
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state.update(finished_at=utc(), diagnostic_wall_seconds=time.perf_counter() - start)
        write(out / 'run.json', state)
    print(json.dumps({'status': state['status'], 'counts': counts, 'audit': state['audit']}))


if __name__ == '__main__':
    main()
