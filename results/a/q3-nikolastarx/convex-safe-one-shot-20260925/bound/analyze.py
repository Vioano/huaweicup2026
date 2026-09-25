import gzip,json,hashlib
from pathlib import Path
from src.q3.static_task_bound import analyze
root=Path.cwd();b=Path(__file__).parent
def pinned(rel,h):
 p=root/rel;v=p.read_bytes();assert hashlib.sha256(v).hexdigest()==h
 return json.loads(gzip.decompress(v) if p.suffix=='.gz' else v)
x=pinned('results/a/q3-nikolastarx/layered-one-shot-20260925/run/prepared.json.gz','91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44')
word=pinned('results/a/q3-nikolastarx/convex-safe-sequence-guard-20260925/candidate_seq.json','21d235d23884039f0f14f00890f72360ce0d43789aae48edff694a6ab2132d52')
tasks={}
for c in range(5):
 t=x['task_return'][0][str(c)];s=x['step2'][c]
 assert not any(s.get(k) for k in ('spill_records','new_ops','new_tensors','new_edges','removed_edges','overflow_log'))
 g=dict(t['graph']);g['edges']=s['ext_edges']
 tasks[c]={'graph':g,'pre_step2_word':word if c==0 else t['seq']}
r=analyze(tasks,x['task_return'][1],capacity=x['capacity'],ddr_bandwidth=60,cache_bandwidth=250,cross_core_delay_cycles=500)
r['binding_scope']='same no-spill Task identity; changed core0 pure stable sort, other cores unchanged; new actual preparation unverified'
(b/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'lower_bound_cycles':r['lower_bound_cycles'],'official_calls':0}))
