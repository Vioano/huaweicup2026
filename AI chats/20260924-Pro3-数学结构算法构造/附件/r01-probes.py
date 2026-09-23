#!/usr/bin/env python3
"""Bounded mathematical checks, NOT the contest evaluator or official test cases.
Python standard library only. Run: python probes.py --output results.json
"""
from __future__ import annotations
import argparse, hashlib, heapq, itertools, json, os, platform, random, sys, time
from fractions import Fraction as F
from pathlib import Path

def topo(n: int, edges: list[tuple[int,int]]) -> list[int] | None:
    out=[[] for _ in range(n)]; deg=[0]*n
    for u,v in set(edges): out[u].append(v); deg[v]+=1
    ready=[i for i,d in enumerate(deg) if d==0]; heapq.heapify(ready); order=[]
    while ready:
        u=heapq.heappop(ready); order.append(u)
        for v in out[u]:
            deg[v]-=1
            if deg[v]==0: heapq.heappush(ready,v)
    return order if len(order)==n else None

def partitions(n: int):
    if not n: yield (); return
    def rec(a, mx):
        if len(a)==n: yield tuple(a); return
        for x in range(mx+2): yield from rec(a+[x], max(mx,x))
    yield from rec([0],0)

def quotient(n,edges,p):
    return max(p)+1, sorted({(p[u],p[v]) for u,v in edges if p[u]!=p[v]})

def quotient_checks():
    """Exhaust all forward-edge DAGs on n<=5 and all set partitions.
    Any labeled DAG is isomorphic to a forward-edge DAG under a topological numbering.
    Test existence of a block-contiguous topological extension by explicit concatenation.
    """
    total=valid=local_total=0
    for n in range(1,6):
        pairs=list(itertools.combinations(range(n),2))
        ps=list(partitions(n))
        for mask in range(1<<len(pairs)):
            edges=[e for j,e in enumerate(pairs) if (mask>>j)&1]
            for p in ps:
                total+=1; k,qe=quotient(n,edges,p); qt=topo(k,qe)
                # Independent existence test: inequalities between each pair of entire blocks.
                found=False
                for block_order in itertools.permutations(range(k)):
                    rank={b:i for i,b in enumerate(block_order)}
                    if all(p[u]==p[v] or rank[p[u]]<rank[p[v]] for u,v in edges):
                        found=True; break
                assert (qt is not None)==found
                if qt is not None:
                    valid+=1
                    word=[u for b in qt for u in range(n) if p[u]==b]
                    pos={u:i for i,u in enumerate(word)}
                    assert all(pos[u]<pos[v] for u,v in edges)
            # For every S, contraction is acyclic iff no path S -> outside -> S.
            for sm in range(1,1<<n):
                S={u for u in range(n) if sm>>u&1}; outside=set(range(n))-S
                out=[[] for _ in range(n)]
                for u,v in edges: out[u].append(v)
                exits={v for u in S for v in out[u] if v in outside}
                seen=set(exits); stack=list(exits); leave_return=False
                while stack:
                    u=stack.pop()
                    for v in out[u]:
                        if v in S: leave_return=True
                        elif v not in seen: seen.add(v); stack.append(v)
                p=[0 if u in S else 1+sorted(outside).index(u) for u in range(n)]
                k,qe=quotient(n,edges,p)
                assert (topo(k,qe) is not None)==(not leave_return)
                local_total+=1
    # Both blocks convex, but their quotient cycles.
    n=4; edges=[(0,1),(2,3)]; p=(0,1,1,0)
    k,qe=quotient(n,edges,p); assert topo(k,qe) is None
    return {'partition_checks':total,'acyclic_quotients':valid,
            'subset_contraction_checks':local_total,
            'convex_blocks_counterexample':{'edges':edges,'partition':p,'quotient':qe}}

def eval_dag(n,edges,seeds):
    preds=[[] for _ in range(n)]
    for u,v,w in edges: preds[v].append((u,w))
    x=[None]*n
    for v in range(n):
        values=([seeds[v]] if v in seeds else [])+[x[u]+w for u,w in preds[v] if x[u] is not None]
        x[v]=max(values) if values else None
    return x

def eliminate(n,edges,B):
    """Maximum weight between retained vertices, internal vertices all outside B."""
    succ=[[] for _ in range(n)]
    for u,v,w in edges: succ[u].append((v,w))
    H={}
    for s in sorted(B):
        d={s:0}
        for u in range(s,n):
            if u not in d: continue
            if u!=s and u in B:
                H[s,u]=max(H.get((s,u),d[u]),d[u]); continue
            for v,w in succ[u]: d[v]=max(d.get(v,d[u]+w),d[u]+w)
    return [(u,v,w) for (u,v),w in H.items()]

