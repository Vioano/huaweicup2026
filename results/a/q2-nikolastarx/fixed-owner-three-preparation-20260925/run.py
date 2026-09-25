"""Gated three-cell mechanism probe, never a full solver benchmark."""
import argparse, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, time
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).absolute().parents[2]; HERE=Path(__file__).absolute().parent
SOURCE='b03a3e1b1b51e97a772966b49a7b63668f3af9e4'; SCOPE='p2-fixed-owner-reverse-three'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_bytes())
def save(p,o):
 t=Path(str(p)+'.tmp'); t.write_text(json.dumps(o,indent=2,allow_nan=False)+'\n'); t.replace(p)
def host():
 raw=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level','vm.swapusage'],text=True,timeout=2).splitlines()
 if len(raw)!=2 or not re.fullmatch(r'[0-9]+',raw[0].strip()): raise ValueError('bad pressure reading')
 m=re.fullmatch(r'total = [0-9.]+[KMGT]\s+used = ([0-9.]+)([KMGT])\s+free = [0-9.]+[KMGT](?:\s+\(encrypted\))?',raw[1].strip())
 if not m: raise ValueError('bad swap reading')
 return int(raw[0]),int(Decimal(m[1])*1024**('KMGT'.index(m[2])+1))
def gate_check(g,mh,rh,hh,out):
 d=load(g)
 if d.get('status')!='admitted' or d.get('scope')!=SCOPE or d.get('manifest_sha256')!=mh or d.get('runner_sha256')!=rh or d.get('helper_sha256')!=hh or d.get('output_dir')!=str(out): raise ValueError('gate mismatch')
 try: expiry=datetime.fromisoformat(d['expires_at_utc'].replace('Z','+00:00'))
 except (KeyError,ValueError,TypeError) as e: raise ValueError('bad expiry') from e
 if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry: raise ValueError('expired gate')
def owners(plan):
 rows=plan['core_schedules']; own={}
 for core,row in enumerate(rows):
  for sg in row:
   if sg in own: raise ValueError('duplicate subgraph owner')
   own[sg]=core
 return {op:own[sg] for op,sg in plan['node_to_subgraph'].items()}
def verify(a,d):
 if d['source_commit']!=subprocess.check_output(['git','rev-parse',SOURCE+'^{commit}'],cwd=ROOT,text=True).strip(): raise ValueError('source commit mismatch')
 for p,h in d['source_files'].items():
  if sha(ROOT/p)!=h or hashlib.sha256(subprocess.check_output(['git','show',f'{SOURCE}:{p}'],cwd=ROOT)).hexdigest()!=h: raise ValueError('source mismatch '+p)
 for p,h in d['official_files'].items():
  if sha(a.raw/p)!=h: raise ValueError('official mismatch '+p)
 if str(a.python.absolute())!=d['python_invocation'] or sha(a.python.resolve(strict=True))!=d['python_sha256']: raise ValueError('Python invocation/binary mismatch')
 if sha(HERE/'construct.py')!=d['helper_sha256']: raise ValueError('helper mismatch')
 for row in d['cells']:
  if Path(row['graph']['path'])!=a.raw/f"data/case_{row['case']}.json": raise ValueError('graph path mismatch')
  for k in ('graph','incumbent','incumbent_result'):
   if sha(Path(row[k]['path']))!=row[k]['sha256']: raise ValueError('input mismatch '+k)
 if [r['case'] for r in d['cells']]!=['006','052','089'] or any(r['cores']!=5 for r in d['cells']): raise ValueError('coordinates mismatch')
 if d['limits']!={'construct':3,'external_E0':3,'E2':0,'fallback':0,'retry':0,'workers':1,'child_seconds':30,'batch_seconds':180,'child_rss_bytes':536870912,'pressure':1,'swap_delta_bytes':268435456,'free_bytes':10737418240}: raise ValueError('limits mismatch')
