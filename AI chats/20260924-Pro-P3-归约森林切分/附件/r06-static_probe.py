"""Static COPY skeleton + Step1 only. No Step2, Step3, prepare, P2 or P3.
The skeleton function is extracted from the verified official builder before
its per-core scheduling loop. This is a diagnostic, not an evaluator.
"""
import ast, collections, copy, hashlib, heapq, importlib, json, pathlib, sys, zipfile
HERE=pathlib.Path(__file__).resolve().parent
ZIP=pathlib.Path('/mnt/data/通用神经网络处理器下的多核调度问题  附件.zip')
with zipfile.ZipFile(ZIP) as z:
    root=HERE/'_official_readonly'; root.mkdir(exist_ok=True)
    for name in z.namelist():
        if name.startswith('code/') and name.endswith('.py'):
            (root/pathlib.Path(name).name).write_bytes(z.read(name))
    raw=z.read('data/case_044.json')
assert hashlib.sha256(raw).hexdigest()=='9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e'
sys.path.insert(0,str(root))
mod=importlib.import_module('multicore_cut_evaluate_problem_3')
s1=importlib.import_module('schedule_step1')
source=(root/'multicore_cut_evaluate_problem_3.py').read_bytes()
assert hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()=='b98ceb4de58cd6767af67cd763c460c79562ac23'
parsed=ast.parse(source)
f=next(x for x in parsed.body if isinstance(x,ast.FunctionDef) and x.name=='_build_scene_b_tasks')
f=copy.deepcopy(f); f.name='static_copy_skeleton'
idx=next(i for i,x in enumerate(f.body) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tasks' for t in x.targets))
f.body=f.body[:idx]+[ast.Return(ast.Tuple(elts=[ast.Name(id=x,ctx=ast.Load()) for x in ('tasks_data','cross_links','plan_view')],ctx=ast.Load()))]
ns=dict(mod.__dict__)
exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),'<verified-prefix-only>','exec'),ns)