def maxplus_checks(rng):
    checks=0
    for trial in range(500):
        n=rng.randint(3,30)
        edges=[(u,v,rng.randint(0,20)) for u in range(n) for v in range(u+1,n) if rng.random()<.15]
        indeg=[0]*n; outdeg=[0]*n
        for u,v,w in edges: indeg[v]+=1; outdeg[u]+=1
        roots={i for i in range(n) if indeg[i]==0}
        B=roots | {i for i in range(n) if outdeg[i]==0} | {i for i in range(n) if rng.random()<.2}
        h=eliminate(n,edges,B)
        for _ in range(5):
            seeds={i:rng.randint(0,100) for i in roots}
            full=eval_dag(n,edges,seeds); reduced=eval_dag(n,h,seeds)
            assert all(full[b]==reduced[b] for b in B); checks+=1
    return {'graphs':500,'boundary_value_comparisons':checks,'exact_integer_arithmetic':True}

def ps_reference(jobs):
    """Fluid processor sharing, per-job remaining work; completions before tied arrivals."""
    jobs=sorted(jobs); i=0; t=F(0); rem={}; done={}
    while i<len(jobs) or rem:
        if not rem and t<jobs[i][0]: t=jobs[i][0]
        while i<len(jobs) and jobs[i][0]==t:
            a,j,w=jobs[i]; rem[j]=w; i+=1
        if not rem: continue
        end=t+min(rem.values())*len(rem)
        nxt=min(end,jobs[i][0]) if i<len(jobs) else end
        amount=(nxt-t)/len(rem)
        rem={j:w-amount for j,w in rem.items()}; t=nxt
        for j in sorted([j for j,w in rem.items() if w==0]): done[j]=t; del rem[j]
    return done

def ps_virtual(jobs):
    """Same fluid model, using a virtual service clock and finishing tags."""
    jobs=sorted(jobs); i=0; t=F(0); V=F(0); heap=[]; done={}
    while i<len(jobs) or heap:
        if not heap and t<jobs[i][0]: t=jobs[i][0]
        while i<len(jobs) and jobs[i][0]==t:
            a,j,w=jobs[i]; heapq.heappush(heap,(V+w,j)); i+=1
        if not heap: continue
        end=t+len(heap)*(heap[0][0]-V)
        nxt=min(end,jobs[i][0]) if i<len(jobs) else end
        V+=(nxt-t)/len(heap); t=nxt
        while heap and heap[0][0]==V:
            tag,j=heapq.heappop(heap); done[j]=t
    return done

def ps_checks(rng):
    jobs_checked=0
    for trial in range(1000):
        n=rng.randint(1,20)
        jobs=[(F(rng.randint(0,25),rng.choice([1,2,3])),j,F(rng.randint(1,20),rng.choice([1,2,3]))) for j in range(n)]
        assert ps_reference(jobs)==ps_virtual(jobs); jobs_checked+=n
    early=ps_virtual([(F(0),0,F(1)),(F(0),1,F(2))])
    later=ps_virtual([(F(0),0,F(1)),(F(1),1,F(2))])
    a=max(early[0]+100,early[1]); b=max(later[0]+100,later[1]); assert (a,b)==(102,101)
    return {'arrival_streams':1000,'jobs':jobs_checked,'arithmetic':'fractions.Fraction',
            'NOT_OFFICIAL':'No integer retirement / ceil(-1e-9) / floating point semantics modeled',
            'earlier_release_counterexample':{'early_makespan':str(a),'later_makespan':str(b)}}

def fifo_insert(entries,key,size,cap):
    entries=list(entries)
    if any(k==key for k,s in entries) or size>cap: return entries
    while entries and sum(s for k,s in entries)+size>cap: entries.pop(0)
    return entries+[(key,size)]

def cache_normalize(entries, live):
    """Observational quotient relative to future query/insert alphabet `live`.
    Drops a leading dead prefix and aggregates each other contiguous dead run.
    Does NOT preserve cache-used-bytes/evicted-ID diagnostics; retain a witness.
    """
    entries=list(entries)
    while entries and entries[0][0] not in live: entries.pop(0)
    ans=[]
    for key,size in entries:
        if key in live: ans.append((key,size))
        elif ans and ans[-1][0]=='#DEAD': ans[-1]=('#DEAD',ans[-1][1]+size)
        else: ans.append(('#DEAD',size))
    return ans

