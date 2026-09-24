"""Frozen four-cell smoke controller; source binding and EXECUTE are separate gates.

Reuses finite-probe artifact/environment helpers and the Pro supervisor process-group
model. Adds sampled group RSS and the online-E1 ledger; never ranks candidates itself.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h

HERE = Path(__file__).relative_to(ROOT).as_posix()
RESULTS = ROOT / 'results/a/q1-unified-smoke-20260925'
CELLS = ['051', '044', '031', '008']
GIB4 = 4 * 1024**3


def group_members(pgid):
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,pgid=,rss=,stat='], timeout=1)
    rows = []
    for line in raw.decode().splitlines():
        pid, group, rss, state = line.split()
        if int(group) == pgid:
            rows.append({'pid': int(pid), 'rss_bytes': int(rss) * 1024, 'state': state})
    return rows


def group_gone(pgid):
    try:
        os.killpg(pgid, 0)
        return False
    except ProcessLookupError:
        return True


def process(argv, folder, name, timeout, deadline, on_start, rss_limit=GIB4):
    """Own process group only. Timeout includes a 2-second cleanup reserve."""
    start = time.perf_counter()
    end = min(start + timeout, deadline)
    reserve = min(2.0, (end-start) / 3)
    if end-start < 0.3:
        raise TimeoutError('No remaining launch/cleanup budget')
    receipt = dict(argv=[str(a) for a in argv], cwd='.', started_at=h.utc(), status='starting',
                   pid=None, exit_code=None, cleanup_confirmed=False, sampled_peak_group_rss_bytes=0,
                   rss_limit_bytes=rss_limit, sample_interval_seconds=0.1,
                   rss_scope='Sum of observed owned process-group RSS; sampled, not continuous',
                   timeout_including_cleanup_seconds=end-start, cleanup_reserve_seconds=reserve)
    h.write(folder / f'{name}-process.json', receipt)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    child = None
    reason = None
    try:
        with (folder/f'{name}.stdout.txt').open('xb') as out, (folder/f'{name}.stderr.txt').open('xb') as err, (folder/f'{name}.rss.jsonl').open('x') as samples:
            child = subprocess.Popen(receipt['argv'], cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
            receipt.update(pid=child.pid, process_group_id=child.pid, status='running')
            h.write(folder/f'{name}-process.json', receipt)
            on_start()
            while True:
                code = child.poll()
                members = group_members(child.pid)
                rss = sum(row['rss_bytes'] for row in members)
                receipt['sampled_peak_group_rss_bytes'] = max(rss, receipt['sampled_peak_group_rss_bytes'])
                samples.write(json.dumps(dict(elapsed_seconds=time.perf_counter()-start, rss_bytes=rss, members=members))+'\n')
                samples.flush()
                if rss > rss_limit:
                    reason = 'rss_limit'; break
                if code is not None and not members and group_gone(child.pid):
                    break
                if time.perf_counter() >= end-reserve:
                    reason = 'timeout'; break
                time.sleep(min(0.1, max(0, end-reserve-time.perf_counter())))
    except BaseException as exc:
        reason = 'supervisor_failure'
        receipt['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if child is not None:
            if child.poll() is None or not group_gone(child.pid):
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                child.wait(timeout=max(0, end-time.perf_counter()))
            except subprocess.TimeoutExpired:
                reason = 'cleanup_failure'
            while not group_gone(child.pid) and time.perf_counter() < end:
                time.sleep(0.02)
            receipt.update(exit_code=child.returncode, cleanup_confirmed=child.poll() is not None and group_gone(child.pid))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(finished_at=h.utc(), wall_seconds=time.perf_counter()-start,
                       user_cpu_seconds=after.ru_utime-before.ru_utime,
                       system_cpu_seconds=after.ru_stime-before.ru_stime,
                       cpu_scope='Controller child rusage including ps sampler',
                       status=reason or ('ok' if receipt['exit_code'] == 0 else 'failed'))
        h.write(folder/f'{name}-process.json', receipt)
    if not receipt['cleanup_confirmed']:
        raise RuntimeError('Owned group cleanup not confirmed; no further dispatch permitted')
    return receipt


def ledger(stdout, diagnostics=None):
    events = []
    for line in stdout.splitlines():
        try:
            item = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(item, dict) and 'event' in item:
            events.append(item)
    starts = [x for x in events if x['event'] == 'score_attempt_started']
    returns = [x for x in events if x['event'] == 'score_attempt_returned']
    confirmed = sum(x.get('worker_pid') is not None for x in returns)
    unresolved = len(starts)-len(returns)
    if not 0 <= len(returns) <= len(starts) <= 4:
        raise ValueError('Invalid or over-budget online score ledger')
    value = dict(score_attempts_observed=len(starts), score_returns_observed=len(returns),
                 confirmed_worker_calls_lower_bound=confirmed,
                 worker_calls_upper_bound=confirmed+unresolved,
                 actual_e1_calls=confirmed if unresolved == 0 else None,
                 exact=unresolved == 0, unresolved_requests=unresolved)
    if diagnostics is not None:
        records = diagnostics['online_scores']
        normalized = [{k:v for k,v in row.items() if k not in ('event','monotonic_seconds')} for row in returns]
        if normalized != records or diagnostics['online_score_attempts'] != len(starts) or diagnostics['actual_e1_calls'] != confirmed or unresolved:
            raise ValueError('Final diagnostics and flushed event ledger disagree')
        if not any(x['event'] == 'solver_completed' for x in events):
            raise ValueError('Missing solver completion event')
    return value


def winner_check(info, result):
    scores = info['online_scores']
    if info['stop_reason'] == 'first-score-failure' or any(x['status'] != 'ok' for x in scores):
        raise ValueError('Internal scoring failure: batch must stop')
    if not scores:
        if info['actual_e1_calls'] or info['online_score_attempts'] or len(info['candidates']) != 1:
            raise ValueError('Invalid zero-E1 single-plan path')
        return {'status': 'not_applicable', 'reason': 'single distinct plan, zero E1'}
    selected = [x for x in scores if x['name'] == info['selected']]
    if len(selected) != 1:
        raise ValueError('Winner record absent or ambiguous')
    expected = selected[0]
    if expected['makespan'] != result['makespan'] or expected['data_movement_bytes'] != result['data_movement_bytes']:
        raise ValueError('Internal winner versus external E0 makespan/movement mismatch')
    return {'status': 'equal', 'makespan': result['makespan'], 'data_movement_bytes': result['data_movement_bytes']}


def verify(spec, spec_path):
    if sys.version_info[:2] != (3,12):
        raise RuntimeError('Locked Python 3.12 required')
    if spec['cells'] != [[case,5] for case in CELLS] or spec['timeouts_seconds'] != {'solver':300,'external_E0':120,'batch':1800} or spec['maximum_calls'] != {'solver':4,'external_E0':4,'internal_E1':16,'E2':0,'retries':0}:
        raise ValueError('Frozen scope mismatch')
    source = spec.get('source_commit')
    if not source or len(source) != 40:
        raise RuntimeError('WAIT_SOURCE_AND_ROOT_EXECUTE: fixed algorithm source is missing')
    head = h.git('rev-parse','HEAD').decode().strip()
    if h.git('diff','--name-only',head).strip():
        raise RuntimeError('Tracked source is dirty')
    receipts = []
    paths = h.git('ls-tree','-r','--name-only',source,'src/q1','src/eval_exact').decode().splitlines()
    paths = [p for p in paths if p.endswith(('.py','.json'))]
    if 'src/q1/unified.py' not in paths or 'src/eval_exact/pool.py' not in paths:
        raise ValueError('Frozen source closure incomplete')
    actual = [str(p.relative_to(ROOT)) for folder in ('src/q1','src/eval_exact') for p in (ROOT/folder).rglob('*') if p.suffix in ('.py','.json')]
    if set(paths) != set(actual):
        raise ValueError('Local algorithm module set differs from frozen source')
    dependencies = [(p,source) for p in paths] + [(p,head) for p in (HERE,'src/q1_benchmarks/bounded_full4_e0.py',str(spec_path.relative_to(ROOT)))] + [(p,source) for p in ('uv.lock','pyproject.toml','docs/a/source-manifest.json')]
    for path, commit in dependencies:
        raw = (ROOT/path).read_bytes()
        if raw != h.git('show',f'{commit}:{path}'):
            raise ValueError(f'Frozen source mismatch: {path}')
        receipts.append(dict(path=path,commit=commit,sha256=h.digest(raw)))
    official = h.read(ROOT/'docs/a/source-manifest.json')
    files = {r['path']:r for r in official['files']}
    for path,row in files.items():
        if path.startswith('code/') or path == 'data/config.txt':
            if h.sha(h.OFFICIAL/path) != row['sha256']:
                raise ValueError(f'Official source/config mismatch: {path}')
    code_hash = h.digest(''.join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files) if p.startswith('code/')).encode())
    if code_hash != official['official_code_hash'] or h.sha(ROOT/official['case_archive']['path']) != official['case_archive']['sha256']:
        raise ValueError('Official aggregate/archive mismatch')
    return head, official, files, receipts


def run(spec_path, run_id, authorization):
    spec = h.read(spec_path)
    head, official, files, receipts = verify(spec,spec_path)
    auth = h.read(authorization)
    if auth.get('gate') != 'AUTHORIZED' or auth.get('runner_commit') != head or auth.get('source_commit') != spec['source_commit'] or auth.get('run_id') != run_id:
        raise RuntimeError('WAIT_ROOT_EXECUTE: exact runner/source/run authorization required')
    batch = RESULTS/run_id
    batch.mkdir(parents=True,exist_ok=False)
    h.write(batch/'EXECUTION_AUTHORIZATION.json',auth)
    started = time.perf_counter(); deadline = started+1800
    meta = dict(run_id=run_id,status='running',gate='RUNNING',started_at=h.utc(),runner_commit=head,
                source_commit=spec['source_commit'],source_receipts=receipts,manifest=spec,
                environment=h.environment(),official_code_hash=official['official_code_hash'],
                config_sha256=files['data/config.txt']['sha256'],input_archive_sha256=official['case_archive']['sha256'],
                calls=dict(solver=0,external_E0=0,internal_E1_confirmed=0,internal_E1_upper_bound=0,E2=0,retries=0))
    rows = []
    for case in CELLS:
        folder=batch/'cells'/case/'k5'; folder.mkdir(parents=True)
        row=dict(case_id=case,cores=5,status='not_run',calls={'solver':0,'external_E0':0},artifacts={})
        h.write(folder/'run.json',row); rows.append((folder,row))
    h.write(batch/'batch.json',meta)
    failure=None
    try:
        with tempfile.TemporaryDirectory(prefix='q1-unified-smoke-') as temp:
            for folder,row in rows:
                if failure:
                    row['not_run_reason']=failure; h.write(folder/'run.json',row); continue
                case=row['case_id']; graph=Path(temp)/f'case_{case}.json'
                plan=folder/'plan.json'; diag=folder/'diagnostics.json'; result=folder/'result.json'
                row.update(status='running',started_at=h.utc(),graph_sha256=files[f'data/case_{case}.json']['sha256'])
                def launched(kind):
                    row['calls'][kind]+=1; meta['calls'][kind]+=1
                    h.write(folder/'run.json',row); h.write(batch/'batch.json',meta)
                try:
                    verify(spec,spec_path)
                    with zipfile.ZipFile(ROOT/official['case_archive']['path']) as z:
                        raw=z.read(f'data/case_{case}.json')
                    if h.digest(raw)!=row['graph_sha256']: raise ValueError('Graph hash mismatch')
                    graph.write_bytes(raw)
                    row['solver']=process([sys.executable,'-B','src/q1/unified.py',graph,'--cores','5','--output',plan,'--diagnostics',diag],folder,'solver',300,deadline,lambda:launched('solver'))
                    if row['solver']['status']!='ok': raise RuntimeError('Solver '+row['solver']['status'])
                    info=h.read(diag); row['online_ledger']=ledger((folder/'solver.stdout.txt').read_text(),info)
                    if info['stop_reason']=='first-score-failure' or any(x['status']!='ok' for x in info['online_scores']): raise RuntimeError('Internal score failure; stop before E0')
                    obj=h.read(plan)
                    if set(obj)!={'node_to_subgraph','core_schedules'} or len(obj['core_schedules'])!=5: raise ValueError('Plan schema/cores mismatch')
                    winner=[x for x in info['candidates'] if x['name']==info['selected']]
                    if len(winner)!=1 or h.sha(plan)!=winner[0]['plan_sha256']: raise ValueError('Selected candidate plan hash mismatch')
                    verify(spec,spec_path)
                    row['evaluation']=process([sys.executable,'-B',h.OFFICIAL/'code/multicore_cut_evaluate_problem_1.py',graph,plan,'--config',h.OFFICIAL/'data/config.txt','--output',result,'--trace-output',folder/'trace.json','--log-output',folder/'official.log'],folder,'e0',120,deadline,lambda:launched('external_E0'))
                    if row['evaluation']['status']!='ok': raise RuntimeError('E0 '+row['evaluation']['status'])
                    score=h.read(result); h.read(folder/'trace.json')
                    if score['scene']!='A' or score['num_cores']!=5 or score['makespan']<=0: raise ValueError('E0 identity/value mismatch')
                    row.update(consistency=winner_check(info,score),status='ok',selected=info['selected'],makespan_cycles=score['makespan'],data_movement_bytes=score['data_movement_bytes'])
                except BaseException as exc:
                    failure=f'{case}: {type(exc).__name__}: {exc}'
                    row.update(status='failed',failure=failure)
                finally:
                    stdout=folder/'solver.stdout.txt'
                    if 'online_ledger' not in row and stdout.exists():
                        try: row['online_ledger']=ledger(stdout.read_text())
                        except Exception as exc: row['online_ledger']={'actual_e1_calls':None,'error':str(exc),'confirmed_worker_calls_lower_bound':0,'worker_calls_upper_bound':4}
                    account=row.get('online_ledger',{})
                    meta['calls']['internal_E1_confirmed']+=account.get('confirmed_worker_calls_lower_bound',0)
                    meta['calls']['internal_E1_upper_bound']+=account.get('worker_calls_upper_bound',0)
                    row['finished_at']=h.utc()
                    for path in folder.iterdir():
                        if path.is_file() and path.name!='run.json': row['artifacts'][path.name]=h.artifact(path)
                    h.write(folder/'run.json',row); h.write(batch/'batch.json',meta)
    except BaseException as exc:
        failure = failure or f'Supervisor {type(exc).__name__}: {exc}'
        for folder,row in rows:
            if row['status']=='not_run':
                row['not_run_reason']=failure
                h.write(folder/'run.json',row)
        raise
    finally:
        meta.update(status='failed' if failure else 'complete',gate='CLOSED',failure=failure,finished_at=h.utc(),wall_seconds=time.perf_counter()-started)
        meta['cells']=[row for _,row in rows]
        meta['cleanup_confirmed']=all(h.read(p)['cleanup_confirmed'] for folder,_ in rows for p in folder.glob('*-process.json'))
        h.write(batch/'batch.json',meta)
    return 1 if failure else 0


def selftest():
    """Fake child processes and dictionaries only: zero graph, E0 or E1 calls."""
    checks=[]
    with tempfile.TemporaryDirectory(prefix='unified-controller-test-') as temp:
        folder=Path(temp)
        for name,code,timeout,limit,expected in [('success','print(42)',3,GIB4,'ok'),('timeout','import time; time.sleep(30)',0.6,GIB4,'timeout'),('rss','import time; a=bytearray(8*1024**2); time.sleep(30)',3,1,'rss_limit'),('nonzero','raise SystemExit(3)',3,GIB4,'failed')]:
            rec=process([sys.executable,'-B','-c',code],folder,name,timeout,time.perf_counter()+5,lambda:None,limit)
            assert rec['status']==expected and rec['cleanup_confirmed'],rec
            checks.append(name)
    assert ledger('{"event":"score_attempt_started"}\n')['actual_e1_calls'] is None
    checks.append('interrupted E1 request remains unknown')
    movement={'scheduled_copy_bytes':12,'spill_copy_bytes':0}
    info={'stop_reason':'scored','selected':'a','online_scores':[dict(name='a',status='ok',makespan=3,data_movement_bytes=movement)]}
    assert winner_check(info,dict(makespan=3,data_movement_bytes=movement))['status']=='equal'
    try: winner_check(info,dict(makespan=3,data_movement_bytes={'scheduled_copy_bytes':12,'spill_copy_bytes':1}))
    except ValueError: checks.append('full movement mismatch rejected')
    else: raise AssertionError('Movement mismatch was accepted')
    info['online_scores'][0]['status']='error'
    try: winner_check(info,{})
    except ValueError: checks.append('internal failure rejected')
    else: raise AssertionError('Internal failure was accepted')
    return dict(status='passed',checks=checks,real_graph_reads=0,solver_calls=0,E0_calls=0,E1_calls=0,generated_at=h.utc())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['selftest','run'])
    p.add_argument('--manifest',type=Path)
    p.add_argument('--run-id')
    p.add_argument('--authorization',type=Path)
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    if args.action=='selftest':
        result=selftest()
        if args.report: h.write(args.report,result)
        print(json.dumps(result)); return
    if not args.manifest or not args.run_id or not args.authorization: p.error('run requires manifest, run-id, authorization')
    if Path(args.run_id).name!=args.run_id or args.run_id in ('.','..'): p.error('run-id must be a basename')
    raise SystemExit(run(args.manifest.resolve(),args.run_id,args.authorization))

if __name__=='__main__': main()
