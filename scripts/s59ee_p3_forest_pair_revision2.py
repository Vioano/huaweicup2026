"""Add fixed same-plan P2 evidence to the unpublished forest revision 2 draft."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft'
P2_COMMIT = '11d5d3ba1820864626bb49acccbeec7a75553e80'

def digest(data): return hashlib.sha256(data).hexdigest()
def fixed(repo, path):
    return subprocess.run(['git', '-C', str(repo), 'show', f'{P2_COMMIT}:{path}'],
                          check=True, capture_output=True).stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', type=Path, required=True)
    parser.add_argument('--delta-dir', type=Path, required=True)
    args = parser.parse_args()
    delta = args.delta_dir.resolve()
    manifest_bytes = (delta / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    run_bytes = (delta / 'run.json').read_bytes()
    run = json.loads(run_bytes)
    if (manifest['sources']['p2_result_artifact_commit'] != P2_COMMIT
            or manifest['sources']['forest_run_id'] != 'q3-forest-full500-20260925-s59'
            or manifest['counts'] != {'coordinates': 500, 'reuse_existing_p2': 476, 'new_p2_e0': 24}
            or run['status'] != 'complete' or run['new_p2_e0_succeeded'] != 24
            or run['manifest_sha256'] != digest(manifest_bytes)):
        raise ValueError('delta source, completion or manifest changed')
    lookup = {(x['case_id'], x['cores']): x for x in manifest['records']}
    if len(lookup) != 500: raise ValueError('delta manifest coordinates are not unique')
    jobs = {x['coordinate']: x for x in run['jobs']}
    feeds = [json.loads((DRAFT / f'board-feed-s{n:02}-revision2.json').read_text())
             for n in range(1, 11)]
    rows = [r for f in feeds for r in f['records']]
    if len(rows) != 500 or len({(r['case_id'], r['cores']) for r in rows}) != 500:
        raise ValueError('draft does not cover full matrix')
    planned = {}
    new_artifacts = {}
    for row in rows:
        case, cores = row['case_id'], row['cores']
        key = f'{case}-k{cores}'
        item = lookup[(case, cores)]
        identity = row['identity']
        if (row['revision'] != 2 or row.get('cache_pair') is not None
                or any(item[k] != identity[k] for k in ('graph_sha256','config_sha256','official_sha256'))
                or item['forest_plan']['sha256'] != identity['plan_sha256']
                or item['forest_plan'] != row['artifacts']['plan']):
            raise ValueError('forest identity/plan or revision changed: ' + key)
        if item['action'] == 'reuse_existing_p2':
            ref = item['reused_p2']
            if not item['same_plan_bytes'] or ref['source_plan_sha256'] != identity['plan_sha256']:
                raise ValueError('reused P2 did not score the same plan: ' + key)
            raw = fixed(args.source_repo, ref['path'])
            if digest(raw) != ref['sha256']: raise ValueError('fixed P2 hash mismatch: ' + key)
            source_note = f'Fixed P2 E0 source {P2_COMMIT}:{ref["path"]}'
        elif item['action'] == 'requires_new_p2_e0':
            cell = delta / 'cells' / key
            raw = (cell / 'result.json.gz').read_bytes()
            plan = (cell / 'plan.json').read_bytes()
            receipt = (cell / 'run.json').read_bytes()
            job = jobs[key]
            saved = json.loads(receipt)
            if (job['status'] != 'ok' or saved != job or digest(raw) != job['result_sha256']
                    or digest(plan) != identity['plan_sha256'] or saved['plan_sha256'] != identity['plan_sha256']
                    or saved['graph_sha256'] != identity['graph_sha256']):
                raise ValueError('new P2 result/plan/run mismatch: ' + key)
            new_artifacts[key] = {'plan.json': plan, 'run.json': receipt}
            source_note = f'New P2 E0 source delta {delta.name}/cells/{key}; run and plan copied into draft'
        else: raise ValueError('unknown P2 source action: ' + key)
        result = json.loads(gzip.decompress(raw))
        if (result.get('scene') != 'B' or result.get('num_cores') != cores
                or result.get('problem') not in (None, 2) or result.get('cache_mode') is not None
                or 'cache_stats' in result or not isinstance(result.get('makespan'), (int,float))):
            raise ValueError('source is not matching P2 E0 result: ' + key)
        path = DRAFT / 'cache_pair' / key / 'result.json.gz'
        planned[key] = (path, raw, source_note)

    (DRAFT / 'cache_pair_delta').mkdir(exist_ok=True)
    (DRAFT / 'cache_pair_delta' / 'manifest.json').write_bytes(manifest_bytes)
    (DRAFT / 'cache_pair_delta' / 'run.json').write_bytes(run_bytes)
    for key, parts in new_artifacts.items():
        for name, raw in parts.items():
            path = DRAFT / 'cache_pair_delta' / 'cells' / key / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    for key, (path, raw, _) in planned.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    for shard, feed in enumerate(feeds, 1):
        for row in feed['records']:
            case, cores = row['case_id'], row['cores']; key = f'{case}-k{cores}'
            path, raw, note = planned[key]
            row['cache_pair'] = {k: row['identity'][k] for k in ('graph_sha256','config_sha256','official_sha256','plan_sha256')}
            row['cache_pair'].update(cores=cores, route='E0', result={'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(raw)})
            row['notes'].append('Same-plan no-L2 Cache pair added in revision 2. ' + note)
        (DRAFT / f'board-feed-s{shard:02}-revision2.json').write_text(
            json.dumps(feed, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'pairs': len(planned), 'reused': len(planned)-len(new_artifacts),
                      'new_p2': len(new_artifacts), 'draft': str(DRAFT.relative_to(ROOT))}))

if __name__ == '__main__': main()
