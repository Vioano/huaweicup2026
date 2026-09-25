"""Dedicated Linux Colab VM guard. Prepared for review; invoking starts full500."""
import ctypes, hashlib, json, os, signal, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/content/p1_s6607_repo')
EXPECTED_HEAD = 'bd6dc85a0b69f30d08714cbb46200f90632bb2d7'
EXPECTED_WRAPPER_SHA256 = '589cf9a544b3edfe31b3b515d5bdf9ec876badda52f3a26310af8640d5baa4e9'
WRAPPER = REPO / 'src/q1_benchmarks/s6607_colab_fresh.py'
OUTPUT = REPO / 'results/a/p1-colab-full500-20260925/20260925T0110Z-s6607'
RECEIPT = REPO / 'output/p1-colab-full500-supervisor-receipt.json'
LIVE = REPO / 'output/p1-colab-full500-supervisor-live.json'
MAX_WALL = 4600

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def proc_table():
    table = {}
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            raw = (directory/'stat').read_text()
            fields = raw[raw.rfind(')')+2:].split()
            table[int(directory.name)] = (int(fields[1]), int(fields[19]), int(fields[21])*os.sysconf('SC_PAGE_SIZE'))
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
            continue
    return table

def descendants(root, birth, table):
    if root not in table or table[root][1] != birth:
        return {}
    result = {root: table[root]}
    while True:
        new = {p:v for p,v in table.items() if p not in result and v[0] in result}
        if not new: return result
        result.update(new)

def repo_process(pid):
    try:
        directory=Path('/proc')/str(pid)
        cwd=os.readlink(directory/'cwd')
        command=(directory/'cmdline').read_bytes()
        return cwd==str(REPO) or cwd.startswith(str(REPO)+'/') or str(REPO).encode() in command
    except OSError: return False

def adopted(birth, table):
    # Only children reparented to this subreaper after this runner was born.
    return {p:v for p,v in table.items() if v[0]==os.getpid() and
            v[1]>=birth and repo_process(p)}

def owned(root, birth, table):
    result=descendants(root,birth,table)
    result.update(adopted(birth,table))
    while True:
        new={p:v for p,v in table.items() if p not in result and v[0] in result}
        if not new: return result
        result.update(new)

def mem_kib():
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, val = line.split(':',1)
        values[key] = int(val.split()[0])
    return values['MemTotal'], values['MemAvailable']

def signal_ids(ids, sig):
    live = proc_table()
    for pid, old in ids.items():
        if pid in live and live[pid][1] == old[1]:
            try: os.kill(pid, sig)
            except ProcessLookupError: pass

