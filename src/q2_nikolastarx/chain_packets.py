"""Deterministic P2 chain-packet placement heuristic; no evaluator calls.

Maximal nonbranching dependency chains are indivisible placement units. Each
original operation still advances its own Pipe clock. COPY clocks assume
isolated bandwidth, so predicted times are heuristic values, never bounds.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq
import math

from .dag_direct import DAGIndex, PIPES
from .direct import derive_multicore_plan


def packetize(index: DAGIndex):
    """Partition the contracted compute DAG into maximal nonbranching chains."""
    packets = []
    packet_of = {}
    for first in index.order:
        if first in packet_of:
            continue
        packet = []
        u = first
        while True:
            packet_of[u] = len(packets)
            packet.append(u)
            if len(index.succ[u]) != 1:
                break
            v = next(iter(index.succ[u]))
            if len(index.pred[v]) != 1 or v in packet_of:
                break
            u = v
        packets.append(tuple(packet))
    preds = [set() for _ in packets]
    succs = [set() for _ in packets]
    for u in index.ops:
        source = packet_of[u]
        for v in index.succ[u]:
            target = packet_of[v]
            if source != target:
                succs[source].add(target)
                preds[target].add(source)
    return packets, packet_of, preds, succs


def construct(graph, cores: int, *, bandwidth, cross_core_delay):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    if (type(bandwidth) not in (int, float) or not math.isfinite(bandwidth)
            or bandwidth <= 0):
        raise ValueError('bandwidth must be finite and positive')
    if (type(cross_core_delay) not in (int, float) or not math.isfinite(cross_core_delay)
            or cross_core_delay < 0):
        raise ValueError('cross_core_delay must be finite and nonnegative')
    index = DAGIndex(graph)
    packets, packet_of, preds, succs = packetize(index)
    tail = {}
    for p in reversed(range(len(packets))):
        tail[p] = sum(index.duration(u) for u in packets[p]) + max(
            (tail[q] for q in succs[p]), default=0)
    degree = {p: len(preds[p]) for p in range(len(packets))}
    ready = [(-tail[p], packets[p][0], p) for p in degree if degree[p] == 0]
    heapq.heapify(ready)
    pipe_at = [{pipe: 0 for pipe in PIPES} for _ in range(cores)]
    pipe_work = [{pipe: 0 for pipe in PIPES} for _ in range(cores)]
    owner, finish = {}, {}
    tensor_sources = defaultdict(dict)
    remaining = {tid: len(sources) for tid, sources in index.producers.items()}
    arrivals = {}
    placed = [[] for _ in range(cores)]
    traffic = Counter()
    pair_count = 0

    def copy_duration(size):
        return max(1, math.ceil(size / bandwidth))

    def propose(packet, core):
        clocks = [dict(row) for row in pipe_at]
        local_arrivals = {}
        local_owner, local_finish = {}, {}
        local_sources = {}
        local_remaining = {}
        added = Counter()
        pairs = 0
        last_end = 0

        def sources(tid):
            return local_sources.setdefault(tid, dict(tensor_sources[tid]))

        def transfer(key, source, source_end, size):
            nonlocal pairs
            if key in arrivals:
                return arrivals[key]
            if key in local_arrivals:
                return local_arrivals[key]
            duration = copy_duration(size)
            if source is None:
                release = 0
                added['external_input_bytes'] += size
            else:
                clocks[source]['PIPE_MTE3'] = max(
                    source_end, clocks[source]['PIPE_MTE3']) + duration
                release = clocks[source]['PIPE_MTE3'] + cross_core_delay
                added['cross_core_bytes'] += 2 * size
                pairs += 1
            clocks[core]['PIPE_MTE2'] = max(release, clocks[core]['PIPE_MTE2']) + duration
            local_arrivals[key] = clocks[core]['PIPE_MTE2']
            return local_arrivals[key]

        for u in packet:
            release = max((local_finish.get(v, finish.get(v, 0)) for v in index.pred[u]),
                          default=0)
            for tid in index.inputs[u]:
                size = index.tensors[tid]['size']
                if not index.producers[tid]:
                    release = max(release, transfer(('tensor', tid, None, core), None, 0, size))
                else:
                    for source, source_end in sorted(sources(tid).items()):
                        if source != core:
                            release = max(release, transfer(
                                ('tensor', tid, source, core), source, source_end, size))
            for pred, size in index.direct_inputs[u]:
                source = local_owner.get(pred, owner.get(pred))
                if source != core:
                    release = max(release, transfer(
                        ('direct', pred, u), source,
                        local_finish.get(pred, finish.get(pred, 0)), size))
            pipe = index.ops[u]['pipe']
            end = max(release, clocks[core][pipe]) + index.duration(u)
            clocks[core][pipe] = end
            local_owner[u], local_finish[u] = core, end
            last_end = max(last_end, end)
            for tid in index.outputs[u]:
                left = local_remaining.get(tid, remaining[tid]) - 1
                local_remaining[tid] = left
                source_ends = sources(tid)
                source_ends[core] = max(source_ends.get(core, 0), end)
                if left or (index.consumers[tid] and tid not in index.copy_out_inputs):
                    continue
                for source, source_end in sorted(source_ends.items()):
                    clocks[source]['PIPE_MTE3'] = max(
                        source_end, clocks[source]['PIPE_MTE3']) + copy_duration(index.tensors[tid]['size'])
                    added['output_bytes'] += index.tensors[tid]['size']
        work = dict(pipe_work[core])
        for u in packet:
            pipe = index.ops[u]['pipe']
            work[pipe] += index.duration(u)
        peak_work = max([max(work.values())] + [
            max(row.values()) for c, row in enumerate(pipe_work) if c != core])
        score = (max(max(row.values()) for row in clocks),
                 peak_work,
                 sum(added.values()), sum(work.values()), core)
        return score, clocks, local_owner, local_finish, local_sources, local_remaining, local_arrivals, added, pairs

    dispatched = 0
    while ready:
        _, _, p = heapq.heappop(ready)
        chosen = min((propose(packets[p], c) for c in range(cores)), key=lambda item: item[0])
        score, pipe_at, new_owner, new_finish, sources, left, incoming, added, pairs = chosen
        core = score[-1]
        owner.update(new_owner)
        finish.update(new_finish)
        arrivals.update(incoming)
        for tid, source_ends in sources.items():
            tensor_sources[tid] = source_ends
        remaining.update(left)
        traffic.update(added)
        pair_count += pairs
        placed[core].append(p)
        dispatched += 1
        for u in packets[p]:
            pipe_work[core][index.ops[u]['pipe']] += index.duration(u)
        for q in sorted(succs[p]):
            degree[q] -= 1
            if degree[q] == 0:
                heapq.heappush(ready, (-tail[q], packets[q][0], q))
    if dispatched != len(packets):
        raise ValueError('contracted packet graph is cyclic')
    # Keep one official subgraph per operation. Packet placement controls core
    # choice; expanded orders preserve the real chain sequence as priorities.
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for p in row for u in packets[p]] for row in placed]
    plan = {'node_to_subgraph': mapping, 'core_schedules': schedules}
    derive_multicore_plan(graph, plan)
    return plan, {
        'strategy': 'chain_packets_eft', 'packet_count': len(packets),
        'max_packet_length': max(map(len, packets), default=0),
        'multi_op_packets': sum(len(packet) > 1 for packet in packets),
        'predicted_finish_cycles': max((max(row.values()) for row in pipe_at), default=0),
        'predicted_ddr_bytes_without_spill': dict(traffic),
        'predicted_cross_core_pairs': pair_count,
        'compute_work_by_core_pipe': pipe_work,
        'complexity': ('O(k^2*P + k*(V+E+R) + P log P) placement; P=packets, '
                       'R=visited tensor/source-core incidences; one deterministic pass'),
        'model_limitations': ['Pipe and COPY clocks are heuristic, not official start times',
                              'isolated COPY bandwidth omits shared-DDR contention',
                              'Step2 spills, Step3 memory dependencies and final reorder omitted'],
    }


def build(graph, cores, config):
    return construct(graph, cores, bandwidth=config['bandwidth'],
                     cross_core_delay=config['cross_core_copy_delay_cycles'])
