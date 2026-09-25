"""Frozen two-case pure static probe; see FROZEN.md before execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from src.q3 import layered_query_flow as layered
from src.q3.construct import derive_multicore_plan

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'data/raw/a/official/data'
EXPECTED = {
    '068': 'dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d',
    '088': '2ff71575ba33875431f54823fc1f2214e018edcfc9d568edfb7c47b0f264b825',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')

def original_partition():
    source = subprocess.check_output(['git', 'show', 'HEAD:src/q3/layered_query_flow.py'], cwd=ROOT, text=True)
    node = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == 'partition_tracks')
    namespace = dict(layered.__dict__)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<frozen-original-partition>', 'exec'), namespace)
    return namespace['partition_tracks']

receipt = {'constructor_calls': 0, 'derive_multicore_plan_calls': 0,
           'Task_calls': 0, 'Step_calls': 0, 'E0_E1_E2_calls': 0,
           'retry_count': 0, 'cases': [], 'status': 'STARTED'}
save('receipt.json', receipt)
try:
    pairs = [(9, 1), (3, 7), (4, 4), (1, 8)]
    ops = {2*i+j: {'pipe': ('PIPE_M', 'PIPE_V')[j], 'cycles': pair[j]}
           for i, pair in enumerate(pairs) for j in range(2)}
    private = {2*i+j: i for i in range(4) for j in range(2)}
    toy = SimpleNamespace(ops=ops, duration=lambda u: ops[u]['cycles'])
    for k in (1, 2, 3, 4):
        assert layered.partition_tracks(toy, private, 4, k) == original_partition()(toy, private, 4, k)
    receipt['toy_r_ge_K_byte_equivalent'] = True
    save('receipt.json', receipt)

    for case in ('068', '088'):
        path = DATA / f'case_{case}.json'
        raw = path.read_bytes()
        assert sha(raw) == EXPECTED[case]
        graph = json.loads(raw)
        record = {'case': case, 'graph_sha256': sha(raw), 'requested_cores': 5,
                  'capacity': {'L1': 524288, 'UB': 131072}, 'cross_delay_cycles': 500}
        receipt['cases'].append(record)
        receipt['constructor_calls'] += 1
        save('receipt.json', receipt)
        plan, meta, evidence = layered.construct_layered(
            graph, 5, capacity=record['capacity'], cross_delay_cycles=500)
        assert len(plan['core_schedules']) == 5
        assert set(plan) == {'node_to_subgraph', 'core_schedules'}
        assert len(evidence['ownership']) == len(plan['node_to_subgraph'])
        assert len({row['op'] for row in evidence['ownership']}) == len(evidence['ownership'])
        assert len({row['op'] for row in evidence['ownership'] if row['core'] is not None}) == len(evidence['ownership'])
        assert meta['memory']['step2_no_spill_certificate']
        assert meta['whole_path_envelope']['max_remote_edges'] <= meta['layers'] + 1
        receipt['derive_multicore_plan_calls'] += 1
        save('receipt.json', receipt)
        view = derive_multicore_plan(graph, plan)
        assert len(view['core_orders']) == 5
        plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
        (OUT / f'case_{case}_K5_plan.json').write_bytes(plan_bytes)
        save(f'case_{case}_K5_metadata.json', meta)
        record.update(status='STATIC_CONSTRUCTED_DERIVED', plan_sha256=sha(plan_bytes),
                      tracks=len(meta['tracks']), selected_groups=meta['selected_groups'],
                      per_core_schedule_lengths=list(map(len, plan['core_schedules'])),
                      per_core_M_V_work=meta['core_pipe_work_M_V'],
                      compute_fifo_Ldelta=meta['compute_mv_fifo']['Ldelta'],
                      whole_path_Ldelta=meta['whole_path_envelope']['Ldelta'],
                      fixed_plan_lower_bound_cycles=meta['compute_mv_fifo']['Ldelta'],
                      fixed_plan_lower_bound_scope='Original compute dependencies plus per-core M/V FIFO and 500-cycle remote compute edges; excludes COPY/DDR/cache/memory-edge service',
                      capacity_peak_bytes=meta['memory']['bucket_frontier_peaks'])
        save('receipt.json', receipt)
    receipt['status'] = 'COMPLETED_STATIC_ONLY'
except Exception as exc:
    receipt['status'] = 'STOPPED_FIRST_EXCEPTION'
    receipt['exception'] = f'{type(exc).__name__}: {exc}'
    if receipt['cases']:
        receipt['cases'][-1]['status'] = 'FAILED'
    raise
finally:
    save('receipt.json', receipt)
