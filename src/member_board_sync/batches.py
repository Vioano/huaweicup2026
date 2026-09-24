"""Read-only batch endpoint audit using the independent cell oracle.

The production board/sync modules are never imported. This extends the existing
snapshot audit to all batch entries, including failed and out-of-scope runs.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen
from audit import canonical, digest, expected_cells, require, verify_envelope, verify_snapshot


def numeric(value, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def compare(actual, expected, context='response'):
    if isinstance(expected, dict):
        require(set(actual) == set(expected), context + ': keys differ')
        for key, value in expected.items():
            compare(actual[key], value, context + '.' + key)
    elif isinstance(expected, list):
        require(len(actual) == len(expected), context + ': list length differs')
        for index, value in enumerate(expected):
            compare(actual[index], value, context + '[' + str(index) + ']')
    elif type(expected) is float:
        require(type(actual) in (int, float) and math.isclose(actual, expected, rel_tol=1e-13, abs_tol=1e-13),
                context + ': numeric value differs')
    else:
        require(type(actual) is type(expected) and actual == expected, context + ': value/type differs')


def expected_batches(latest, cells_by_run, problem, cores, cases):
    candidates = []
    runs = sorted({r['run_id'] for r in latest if r['problem'] == problem})
    for run in runs:
        whole = [r for r in latest if r['run_id'] == run and r['problem'] == problem]
        scope = [r for r in whole if r['cores'] == cores and r['case_id'] in cases]
        winners = [c['best'] for c in cells_by_run[run] if c['problem'] == problem
                   and c['cores'] == cores and c['case_id'] in cases and c['best']]
        sources = {(r['algorithm_id'], r.get('solver_commit')) for r in whole}
        single = len(sources) == 1 and all(re.fullmatch('[0-9a-f]{40}', commit or '') for _, commit in sources)
        ratios = [r['metrics']['baseline_speedup'] for r in winners
                  if r.get('baseline_verified') and numeric(r['metrics'].get('baseline_speedup'), True)]
        times = [r['metrics']['solver_wall_seconds'] for r in winners
                 if numeric(r['metrics'].get('solver_wall_seconds'))]
        candidates.append(dict(run_id=run, algorithm_ids=sorted({a for a, _ in sources}),
            solver_commits=sorted({v for _, v in sources if v}), single_source=bool(single),
            valid_count=len(winners), scored_count=len(ratios), target_count=len(cases),
            mean_speedup=sum(ratios)/len(ratios) if ratios else None,
            mean_solver_seconds=sum(times)/len(times) if times else None, solver_count=len(times),
            complete=bool(single and len(ratios) == len(cases)),
            missing_cases=sorted(set(cases) - {r['case_id'] for r in winners}),
            record_count=len(whole), scope_attempts=len(scope), status_counts=dict(Counter(r['status'] for r in scope))))
    complete = sorted([r for r in candidates if r['complete']], key=lambda r: (-r['mean_speedup'], r['run_id']))
    partial = sorted([r for r in candidates if not r['complete']], key=lambda r: (-r['scored_count'], -r['valid_count'], r['run_id']))
    return dict(problem=problem, cores=cores, case_ids=sorted(cases), target_count=len(cases),
        complete_count=len(complete), partial_count=len(partial), complete=complete[:3], partial=partial[:3],
        batches=complete+partial)


def audit(args):
    manifest = json.loads((args.sync_state/'accepted/current.json').read_bytes())
    config = json.loads((args.sync_state/'config.json').read_bytes())
    public = {k:v for k,v in manifest.items() if k not in ('_channel', 'verified_at')}
    require(verify_envelope(manifest['_channel'], config['trusted_keys']['nikolastarx'].encode(), args.key_sha256)
            == public, 'snapshot signature differs')
    require(re.fullmatch(r'snapshot-[0-9a-f]{64}\.json\.gz', manifest['payload_file']), 'unsafe payload name')
    payload = verify_snapshot(manifest, (args.sync_state/'accepted'/manifest['payload_file']).read_bytes())
    def get(path, query=None):
        with urlopen(args.url.rstrip('/')+path+('?' + urlencode(query) if query else ''), timeout=30) as response:
            require(response.headers.get('Cache-Control') == 'no-store', 'unexpected caching')
            return json.load(response)
    require(get('/api/v1/health')['runtime']['snapshot_id'] == payload['snapshot_id'], 'initial snapshot differs')
    revisions = {}
    for row in sorted(payload['records'], key=lambda r:r['revision']):
        revisions[row['attempt_id']] = row
    latest = list(revisions.values())
    cells = {run:expected_cells(payload, run=run) for run in sorted({r['run_id'] for r in latest})}
    checks = []
    for cases in ([f'{n:03d}' for n in range(1,101)], [f'{n:03d}' for n in range(1,26)]):
        for problem in ('P1','P2','P3'):
            for cores in range(1,6):
                actual = get('/api/v1/batches', dict(problem=problem, cores=cores, cases=','.join(cases)))
                require(isinstance(actual.pop('ranking'), str), 'missing ranking description')
                expected = expected_batches(latest, cells, problem, cores, cases)
                compare(actual, expected, problem+' k'+str(cores)+' n'+str(len(cases)))
                checks.append(dict(problem=problem, cores=cores, cases=len(cases), batches=len(actual['batches']),
                    complete=actual['complete_count'], partial=actual['partial_count'], response_sha256=digest(canonical(actual))))
    require(get('/api/v1/health')['runtime']['snapshot_id'] == payload['snapshot_id'], 'snapshot changed during audit')
    return dict(status='passed', checked_at=datetime.now(timezone.utc).isoformat(), snapshot=public,
        checks=checks, scope='All batch fields and ordering at 30 problem/core/case scopes; independent cell oracle, no production imports.',
        numeric_tolerance='1e-13 absolute/relative for arithmetic means; identifiers/counts/status/source and ordering exact.',
        limitations='Fixed accepted snapshot and read-only HTTP. Does not replace browser interaction or original artifact/evaluator verification.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sync-state',type=Path,required=True)
    p.add_argument('--url',required=True)
    p.add_argument('--key-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=audit(a)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],snapshot_id=result['snapshot']['snapshot_id'],checks=len(result['checks']))))