def views(g):
    ops={o['id']:o for o in g['ops']}; comp={u:o for u,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    t={x['id']:x for x in g['tensors']};prod=collections.defaultdict(set);cons=collections.defaultdict(set)
    ins=collections.defaultdict(set);out=collections.defaultdict(set)
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a in ops:prod[b].add(a);out[a].add(b)
        else:cons[a].add(b);ins[b].add(a)
    pred={u:set() for u in comp};succ={u:set() for u in comp}
    for tid in prod:
        for a in prod[tid]&comp.keys():
            for b in cons[tid]&comp.keys():pred[b].add(a);succ[a].add(b)
    order=[];degree={u:len(pred[u]) for u in comp};ready=[u for u in comp if not degree[u]];heapq.heapify(ready)
    while ready:
        u=heapq.heappop(ready);order.append(u)
        for v in succ[u]:
            degree[v]-=1
            if not degree[v]:heapq.heappush(ready,v)
    seen=set();jobs=[]
    for u in order:
        if u in seen:continue
        group={u};seen.add(u);stack=[u]
        while stack:
            v=stack.pop()
            for w in (pred[v]|succ[v])-seen:seen.add(w);group.add(w);stack.append(w)
        job=[v for v in order if v in group]
        assert all(v in succ[u] for u,v in zip(job,job[1:]))
        jobs.append(job)
    return ops,comp,t,prod,cons,ins,out,pred,succ,order,jobs

def interval_peak(g,word):
    pos={u:i for i,u in enumerate(word)};opids=set(pos);ends={};tensors={t['id']:t for t in g['tensors']}
    for edge in g['edges']:
        a,b=edge['source'],edge['target']
        if a in opids and b in tensors:u,tid=a,b
        elif b in opids and a in tensors:u,tid=b,a
        else:continue
        if tensors[tid]['pos']=='DDR':continue
        if tid not in ends:ends[tid]=[pos[u],pos[u]]
        else:ends[tid]=[min(ends[tid][0],pos[u]),max(ends[tid][1],pos[u])]
    events={p:[0]*(len(word)+1) for p in ('L1','UB')}
    for tid,(l,r) in ends.items():
        p=tensors[tid]['pos'];s=tensors[tid]['size'];events[p][l]+=s;events[p][r+1]-=s
    result={}
    for p,a in events.items():
        used=peak=0
        for x in a:used+=x;peak=max(peak,used)
        result[p]=peak
    return result

g=json.loads(raw);ops,comp,t,prod,cons,ins,out,pred,succ,order,jobs=views(g)
cuts=[0,24,51,68,96,124];k=5
mapping={str(u):i for i,u in enumerate(order)}
base={'node_to_subgraph':mapping,'core_schedules':[[mapping[str(u)] for job in jobs for u in job[l:r]] for l,r in zip(cuts,cuts[1:])]}
# Identify matching serialization, without claiming a saved file was downloaded.
serializations={}
for sort in (False,True):
    for newline in ('','\n'):
        text=json.dumps(base,sort_keys=sort,separators=(',',':'))+newline
        serializations[f'sort={sort},newline={bool(newline)}']=hashlib.sha256(text.encode()).hexdigest()
common=set.intersection(*[{tid for u in job for tid in ins[u] if not(prod[tid]&comp.keys())} for job in jobs])
# Explicitly one 5-core static Task/COPY skeleton, five Step1 calls.
data,links,pv=ns['static_copy_skeleton'](g,base,60,{'L1':524288,'UB':131072})
rawseq={};graphs={};gate_ids={c:collections.defaultdict(list) for c in range(k)}
for link in links:
    c=link['target_core'];cid=link['target_copy_in_id'];tid=link['tensor_id']
    cj={j for j,job in enumerate(jobs) if set(job)&cons[tid]&comp.keys()}
    assert len(cj)==1
    gate_ids[c][next(iter(cj))].append(cid)
commoncopies={}
records=[];valid=set(range(len(jobs)))
for c in range(k):
    d=data[c];graph={'ops':d['ops'],'tensors':list(d['tensors'].values()),'edges':d['edges']};graphs[c]=graph
    rawseq[c]=s1.step1_schedule(graph);rp={u:i for i,u in enumerate(rawseq[c])}
    cp=[]
    for e in d['edges']:
        if e['target'] in common and e['source'] not in comp:
            cp.append(e['source'])
    cp=sorted(set(cp),key=rp.get);commoncopies[c]=cp
    last=max((rp[u] for u in cp),default=-1)
    ok={j for j in range(len(jobs)) if c==0 or gate_ids[c][j] and last<min(rp[u] for u in gate_ids[c][j])}
    if c:valid &= ok
    records.append({'core':c,'common_copy_count':len(cp),'common_bytes':sum(t[e['target']]['size'] for e in d['edges'] if e['source'] in cp and e['target'] in common),'last_common_raw_rank':last,'valid_pilot_jobs':sorted(ok),'base_interval_peak':interval_peak(graph,mod._prioritize_task_seq(graph,rawseq[c],d['op_subgraph'],d['subgraph_order']))})
assert valid
pilot=min(valid,key=lambda j: min(jobs[j]));perm=[pilot]+[j for j in range(len(jobs)) if j!=pilot]
newmapping=dict(mapping);nextsg=max(mapping.values())+1
for c,(l,r) in enumerate(zip(cuts,cuts[1:])):
    if c:
        for u in jobs[pilot][l:r]:newmapping[str(u)]=nextsg
        nextsg+=1
schedules=[]
for c,(l,r) in enumerate(zip(cuts,cuts[1:])):
    word=[]
    for j in perm:
        for u in jobs[j][l:r]:
            sg=newmapping[str(u)]
            if not word or word[-1]!=sg:word.append(sg)
    assert len(word)==len(set(word));schedules.append(word)
proposal={'node_to_subgraph':newmapping,'core_schedules':schedules}
# Original plan validator only. No Step1 is rerun for the proposal.
newview=mod.derive_multicore_plan(g,proposal)
for c in range(k):
    ann={}
    _,_,tt,pp,cc,*_=views(graphs[c])
    for o in graphs[c]['ops']:
        u=o['id']
        if u in comp:ann[u]=newmapping[str(u)]
        elif o['op']=='COPY_IN':
            local=[e['target'] for e in graphs[c]['edges'] if e['source']==u and tt[e['target']]['pos']!='DDR'];assert len(local)==1
            consumers=[v for v in cc[local[0]] if v in comp]
            ann[u]=min((newmapping[str(v)] for v in consumers),key=schedules[c].index)
        else:
            local=[e['source'] for e in graphs[c]['edges'] if e['target']==u and tt[e['source']]['pos']!='DDR'];assert len(local)==1
            producers=[v for v in pp[local[0]] if v in comp]
            ann[u]=max((newmapping[str(v)] for v in producers),key=schedules[c].index)
    seq=mod._prioritize_task_seq(graphs[c],rawseq[c],ann,schedules[c])
    coreops={o['id']:o for o in graphs[c]['ops']};prefix=[]
    for u in seq:
        if u not in commoncopies[c]:break
        prefix.append(u)
    computes=[u for u in seq if u in comp]
    expected=[u for j in perm for u in jobs[j][cuts[c]:cuts[c+1]]]
    assert computes==expected
    records[c].update({'candidate_interval_peak':interval_peak(graphs[c],seq),'prefix_common_copy_ids':prefix,'prefix_covers_all_common':set(prefix)==set(commoncopies[c]),'candidate_first_ops':seq[:len(commoncopies[c])+5],'compute_word_matches_permuted_anchor':True})
    if c:assert set(prefix)==set(commoncopies[c])
    # save source data for a pure algebra verifier/adapter
    (HERE/f'core{c}_prestep2_word.json').write_text(json.dumps({'raw':rawseq[c],'candidate':seq,'common_copy_ids':commoncopies[c],'pilot_gate_ids':gate_ids[c].get(pilot,[])},indent=2))
assert all(r['candidate_interval_peak']['L1']<=524288 and r['candidate_interval_peak']['UB']<=131072 for r in records)
(HERE/'case044_bucket_candidate.json').write_text(json.dumps(proposal,separators=(',',':'))+'\n')
result={'scope':'Original graph + exact pre-Step2 skeleton and Step1; no prepare/Step2/Step3/E0', 'source_ref':'845846b38f4d7cc2b5dc11a2fe8d10027560edcd','graph_sha256':hashlib.sha256(raw).hexdigest(),'calls':{'static_extracted_Task_COPY_skeleton':1,'official_step1':5,'official_step2':0,'official_step3':0,'official_prepare':0,'E0_P3':0,'E0_P2':0},'cuts':cuts,'jobs':len(jobs),'pilot_job_index':pilot,'pilot_head_op':jobs[pilot][0],'permutation':perm,'unchanged_owner':True,'unchanged_original_operations':True,'original_compute_FIFO_same_up_to_permutation':True,'copies_before_spill_unchanged':True,'cross_links':len(links),'baseline_serialization_hash_checks':serializations,'candidate_sha256':hashlib.sha256((HERE/'case044_bucket_candidate.json').read_bytes()).hexdigest(),'cores':records,'status':'Static prefix + Step2 no-spill input certificate; not officially evaluated'}
(HERE/'static_certificate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
