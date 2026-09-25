#!/usr/bin/env python3
"""Independently check a singleton plan using raw incidences. No Task/Step/E0."""
import argparse
from collections import Counter
import json
from pathlib import Path
import r9_static_core as r9
from row_recognizer_frozen import _ports


def verify(graph, plan):
    assert set(plan)=={'node_to_subgraph','core_schedules'}
    ix=r9.RawIndex.build(graph);p=_ports(ix)
    mp={int(u):v for u,v in plan['node_to_subgraph'].items()}
    assert len(mp)==len(plan['node_to_subgraph']) and set(mp)==set(ix.ops)
    assert all(type(v)is int and v>=0 for v in mp.values())
    assert len(set(mp.values()))==len(mp),'singleton only'
    inv={v:u for u,v in mp.items()}
    flat=[v for w in plan['core_schedules'] for v in w]
    assert len(flat)==len(set(flat))==len(mp) and set(flat)==set(inv)
    words=[[inv[sg]for sg in w]for w in plan['core_schedules']]
    successors={u:set(ix.succ[u])for u in ix.ops}
    for w in words:
        for u,v in zip(w,w[1:]):successors[u].add(v)
    tau=r9.topo(ix.ops,successors)
    out=[]
    for w in words:
        inc={u:set(p.inputs[u])|set(p.outputs[u])for u in w}
        remain=Counter(t for u in w for t in inc[u]);active=set();used=Counter()
        peak={'L1':0,'UB':0};arg={}
        for j,u in enumerate(w):
            for t in inc[u]-active:
                active.add(t);pool=p.tensors[t]['pos'];pool='UB' if pool=='DDR' else pool
                used[pool]+=p.tensors[t]['size']
            for pool in peak:
                if used[pool]>peak[pool]:peak[pool]=used[pool];arg[pool]={'bucket':j,'op':u}
            for t in inc[u]:
                remain[t]-=1
                if remain[t]==0:
                    active.remove(t);pool=p.tensors[t]['pos'];pool='UB' if pool=='DDR' else pool
                    used[pool]-=p.tensors[t]['size']
        assert not active and not any(used.values())
        out.append({'peaks':peak,'arguments':arg})
    return {'static_only':True,'official_calls':0,'compute_ops':len(ix.ops),
            'coverage_and_original_DAG_plus_full_core_words_acyclic':True,
            'independent_incidence_frontier':out,'M2':None,'M3':None,'G':None}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True)
    a=ap.parse_args();print(json.dumps(verify(json.loads(a.graph.read_text()),json.loads(a.plan.read_text())),indent=2))
