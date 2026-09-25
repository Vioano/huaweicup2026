"""Two static official compilations; never invokes evaluate_scene_a or E0.

Fixed synthetic metamorphic pair tests order-preserving tensor-ID translation.
No production input or official source/configuration is modified.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, json, platform, sys, time
ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor'
sys.path[:0] = [str(VENDOR), str(VENDOR / 'data/raw/a/official/code')]
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_1 import _build_scene_a_tasks
from archived_recognizer import recognize, views


def graph(offset: int) -> dict:
    ops=[]; tensors=[]; edges=[]
    for k in range(2):
        a,b,c=10+10*k,11+10*k,12+10*k
        ci,co=100+2*k,101+2*k
        base=1000+100*k+offset
        din,x,y,z,w,dout=base-1,base,base+1,base+2,base+3,base+4
        ops += [dict(id=u,op=op,pipe=pipe,cycles=d) for u,op,pipe,d in
                [(ci,'COPY_IN','PIPE_MTE2',1),(a,'MATMUL','PIPE_M',100),
                 (b,'ADD','PIPE_V',100),(c,'MATMUL','PIPE_M',100),
                 (co,'COPY_OUT','PIPE_MTE3',1)]]
        tensors += [dict(id=t,pos='DDR' if t in (din,dout) else 'UB',size=32768)
                    for t in (din,x,y,z,w,dout)]
        pairs=[(din,ci),(ci,x),(x,a),(a,y),(x,b),(y,b),(b,z),(z,c),(c,w),(w,co),(co,dout)]
        edges += [dict(source=u,target=v) for u,v in pairs]
    return dict(ops=ops,tensors=tensors,edges=edges)


def ordered_prekey(g: dict) -> tuple:
    # Same fields/order as Family.prekey for a full-compute single Task.
    v=views(g); ns={u for u,o in v.ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    ids=sorted(ns);ix={u:i for i,u in enumerate(ids)}
    tids=sorted(set().union(*(v.in_t[u]|v.out_t[u] for u in ns)))
    ts=[]
    for t in tids:
        ps=v.producers[t]&ns;cs=v.consumers[t]&ns
        h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[t])
        ib=bool(cs) and not ps;ob=bool(ps) and (h or not cs)
        ts.append(('UB' if v.tensors[t]['pos']=='DDR' else v.tensors[t]['pos'],
                   v.tensors[t]['size'],tuple(sorted(ix[u] for u in ps)),
                   tuple(sorted(ix[u] for u in cs)),bool(ib),bool(ob)))
    direct=tuple(sorted((ix[e['source']],ix[e['target']]) for e in g['edges']
                        if e['source'] in ns and e['target'] in ns))
    return tuple((v.ops[u]['op'],v.ops[u]['pipe'],v.ops[u]['cycles']) for u in ids),tuple(ts),direct


def need_signature(task: dict) -> tuple:
    pipes=('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3')
    positions={u:(p,rank) for p,pipe in enumerate(pipes)
               for rank,u in enumerate(task['pipe_ops'][pipe],1)}
    result=[]
    from schedule_step3 import _op_duration,_uses_ddr_bandwidth
    for pipe in pipes:
        row=[]
        for u in task['pipe_ops'][pipe]:
            need=[0]*4
            for pred in task['op_preds'][u]:
                p,rank=positions[pred];need[p]=max(need[p],rank)
            op=task['op_by_id'][u]
            row.append((_op_duration(op,task['in_tids'],task['out_tids'],task['tensor_by_id'],60),
                        _uses_ddr_bandwidth(op,task['in_tids'],task['out_tids'],task['tensor_by_id']),tuple(need)))
        result.append(tuple(row))
    return tuple(result)


def main() -> None:
    out=ROOT/'results'/'set_order_probe';out.mkdir(exist_ok=False)
    config=VENDOR/'data/raw/a/official/data/config.txt'
    settings=read_evaluation_config(str(config))
    started=time.perf_counter();rows=[];keys=[];sigs=[]
    for offset in (0,7):
        g=graph(offset);_,chains,_,_,_=recognize(g)
        plan=dict(node_to_subgraph={str(u):0 for chain in chains for u in chain},core_schedules=[[0]])
        (out/f'graph_{offset}.json').write_text(json.dumps(g,indent=2)+'\n')
        (out/f'plan_{offset}.json').write_text(json.dumps(plan,indent=2)+'\n')
        keys.append(ordered_prekey(g))
        t=time.perf_counter()
        tasks,_,traffic,_=_build_scene_a_tasks(g,plan,settings['bandwidth'],settings['capacity'])
        elapsed=time.perf_counter()-t;task=tasks[0];sig=need_signature(task);sigs.append(sig)
        rows.append(dict(tensor_id_offset=offset,recognizer_chains=chains,static_seconds=elapsed,
            V_input_iteration=list(set(task['in_tids'][11])),
            fifo=task['pipe_ops'],signature=sig,memory_dependencies=task['step3']['memory_dependencies'],
            compile_peak=task['step3']['memory_peak'],traffic=traffic,
            memory_events=task['step3']['memory_events'],execution_contract_validated=task['step3']['execution_contract_validated']))
    differences=[]
    for p in range(4):
        for j,(a,b) in enumerate(zip(sigs[0][p],sigs[1][p])):
            if a!=b: differences.append(dict(pipe_index=p,rank=j+1,left=a,right=b))
    report=dict(kind='synthetic_static_compilation_counterexample_NOT_E0',python=sys.version,platform=platform.platform(),
        ordered_prekeys_equal=keys[0]==keys[1],raw_need_signatures_equal=sigs[0]==sigs[1],differences=differences,
        rows=rows,config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        wall_seconds=time.perf_counter()-started,
        calls=dict(official_static_task_compiles=2,response_simulations=0,E0=0,E1=0,E2=0,real_case_candidates=0,retries=0))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