def fifo_checks(rng):
    a=fifo_insert([('a',1),('b',1)],'c',1,2)
    b=fifo_insert([('b',1),('a',1)],'c',1,2)
    assert not any(k=='a' for k,s in a) and any(k=='a' for k,s in b)
    # Removing an INTERIOR dead item incorrectly can prevent eviction of live a.
    raw=fifo_insert([('a',1),('dead',1)],'b',1,2)
    incorrectly_removed=fifo_insert([('a',1)],'b',1,2)
    assert not any(k=='a' for k,s in raw) and any(k=='a' for k,s in incorrectly_removed)
    deletion_example=[raw, incorrectly_removed]
    # A key with a pending insert must remain in the observable alphabet.
    pending_raw=fifo_insert([('a',1),('x',1)],'x',1,2)
    pending_wrong=fifo_insert(cache_normalize([('a',1),('x',1)],{'a'}),'x',1,2)
    assert any(k=='a' for k,_ in pending_raw) and not any(k=='a' for k,_ in pending_wrong)
    checks=0; streams=5000; shrink_checks=0
    for _ in range(streams):
        keys=[f'k{i}' for i in range(rng.randint(2,12))]
        rng.shuffle(keys)
        sizes={k:rng.randint(1,7) for k in keys}
        raw=[(k,sizes[k]) for k in keys]
        cap=sum(s for k,s in raw)+rng.randint(0,7)
        live={k for k in keys if rng.random()<.5} | {'fresh0','fresh1'}
        sizes.update({'fresh0':rng.randint(1,7),'fresh1':rng.randint(1,7)})
        compressed=cache_normalize(raw,live)
        for _ in range(20):
            key=rng.choice(sorted(live))
            assert any(k==key for k,s in raw)==any(k==key for k,s in compressed)
            raw=fifo_insert(raw,key,sizes[key],cap)
            compressed=cache_normalize(fifo_insert(compressed,key,sizes[key],cap),live)
            assert cache_normalize(raw,live)==compressed
            checks+=1
        smaller={k for k in live if rng.random()<.5}
        assert cache_normalize(cache_normalize(raw,live),smaller)==cache_normalize(raw,smaller)
        shrink_checks+=1
    exhaustive=0
    base=['a','b','c']; all_keys=base+['d']
    for cap in range(1,9):
        for n in range(4):
            for order in itertools.permutations(base,n):
                for size_values in itertools.product(range(1,4),repeat=4):
                    sizes=dict(zip(all_keys,size_values)); state=[(k,sizes[k]) for k in order]
                    if sum(s for _,s in state)>cap: continue
                    for mask in range(16):
                        live={k for i,k in enumerate(all_keys) if mask>>i&1}
                        normal=cache_normalize(state,live)
                        assert all(any(k==q for k,_ in state)==any(k==q for k,_ in normal) for q in live)
                        for key in live:
                            left=cache_normalize(fifo_insert(state,key,sizes[key],cap),live)
                            right=cache_normalize(fifo_insert(normal,key,sizes[key],cap),live)
                            assert left==right
                            exhaustive+=1
    return {'ordered_set_counterexample':[a,b],
            'unsafe_interior_dead_deletion':deletion_example,
            'pending_insert_counterexample':[pending_raw,pending_wrong],
            'exhaustive_small_state_insertion_checks':exhaustive,
            'alphabet_shrink_checks':shrink_checks,
            'normalized_dead_run_streams':streams,'normalized_dead_run_transitions':checks,
            'scope':'Future queries/inserts only on fixed live alphabet; ordered raw cache diagnostics NOT preserved'}

def segmentation_checks(rng):
    """One-core additive closed-task model, NOT asserted to match official compilation."""
    checks=0
    for _ in range(500):
        n=rng.randint(1,11); wait=rng.randint(0,10)
        cost={(i,j):rng.randint(1,40) for i in range(n) for j in range(i+1,n+1)}
        dp=[0]+[10**9]*n
        for j in range(1,n+1): dp[j]=min(dp[i]+cost[i,j]+(wait if i else 0) for i in range(j))
        vals=[]
        for mask in range(1<<(n-1)):
            cuts=[0]+[i for i in range(1,n) if mask>>(i-1)&1]+[n]
            vals.append(sum(cost[i,j] for i,j in zip(cuts,cuts[1:]))+(len(cuts)-2)*wait)
        assert dp[n]==min(vals); checks+=1
    return {'random_cost_tables':checks,'scope':'exact additive closed-task special case only'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='probe_results.json'); args=ap.parse_args()
    seed=20260923; rng=random.Random(seed); t=time.perf_counter()
    results={'scope':'Mathematical-model checks only. NO official code / official cases / GPU execution.',
      'seed':seed,'environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'logical_cpus_visible':os.cpu_count()},
      'official_code_hash_supplied_not_verified':'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0',
      'quotients':quotient_checks(), 'maxplus':maxplus_checks(rng), 'processor_sharing':ps_checks(rng),
      'fifo':fifo_checks(rng),'segmentation':segmentation_checks(rng)}
    results['elapsed_seconds_nonbenchmark']=time.perf_counter()-t
    results['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    results['all_assertions_passed']=True
    Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
