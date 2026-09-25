"""Evaluate exactly two already frozen C02 plans after an explicit resource gate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.evaluate_feedback import monitored, dump, utc

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--raw', type=Path, required=True)
    p.add_argument('--gate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    start = time.perf_counter()  # One deadline includes identity preflight.
    mpath = HERE / 'mechanism-manifest.json'
    doc = json.loads(mpath.read_bytes())
    gate = json.loads(args.gate.read_bytes())
    assert gate['scope'] == 'c02-two-frozen-plans' and gate['status'] == 'admitted'
    assert gate['manifest_sha256'] == sha(mpath) and gate['runner_sha256'] == sha(Path(__file__))
    assert doc['limits'] == {'external_E0': 2, 'E2': 0, 'retry': 0, 'workers': 1,
        'per_process_seconds': 30, 'batch_seconds': 90, 'rss_bytes': 536870912}
    graph, config = args.raw / 'case_069.json', args.raw / 'config.txt'
    assert sha(graph) == doc['graph_sha256'] and sha(config) == doc['config_sha256']
    official_root = ROOT / 'data/raw/a/official/code'
    source = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    for record in source['files']:
        if record['path'].startswith('code/'):
            assert sha(official_root.parent / record['path']) == record['sha256']
    for candidate in doc['candidates']:
        assert sha(ROOT / candidate['path']) == candidate['sha256']
    assert len(doc['candidates']) == 2
    assert time.perf_counter() < start + 90, 'Preflight exhausted the batch deadline'
    args.output.mkdir(exist_ok=False)
    ledger = {'status': 'running', 'started_at': utc(), 'external_E0_started': 0,
              'E2': 0, 'retry': 0, 'rows': [], 'gate_sha256': sha(args.gate),
              'runner_sha256': sha(Path(__file__)), 'manifest_sha256': sha(mpath)}
    try:
        for i, candidate in enumerate(doc['candidates']):
            assert time.perf_counter() < start + 90
            folder = args.output / str(i)
            folder.mkdir()
            ledger['external_E0_started'] += 1
            dump(args.output / 'ledger.json', ledger)
            argv = [sys.executable, '-B', str(official_root / 'multicore_cut_evaluate_problem_2.py'),
                str(graph), str(ROOT / candidate['path']), '--config', str(config),
                '--output', str(folder / 'result.json'), '--trace-output', str(folder / 'trace.json'),
                '--log-output', str(folder / 'official.log')]
            process = monitored(argv, folder / 'process', min(start + 90, time.perf_counter() + 30), 536870912)
            row = {'candidate': i, 'plan_sha256': candidate['sha256'], 'process': process}
            ledger['rows'].append(row)
            assert process['status'] == 'ok' and not process['surviving_pids']
            result = json.loads((folder / 'result.json').read_bytes())
            assert result['scene'] == 'B' and result['num_cores'] == 5
            row.update(makespan=result['makespan'], data_movement_bytes=result['data_movement_bytes'],
                       result_sha256=sha(folder / 'result.json'))
            dump(args.output / 'ledger.json', ledger)
        ledger['status'] = 'completed'
    except BaseException as error:
        ledger.update(status='stopped', error=repr(error))
        raise
    finally:
        ledger.update(finished_at=utc(), wall_seconds=time.perf_counter()-start)
        dump(args.output / 'ledger.json', ledger)

if __name__ == '__main__':
    main()
