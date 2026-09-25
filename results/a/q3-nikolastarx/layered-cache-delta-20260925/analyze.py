import argparse,collections,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser(); a.add_argument('--manifest',required=True); m=json.loads((ROOT/a.parse_args().manifest).read_text()); out=Path(__file__).resolve().parent
 if sha(out/'analyze.py')!=m['script_sha256']: raise SystemExit('script SHA mismatch')
 fs=[ROOT/m[k] for k in ('old_path','new_path')]
 if [sha(x) for x in fs]!=[m['old_sha256'],m['new_sha256']]: raise SystemExit('input SHA mismatch')
 d=[json.loads(gzip.decompress(x.read_bytes())) for x in fs]
 for x in d:
  if (x.get('scene'),x.get('problem'),x.get('cache_mode'),x.get('num_cores'))!=('B',3,'read_only',5): raise SystemExit('identity/schema mismatch')
  if not isinstance(x.get('cache_events'),list) or not isinstance(x.get('cache_stats'),dict): raise SystemExit('missing cache event fields')
 for x in d:
  for e in x['cache_events']:
   if e.get('event') not in ('hit','miss','insert') or not all(k in e for k in ('time','tensor_id','size_bytes','core_id','op_id')): raise SystemExit('unknown/incomplete event schema')
   if e['event']=='insert' and not all(k in e for k in ('used_bytes','evicted_tensor_ids')): raise SystemExit('incomplete insert schema')
 def agg(x):
  by=collections.defaultdict(lambda:collections.Counter()); sig=collections.Counter(); ev=[]
  for e in x['cache_events']:
   if e['event'] in ('hit','miss'):
    k=str(e['tensor_id']); by[k][e['event']+'_bytes']+=e['size_bytes']; by[k][e['event']+'_count']+=1; by[k][e['event']+'_times'].append(e['time'])
    sig[((k,e['size_bytes'],e['core_id'],e['op_id'],e.get('op')),e['event'])]+=1
   else: ev.append({'time':e['time'],'tensor_id':str(e['tensor_id']),'size_bytes':e['size_bytes'],'core_id':e['core_id'],'op_id':e['op_id'],'evicted_tensor_ids':[str(z) for z in e['evicted_tensor_ids']]})
  for kind in ('hit','miss'):
   if sum(q[kind+'_bytes'] for q in by.values())!=x['cache_stats'][kind+'_bytes']: raise SystemExit('event byte total != cache_stats')
  return by,sig,ev
 A,AS,AE=agg(d[0]); B,BS,BE=agg(d[1]); trans=collections.Counter(); transb=collections.Counter()
 for (sig,t),n in AS.items():
  other='hit' if t=='miss' else 'miss'; q=min(n,BS.get((sig,other),0)); trans[t+'_to_'+other]+=q; transb[t+'_to_'+other]+=q*sig[1]
 keys=[]
 for k in set(A)|set(B):
  x,y=A.get(k,{}),B.get(k,{})
  keys.append({'tensor_id':k,'old_miss_bytes':x.get('miss_bytes',0),'new_miss_bytes':y.get('miss_bytes',0),'miss_delta':y.get('miss_bytes',0)-x.get('miss_bytes',0),'old_hit_bytes':x.get('hit_bytes',0),'new_hit_bytes':y.get('hit_bytes',0),'old_accesses':x.get('miss_count',0)+x.get('hit_count',0),'new_accesses':y.get('miss_count',0)+y.get('hit_count',0),'old_miss_times':x.get('miss_times',[])[:6],'new_miss_times':y.get('miss_times',[])[:6]})
 keys.sort(key=lambda z:(-z['miss_delta'],z['tensor_id'])); top=[z for z in keys if z['miss_delta']>0][:10]
 for z in top:
  k=z['tensor_id']; z['old_cache_events']=[e for e in AE if e['tensor_id']==k or k in e['evicted_tensor_ids']][:20]; z['new_cache_events']=[e for e in BE if e['tensor_id']==k or k in e['evicted_tensor_ids']][:20]
 report={'old_makespan':d[0]['makespan'],'new_makespan':d[1]['makespan'],'old_scheduled_copy_bytes':d[0]['data_movement_bytes']['scheduled_copy_bytes'],'new_scheduled_copy_bytes':d[1]['data_movement_bytes']['scheduled_copy_bytes'],'old_cache_stats':d[0]['cache_stats'],'new_cache_stats':d[1]['cache_stats'],'miss_bytes_delta':d[1]['cache_stats']['miss_bytes']-d[0]['cache_stats']['miss_bytes'],'hit_bytes_delta':d[1]['cache_stats']['hit_bytes']-d[0]['cache_stats']['hit_bytes'],'event_counts':[len(x['cache_events']) for x in d],'logical_key':'tensor_id','request_identity':['tensor_id','size_bytes','core_id','op_id','op'],'exact_event_transitions':dict(trans),'transition_bytes':dict(transb),'old_only_keys':sorted(set(A)-set(B)),'new_only_keys':sorted(set(B)-set(A)),'top_positive_miss_keys':top,'all_key_deltas':keys,'limits':['unpaired request identities remain unexplained','insert evictions do not prove miss causation','event time is simulated cycles, not wall time']}
 (out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n'); (out/'zero_call_ledger.json').write_text(json.dumps({'analysis_processes':1,'candidate_construction':0,'Task':0,'Step':0,'E0':0,'E1':0,'E2':0,'pipe_bound':0,'retries':0},indent=2)+'\n')
 lines=[f"M3 {report['old_makespan']} → {report['new_makespan']}; scheduled copy {report['old_scheduled_copy_bytes']} → {report['new_scheduled_copy_bytes']} B.",f"Miss bytes {d[0]['cache_stats']['miss_bytes']} → {d[1]['cache_stats']['miss_bytes']} (+{report['miss_bytes_delta']}); hit bytes {d[0]['cache_stats']['hit_bytes']} → {d[1]['cache_stats']['hit_bytes']} ({report['hit_bytes_delta']:+}).",f"Events {report['event_counts']}; shared keys {len(set(A)&set(B))}, old-only {len(set(A)-set(B))}, new-only {len(set(B)-set(A))}.",f"Exact operation transitions: {dict(trans)}; bytes: {dict(transb)}.",'Largest positive per-key miss deltas:']
 for z in top: lines.append(f"- tensor_id {z['tensor_id']}: {z['old_miss_bytes']}→{z['new_miss_bytes']} B ({z['miss_delta']:+}), new miss cycles {z['new_miss_times']}; insert/eviction details in analysis.json.")
 lines.append('These are byte/event comparisons, not causal attribution or optimization evidence. Per-key request identity requires same tensor_id, size, core, op ID and type; unpaired events are not guessed. Evictions are reported only where recorded on insert events.')
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()
