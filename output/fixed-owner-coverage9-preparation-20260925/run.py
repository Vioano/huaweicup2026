"""One-worker, three-cell fixed-owner qualification adapter. No score in preflight."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, platform, re, shutil, subprocess, sys, time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
DEV=Path(__file__).absolute().parents[2]; ROOT=DEV; HERE=Path(__file__).absolute().parent
SOURCE='fcc7fa2410edb5e2cd3868b1b7f2d7bce82b58a9'; SCOPE='p2-fixed-owner-coverage-nine'
COORDS=(('019',5),('052',5),('061',5),('070',5),('074',5),('099',5),('076',5),('003',5),('084',5))
LIMITS={'cells':9,'workers':1,'E2_api':36,'E0_independent':9,'solver_seconds':180,'e0_seconds':180,'batch_seconds':900,'rss_bytes_per_cell':2<<30,'rss_bytes_total':2<<30,'retries':0,'E0_fallback_reserve':1}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');t.replace(p)
def gate_check(path,doc,output):
 g=read(path)
 if g.get('status')!='admitted' or g.get('scope')!=SCOPE or g.get('manifest_sha256')!=sha(HERE/'manifest.json') or g.get('runner_sha256')!=sha(__file__) or g.get('output_dir')!=str(output):raise ValueError('gate status/scope/pin/output mismatch')
 for k in ('holdout_runner_sha256','monitor_sha256','e2_manifest_sha256'):
  if g.get(k)!=doc[k]:raise ValueError('gate dependency mismatch: '+k)
 try:t=datetime.fromisoformat(g['expires_at_utc'].replace('Z','+00:00'))
 except (KeyError,TypeError,ValueError) as e:raise ValueError('gate expiry invalid') from e
 if t.tzinfo is None or datetime.now(timezone.utc)>=t:raise ValueError('gate expired')
def host():
 r=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level','vm.swapusage'],text=True,timeout=2).splitlines()
 if len(r)!=2 or not re.fullmatch(r'[0-9]+',r[0].strip()):raise ValueError('bad VM pressure reading')
 m=re.fullmatch(r'total = [0-9.]+[KMGT]\s+used = ([0-9.]+)([KMGT])\s+free = [0-9.]+[KMGT](?:\s+\(encrypted\))?',r[1].strip())
 if not m:raise ValueError('bad swap reading')
 return int(r[0]),int(Decimal(m[1])*1024**('KMGT'.index(m[2])+1))
def fixed_zero(detail,base):
 e="UnsupportedStructure('requires both fork and join')"
 return (detail.get('skip_reason')=='fixed_owner_construction_unavailable' and detail.get('fixed_owner_error')==e and detail.get('fixed_owner_detail') is None
  and detail.get('selected')=='incumbent' and detail.get('reason')=='incumbent_retained' and detail.get('score_evidence')=='not_requested'
  and detail.get('scores')=={} and detail.get('oracle_requests')==0 and detail.get('oracle_request_limit')==4
  and detail.get('unique_scored_plans')==0 and detail.get('constructed_plans')==1
  and base.get('selected')=='baseline' and base.get('reason')=='gap_structure_unsupported' and base.get('score_evidence')=='not_requested'
  and base.get('unique_plans')==1 and base.get('construction_errors')==[{'stage':'gap_candidate','kind':'unsupported_structure','error':e}])
def fixed_duplicate(detail,base):
 """Exact unscored equality branch in frozen fixed-owner wrapper."""
 candidate=detail.get('fixed_owner_detail')
 return (detail.get('skip_reason')=='fixed_owner_duplicates_incumbent'
  and detail.get('selected')=='incumbent' and detail.get('selected_strategy')==base.get('selected_strategy')
  and detail.get('reason')=='incumbent_retained' and detail.get('score_evidence')=='not_requested'
  and detail.get('scores')=={} and detail.get('oracle_requests')==0 and detail.get('oracle_request_limit')==4
  and detail.get('unique_scored_plans')==0 and detail.get('cache_hits')==0
  and 'fixed_owner_error' not in detail
  and isinstance(candidate,dict) and candidate.get('selected')=='fixed_owner_reverse'
  and candidate.get('online_E0_calls')==0
  and set(candidate)=={'selected','segment_count','owner_split_count','modeled_reverse_compute_finish',
                      'modeled_reverse_op_starts','modeled_split_cross_core_lags','online_E0_calls','scope'}
  and base.get('score_evidence')=='not_requested' and base.get('unique_plans')==1
  and base.get('oracle_requests')==0 and base.get('scores')=={}
  and type(base.get('constructed_plans')) is int and base['constructed_plans']>=1
  and detail.get('constructed_plans')==base['constructed_plans']+1
  and not any(isinstance(x,dict) and x.get('kind')=='unexpected'
              for x in base.get('construction_errors',[])))

def preflight(a,m,hold):
 if platform.system()!='Darwin' or platform.machine()!='arm64':raise ValueError('Mac arm64 required')
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip()!=SOURCE:raise ValueError('source HEAD mismatch')
 if a.repo!=ROOT or m.get('source_commit')!=SOURCE or m.get('coordinates')!=[list(x) for x in COORDS] or m.get('limits')!=LIMITS or m.get('zero_E2_allowed_routes')!=['known_no_fork_or_join','fixed_owner_duplicates_incumbent_exact']:raise ValueError('manifest scope mismatch')
 if str(a.python)!=m['python_invocation'] or sha(a.python.resolve(strict=True))!=m['python_sha256']:raise ValueError('venv invocation/binary mismatch')
 if sha(ROOT/'scripts/q2_bidirectional_holdout.py')!=m['holdout_runner_sha256']:raise ValueError('holdout dependency drift')
 if sha(ROOT/'src/q2_nikolastarx/evaluate_feedback.py')!=m['monitor_sha256']:raise ValueError('monitor drift')
 if sha(ROOT/'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json')!=m['e2_manifest_sha256']:raise ValueError('E2 manifest drift')
 names=subprocess.check_output(['git','ls-tree','-r','--name-only',SOURCE,'src/q2_nikolastarx','data/raw/a/official/code'],cwd=ROOT,text=True).splitlines()
 if set(names)!=set(m['source_files']):raise ValueError('source file set drift')
 for n,h in m['source_files'].items():
  if sha(ROOT/n)!=h or hashlib.sha256(subprocess.check_output(['git','show',SOURCE+':'+n],cwd=ROOT)).hexdigest()!=h:raise ValueError('source bytes drift '+n)
 sol={n:h for n,h in m['source_files'].items() if n.startswith('src/q2_nikolastarx/') and n.endswith('.py')}
 actual={p.relative_to(ROOT).as_posix() for p in (ROOT/'src/q2_nikolastarx').rglob('*.py')}
 if actual!=set(sol):raise ValueError('solver Python set drift')
 for n,h in m['official_files'].items():
  if sha(a.raw_root/n)!=h:raise ValueError('official bytes drift '+n)
  if n.startswith('code/') and sha(ROOT/'data/raw/a/official'/n)!=h:raise ValueError('tracked official drift '+n)
 if set(m['e2_files'])!={p.relative_to(a.e2_root).as_posix() for p in a.e2_root.rglob('*') if p.is_file()}:raise ValueError('E2 file set drift')
 for n,h in m['e2_files'].items():
  if sha(a.e2_root/n)!=h:raise ValueError('E2 file drift '+n)
 if m['official_source_manifest_sha256']!=sha(ROOT/'docs/a/source-manifest.json'):raise ValueError('official manifest drift')
 if sha(m['selection']['path'])!=m['selection']['sha256']:raise ValueError('selection original drift')
 selection=read(m['selection']['path']); selected=[tuple(x) for x in selection['coordinates'] if x[0] not in ('006','089','097')]
 if tuple(selected)!=COORDS:raise ValueError('coverage selection/order drift')
 if m['singlecore_baseline']['sha256']!=sha(HERE/m['singlecore_baseline']['path']):raise ValueError('baseline drift')
 baseline=read(HERE/m['singlecore_baseline']['path']); den={r['case']:r['makespan'] for r in baseline['records']}
 if len(den)!=100:raise ValueError('baseline incomplete')
 # Real child with the exact invocation path. Imports only; no graph, constructor or evaluator call.
 code='import pathlib,sys; r=pathlib.Path(sys.argv[1]); e=pathlib.Path(sys.argv[2]); assert pathlib.Path(sys.executable)==pathlib.Path(sys.argv[3]); assert sys.prefix!=sys.base_prefix; sys.path[:0]=[str(r),str(r/"data/raw/a/official/code"),str(e)]; from src.q2_nikolastarx import adaptive_fixed_owner_guarded; import research.a.e2_search; import src.eval_exact._official; print("import-only-ok")'
 p=subprocess.run([str(a.python),'-B','-c',code,str(a.repo),str(a.e2_root),str(a.python)],cwd=a.repo,capture_output=True,text=True,timeout=15)
 if p.returncode or p.stdout.strip()!='import-only-ok':raise ValueError('import-only preflight failed '+p.stderr[-1000:])
 sys.path[:0]=[str(a.repo),str(a.repo/'data/raw/a/official/code')]
 from src.q2_nikolastarx.adaptive_guarded import check_e2_source
 from src.q2_nikolastarx import evaluate_feedback
 e2=check_e2_source(a.e2_root)
 if e2['native_binary_sha256']!=m['native_binary_sha256']:raise ValueError('native binary drift')
 hold.ROOT=a.repo;hold.PYTHON=a.python;hold.E2_ROOT=a.e2_root;hold.RAW_ROOT=a.raw_root;hold.MODULE='src.q2_nikolastarx.adaptive_fixed_owner_guarded';hold.SOLVER=SOURCE;hold.LIMITS=LIMITS;hold.known_structural_unavailable=lambda detail,base: fixed_zero(detail,base) or fixed_duplicate(detail,base)
 return sol,den,e2,evaluate_feedback

def run(a,m,hold,sol,den,e2,monitor,start):
 if a.output.exists():raise ValueError('fresh output required')
 deadline=start+900
 gate_check(a.gate,m,a.output)
 if shutil.disk_usage(a.output.parent).free<10<<30:raise ValueError('disk reserve')
 pressure,baseline=host()
 if pressure!=1:raise ValueError('VM pressure')
 gate_check(a.gate,m,a.output)
 if time.perf_counter()>=deadline:raise TimeoutError('preflight deadline')
 a.output.mkdir(exist_ok=False)
 old_snapshot=monitor.process_snapshot; watch={'armed':False,'last':0,'max_delta':0}
 def observed_snapshot():
  s=old_snapshot()
  if os.getpid() not in s:raise RuntimeError('observer identity missing')
  if watch['armed'] and time.perf_counter()-watch['last']>=0.5:
   watch['last']=time.perf_counter()
   try:
    pressure,used=host();watch['max_delta']=max(watch['max_delta'],used-baseline)
    if pressure!=1 or used-baseline>256<<20 or shutil.disk_usage(a.output).free<10<<30:raise RuntimeError('host resource guard')
   except BaseException:
    watch['armed']=False  # allow fixed monitor cleanup snapshots
    raise
  return s
 monitor.process_snapshot=observed_snapshot
 def watched(*args,**kw):
  watch['armed']=True;watch['last']=0
  try:return monitor.monitored(*args,**kw)
  finally:watch['armed']=False
 doc={'solver_sources':sol,'singlecore_baseline_m':den}
 summary={'schema':'fixed-owner-coverage-nine-v1','status':'running','source_commit':SOURCE,'scope':SCOPE,'started_at':datetime.now(timezone.utc).isoformat(),'gate_sha256':sha(a.gate),'manifest_sha256':sha(HERE/'manifest.json'),'runner_sha256':sha(__file__),'limits':LIMITS,'calls':{'solver_started':0,'E2_api_attempted':0,'native_returns':0,'E0_fallback_possible':0,'E0_independent_started':0},'call_count_complete':True,'E2_api_unresolved_upper_bound':0,'rows':[],'in_flight':[],'unresolved_requests':[],'accepted_cells':0,'swap_baseline':baseline,'max_swap_delta':0}
 save(a.output/'summary.json',summary)
 try:
  for case,cores in COORDS:
   gate_check(a.gate,m,a.output)
   pressure,used=host();summary['max_swap_delta']=max(summary['max_swap_delta'],used-baseline,watch['max_delta'])
   if pressure!=1 or used-baseline>256<<20 or shutil.disk_usage(a.output).free<10<<30 or time.perf_counter()>=deadline:raise RuntimeError('pre-dispatch guard')
   if summary['calls']['E2_api_attempted']+4>36:raise ValueError('E2 dispatch budget')
   key=f'{case}-k{cores}';summary['calls']['solver_started']+=1;summary['in_flight']=[key];save(a.output/'summary.json',summary)
   try:row=hold.cell(case,cores,doc,{'native_binary_sha256':e2['native_binary_sha256']},e2,watched,a.output,deadline)
   except BaseException as err:row={'case':case,'cores':cores,'status':'stopped','error':'cell raised '+repr(err),'calls':{},'call_count_complete':False}
   if (a.output/key/'cell.json').exists():save(a.output/key/'cell.json',row)
   uncertain=(row.get('request_in_flight') is True or row.get('solver_process_in_flight') is True or row.get('independent_e0_in_flight') is True or row.get('call_count_complete') is False)
   summary['in_flight']=[key] if uncertain else []
   if uncertain:summary['unresolved_requests'].append(key)
   summary['rows'].append(row)
   for name in ('E2_api_attempted','native_returns','E0_fallback_possible','E0_independent_started'):
    x=row.get('calls',{}).get(name)
    if type(x) is int:summary['calls'][name]+=x
    else:
     summary['call_count_complete']=False
     if name=='E2_api_attempted':summary['E2_api_unresolved_upper_bound']+=4
     if name=='E0_fallback_possible':summary['calls'][name]+=1
   summary['max_swap_delta']=max(summary['max_swap_delta'],watch['max_delta'])
   if row.get('status')!='accepted' or row.get('call_count_complete') is False:summary['status']='stopped_first_failure'
   else:summary['accepted_cells']+=1
   if summary['calls']['E2_api_attempted']>36 or summary['calls']['E0_fallback_possible']>1 or summary['calls']['E0_fallback_possible']+summary['calls']['E0_independent_started']>10:summary['status']='stopped_budget'
   save(a.output/'summary.json',summary)
   if summary['status']!='running':break
  if summary['status']=='running':summary['status']='completed' if summary['accepted_cells']==9 else 'stopped_incomplete'
 except BaseException as e:summary.update(status='stopped_pre_dispatch',error=repr(e));raise
 finally:
  summary['finished_at']=datetime.now(timezone.utc).isoformat();summary['wall_seconds']=time.perf_counter()-start;summary['max_swap_delta']=max(summary['max_swap_delta'],watch['max_delta']);save(a.output/'summary.json',summary)
 return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('preflight','run'))
 for n in ('repo','raw_root','e2_root','python','manifest','gate','output'):p.add_argument('--'+n.replace('_','-'),type=Path,required=n not in ('gate','output'))
 global ROOT
 a=p.parse_args();batch_start=time.perf_counter();a.repo=a.repo.resolve(strict=True);a.raw_root=a.raw_root.resolve(strict=True);a.e2_root=a.e2_root.resolve(strict=True);a.python=a.python.absolute();a.manifest=a.manifest.absolute()
 ROOT=a.repo
 if a.manifest!=HERE/'manifest.json':raise ValueError('wrong manifest path')
 m=read(a.manifest)
 spec=importlib.util.spec_from_file_location('holdout_fixed_dependency',ROOT/'scripts/q2_bidirectional_holdout.py');hold=importlib.util.module_from_spec(spec);spec.loader.exec_module(hold)
 sol,den,e2,monitor=preflight(a,m,hold)
 if a.mode=='preflight':print(json.dumps({'status':'preflight_ok','coordinates':COORDS,'calls':0}));return
 if not a.output or not a.gate:raise ValueError('run needs gate/output')
 a.output=a.output.absolute();a.gate=a.gate.absolute()
 if a.output!=Path(m['output_dir']):raise ValueError('wrong output directory')
 result=run(a,m,hold,sol,den,e2,monitor,batch_start)
 if result['status']!='completed':raise SystemExit(1)
if __name__=='__main__':main()
