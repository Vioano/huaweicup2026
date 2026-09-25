"""One deterministic COPY-prefix bucket transformation, no evaluator calls.

Input tasks must be the exact pre-Step2 graphs plus Step1 raw words for the
same graph/owner, captured from the frozen builder. Times are not submitted.
The caller still validates with derive_multicore_plan and official prepare.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any

class GuardFailure(ValueError):
    pass

def _ports(graph: dict[str, Any]):
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    if len(ops) != len(graph['ops']) or set(ops) & set(tensors):
        raise GuardFailure('IDs must be unique and disjoint')
    prod, cons, inputs, outputs = (defaultdict(set) for _ in range(4))
    for e in graph['edges']:
        a,b = e['source'], e['target']
        if a in ops and b in tensors:
            prod[b].add(a); outputs[a].add(b)
        elif a in tensors and b in ops:
            cons[a].add(b); inputs[b].add(a)
        else:
            raise GuardFailure('tensor-mediated edges required')
    return ops,tensors,prod,cons,inputs,outputs

def _check_word(graph, word):
    ops,tensors,prod,cons,inputs,outputs = _ports(graph)
    if len(word) != len(ops) or set(word) != set(ops):
        raise GuardFailure('word coverage mismatch')
    rank = {u:i for i,u in enumerate(word)}
    for t in tensors:
        for u in prod[t]:
            for v in cons[t]:
                if rank[u] >= rank[v]:
                    raise GuardFailure('word violates a data edge')

def interval_peaks(graph, word, capacity):
    """Exact no-spill pre-Step2 interval test, not asynchronous memory peaks."""
    _check_word(graph,word)
    ops,tensors,prod,cons,inputs,outputs = _ports(graph)
    rank = {u:i for i,u in enumerate(word)}
    delta = {p:[0]*(len(word)+1) for p in capacity}
    for t,x in tensors.items():
        if x['pos'] not in capacity: continue
        uses = prod[t] | cons[t]
        if not uses: continue
        if not prod[t]:
            raise GuardFailure('initial resident tensors not supported by this certificate')
        lo=min(rank[u] for u in uses); hi=max(rank[u] for u in uses)
        delta[x['pos']][lo]+=x['size']; delta[x['pos']][hi+1]-=x['size']
    peaks={}
    for p,events in delta.items():
        used=peak=0
        for change in events: used+=change; peak=max(peak,used)
        peaks[p]=peak
        if peak>capacity[p]: raise GuardFailure(f'no-spill test fails: {p} {peak}>{capacity[p]}')
    return peaks

def construct(graph, anchor, jobs, cuts, tasks, cross_links,
              capacity=None):
    """Same owner/cuts, one global pilot-first job permutation, four or fewer merges.

    tasks[c] = {'graph': exact_pre_step2_task_graph,
                'raw_seq': exact_step1_word}
    No candidate enumeration: choose the first job satisfying all raw-rank guards.
    """
    capacity = capacity or {'L1':524288,'UB':131072}
    ops,tensors,prod,cons,inputs,outputs = _ports(graph)
    compute={u for u,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    k=len(cuts)-1
    if not (2<=k<=5 and len(jobs)>=2 and len(anchor['core_schedules'])==k):
        raise GuardFailure('requires >=2 jobs and 2..5 stages')
    if set(u for job in jobs for u in job)!=compute or sum(map(len,jobs))!=len(compute):
        raise GuardFailure('jobs must partition compute nodes')
    if cuts[0]!=0 or any(a>=b for a,b in zip(cuts,cuts[1:])) or any(len(job)!=cuts[-1] for job in jobs):
        raise GuardFailure('nonempty shared position intervals required')
    for job in jobs:
        for u,v in zip(job,job[1:]):
            if not any(u in prod[t] for t in inputs[v]):
                raise GuardFailure('each job must have its Hamiltonian data chain')
    oldmap={int(u):sg for u,sg in anchor['node_to_subgraph'].items()}
    if set(oldmap)!=compute or len(set(oldmap.values()))!=len(compute):
        raise GuardFailure('anchor must be singleton')
    for c,(l,r) in enumerate(zip(cuts,cuts[1:])):
        if anchor['core_schedules'][c] != [oldmap[u] for job in jobs for u in job[l:r]]:
            raise GuardFailure('anchor must use common job-major order')
    ext=[{t for u in job for t in inputs[u] if not(prod[t]&compute)} for job in jobs]
    common=set.intersection(*ext)
    if not common: raise GuardFailure('no shared external input')
    signatures=[tuple((ops[u]['pipe'],ops[u]['cycles'],tuple(sorted(inputs[u]&common))) for u in job) for job in jobs]
    if any(s!=signatures[0] for s in signatures[1:]):
        raise GuardFailure('nonidentical shared-port signatures')
    jobof={u:j for j,job in enumerate(jobs) for u in job}
    for tid in tensors:
        writers=prod[tid]&compute
        if len(writers)>1:
            raise GuardFailure('unique original compute producer required')
        if writers:
            writer=next(iter(writers))
            if any(jobof[v]!=jobof[writer] for v in cons[tid]&compute):
                raise GuardFailure('different jobs must have no compute edges')
    valid=set(range(len(jobs))); common_copy={}; gate_copy=defaultdict(lambda:defaultdict(list))
    taskports={}
    for c in range(k):
        taskports[c]=_ports(tasks[c]['graph']); _check_word(tasks[c]['graph'],tasks[c]['raw_seq'])
        to,tt,tp,tc,ti,tout=taskports[c]
        common_copy[c]={u for u,o in to.items() if o['op']=='COPY_IN' and tout[u]&common}
        expected={t for u in jobs[0][cuts[c]:cuts[c+1]] for t in inputs[u]&common}
        if {t for u in common_copy[c] for t in tout[u]&common} != expected:
            raise GuardFailure('task shared-input coverage mismatch')
    for link in cross_links:
        c=link['target_core']; u=link['target_copy_in_id']
        to,tt,tp,tc,ti,tout=taskports[c]
        readers={v for t in tout[u] for v in tc[t] if v in compute}
        js={jobof[v] for v in readers}
        if len(js)!=1: raise GuardFailure('activation shared across jobs')
        gate_copy[c][next(iter(js))].append(u)
    for c in range(1,k):
        rank={u:i for i,u in enumerate(tasks[c]['raw_seq'])}
        last=max((rank[u] for u in common_copy[c]),default=-1)
        valid &= {j for j in range(len(jobs)) if gate_copy[c][j] and last<min(rank[u] for u in gate_copy[c][j])}
    if not valid: raise GuardFailure('no common raw-late pilot; no fallback search')
    pilot=min(valid,key=lambda j:min(jobs[j])); perm=[pilot]+[j for j in range(len(jobs)) if j!=pilot]
    mapping=dict(oldmap); fresh=max(mapping.values())+1
    for c in range(1,k):
        for u in jobs[pilot][cuts[c]:cuts[c+1]]: mapping[u]=fresh
        fresh+=1
    schedules=[]
    for c,(l,r) in enumerate(zip(cuts,cuts[1:])):
        word=[]
        for j in perm:
            for u in jobs[j][l:r]:
                sg=mapping[u]
                if not word or word[-1]!=sg:word.append(sg)
        schedules.append(word)
    records=[]
    for c in range(k):
        rank={sg:i for i,sg in enumerate(schedules[c])}; buckets=[[] for _ in schedules[c]]
        to,tt,tp,tc,ti,tout=taskports[c]
        for u in tasks[c]['raw_seq']:
            o=to[u]
            if u in compute: sg=mapping[u]
            elif o['op']=='COPY_IN':
                readers={v for t in tout[u] if tt[t]['pos']!='DDR' for v in tc[t] if v in compute}
                if not readers: raise GuardFailure('unexpected internal COPY_IN')
                sg=min((mapping[v] for v in readers),key=rank.get)
            elif o['op']=='COPY_OUT':
                writers={v for t in ti[u] if tt[t]['pos']!='DDR' for v in tp[t] if v in compute}
                if not writers: raise GuardFailure('unexpected internal COPY_OUT')
                sg=max((mapping[v] for v in writers),key=rank.get)
            else: raise GuardFailure('unknown noncompute op')
            buckets[rank[sg]].append(u)
        seq=[u for b in buckets for u in b]
        expected=[u for j in perm for u in jobs[j][cuts[c]:cuts[c+1]]]
        if [u for u in seq if u in compute]!=expected:
            raise GuardFailure('compute projection changed beyond job permutation')
        prefix=[]
        for u in seq:
            if u not in common_copy[c]:break
            prefix.append(u)
        if c and set(prefix)!=common_copy[c]:
            raise GuardFailure('shared input is not the complete gate-free prefix')
        peaks=interval_peaks(tasks[c]['graph'],seq,capacity)
        records.append({'core':c,'prefix':prefix,'pre_step2_word':seq,'interval_peak':peaks})
    plan={'node_to_subgraph':{str(u):mapping[u] for u in oldmap},'core_schedules':schedules}
    return plan, {'pilot':pilot,'job_permutation':perm,'cuts':cuts,'cores':records,
                  'scope':'pre-Step2 prefix and no-spill INPUT certificates, not E0 timing',
                  'official_calls':0}