def main():
 p=argparse.ArgumentParser(); p.add_argument('--raw',type=Path,required=True); p.add_argument('--python',type=Path,required=True); p.add_argument('--gate',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
 start=time.perf_counter(); deadline=start+180; a.raw=a.raw.absolute(); a.python=a.python.absolute(); a.output=a.output.absolute(); a.gate=a.gate.absolute()
 if a.output.exists(): raise ValueError('output must not exist')
 d=load(HERE/'manifest.json'); mh=sha(HERE/'manifest.json'); rh=sha(__file__); hh=sha(HERE/'construct.py')
 gate_check(a.gate,mh,rh,hh,a.output); verify(a,d)
 if shutil.disk_usage(a.output.parent).free<10<<30: raise RuntimeError('disk reserve')
 pressure,baseline=host()
 if pressure!=1: raise RuntimeError('pressure')
 if time.perf_counter()>=deadline: raise TimeoutError('preflight exceeded deadline')
 a.output.mkdir(exist_ok=False)
 spec=importlib.util.spec_from_file_location('fixed_monitor',ROOT/'src/q2_nikolastarx/evaluate_feedback.py'); monitor=importlib.util.module_from_spec(spec); spec.loader.exec_module(monitor)
 original_snapshot=monitor.process_snapshot
 check_state={'armed':False,'last':0.0,'peak_delta':0}
 def guarded_snapshot():
  snapshot=original_snapshot()
  if os.getpid() not in snapshot: raise RuntimeError('observer identity missing from process snapshot')
  if check_state['armed'] and time.perf_counter()-check_state['last']>=0.5:
   check_state['last']=time.perf_counter()
   try:
    pressure,used=host()
    check_state['peak_delta']=max(check_state['peak_delta'],used-baseline)
    if pressure!=1 or used-baseline>256<<20 or shutil.disk_usage(a.output).free<10<<30:
     raise RuntimeError('host pressure/swap/disk guard')
   except BaseException:
    check_state['armed']=False  # permit fixed monitor's cleanup snapshots
    raise
  return snapshot
 monitor.process_snapshot=guarded_snapshot
 ledger={'status':'running','started_at':datetime.now(timezone.utc).isoformat(),'gate_sha256':sha(a.gate),'manifest_sha256':mh,'runner_sha256':rh,'helper_sha256':hh,'construct_started':0,'external_E0_started':0,'E2':0,'fallback':0,'retry':0,'rows':[],'swap_baseline':baseline,'max_swap_delta':0}
 try:
  for row in d['cells']:
   gate_check(a.gate,mh,rh,hh,a.output)
   pressure,used=host(); ledger['max_swap_delta']=max(ledger['max_swap_delta'],used-baseline)
   if pressure!=1 or used-baseline>256<<20 or shutil.disk_usage(a.output).free<10<<30 or time.perf_counter()>=deadline: raise RuntimeError('host/deadline guard')
   c=row['case']; folder=a.output/(c+'-k5'); folder.mkdir(); rr={'case':c,'incumbent_plan_sha256':row['incumbent']['sha256'],'incumbent_result_sha256':row['incumbent_result']['sha256']}; ledger['rows'].append(rr)
   graph=a.raw/('data/case_'+c+'.json'); config=a.raw/'data/config.txt'; code=a.raw/'code'
   ledger['construct_started']+=1; save(a.output/'ledger.json',ledger)
   argv=[str(a.python),'-B',str(HERE/'construct.py'),'--graph',str(graph),'--config',str(config),'--incumbent',row['incumbent']['path'],'--output',str(folder/'plan.json'),'--detail',str(folder/'detail.json'),'--official_code',str(code)]
   check_state['armed']=True; check_state['last']=0.0
   pr=monitor.monitored(argv,folder/'construct-process',min(deadline,time.perf_counter()+30),536870912)
   check_state['armed']=False; ledger['max_swap_delta']=max(ledger['max_swap_delta'],check_state['peak_delta'])
   rr['construct_process']=pr; save(a.output/'ledger.json',ledger)
   pressure,used=host(); ledger['max_swap_delta']=max(ledger['max_swap_delta'],used-baseline)
   if pressure!=1 or used-baseline>256<<20: raise RuntimeError('host changed after construct')
   if pr['status']!='ok' or pr['surviving_pids']: raise RuntimeError('construct failed')
   old=load(row['incumbent']['path']); new=load(folder/'plan.json')
   if owners(old)!=owners(new) or old['node_to_subgraph']!=new['node_to_subgraph']: raise RuntimeError('owner/partition changed')
   rr['plan_sha256']=sha(folder/'plan.json'); rr['detail_sha256']=sha(folder/'detail.json')
   if old==new: rr['status']='identical_skip'; save(a.output/'ledger.json',ledger); continue
   ledger['external_E0_started']+=1; save(a.output/'ledger.json',ledger)
   argv=[str(a.python),'-B',str(code/'multicore_cut_evaluate_problem_2.py'),str(graph),str(folder/'plan.json'),'--config',str(config),'--output',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'official.log')]
   check_state['armed']=True; check_state['last']=0.0
   pr=monitor.monitored(argv,folder/'e0-process',min(deadline,time.perf_counter()+30),536870912)
   check_state['armed']=False; ledger['max_swap_delta']=max(ledger['max_swap_delta'],check_state['peak_delta'])
   rr['e0_process']=pr; save(a.output/'ledger.json',ledger)
   pressure,used=host(); ledger['max_swap_delta']=max(ledger['max_swap_delta'],used-baseline)
   if pressure!=1 or used-baseline>256<<20: raise RuntimeError('host changed after E0')
   if pr['status']!='ok' or pr['surviving_pids']: raise RuntimeError('E0 failed')
   oldr=load(row['incumbent_result']['path']); newr=load(folder/'result.json')
   if newr['scene']!='B' or newr['num_cores']!=5: raise ValueError('wrong result')
   oldd=oldr['data_movement_bytes']; newd=newr['data_movement_bytes']; spillold=oldd['spill_added_copy_bytes']; spillnew=newd['spill_added_copy_bytes']
   rr.update(status='ok',result_sha256=sha(folder/'result.json'),old_makespan=oldr['makespan'],new_makespan=newr['makespan'],old_ddr=oldd,new_ddr=newd,old_spill=spillold,new_spill=spillnew,byte_invariant_if_zero_spill=(oldd==newd) if spillold==spillnew==0 else None)
   save(a.output/'ledger.json',ledger)
  ledger['status']='completed'
 except BaseException as e:
  ledger.update(status='stopped',error=repr(e)); raise
 finally:
  ledger['wall_seconds']=time.perf_counter()-start; ledger['finished_at']=datetime.now(timezone.utc).isoformat(); save(a.output/'ledger.json',ledger)
if __name__=='__main__': main()
