"""One bounded E0 pass over six frozen C04 plans; no online solver or E2."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.evaluate_feedback import dump, monitored, utc

LIMITS = {'external_E0': 6, 'E1': 0, 'E2': 0, 'retry': 0, 'workers': 1,
          'per_process_seconds': 30, 'batch_seconds': 240, 'rss_bytes': 1073741824}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(manifest, commit):
    doc = json.loads(manifest.read_bytes())
    require(doc['scope'] == 'c04-six-frozen-plans' and doc['limits'] == LIMITS,
            'scope/limits mismatch')
    cells = doc['candidates']
    require(len(cells) == 6 and len({(c['case'], c['cores']) for c in cells}) == 6,
            'six unique coordinates required')
    pinned = {manifest.relative_to(ROOT).as_posix(): sha(manifest),
              Path(__file__).relative_to(ROOT).as_posix(): sha(Path(__file__))}
    pinned.update(doc['source_sha256'])
    for row in cells:
        pinned[row['plan_path']] = row['plan_sha256']
        for item in row['control_artifacts']:
            require(sha(ROOT / item['path']) == item['sha256'], 'control artifact changed')
    for rel, digest in pinned.items():
        require(sha(ROOT / rel) == digest, 'local source/plan changed: ' + rel)
        original = subprocess.check_output(['git', 'show', f'{commit}:{rel}'], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == digest,
                'commit source/plan mismatch: ' + rel)
    official = ROOT / 'data/raw/a/official'
    source = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    for record in source['files']:
        if record['path'].startswith('code/'):
            require(sha(official / record['path']) == record['sha256'], 'official source changed')
    require(sha(official / 'data/config.txt') == doc['config_sha256'], 'config changed')
    archive = ROOT / 'data/raw/a/official-cases.zip'
    require(sha(archive) == doc['official_zip_sha256'], 'official graph archive changed')
    with zipfile.ZipFile(archive) as z:
        for row in cells:
            graph = z.read(f"data/case_{row['case']}.json")
            require(hashlib.sha256(graph).hexdigest() == row['graph_sha256'], 'graph changed')
    return doc


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--gate', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = args.manifest.absolute()
    doc = validate(manifest, args.commit)
    if args.preflight_only:
        print(json.dumps({'preflight': 'passed', 'coordinates': 6, 'E0': 0,
                          'E1': 0, 'E2': 0, 'manifest_sha256': sha(manifest)}))
        return
    require(args.gate is not None and args.output is not None, 'gate/output required')
    gate = json.loads(args.gate.read_bytes())
    require(gate['scope'] == doc['scope'] and gate['status'] == 'admitted', 'not admitted')
    require(gate['manifest_sha256'] == sha(manifest), 'gate manifest changed')
    require(gate['runner_sha256'] == sha(Path(__file__)), 'gate runner changed')
    expiry = datetime.fromisoformat(gate['expires_at'].replace('Z', '+00:00'))
    require(expiry.tzinfo is not None and datetime.now(timezone.utc) < expiry, 'gate expired')
    out = args.output.absolute()
    require(out == ROOT / doc['output_path'], 'unexpected output directory')
    require(time.perf_counter() < started + LIMITS['batch_seconds'], 'preflight deadline')
    out.mkdir(parents=True, exist_ok=False)
    ledger = {'scope': doc['scope'], 'status': 'running', 'started_at': utc(),
              'source_commit': args.commit, 'gate_sha256': sha(args.gate),
              'manifest_sha256': sha(manifest), 'runner_sha256': sha(Path(__file__)),
              'external_E0_started': 0, 'E1': 0, 'E2': 0, 'retry': 0, 'rows': [],
              'timing_scope': 'External E0 only; plans were constructed offline for mechanism falsification.'}
    official = ROOT / 'data/raw/a/official'
    try:
        with zipfile.ZipFile(ROOT / 'data/raw/a/official-cases.zip') as archive:
            for candidate in doc['candidates']:
                require(time.perf_counter() < started + LIMITS['batch_seconds'], 'batch deadline')
                folder = out / f"{candidate['case']}-k{candidate['cores']}"
                folder.mkdir()
                graph = folder / 'graph.json'
                graph.write_bytes(archive.read(f"data/case_{candidate['case']}.json"))
                plan = ROOT / candidate['plan_path']
                require(sha(plan) == candidate['plan_sha256'], 'plan changed before dispatch')
                row = {'case': candidate['case'], 'cores': candidate['cores'], 'status': 'running',
                       'control_makespan': candidate['control_makespan'],
                       'plan_sha256': sha(plan), 'graph_sha256': sha(graph)}
                ledger['rows'].append(row)
                ledger['external_E0_started'] += 1
                dump(out / 'ledger.json', ledger)
                argv = [sys.executable, '-B', str(official / 'code/multicore_cut_evaluate_problem_2.py'),
                        str(graph), str(plan), '--config', str(official / 'data/config.txt'),
                        '--output', str(folder / 'result.json'),
                        '--trace-output', str(folder / 'trace.json'),
                        '--log-output', str(folder / 'official.log')]
                process = monitored(argv, folder / 'process',
                    min(started + LIMITS['batch_seconds'], time.perf_counter() + LIMITS['per_process_seconds']),
                    LIMITS['rss_bytes'])
                row['process'] = process
                require(process['status'] == 'ok' and not process['surviving_pids'],
                        'official process failed, timed out, exceeded memory or survived cleanup')
                result = json.loads((folder / 'result.json').read_bytes())
                require(result['scene'] == 'B' and result['num_cores'] == candidate['cores'],
                        'official coordinate mismatch')
                row.update(status='ok', makespan=result['makespan'],
                           data_movement_bytes=result['data_movement_bytes'],
                           result_sha256=sha(folder / 'result.json'))
                movement = result['data_movement_bytes']
                require(movement['spill_added_copy_bytes'] == 0, 'zero-spill certificate mismatch')
                require(movement['scheduled_copy_bytes'] == candidate['static_copy_bytes'],
                        'static versus official COPY byte mismatch')
                dump(out / 'ledger.json', ledger)
                print(json.dumps({'case': row['case'], 'makespan': row['makespan'],
                                  'control_makespan': row['control_makespan']}), flush=True)
        ledger['status'] = 'completed'
    except BaseException as error:
        ledger.update(status='stopped', error=repr(error))
        if ledger['rows']:
            ledger['rows'][-1]['status'] = 'stopped'
        raise
    finally:
        ledger.update(finished_at=utc(), wall_seconds=time.perf_counter() - started)
        dump(out / 'ledger.json', ledger)


if __name__ == '__main__':
    main()
