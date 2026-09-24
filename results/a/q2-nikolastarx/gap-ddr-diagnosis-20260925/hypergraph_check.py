#!/usr/bin/env python3
"""Independent static hyperedge recount and move-delta identity check."""
import sys
sys.dont_write_bytecode=True
import gzip,hashlib,json,random,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
PILOT='a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075'
def blob(rev,path): return subprocess.check_output(['git','-C',str(ROOT),'show',f'{rev}:{path}'])
def sha(b): return hashlib.sha256(b).hexdigest()
def jsonblob(rev,path): return json.loads(blob(rev,path))
def load_ref(x):
 b=blob(x['commit'],x['path'])
 if sha(b)!=x['sha256']: raise ValueError('pinned source hash mismatch: '+x['path'])
 return json.loads(gzip.decompress(b)) if x['path'].endswith('.gz') else json.loads(b)

def hyper_count(graph,plan):
 from src.q2_nikolastarx.direct import derive_multicore_plan
 from multicore_cut_evaluate_problem_1 import _original_tensor_views
 v=derive_multicore_plan(graph,plan); mp=v['mapping']; owner=v['core_by_subgraph']; core={op:owner[sg] for op,sg in mp.items()}
 producers,consumers,direct=_original_tensor_views(graph); op_by={o['id']:o for o in graph['ops']}
 out={'boundary_input':0,'boundary_output':0,'cross_tensor':0,'cross_direct':0}; cross=[]; multi_source=[]
 for t in graph['tensors']:
  tid,s=t['id'],t['size']; ps={o for o in producers.get(tid,()) if o in mp}; cs={o for o in consumers.get(tid,()) if o in mp}
  pc={core[o] for o in ps}; cc={core[o] for o in cs}
  if cc and not pc: # input hyperedge on consumer pins, s*lambda
   out['boundary_input']+=s*len(cc)
  original_out=any(op_by[o].get('op')=='COPY_OUT' for o in consumers.get(tid,()) if o in op_by)
  if pc and (original_out or not cc): # output hyperedge; singleton source is constant s
   out['boundary_output']+=s*len(pc)
  if pc and cc:
   pairs=[(a,b) for a in pc for b in cc if a!=b]
   bytes_=2*s*len(pairs); out['cross_tensor']+=bytes_
   if len(ps)==1:
    lam=len(pc|cc); h=2*s*max(0,lam-1)
    if h!=bytes_: raise ValueError(f'unique-producer hyperedge mismatch tensor {tid}')
   elif len(ps)>1: multi_source.append({'tensor_id':tid,'eligible_producer_count':len(ps),'producer_core_count':len(pc),'consumer_core_count':len(cc)})
   for a,b in pairs: cross.append({'tensor_id':tid,'src_core':a,'dst_core':b,'size_bytes':s,'copy_transfer_bytes':2*s})
 for e in direct:
  a,b=e['source'],e['target']
  if a in mp and b in mp and core[a]!=core[b]:
   s=e.get('data_size',0); out['cross_direct']+=2*s; cross.append({'direct_edge':[a,b],'src_core':core[a],'dst_core':core[b],'size_bytes':s,'copy_transfer_bytes':2*s})
 return out,cross,multi_source

def synthetic(seed=20260925,trials=2000):
 rng=random.Random(seed); checks=0
 for _ in range(trials):
  n=rng.randint(3,10); cores=[rng.randrange(4) for _ in range(n)]
  a=rng.choice(cores); U={i for i,c in enumerate(cores) if c==a and rng.random()<.7}
  if not U: U={cores.index(a)}
  b=rng.choice([c for c in range(4) if c!=a]); edges=[]
  for j in range(rng.randint(1,10)):
   typ=rng.choice(('unique_producer_tensor','external_input','fixed_output','direct'))
   pins=set(rng.sample(range(n),2 if typ=='direct' else rng.randint(1,min(n,6))))
   weight=rng.randint(1,20)*2
   edges.append((typ,pins,weight))
  for typ,pins,w in edges:
   if not pins & U: continue
   oldcores={cores[i] for i in pins}; after=list(cores)
   for i in U: after[i]=b
   newcores={after[i] for i in pins}
   if typ=='fixed_output': oldcost=newcost=w; expected=0
   else:
    offset=0 if typ=='external_input' else 1
    oldcost=w*(len(oldcores)-offset); newcost=w*(len(newcores)-offset)
    na=sum(1 for i in pins if cores[i]==a); nb=sum(1 for i in pins if cores[i]==b); ui=len(pins&U)
    expected=w*((1 if nb==0 else 0)-(1 if na==ui else 0))
   if newcost-oldcost!=expected: raise ValueError(f'move delta mismatch: {typ},{pins},{U},{a}->{b}')
   checks+=1
 return {'seed':seed,'trials':trials,'incident_hyperedge_checks':checks,'mismatches':0}

