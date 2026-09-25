"""Read saved 075 graph/plans only; no project code or evaluator imports."""
from collections import Counter, defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent / 'official-transfer4/cells/075-k5'
def read(name):
    b = (SRC/{'graph.raw.json': 'graph.json', 'base.raw.json': 'reference-plan.json', 'candidate.raw.json': 'candidate-plan.json', 'candidate.diagnostics.json': 'candidate-diagnostics.json'}[name]).read_bytes()
    return json.loads(b), sha256(b).hexdigest()
g, gh = read('graph.raw.json')
base, bh = read('base.raw.json')
cand, ch = read('candidate.raw.json')
diag, dh = read('candidate.diagnostics.json')
ops = {o['id']:o for o in g['ops']}
noncopy = {u for u,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
tids = {t['id'] for t in g['tensors']}
producers, consumers = defaultdict(set), defaultdict(set)
full = defaultdict(set)
for e in g['edges']:
    a,b=e['source'],e['target']
    if a in ops and b in tids: producers[b].add(a)
    elif a in tids and b in ops: consumers[a].add(b)
    elif a in ops and b in ops: full[a].add(b)
for t in tids:
    for a in producers[t]: full[a].update(consumers[t]-{a})
# Traverse only excluded COPY nodes, matching the static graph contraction.
succ = {u:set() for u in noncopy}
for u in noncopy:
    stack=list(full[u]); seen=set()
    while stack:
        v=stack.pop()
        if v in seen: continue
        seen.add(v)
        if v in noncopy: succ[u].add(v)
        else: stack.extend(full[v])
mapping={int(u):int(t) for u,t in base['node_to_subgraph'].items()}
owner={t:c for c,order in enumerate(base['core_schedules']) for t in order}
tasks=set(owner)
pred=defaultdict(set); tsucc=defaultdict(set)
for u,vs in succ.items():
    a=mapping[u]
    for v in vs:
        b=mapping[v]
        if a!=b: pred[b].add(a);tsucc[a].add(b)
degree={t:len(pred[t]) for t in tasks}
ready=deque(sorted(t for t in tasks if not degree[t])); height={t:0 for t in ready}
while ready:
    t=ready.popleft()
    for v in sorted(tsucc[t]):
        height[v]=max(height.get(v,0),height[t]+1)
        degree[v]-=1
        if not degree[v]:ready.append(v)
assert len(height)==len(tasks)
work=defaultdict(Counter);members=defaultdict(set)
for u,t in mapping.items():
    work[t][ops[u]['pipe']]+=max(1,ops[u]['cycles'])
    members[t].add(u)
waves=defaultdict(dict)
for t,h in height.items(): waves[h][owner[t]]=t
rows=[]
def bridge_joins(task):
    nodes=members[task]
    adj={u:(succ[u]|{p for p in nodes if u in succ[p]}) & nodes for u in nodes}
    tin={}; low={}; bridges=set(); clock=[0]
    def dfs(u,parent):
        tin[u]=low[u]=clock[0];clock[0]+=1
        for v in adj[u]:
            if v==parent:continue
            if v not in tin:
                dfs(v,u);low[u]=min(low[u],low[v])
                if low[v]>tin[u]:bridges.add(frozenset((u,v)))
            else:low[u]=min(low[u],tin[v])
    for u in nodes:
        if u not in tin:dfs(u,None)
    result=[]
    for j in nodes:
        incoming=sorted(u for u in nodes if j in succ[u])
        if len(incoming)!=2 or any(frozenset((p,j)) not in bridges for p in incoming):continue
        sides=[]
        for p in incoming:
            forbidden=frozenset((p,j)); found={p}; stack=[p]
            while stack:
                u=stack.pop()
                for v in adj[u]:
                    if frozenset((u,v))!=forbidden and v not in found:
                        found.add(v);stack.append(v)
            sides.append({'pred':p,'nodes':len(found),
                'work':dict(sum((Counter({ops[u]['pipe']:max(1,ops[u]['cycles'])}) for u in found),Counter()))})
        result.append({'join':j,'sides':sides})
    return result
for h,by in sorted(waves.items()):
    loads={c:work[t] for c,t in by.items()};total=sum(loads.values(),Counter())
    p=min(total,key=lambda q:(-total[q],q))
    donors=[c for c in by if 5*loads[c][p]>total[p]]
    helpers=[c for c in by if 5*loads[c][p]<total[p]]
    mx=max(max(load.values(),default=0) for load in loads.values())
    rows.append({'height':h,'tasks_by_core':{str(c):t for c,t in sorted(by.items())},
      'loads_by_core':{str(c):dict(load) for c,load in sorted(loads.items())},
      'dominant_pipe':p,'donors':sorted(donors),'helpers':sorted(helpers),
      'max_task_pipe_work':mx})
for row in rows:
    if row['height'] == 0 or row['height'] >= 2:
        row['bridge_join_candidates_by_core']={c:bridge_joins(t) for c,t in row['tasks_by_core'].items()}
old={int(u):int(t) for u,t in base['node_to_subgraph'].items()}
new={int(u):int(t) for u,t in cand['node_to_subgraph'].items()}
changes=Counter((old[u],new[u]) for u in old if old[u]!=new[u])
candidate_pieces=defaultdict(Counter)
for u,t in new.items():
    if t in (6,107,108):candidate_pieces[t][ops[u]['pipe']]+=max(1,ops[u]['cycles'])
out={'input_sha256':{'graph.raw.json':gh,'base.raw.json':bh,'candidate.raw.json':ch,
                     'candidate.diagnostics.json':dh},'waves':rows,
     'mapping_changes':{f'{a}->{b}':n for (a,b),n in sorted(changes.items())},
     'candidate_task_6_107_108_pipe_work':{str(t):dict(w) for t,w in sorted(candidate_pieces.items())},
     'candidate_reported_waves':diag.get('waves'),
     'new_calls':{'constructors':0,'Task_compiler':0,'response':0,'E0':0,'E1':0,'E2':0}}
print(json.dumps(out,indent=2))
