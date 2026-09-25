"""Synthetic counterexamples only. No official code or official graph execution."""
import json
from types import SimpleNamespace
import r9_static_core as r9
from row_recognizer_frozen import _ports

def graph():
    ops=[];tensors=[];edges=[]
    for branch in range(2):
        for stage,size in enumerate((4,4,1)):
            op=1+branch*3+stage;tid=100+op
            ops.append({'id':op,'op':'REDUCE' if stage==2 else 'RELU','pipe':'PIPE_V','cycles':1})
            tensors.append({'id':tid,'pos':'UB','size':size})
            edges.append({'source':op,'target':tid})
            if stage:edges.append({'source':tid-1,'target':op})
    return {'ops':ops,'tensors':tensors,'edges':edges}

ix=r9.RawIndex.build(graph());p=_ports(ix);owner={u:0 for u in ix.ops}
a,_=r9.interval_certificate(ix,p,owner,[[1,4,2,5,3,6]],{'UB':8,'L1':8})
b,_=r9.interval_certificate(ix,p,owner,[[1,2,3,4,5,6]],{'UB':8,'L1':8})
assert a['bucket_frontier_peaks'][0]['UB']['bytes']==12 and not a['step2_no_spill_certificate']
assert b['bucket_frontier_peaks'][0]['UB']['bytes']==8 and b['step2_no_spill_certificate']
# Four compute ops: original A->B, C->D is acyclic; orders D,A / B,C create a cycle.
nodes={1,2,3,4};succ={1:{2},2:{3},3:{4},4:{1}}
try:r9.topo(nodes,succ)
except r9.GuardError:detected=True
else:detected=False
assert detected
# Compute-only load counterexample: four private 10-cycle jobs plus five auxiliary
# 10-cycle jobs. All auxiliary work on one core gives 50, whereas 2/2/2/2/1 gives 20.
assert max(10,10,10,10,50)>max(20,20,20,20,10)
print(json.dumps({'status':'SYNTHETIC_STATIC_ONLY','interleaved_UB':12,'component_contiguous_UB':8,
'capacity':8,'FIFO_cycle_detected':detected,'extra_core_overload_toy':{'all_aux_extra':50,'balanced':20},
'official_calls':0},indent=2))
