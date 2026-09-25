"""Pure graph arithmetic checks; no official imports."""
import collections,hashlib,heapq,json,pathlib,zipfile
h=pathlib.Path(__file__).resolve().parent
with zipfile.ZipFile('/mnt/data/通用神经网络处理器下的多核调度问题  附件.zip') as z:g=json.loads(z.read('data/case_044.json'))
allops={o['id']:o for o in g['ops']};ops={u:o for u,o in allops.items() if o['op'] not in ('COPY_IN','COPY_OUT')};tensors={t['id']:t for t in g['tensors']}
prod=collections.defaultdict(set);cons=collections.defaultdict(set);ins=collections.defaultdict(set)
for e in g['edges']:
 a,b=e['source'],e['target']
 if a in allops:prod[b].add(a)
 else:cons[a].add(b);ins[b].add(a)
pred={u:set() for u in ops};succ={u:set() for u in ops}
for t in tensors:
 for u in prod[t]&ops.keys():
  for v in cons[t]&ops.keys():pred[v].add(u);succ[u].add(v)
meta=json.loads((h/'raw_044_structure.json').read_text());jobs=meta['jobs'];cuts=meta['cuts'];k=5
owner={u:c for c,(l,r) in enumerate(zip(cuts,cuts[1:])) for job in jobs for u in job[l:r]}
basewords=[[u for job in jobs for u in job[l:r]] for l,r in zip(cuts,cuts[1:])]
newwords=[[u for u in json.loads((h/f'core{c}_prestep2_word.json').read_text())['candidate'] if u in ops] for c in range(k)]
def bound(words):
 adj={u:{v:500 if owner[u]!=owner[v] else 0 for v in succ[u]} for u in ops}
 for word in words:
  last={}
  for u in word:
   p=ops[u]['pipe']
   if p in last:adj[last[p]][u]=max(adj[last[p]].get(u,0),0)
   last[p]=u
 deg={u:0 for u in ops}
 for u in adj:
  for v in adj[u]:deg[v]+=1
 q=[u for u in deg if deg[u]==0];heapq.heapify(q);start={u:0 for u in ops};visited=0
 while q:
  u=heapq.heappop(q);visited+=1
  for v,d in adj[u].items():
   start[v]=max(start[v],start[u]+ops[u]['cycles']+d);deg[v]-=1
   if deg[v]==0:heapq.heappush(q,v)
 assert visited==len(ops)
 return max(start[u]+ops[u]['cycles'] for u in ops)
base_bound=bound(basewords);new_bound=bound(newwords);assert base_bound==new_bound==26842
common=set(meta['common_keys']);private=[]
for job in jobs:
 ext={t for u in job for t in ins[u] if not(prod[t]&ops.keys())}
 private.append([{'tensor':t,'bytes':tensors[t]['size'],'reader_positions':[p for p,u in enumerate(job) if t in ins[u]]} for t in sorted(ext-common)])
weights=[ops[u]['cycles'] for u in jobs[0]];l,r=cuts[2:4]
seen=set();P=0;parts=[]
for pos in range(l,r):
 for t in sorted(ins[jobs[0][pos]]&common-seen):
  seen.add(t);tau=max(1,(tensors[t]['size']+59)//60);P+=tau
  parts.append({'first_reader_position':pos,'tensor':t,'bytes':tensors[t]['size'],'copy_exclusive_cycles':tau,'cumulative_copy_cycles':P,'compute_suffix_cycles':sum(weights[pos:r]),'gated_finish_bound_offset':P+sum(weights[pos:r])})
rec=json.loads((h/'static_certificate.json').read_text())
rec.update({'original_compute_FIFO_lower_bound':base_bound,'candidate_compute_FIFO_lower_bound':new_bound,'copy_budget_before_spill':{'copy_in_count':182,'copy_out_count':132,'scheduled_copy_bytes':1116256,'added_copy_bytes':140800},'common_and_private_inputs':{'common_keys':len(common),'common_bytes':sum(tensors[t]['size'] for t in common),'private_per_job':private},'third_stage_gated_copy_bound':{'scope':'relative to first incoming activation COPY_IN end; cold, non-reloaded seven unique source keys after that FIFO gate','rows':parts,'stage_finish_lower_offset':max(sum(weights[l:r]),max(x['gated_finish_bound_offset'] for x in parts))}})
rec['calls']['official_derive_multicore_plan']=2
(h/'static_certificate.json').write_text(json.dumps(rec,indent=2)+'\n')
for case in ('044','046'):
 p=h/f'raw_{case}_structure.json';rr=json.loads(p.read_text());rr['all_external_inputs_common']=False;rr['private_input_note']='Each job has an additional private graph input; downstream preload proof covers only shared inputs.';p.write_text(json.dumps(rr,indent=2)+'\n')
print('COMPUTE BOUNDS',base_bound,new_bound)
print('PRIVATE',private[0])
print('THIRD STAGE',rec['third_stage_gated_copy_bound'])
