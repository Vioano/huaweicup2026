"""Extract a conditional first-job FIFO model from an already saved Task graph."""
from collections import defaultdict
from model import signature


def task_signature(task_graph, word, pilot_compute, cross_links, core, bandwidth):
    """No official calls. Assume all modeled inputs use fixed DDR service.

    Copy service excludes fair-sharing contention and cache. The caller must
    preserve Task/COPY identities. Restrict to the first pilot input window;
    unrelated earlier transfers reject instead of silently dropping interference.
    """
    if type(bandwidth) is not int or bandwidth<=0:
        raise ValueError('positive fixed model bandwidth required')
    ops={o['id']:o for o in task_graph['ops']}
    tensors={t['id']:t for t in task_graph['tensors']}
    ins,outs,cons,prod=(defaultdict(set) for _ in range(4))
    for e in task_graph['edges']:
        u,v=e['source'],e['target']
        if u in ops and v in tensors:
            outs[u].add(v);prod[v].add(u)
        elif u in tensors and v in ops:
            ins[v].add(u);cons[u].add(v)
        else:
            raise ValueError('requires bipartite tensor graph')
    if len(set(pilot_compute))!=len(pilot_compute) or not pilot_compute:
        raise ValueError('nonempty unique pilot compute sequence required')
    before={};total=0
    for u in pilot_compute:
        if ops[u]['pipe'] not in ('PIPE_M','PIPE_V'):
            raise ValueError('pilot contains noncompute')
        before[u]=total;total+=max(1,ops[u]['cycles'])
    for u,v in zip(pilot_compute,pilot_compute[1:]):
        if not any(u in prod[t] for t in ins[v]):
            raise ValueError('pilot must be an actual serial dependency chain')
    gates={l['target_copy_in_id']:f"{l['source_core']}:{l['source_copy_out_id']}"
           for l in cross_links if l['target_core']==core}
    required={u for u,o in ops.items() if o['op']=='COPY_IN'
              and any(v in before for t in outs[u] for v in cons[t])}
    queue=[u for u in word if ops[u]['pipe']=='PIPE_MTE2']
    selected=[i for i,u in enumerate(queue) if u in required]
    if not selected or set(queue[:max(selected)+1])!=required:
        raise ValueError('unmodeled transfer inside first-pilot FIFO window')
    queue=queue[:max(selected)+1]
    work,uses,keys,records=[],[],[],[]
    for u in queue:
        if ops[u]['op']!='COPY_IN' or any(tensors[t]['pos']!='DDR' for t in ins[u]):
            raise ValueError('model requires DDR-backed COPY_IN')
        readers={v for t in outs[u] for v in cons[t] if v in before}
        p=min(before[v] for v in readers)
        size=sum(tensors[t]['size'] for t in ins[u])
        w=max(1,(size+bandwidth-1)//bandwidth)
        key=gates.get(u)
        # A non-cross read must not depend on local compute or other local ops.
        if key is None and any(prod[t] for t in ins[u]):
            raise ValueError('internal transfer release not modeled')
        work.append(w);uses.append(p);keys.append(key)
        records.append({'copy_id':u,'size_bytes':size,'fixed_service':w,
                        'compute_before_first_use':p,'release_key':key})
    return {'signature':signature(work,uses,keys,total),'total_compute':total,
            'fixed_input_work':sum(work),'transfers':records,
            'release_convention':'source COPY_OUT completion plus the fixed cross-core delay; independent nonnegative variables in this mathematical model',
            'service_convention':'all inputs use rounded exclusive DDR service, no shared pool/cache/allocator effects'}
