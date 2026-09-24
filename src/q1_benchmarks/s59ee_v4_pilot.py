"""Frozen, bounded 500-cell P1 unified benchmark; no retries or historical plan reuse."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h
from src.q1_benchmarks import unified_smoke as smoke

SOURCE = 'a0537aeb72dc702af86d67d3194587d581ac207c'
HERE = 'src/q1_benchmarks/s59ee_v4_pilot.py'
MANIFEST = 'src/q1_benchmarks/s59ee_v4_pilot_manifest.json'
RESULTS = ROOT / 'output/p1-v4-pilot-s59ee'
CELLS = [('039',4),('080',4),('084',5),('008',5)]


def ledger6(stdout, diagnostics):
    events=[]
    for line in stdout.splitlines():
        try: item=json.loads(line)
        except (ValueError, TypeError): continue
        if isinstance(item,dict) and 'event' in item: events.append(item)
    starts=[x for x in events if x['event']=='score_attempt_started']
    returns=[x for x in events if x['event']=='score_attempt_returned']
    confirmed=sum(x.get('worker_pid') is not None for x in returns)
    unresolved=len(starts)-len(returns)
    if not 0 <= len(returns) <= len(starts) <= 6:
        raise ValueError('Invalid or over-budget online score ledger')
    value=dict(score_attempts_observed=len(starts), score_returns_observed=len(returns),
               confirmed_worker_calls_lower_bound=confirmed,
               worker_calls_upper_bound=confirmed+unresolved,
               actual_e1_calls=confirmed if unresolved==0 else None,
               exact=unresolved==0, unresolved_requests=unresolved)
    normalized=[{k:v for k,v in row.items() if k not in ('event','monotonic_seconds')} for row in returns]
    if (normalized!=diagnostics['online_scores'] or
        diagnostics['online_score_attempts']!=len(starts) or
        diagnostics['actual_e1_calls']!=confirmed or unresolved or
        not any(x['event']=='solver_completed' for x in events)):
        raise ValueError('Final diagnostics and flushed event ledger disagree')
    return value


def check():
    if sys.version_info[:2] != (3, 12): raise RuntimeError('locked Python 3.12 required')
    head = h.git('rev-parse', 'HEAD').decode().strip()
    if h.git('diff', '--name-only', head).strip(): raise RuntimeError('tracked runner/source dirty')
    manifest = h.read(ROOT/MANIFEST)
    assert manifest['source_commit'] == SOURCE
    assert manifest['cells'] == [[c,k] for c,k in CELLS]
    assert manifest['maximum_calls'] == {'solver':4,'external_E0':4,'internal_E1':24,'E2':0,'retries':0}
    assert manifest['timeouts_seconds'] == {'solver':300,'external_E0':180,'batch':1200}
    source_paths = h.git('ls-tree','-r','--name-only',SOURCE,'src/q1','src/eval_exact').decode().splitlines()
    source_paths = [p for p in source_paths if p.endswith(('.py','.json'))]
    actual_paths = [str(p.relative_to(ROOT)) for folder in ('src/q1','src/eval_exact') for p in (ROOT/folder).rglob('*') if p.suffix in ('.py','.json')]
    if set(source_paths) != set(actual_paths): raise RuntimeError('source module closure differs')
    sources = h.read(ROOT/'src/q1/unified_sources.json')
    archived = sources['archived_return_path']
    if archived != 'AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py':
        raise RuntimeError('Archived return dependency path changed')
    for path in source_paths + [archived,'uv.lock','pyproject.toml','docs/a/source-manifest.json']:
        if (ROOT/path).read_bytes() != h.git('show',f'{SOURCE}:{path}'):
            raise RuntimeError(f'fixed source differs: {path}')
    if h.sha(ROOT/archived) != sources['archived_return_sha256']:
        raise RuntimeError('Archived return dependency SHA-256 differs')
    import subprocess
    check_import = subprocess.run([sys.executable,'-B','-c','import src.q1.unified'],
                                  cwd=ROOT,capture_output=True,text=True)
    if check_import.returncode:
        raise RuntimeError(f'fixed solver import failed: {check_import.stderr[-1000:]}')
    for path in (HERE,MANIFEST,'src/q1_benchmarks/unified_smoke.py','src/q1_benchmarks/bounded_full4_e0.py'):
        if (ROOT/path).read_bytes() != h.git('show',f'{head}:{path}'):
            raise RuntimeError(f'fixed runner differs: {path}')
    official = h.read(ROOT/'docs/a/source-manifest.json')
    files = {r['path']:r for r in official['files']}
    for path,r in files.items():
        if path.startswith('code/') or path == 'data/config.txt':
            if h.sha(h.OFFICIAL/path) != r['sha256']: raise RuntimeError(f'official file differs: {path}')
    code_hash = h.digest(''.join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files) if p.startswith('code/')).encode())
    if code_hash != official['official_code_hash']: raise RuntimeError('official code hash differs')
    if h.sha(ROOT/official['case_archive']['path']) != official['case_archive']['sha256']:
        raise RuntimeError('official archive differs')
    return head,manifest,official,files


def run(run_id):
    began = time.perf_counter()
    head,spec,official,files = check()
    batch=RESULTS/run_id
    batch.mkdir(parents=True,exist_ok=False)
    deadline=began+spec['timeouts_seconds']['batch']
    meta=dict(run_id=run_id,source_commit=SOURCE,runner_commit=head,manifest=spec,
              official_code_hash=official['official_code_hash'],config_sha256=files['data/config.txt']['sha256'],
              input_archive_sha256=official['case_archive']['sha256'],environment=h.environment(),
              started_at=h.utc(),status='running',calls=dict(solver=0,external_E0=0,internal_E1=0,E2=0,retries=0),
              completed=0,stop_reason=None,worker_ramp=[1],cold_start='fresh interpreter per cell; OS caches not flushed')
    h.write(batch/'batch.json',meta)
    stop=threading.Event()
    results={}
    with tempfile.TemporaryDirectory(prefix='p1-v4-pilot-input-') as tmp:
        inputs=Path(tmp)
        with zipfile.ZipFile(ROOT/official['case_archive']['path']) as z:
            for n in range(1,101):
                c=f'{n:03d}'; raw=z.read(f'data/case_{c}.json')
                if h.digest(raw)!=files[f'data/case_{c}.json']['sha256']: raise RuntimeError(f'graph {c} mismatch')
                (inputs/f'case_{c}.json').write_bytes(raw)
        for c,k in CELLS:
            folder=batch/'cells'/c/f'k{k}'; folder.mkdir(parents=True)
            h.write(folder/'run.json',dict(case_id=c,cores=k,status='not_run',calls={'solver':0,'external_E0':0,'internal_E1':0,'E2':0},
                                           graph_sha256=files[f'data/case_{c}.json']['sha256'],reason='not dispatched'))
        def worker(job):
            c,k=job; folder=batch/'cells'/c/f'k{k}'; graph=inputs/f'case_{c}.json'
            plan=folder/'plan.json'; diag=folder/'diagnostics.json'; result=folder/'result.json'
            row=dict(case_id=c,cores=k,status='running',started_at=h.utc(),finished_at=None,
                     graph_sha256=files[f'data/case_{c}.json']['sha256'],calls={'solver':0,'external_E0':0,'internal_E1':0,'E2':0},
                     artifacts={},reason=None)
            h.write(folder/'run.json',row)
            try:
                if stop.is_set(): raise RuntimeError('batch stopped before solver')
                row['solver']=smoke.process([sys.executable,'-B','src/q1/unified.py',graph,'--cores',str(k),'--output',plan,'--diagnostics',diag],
                                            folder,'solver',300,deadline,lambda:row['calls'].__setitem__('solver',1))
                if row['solver']['status']!='ok': raise RuntimeError('solver '+row['solver']['status'])
                info=h.read(diag); plan_obj=h.read(plan)
                if set(plan_obj)!={'node_to_subgraph','core_schedules'} or len(plan_obj['core_schedules'])!=k:
                    raise RuntimeError('plan schema/cores mismatch')
                chosen=[x for x in info['candidates'] if x['name']==info['selected']]
                if len(chosen)!=1 or h.sha(plan)!=chosen[0]['plan_sha256']: raise RuntimeError('selected plan hash mismatch')
                row['online_ledger']=ledger6((folder/'solver.stdout.txt').read_text(),info)
                if not row['online_ledger']['exact']: raise RuntimeError('ambiguous online E1 call ledger')
                row['calls']['internal_E1']=row['online_ledger']['actual_e1_calls']
                if row['calls']['internal_E1']>6: raise RuntimeError('per-cell E1 bound exceeded')
                if stop.is_set():
                    row['status']='not_run'; row['reason']='batch stopped after solver, before external E0'
                    return row
                row['evaluation']=smoke.process([sys.executable,'-B',h.OFFICIAL/'code/multicore_cut_evaluate_problem_1.py',graph,plan,
                    '--config',h.OFFICIAL/'data/config.txt','--output',result,'--trace-output',folder/'trace.json',
                    '--log-output',folder/'official.log'],folder,'e0',180,deadline,lambda:row['calls'].__setitem__('external_E0',1))
                if row['evaluation']['status']!='ok': raise RuntimeError('external E0 '+row['evaluation']['status'])
                score=h.read(result)
                if score['scene']!='A' or score['num_cores']!=k or score['makespan']<=0:
                    raise RuntimeError('external E0 identity/value mismatch')
                if info['stop_reason']!='first-score-failure':
                    row['consistency']=smoke.winner_check(info,score)
                else:
                    row['consistency']={'status':'internal-score-failure','reason':'fixed algorithm fallback; external E0 valid'}
                row.update(status='ok',selected=info['selected'],stop_reason=info['stop_reason'],
                           makespan_cycles=score['makespan'],data_movement_bytes=score['data_movement_bytes'])
            except BaseException as e:
                row.update(status='timeout' if any(row.get(p,{}).get('status')=='timeout' for p in ('solver','evaluation')) else 'failed',
                           reason=f'{type(e).__name__}: {e}')
                stop.set()
            finally:
                row['finished_at']=h.utc()
                for p in folder.iterdir():
                    if p.is_file() and p.name!='run.json': row['artifacts'][p.name]=h.artifact(p)
                h.write(folder/'run.json',row)
                print(json.dumps({'case':c,'cores':k,'status':row['status'],'makespan':row.get('makespan_cycles'),'E1':row['calls']['internal_E1']}),flush=True)
            return row
        inflight={}; next_index=0; successful=0
        with ThreadPoolExecutor(max_workers=1) as pool:
            while next_index<len(CELLS) or inflight:
                limit=1
                while not stop.is_set() and next_index<len(CELLS) and len(inflight)<limit and time.perf_counter()<deadline:
                    job=CELLS[next_index]; next_index+=1
                    inflight[pool.submit(worker,job)]=job
                if time.perf_counter()>=deadline: stop.set()
                if not inflight: break
                done,_=wait(inflight,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:
                    job=inflight.pop(future)
                    try: row=future.result()
                    except BaseException as e:
                        stop.set(); row={'status':'failed','reason':f'supervisor {type(e).__name__}: {e}','calls':{}}
                    results[job]=row
                    if row['status']=='ok': successful+=1
                    else: stop.set()
                    meta['completed']=len(results)
                    meta['calls']={key:sum(r['calls'].get(key,0) for r in results.values()) for key in meta['calls']}
                    meta['stop_reason']=row.get('reason') if stop.is_set() and not meta['stop_reason'] else meta['stop_reason']
                    h.write(batch/'batch.json',meta)
        meta['finished_at']=h.utc(); meta['wall_seconds']=time.perf_counter()-began
        meta['status']='complete' if successful==4 else 'stopped'
        meta['status_counts']=dict(Counter(h.read(batch/'cells'/c/f'k{k}'/'run.json')['status'] for c,k in CELLS))
        meta['cleanup_confirmed']=all(h.read(p)['cleanup_confirmed'] for p in batch.glob('cells/*/k*/*-process.json'))
        h.write(batch/'batch.json',meta)
        print(json.dumps({'run_id':run_id,'status':meta['status'],'counts':meta['status_counts'],'calls':meta['calls'],
                          'wall_seconds':meta['wall_seconds'],'cleanup_confirmed':meta['cleanup_confirmed']}),flush=True)
        return 0 if meta['status']=='complete' and meta['cleanup_confirmed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('run_id'); args=p.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in ('.','..'): p.error('invalid run_id')
    raise SystemExit(run(args.run_id))
