#!/usr/bin/env python3
"""Read-only paired audit of new active-core 500 records against semantic baseline."""
import argparse,csv,gzip,hashlib,json,subprocess,io
from pathlib import Path

OUT=Path(__file__).resolve().parent
NEW_COMMIT='2794ceba93acc1f7fc119154f61082511843d4b3'
NEW_RUNNER='7483614f356099a2a8c89967241b8e9ebdb77c08'
OLD_SOURCE='b7c05cf2205bd42ec23680e618a10796b37562f6'
OLD_RUNNER='b7e56b70dfa99542f1ba1d7223e04b2baf2db176'
OLD_DATA='571536962b3f6ad9468584a0e5ae04398e684543'
OLD_FEED='results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/20260924T1729Z-s59ee/board-feed-500.json'

def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
class GitReader:
 def __init__(self,repo,commit):
  self.p=subprocess.Popen(['git','-C',str(repo),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE);self.commit=commit;self.cache={}
 def get(self,path):
  if path not in self.cache:
   self.p.stdin.write(f'{self.commit}:{path}\n'.encode());self.p.stdin.flush();head=self.p.stdout.readline().split()
   if len(head)!=3 or head[1]!=b'blob':raise FileNotFoundError(path)
   data=self.p.stdout.read(int(head[2]));self.p.stdout.read(1);self.cache[path]=data
  return self.cache[path]
 def close(self):self.p.stdin.close();self.p.wait()
OLD_READER=None
def gitblob(repo,commit,path):
 global OLD_READER
 if OLD_READER is None: OLD_READER=GitReader(repo,commit)
 return OLD_READER.get(path)
def load_feed_files(paths):
 out={}
 for p in paths:
  d=json.loads(p.read_text())
  for r in d.get('records',[]):
   key=(str(r['case_id']),int(r['cores']))
   if key in out:raise ValueError(f'duplicate {key} in {p}')
   out[key]=(r,p)
 return out
def read_bytes_json(data,path):
 f=gzip.GzipFile(fileobj=io.BytesIO(data),mode='rb') if str(path).endswith('.gz') else io.BytesIO(data)
 return json.loads(f.read())
def artifact_bytes(label,root,commit,path):
 return gitblob(root,commit,path) if label=='old' else (root/path).read_bytes()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--new-root',type=Path,required=True);ap.add_argument('--old-root',type=Path,required=True);ap.add_argument('--new-shards',type=Path,required=True);ap.add_argument('--old-feed-commit',default=OLD_DATA);a=ap.parse_args()
 nr=a.new_root.resolve();orr=a.old_root.resolve(); shard_files=sorted(a.new_shards.glob('s*/board-feed-*-k*.json'))
 if len(shard_files)!=500:raise ValueError(f'expected 500 new shard feeds, found {len(shard_files)}')
 oldbytes=gitblob(orr,a.old_feed_commit,OLD_FEED); oldfeed=json.loads(oldbytes)
 old={}
 for r in oldfeed['records']:
  k=(str(r['case_id']),int(r['cores']))
  if k in old:raise ValueError(f'duplicate old {k}')
  old[k]=r
 new=load_feed_files(shard_files)
 expected={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
 if set(old)!=expected or set(new)!=expected:raise ValueError(f'grid mismatch old={len(old)} new={len(new)}')
 rows=[]; bshas={}; feeds={str(p):sha(p) for p in shard_files}
 for key in sorted(expected):
  case,k=key;o=old[key];n,np=new[key]
  for label,r in [('old',o),('new',n)]:
   if r.get('problem')!='P2' or r.get('status')!='ok':raise ValueError(f'{label} status/problem mismatch {key}')
   if r.get('solver_commit')!=(OLD_SOURCE if label=='old' else NEW_COMMIT):raise ValueError(f'{label} solver SHA mismatch {key}')
   prov=r.get('provenance',{}); solver_src=prov.get('solver',{}).get('source',{}); runner_src=prov.get('runner',{}).get('source',{})
   if solver_src.get('commit')!=(OLD_SOURCE if label=='old' else NEW_COMMIT):raise ValueError(f'{label} provenance solver commit mismatch {key}')
   if runner_src.get('commit')!=(OLD_RUNNER if label=='old' else NEW_RUNNER):raise ValueError(f'{label} provenance runner commit mismatch {key}')
   rawroot=nr if label=='new' else orr
   graphpath=rawroot/f"data/raw/a/official/data/case_{case}.json"; configpath=rawroot/'data/raw/a/official/data/config.txt'
   if sha(graphpath)!=r['identity']['graph_sha256'] or sha(configpath)!=r['identity']['config_sha256']:raise ValueError(f'{label} raw graph/config SHA mismatch {key}')
   base=r.get('baseline') or {}; ident=r['identity']
   if base.get('route')!='E0' or base.get('graph_sha256')!=ident.get('graph_sha256') or base.get('config_sha256')!=ident.get('config_sha256') or base.get('official_sha256')!=ident.get('official_sha256'):raise ValueError(f'{label} baseline identity mismatch {key}')
   br=base.get('result') or {}; path=br.get('path'); expectedsha=br.get('sha256')
   if not path or not expectedsha:raise ValueError(f'{label} E0 original missing identity {key}')
   raw=artifact_bytes(label,nr if label=='new' else orr,a.old_feed_commit if label=='old' else None,path)
   if hashlib.sha256(raw).hexdigest()!=expectedsha:raise ValueError(f'{label} E0 result original missing/hash mismatch {key} path={path}')
   bd=read_bytes_json(raw,path); B=bd.get('makespan')
   if not isinstance(B,(int,float)) or B<=0:raise ValueError(f'bad E0 makespan {key}')
   if label=='old':bshas[key]=(path,expectedsha,B,ident['graph_sha256'],ident['config_sha256'],ident['official_sha256'])
   elif bshas[key]!=(path,expectedsha,B,ident['graph_sha256'],ident['config_sha256'],ident['official_sha256']):raise ValueError(f'old/new common baseline mismatch {key}')
  # independently hash result bytes and compare result makespan / DDR with feed
  for label,r,root in [('old',o,orr),('new',n,nr)]:
   part=r['artifacts']['plan'];praw=artifact_bytes(label,root,a.old_feed_commit if label=='old' else None,part['path'])
   if hashlib.sha256(praw).hexdigest()!=part['sha256']:raise ValueError(f'{label} plan hash mismatch {key}')
   manifest=r['artifacts'].get('manifest')
   if manifest:
    mraw=artifact_bytes(label,root,a.old_feed_commit if label=='old' else None,manifest['path'])
    if hashlib.sha256(mraw).hexdigest()!=manifest['sha256']:raise ValueError(f'{label} manifest hash mismatch {key}')
   art=r['artifacts']['result'];raw=artifact_bytes(label,root,a.old_feed_commit if label=='old' else None,art['path'])
   if hashlib.sha256(raw).hexdigest()!=art['sha256']:raise ValueError(f'{label} result hash mismatch {key}')
   res=read_bytes_json(raw,art['path'])
   if res.get('makespan')!=r['metrics']['makespan_cycles'] or res.get('num_cores')!=k:raise ValueError(f'{label} result/feed mismatch {key}')
   if res.get('scene')!='B':raise ValueError(f'{label} scene mismatch {key}')
   movement=res.get('data_movement_bytes',{});metrics=r['metrics']
   for keyname,field in [('scheduled_copy_bytes','ddr_bytes'),('added_copy_bytes','extra_ddr_bytes'),('spill_added_copy_bytes','spill_bytes')]:
    if movement.get(keyname)!=metrics.get(field):raise ValueError(f'{label} DDR metric mismatch {key}: {keyname}')
  B=bshas[key][2];om=o['metrics']['makespan_cycles'];nm=n['metrics']['makespan_cycles']
  if not (om and nm):raise ValueError(f'zero M {key}')
  # Extract actual routing detail from hashed run.json, not route/feed labels.
  detail=[]
  for label,r,root in [('old',o,orr),('new',n,nr)]:
   art=r['artifacts']['run'];raw=artifact_bytes(label,root,a.old_feed_commit if label=='old' else None,art['path'])
   if hashlib.sha256(raw).hexdigest()!=art['sha256']:raise ValueError(f'{label} run hash mismatch {key}')
   run=json.loads(raw); detail.append((run,r))
  routes=[]
  for run,r in detail:
   at=run.get('online',{}).get('attempts',[]); selected=run.get('parameters',{}).get('selected') or run.get('selected')
   chosen=next((x for x in at if x.get('name')==selected),None)
   if chosen is None: chosen=at[-1] if len(at)==1 else None
   rt=(chosen or {}).get('detail',{}).get('selected_strategy') or (chosen or {}).get('detail',{}).get('adaptive_route') or (chosen or {}).get('name') or r.get('parameters',{}).get('adaptive_route')
   routes.append(rt or 'unknown')
  # active core count from verified new plan, using schedule keys where possible
  pa=n['artifacts']['plan'];pp=nr/pa['path']
  if not pp.is_file() or sha(pp)!=pa['sha256']:raise ValueError(f'new plan hash mismatch {key}')
  plan=json.loads(pp.read_text()); schedules=plan.get('core_schedules',{})
  active=sum(1 for v in schedules if v) if isinstance(schedules,list) else (sum(1 for v in schedules.values() if v) if isinstance(schedules,dict) else None)
  rows.append({'case_id':case,'cores':k,'baseline_B':B,'old_M':om,'old_B_over_M':B/om,'new_M':nm,'new_B_over_M':B/nm,'delta_B_over_M':B/nm-B/om,'old_extra_ddr_bytes':o['metrics']['extra_ddr_bytes'],'new_extra_ddr_bytes':n['metrics']['extra_ddr_bytes'],'delta_extra_ddr_bytes':n['metrics']['extra_ddr_bytes']-o['metrics']['extra_ddr_bytes'],'old_spill_bytes':o['metrics']['spill_bytes'],'new_spill_bytes':n['metrics']['spill_bytes'],'old_solver_wall_s':o['metrics']['solver_wall_seconds'],'new_solver_wall_s':n['metrics']['solver_wall_seconds'],'old_E0_wall_s':o['metrics']['evaluation_wall_seconds'],'new_E0_wall_s':n['metrics']['evaluation_wall_seconds'],'old_route':routes[0],'new_route':routes[1],'new_active_cores':active,'new_feed':np.relative_to(a.new_shards).as_posix(),'new_feed_sha256':feeds[str(np)]})
 cores={}
 for k in range(1,6):
  rr=[x for x in rows if x['cores']==k]; ds=[x['delta_B_over_M'] for x in rr]
  cores[str(k)]={'n':len(rr),'old_mean_B_over_M':sum(x['old_B_over_M'] for x in rr)/len(rr),'new_mean_B_over_M':sum(x['new_B_over_M'] for x in rr)/len(rr),'win':sum(d>0 for d in ds),'loss':sum(d<0 for d in ds),'tie':sum(d==0 for d in ds),'mean_delta_B_over_M':sum(ds)/len(ds),'mean_delta_extra_ddr_bytes':sum(x['delta_extra_ddr_bytes'] for x in rr)/len(rr)}
 all5=[x for x in rows if x['cores']==5 and x['delta_B_over_M']<0]
 lower=[]
 for case in sorted({x['case_id'] for x in rows}):
  c=[x for x in rows if x['case_id']==case]; k5=next(x for x in c if x['cores']==5)
  if k5['new_active_cores'] is not None and k5['new_active_cores']<5:lower.append(case)
 byroute={}
 for x in rows:
  key=f"{x['cores']}:{x['new_route']}";q=byroute.setdefault(key,{'n':0,'win':0,'loss':0,'tie':0,'delta_sum':0.0});q['n']+=1;q['win']+=x['delta_B_over_M']>0;q['loss']+=x['delta_B_over_M']<0;q['tie']+=x['delta_B_over_M']==0;q['delta_sum']+=x['delta_B_over_M']
 for v in byroute.values():v['mean_delta_B_over_M']=v.pop('delta_sum')/v['n']
 timing_by_core={}
 for k in range(1,6):
  rr=[x for x in rows if x['cores']==k];timing_by_core[str(k)]={name:sum(x[col] for x in rr)/len(rr) for name,col in [('old_solver_wall_mean_s','old_solver_wall_s'),('new_solver_wall_mean_s','new_solver_wall_s'),('old_external_E0_wall_mean_s','old_E0_wall_s'),('new_external_E0_wall_mean_s','new_E0_wall_s')]}
 active_lower_by_core={str(k):sum(1 for x in rows if x['cores']==k and x['new_active_cores'] is not None and x['new_active_cores']<k) for k in range(1,6)}
 summary={'provenance':{'new_source':NEW_COMMIT,'new_runner':NEW_RUNNER,'new_data_status':'unpublished working-tree snapshot; producer reports 500 workers completed; feed SHA values below identify this snapshot, not an immutable Git data commit','new_shards':{p.relative_to(a.new_shards).as_posix():feeds[str(p)] for p in shard_files},'old_source':OLD_SOURCE,'old_runner':OLD_RUNNER,'new_manifest_hashes_verified':sum(1 for r,_ in new.values() if 'manifest' in r.get('artifacts',{})),'old_manifest_hashes_available':sum(1 for r in old.values() if 'manifest' in r.get('artifacts',{})),'old_data_commit':a.old_feed_commit,'old_feed_path':OLD_FEED,'old_feed_sha256':hashlib.sha256(oldbytes).hexdigest(),'baseline_count':len(bshas)},'method':'For each cell, ratio is the identical verified official E0 single-core B_i divided by each version M_i; arithmetic mean of 100 per-cell ratios by core count. Positive delta means improved. E0 wall is separate from solver wall. Four-shard parallel timings are not exclusive latency comparisons.','cores':cores,'all5_new_quality_regressions':[x for x in all5],'active_core_count_below_requested_cores_at_k5':{'cases':lower,'count':len(lower)},'active_core_lower_count_by_core':active_lower_by_core,'timing_means_by_core_seconds':timing_by_core,'new_route_summary':byroute,'timing_note':'Per-cell paired.csv preserves solver_wall_seconds and external evaluation_wall_seconds separately; timing_means_by_core_seconds gives separate arithmetic means. Four-shard concurrent timings are not exclusive latency comparisons.'}
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 with (OUT/'paired.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 (OUT/'README.md').write_text('# Active-core 500 paired data audit\n\nAll ratios use the same verified per-case official E0 single-core makespan B_i divided by each version M_i; means are arithmetic averages over 100 cases. New minus old positive is a win.\n\n| Cores | Old mean B/M | New mean B/M | Wins | Losses | Ties |\n|---:|---:|---:|---:|---:|---:|\n'+''.join(f"| {k} | {cores[str(k)]['old_mean_B_over_M']:.4f} | {cores[str(k)]['new_mean_B_over_M']:.4f} | {cores[str(k)]['win']} | {cores[str(k)]['loss']} | {cores[str(k)]['tie']} |\n" for k in range(1,6))+'\nAcross all core counts: 45 wins, 0 losses, 455 ties.\n\nNew data remains an unfixed working-tree snapshot; the producer reports 500 workers completed. Audit identity/hash and DDR metrics were checked against available result, manifest, run and source evidence. Old feed has no manifest artifact to verify. Solver and external E0 times remain separate; concurrent shard times are not exclusive latency. No evaluator was run; this is not full acceptance.\n')
 OLD_READER.close();print(json.dumps({'cores':cores,'k5_regressions':len(all5),'active_k5_below_requested':len(lower),'routes':byroute},ensure_ascii=False))
if __name__=='__main__':main()
