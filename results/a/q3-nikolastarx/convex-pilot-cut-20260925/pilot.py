"""One fixed 005 core-0 convex segment audit; pure graph operations, no evaluator."""
from __future__ import annotations
from collections import defaultdict, deque
from hashlib import sha256
from pathlib import Path
import gzip, json, time

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
FILES={
 'graph':('data/raw/a/official/data/case_005.json','c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f'),
 'plan':('results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json','2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
 'prepared':('results/a/q3-nikolastarx/layered-one-shot-20260925/run/prepared.json.gz','91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44'),
 'p3':('results/a/q3-nikolastarx/layered-one-shot-20260925/run/p3.json.gz','3c51fac6f14a7c2fdafad3eef6694fb8f38d473e00534c25cd4dadff13cfa0d8'),
}

def read(name):
    rel,h=FILES[name]; p=ROOT/rel; data=p.read_bytes()
    if sha256(data).hexdigest()!=h: raise ValueError(f'{name} input hash differs')
    return json.loads(gzip.decompress(data) if p.suffix=='.gz' else data)

def topo(nodes,edges):
    succ={u:set() for u in nodes}; deg=dict.fromkeys(nodes,0)
    for u,v in edges:
        if u!=v and v not in succ[u]: succ[u].add(v); deg[v]+=1
    q=deque(u for u in nodes if deg[u]==0); order=[]
    while q:
        u=q.popleft(); order.append(u)
        for v in succ[u]:
            deg[v]-=1
            if deg[v]==0:q.append(v)
    return order if len(order)==len(nodes) else None

def cutoff(nodes,edges,word,r):
    """Max last exit index into an alien-core path ending at each core reentry."""
    order=topo(nodes,edges)
    if order is None: raise ValueError('input DAG cyclic')
    index={u:i for i,u in enumerate(word)}
    pred=defaultdict(set)
    for u,v in edges:pred[v].add(u)
    reach={}; reentry={}; witness={}
    for v in order:
        if v in index:
            options=[(reach[u][0],u) for u in pred[v] if u not in index and reach.get(u,(-1,))[0]>=0]
            if options:
                i,u=max(options);reentry[index[v]]=i;witness[index[v]]=(word[i],u,v)
            reach[v]=(index[v],v)
        else:
            options=[reach[u] for u in pred[v] if reach.get(u,(-1,))[0]>=0]
            reach[v]=max(options,default=(-1,None))
    b=max((i for j,i in reentry.items() if j<=r),default=-1)
    return b+1,reentry,witness

def acyclic_contraction(nodes,edges,subset):
    tag=lambda u: ('merged',0) if u in subset else ('node',u)
    return topo({tag(u) for u in nodes},{(tag(u),tag(v)) for u,v in edges if tag(u)!=tag(v)}) is not None

def toy_tests():
    # The word itself is a topological order on the selected core.
    cases=[
      ('direct_safe',{0,1},{(0,1)},[0,1],1,0,True),
      ('cross_return',{0,1,8},{(0,8),(8,1)},[0,1],1,1,False),
      ('unrelated_alien',{0,1,8,9},{(0,8),(9,1)},[0,1],1,0,True),
      ('last_exit_wins',{0,1,2,3,8,9},{(0,8),(8,1),(2,9),(9,3)},[0,1,2,3],3,3,False),
      ('direct_then_cross',{0,1,2,8},{(0,1),(1,8),(8,2)},[0,1,2],2,2,False),
    ]
    report=[]
    for name,n,e,w,r,want,whole_ok in cases:
        got,_,_=cutoff(n,e,w,r)
        if got!=want or acyclic_contraction(n,e,set(w))!=whole_ok: raise AssertionError(name)
        for L in range(r+1):
            if acyclic_contraction(n,e,set(w[L:r+1]))!=(L>=got):raise AssertionError((name,L))
        report.append({'name':name,'cutoff':got,'whole_contraction_acyclic':whole_ok})
    return report

def main():
    start=time.monotonic(); toys=toy_tests()
    g,p,prepared,trace=[read(x) for x in ('graph','plan','prepared','p3')]
    ops={o['id']:o for o in g['ops']}; tensors={t['id']:t for t in g['tensors']}
    compute={u for u,o in ops.items() if not o['op'].startswith('COPY')}
    prod=defaultdict(set); cons=defaultdict(set); edges=set()
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a in ops and b in tensors:prod[b].add(a)
        elif a in tensors and b in ops:cons[a].add(b)
        elif a in ops and b in ops:edges.add((a,b))
        else:raise ValueError(f'unrecognized raw edge {e}')
    for t in tensors:edges.update((u,v) for u in prod[t] for v in cons[t])
    if topo(set(ops),edges) is None:raise ValueError('raw op DAG cyclic')
    mapping={int(u):sg for u,sg in p['node_to_subgraph'].items()}; schedules=p['core_schedules']
    if set(mapping)!=compute or len(mapping)!=len(set(mapping.values())):raise ValueError('base singleton coverage')
    sg_owner={sg:c for c,w in enumerate(schedules) for sg in w}
    if set(sg_owner)!=set(mapping.values()) or len(schedules)!=5:raise ValueError('base schedule coverage')
    word=[next(u for u,sg in mapping.items() if sg==s) for s in schedules[0]]
    index={u:i for i,u in enumerate(word)}
    rank={u:(sg_owner[mapping[u]],schedules[sg_owner[mapping[u]]].index(mapping[u])) for u in compute}
    for u,v in edges:
        if u in compute and v in compute and rank[u][0]==rank[v][0] and rank[u][1]>rank[v][1]:
            raise ValueError('base same-core order invalid')
    key=1000000048; target=1289
    task=prepared['task_return'][0]['0']
    if key not in task['in_tids'][str(target)]:raise ValueError('pilot consumer evidence differs')
    if not any(e.get('tensor_id')==key and e.get('event')=='miss' and e.get('core_id')==0 for e in trace['cache_events']):
        raise ValueError('pilot miss evidence differs')
    r=index[target]
    L,reentry,witness=cutoff(set(ops),edges,word,r)
    if L>r:raise ValueError('cutoff exceeds consumer')
    span=word[L:r+1]
    if len(span)<2:raise ValueError('only singleton safe; no merge candidate')
    candidate_map=dict(mapping); anchor=mapping[span[0]]
    for u in span:candidate_map[u]=anchor
    candidate_schedule=[list(w) for w in schedules]; removed={mapping[u] for u in span[1:]}
    candidate_schedule[0]=[sg for sg in schedules[0] if sg not in removed]
    if set(candidate_map)!=compute or set(candidate_map.values())!={sg for w in candidate_schedule for sg in w}:
        raise ValueError('candidate coverage differs')
    # Full original op arcs, including COPY operations as separate quotient vertices.
    tag=lambda u:('sg',candidate_map[u]) if u in compute else ('copy',u)
    qnodes={tag(u) for u in ops};qedges={(tag(u),tag(v)) for u,v in edges if tag(u)!=tag(v)}
    if topo(qnodes,qedges) is None:raise ValueError('explicit full-op quotient cyclic')
    if not acyclic_contraction(set(ops),edges,set(span)):raise ValueError('single-set contraction cyclic')
    out={'schema':'convex-pilot-cut-v1','source_head':'2c1e12ac','input_sha256':{k:v[1] for k,v in FILES.items()},
      'toy_cases':toys,'pilot_key':key,'consumer':target,'core':0,'consumer_rank':r,
      'earliest_safe_start':L,'merged_ops':len(span),'span_first_op':span[0],'span_last_op':span[-1],
      'max_exit_before_cut':L-1,'reentry_count_through_rank':sum(j<=r for j in reentry),
      'last_obstruction_witness':witness.get(next((j for j,i in reentry.items() if i==L-1 and j<=r),-1)),
      'raw_ops':len(ops),'raw_op_arcs':len(edges),'quotient_vertices':len(qnodes),'quotient_arcs':len(qedges),
      'explicit_full_op_quotient_acyclic':True,'elapsed_seconds':time.monotonic()-start,
      'limitations':'No official Task/Step/E0 run. No raw Step1 sequence, so COPY issue order is unknown; singleton capacity theorem does not apply to multi-op SG.'}
    (OUT/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n')
    plan={'node_to_subgraph':{str(u):candidate_map[u] for u in sorted(candidate_map)},'core_schedules':candidate_schedule}
    (OUT/'CANDIDATE_UNVALIDATED.json').write_text(json.dumps(plan,indent=2)+'\n')

if __name__=='__main__':main()
