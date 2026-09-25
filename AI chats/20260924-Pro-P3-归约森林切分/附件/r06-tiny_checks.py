"""Hand-checkable original two-job graph and exact supplied raw words.
No official builder or evaluator is run by this file.
"""
import json,pathlib
from prefix_bucket import construct, GuardFailure
H=pathlib.Path(__file__).resolve().parent

def op(u,kind,w=1,pipe='PIPE_M'):return {'id':u,'op':kind,'pipe':pipe,'cycles':w}
def tensor(t,s=60,pos='L1'):return {'id':t,'size':s,'pos':pos}
def graph(ops,tensors,edges):return {'ops':ops,'tensors':tensors,'edges':[{'source':u,'target':v} for u,v in edges]}
commonops=[op(10,'MATMUL',2000),op(11,'RELU',100,'PIPE_V'),op(12,'ADD',100,'PIPE_V'),op(20,'MATMUL',2000),op(21,'RELU',100,'PIPE_V'),op(22,'ADD',100,'PIPE_V')]
tensors=[tensor(100),tensor(102,60000)]+[tensor(t) for t in (110,111,112,120,121,122)]+[tensor(t,60,'DDR') for t in (500,512,522)]+[tensor(502,60000,'DDR')]
edges=[(500,1),(1,100),(502,2),(2,102),(100,10),(100,20),(10,110),(110,11),(11,111),(111,12),(102,12),(12,112),(112,3),(3,512),(20,120),(120,21),(21,121),(121,22),(102,22),(22,122),(122,4),(4,522)]
g=graph(commonops+[op(1,'COPY_IN',pipe='PIPE_MTE2'),op(2,'COPY_IN',pipe='PIPE_MTE2'),op(3,'COPY_OUT',pipe='PIPE_MTE3'),op(4,'COPY_OUT',pipe='PIPE_MTE3')],tensors,edges)
map0={str(u):i for i,u in enumerate((10,11,12,20,21,22))};anchor={'node_to_subgraph':map0,'core_schedules':[[0,3],[1,2,4,5]]}
t0=graph([commonops[0],commonops[3],op(1000,'COPY_IN',pipe='PIPE_MTE2'),op(1010,'COPY_OUT',pipe='PIPE_MTE3'),op(1020,'COPY_OUT',pipe='PIPE_MTE3')],[tensor(100),tensor(110),tensor(120),tensor(500,60,'DDR'),tensor(510,60,'DDR'),tensor(520,60,'DDR')],[(500,1000),(1000,100),(100,10),(100,20),(10,110),(110,1010),(1010,510),(20,120),(120,1020),(1020,520)])
t1=graph([commonops[i] for i in (1,2,4,5)]+[op(u,'COPY_IN',pipe='PIPE_MTE2') for u in (1002,1110,1120)]+[op(u,'COPY_OUT',pipe='PIPE_MTE3') for u in (2012,2022)], [tensor(102,60000)]+[tensor(t) for t in (110,111,112,120,121,122)]+[tensor(t,60,'DDR') for t in (510,520,512,522)]+[tensor(502,60000,'DDR')],[(502,1002),(1002,102),(510,1110),(1110,110),(110,11),(11,111),(111,12),(102,12),(12,112),(112,2012),(2012,512),(520,1120),(1120,120),(120,21),(21,121),(121,22),(102,22),(22,122),(122,2022),(2022,522)])
tasks={0:{'graph':t0,'raw_seq':[1000,10,1010,20,1020]},1:{'graph':t1,'raw_seq':[1110,11,1002,12,2012,1120,21,22,2022]}}
links=[{'target_core':1,'target_copy_in_id':1110},{'target_core':1,'target_copy_in_id':1120}]
plan,cert=construct(g,anchor,[[10,11,12],[20,21,22]],[0,1,3],tasks,links)
assert cert['pilot']==1
assert cert['cores'][1]['prefix']==[1002]
assert cert['cores'][1]['pre_step2_word']==[1002,1120,21,22,2022,1110,11,12,2012]
# Capacity negative: all source constants fit, but activation/compute coexistence does not.
try:
 construct(g,anchor,[[10,11,12],[20,21,22]],[0,1,3],tasks,links,{'L1':60060,'UB':131072})
except GuardFailure:cap_rejected=True
else:raise AssertionError('capacity negative was not rejected')
# Exogenous activation-release model; these are not official graph scores.
rows=[]
for R,x,L in ((2000,100,1000),(0,100,1000),(2000,1200,1000)):
 d=y=1
 old=R+d+max(x,L)+y;new=max(R,L)+d+x+y
 assert old-new==min(R,L)-min(x,L)
 rows.append({'R':R,'local_prefix_compute':x,'cold_load':L,'old_tail_completion':old,'new_tail_completion':new,'gain':old-new})
record={'scope':'supplied raw-word bucket algebra and exogenous-release arithmetic only','official_calls':0,'candidate':plan,'certificate':cert,'capacity_negative_rejected':cap_rejected,'timing_examples':rows}
(H/'tiny_certificate.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'new_raw_projection':cert['cores'][1]['pre_step2_word'],'capacity_negative_rejected':cap_rejected,'timing_examples':rows},indent=2))
