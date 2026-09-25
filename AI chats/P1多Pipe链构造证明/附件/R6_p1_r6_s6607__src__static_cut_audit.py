#!/usr/bin/env python3
"""Read-only R6 graph/cut audit. Never imports a solver or an evaluator.

The literal witness IDs below locate cuts in supplied evidence, not a solver
routing table. This program emits cut sets and arithmetic, NOT a two-key plan.
Usage: python static_cut_audit.py INPUT.zip --output NEW_DIRECTORY
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, pathlib, zipfile

COPY = {'COPY_IN','COPY_OUT'}

def sha(raw): return hashlib.sha256(raw).hexdigest()

def load_view(g, plan, result):
    ops={o['id']:o for o in g['ops']}; ts={t['id']:t for t in g['tensors']}
    eligible={u for u in ops if ops[u]['op'] not in COPY}
    prod=collections.defaultdict(set); cons=collections.defaultdict(set)
    full={u:set() for u in ops}
    for e in g['edges']:
        u,v=e['source'],e['target']
        if u in ops and v in ts: prod[v].add(u)
        elif u in ts and v in ops: cons[u].add(v)
        elif u in ops and v in ops: full[u].add(v)
        else: raise ValueError('unsupported original edge')
    for tid in ts:
        for u in prod[tid]:
            full[u].update(cons[tid]-{u})
    pred={u:set() for u in eligible}; succ={u:set() for u in eligible}
    for u in eligible:
        stack=list(full[u]); seen=set()
        while stack:
            v=stack.pop()
            if v in eligible: succ[u].add(v);pred[v].add(u)
            elif v not in seen: seen.add(v);stack.extend(full[v])
    mapping={int(u):t for u,t in plan['node_to_subgraph'].items()}
    assert set(mapping)==eligible
    groups=collections.defaultdict(set)
    for u,t in mapping.items():groups[t].add(u)
    assert set(t for order in plan['core_schedules'] for t in order)==set(groups)
    assert sum(map(len,plan['core_schedules']))==len(groups)
    pairs={(mapping[u],mapping[v]) for u in eligible for v in succ[u] if mapping[u]!=mapping[v]}
    assert pairs=={(e['source'],e['target']) for e in result['task_dependencies']}
    tp={t:set() for t in groups}
    for a,b in pairs:tp[b].add(a)
    heights={}
    def height(t):
        if t not in heights: heights[t]=max([height(p)+1 for p in tp[t]]+[0])
        return heights[t]
    for t in groups: height(t)
    assert all(all(heights[a]<heights[b] for a,b in zip(line,line[1:])) for line in plan['core_schedules'])
    return dict(ops=ops,ts=ts,eligible=eligible,prod=prod,cons=cons,pred=pred,succ=succ,
                mapping=mapping,groups=groups,task_preds=tp,heights=heights,
                copy_bridge_pairs=sum(len(succ[u]-(full[u]&eligible)) for u in eligible))

def component(v, nodes, d):
    out={v};stack=[v]
    while stack:
        u=stack.pop()
        for w in (d['pred'][u]|d['succ'][u])&nodes:
            if w not in out:out.add(w);stack.append(w)
    return out

def closure(v, nodes, adj):
    out={v};stack=[v]
    while stack:
        u=stack.pop()
        for w in adj[u]&nodes:
            if w not in out:out.add(w);stack.append(w)
    return out

def work(ns,d):
    c=collections.Counter()
    for u in ns:c[d['ops'][u]['pipe']]+=max(1,d['ops'][u]['cycles'])
    return dict(sorted(c.items()))

def boundary(ns,d):
    ans={}
    for tid in d['ts']:
        ps=d['prod'][tid]&ns;cs=d['cons'][tid]&ns
        ecs=d['cons'][tid]&d['eligible']
        has_co=any(d['ops'][u]['op']=='COPY_OUT' for u in d['cons'][tid])
        ib=bool(cs) and not bool(ps)
        ob=bool(ps) and (has_co or not ecs or bool(ecs-ns))
        if ib or ob:ans[tid]=(int(ib),int(ob))
    return ans

def refinement(d,S,parts,bandwidth):
    b0=boundary(S,d);bs=[boundary(ns,d) for ns in parts]; rows=[]
    touched=set(b0)|set().union(*(set(b) for b in bs))
    for tid in sorted(touched):
        old=b0.get(tid,(0,0));new=tuple(sum(b.get(tid,(0,0))[i] for b in bs) for i in (0,1))
        change=(new[0]-old[0],new[1]-old[1])
        if change==(0,0):continue
        size=d['ts'][tid]['size']; service=max(1,(size+bandwidth-1)//bandwidth)
        kind='internal_interface' if d['prod'][tid]&S else 'duplicated_upstream_or_external_read'
        rows.append(dict(tensor_id=tid,size=size,old=old,new=new,change=change,kind=kind,
                         copy_byte_change=sum(change)*size,service_change=sum(change)*service,
                         original_producers=sorted(d['prod'][tid]),
                         part_consumers=[sorted(d['cons'][tid]&p) for p in parts]))
    return dict(copy_byte_change=sum(x['copy_byte_change'] for x in rows),
                service_change=sum(x['service_change'] for x in rows),
                internal_copy_byte_change=sum(x['copy_byte_change'] for x in rows if x['kind']=='internal_interface'),
                repeated_input_copy_byte_change=sum(x['copy_byte_change'] for x in rows if x['kind']!='internal_interface'),
                rows=rows,scope='Exact boundary-COPY delta for this local refinement, excluding any future compiler spill; no new plan generated')

def cut_witness(d,task,anchor,join,parent,bandwidth):
    S=d['groups'][task]; P=component(anchor,S,d)
    X=closure(parent,P,d['pred']);J=closure(join,P,d['succ']);Y=S-X-J
    assert X and J and Y and not X&J
    assert X|Y|J==S
    outgoing={(u,v) for u in X for v in d['succ'][u]&P if v not in X}
    assert outgoing=={(parent,join)}
    assert len(d['pred'][join]&P)>=2
    xy=[(u,v) for u in X for v in d['succ'][u]&Y]
    yx=[(u,v) for u in Y for v in d['succ'][u]&X]
    back=[(u,v) for u in J for v in d['succ'][u]&(X|Y)]
    assert not xy and not yx and not back
    # Removal of the export edge disconnects the packet's undirected graph.
    assert not any((d['pred'][u]|d['succ'][u])&(P-X) - ({join} if u==parent else set()) for u in X)
    parts={'export_X':X,'donor_early_Y':Y,'join_late_J':J}
    local_edges={}
    for a,aa in parts.items():
        for b,bb in parts.items():
            if a!=b:
                es=sorted((u,v) for u in aa for v in d['succ'][u]&bb)
                if es:local_edges[a+' -> '+b]=es
    summary={name:dict(ops=len(ns),work=work(ns,d),members=sorted(ns),
                        old_external_predecessor_tasks=sorted({d['mapping'][v] for u in ns for v in d['pred'][u] if v not in S}))
             for name,ns in parts.items()}
    return dict(original_task=task,packet_anchor=anchor,packet_ops=len(P),join=join,export_parent=parent,
                original_task_ops=len(S),original_task_work=work(S,d),parts=summary,
                local_data_edges=local_edges,forbidden_edges=dict(X_to_Y=xy,Y_to_X=yx,J_to_early=back),
                source_ideal_export_bridge=True,local_refinement_task_increment=2,
                boundary=refinement(d,S,list(parts.values()),bandwidth),
                scope='Static membership witness only; neither a generated two-key plan nor a Task compilation')

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('zip',type=pathlib.Path);a.add_argument('--output',type=pathlib.Path,required=True);args=a.parse_args()
    if args.output.exists():raise FileExistsError('refuse to overwrite audit output')
    raw=args.zip.read_bytes();z=zipfile.ZipFile(args.zip);manifest=json.loads(z.read('MANIFEST.json'))
    checks=[]
    for f in manifest['files']:
        b=z.read(f['path']);assert len(b)==f['bytes'] and sha(b)==f['sha256'],f['path']
        checks.append(dict(path=f['path'],bytes=len(b),sha256=sha(b),matched=True,source=f['source']))
    cfg=z.read('data/raw/a/official/data/config.txt').decode()
    assert 'bandwidth 60' in cfg and 'L1 524288' in cfg and 'UB 131072' in cfg
    # These are evidence locations supplied/identified during read-only R6 analysis.
    witnesses={'085':[(12,136,2064,2063),(13,139,2083,2082),(14,142,2102,2101)],
               '005':[(14,114,1278,1277),(15,117,1297,1296)]}
    result={}
    for case,queries in witnesses.items():
        gb=z.read(f'data/case_{case}.json');g=json.loads(gb)
        pb=z.read(f'v4/{case}/plan.json');p=json.loads(pb)
        rb=gzip.decompress(z.read(f'v4/{case}/result.json.gz'));r=json.loads(rb)
        receipt=json.loads(z.read(f'v4/{case}/run-derived.json'))
        assert receipt['graph_sha256']==sha(gb)
        assert r['makespan']==receipt['makespan_cycles']
        assert r['data_movement_bytes']==receipt['data_movement_bytes']
        d=load_view(g,p,r)
        old_cores=[]
        for c in r['per_core_timeline']:
            spans=c['tasks'];old_cores.append(dict(core=c['core_id'],tasks=len(spans),
                occupied=sum(t['duration'] for t in spans),
                gaps=[b['start']-a['end'] for a,b in zip(spans,spans[1:])]))
        wave=[t for t in sorted(d['groups']) if d['heights'][t]==3]
        packets=[]
        for t in wave:
            remaining=set(d['groups'][t]);gs=[]
            while remaining:
                ns=component(min(remaining),remaining,d);remaining-=ns
                gs.append(dict(ops=len(ns),anchor=min(ns),sinks=sorted(u for u in ns if not d['succ'][u]&ns),work=work(ns,d)))
            packets.append(dict(task=t,ops=len(d['groups'][t]),work=work(d['groups'][t],d),packets=gs))
        result[case]=dict(graph_sha256=sha(gb),old_plan_sha256=sha(pb),old_result_sha256=sha(rb),
                         compute_ops=len(d['eligible']),raw_op_count=len(d['ops']),tensor_count=len(d['ts']),
                         max_tensor_producers=max(map(len,d['prod'].values())),
                         extra_copy_bridge_pairs=d['copy_bridge_pairs'],
                         old_makespan=r['makespan'],old_movement=r['data_movement_bytes'],
                         old_task_count=len(d['groups']),old_core_usage=old_cores,
                         old_data_task_dag_height_counts=dict(collections.Counter(d['heights'].values())),
                         old_core_orders_strictly_forward_in_height=True,
                         first_compute_wave=packets,
                         cut_witnesses=[cut_witness(d,*query,60) for query in queries])
    args.output.mkdir(parents=True)
    (args.output/'static_cut_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.output/'integrity.json').write_text(json.dumps(dict(zip_bytes=len(raw),zip_sha256=sha(raw),payload_count=len(checks),checks=checks),indent=2)+'\n')
    print(json.dumps({case:[dict(task=w['original_task'],export_ops=w['parts']['export_X']['ops'],
                                delta_bytes=w['boundary']['copy_byte_change'],delta_service=w['boundary']['service_change'])
                          for w in r['cut_witnesses']] for case,r in result.items()}))
if __name__=='__main__':main()
