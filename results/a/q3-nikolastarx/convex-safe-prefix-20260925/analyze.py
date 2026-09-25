"""One read-only frozen sequence-difference diagnostic; no evaluator."""
import gzip,json,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
F={'prepared':('layered-one-shot-20260925/run/prepared.json.gz','91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44'),'seq':('convex-safe-sequence-guard-20260925/candidate_seq.json','21d235d23884039f0f14f00890f72360ce0d43789aae48edff694a6ab2132d52')}
def read(k):
 p,h=F[k];r=(B/p).read_bytes();assert hashlib.sha256(r).hexdigest()==h
 return json.loads(gzip.decompress(r) if p.endswith('.gz') else r)
def diff(a,b):
 return {'identical':a==b,'lengths':[len(a),len(b)],'first_difference':next(({'index':i,'old':u,'new':v} for i,(u,v) in enumerate(zip(a,b)) if u!=v),None)}
p=read('prepared');t=p['task_return'][0]['0'];old=t['seq'];new=read('seq')
assert isinstance(new,list) and set(new)==set(old) and len(new)==len(old)
ops={o['id']:o for o in t['graph']['ops']};tids={x['id']:x for x in t['graph']['tensors']};managed={e['source'] for e in p['step2'][0]['ext_edges'] if e['source'] in ops and e['target'] in tids and tids[e['target']]['pos'] in ('L1','UB')}
out={'new_official_calls':0,'inputs':{k:v[1] for k,v in F.items()},'seq':diff(old,new),'pipes':{}}
for pipe in sorted({o['pipe'] for o in ops.values()}):
 a=[u for u in old if ops[u]['pipe']==pipe];b=[u for u in new if ops[u]['pipe']==pipe];out['pipes'][pipe]=diff(a,b)
a=[u for u in old if u in managed];b=[u for u in new if u in managed];target=1000004471
out['allocation']=diff(a,b);out['allocation']['target_ranks']=[a.index(target),b.index(target)];out['allocation']['through_target_prefix_equal']=a[:a.index(target)+1]==b[:b.index(target)+1]
out['changed_adjacent_edges']={}
for pipe in sorted({o['pipe'] for o in ops.values()}):
 a=[u for u in old if ops[u]['pipe']==pipe];b=[u for u in new if ops[u]['pipe']==pipe];ea=set(zip(a,a[1:]));eb=set(zip(b,b[1:]));out['changed_adjacent_edges'][pipe]={'removed':sorted(ea-eb),'added':sorted(eb-ea)}
(O/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='changed_adjacent_edges'}))
