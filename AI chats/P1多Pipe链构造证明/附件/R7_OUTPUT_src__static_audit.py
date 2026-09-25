#!/usr/bin/env python3
"""R7 static witness audit only: reads an archive and saved records.

Never imports a constructor/compiler/evaluator. Never creates or emits a plan.
The four witness intervals are a declared object of static analysis, not a
parameter sweep. Ranks are analysis labels; all original input IDs are intact.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, Counter
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import zipfile

EXPECTED_ZIP = '6d461d4c092166363b211f45bbbf36c5627a51abe89ef491257b8cbd4b3a4a49'
COPY = {'COPY_IN', 'COPY_OUT'}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run(path: Path) -> dict:
    raw = path.read_bytes()
    if sha(raw) != EXPECTED_ZIP:
        raise ValueError('This witness audit requires the exact R7 input packet')
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('MANIFEST.json'))
        for item in manifest['files']:
            b = z.read(item['path'])
            if len(b) != item['bytes'] or sha(b) != item['sha256']:
                raise ValueError('Payload mismatch: ' + item['path'])
        files = {name: z.read(name) for name in z.namelist()}
    g = json.loads(files['case044/case_044.json'])
    ops = {o['id']: o for o in g['ops']}
    compute = {u:o for u,o in ops.items() if o['op'] not in COPY}
    tensors = {t['id']:t for t in g['tensors']}
    ids = set(compute)
    prod, cons, ins, outs = (defaultdict(set) for _ in range(4))
    direct = []
    for e in g['edges']:
        a,b = e['source'],e['target']
        if a in ops and b in tensors:
            prod[b].add(a); outs[a].add(b)
        elif a in tensors and b in ops:
            cons[a].add(b); ins[b].add(a)
        else:
            direct.append((a,b))
    if any(len(prod[t]) > 1 for t in tensors):
        raise ValueError('Multiple producer')
    pred,succ = {u:set() for u in ids},{u:set() for u in ids}
    for t in tensors:
        for u in prod[t]&ids:
            for v in cons[t]&ids:
                pred[v].add(u);succ[u].add(v)
    for u,v in direct:
        if u in ids and v in ids:
            pred[v].add(u);succ[u].add(v)
    remaining = set(ids); components=[]
    while remaining:
        todo=[min(remaining)]; cc=set()
        while todo:
            u=todo.pop()
            if u in cc:continue
            cc.add(u);todo.extend((pred[u]|succ[u])-cc)
        remaining -= cc
        indeg={u:len(pred[u]&cc) for u in cc}
        ready=sorted(u for u in cc if not indeg[u]);heapq.heapify(ready)
        line=[]
        while ready:
            if len(ready)!=1:
                raise ValueError('Witness requires a unique spine topological order')
            u=heapq.heappop(ready);line.append(u)
            for v in sorted(succ[u]):
                indeg[v]-=1
                if not indeg[v]:heapq.heappush(ready,v)
        if len(line)!=len(cc):raise ValueError('Cycle')
        components.append(line)
    components.sort(key=min)
    component_of={u:i for i,c in enumerate(components) for u in c}
    ext={t for t in tensors if cons[t]&ids and not prod[t]&ids}
    shared={t for t in ext if len({component_of[u] for u in cons[t]&ids})>1}
    # Guard standard external DDR -> COPY_IN paths, and original terminal COPY_OUT.
    for t in ext:
        if len(prod[t])!=1 or ops[next(iter(prod[t]))]['op']!='COPY_IN':
            raise ValueError('Nonstandard external input')
    for u,o in ops.items():
        if o['op']=='COPY_IN':
            if any(prod[t]&ids for t in ins[u]):raise ValueError('COPY bridge')
        if o['op']=='COPY_OUT':
            if any(cons[t]&ids for t in outs[u]):raise ValueError('COPY bridge')
    if any(o['pipe']=='PIPE_M' and len(ins[u]&shared)!=1 for u,o in compute.items()):
        raise ValueError('M serialization witness requires one common-input column per M op')
    if not all(len(cons[t]&ids)==len(components) for t in shared):
        raise ValueError('Not one shared consumer per component')
    patterns=[]
    for c in components:
        cset=set(c);rank={u:i for i,u in enumerate(c)}
        touched=set().union(*(ins[u]|outs[u] for u in c))
        pattern=(tuple((compute[u]['op'],compute[u]['pipe'],compute[u]['cycles']) for u in c),
          tuple(sorted((rank[u],rank[v]) for u in c for v in succ[u])),
          tuple(sorted((tensors[t]['pos'],tensors[t]['size'],
                        tuple(sorted(rank[u] for u in prod[t]&cset)),
                        tuple(sorted(rank[u] for u in cons[t]&cset)),
                        t if t in shared else -1) for t in touched)))
        patterns.append(pattern)
    if any(p != patterns[0] for p in patterns):raise ValueError('Different component patterns')
    first=components[0]; n=len(components); k=5; h=(n+k-1)//k; m=(n+h-1)//h
    def work(nodes):
        return {p:sum(max(1,compute[u]['cycles']) for u in nodes if compute[u]['pipe']==p)
                for p in ('PIPE_M','PIPE_V')}
    def service(t):return max(1,(tensors[t]['size']+59)//60)
    def touched(nodes):return set().union(*(ins[u]|outs[u] for u in nodes)) if nodes else set()
    def footprint(a,b,count):
        ns=[u for c in components[:count] for u in c[a:b]]
        return {p:sum(tensors[t]['size'] for t in touched(ns)
                    if ('UB' if tensors[t]['pos']=='DDR' else tensors[t]['pos'])==p)
                for p in ('L1','UB')}
    read_ranks=[i for i,u in enumerate(first) if ins[u]&shared]
    columns=[]
    for j,a in enumerate(read_ranks):
        b=read_ranks[j+1] if j+1<len(read_ranks) else len(first)
        ns=first[a:b]; st=set().union(*(ins[u]&shared for u in ns))
        u=sum(work(ns).values()); d=sum(service(t) for t in st)
        pooled=max(n*u,d); replicated=max(h*u,m*d)
        columns.append(dict(start_rank=a,end_rank_exclusive=b,shared_tensors=sorted(st),
          shared_bytes=sum(tensors[t]['size'] for t in st),service=d,serial_compute=u,
          pooled_proxy=pooled,replicated_proxy=replicated,pool_proxy_preferred=pooled<replicated))
    # The declared four-interval witness. This is not a node-to-Task map.
    regions=[('prefix',0,48,m,h),('pool_A',48,65,1,n),
             ('pool_B',65,75,1,n),('suffix',75,124,m,h)]
    if [r['start_rank'] for r in columns if r['pool_proxy_preferred']] != [48,50,52,55,57,60,62,65,67,70,72]:
        raise ValueError('Witness no longer matches the stated input-driven proxy rule')
    phase_of={u:name for name,a,b,_,_ in regions for u in first[a:b]}
    phase_stats={}
    for name,a,b,rep,members in regions:
        st={t for u in first[a:b] for t in ins[u]&shared}
        phase_stats[name]=dict(start_rank=a,end_rank_exclusive=b,representative_original_ops=first[a:b],
          per_component_work=work(first[a:b]),replication=rep,max_components_per_task=members,
          footprint_max=footprint(a,b,members),shared_unique_bytes=sum(tensors[t]['size'] for t in st),
          shared_unique_service=sum(service(t) for t in st),copy_bytes=rep*sum(tensors[t]['size'] for t in st),
          copy_service=rep*sum(service(t) for t in st))
    if footprint(48,67,n)['L1'] <= 524288:
        raise ValueError('Greedy pool cut witness inconsistent')
    cset=set(first); boundary=[]
    for t in tensors:
        cp=prod[t]&cset; cc=cons[t]&cset
        if not cp:
            if t in ext-shared and cc:
                dest=phase_of[next(iter(cc))]
                phase_stats[dest]['copy_bytes'] += n*tensors[t]['size']
                phase_stats[dest]['copy_service'] += n*service(t)
            continue
        source=phase_of[next(iter(cp))]
        if not cc:
            phase_stats[source]['copy_bytes'] += n*tensors[t]['size']
            phase_stats[source]['copy_service'] += n*service(t)
            continue
        targets={phase_of[u] for u in cc}-{source}
        if targets:
            row=dict(representative_tensor_id=t,size=tensors[t]['size'],source=source,targets=sorted(targets),
              copies_per_component=1+len(targets),bytes_per_component=(1+len(targets))*tensors[t]['size'],
              service_per_component=(1+len(targets))*service(t))
            boundary.append(row)
            for ph in [source]+sorted(targets):
                phase_stats[ph]['copy_bytes'] += n*tensors[t]['size']
                phase_stats[ph]['copy_service'] += n*service(t)
    saved={}
    for tag in ('v4-k5','prior-k3'):
        plan=json.loads(files[tag+'/plan.json']) # read saved plan only
        result=json.loads(gzip.decompress(files[tag+'/result.json.gz']))
        trace=json.loads(gzip.decompress(files[tag+'/trace.json.gz']))
        mapping={int(u):task for u,task in plan['node_to_subgraph'].items()}
        owner={task:c for c,order in enumerate(plan['core_schedules']) for task in order}
        if any(len({owner[mapping[u]] for u in cc})!=1 for cc in components):
            raise ValueError('Saved plan no longer retains each component on one core')
        ext_mult=Counter()
        for t in ext:
            ext_mult[len({mapping[u] for u in cons[t]&ids})]+=tensors[t]['size']
        percore=[]
        for c in result['per_core_timeline']:
            sums={p:sum(op['duration'] for op in c['ops'] if op['pipe']==p)
                  for p in ('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3')}
            trace_sums=Counter()
            for e in trace['traceEvents']:
                if e.get('ph')=='X' and e.get('args',{}).get('core_id')==c['core_id'] and e.get('cat','').startswith('PIPE_'):
                    trace_sums[e['cat']]+=e['dur']
            if any(trace_sums[p]!=s for p,s in sums.items()):raise ValueError('Trace/result mismatch')
            percore.append(dict(core=c['core_id'],tasks=c['tasks'],pipe_duration_sums=sums,
               component_count=sum(owner[mapping[cc[0]]]==c['core_id'] for cc in components),
               task_interval_sum=sum(t['duration'] for t in c['tasks'])))
        saved[tag]=dict(makespan=result['makespan'],movement=result['data_movement_bytes'],
          memory_peak_by_core=result['memory_peak_by_core'],task_dependencies=result['task_dependencies'],
          external_bytes_by_task_count=dict(ext_mult),per_core=percore,
          compressed_result_sha256=sha(files[tag+'/result.json.gz']),
          result_sha256=sha(gzip.decompress(files[tag+'/result.json.gz'])))
    d_shared=sum(service(t) for t in shared)
    d_other=sum(service(t) for t in ext-shared)+sum(service(t) for t in tensors if prod[t]&ids and not cons[t]&ids)
    serial_upper=phase_lower=2100
    for name,_,_,_,_ in regions:
        st=phase_stats[name]; w=st['per_component_work']; count=st['max_components_per_task']
        st['stage_lower_no_gates']=max(count*max(w.values()),st['copy_service'])
        st['stage_serial_service_upper_no_gates']=count*sum(w.values())+st['copy_service']
        serial_upper+=st['stage_serial_service_upper_no_gates'];phase_lower+=st['stage_lower_no_gates']
    total_bytes=sum(st['copy_bytes'] for st in phase_stats.values())
    return dict(kind='static graph/saved-record/witness analysis; NOT a constructed or evaluated plan',
      input=dict(zip_sha256=sha(raw),zip_bytes=len(raw),entries=len(files),verified_manifest_payloads=len(manifest['files']),
                 graph_sha256=sha(files['case044/case_044.json'])),
      graph=dict(components=n,component_compute_ops=len(first),component_work=work(first),
                 unique_spine_and_aligned_patterns=True,all_tensor_producers_unique=True,
                 shared_input_tensors=len(shared),shared_input_bytes=sum(tensors[t]['size'] for t in shared),
                 private_input_bytes=sum(tensors[t]['size'] for t in ext-shared),
                 all_shared_inputs_have_one_consumer_per_component=True),
      saved=saved,
      witness=dict(rank_origin='zero-based rank in each ORIGINAL unique compute spine; not changed IDs',
         core_budget=k,cohort_size_cap=h,peripheral_cohorts=m,pooled_owner='one otherwise unused core',
         columns=columns,regions=phase_stats,interfaces=boundary,
         predicted_task_count_by_definition=2*m+2,
         proven_unspilled_boundary_bytes=total_bytes,
         added_boundary_bytes_vs_original=total_bytes-saved['v4-k5']['movement']['original_graph_copy_bytes'],
         needed_copy_service=sum(st['copy_service'] for st in phase_stats.values()),
         no_spill_no_MEM='Sufficient total-managed-footprint theorem only; no compiler validation executed',
         mathematical_time_envelope=dict(lower=phase_lower,upper=serial_upper,
             scope='Fixed declared partition in exact work-conserving DDR service model; NOT E0/model replay or timing prediction')),
      bounds=dict(shared_once_service=d_shared,necessary_private_input_output_service=d_other,
          global_resource_lower=max((sum(o['cycles'] for o in compute.values() if o['pipe']=='PIPE_M')+k-1)//k,d_shared+d_other),
          component_to_single_core_replication_service={str(a):a*d_shared+d_other for a in range(1,k+1)},
          all_shared_consumers_coalesced_M_serial_lower=sum(o['cycles'] for o in compute.values() if o['pipe']=='PIPE_M')),
      calls=dict(new_plan_generators=0,new_plans=0,Task_compiles=0,response=0,E0=0,E1=0,E2=0))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet',type=Path);parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    if a.output.exists():raise FileExistsError('Refuse overwrite')
    data=run(a.packet)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'kind':data['kind'],'graph':data['graph'],'witness_boundary_bytes':data['witness']['proven_unspilled_boundary_bytes'],'bounds':data['bounds'],'calls':data['calls']},ensure_ascii=False))
