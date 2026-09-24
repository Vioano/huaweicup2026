"""DERIVED portable reproduction copy; not the exact executed runner and not execution evidence.
The original runner SHA and run receipt are recorded in manifest.json and receipt.json.
"""
from __future__ import annotations
import hashlib,json,os,platform,signal,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PYTHON=Path(sys.executable)
SOLVER_COMMIT='6e22fd4356842c7473fcf7ee6aa071bf77c8a452'
OFFICIAL_COMMIT='8685b5a867a4f66c7cacaf166d50896bd7c09a41'
SOURCES=['src/q1/shared_input_full_core.py','src/q1/shared_input_budget.py','src/q1/component_pack.py','data/raw/a/official/code/stub_multicore_cut_and_schedule.py','data/raw/a/official/code/evaluation_validation.py','data/raw/a/official/code/contest_io.py','data/raw/a/official/code/multicore_cut_evaluate_problem_1.py']
def sha(b):return hashlib.sha256(b).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def run(argv,env,name,limit,started):
 row={'argv':argv,'cwd':'.','timeout_seconds':limit,'started_at':utc()}; t=time.perf_counter()
 with (OUT/f'{name}.stdout.txt').open('xb') as so,(OUT/f'{name}.stderr.txt').open('xb') as se:
  child=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=so,stderr=se,start_new_session=True)
  try:child.wait(timeout=limit); clean=True
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGKILL)
   try:child.wait(timeout=10);clean=True
   except subprocess.TimeoutExpired:clean=False
  row.update(exit_code=child.returncode,cleanup_confirmed=clean,status='timeout' if child.returncode is None else ('ok' if child.returncode==0 else 'failed'))
 row.update(wall_seconds=time.perf_counter()-t,finished_at=utc())
 for ext in ('stdout','stderr'):row[ext+'_sha256']=sha((OUT/f'{name}.{ext}.txt').read_bytes())
 row['status']='timeout' if row['wall_seconds']>=limit or not row['cleanup_confirmed'] else ('ok' if row['exit_code']==0 else 'failed')
 return row
def main():
 global OUT
 OUT=Path(__file__).resolve().parent/'replay-output'; OUT.mkdir(exist_ok=True); started=time.perf_counter(); runtime=str(PYTHON); assert PYTHON.is_file()
 pyver=subprocess.check_output([runtime,'-B','-c','import sys;print(sys.version)'],text=True).strip(); assert pyver.startswith('3.12.13')
 src_hashes={}
 for s in SOURCES:
  b=(ROOT/s).read_bytes(); exp=subprocess.check_output(['git','show',f'{SOLVER_COMMIT}:{s}'],cwd=ROOT); assert b==exp,s; src_hashes[s]=sha(b)
 manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_text()); mf={x['path']:x for x in manifest['files']}; official_files={p:mf[p]['sha256'] for p in mf if p.startswith('code/') or p=='data/config.txt'}
 for p,h in official_files.items():assert sha((ROOT/'data/raw/a/official'/p).read_bytes())==h,p
 zpath=ROOT/manifest['case_archive']['path']; assert sha(zpath.read_bytes())==manifest['case_archive']['sha256']
 with zipfile.ZipFile(zpath) as z: graph=z.read('data/case_044.json')
 graph_sha=sha(graph); (OUT/'case_044.json').write_bytes(graph)
 env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'data/raw/a/official/code')+os.pathsep+env.get('PYTHONPATH','')
 for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):env[n]='1'
 receipt={'solver_commit':SOLVER_COMMIT,'source_hashes':src_hashes,'official_commit':OFFICIAL_COMMIT,'official_code_hash':manifest['official_code_hash'],'official_files':official_files,'archive_sha256':sha(zpath.read_bytes()),'input_member':'data/case_044.json','input_sha256':graph_sha,'input_bytes':len(graph),'runtime_requested':runtime,'runtime_actual':str(PYTHON.resolve()),'python_version':pyver,'platform':platform.platform(),'workers':1,'limits':{'solver_seconds':30,'E0_seconds':60,'whole_window_seconds':120,'retries':0,'E1':0,'E2':0},'calls':{'constructor':0,'E0':0,'E1':0,'E2':0,'retry':0},'v4_comparison_makespan_cycles':64624,'started_at':utc(),'stages':[]}
 solver=[runtime,'-B','-m','src.q1.shared_input_full_core',str((OUT/'case_044.json').resolve()),'--cores','3','--output',str((OUT/'plan.json').resolve()),'--diagnostics',str((OUT/'diagnostics.json').resolve())]
 rec=run(solver,env,'solver',30,started); receipt['stages'].append(rec); receipt['calls']['constructor']=1
 if rec['status']!='ok' or not (OUT/'plan.json').exists() or not (OUT/'diagnostics.json').exists():
  receipt.update(status='solver_failed_stop',finished_at=utc(),whole_window_wall_seconds=time.perf_counter()-started);(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return
 plan=json.loads((OUT/'plan.json').read_bytes()); assert set(plan)=={'node_to_subgraph','core_schedules'}
 receipt['plan_sha256']=sha((OUT/'plan.json').read_bytes());receipt['diagnostics_sha256']=sha((OUT/'diagnostics.json').read_bytes());receipt['plan_keys']=list(plan)
 e0=[runtime,'-B',str(ROOT/'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py'),str((OUT/'case_044.json').resolve()),str((OUT/'plan.json').resolve()),'--config',str(ROOT/'data/raw/a/official/data/config.txt'),'--output',str((OUT/'e0-result.json').resolve()),'--trace-output',str((OUT/'e0-trace.json').resolve()),'--log-output',str((OUT/'e0.log').resolve())]
 remaining=120-(time.perf_counter()-started); limit=min(60,max(.1,remaining)); rec=run(e0,env,'e0',limit,started);receipt['stages'].append(rec);receipt['calls']['E0']=1
 if rec['status']=='ok' and (OUT/'e0-result.json').exists():
  result=json.loads((OUT/'e0-result.json').read_bytes()); d=result.get('data_movement_bytes',{});receipt['metrics']={'makespan_cycles':result.get('makespan'),'scheduled_ddr_bytes':d.get('scheduled_copy_bytes'),'extra_ddr_bytes':d.get('added_copy_bytes'),'spill_bytes':d.get('spill_added_copy_bytes')};receipt['result_sha256']=sha((OUT/'e0-result.json').read_bytes());receipt['trace_sha256']=sha((OUT/'e0-trace.json').read_bytes()) if (OUT/'e0-trace.json').exists() else None
  receipt['plan_match']=result.get('input_plan')==plan if 'input_plan' in result else None
 receipt.update(status='ok' if rec['status']=='ok' else 'e0_failed_stop',finished_at=utc(),whole_window_wall_seconds=time.perf_counter()-started);(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
