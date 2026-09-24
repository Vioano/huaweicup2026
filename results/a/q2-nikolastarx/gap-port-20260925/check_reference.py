"""Synthetic equivalence check against fixed Fang constructor; zero evaluation."""
from pathlib import Path
import hashlib
import json
import random
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx import gap_calendar, gap_candidate
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import derive_multicore_plan

SOURCE = '71616ac7c4c7fca56e37e2d3245dd13725316d82'
CONFIG = {'bandwidth': 60, 'cross_core_copy_delay_cycles': 500}


def main():
    raw = subprocess.check_output(['git', 'show', SOURCE + ':src/q2/feedback/gap_packet.py'], cwd=ROOT)
    calendar = subprocess.check_output(['git', 'show', SOURCE + ':src/q2/feedback/gap_calendar.py'], cwd=ROOT)
    assert calendar == Path(gap_calendar.__file__).read_bytes()
    # Isolate the original function from its CLI and unrelated fallback imports.
    prefix = '_frozen_fang_gap'
    package = types.ModuleType(prefix)
    package.__path__ = []
    sys.modules[prefix] = package
    def no_fallback(*args, **kwargs):
        raise AssertionError('Unexpected fallback in guarded synthetic fixture')
    for name, members in {
        'capacity_window': {'build': no_fallback},
        'construct': {'ROOT': ROOT, 'derive_multicore_plan': derive_multicore_plan},
        'tensor_packet': {'TensorIndex': object},
    }.items():
        module = types.ModuleType(prefix + '.' + name)
        module.__dict__.update(members)
        sys.modules[module.__name__] = module
    sys.modules[prefix + '.gap_calendar'] = gap_calendar
    reference = types.ModuleType(prefix + '.gap_packet')
    reference.__package__ = prefix
    exec(compile(raw, 'frozen_fang_gap_packet.py', 'exec'), reference.__dict__)
    checked = []
    for seed in range(20):
        rng = random.Random(seed)
        edges = {(0, 1), (0, 2), (1, 3), (2, 3)}
        edges |= {(u, v) for u in range(10) for v in range(u + 1, 10) if rng.random() < .15}
        graph = {'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': rng.choice(['PIPE_M', 'PIPE_V']),
                          'cycles': rng.randint(1, 50)} for u in range(10)],
                 'tensors': [], 'edges': []}
        for i, (u, v) in enumerate(sorted(edges)):
            tid = 1000 + i
            graph['tensors'].append({'id': tid, 'pos': 'UB', 'size': rng.randint(1, 256)})
            graph['edges'] += [{'source': u, 'target': tid}, {'source': tid, 'target': v}]
        index = DAGIndex(graph)
        index.producer = {tid: next(iter(ps)) for tid, ps in index.producers.items() if ps}
        index.direct = {u: tuple((None, p, size) for p, size in ps)
                        for u, ps in index.direct_inputs.items()}
        for cores in (1, 2, 5):
            original, _ = reference.build(index, cores, 60, 500, {'UB': 131072, 'L1': 524288})
            adapted, detail = gap_candidate.build(graph, cores, CONFIG)
            assert adapted == original, (seed, cores)
            assert detail['arithmetic_placement_choices'] <= detail['choice_bound']
            checked.append({'seed': seed, 'cores': cores,
                            'plan_sha256': hashlib.sha256(json.dumps(adapted).encode()).hexdigest()})
    result = {'reference_commit': SOURCE, 'reference_source_sha256': hashlib.sha256(raw).hexdigest(),
              'candidate_source_sha256': hashlib.sha256(Path(gap_candidate.__file__).read_bytes()).hexdigest(),
              'calendar_sha256': hashlib.sha256(calendar).hexdigest(),
              'synthetic_plan_pairs': len(checked), 'pairs': checked,
              'E0_E1_E2_calls': 0,
              'scope': 'Guarded synthetic tensor DAGs only, original placement function with a DAGIndex field adapter. Not full fallback equivalence, official performance, or memory feasibility.'}
    with Path(__file__).with_name('reference-check.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ['synthetic_plan_pairs', 'E0_E1_E2_calls', 'candidate_source_sha256']}))


if __name__ == '__main__':
    main()
