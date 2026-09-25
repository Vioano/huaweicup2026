#!/usr/bin/env python3
"""Small synthetic checks only. Never imports or invokes an official evaluator."""
from collections import defaultdict
from itertools import product
import json
from types import SimpleNamespace
import layered_affinity_r9 as r

def all_partitions(n,k):
    def rec(a,m):
        if len(a)==n:
            if m+1==k: yield a
            return
        for x in range(min(m+1,k-1)+1):
            yield from rec(a+[x],max(m,x))
    yield from rec([0],0)

def test_dp():
    checks=0
    for weights in [((5,2),(4,5),(2,4)), ((10,4),(9,5),(7,7),(5,10),(4,8)),
                    ((11,7),(11,7),(8,8),(7,9),(4,4),(3,5))]:
        n=len(weights);ops={};private={}
        for i,(a,b) in enumerate(weights):
            for j,w in enumerate((a,b)):
                u=2*i+j;ops[u]={'pipe':r.PIPES[j],'cycles':w};private[u]=i
        ix=SimpleNamespace(ops=ops,duration=lambda u:ops[u]['cycles'])
        for k in range(1,min(4,n)+1):
            groups,meta=r.partition_tracks(ix,private,n,k)
            truth=None
            for assignment in all_partitions(n,k):
                sums=[[sum(weights[i][p] for i in range(n) if assignment[i]==c) for p in range(2)] for c in range(k)]
                score=(max(max(s) for s in sums),sum(v*v for s in sums for v in s))
                truth=score if truth is None or score<truth else truth
            assert (meta['bottleneck_private_pipe_work'],meta['tie_break_sum_squared_pipe_work'])==truth
            checks+=1
    return checks

def test_four_crossings():
    # S(c1)->P0a(c0)->A0b(c1)->P1b(c1)->A1a(c0)->P2a(c0)->A2b(c1)
    n=7;owners=dict(enumerate([1,0,1,1,0,0,1]));ops={u:{'pipe':'PIPE_M','cycles':1} for u in range(n)}
    succ={u:({u+1} if u<n-1 else set()) for u in range(n)}
    ix=SimpleNamespace(ops=ops,succ=succ,duration=lambda u:1)
    words=[[u for u in range(n) if owners[u]==c] for c in range(2)]
    stats=r.path_stats(ix,owners,words,list(range(n)),500,True)
    assert stats['max_remote_edges']==4
    return {'nodes':n,'crossings':stats['max_remote_edges'],'weighted_chain':stats['Ldelta']}

def test_frontier():
    # Four one-byte intermediates on a linear chain. Capacity two.
    ops={u:{'pipe':'PIPE_M','cycles':1,'op':'ADD'} for u in range(4)}
    tensors={10+u:{'pos':'L1','size':1} for u in range(4)}
    inputs=defaultdict(set,{u:{9+u} for u in range(1,4)})
    outputs={u:{10+u} for u in range(4)}
    producer={10+u:u for u in range(4)}
    consumers=defaultdict(set,{10+u:{u+1} for u in range(3)})
    ports=SimpleNamespace(tensors=tensors,inputs=inputs,outputs=outputs,producer=producer,consumers=consumers)
    ix=SimpleNamespace(ops=ops)
    cert,_=r.interval_certificate(ix,ports,{u:0 for u in range(4)},[list(range(4))],{'L1':2,'UB':2})
    assert cert['step2_no_spill_certificate'] and not cert['union_guard_passes']
    assert cert['bucket_frontier_peaks'][0]['L1']['bytes']==2
    # Incorrect free-before-output allocation would predict one byte and admit C=1.
    cert1,_=r.interval_certificate(ix,ports,{u:0 for u in range(4)},[list(range(4))],{'L1':1,'UB':2})
    assert not cert1['step2_no_spill_certificate']
    return {'union_bytes':4,'correct_frontier_bytes':2,'capacity_one_rejected':True}

def test_non_markov_bypass():
    # Same current-layer owner, different owner of surviving x from layer zero.
    def remaining_cost(x_owner,current_owner,next_owner):
        return 500*int(x_owner!=next_owner)+500*int(current_owner!=next_owner)
    a=remaining_cost(0,0,0);b=remaining_cost(1,0,0)
    assert a!=b
    return {'identical_layer1_owner':0,'layer2_owner':0,'cost_x_from_core0':a,'cost_x_from_core1':b}

def test_cross_stream_join_rejected():
    ops={1:{'pipe':'PIPE_V','cycles':1},2:{'pipe':'PIPE_V','cycles':1},3:{'pipe':'PIPE_V','cycles':1},4:{'pipe':'PIPE_M','cycles':1}}
    pred={1:set(),2:set(),3:{1,2},4:{3}};succ={1:{3},2:{3},3:{4},4:set()}
    ix=SimpleNamespace(ops=ops,pred=pred,succ=succ,order=[1,2,3,4])
    labels={1:('A',0,10),2:('A',0,20),4:('P',1,30)}
    try:r.decompose(ix,labels,set())
    except r.GuardError as e:
        assert 'two keys' in str(e)
        return {'guard_rejects_shared_join':True,'error':str(e)}
    raise AssertionError('genuine shared join silently treated as private')

def test_direct_bridge():
    ix=SimpleNamespace(ops={1:{},2:{}},pred={1:set(),2:{1}},succ={1:{2},2:set()},order=[1,2])
    tracks,private,*_=r.decompose(ix,{1:('A',0,10),2:('P',1,20)},set())
    assert len(tracks)==1 and private[1]==private[2]
    return {'zero_interior_bridge_recognized':True}

if __name__=='__main__':
    print(json.dumps({'status':'passed','dp_exhaustive_cases':test_dp(),
                      'multi_layer_crossing':test_four_crossings(),'frontier':test_frontier(),
                      'bypass_state':test_non_markov_bypass(),'shared_join':test_cross_stream_join_rejected(),
                      'direct_bridge':test_direct_bridge(),'official_calls':0},indent=2))
