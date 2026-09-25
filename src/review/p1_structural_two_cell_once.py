"""One supervised run of frozen structural-refine on cases 016/024 at K5."""
from __future__ import annotations
import argparse,ctypes,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OFFICIAL=ROOT/'data/raw/a/official'
CASES=('016','024');SOLVER='3a1b82b71ca1ff6689eb8e72f17d26c48b52073c'
MAX_E1=18
GRAPH_SHA={'016':'76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef','024':'f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def proc_table():
 out={}
 for d in Path('/proc').glob('[0-9]*'):
  try:
   f=(d/'stat').read_text().rsplit(') ',1)[1].split();out[int(d.name)]=(int(f[1]),int(f[19]),int(f[21])*os.sysconf('SC_PAGE_SIZE'))
  except (OSError,ValueError,IndexError):pass
 return out
def repo_owned(birth,table):
 found={}
 for pid,(ppid,start,rss) in table.items():
  if ppid!=os.getpid() or start<birth:continue
  try:
   cwd=os.readlink(f'/proc/{pid}/cwd');cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
   if cwd==str(ROOT) or cwd.startswith(str(ROOT)+'/') or str(ROOT).encode() in cmd:found[pid]=(ppid,start,rss)
  except OSError:pass
 return found
def drain_adopted(birth):
 before=repo_owned(birth,proc_table());seen=dict(before)
 for pid,(_,start,_) in before.items():
  live=proc_table().get(pid)
  if live and live[1]==start:
   try:os.kill(pid,signal.SIGKILL)
   except ProcessLookupError:pass
 for _ in range(20):
  table=proc_table();remaining=[p for p,(_,st,_) in seen.items() if p in table and table[p][1]==st]
  if not remaining:break
  for pid in remaining:
   try:os.kill(pid,signal.SIGKILL)
   except ProcessLookupError:pass
   for pid in seen:
    try:os.waitpid(pid,os.WNOHANG)
    except (ChildProcessError,ProcessLookupError):pass
  time.sleep(.1)
 for pid in seen:
  try:os.waitpid(pid,os.WNOHANG)
  except (ChildProcessError,ProcessLookupError):pass
 return {'confirmed':not remaining,'observed_pids':sorted(seen),'remaining_pids':remaining}
def supervised_process(process_fn,argv,folder,name,timeout,input_root,birth):
 result=None;raised=None
 from src.q1_benchmarks import bounded_probe_e0 as helper
 original=subprocess.Popen;ident={}
 class Tracked:
  def __init__(self,child,streams):self.child=child;self.pid=child.pid;self.streams=streams
  def __getattr__(self,key):return getattr(self.child,key)
  def wait(self,*a,**kw):
   rc=self.child.wait(*a,**kw)
   for src,dst in self.streams:
    if src.exists():dst.write_bytes(src.read_bytes())
   return rc
 def hooked(*args,**kwargs):
  child=original(*args,**kwargs);pid=child.pid
  try:
   stat=Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split();start=int(stat[19]);pgid=os.getpgid(pid)
  except (OSError,ValueError,IndexError):start=None;pgid=None
  ident.update(pid=pid,pgid=pgid,linux_proc_start_ticks=start)
  (folder/'process-live.json').write_text(json.dumps(ident)+'\n')
  streams=[]
  for key in ('stdout','stderr'):
   stream=kwargs.get(key);src=Path(stream.name) if getattr(stream,'name',None) else None
   if src:streams.append((src,src.with_name(src.stem+'.raw'+src.suffix)))
  return Tracked(child,streams)
 try:
  helper.subprocess.Popen=hooked
  result=process_fn(argv,folder,name,timeout,input_root)
 except Exception as exc:raised=exc
 finally:helper.subprocess.Popen=original
 cleanup=drain_adopted(birth)
 if raised:raise RuntimeError(f'{name} helper failed; adopted cleanup={cleanup}') from raised
 result['adopted_cleanup']=cleanup
 result['process_identity']=ident
 if not cleanup['confirmed']:raise RuntimeError(f'{name} left owned descendants: {cleanup}')
 return result
def diag_ok(d):
 if type(d.get('actual_e1_calls_total')) is not int:return False
 parent=d.get('parent',{});base=parent.get('baseline',{}).get('diagnostics',{})
 if type(base.get('actual_e1_calls')) is not int:return False
 scores=base.get('online_scores',[])
 if any(not isinstance(x,dict) or x.get('status')!='ok' or x.get('worker_pid') is None for x in scores):return False
 ref=parent.get('refinement',{})
 if ref.get('actual_e1_calls') is None or ref.get('actual_e1_calls')!=0:return False
 extra=d.get('extra')
 return isinstance(extra,list) and all(x.get('status') in ('strict-improvement','no-strict-improvement','duplicate-plan') and (x.get('score') is None or x.get('score',{}).get('status')=='ok') and (not x.get('score_attempted') or x.get('score',{}).get('worker_pid') is not None) for x in extra)
def main(output_root=None,process_fn=None,subreaper_enable=None,deadline_monotonic=None):
 from src.q1_benchmarks.bounded_probe_e0 import process as bounded_process
 process_fn=process_fn or bounded_process
 if subreaper_enable is None:subreaper_enable=lambda:ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)
 if subreaper_enable()!=0:raise OSError(ctypes.get_errno(),'subreaper setup failed')
 driver=proc_table().get(os.getpid());
 if not driver:raise RuntimeError('driver birth ticks unavailable')
 birth=driver[1];out=Path(output_root or '/content/p1_structural_two_cell/run');out.mkdir(parents=True,exist_ok=False)
 os.environ['PYTHONPATH']=str(ROOT)+os.pathsep+str(OFFICIAL/'code')+os.pathsep+os.environ.get('PYTHONPATH','')
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
 calls={'solver':0,'E1':0,'E0':0,'E2':0,'retry':0};record={'status':'running','solver_commit':SOLVER,'cases':CASES,'cores':5,'worker_limit':1,'maximum_calls':{'solver':2,'E1':MAX_E1,'E0':2,'E2':0,'retry':0},'calls':calls,'E1_reserved_max':MAX_E1,'subreaper':True,'cells':[]}
 (out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
 stopped=False;inputs=out/'inputs';inputs.mkdir()
 for case in CASES:
  cell=out/case;cell.mkdir();row={'case':case,'cores':5,'status':'not_run','calls':{'solver':0,'E1':0,'E0':0},'graph_sha256':sha(ROOT/f'data/raw/a/official-cases/case_{case}.json') if (ROOT/f'data/raw/a/official-cases/case_{case}.json').exists() else None}
  graph=ROOT/f'case_{case}.json'
  expected=GRAPH_SHA[case]
  record['cells'].append(row)
  if stopped:row['not_run_reason']='prior cell failed';continue
  row['graph_sha256']=sha(graph);plan=cell/f'case_{case}_multicore_res.json';diag=cell/'diagnostics.json'
  try:
   if row['graph_sha256']!=expected:raise RuntimeError('input graph SHA mismatch')
   solver_timeout=min(180,deadline_monotonic-time.monotonic()-120) if deadline_monotonic else 180
   if solver_timeout<1:raise TimeoutError('refuse solver without E0 reserve')
   calls['solver']+=1;calls['E1']=None;row['calls']['solver']=1;row['calls']['E1']=None;row['E1_reserved_max']=9;record['E1_unknown_dispatch']=case;row['status']='solver-running';(out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
   cmd=[sys.executable,'-B',str(ROOT/'src/q1/structural_refine.py'),str(graph),'--cores','5','--output',str(plan),'--diagnostics',str(diag)]
   sr=supervised_process(process_fn,cmd,cell,'solver',solver_timeout,ROOT,birth)
   row['solver']=sr
   if sr.get('status')!='ok' or not plan.is_file() or not diag.is_file():raise RuntimeError('solver failed/missing outputs')
   d=json.loads(diag.read_text());e1=d.get('actual_e1_calls_total')
   if not diag_ok(d) or type(e1)is not int or not 0<=e1<=9 or sum(x['calls']['E1'] or 0 for x in record['cells'] if x is not row)+e1>MAX_E1:raise RuntimeError('diagnostic E1 ledger/status missing or out of bound')
   row['calls']['E1']=e1;record['E1_unknown_dispatch']=None;calls['E1']=sum(x['calls']['E1'] for x in record['cells'] if x is not row and type(x['calls']['E1']) is int)+e1
   obj=json.loads(plan.read_text())
   if set(obj)!={'node_to_subgraph','core_schedules'} or len(obj['core_schedules'])!=5:raise RuntimeError('invalid solver plan contract')
   row['plan_sha256']=sha(plan);row['diagnostic_sha256']=sha(diag)
   if d.get('selected_plan_sha256')!=row['plan_sha256']:raise RuntimeError('diagnostics do not attest emitted plan')
   e0_timeout=min(120,deadline_monotonic-time.monotonic()-12) if deadline_monotonic else 120
   if e0_timeout<1:raise TimeoutError('refuse E0 after remote deadline')
   calls['E0']+=1;row['calls']['E0']=1;row['status']='E0-running';(out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
   evaluator=OFFICIAL/'code/multicore_cut_evaluate_problem_1.py';result=cell/'result.json';trace=cell/'trace.json';log=cell/'official.log'
   er=supervised_process(process_fn,[sys.executable,'-B',str(evaluator),str(graph),str(plan),'--config',str(OFFICIAL/'data/config.txt'),'--output',str(result),'--trace-output',str(trace),'--log-output',str(log)],cell,'E0',e0_timeout,ROOT,birth)
   row['evaluation']=er
   if er.get('status')!='ok' or not all(p.is_file() for p in (result,trace,log)):raise RuntimeError('E0 failed/missing artifacts')
   result_obj=json.loads(result.read_text())
   if result_obj.get('scene')!='A' or result_obj.get('num_cores')!=5 or not isinstance(result_obj.get('makespan'),(int,float)):raise RuntimeError('E0 result identity invalid')
   row['makespan_cycles']=result_obj['makespan'];row['data_movement_bytes']=result_obj.get('data_movement_bytes');row['status']='ok'
  except Exception as exc:row.update(status='failed',failure=f'{type(exc).__name__}: {exc}');stopped=True
  row['finished_monotonic']=time.monotonic();(out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
 record['status']='complete' if len(record['cells'])==2 and all(x['status']=='ok' for x in record['cells']) else 'stopped'
 record['worker_cleanup']=drain_adopted(birth)
 if not record['worker_cleanup']['confirmed']:record['status']='cleanup-unconfirmed'
 record['finished_monotonic']=time.monotonic();(out/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
 if record['status']!='complete':raise SystemExit(1)
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-root',required=True);parser.add_argument('--deadline-monotonic',type=float);args=parser.parse_args();main(args.output_root,deadline_monotonic=args.deadline_monotonic)
