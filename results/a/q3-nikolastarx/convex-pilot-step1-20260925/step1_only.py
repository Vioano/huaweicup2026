"""One admitted official Step1 call on archived 005 core-0 Task graph; no Task/Step2/Step3/E0."""
from __future__ import annotations
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import gzip, json, sys, time

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
FILES={
 'prepared':('results/a/q3-nikolastarx/layered-one-shot-20260925/run/prepared.json.gz','91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44'),
 'old_plan':('results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json','2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
 'new_plan':('results/a/q3-nikolastarx/convex-pilot-cut-20260925/CANDIDATE_UNVALIDATED.json','f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2'),
 'step1_source':('data/raw/a/official/code/schedule_step1.py','d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034'),
 'p3_source':('data/raw/a/official/code/multicore_cut_evaluate_problem_3.py','eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0'),
}

def read(name):
    rel,h=FILES[name];p=ROOT/rel;raw=p.read_bytes()
    if sha256(raw).hexdigest()!=h:raise ValueError(f'frozen {name} SHA differs')
    if name.endswith('source'):return raw
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)

def edges(es):return Counter((e['source'],e['target'],e.get('dependency')) for e in es)

def reconstruct(prepared):
    task=prepared['task_return'][0]['0'];step=prepared['step2'][0]
    if any(step[k] for k in ('new_ops','new_tensors','new_edges','removed_edges','spill_records')):
        raise ValueError('core0 Step2 was not a no-spill/no-rewire identity')
    graph=task['graph'];saved=edges(graph['edges']);ext=edges(step['ext_edges'])
    memory=Counter((d['source'],d['target'],'MEMORY_REUSE') for d in task['step3']['memory_dependencies'])
    if saved-ext!=memory or ext-saved or len(graph['edges'])!=len(step['ext_edges'])+sum(memory.values()):
        raise ValueError('Step3 MEMORY_REUSE edge subtraction differs')
    if graph['seq_ext']!=step['seq_ext'] or graph['seq_ext']!=task['seq']:
        raise ValueError('saved Step2/Step3 sequence differs')
    op_ids=[o['id'] for o in graph['ops']];tid_ids=[t['id'] for t in graph['tensors']]
    if (len(op_ids)!=len(set(op_ids)) or len(tid_ids)!=len(set(tid_ids))
            or set(op_ids)&set(tid_ids)):
        raise ValueError('task graph IDs differ')
    valid=set(op_ids)|set(tid_ids)
    if any(e['source'] not in valid or e['target'] not in valid for e in step['ext_edges']):
        raise ValueError('reconstructed edge endpoint missing')
    # _build_extended_graph(graph,result) appends new_ops/new_tensors and uses result.ext_edges.
    # With all new/removed/spill fields empty, these are exactly pre-Step2 ops/tensors/edges.
    return {'ops':graph['ops'],'tensors':graph['tensors'],'edges':step['ext_edges']},task,step

def copy_labels(graph, old_map, new_map, old_sg, new_sg, old_labels):
    ops={o['id']:o for o in graph['ops']}; out=defaultdict(set);inn=defaultdict(set)
    for e in graph['edges']:
        if e['source'] in ops and e['target'] not in ops:out[e['source']].add(e['target']);inn[e['target']].add(e['source'])
        if e['source'] not in ops and e['target'] in ops:out[e['source']].add(e['target']);inn[e['target']].add(e['source'])
    old_rank={sg:i for i,sg in enumerate(old_sg)}
    new_rank={sg:i for i,sg in enumerate(new_sg)}
    labels={}
    for u,op in ops.items():
        if u in old_map:
            if old_labels.get(u)!=old_map[u]:raise ValueError(f'old compute label differs: {u}')
            labels[u]=new_map[u];continue
        if op['op'] not in ('COPY_IN','COPY_OUT'):raise ValueError(f'unknown synthesized op {u}')
        tids=out[u] if op['op']=='COPY_IN' else inn[u]
        neighbor=set()
        for tid in tids:
            neighbor.update(out[tid] if op['op']=='COPY_IN' else inn[tid])
        neighbor={v for v in neighbor if v in old_map}
        if not neighbor:raise ValueError(f'COPY {u} has no compute endpoint')
        selector=min if op['op']=='COPY_IN' else max
        old_expected=selector((old_map[v] for v in neighbor),key=old_rank.__getitem__)
        new_expected=selector((new_map[v] for v in neighbor),key=new_rank.__getitem__)
        if old_labels.get(u)!=old_expected:raise ValueError(f'old COPY label cannot be inferred: {u}')
        labels[u]=new_expected
    if set(labels)!=set(ops):raise ValueError('op label coverage differs')
    return labels

