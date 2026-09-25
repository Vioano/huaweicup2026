"""Pure JSON audit of this run's saved Fraction traces; no model or evaluator calls."""
import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/review'))
from p1_saved_trace_causal_audit import audit

SOURCE = 'results/a/p1-r5-phase-colab-20260925/run-0717Z/evidence.tar.gz'
SHA = '215c6f501a4f5ed835c20411b7f809605b0247cbbe11902c25ff88901b233d9b'
A = 'results/a/p1-r5-local-audit-20260925/traces/whole_seed-audit.json'
A_SHA = '6f1a7f8ebd027253a3d0480440c673ff0111df0c15c2eafbc15a014213fe87b6'

def union(intervals):
    total = lo = hi = 0
    for start, end in sorted(intervals):
        if start > hi:
            total += hi - lo
            lo, hi = start, end
        else:
            hi = max(hi, end)
    return total + hi - lo

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; refusing overwrite')
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SHA:
        raise ValueError('source archive SHA mismatch')
    a_path = ROOT / A
    if hashlib.sha256(a_path.read_bytes()).hexdigest() != A_SHA:
        raise ValueError('A audit SHA mismatch')
    a_saved = json.loads(a_path.read_text())
    with tarfile.open(args.source) as bundle:
        base = 'workspace/evidence/r5-008-k5/'
        data = json.load(bundle.extractfile(base + 'diagnostics.json'))
        plans = {name: json.load(bundle.extractfile(base + name + '-plan.json')) for name in ('control', 'phase')}
    result = {'kind': 'LOCAL_COLAB_SAVED_FRACTION_TRACE_STATIC_AUDIT_NOT_RERUN_NOT_E0',
              'source_archive': SOURCE, 'source_archive_sha256': SHA,
              'A_reference': {'path': A, 'sha256': A_SHA, 'makespan': a_saved['makespan'],
                              'decomposition': a_saved['decomposition']},
              'calls_this_audit': {'Task_compile': 0, 'Fraction_simulate': 0, 'E0': 0, 'E1': 0, 'E2': 0}, 'modes': {}}
    for name in ('control', 'phase'):
        model = data[name + '_model']
        schedules = plans[name]['core_schedules']
        owner = {task: core for core, line in enumerate(schedules) for task in line}
        tasks = [{'task_id': int(task), 'core': owner[int(task)],
                  'ports': [[[op['work'], op['ddr'], op['need']] for op in port] for port in ports]}
                 for task, ports in data['compiled_ports'].items()]
        checked = audit(tasks, schedules, data['parameters']['gate'], model['trace'],
                        model['task_intervals'], model['makespan'])
        cores = []
        for core, line in enumerate(schedules):
            trace = [op for op in model['trace'] if op['core'] == core]
            intervals = sorted((item for item in model['task_intervals'] if item['core'] == core),
                               key=lambda item: item['start'])
            m = sum(op['end']-op['start'] for op in trace if op['pipe'] == 'PIPE_M')
            v = sum(op['end']-op['start'] for op in trace if op['pipe'] == 'PIPE_V')
            both = union((op['start'], op['end']) for op in trace if op['pipe'] in ('PIPE_M', 'PIPE_V'))
            cores.append({'core': core, 'M_busy': m, 'V_busy': v, 'M_V_overlap': m+v-both,
                          'DDR_union_on_core': union((op['start'], op['end']) for op in trace if op['ddr']),
                          'gate_gaps': [intervals[i]['start']-intervals[i-1]['end'] for i in range(1,len(intervals))],
                          'last_two_tasks': intervals[-2:], 'finish': intervals[-1]['end']})
        result['modes'][name] = {'makespan': model['makespan'],
                                 'global_DDR_union': union((op['start'], op['end']) for op in model['trace'] if op['ddr']),
                                 'cores': cores, 'observed_duration_DAG': {key: checked[key] for key in
                                    ('status','observed_duration_DAG_longest','unexplained_gap','decomposition','max_operation_start_slack','checked_operations')},
                                 'critical_chain_last_8': checked['critical_chain'][-8:]}
    result['comparison'] = {'phase_minus_control': result['modes']['phase']['makespan']-result['modes']['control']['makespan'],
                            'phase_minus_A': result['modes']['phase']['makespan']-a_saved['makespan'],
                            'phase_minus_threshold': result['modes']['phase']['makespan']-data['parameters']['threshold']}
    result['tail_scope'] = 'Core 2 Task 32 is remainder tail1 after reserve7 and body14; reserved Tasks are 22..28.'
    result['limitation'] = 'Saved-trace algebra only; DDR fairness, E0 score and counterfactual tail cost unverified.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')

if __name__ == '__main__':
    main()
