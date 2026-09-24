"""Dispatch four fixed P2 shards; no scoring, retries, or historical result reuse."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx import evaluate_feedback as common
from src.q2_nikolastarx import evaluate_matrix as matrix

HOME = Path(__file__).resolve().parent
MANIFEST = HOME / 'manifest.json'


def stop_once(path, reason):
    try:
        with path.open('x') as f:
            json.dump({'time': common.utc(), 'reason': reason}, f)
            f.write('\n')
    except FileExistsError:
        pass


def preflight(runner):
    manifest = matrix.read(MANIFEST)
    for path in (MANIFEST, Path(__file__).resolve()):
        rel = path.relative_to(ROOT).as_posix()
        if path.read_bytes() != common.git_bytes(runner, rel):
            raise RuntimeError(f'Runner input differs from fixed commit: {rel}')
    if manifest['source_commit'] != '2794ceba93acc1f7fc119154f61082511843d4b3':
        raise RuntimeError('Source changed')
    if manifest['total_cells'] != 500 or manifest['max_workers'] != 4:
        raise RuntimeError('Scope changed')
    if manifest['maximum_calls'] != {'solver':500,'external_E0':500,'online_E0':0,'E1':0,'E2':0,'retries':0}:
        raise RuntimeError('Call budget changed')
    if manifest['aggregate_wall_seconds'] != 1800 or manifest['global_rss_cap_bytes'] != 4*1024**3:
        raise RuntimeError('Wall or RSS budget changed')
    if 4*manifest['conservative_per_shard_rss_cap_bytes'] >= manifest['global_rss_cap_bytes']:
        raise RuntimeError('Per-shard RSS caps have no controller reserve')
    coords = []
    protocols = []
    batch = ROOT / Path(manifest['global_stop_file']).parent
    if batch.exists():
        raise RuntimeError('Batch output already exists; never resume or repeat automatically')
    for n, name in enumerate(manifest['protocols'], 1):
        path = ROOT / name
        p = matrix.read(path)
        cells = matrix.validate_protocol(p)
        if p['output_prefix'] != (batch/f's{n:02}').relative_to(ROOT).as_posix():
            raise RuntimeError('Shard output path changed')
        if p['global_stop_file'] != manifest['global_stop_file']:
            raise RuntimeError('Global stop path changed')
        if p['solver_module'] != manifest['solver_module'] or p['workers'] != 1:
            raise RuntimeError('Solver entry or shard worker count changed')
        if (p['max_E0'], p['max_internal_per_cell'], p['max_E1'], p['max_E2'], p['retries']) != (125,0,0,0,0):
            raise RuntimeError('Shard call budget changed')
        if p['rss_observation_stop_bytes'] != manifest['conservative_per_shard_rss_cap_bytes']:
            raise RuntimeError('Shard memory cap changed')
        if (p['solver_wall_seconds'],p['evaluation_timeout_seconds'],p['cell_wall_seconds']) != (25,60,95):
            raise RuntimeError('Per-cell time budget changed')
        matrix.frozen_inputs(p, path, manifest['source_commit'], runner)
        coords.extend(cells)
        protocols.append((path,p))
    expected = {(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
    if len(coords) != 500 or set(coords) != expected:
        raise RuntimeError('Four shards do not partition the official 500 cells')
    return manifest, protocols, batch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runner-commit',required=True)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    manifest,protocols,batch=preflight(args.runner_commit)
    if not args.run:
        print(json.dumps({'preflight':'ok','dispatched':0,'cells':500,'shards':4,
                          'source_commit':manifest['source_commit'],'runner_commit':args.runner_commit}))
        return 0
    batch.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    deadline=started+manifest['aggregate_wall_seconds']
    stop_path=ROOT/manifest['global_stop_file']
    summary={'schema':'q2-activecore-four-shard-v1','source_commit':manifest['source_commit'],
             'runner_commit':args.runner_commit,'started_at':common.utc(),'status':'running',
             'max_workers':4,'per_shard_rss_cap_bytes':manifest['conservative_per_shard_rss_cap_bytes'],
             'global_rss_cap_bytes':manifest['global_rss_cap_bytes'],'shards':{}}
    matrix.save(batch/'dispatch.json',summary)

    def worker(n,path,p):
        argv=[sys.executable,'-B','-m','src.q2_nikolastarx.evaluate_matrix','run',
              '--protocol',path.relative_to(ROOT).as_posix(),
              '--source-commit',manifest['source_commit'],'--runner-commit',args.runner_commit]
        receipt=common.monitored(argv,batch/'controller'/f's{n:02}',deadline,
                                  manifest['conservative_per_shard_rss_cap_bytes'])
        journal_path=ROOT/p['output_prefix']/'journal.json'
        journal=matrix.read(journal_path) if journal_path.exists() else None
        cells={} if journal is None else journal['cells']
        accepted=(receipt['status']=='ok' and not receipt.get('surviving_pids') and
                  journal is not None and journal.get('stop_reason')=='all_fixed_cells_dispatched' and
                  len(cells)==125 and all(v['state']=='ok' and
                  v['calls']=={'solver':1,'E0':1,'E1':0,'E2':0} for v in cells.values()))
        if not accepted:
            stop_once(stop_path,f's{n:02} failed or unverified')
        return {'accepted':accepted,'receipt':receipt,'journal':journal_path.relative_to(ROOT).as_posix()
                if journal_path.exists() else None,'cell_count':len(cells),
                'stop_reason':None if journal is None else journal.get('stop_reason')}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(worker,n,path,p):n for n,(path,p) in enumerate(protocols,1)}
        for future in as_completed(futures):
            n=futures[future]
            try: value=future.result()
            except BaseException as exc:
                stop_once(stop_path,f's{n:02} supervisor {type(exc).__name__}')
                value={'accepted':False,'error':f'{type(exc).__name__}: {exc}'}
            summary['shards'][f's{n:02}']=value
            matrix.save(batch/'dispatch.json',summary)
            print(json.dumps({'shard':n,'accepted':value.get('accepted'),
                              'cell_count':value.get('cell_count'),'stop_reason':value.get('stop_reason')}),flush=True)
    summary['finished_at']=common.utc()
    summary['aggregate_wall_seconds']=time.perf_counter()-started
    summary['status']='complete' if len(summary['shards'])==4 and all(v.get('accepted') for v in summary['shards'].values()) else 'stopped'
    matrix.save(batch/'dispatch.json',summary)
    print(json.dumps({'status':summary['status'],'shards':len(summary['shards']),
                      'cells':sum(v.get('cell_count',0) for v in summary['shards'].values()),
                      'wall_seconds':summary['aggregate_wall_seconds']}),flush=True)
    return 0 if summary['status']=='complete' else 1

if __name__=='__main__':
    raise SystemExit(main())
