"""Deterministic fifth-core candidate for K-1 persistent attention tracks.

This is a single static construction, not an official P3 evaluation.  It
neither searches placements nor calls Task, Step, or E0.  A failed structural
or memory guard leaves the graph unsupported.
"""
from __future__ import annotations

from .attention_rows import _ports, _recognize
from .layered_query_flow import (
    PIPES,
    RawIndex,
    decompose,
    interval_certificate,
    need,
    path_stats,
    priority_words,
    recognize_layers,
    traffic_counts,
)


def construct(graph: dict, cores: int, capacity: dict, delay: int):
    """Return a two-field singleton plan, metadata, and static evidence.

    Every private track occupies its numbered core; every ancestor-closed
    shared component occupies the last core.  Feeder components precede
    terminal components.  The temporary component phases order construction
    only; they add no submitted dependencies or completion barrier.
    """
    need(type(cores) is int and cores >= 2, 'requires at least two cores')
    need(isinstance(capacity, dict) and set(capacity) == {'L1', 'UB'}
         and all(type(x) is int and x > 0 for x in capacity.values()), 'bad capacity')
    need(type(delay) is int and delay >= 0, 'bad delay')
    index = RawIndex.build(graph)
    ports = _ports(index)
    rows, depth, keys, labels, kv, qsucc = recognize_layers(index, ports, _recognize)
    tracks, private, parts, phase, up, down, anchors, sigs = decompose(index, labels, kv)
    need(len(tracks) == cores - 1, 'requires exactly K-1 persistent tracks')
    need(bool(parts), 'no shared residual to offload')
    need(all(ports.outputs[u] for u in index.ops), 'every compute op needs an output')

    extra = cores - 1
    owner = dict(private)
    for part in parts:
        owner.update((u, extra) for u in part)
    need(set(owner) == set(index.ops), 'incomplete/overlapping ownership')

    def component_key(part):
        consumers = {v for u in part for v in index.succ[u] if v in private}
        return (not bool(consumers),
                min((phase[v] for v in consumers), default=10**9), min(part))

    ordered = sorted(parts, key=component_key)
    microphase = {u: phase[u] for u in private}
    for j, part in enumerate(ordered):
        for u in part:
            microphase[u] = j - len(ordered)

    words, tau = priority_words(index, microphase, owner, cores, delay)
    memory, intervals = interval_certificate(index, ports, owner, words, capacity)
    need(memory['step2_no_spill_certificate'],
         'one candidate exceeded bucket-frontier capacity; stop')
    mv = path_stats(index, owner, words, tau, delay)
    envelope = path_stats(index, owner, words, tau, delay, True)
    need(envelope['max_remote_edges'] <= 2 + max(depth.values()),
         'L+1 path-count guard failed')
    traffic, links = traffic_counts(index, ports, owner, kv)

    mapping = {str(u): j for j, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in word] for word in words]}
    metadata = {
        'status': 'STATIC_ONLY_NOT_OFFICIALLY_EVALUATED', 'official_calls': 0,
        'rule': 'component_contiguous_extra_core', 'M3': None, 'M2': None, 'G': None,
        'tracks': tracks, 'private_ops': len(private), 'shared_components': len(parts),
        'shared_ops': sum(map(len, parts)),
        'ordered_components': [{'min_op_id': min(part), 'nodes': sorted(part),
                                'kind': 'terminal' if component_key(part)[0] else 'feeder'}
                               for part in ordered],
        'core_lengths': list(map(len, words)),
        'core_work_M_V': [[sum(index.duration(u) for u in word if index.ops[u]['pipe'] == p)
                           for p in PIPES] for word in words],
        'memory': memory, 'compute_MV_FIFO': mv, 'whole_word_envelope': envelope,
        'traffic_prediction': traffic,
    }
    evidence = {'global_tau': tau, 'core_compute_words': words, 'owner': owner,
                'intervals': intervals, 'source_rule_cross_links': links}
    return plan, metadata, evidence
