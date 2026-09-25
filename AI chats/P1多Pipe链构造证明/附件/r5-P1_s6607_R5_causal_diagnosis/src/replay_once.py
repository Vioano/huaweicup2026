"""One authorized fixed-plan replay. No compilation or official evaluation.

All input PortOp.original_id values remain -1 (original IDs are unavailable).
Trace operations are labelled afterwards by (core, Task, Pipe, 1-based rank).
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, time

def main():
 p=argparse.ArgumentParser();p.add_argument('variant', choices=['whole_seed','period7_seed']);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 inp=a.root/'input'; pairs_path=inp/'results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json'
 pairs=json.loads(pairs_path.read_bytes()); opath=inp/'src/q1/response_oracle.py'; raw=opath.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==pairs['oracle_sha256']
 spec=importlib.util.spec_from_file_location('r5_uploaded_oracle',opath);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 v=pairs['variants'][a.variant];tasks={}
 for item in v['tasks']:
  ports=tuple(tuple(mod.PortOp(work=int(o[0]),ddr=o[1],need=tuple(o[2]),original_id=-1) for o in port) for port in item['ports'])
  tasks[item['task_id']]=mod.Task(ports,item['task_id'])
 lines=[[tasks[t] for t in order] for order in v['core_schedules']]
 t=time.perf_counter()
 result=mod.simulate(lines,pairs['gate'],keep_trace=True)
 elapsed=time.perf_counter()-t
 # Do not simulate again on a mismatch.
 if result['makespan'] != v['expected_model_makespan']:
  raise RuntimeError(f"STOP: {a.variant} expected {v['expected_model_makespan']}, observed {result['makespan']}")
 counts={}
 for event in result['trace']:
  assert event.pop('op_id')==-1
  key=(event['core'],event['task'],event['pipe']);counts[key]=counts.get(key,0)+1;event['rank']=counts[key]
 assert all(counts.get((i,t,pipe),0)==len(tasks[t].ports[j]) for i,line in enumerate(v['core_schedules']) for t in line for j,pipe in enumerate(mod.PIPES))
 result.update(variant=a.variant,oracle_sha256=hashlib.sha256(raw).hexdigest(),signatures_sha256=hashlib.sha256(pairs_path.read_bytes()).hexdigest(),expected_makespan=v['expected_model_makespan'],matched=True,simulate_wall_seconds=elapsed,operation_identity='(core, task, pipe, rank); original op IDs unavailable',calls={'fixed_plan_Fraction_keep_trace':1,'Task_compile':0,'E0':0,'E1':0,'E2':0,'retry':0})
 with a.out.open('x') as f:json.dump(result,f,separators=(',',':'));f.write('\n')
 print(json.dumps({k:result[k] for k in ['variant','makespan','service_cycles','ddr_retirement_union','events','per_core_finish','simulate_wall_seconds','calls']}))
if __name__=='__main__':main()