def main():
 for source_path in ('src/q2_nikolastarx/candidate_ddr.py', 'src/q2_nikolastarx/direct.py', 'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py'):
  if (ROOT/source_path).read_bytes()!=blob(PILOT,source_path): raise ValueError('Static counter source drift: '+source_path)
 from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
 pilot=f'results/a/q2-nikolastarx/gap-solver-pilot-20260925/'
 mraw=blob(PILOT,pilot+'manifest.json'); m=json.loads(mraw); ar=jsonblob(PILOT,pilot+'archive-manifest.json'); archived={x['archive_path']:x for x in ar['files']}
 cells=[]
 for r in m['rows']:
  case=r['case']; k=r['cores']; d=pilot+f'run/{case}-k{k}/'; gb=(ROOT/r['graph']['path']).read_bytes()
  if sha(gb)!=r['graph']['sha256']: raise ValueError('graph hash mismatch '+case)
  graph=json.loads(gb); oldplan=load_ref(r['baseline_plan']); oldtruth=load_ref(r['baseline_truth'])
  newplan_path=d+'plan.json.gz'; newtruth_path=d+'result.json.gz'
  npz=blob(PILOT,newplan_path); nrz=blob(PILOT,newtruth_path)
  for p,b in ((newplan_path,npz),(newtruth_path,nrz)):
   if p not in archived or sha(b)!=archived[p]['stored_sha256']: raise ValueError('archive hash mismatch '+p)
  plan=json.loads(gzip.decompress(npz)); truth=json.loads(gzip.decompress(nrz))
  if sha(gzip.decompress(npz))!=archived[newplan_path]['original_sha256'] or sha(gzip.decompress(nrz))!=archived[newtruth_path]['original_sha256']: raise ValueError('archive roundtrip mismatch '+case)
  for label,p,t in (('old',oldplan,oldtruth),('new',plan,truth)):
   model,cross,multi=hyper_count(graph,p); api=mandatory_copy_work(graph,p,60)
   api_cat={q:api['categories'][q]['transfer_bytes'] for q in model}
   if model!=api_cat or sum(model.values())!=api['transfer_bytes']: raise ValueError(f'hypergraph/API byte mismatch {case}/{label}: {model} vs {api_cat}')
   mv=t['data_movement_bytes']
   if mv['spill_added_copy_bytes']!=0 or api['transfer_bytes']!=mv['scheduled_copy_bytes']: raise ValueError(f'E0 COPY byte mismatch/nonzero spill {case}/{label}')
   cells.append({'case':case,'cores':k,'version':label,'sha256':{'graph':sha(gb),'plan':sha(gzip.decompress(npz)) if label=='new' else sha(blob(r['baseline_plan']['commit'],r['baseline_plan']['path'])),'truth':sha(nrz) if label=='new' else sha(blob(r['baseline_truth']['commit'],r['baseline_truth']['path']))},'category_copy_bytes':model,'hypergraph_equals_mandatory_copy_work':True,'mandatory_transfer_bytes':api['transfer_bytes'],'E0_scheduled_copy_bytes':mv['scheduled_copy_bytes'],'zero_spill':True,'cross_tensor_pair_count':sum(1 for x in cross if 'tensor_id' in x),'multi_source_tensor_count':len(multi)})
  # Save pair-level rows for the selected new plan, adequate to reproduce diagnosis.
  if case in ('003','005','056'):
   _,cross,_=hyper_count(graph,plan)
   cc=[x for x in cross if 'tensor_id' in x]; cc.sort(key=lambda x:(-x['copy_transfer_bytes'],x['tensor_id'],x['src_core'],x['dst_core']))
   # Full edge inventory is bounded by four selected plans and aids localized placement review.
   for cell in cells[-1:]:
    if cell['case']==case and cell['version']=='new': cell['top_cross_tensor_pairs']=cc[:10]
 res={'pilot_commit':PILOT,'manifest_sha256':sha(mraw),'api':'candidate_ddr.mandatory_copy_work(graph,plan,60)','api_source_sha256':sha(blob(PILOT,'src/q2_nikolastarx/candidate_ddr.py')),'fixed_commit_checks':cells,'synthetic_move_identity':synthetic(),'move_identity':'For incident hyperedge t and nonempty same-core U moved a→b, Δλ=1[n_t(b)=0]−1[n_t(a)=|t∩U|]. Cost delta is weight*Δλ for λ or λ−1 edges; fixed singleton output cost s has delta zero. Producer is included as a pin; direct edges are two-pin hyperedges.','placement_note':'Changing only within-core order preserves every op-to-core assignment and therefore all original pre-Step2 COPY bytes counted here; it does not guarantee unchanged Makespan, spill behavior, or added Step2 traffic.','scope_note':'Exact original COPY bytes before Step2; service_work is a separate abstract count, not a Makespan guarantee.'}
 (OUT/'hypergraph-check.json').write_text(json.dumps(res,indent=2)+'\n')
 print(json.dumps({'rows':len(cells),'synthetic':res['synthetic_move_identity'],'all_equal':all(x['hypergraph_equals_mandatory_copy_work'] for x in cells)},ensure_ascii=False))
if __name__=='__main__': main()
