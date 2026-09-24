"""Bounded structural checks; ZERO official evaluator/solver calls.

Domain: abstract nonempty blocks partition n labelled vertices; k ordered core
lists; original quotient plus consecutive core-order arcs is acyclic.
This does NOT model Step1/2/3, memory, COPY, floating point, or P_exec.
"""
from __future__ import annotations
import itertools as it
import json, platform, sys, time, hashlib
from collections import deque
from pathlib import Path


def partitions(n):
    def rec(i, blocks):
        if i == n:
            yield tuple(tuple(b) for b in blocks); return
        for j in range(len(blocks)):
            blocks[j].append(i); yield from rec(i+1,blocks); blocks[j].pop()
        blocks.append([i]); yield from rec(i+1,blocks); blocks.pop()
    yield from rec(0,[])


def compositions(n,k):
    if k==1:
        yield (n,); return
    for i in range(n+1):
        for rest in compositions(n-i,k-1): yield (i,)+rest


def plans(n,k):
    for blocks in partitions(n):
        for word in it.permutations(blocks):
            for lens in compositions(len(blocks),k):
                i=0; core=[]
                for length in lens: core.append(word[i:i+length]); i+=length
                yield tuple(core)


def adjacency(plan,edges,omit=None):
    blocks=[b for c in plan for b in c]
    owner={v:b for b in blocks for v in b}
    succ={b:set() for b in blocks}
    for u,v in edges:
        if owner[u]!=owner[v]:succ[owner[u]].add(owner[v])
    for c in plan:
        rest=[b for b in c if b!=omit]
        for a,b in zip(rest,rest[1:]):succ[a].add(b)
    return succ


def acyclic(succ):
    ind={u:0 for u in succ}
    for ns in succ.values():
        for v in ns:ind[v]+=1
    stack=[v for v in ind if ind[v]==0]; done=0
    while stack:
        u=stack.pop(); done+=1
        for v in succ[u]:
            ind[v]-=1
            if ind[v]==0:stack.append(v)
    return done==len(succ)


def freeze(plan):return tuple(tuple(c) for c in plan)


def move(plan,b,c,j):
    p=[[x for x in core if x!=b] for core in plan]
    p[c].insert(j,b); return freeze(p)


def reach(succ,b):
    seen=set(); stack=list(succ[b])
    while stack:
        x=stack.pop()
        if x not in seen:seen.add(x); stack.extend(succ[x]-seen)
    return seen


def bounds(plan,edges,b,c):
    succ=adjacency(plan,edges,omit=b); pred={u:set() for u in succ}
    for u,ns in succ.items():
        for v in ns:pred[v].add(u)
    anc,des=reach(pred,b),reach(succ,b)
    rest=[x for x in plan[c] if x!=b]
    lo=1+max((i for i,x in enumerate(rest) if x in anc),default=-1)
    hi=min((i for i,x in enumerate(rest) if x in des),default=len(rest))
    return set(range(lo,hi+1))


def neighbors(plan,edges):
    for c,core in enumerate(plan):
        for i,b in enumerate(core):
            for target in range(len(plan)):
                for j in bounds(plan,edges,b,target):
                    p=move(plan,b,target,j)
                    if p!=plan:yield p
            for size in range(1,len(b)):
                for subset in it.combinations(b,size):
                    I=set(subset)
                    if any(u in b and v in I and u not in I for u,v in edges):continue
                    p=[list(x) for x in plan]
                    p[c][i:i+1]=[tuple(subset),tuple(v for v in b if v not in I)]
                    p=freeze(p)
                    assert acyclic(adjacency(p,edges)), 'ideal split broke structural domain'
                    yield p
        for i in range(len(core)-1):
            p=[list(x) for x in plan]
            p[c][i:i+2]=[tuple(sorted(core[i]+core[i+1]))]
            p=freeze(p)
            if acyclic(adjacency(p,edges)):yield p


def run():
    start=time.perf_counter(); envs=states=slots=links=0; rows=[]
    for n in range(1,5):
        possible=list(it.combinations(range(n),2))
        all_plans={k:list(plans(n,k)) for k in (1,2)}
        for mask in range(1<<len(possible)):
            edges=[e for i,e in enumerate(possible) if (mask>>i)&1]
            for k in (1,2):
                legal={p for p in all_plans[k] if acyclic(adjacency(p,edges))}
                assert legal
                for p in legal:
                    for b in (b for c in p for b in c):
                        for c in range(k):
                            predicted=bounds(p,edges,b,c)
                            count=len(p[c])+1-int(b in p[c]); slots+=count
                            truth={j for j in range(count) if acyclic(adjacency(move(p,b,c,j),edges))}
                            assert predicted==truth, (p,b,c,predicted,truth)
                root=next(iter(legal)); visited={root}; queue=deque([root])
                while queue:
                    p=queue.popleft()
                    for q in neighbors(p,edges):
                        links+=1
                        assert q in legal
                        if q not in visited:visited.add(q); queue.append(q)
                assert visited==legal, (n,k,edges,len(visited),len(legal))
                envs+=1;states+=len(legal)
                rows.append(dict(n=n,k=k,edge_mask=mask,legal_states=len(legal),connected=True))
    result={
      'scope':'abstract ordered-partition structural domain only; not official P_exec',
      'official_evaluator_calls':0,'solver_optimization_runs':0,
      'n_values':[1,2,3,4],'k_values':[1,2],
      'graph_family':'all subsets of forward-labelled edges; covers every DAG up to relabelling',
      'environments':envs,'legal_states_across_environments':states,
      'insertion_slots_checked':slots,'generated_edges_checked':links,
      'all_insertion_intervals_exact':True,'all_state_graphs_connected':True,
      'elapsed_seconds':time.perf_counter()-start,
      'python':sys.version,'platform':platform.platform(),
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'rows':rows}
    dest=Path(__file__).with_name('algebra_structural_checks.json')
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':run()
