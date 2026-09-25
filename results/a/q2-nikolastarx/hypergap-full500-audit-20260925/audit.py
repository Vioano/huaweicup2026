#!/usr/bin/env python3
"""Read-only full500 audit. Requires a completed runtime summary and archived cells."""
import argparse, gzip, hashlib, json, math, statistics, subprocess
from pathlib import Path
SOLVER='c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'; RUNNER='ff47cbca4a953602dec7e4b959bbb10a016eca9a'
BASE='60afc38b327680fbda0ff10182e3e05a01edd72d'; FEED='results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json'; FEED_SHA='0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c'
FIELDS=('original_graph_copy_bytes','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')
GRID=[(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)]
def sha(b): return hashlib.sha256(b).hexdigest()
def readj(p): return json.loads(p.read_bytes())
def unpack(p):
 b=p.read_bytes(); return gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b
def stat(x):
 x=sorted(x); return {'n':len(x),'mean':statistics.fmean(x),'p95_nearest_rank':x[math.ceil(.95*len(x))-1],'max':x[-1]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--summary',type=Path,required=True);ap.add_argument('--archive-root',type=Path,required=True);ap.add_argument('--repo-root',type=Path,default=Path.cwd());a=ap.parse_args()
 if not a.summary.is_file():
  print(json.dumps({'status':'incomplete','reason':'summary_missing','scores_computed':False}));return 2
 s=readj(a.summary); rows=s.get('rows',[]); accepted=[r for r in rows if r.get('status')=='accepted']
 if s.get('status')!='completed' or len(rows)!=500 or len(accepted)!=500 or s.get('accepted_cells')!=500 or s.get('call_count_complete') is not True or s.get('in_flight') or any(r.get('solver_process_in_flight') or r.get('independent_e0_in_flight') or r.get('request_in_flight') for r in rows):
  print(json.dumps({'status':'incomplete','run_status':s.get('status'),'rows':len(rows),'accepted':len(accepted),'scores_computed':False}));return 2
 if s.get('solver_commit')!=SOLVER or s.get('runner_commit')!=RUNNER or {(str(r['case']),int(r['cores'])) for r in rows}!=set(GRID): raise ValueError('run identity/grid mismatch')
 if s.get('limits',{}).get('workers')!=1:raise ValueError('worker parameter mismatch')
 repo=a.repo_root.resolve(); feedraw=subprocess.check_output(['git','-C',str(repo),'show',f'{BASE}:{FEED}'])
 if sha(feedraw)!=FEED_SHA: raise ValueError('pinned baseline feed SHA mismatch')
 old={}
 for r in json.loads(feedraw).get('records',[]):
  key=(str(r['case_id']),int(r['cores']))
  if key in old or r.get('status')!='ok':raise ValueError('duplicate/bad old-feed row')
  old[key]=r
 if set(old)!=set(GRID):raise ValueError('old feed grid mismatch')
 newvals={k:[] for k in range(1,6)}; oldvals={k:[] for k in range(1,6)}; wins={k:[0,0,0] for k in range(1,6)}; sw=[]; ew=[]; improved=set(); plan_changed=set(); calls={'solver':0,'E2':0,'native':0,'E0':0,'fallback':0,'unknown':0}
 root=a.archive_root.resolve()
 feed_records={}; params={'global_budget':{'E0_fallback_reserved':1500,'E0_independent':500,'E2_api':1500,'batch_seconds':7200,'cells':500,'e0_seconds':60,'retries':0,'rss_bytes_per_cell':4294967296,'solver_seconds':60,'workers':1},'candidate_limit':3,'selection':'strict_lexicographic_makespan_added_copy_bytes','retry':False}
 for lo in range(1,100,10):
  shard=root/f'cases-{lo:03d}-{lo+9:03d}'; snap=readj(shard/'snapshot.json'); feed=readj(shard/'board-feed.json')
  for fr in feed.get('records',[]):
   if (fr.get('run_id')!=snap['run_id'] or fr.get('algorithm_id')!='q2-adaptive-hypergap-guarded' or fr.get('solver_commit')!=SOLVER or fr.get('parameters')!=params or fr.get('provenance',{}).get('runner',{}).get('source',{}).get('commit')!=RUNNER or fr.get('status')!='ok'):raise ValueError('archived feed run/algorithm/parameter/runner mismatch')
   fk=(str(fr['case_id']),int(fr['cores']))
   if fk in feed_records:raise ValueError(f'duplicate feed row {fk}')
   feed_records[fk]=fr
 if set(feed_records)!=set(GRID):raise ValueError('archived shard feeds do not cover unique 500 grid')
 for row in rows:
  case=str(row['case']);k=int(row['cores']);key=(case,k); rec=old[key]
  base=rec['baseline']['result']; br=unpack_from_git(repo,BASE,base['path'])
  if sha(br)!=base['sha256']:raise ValueError(f'baseline artifact hash mismatch {key}')
  B=json.loads(unpack_bytes(br))['makespan']; om=rec['metrics']['makespan_cycles']; nm=row['official']['makespan']
  shard=(int(case)-1)//10*10+1; cell=root/f'cases-{shard:03d}-{shard+9:03d}'/f'{case}-k{k}'
  c=readj(cell/'cell.json'); arch=readj(cell/'run.json'); fr=feed_records[key]
  if (c['case'],int(c['cores']),c['status'])!=(case,k,'accepted') or c['graph_sha256']!=row['graph_sha256'] or c['config_sha256']!=row['config_sha256']:raise ValueError(f'archive identity mismatch {key}')
  plan=unpack(cell/'plan.json.gz'); result=unpack(cell/'result.json.gz')
  if sha(plan)!=c['plan_sha256'] or sha(result)!=c['official']['result_sha256']:raise ValueError(f'compressed artifact hash mismatch {key}')
  if sha((cell/'plan.json.gz').read_bytes())!=fr['artifacts']['plan']['sha256'] or sha((cell/'result.json.gz').read_bytes())!=fr['artifacts']['result']['sha256'] or fr['artifacts']['run']['sha256']!=sha((cell/'run.json').read_bytes()):raise ValueError(f'feed artifact SHA reference mismatch {key}')
  for procfile in ('solver-process.json','e0-process.json'):
   proc=readj(cell/procfile)
   if proc.get('status')!='ok' or proc.get('exit_code')!=0 or proc.get('surviving_pids')!=[]:raise ValueError(f'process receipt mismatch {key}/{procfile}')
  ledgerraw=(cell/'online-ledger.json').read_bytes();ledger=json.loads(ledgerraw)
  if sha(ledgerraw)!=c.get('solver_ledger_sha256') or ledger.get('solver_checkout_commit')!=RUNNER or ledger.get('request_in_flight') or ledger.get('possible_E0_fallback_calls')!=0 or ledger.get('calls',{}).get('E2_api_attempted')!=c['calls']['E2_api_attempted'] or ledger.get('calls',{}).get('native_returns')!=c['calls']['native_returns']:raise ValueError(f'online solver identity/uncertainty mismatch {key}')
  out=json.loads(result)
  if out['makespan']!=nm or out.get('cross_task_traffic')!=row['official'].get('cross_task_traffic') or {f:out['data_movement_bytes'][f] for f in FIELDS}!=row['official'].get('movement'):raise ValueError(f'E0/result metric mismatch {key}')
  ident=rec.get('identity',{})
  source=json.loads((repo/'docs/a/source-manifest.json').read_bytes())
  if ident.get('graph_sha256')!=c['graph_sha256'] or ident.get('config_sha256')!=c['config_sha256'] or ident.get('official_sha256')!=source['official_code_hash']:raise ValueError(f'baseline graph/config/official mismatch {key}')
  pair_old=B/om; pair_new=B/nm; oldvals[k].append(pair_old);newvals[k].append(pair_new)
  ix=0 if pair_new>pair_old else 2 if pair_new<pair_old else 1;wins[k][ix]+=1
  if nm<om:improved.add(case)
  op=rec['artifacts']['plan']; oldplanblob=unpack_from_git(repo,BASE,op['path'])
  if sha(oldplanblob)!=op['sha256']:raise ValueError(f'old plan hash mismatch {key}')
  oldplan=unpack_bytes(oldplanblob)
  if oldplan!=plan:plan_changed.add(case)
  sw.append(float(row['solver_process']['wall_seconds']));ew.append(float(row['e0_process']['wall_seconds']))
  calls['solver']+=1;calls['E2']+=int(c['calls']['E2_api_attempted']);calls['native']+=int(c['calls']['native_returns']);calls['E0']+=int(c['calls']['E0_independent_started']);calls['fallback']+=int(c['calls']['E0_fallback_confirmed']+c['calls']['E0_fallback_possible']);calls['unknown']+=int(c['request_in_flight'])
 total=s.get('calls',{})
 if calls['solver']!=500 or calls['E0']!=500 or calls['fallback'] or calls['unknown'] or calls['E2']!=calls['native'] or total.get('solver_started')!=500 or total.get('E0_independent_started')!=500 or total.get('E2_api_attempted')!=calls['E2'] or total.get('native_returns')!=calls['native'] or total.get('E0_fallback_confirmed') or total.get('E0_fallback_possible'):raise ValueError('call accounting mismatch')
 out={'status':'complete','cells':500,'core_comparison':{str(k):{'new_mean_B_over_M':statistics.fmean(newvals[k]),'old_mean_B_over_M':statistics.fmean(oldvals[k]),'wins_ties_losses':wins[k]} for k in range(1,6)},'cases_improved_makespan_any_core':len(improved),'cases_with_plan_change_any_core':len(plan_changed),'solver_wall_seconds':stat(sw),'external_E0_wall_seconds':stat(ew),'calls':calls,'peer_targets_reference_only':[2.26,3.18,3.96,4.53],'limitations':'Paired full500 evidence only; peer targets are external context, not reproduced here; these results do not prove optimality.'}
 print(json.dumps(out,indent=2));return 0
def unpack_from_git(repo,commit,path):
 return subprocess.check_output(['git','-C',str(repo),'show',f'{commit}:{path}'])
def unpack_bytes(b): return gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b
if __name__=='__main__':raise SystemExit(main())
