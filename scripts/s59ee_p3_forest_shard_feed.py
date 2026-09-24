"""Export one completed fixed 50-cell P3 forest shard without scoring."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q3.board_export import export_batch

SOURCE = '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
GROUP_RUN = 'q3-forest-full500-20260925-s59'
AREA = ROOT / 'results/a/q3-nikolastarx/forest-full500-20260925-s59'
CONTROL = ROOT / 'results/a/q3-nikolastarx/forest500-control-20260925-s59'

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(1,11), required=True)
    args = parser.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(AREA) or batch == AREA:
        parser.error('batch outside fixed P3 result area')
    n = args.shard
    tag = f's{n:02}'
    dispatch = read(batch / 'dispatch.json')
    if dispatch['source_commit'] != SOURCE or dispatch['max_workers'] != 4 or dispatch['shards'][tag]['status'] != 'stage_complete':
        raise ValueError('fixed source/worker identity or shard completion differs')
    if sha(ROOT / dispatch['controller_path']) != dispatch['controller_sha256']:
        raise ValueError('controller bytes drift')
    manifest_path = CONTROL / f'manifest-s{n:02}.json'
    if sha(manifest_path) != dispatch['shards'][tag]['manifest_sha256']:
        raise ValueError('manifest bytes drift')
    manifest = read(manifest_path)
    native = batch / tag / 'batch.json'
    source_batch = read(native)
    if source_batch['status'] != 'stage_complete' or source_batch['solver_commit'] != SOURCE or source_batch['run_id'] != manifest['run_id']:
        raise ValueError('native shard not complete/fixed')
    payload = export_batch(native, root=ROOT)
    rows = payload['records']
    wanted = {(j['case_id'],j['cores']) for j in manifest['jobs']}
    actual = {(r['case_id'],r['cores']) for r in rows}
    if len(rows) != 50 or actual != wanted or any(r['status'] != 'ok' or r['solver_commit'] != SOURCE for r in rows):
        raise ValueError('shard does not contain 50 unique successful fixed-source cells')
    calls = {key:sum(x['calls'][key] for x in source_batch['records']) for key in ['solver','E0','E1','E2']}
    if calls['solver'] != 50 or not 50 <= calls['E0'] <= 150 or calls['E1'] or calls['E2']:
        raise ValueError('native call ledger outside frozen budget')
    native_sha, controller_sha = sha(native), sha(ROOT / dispatch['controller_path'])
    for record in rows:
        record['run_id'] = GROUP_RUN
        record['parameters'].update(native_shard_run_id=source_batch['run_id'], global_max_workers=4,
                                    controller_source_sha256=controller_sha, native_shard_batch_sha256=native_sha,
                                    native_manifest_sha256=sha(manifest_path))
        record['notes'].append('One fixed 50-cell shard of a single fresh 500-cell algorithm run; original shard run, receipt and manifest remain attached. This slice alone is not a full-batch score. Four shard workers maximum; no prior witness result fills a cell.')
    output = batch / f'board-feed-{tag}-50.json'
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'feed':output.relative_to(ROOT).as_posix(),'records':len(rows),'run_id':GROUP_RUN,'calls':calls,'sha256':sha(output)}))

if __name__ == '__main__': main()