def other_repo_scoring():
    found = []
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            pid = int(directory.name)
            if pid == os.getpid(): continue
            cmd = (directory/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            cwd = os.readlink(directory/'cwd')
            if cwd.startswith(str(REPO)) and any(x in cmd for x in
                ('src/q1/', 'src/q1_benchmarks/', 'multicore_cut_evaluate_problem_1', 'src.eval_exact')):
                found.append(pid)
        except (OSError, ValueError): pass
    return found

def cleanup(child, birth, seen):
    if child.poll() is None: signal_ids({child.pid:seen[child.pid]}, signal.SIGSTOP)
    for _ in range(2):
        seen.update(owned(child.pid,birth,proc_table()))
        signal_ids({p:v for p,v in seen.items() if p != child.pid}, signal.SIGSTOP)
        time.sleep(.1)
    seen.update(owned(child.pid,birth,proc_table()))
    signal_ids({p:v for p,v in seen.items() if p != child.pid}, signal.SIGKILL)
    signal_ids({child.pid:seen[child.pid]}, signal.SIGKILL)
    try: child.wait(timeout=10)
    except subprocess.TimeoutExpired: return {'confirmed':False,'reason':'root reap timeout'}
    for pid in seen:
        if pid != child.pid:
            try: os.waitpid(pid,os.WNOHANG)  # only our adopted child can be reaped
            except (ChildProcessError,ProcessLookupError): pass
    live = proc_table()
    remaining = [p for p,v in seen.items() if p in live and live[p][1] == v[1]]
    return {'confirmed':not remaining,'remaining_owned_pids':remaining,
            'scope':'birth-identified root, descendants and repo-owned children adopted by this subreaper'}

def main():
    if RECEIPT.exists() or LIVE.exists() or OUTPUT.exists(): raise FileExistsError('new output, live marker and receipt required')
    record = {'started_at':utc(),'status':'preflight','calls':None,'samples':[], 'cleanup':None}
    child = None; birth = None; seen = {}
    t0 = time.monotonic()
    try:
        if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)!=0:
            raise OSError(ctypes.get_errno(),'PR_SET_CHILD_SUBREAPER failed')
        record['child_subreaper']=True
        head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
        wrapper_sha = sha(WRAPPER)
        if head != EXPECTED_HEAD or wrapper_sha != EXPECTED_WRAPPER_SHA256:
            raise RuntimeError('fixed HEAD/wrapper bytes mismatch')
        record.update(head=head,wrapper_sha256=wrapper_sha,
                      python=str(REPO/'.venv/bin/python'))
        for i in range(2):
            total,available=mem_kib(); record['samples'].append({'at':utc(),'available_kib':available})
            if abs(total-13286944)>1328694 or available<8*1024*1024:
                raise RuntimeError('VM memory preflight failed')
            if i==0: time.sleep(1)
        if len(os.sched_getaffinity(0))!=2 or other_repo_scoring():
            raise RuntimeError('CPU count or other repo scoring preflight failed')
        argv=[str(REPO/'.venv/bin/python'),'-B',str(WRAPPER),'--full500','--output-root',str(OUTPUT)]
        record.update(argv=argv,workers=1,runner_started_at=utc())
        RECEIPT.parent.mkdir(parents=True,exist_ok=True)
        with (RECEIPT.with_suffix('.stdout.txt')).open('xb') as out, (RECEIPT.with_suffix('.stderr.txt')).open('xb') as err:
            env=os.environ.copy(); env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
            env.update(PYTHONPATH='.:data/raw/a/official/code',PYTHONDONTWRITEBYTECODE='1')
            record['runner_env_overrides']={k:env[k] for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
            child=subprocess.Popen(argv,cwd=REPO,env=env,stdout=out,stderr=err,start_new_session=True)
            table=proc_table()
            if child.pid not in table: raise RuntimeError('runner birth identity unavailable')
            birth=table[child.pid][1]; seen={child.pid:table[child.pid]}
            with LIVE.open('x') as live:
                json.dump({'started_at':record['runner_started_at'],'runner_pid':child.pid,
                           'proc_starttime_ticks':birth,'head':head,'wrapper_sha256':wrapper_sha},live,indent=2)
                live.write('\n')
            record['status']='running'
            while child.poll() is None:
                time.sleep(1)
                total,available=mem_kib(); table=proc_table(); seen.update(owned(child.pid,birth,table))
                rss=sum(table[p][2] for p,v in seen.items() if p in table and table[p][1]==v[1])
                record['samples'].append({'at':utc(),'available_kib':available,'sampled_owned_tree_rss_bytes':rss})
                reason=('available<1GiB' if available<1024*1024 else
                        'treeRSS>9GiB' if rss>9*1024**3 else
                        'wall>4600s' if time.monotonic()-t0>MAX_WALL else None)
                if reason:
                    record.update(status='aborted',abort_reason=reason,cleanup=cleanup(child,birth,seen)); break
            if record['status']=='running':
                child.wait(); record.update(status='runner-exited',exit_code=child.returncode)
                seen.update(owned(child.pid,birth,proc_table()))
                if any(p!=child.pid for p in seen if p in proc_table()):
                    record['cleanup']=cleanup(child,birth,seen)
        batch=OUTPUT/'batch.json'
        if batch.exists():
            state=json.loads(batch.read_bytes()); record['batch_sha256']=sha(batch)
            record['batch_status']=state.get('status')
            if state.get('status') in ('complete','stopped') and state.get('actual_calls') is not None:
                record['calls']=state['actual_calls']; record['known_calls_lower_bound']=state.get('known_calls_lower_bound')
            if record['status']=='runner-exited' and child.returncode==0 and state.get('status')=='complete':
                record['status']='complete'
        if record['status']!='complete' and record['cleanup'] is None:
            record['cleanup']={'confirmed':False,'reason':'normal/failed exit descendants not independently certified'}
    except Exception as exc:
        record.update(status='failed',failure={'type':type(exc).__name__,'message':str(exc)})
        if child is not None and child.poll() is None:
            if birth is not None:
                record['cleanup']=cleanup(child,birth,seen)
            else:
                child.kill(); child.wait(timeout=10)
                record['cleanup']={'confirmed':False,'reason':'root killed; descendant birth unknown; stop VM'}
    finally:
        if child is not None:
            table=proc_table()
            if birth is not None: seen.update(adopted(birth,table))
            record['remaining_owned_pids']=[p for p,v in seen.items() if p in table and table[p][1]==v[1]]
            record['unclassified_adopted_pids']=(
                [p for p,v in table.items() if birth is not None and v[0]==os.getpid()
                 and v[1]>=birth and p not in seen and p!=child.pid])
            if record['remaining_owned_pids']:
                record['status']='cleanup-unknown'
                record['cleanup']={'confirmed':False,'reason':'owned PIDs remain after terminal runner receipt'}
            if record['unclassified_adopted_pids']:
                record['status']='cleanup-unknown'
                record['cleanup']={'confirmed':False,'reason':'unclassified adopted children; do not kill unrelated processes; stop VM'}
            if record['status']=='complete' and record['cleanup'] and not record['cleanup'].get('confirmed'):
                record['status']='cleanup-unknown'
        if record['cleanup'] is None:
            record['cleanup']={'confirmed':True,'scope':'no owned root/descendant/adopted process remains'} if child is not None else {'confirmed':True,'scope':'preflight failed before runner launch'}
        if child is None: record['calls']={'solver':0,'E1':0,'E0':0,'E2':0}
        record['sampled_max_tree_rss_bytes']=max((s.get('sampled_owned_tree_rss_bytes',0) for s in record['samples']),default=0)
        record['sampled_min_available_kib']=min((s['available_kib'] for s in record['samples']),default=None)
        record['external_vm_stop_required']=bool(record['cleanup'] and not record['cleanup'].get('confirmed'))
        record.update(supervisor_sha256=sha(__file__),finished_at=utc(),wall_seconds=time.monotonic()-t0,
                      rss_scope='1-second samples; maximum observed is not a true peak')
        RECEIPT.parent.mkdir(parents=True,exist_ok=True)
        with RECEIPT.open('x') as out: json.dump(record,out,indent=2); out.write('\n')
    return 0 if record['status']=='complete' else 1

if __name__=='__main__': raise SystemExit(main())
