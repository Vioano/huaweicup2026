"""Read-only, standard-library reconstruction of construct.Index components."""
import hashlib, heapq, json, sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
FOREST=Path(sys.argv[1])
S=json.loads((ROOT/'results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json').read_text())
R=next(x['best'] for x in S['cells'] if x['case_id']=='065' and x['cores']==5)
def verified(path, digest):
 raw=path.read_bytes(); assert hashlib.sha256(raw).hexdigest()==digest,(path,digest)
 return json.loads(raw)
g=verified(ROOT/'data/raw/a/official/data/case_065.json',R['identity']['graph_sha256'])
p=verified(FOREST/R['artifacts']['plan']['path'],R['artifacts']['plan']['sha256'])
ops={o['id']:o for o in g['ops']}; eligible={u:o for u,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
succ={u:set() for u in ops}; prod=defaultdict(set); cons=defaultdict(set); touched=defaultdict(set)
for e in g['edges']:
 a,b=e['source'],e['target']
 if a in ops and b in ops and a!=b:succ[a].add(b)
 elif a in ops:prod[b].add(a);touched[a].add(b)
 elif b in ops:cons[a].add(b);touched[b].add(a)
for t,ps in prod.items():
 for a in ps:
  for b in cons[t]:
   if a!=b:succ[a].add(b)
cs={u:set() for u in eligible}; cp={u:set() for u in eligible}
for u in eligible:
 stack=list(succ[u]); seen=set()
 while stack:
  v=stack.pop()
  if v in eligible:
   if v!=u:cs[u].add(v);cp[v].add(u)
  elif v not in seen:seen.add(v);stack.extend(succ[v])
deg={u:len(cp[u]) for u in eligible};ready=[u for u in eligible if not deg[u]];heapq.heapify(ready);order=[]
while ready:
 u=heapq.heappop(ready);order.append(u)
 for v in cs[u]:
  deg[v]-=1
  if not deg[v]:heapq.heappush(ready,v)
assert len(order)==len(eligible)
left=set(eligible);groups=[];owner={}
for seed in order:
 if seed not in left:continue
 j=len(groups);groups.append([]);left.remove(seed);stack=[seed]
 while stack:
  u=stack.pop();owner[u]=j
  for v in cs[u]|cp[u]:
   if v in left:left.remove(v);stack.append(v)
for u in order:groups[owner[u]].append(u)
assert len(groups)==42
sgcore={}
for core,seq in enumerate(p['core_schedules']):
 for sg in seq:assert sg not in sgcore;sgcore[sg]=core
opcore={int(u):sgcore[sg] for u,sg in p['node_to_subgraph'].items()}
assert set(opcore)==set(eligible)
tensors={x['id']:x for x in g['tensors']}; out=[]
for j,nodes in enumerate(groups):
 cores={opcore[u] for u in nodes};assert len(cores)==1
 work=defaultdict(int)
 for u in nodes:work[eligible[u]['pipe']]+=max(1,eligible[u]['cycles'])
 ext={t for u in nodes for t in touched[u] if any(v in eligible and owner[v]!=j for v in prod[t]|cons[t])}
 out.append({'component':j,'core':next(iter(cores)),'ops':nodes,'op_count':len(nodes),'first_op':min(nodes),
             'work':dict(work),'shared_boundary_tensors':len(ext),'shared_boundary_bytes':sum(tensors[t]['size'] for t in ext)})
summary={'source_commit':R['solver_commit'],'record_id':R['id'],'graph_sha256':R['identity']['graph_sha256'],
         'plan_sha256':R['artifacts']['plan']['sha256'],'components':out,
         'owner_counts':{str(k):sum(x['core']==k for x in out) for k in range(5)},
         'owner_work':{str(k):{pipe:sum(x['work'].get(pipe,0) for x in out if x['core']==k) for pipe in ('PIPE_M','PIPE_V')} for k in range(5)}}
(Path(__file__).parent/'inventory.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'components':len(out),'owner_counts':summary['owner_counts'],'owner_work':summary['owner_work'],
                  'move_candidates':sorted((x for x in out if x['core'] in (1,3,4) and x['shared_boundary_tensors']==0),key=lambda x:(-x['work'].get('PIPE_V',0),x['work'].get('PIPE_M',0)))[:8]},ensure_ascii=False))
