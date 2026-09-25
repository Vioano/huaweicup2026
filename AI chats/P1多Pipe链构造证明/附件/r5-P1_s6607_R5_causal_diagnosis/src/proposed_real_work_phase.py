"""UNEXECUTED R5 proposal: same partition, real-work phase rotation.

Caller MUST certify private true M-V+-M chains, no COPY bridge, and supply one
already-chosen periodic (q,s) body. No case name, historic answer, or q/s loop
is used here. This module does NOT compile, score, simulate, or write plans.
It returns a controlled pair of two-key P1 plans: identical Task members, IDs,
core ownership; only legal Task orders differ. Official acceptance is external.
"""
from __future__ import annotations
from collections.abc import Sequence

class UnsupportedPhase(ValueError):
    pass

def construct_pair(
    chain_bins: Sequence[Sequence[Sequence[int]]], *,
    q: int, s: int, body_period: int, chain_compute_work: int,
    compute_ids_in_input_order: Sequence[int], max_tasks_per_core_budget: int = 12,
) -> tuple[dict, dict, dict]:
    """O(total compute operations + K) construction on a certified family.

    Whole chains reserved as individual independent Tasks are moved from the
    prologue to the epilogue. They are not dummy padding. A shared Task-ID map
    is constructed ONCE, which preserves official local compilation exactly
    when only core_schedules is changed within this no-cross-core domain.

    body_period is one fixed current-input model response / declared kernel
    period, never a fitted historical score. It sets only a proposal phase.
    Actual times are NOT submitted and need not match the proposed offsets.
    """
    K = len(chain_bins)
    if not 2 <= K <= 5:
        raise UnsupportedPhase('phase experiment requires 2..5 cores')
    if any(type(x) is not int or x <= 0 for x in (q, body_period, chain_compute_work)):
        raise ValueError('q, period, and chain work must be positive integers')
    if type(s) is not int or not 1 <= s <= q:
        raise UnsupportedPhase('a fixed nonempty cut body is required')
    counts = list(map(len, chain_bins))
    if max(counts)-min(counts)>1:
        raise UnsupportedPhase('balanced family assignment required for this experiment')
    B = min(counts)
    den = K * chain_compute_work
    shifts = [(2*k*body_period + den)//(2*den) for k in range(K)]
    reserve = q*((max(shifts)+q-1)//q)
    if reserve == 0 or B-reserve < 2*q:
        raise UnsupportedPhase('not enough REAL work for a phase reserve and two body packets')
    packets = (B-reserve)//q
    nbody = packets*q
    mapping: dict[int,int] = {}
    control_orders, phase_orders = [], []
    next_task = 0
    all_chain_ops = [u for line in chain_bins for c in line for u in c]
    if len(all_chain_ops)!=len(set(all_chain_ops)):
        raise ValueError('duplicate original compute op')
    if set(all_chain_ops)!=set(compute_ids_in_input_order) or len(all_chain_ops)!=len(compute_ids_in_input_order):
        raise ValueError('certified chains must exactly cover original non-COPY ops')
    if any(len(c)<3 for line in chain_bins for c in line):
        raise UnsupportedPhase('every chain must have a nonempty prefix and return')

    def emit(nodes):
        nonlocal next_task
        if not nodes:
            raise AssertionError('no empty or dummy Task')
        t = next_task; next_task += 1
        for u in nodes:
            if u in mapping:
                raise AssertionError('compute membership duplicated')
            mapping[u]=t
        return t

    for core,line in enumerate(chain_bins):
        reserves=[emit(list(c)) for c in line[:reserve]]
        body=line[reserve:reserve+nbody]
        previous=[]; block=[]
        for j in range(packets):
            new=body[j*q:(j+1)*q]
            whole=new[:q-s]; cut=new[q-s:]
            nodes=([c[-1] for c in previous]
                   +[u for c in whole for u in c]
                   +[u for c in cut for u in c[:-1]])
            block.append(emit(nodes)); previous=cut
        block.append(emit([c[-1] for c in previous]))  # close the body
        tail=[emit(list(c)) for c in line[reserve+nbody:]]
        h=shifts[core]
        control_orders.append(reserves+block+tail)
        phase_orders.append(reserves[:h]+block+reserves[h:]+tail)
    if next_task>K*max_tasks_per_core_budget:
        raise UnsupportedPhase('predeclared total Task budget exceeded')
    # Only the Task core order is changed; IDs stay fixed so the official
    # builder's sorted-subgraph traversal allocates the SAME boundary IDs.
    final_map={str(u):mapping[u] for u in compute_ids_in_input_order}
    control=dict(node_to_subgraph=dict(final_map),core_schedules=control_orders)
    phase=dict(node_to_subgraph=dict(final_map),core_schedules=phase_orders)
    for orders in (control_orders,phase_orders):
        positions=[{t:i for i,t in enumerate(line)} for line in orders]
        for k,line in enumerate(chain_bins):
            for chain in line:
                for a,b in zip(chain,chain[1:]):
                    if mapping[a]!=mapping[b]:
                        assert positions[k][mapping[a]]<positions[k][mapping[b]]
    info=dict(kind='UNSCORED_same_partition_phase_proposal',q=q,s=s,
              body_period_reference=body_period,whole_chain_reserve=reserve,
              whole_prologue_counts=shifts,body_packets=packets,
              tasks=next_task,copy_bytes_identical_by_partition=True,
              expected_compiler_invariance='same mapping/Task IDs/core ownership; sorted compiler traversal unchanged',
              scope='legality conditional on certified private chains; not a speedup guarantee')
    return control,phase,info
