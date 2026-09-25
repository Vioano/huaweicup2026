"""Research-only R5 reserve coalescing; no compiler, response, or E0 calls.

Adapted from archived R5 proposed_real_work_phase.py. The caller must first
certify private, independent M-V+-M chains and validate both plans officially.
Coalescing changes Task-local FIFO/MEM behavior; no quality claim follows.
"""
from __future__ import annotations


class UnsupportedPhase(ValueError):
    pass


def construct_pair(chain_bins, *, q, s, body_period, chain_compute_work,
                   compute_ids_in_input_order, max_tasks_per_core_budget=12):
    K = len(chain_bins)
    if not 2 <= K <= 5:
        raise UnsupportedPhase('requires 2..5 cores')
    if any(type(x) is not int or x <= 0 for x in
           (q, body_period, chain_compute_work, max_tasks_per_core_budget)):
        raise ValueError('positive integer q, period, work, and budget required')
    if type(s) is not int or not 1 <= s <= q:
        raise UnsupportedPhase('fixed nonempty cut body required')
    counts = [len(line) for line in chain_bins]
    if max(counts)-min(counts)>1:
        raise UnsupportedPhase('balanced assignment required')
    B=min(counts)
    den=K*chain_compute_work
    shifts=[(2*k*body_period+den)//(2*den) for k in range(K)]
    reserve=q*((max(shifts)+q-1)//q)
    if reserve==0 or B-reserve<2*q:
        raise UnsupportedPhase('insufficient real work for reserve and two packets')
    packets=(B-reserve)//q
    nbody=packets*q
    all_ops=[u for line in chain_bins for c in line for u in c]
    requested=list(compute_ids_in_input_order)
    if len(all_ops)!=len(set(all_ops)) or len(requested)!=len(set(requested)) or set(all_ops)!=set(requested):
        raise ValueError('chains must exactly cover unique compute IDs')
    if any(len(c)<3 for line in chain_bins for c in line):
        raise UnsupportedPhase('nonempty prefix and return required')
    mapping={}; owners={}; control_orders=[];phase_orders=[]
    next_task=0
    def emit(nodes,core):
        nonlocal next_task
        if not nodes:raise AssertionError('empty Task')
        task=next_task;next_task+=1;owners[task]=core
        for u in nodes:
            if u in mapping:raise AssertionError('duplicate compute member')
            mapping[u]=task
        return task
    for core,line in enumerate(chain_bins):
        h=shifts[core]
        before=line[:h]
        after=line[h:reserve]
        left=[emit([u for c in before for u in c],core)] if before else []
        right=[emit([u for c in after for u in c],core)] if after else []
        body=line[reserve:reserve+nbody]
        previous=[];block=[]
        for j in range(packets):
            new=body[j*q:(j+1)*q]
            whole,cut=new[:q-s],new[q-s:]
            nodes=([c[-1] for c in previous]
                   +[u for c in whole for u in c]
                   +[u for c in cut for u in c[:-1]])
            block.append(emit(nodes,core));previous=cut
        block.append(emit([c[-1] for c in previous],core))
        tail=[emit(list(c),core) for c in line[reserve+nbody:]]
        control_orders.append(left+right+block+tail)
        phase_orders.append(left+block+right+tail)
    if any(len(line)>max_tasks_per_core_budget for line in control_orders):
        raise UnsupportedPhase('per-core Task budget exceeded')
    final_map={str(u):mapping[u] for u in requested}
    control={'node_to_subgraph':dict(final_map),'core_schedules':control_orders}
    phase={'node_to_subgraph':dict(final_map),'core_schedules':phase_orders}
    for orders in (control_orders,phase_orders):
        pos=[{t:i for i,t in enumerate(line)} for line in orders]
        for core,line in enumerate(chain_bins):
            for chain in line:
                for a,b in zip(chain,chain[1:]):
                    if mapping[a]!=mapping[b] and pos[core][mapping[a]]>=pos[core][mapping[b]]:
                        raise AssertionError('chain dependency reversed')
    info={'kind':'UNSCORED_coalesced_real_reserve_phase', 'q':q,'s':s,
          'body_period_reference':body_period,'chain_compute_work':chain_compute_work,
          'whole_chain_reserve':reserve,'phase_counts':shifts,'body_packets':packets,
          'tasks':next_task,'tasks_per_core':[len(x) for x in control_orders],
          'same_partition_and_core_ownership':True,
          'scope':'Private chains only; requires fresh Task compile and model replay'}
    return control,phase,info
