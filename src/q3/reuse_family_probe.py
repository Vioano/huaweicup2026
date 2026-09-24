"""Falsify one frozen reuse proposal over its complete recognized input family.

This is an offline mechanism probe, not a new full500 solver benchmark. Every
coordinate comes from the previously frozen structural coverage scan.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .construct import ROOT, Index
from .feedback_benchmark import digest, read, utc, verify_source, write
from .forest_reuse_grid import construct
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded
from evaluation_validation import read_required_settings

COVERAGE = "results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json"
OLD_PROBE = "results/a/q3-nikolastarx/forest-reuse-grid-probe-20260925"
BUDGET = {"constructors_in_process": 33, "new_p3_e0_max": 31,
          "workers": 1, "retries": 0, "per_cell_seconds": 90,
          "batch_seconds": 600, "solver_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    rows = [r for r in read(ROOT / COVERAGE) if r.get("eligible_remaining_call")]
    if len(rows) != 33 or len({(r['case'], r['cores']) for r in rows}) != 33:
        raise ValueError("frozen eligible family changed")
    official, hashes = verify_source(args.source, {f"{r['case']:03d}" for r in rows})
    hashes[COVERAGE] = digest(ROOT / COVERAGE)
    old = read(ROOT / OLD_PROBE / "run.json")
    for path, expected in old["source_input_sha256"].items():
        if path.startswith("data/raw/") and digest(ROOT / path) != expected:
            raise ValueError("historical probe input/official identity changed")
    historical = {r['case_id']: r for r in old['results'] if r['problem'] == 3}
    delay = read_required_settings(ROOT / "data/raw/a/official/data/config.txt",
                                  "multicore_scene_b", ("cross_core_copy_delay_cycles",))[
                                      "cross_core_copy_delay_cycles"]
    proposals = []
    for row in rows:
        case = f"{row['case']:03d}"
        graph = ROOT / f"data/raw/a/official/data/case_{case}.json"
        t0 = time.monotonic()
        plan, metadata = construct(Index(read(graph)), row['cores'])
        raw = encoded(plan)
        import hashlib
        if hashlib.sha256(raw).hexdigest() != row['proposal_sha256']:
            raise ValueError(f"proposal no longer matches frozen coverage: {case}/{row['cores']}")
        lower = None
        try:
            lower = analyze(read(graph), plan, delay)['with_cross_core_delay']['lower_bound_cycles']
        except UnsupportedBound:
            pass
        reuse = historical.get(case) if row['cores'] == 5 else None
        if reuse:
            if reuse['plan_sha256'] != row['proposal_sha256'] or digest(ROOT / reuse['result_path']) != reuse['result_sha256']:
                raise ValueError("historical proposal/result identity mismatch")
            result = read(ROOT / reuse['result_path'])
            if result.get('problem') != 3 or result.get('num_cores') != row['cores']:
                raise ValueError("historical P3 identity mismatch")
        proposals.append((row, raw, metadata, lower, reuse, time.monotonic() - t0))
    if args.preflight:
        print(json.dumps({"valid": True, "coordinates": len(proposals),
                          "bound_pruned": sum(p[3] is not None and p[3] >= p[0]['forest500_makespan'] for p in proposals),
                          "historical_p3_available": sum(p[4] is not None for p in proposals),
                          "new_e0": 0, "seconds": time.monotonic() - started}))
        return
    out = args.output.resolve()
    out.relative_to(ROOT / "results/a/q3-nikolastarx")
    out.mkdir(parents=True, exist_ok=False)
    state = {"schema": "q3-reuse-family-probe-v1", "status": "running",
             "source_commit": args.source, "started_at": utc(), "budget": BUDGET,
             "official_code_sha256": official, "source_input_sha256": hashes,
             "records": [], "new_e0_calls": 0, "historical_results_reused": 0,
             "scope": "offline candidate-family mechanism evidence; old forest500 baseline, not fresh solver wall or new full500 algorithm score"}

    def save():
        state['elapsed_seconds'] = time.monotonic() - started
        write(out / "run.json", state)

    save()
    try:
        for row, raw, metadata, lower, reuse, construct_wall in proposals:
            case, cores = f"{row['case']:03d}", row['cores']
            key = f"{case}-k{cores}"
            folder = out / key
            folder.mkdir()
            plan_path = folder / "plan.json"
            plan_path.write_bytes(raw)
            record = {"case_id": case, "cores": cores, "plan_sha256": digest(plan_path),
                      "graph_sha256": digest(ROOT / f"data/raw/a/official/data/case_{case}.json"),
                      "baseline_source_commit": "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1",
                      "baseline_receipt_path": row['receipt_path'],
                      "baseline_plan_sha256": row['forest500_plan_sha256'],
                      "baseline_makespan": row['forest500_makespan'],
                      "construct_and_bound_seconds": construct_wall,
                      "certified_lower_bound_cycles": lower, "metadata": metadata,
                      "status": "constructed", "new_e0_calls": 0}
            state['records'].append(record)
            if lower is not None and lower >= row['forest500_makespan']:
                record['status'] = 'bound_pruned'
                save()
                continue
            if reuse:
                result = read(ROOT / reuse['result_path'])
                record.update(status='historical_exact_plan_reuse',
                              result_path=reuse['result_path'], result_sha256=reuse['result_sha256'])
                state['historical_results_reused'] += 1
            else:
                remaining = BUDGET['batch_seconds'] - (time.monotonic() - started)
                if remaining <= 0 or state['new_e0_calls'] >= BUDGET['new_p3_e0_max']:
                    raise TimeoutError("batch budget reached")
                result_path = folder / "result.json.gz"
                command = ["-m", "src.q3.oracle", f"data/raw/a/official/data/case_{case}.json",
                           str(plan_path.relative_to(ROOT)), "3", str(result_path.relative_to(ROOT))]
                record.update(status='reserved', command=['python', *command], new_e0_calls=1)
                state['new_e0_calls'] += 1
                save()
                t0 = time.monotonic()
                with (folder / 'stdout.json').open('xb') as stdout, (folder / 'stderr.txt').open('xb') as stderr:
                    child = subprocess.run([sys.executable, *command], cwd=ROOT, stdout=stdout,
                                           stderr=stderr, timeout=min(90, remaining), check=True)
                record['external_e0_wall_seconds'] = time.monotonic() - t0
                result = read(result_path)
                if result.get('problem') != 3 or result.get('num_cores') != cores:
                    raise ValueError("unexpected official result identity")
                record.update(status='ok', result_path=str(result_path.relative_to(ROOT)),
                              result_sha256=digest(result_path))
            record.update(makespan=result['makespan'], data_movement_bytes=result['data_movement_bytes'],
                          cache_stats=result['cache_stats'],
                          delta_makespan=result['makespan'] - row['forest500_makespan'])
            save()
        if any(digest(ROOT / path) != expected for path, expected in hashes.items()):
            raise ValueError('source or input changed while running')
        state['status'] = 'complete'
    except Exception as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at'] = utc()
        save()
    print(json.dumps({k: state[k] for k in ('status', 'new_e0_calls', 'historical_results_reused', 'elapsed_seconds')}))


if __name__ == '__main__':
    main()
