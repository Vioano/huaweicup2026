"""Read-only trace / DAG analysis. Does NOT call simulate or a compiler.

Identities are (core, Task, Pipe, 1-based rank), never original op IDs.
All copies retain their complete compiled need vector, including MEM.
"""
from pathlib import Path
import collections, heapq, json
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'input/results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json'
pairs=json.loads(P.read_bytes());pipes=pairs['pipes'];pi={p:i for i,p in enumerate(pipes)}

def union(xs):
    out=[]
    for a,b in sorted(xs):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out

def intersection(a,b):
    i=j=0;out=[]
    while i<len(a) and j<len(b):
        lo=max(a[i][0],b[j][0]);hi=min(a[i][1],b[j][1])
        if lo<hi:out.append([lo,hi])
        if a[i][1]<=b[j][1]:i+=1
        else:j+=1
    return out

def size(xs):return sum(b-a for a,b in xs)
def ref(v):return [pipes[v[0]],v[1]]

def fixed_dag(task,multiplicity):
    """Longest paths with exclusive COPY service times times a certified orbit size.
    This is a fixed compiled-plan lower bound, NOT a fair-sharing resimulation.
    """
    nodes={(p,j+1):o for p,port in enumerate(task['ports']) for j,o in enumerate(port)}
    pred={};succ={u:[] for u in nodes}
    for (p,j),o in nodes.items():
        pred[p,j]=set((q,k) for q,k in enumerate(o[2]) if k)
        if j>1:pred[p,j].add((p,j-1))
    deg={u:len(ps) for u,ps in pred.items()}
    for v,ps in pred.items():
        for u in ps:succ[u].append(v)
    q=[u for u,d in deg.items() if not d];heapq.heapify(q)
    end={};order=[];parent={};dur={u:o[0]*(multiplicity if o[1] else 1) for u,o in nodes.items()}
    while q:
        v=heapq.heappop(q);u=max(pred[v],key=lambda u:(end[u],u),default=None)
        end[v]=(end[u] if u else 0)+dur[v];parent[v]=u;order.append(v)
        for w in succ[v]:
            deg[w]-=1
            if not deg[w]:heapq.heappush(q,w)
    if len(order)!=len(nodes):raise ValueError('compiled need + FIFO contains a cycle')
    tail={}
    for u in reversed(order):tail[u]=max([dur[v]+tail[v] for v in succ[u]]+[0])
    release={u:end[u]-dur[u] for u in nodes}
    jobs=[dict(op=ref(u),r=release[u],d=dur[u],q=tail[u]) for u,o in nodes.items() if o[1]]
    # Only existing jobs, not arbitrary integer horizons. This exact small-window
    # verifier may be replaced by the earlier O(J log J) certificate generator.
    best=None
    for rv in sorted({j['r'] for j in jobs}):
        for qv in sorted({j['q'] for j in jobs}):
            selected=[j for j in jobs if j['r']>=rv and j['q']>=qv]
            if not selected:continue
            service=sum(j['d'] for j in selected);val=rv+service+qv
            if best is None or val>best['bound']:
                best=dict(bound=val,release_threshold=rv,tail_threshold=qv,service=service,jobs=selected)
    terminal=max(nodes,key=lambda u:(end[u],u));path=[];u=terminal
    while u is not None:
        path.append(dict(op=ref(u),release=end[u]-dur[u],end=end[u],duration=dur[u]));u=parent[u]
    return dict(critical_path_bound=end[terminal],critical_path=list(reversed(path)),
                ddr_window=best,bound=max(end[terminal],best['bound'] if best else 0),
                orbit_size=multiplicity,
                scope='fixed compiled graph; orbit symmetry within the supplied Fraction/integer-retirement model'),nodes,pred

