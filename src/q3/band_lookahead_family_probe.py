"""One structural band/lookahead proposal on the entire recognized 50-cell family.

Historical controls and two exact candidate results are reused by byte identity.
This is mechanism evidence, not a fresh solver or a full500 algorithm score.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import time

from .band_lookahead import construct
from .construct import ROOT, Index, UnsupportedStructure
from .feedback_benchmark import digest, git_bytes, read, utc, verify_source, write
from .leaf_lookahead_probe import FOREST_COMMIT
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded
from evaluation_validation import read_required_settings

COVERAGE = 'results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json'
HISTORY = 'results/a/q3-nikolastarx/leaf-lookahead-probe-20260925/run.json'
BUDGET = {'family_coordinates': 50, 'new_p3_max': 49, 'new_p2': 0, 'solver': 0,
          'workers': 1, 'per_call_seconds': 90, 'batch_seconds': 600, 'retries': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    p.add_argument('--forest-root', required=True, type=Path)
    p.add_argument('--preflight', action='store_true')
    args = p.parse_args()
    start = time.monotonic()
    coordinates = read(ROOT / COVERAGE)
    assert len(coordinates) == 50 and len({(r['case'], r['cores']) for r in coordinates}) == 50
    official, hashes = verify_source(args.source, {f"{r['case']:03d}" for r in coordinates})
    for path in (COVERAGE, HISTORY):
        assert (ROOT / path).read_bytes() == git_bytes(ROOT, args.source, path)
        hashes[path] = digest(ROOT / path)
    history = read(ROOT / HISTORY)
    assert history['status'] == 'complete'
    for path, sha in history['source_input_sha256'].items():
        if path.startswith('data/raw/'):
            assert digest(ROOT / path) == sha
    old = {r['case_id']: r for r in history['evaluations']
           if r['variant'] == 'band_pair' and r['problem'] == 3 and r['status'] == 'ok'}
    delay = read_required_settings(ROOT / 'data/raw/a/official/data/config.txt',
                                  'multicore_scene_b', ('cross_core_copy_delay_cycles',))['cross_core_copy_delay_cycles']
    records, prepared = [], {}
    for row in coordinates:
        case, cores = f"{row['case']:03d}", row['cores']
        rp = Path(row['receipt_path'])
        assert (args.forest_root / rp).read_bytes() == git_bytes(args.forest_root, FOREST_COMMIT, str(rp))
        receipt = read(args.forest_root / rp)
        result_path = args.forest_root / rp.parent / 'result.json.gz'
        plan_path = args.forest_root / rp.parent.parent / f'case_{case}_multicore_res.json'
        assert digest(result_path) == receipt['result_sha256']
        assert digest(plan_path) == receipt['plan_sha256'] == row['forest500_plan_sha256']
        assert receipt['official_e0_calls'] == row['forest500_calls']
        base = read(result_path)
        assert base['makespan'] == row['forest500_makespan']
        assert receipt['graph_sha256'] == hashes[f'data/raw/a/official/data/case_{case}.json']
        assert receipt['config_sha256'] == hashes['data/raw/a/official/data/config.txt']
        rec = {'case_id': case, 'cores': cores, 'baseline_makespan': base['makespan'],
               'baseline_movement': base['data_movement_bytes'], 'baseline_cache_stats': base['cache_stats'],
               'baseline_receipt': str(rp), 'baseline_artifact_commit': FOREST_COMMIT,
               'baseline_result_sha256': receipt['result_sha256'], 'baseline_plan_sha256': receipt['plan_sha256'],
               'forest_online_calls': receipt['official_e0_calls'], 'status': 'pending'}
        records.append(rec)
        if receipt['official_e0_calls'] >= 3:
            rec['status'] = 'no_online_budget'
            continue
        before = time.monotonic()
        graph = read(ROOT / f'data/raw/a/official/data/case_{case}.json')
        try:
            proposal, meta = construct(Index(graph), cores)
        except UnsupportedStructure as error:
            rec.update(status='unsupported', reason=str(error))
            continue
        raw = encoded(proposal)
        sha = hashlib.sha256(raw).hexdigest()
        rec.update(metadata=meta, plan_sha256=sha, construct_seconds=time.monotonic()-before)
        if encoded(read(plan_path)) == raw:
            rec['status'] = 'duplicate'
            continue
        try:
            lower = analyze(graph, proposal, delay)['with_cross_core_delay']['lower_bound_cycles']
            rec['lower_bound_cycles'] = lower
            if lower >= base['makespan']:
                rec['status'] = 'bound_pruned'
        except UnsupportedBound as error:
            rec['bound_unavailable'] = str(error)
        prepared[case, cores] = raw
        reuse = old.get(case) if cores == 5 else None
        if rec['status'] == 'pending' and reuse and reuse['plan_sha256'] == sha:
            assert digest(ROOT / reuse['result_path']) == reuse['result_sha256']
            rec.update(status='historical_exact_reuse', result_path=reuse['result_path'],
                       result_sha256=reuse['result_sha256'])
    if args.preflight:
        from collections import Counter
        print({'valid': True, 'states': dict(Counter(r['status'] for r in records)),
               'new_e0': 0, 'seconds': time.monotonic()-start})
        return
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    state = {'status': 'running', 'source_commit': args.source, 'started_at': utc(),
             'budget': BUDGET, 'official_code_sha256': official, 'source_input_sha256': hashes,
             'records': records, 'new_p3': 0, 'historical_reused': 0,
             'scope': 'complete recognized family, one fixed candidate; old forest controls, NOT fresh solver/full500'}

    def save():
        state['elapsed_seconds'] = time.monotonic()-start
        write(out / 'run.json', state)

    save()
    try:
        # Persist all candidate bytes before the first E0 call.
        for rec in records:
            key = rec['case_id'], rec['cores']
            if key in prepared:
                folder = out / f'{key[0]}-k{key[1]}'
                folder.mkdir()
                path = folder / 'plan.json'
                path.write_bytes(prepared[key])
                assert digest(path) == rec['plan_sha256']
                rec['plan_path'] = str(path.relative_to(ROOT))
        save()
        for rec in records:
            if rec['status'] not in ('pending', 'historical_exact_reuse'):
                continue
            if rec['status'] == 'historical_exact_reuse':
                state['historical_reused'] += 1
            else:
                remaining = BUDGET['batch_seconds'] - (time.monotonic()-start)
                assert remaining > 0 and state['new_p3'] < BUDGET['new_p3_max'], 'budget exhausted'
                folder = ROOT / Path(rec['plan_path']).parent
                path = folder / 'result.json.gz'
                command = ['-m', 'src.q3.oracle', f"data/raw/a/official/data/case_{rec['case_id']}.json",
                           rec['plan_path'], '3', str(path.relative_to(ROOT))]
                rec.update(status='reserved', command=['python', *command])
                state['new_p3'] += 1
                save()
                before = time.monotonic()
                with (folder/'stdout.txt').open('xb') as stdout, (folder/'stderr.txt').open('xb') as stderr:
                    subprocess.run([sys.executable, *command], cwd=ROOT, check=True,
                                   timeout=min(90, remaining), stdout=stdout, stderr=stderr)
                rec.update(status='ok', external_e0_seconds=time.monotonic()-before,
                           result_path=str(path.relative_to(ROOT)), result_sha256=digest(path))
            result = read(ROOT / rec['result_path'])
            assert digest(ROOT / rec['plan_path']) == rec['plan_sha256']
            assert result['problem'] == 3 and result['cache_mode'] == 'read_only'
            assert result['num_cores'] == rec['cores'] and result['scene'] == 'B'
            rec.update(makespan=result['makespan'], movement=result['data_movement_bytes'],
                       cache_stats=result['cache_stats'], delta_makespan=result['makespan']-rec['baseline_makespan'])
            save()
        assert all(digest(ROOT / path) == sha for path, sha in hashes.items())
        state['status'] = 'complete'
    except Exception as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at'] = utc()
        save()
    print({k: state[k] for k in ('status', 'new_p3', 'historical_reused', 'elapsed_seconds')})


if __name__ == '__main__':
    main()
