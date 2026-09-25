"""Closed-form one-core safe cut on the frozen full-core envelope H; no evaluator."""
from collections import defaultdict,deque
from hashlib import sha256
from pathlib import Path
import json,time
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
FILES={
 'graph':('data/raw/a/official/data/case_005.json','c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f'),
 'base':('results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json','2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
 'guard':('results/a/q3-nikolastarx/convex-envelope-guard-20260925/RESULT.json','7c234a2c347b1f94e163c5d0092b521465dd0facc294dc3343a6dc38a429f1ab')}

def read(k):
 rel,h=FILES[k];raw=(ROOT/rel).read_bytes()
 if sha256(raw).hexdigest()!=h:raise ValueError(f'{k} SHA differs')
 return json.loads(raw)

def topo(nodes,arcs):
 succ={u:set() for u in nodes};deg=dict.fromkeys(nodes,0)
 for u,v in arcs:
  if u!=v and v not in succ[u]:succ[u].add(v);deg[v]+=1
 q=deque(u for u in nodes if deg[u]==0);ordered=[]
 while q:
  u=q.popleft();ordered.append(u)
  for v in succ[u]:
   deg[v]-=1
   if deg[v]==0:q.append(v)
 return ordered if len(ordered)==len(nodes) else None

def cutoff(nodes,arcs,word,r):
 order=topo(nodes,arcs)
 if order is None:raise ValueError('envelope H cyclic')
 ix={u:i for i,u in enumerate(word)};pred=defaultdict(set)
 for u,v in arcs:pred[v].add(u)
 label={};returning={};witness={}
 for v in order:
  if v in ix:
   opts=[(label[u][0],u) for u in pred[v] if u not in ix and label.get(u,(-1,))[0]>=0]
   if opts:
    i,u=max(opts);returning[ix[v]]=i;witness[ix[v]]=(word[i],u,v)
   label[v]=(ix[v],v)
  else:
   label[v]=max((label[u] for u in pred[v] if label.get(u,(-1,))[0]>=0),default=(-1,None))
 b=max((i for j,i in returning.items() if j<=r),default=-1)
 return b+1,returning,witness

def main():
 began=time.monotonic();g,p,guard=[read(k) for k in ('graph','base','guard')]
 if not guard['base_envelope']['acyclic'] or guard['candidate_envelope']['acyclic']:
  raise ValueError('frozen envelope guard preconditions differ')
 ops={o['id']:o for o in g['ops']};tid={t['id'] for t in g['tensors']};prod=defaultdict(set);cons=defaultdict(set);arcs=set()
 for e in g['edges']:
  u,v=e['source'],e['target']
  if u in ops and v in tid:prod[v].add(u)
  elif u in tid and v in ops:cons[u].add(v)
  elif u in ops and v in ops:arcs.add((u,v))
  else:raise ValueError('unrecognized raw edge')
 for t in tid:arcs.update((u,v) for u in prod[t] for v in cons[t])
 mapping={int(u):sg for u,sg in p['node_to_subgraph'].items()};inverse={sg:u for u,sg in mapping.items()}
 compute={u for u,o in ops.items() if not o['op'].startswith('COPY')}
 if set(mapping)!=compute or len(inverse)!=len(mapping):raise ValueError('base singleton coverage')
 core_arcs=set()
 for w in p['core_schedules']:
  core_arcs.update((inverse[a],inverse[b]) for a,b in zip(w,w[1:]))
 H=arcs|core_arcs
 if len(H)!=guard['base_envelope']['arcs'] or len(ops)!=guard['base_envelope']['nodes'] or topo(set(ops),H) is None:
  raise ValueError('recomputed base envelope differs')
 word=[inverse[sg] for sg in p['core_schedules'][0]]
 r=word.index(1289)
 if r!=202:raise ValueError('fixed consumer rank differs')
 L,returns,witness=cutoff(set(ops),H,word,r)
 result={'schema':'convex-safe-cut-v1','input_sha256':{k:v[1] for k,v in FILES.items()},
  'core':0,'consumer':1289,'consumer_rank':r,'earliest_safe_start':L,
  'envelope_nodes':len(ops),'envelope_arcs':len(H),
  'reentries_through_consumer':sum(j<=r for j in returns),
  'max_exit_index':L-1,'last_witness':witness.get(next((j for j,i in returns.items() if j<=r and i==L-1),-1)),
  'official_calls':0,'elapsed_seconds':None}
 if L<r:
  span=word[L:r+1];newmap=dict(mapping);anchor=mapping[span[0]]
  for u in span:newmap[u]=anchor
  sched=[list(w) for w in p['core_schedules']];removed={mapping[u] for u in span[1:]}
  sched[0]=[sg for sg in sched[0] if sg not in removed]
  tag=lambda u:('sg',newmap[u]) if u in compute else ('copy',u)
  qnodes={tag(u) for u in ops};qedges={(tag(u),tag(v)) for u,v in H if tag(u)!=tag(v)}
  if topo(qnodes,qedges) is None:raise ValueError('explicit H quotient cyclic')
  if set(newmap)!=compute or {sg for w in sched for sg in w}!=set(newmap.values()):
   raise ValueError('candidate coverage differs')
  result.update(candidate_emitted=True,merged_ops=len(span),span_first_op=span[0],span_last_op=span[-1],
                quotient_nodes=len(qnodes),quotient_arcs=len(qedges),quotient_acyclic=True)
  (OUT/'CANDIDATE_UNVALIDATED.json').write_text(json.dumps({'node_to_subgraph':{str(u):newmap[u] for u in sorted(newmap)},'core_schedules':sched},indent=2)+'\n')
 else:
  result.update(candidate_emitted=False,reason='H permits only the consumer singleton in this fixed suffix family')
 result['elapsed_seconds']=time.monotonic()-began
 (OUT/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