summary={};certs={};all_ready={}
for name,v in pairs['variants'].items():
    x=json.loads((ROOT/f'results/{name}.json').read_bytes())
    assert x['makespan']==v['expected_model_makespan']
    tasks={t['task_id']:t for t in v['tasks']}
    traces=collections.defaultdict(list)
    for e in x['trace']:traces[e['task']].append(e)
    intervals={a['task']:a for a in x['task_intervals']}
    ddr=union([(e['start'],e['end']) for e in x['trace'] if e['ddr']])
    gaps=[];cursor=0
    for a,b in ddr:
        if a>cursor:gaps.append([cursor,a])
        cursor=b
    if cursor<x['makespan']:gaps.append([cursor,x['makespan']])
    assert size(ddr)==x['ddr_retirement_union']
    assert sum(e['work'] for e in x['trace'] if e['ddr'])==x['service_cycles']
    rows=[];ready=[];paths={};bounds={}
    # The first common rounds have equal complete signatures on all five cores.
    common=0
    orders=v['core_schedules']
    while common<min(map(len,orders)):
        desc=[tasks[line[common]]['ports'] for line in orders]
        if any(a!=desc[0] for a in desc[1:]):break
        common+=1
    # Remaining tails in these two artifacts consist of at most one Task/core.
    assert all(len(line)-common<=1 for line in orders)
    tail_orbits=collections.defaultdict(list)
    for c,line in enumerate(orders):
        if len(line)>common:tail_orbits[json.dumps(tasks[line[common]]['ports'])].append(c)
    orbit_by_task={}
    for line in orders:
        for t in line[:common]:orbit_by_task[t]=len(orders)
    for cs in tail_orbits.values():
        for c in cs:orbit_by_task[orders[c][common]]=len(cs)
    for t,task in tasks.items():
        base=intervals[t]['start']; tr=traces[t]
        observed={(pi[e['pipe']],e['rank']):e for e in tr}
        bound,nodes,pred=fixed_dag(task,orbit_by_task[t]);bounds[t]=bound
        for u,o in nodes.items():
            e=observed[u];candidates=[('task-release',None,base)]
            if u[1]>1:
                prev=(u[0],u[1]-1);candidates.append(('FIFO',prev,observed[prev]['end']))
            for p,r in enumerate(o[2]):
                if r:candidates.append(('need',(p,r),observed[p,r]['end']))
            assert e['start']==max(z[2] for z in candidates),(name,t,ref(u),e,candidates)
            bind=[dict(kind=kind,op=ref(vv) if vv else None,end=en) for kind,vv,en in candidates if en==e['start']]
            ready.append(dict(core=task['core'],task=t,op=ref(u),start=e['start'],end=e['end'],
                              relative_start=e['start']-base,relative_end=e['end']-base,
                              work=o[0],ddr=o[1],need=o[2],binding_predecessors=bind))
        # A realized-duration path explains an actual event trace. DDR durations
        # on it include feedback, so the path is NOT a plan-independent bound.
        last=max(observed,key=lambda u:(observed[u]['end'],u));chain=[];u=last
        while True:
            e=observed[u];chain.append(dict(op=ref(u),start=e['start']-base,end=e['end']-base,
                         work=nodes[u][0],ddr=nodes[u][1],elapsed=e['end']-e['start']))
            ps=[w for w in pred[u] if observed[w]['end']==e['start']]
            if not ps:
                assert e['start']==base;break
            u=max(ps)
        chain.reverse();assert sum(z['elapsed'] for z in chain)==intervals[t]['end']-base
        paths[t]=dict(realized_chain=chain,elapsed=sum(z['elapsed'] for z in chain),
          compute_elapsed=sum(z['elapsed'] for z in chain if not z['ddr']),
          ddr_elapsed=sum(z['elapsed'] for z in chain if z['ddr']),
          ddr_exclusive_work=sum(z['work'] for z in chain if z['ddr']))
        if task['core']==0:
            mm=union([(e['start'],e['end']) for e in tr if e['pipe']=='PIPE_M'])
            vv=union([(e['start'],e['end']) for e in tr if e['pipe']=='PIPE_V'])
            mv=size(union(mm+vv));period=intervals[t]['end']-base
            rows.append(dict(task=t,start=base,end=intervals[t]['end'],duration=period,
                pipe_op_counts=list(map(len,task['ports'])),M_busy=size(mm),V_busy=size(vv),
                MV_overlap=size(intersection(mm,vv)),MV_idle=period-mv,
                global_DDR_busy_during_Task=size(intersection(ddr,[[base,intervals[t]['end']]])),
                orbit_size=orbit_by_task[t],fixed_bound=bound['bound']))
    cp_core_bounds={c:sum(bounds[t]['bound'] for t in line)+pairs['gate']*max(0,len(line)-1)
                    for c,line in enumerate(orders)}
    core0=orders[0];comp=sum(row['M_busy']+row['V_busy'] for row in rows);overlap=sum(r['MV_overlap'] for r in rows)
    summary[name]=dict(makespan=x['makespan'],service_cycles=x['service_cycles'],
        DDR_busy_union=size(ddr),DDR_no_request_window_length=size(gaps),
        DDR_busy_intervals=ddr,DDR_no_request_intervals=gaps,
        per_core_finish=x['per_core_finish'],core0_tasks=rows,core0_compute_work=comp,
        core0_MV_overlap=overlap,core0_MV_union=comp-overlap,
        core0_MV_idle_including_Task_gates=x['makespan']-(comp-overlap),
        fixed_plan_symmetry_window_lower_bound=max(cp_core_bounds.values()),
        per_core_symmetry_window_bounds=cp_core_bounds,
        actual_ready_equalities_checked=len(ready),common_symmetric_rounds=common,
        tail_symmetry_orbits=list(tail_orbits.values()))
    certs[name]=dict(tasks=bounds,actual_completion_paths=paths,
        fixed_plan_lower_bound=max(cp_core_bounds.values()),per_core_bounds=cp_core_bounds,
        not_global_P1_bound=True,not_binary64_equivalence=True)
    all_ready[name]=ready
out=ROOT/'results'
(out/'diagnosis.json').write_text(json.dumps(summary,indent=2)+'\n')
(out/'causal_certificates.json').write_text(json.dumps(certs,indent=2)+'\n')
(out/'ready_equalities.json').write_text(json.dumps(all_ready,separators=(',',':'))+'\n')
print(json.dumps({n:{k:v for k,v in x.items() if k not in ['DDR_busy_intervals','DDR_no_request_intervals','core0_tasks']} for n,x in summary.items()},indent=2))
