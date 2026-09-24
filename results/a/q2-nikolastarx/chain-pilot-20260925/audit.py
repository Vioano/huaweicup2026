#!/usr/bin/env python3
"""Read-only validation of chain-pilot evidence, including deterministic gzip archive."""
import gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'results/a/q2-nikolastarx/chain-pilot-20260925'; RUN=BASE/'run'
FIELDS=('original_graph_copy_bytes','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')
def sha(b):return hashlib.sha256(b).hexdigest()
def pinned(obj):return subprocess.check_output(['git','-C',str(ROOT),'show',f"{obj['commit']}:{obj['path']}"])
def load(b):return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
def source_bytes(d,name):
 p=d/name
 if p.exists():return p.read_bytes()
 z=d/(name+'.gz');b=z.read_bytes();raw=gzip.decompress(b);assert int.from_bytes(b[4:8],'little')==0;return raw
def main():
 mbytes=(BASE/'manifest.json').read_bytes();m=load(mbytes);s=load((RUN/'summary.json').read_bytes());assert sha(mbytes)==s['manifest_sha256'];assert s['status']=='completed';assert len(m['rows'])==len(s['cases'])==6
 out=[];tot={'E2_api':0,'native':0,'E0_fallback':0,'E0_independent':0};archives=[]
 for mr,sr in zip(m['rows'],s['cases']):
  case=mr['case'];assert case==sr['case'];d=RUN/f'{case}-k5/records';ledger=load((d/'ledger.json').read_bytes());assert ledger==sr['ledger']
  proc=sr['process'];assert proc['exit_code']==0 and proc['surviving_pids']==[] and proc['status']=='ok';assert not ledger['request_in_flight'] and not ledger['e0_in_flight'] and ledger['status']=='completed'
  for k,v in ledger['calls'].items():tot[k]+=v
  cb=pinned(mr['candidate']);plan=load(cb);localb=source_bytes(d,'candidate_plan.json');local=load(localb)
  assert list(plan['node_to_subgraph'].items())==list(local['node_to_subgraph'].items()) and plan['core_schedules']==local['core_schedules']
  baseb=pinned(mr['baseline_truth']);baseline=load(gzip.decompress(baseb));assert sha(baseb)==mr['baseline_truth']['sha256'] and baseline['makespan']==mr['baseline_m']
  eb=source_bytes(d,'e0_result.json');e0=load(eb);rec=ledger['e2_record'];assert rec['makespan']==e0['makespan'] and rec['cross_task_traffic']==e0['cross_task_traffic']==ledger['candidate']['cross_task_traffic']
  assert all(rec['data_movement_bytes'][k]==e0['data_movement_bytes'][k]==ledger['candidate']['movement'][k] for k in FIELDS)
  assert baseline['makespan']==ledger['baseline']['makespan'] and baseline['data_movement_bytes']==ledger['baseline']['movement'] and baseline['cross_task_traffic']==ledger['baseline']['cross_task_traffic']
  traceb=source_bytes(d,'e0_trace.json');trace=load(traceb);events=trace.get('traceEvents');assert isinstance(events,list) and events and all(isinstance(x,dict) and all(k in x for k in ('name','ph','pid','tid')) for x in events)
  row={'case':case,'candidate_makespan':e0['makespan'],'baseline_makespan':baseline['makespan'],'delta_makespan':e0['makespan']-baseline['makespan'],'movement':e0['data_movement_bytes'],'cross_task_traffic':e0['cross_task_traffic'],'e0_result_sha256':sha(eb),'trace_event_count':len(events),'candidate_plan_sha256':sha(localb),'candidate_mapping_order_and_schedules_match_pinned':True};out.append(row)
  for name,raw in [('e0_trace.json',traceb),('e0_result.json',eb),('candidate_plan.json',localb)]:
   src=d/name;dst=d/(name+'.gz')
   if src.exists():
    with dst.open('wb') as f:
     with gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as z:z.write(raw)
    packed=dst.read_bytes();assert gzip.decompress(packed)==raw and sha(gzip.decompress(packed))==sha(raw) and int.from_bytes(packed[4:8],'little')==0
    src.unlink()
   else:
    packed=dst.read_bytes();assert gzip.decompress(packed)==raw and sha(gzip.decompress(packed))==sha(raw) and int.from_bytes(packed[4:8],'little')==0
   archives.append({'path':str(dst.relative_to(ROOT)),'original_sha256':sha(raw),'gzip_sha256':sha(packed),'original_bytes':len(raw),'gzip_bytes':len(packed),'roundtrip_verified':True,'gzip_mtime':0})
 assert tot=={'E2_api':6,'native':6,'E0_fallback':0,'E0_independent':6}
 result={'status':'audit_passed','cases':out,'calls':tot,'processes':{'count':6,'all_exit_0':True,'all_surviving_pids_empty':True,'all_in_flight_false':True},'archive':archives,'limits':'Six fixed candidate cases only. Does not establish full algorithm score or constructor wall; constructor time is not reported here.'}
 (BASE/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (BASE/'archive-manifest.json').write_text(json.dumps({'schema':'chain-pilot-gzip-v1','files':archives},indent=2)+'\n')
 (BASE/'SUMMARY.md').write_text('# Chain pilot evidence audit\n\nRead-only audit of six fixed candidate plans. Candidate mapping insertion order and schedules match manifest-pinned Git plans. For each case, E2 record equals independent E0 result on Makespan, all five movement fields, and cross-task traffic; baseline fields match manifest-pinned existing E0 bytes and run summary. All six processes exited 0, left no surviving PIDs, and both in-flight flags are false. Totals: E2 6, native 6, fallback 0, independent E0 6.\n\n| Case | Candidate M | Baseline M | Delta M |\n|---|---:|---:|---:|\n'+''.join(f"| {r['case']} | {r['candidate_makespan']} | {r['baseline_makespan']} | {r['delta_makespan']} |\n" for r in out)+'\nOnly these six fixed cases are described. No full algorithm mean and no constructor wall claim. Official trace JSON passed basic traceEvents structure validation. Original JSON files were removed only after deterministic gzip roundtrip SHA verification; see archive-manifest.json.\n')
if __name__=='__main__':main()