def main():
    began=time.monotonic()
    prepared,old,new=(read(x) for x in ('prepared','old_plan','new_plan'))
    read('step1_source');read('p3_source')
    graph,task,step=reconstruct(prepared)
    old_map={int(k):v for k,v in old['node_to_subgraph'].items()}
    new_map={int(k):v for k,v in new['node_to_subgraph'].items()}
    if set(old_map)!=set(new_map):raise ValueError('compute coverage changed')
    if old['core_schedules'][1:]!=new['core_schedules'][1:]:raise ValueError('other core schedule changed')
    old_sg,new_sg=old['core_schedules'][0],new['core_schedules'][0]
    old_labels={int(k):v for k,v in task['op_subgraph'].items()}
    if task['subgraph_ids']!=old_sg:raise ValueError('archived old subgraph order differs')
    labels=copy_labels(graph,old_map,new_map,old_sg,new_sg,old_labels)
    sys.path.insert(0,str(ROOT/'data/raw/a/official/code'))
    from schedule_step1 import step1_schedule
    from multicore_cut_evaluate_problem_3 import _prioritize_task_seq
    raw=step1_schedule(graph) # the sole official Step1 invocation
    old_seq=_prioritize_task_seq(graph,raw,old_labels,old_sg)
    if old_seq!=task['seq']:
        first=next((i for i,(a,b) in enumerate(zip(old_seq,task['seq'])) if a!=b),None)
        raise ValueError(f'old archived seq replay differs at {first}')
    candidate_seq=_prioritize_task_seq(graph,raw,labels,new_sg)
    key=1000000048; target=1289
    copies=[o['id'] for o in graph['ops'] if o['op']=='COPY_IN' and key in task['out_tids'].get(str(o['id']),[])]
    if len(copies)!=1 or target not in old_map:raise ValueError('pilot COPY/consumer not unique')
    copy=copies[0]
    mte2={o['id'] for o in graph['ops'] if o['pipe']=='PIPE_MTE2'}
    old_mte2=[u for u in old_seq if u in mte2];new_mte2=[u for u in candidate_seq if u in mte2]
    result={'schema':'convex-pilot-step1-v1','input_sha256':{k:v[1] for k,v in FILES.items()},
      'official_step1_calls':1,'old_replay_exact':True,'candidate_priority_topological':True,
      'pre_step2_graph':{'ops':len(graph['ops']),'tensors':len(graph['tensors']),'edges':len(graph['edges']),
        'excluded_step3_memory_edges':len(task['step3']['memory_dependencies'])},
      'copy_label_recovered_for_all_ops':len(labels),'pilot_key':key,'pilot_copy_id':copy,'consumer':target,
      'old':{'copy_seq_pos':old_seq.index(copy),'consumer_seq_pos':old_seq.index(target),
             'copy_mte2_rank':old_mte2.index(copy),'mte2_sequence':old_mte2},
      'candidate':{'copy_seq_pos':candidate_seq.index(copy),'consumer_seq_pos':candidate_seq.index(target),
             'copy_mte2_rank':new_mte2.index(copy),'mte2_sequence':new_mte2},
      'raw_seq':raw,'candidate_seq':candidate_seq,'elapsed_seconds':time.monotonic()-began,
      'limitation':'COPY position in Step1/prioritized sequence is not issue time; no new Step2/Step3 or capacity validation.'}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
