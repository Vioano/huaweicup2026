import datetime, json, os, signal, subprocess, sys, time
from pathlib import Path
root = Path.cwd()
out = root / 'output/p1-two-cell-supervisor/20260925T0038Z-s6607'
runner = [sys.executable, '-B', 'src/q1_benchmarks/s6607_structural_full500.py', '--output-root', 'results/a/p1-structural-runner-pilot-20260925/20260925T0038Z-s6607', '--cases', '001,051', '--cores', '5', '--workers', '1']
env = os.environ.copy()
env.update(PYTHONPATH='.:data/raw/a/official/code', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def snapshot():
    raw = subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,pgid='], text=True)
    rows=[]
    for line in raw.splitlines():
        p=line.split()
        if len(p)>=4:
            try: rows.append({'pid':int(p[0]),'ppid':int(p[1]),'rss_kib':int(p[2]),'pgid':int(p[3])})
            except ValueError: pass
    return rows
proc = subprocess.Popen(runner, cwd=root, env=env, start_new_session=True, stdout=(out/'runner.stdout.txt').open('xb'), stderr=(out/'runner.stderr.txt').open('xb'))
t0=utc(); started=time.monotonic(); peak=0; samples=[]; seen_pids=set(); seen_groups={proc.pid}; stopped=False
while proc.poll() is None:
    rows=snapshot(); bypid={r['pid']:r for r in rows}; ids={proc.pid}; changed=True
    while changed:
        more={r['pid'] for r in rows if r['ppid'] in ids}
        changed=not more.issubset(ids); ids |= more
    descendants=[bypid[i] for i in ids if i in bypid]
    total=sum(r['rss_kib'] for r in descendants); peak=max(peak,total); seen_pids.update(ids)
    for r in descendants: seen_groups.add(r['pgid'])
    samples.append({'at':utc(),'aggregate_rss_kib':total,'pids':[r['pid'] for r in descendants]})
    if total > 8*1024*1024:
        stopped=True
        for pg in sorted(seen_groups):
            try: os.killpg(pg, signal.SIGTERM)
            except ProcessLookupError: pass
        end=time.monotonic()+3
        while time.monotonic()<end:
            if proc.poll() is not None: break
            time.sleep(.1)
        for pg in sorted(seen_groups):
            try: os.killpg(pg, signal.SIGKILL)
            except ProcessLookupError: pass
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: pass
        break
    time.sleep(1)
code=proc.wait()
# Verify no processes remain in process groups observed from this owned tree.
left=[]
for r in snapshot():
    if r['pgid'] in seen_groups: left.append(r)
receipt={'command':runner,'interpreter':'<locked-python-3.12>','started_at_utc':t0,'finished_at_utc':utc(),'wall_seconds':time.monotonic()-started,'runner_pid':proc.pid,'runner_exit_code':code,'rss_limit_kib':8*1024*1024,'sample_interval_seconds':1,'sampled_peak_aggregate_rss_kib':peak,'sample_count':len(samples),'observed_pids':sorted(seen_pids),'observed_process_groups':sorted(seen_groups),'rss_samples':samples,'rss_limit_exceeded':stopped,'remaining_owned_group_processes':left,'cleanup_confirmed':not left}
(out/'supervisor.json').write_text(json.dumps(receipt,indent=2)+'\n')
sys.exit(124 if stopped else code)
