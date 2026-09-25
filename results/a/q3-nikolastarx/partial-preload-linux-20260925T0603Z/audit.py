"""Read saved original results only; never imports or calls an evaluator."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROBE = HERE / 'extracted/probe'
OLD = ROOT / 'results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public'
NEW = ROOT / 'results/a/q3-nikolastarx/partial-preload-one-20260925'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def main():
    run = read(PROBE / 'run.json')
    assert run['status'] == 'complete'
    assert run['source_commit'] == '817e9e399f5efaf66cea6ddc495fe444950e43f2'
    assert run['reservations'] == ['prepare', 'candidate-p3', 'candidate-p2', 'control-p2']
    plans = {'candidate': NEW / 'case_044_multicore_res.json',
             'control': OLD / 'artifacts/case_044_multicore_res.json'}
    result, counts = {}, {}
    for phase in run['reservations'][1:]:
        worker = read(PROBE / (phase + '.worker.json'))
        path = PROBE / (phase + '.json.gz')
        assert worker['status'] == 'complete'
        assert sha(path) == worker['result_sha256']
        assert sha(plans[phase.split('-')[0]]) == worker['plan_sha256']
        result[phase] = read(path)
        assert result[phase]['num_cores'] == 5
        for key, value in worker['counts_started'].items():
            counts[key] = counts.get(key, 0) + value
    prepared = read(PROBE / 'prepare/run.json')
    assert prepared['status'] == 'complete'
    assert sha(PROBE / 'prepare/prepared.json.gz') == prepared['prepared_sha256']
    for key in ('Step1', 'Step2'):
        counts[key] += prepared['counts_started'][key]
    counts['prepare_Step3'] += prepared['counts_started']['Step3']
    counts['diagnostic_Task_prepare'] = prepared['counts_started']['Task']
    old_path = OLD / 'artifacts/044-result.json.gz'
    assert sha(old_path) == run['control_result_sha256']
    result['control-p3'] = read(old_path)
    candidate, control = result['candidate-p3'], result['control-p3']
    assert candidate['data_movement_bytes'] == control['data_movement_bytes']
    assert candidate['cache_stats'] == control['cache_stats']
    assert candidate['makespan'] == run['candidate_M'] == 37060
    assert control['makespan'] == run['control_M'] == 38024
    assert run['candidate_G'] == result['candidate-p2']['makespan'] / candidate['makespan']
    assert run['control_G'] == result['control-p2']['makespan'] / control['makespan']
    core_deltas = []
    for a, b in zip(control['per_core_timeline'], candidate['per_core_timeline']):
        assert a['core_id'] == b['core_id']
        identity = lambda c: sorted((o['op_id'], o['op'], o['pipe']) for o in c['ops'])
        assert identity(a) == identity(b)
        for pipe in ('PIPE_M', 'PIPE_V'):
            word = lambda c: [o['op_id'] for o in sorted(c['ops'], key=lambda x: (x['start'], x['op_id'])) if o['pipe'] == pipe]
            assert word(a) == word(b)
        first_compute = lambda c: min(o['start'] for o in c['ops'] if o['pipe'] in ('PIPE_M', 'PIPE_V'))
        end = lambda c: max(o['end'] for o in c['ops'])
        core_deltas.append({'core': a['core_id'], 'control_first_compute': first_compute(a),
                            'candidate_first_compute': first_compute(b), 'control_end': end(a),
                            'candidate_end': end(b)})
    report = {'scope': 'saved-byte/hash/numeric audit; zero new official calls, no independent rerun',
              'source_commit': run['source_commit'], 'artifact_sha256': sha(HERE / 'evidence.tar.gz'),
              'calls': counts, 'prepare_dag': prepared['audit']['union_dag'],
              'control_M': control['makespan'], 'candidate_M': candidate['makespan'],
              'cycles_saved': control['makespan'] - candidate['makespan'],
              'relative_cycle_reduction': 1 - candidate['makespan'] / control['makespan'],
              'candidate_G': run['candidate_G'], 'control_G': run['control_G'],
              'unchanged_data_movement': candidate['data_movement_bytes'],
              'unchanged_cache_stats': candidate['cache_stats'], 'per_core': core_deltas,
              'host_wall_seconds': read(HERE / 'control.json')['wall_seconds'],
              'solver_wall_seconds': None, 'full500_result': False}
    (HERE / 'INDEPENDENT_AUDIT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
