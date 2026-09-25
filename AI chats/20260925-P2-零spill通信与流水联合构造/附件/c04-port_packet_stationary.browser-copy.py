"""C04 pure construction kernel: port packets, tensor-core openings, prefix liveness.

ONLY tested on synthetic canonical IR. No official modules, evaluator, trace,
case-number recognizer, network, or filesystem graph loader is used here.

Adapter obligations (not implemented here): normalize independent original COPY_IN
inputs; single eligible producer per physical tensor; no logical aliases; retained
and validation computation DAGs agree; only eligible M/V ops; preserve singleton
IDs; run the existing physical zero-spill/structural guards and official acceptance.

The returned clocks are hypothetical fixed-isolated-transfer PRIORITIES, neither
predicted official makespan nor an upper/lower bound. Memory envelopes concern
sequential pre-Step2 lifetimes under the guarded COPY anchoring grammar, not actual
runtime timestamps or the absence of Step3 memory dependencies.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import heapq
from typing import Mapping

PIPES = ('PIPE_M', 'PIPE_V')
POOLS = ('L1', 'UB')


class NoCandidate(ValueError):
    """This deterministic constructor family abstains; not infeasibility of P2."""


@dataclass(frozen=True)
class Tensor:
    id: int
    size: int
    pool: str
    producer: int | None
    consumers: frozenset[int]
    required_output: bool = False


@dataclass(frozen=True)
class IR:
    pipe: Mapping[int, str]
    duration: Mapping[int, int]
    tensors: tuple[Tensor, ...]


@dataclass(frozen=True)
class Packet:
    id: int
    word: tuple[int, ...]
    touched: frozenset[int]
    consumed_counts: Mapping[int, int]
    produced: frozenset[int]
    ports: tuple[int, ...]  # production completion ports, not one packet finish
    work: Mapping[str, int]


def topological(succ):
    degree = dict.fromkeys(succ, 0)
    for u, vs in succ.items():
        for v in vs:
            if v not in degree or v == u:
                raise ValueError('unknown/self computation edge')
            degree[v] += 1
    ready = [u for u, d in degree.items() if not d]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if len(order) != len(succ):
        raise ValueError('cyclic computation/priority graph')
    return order


def views(ir):
    nodes = set(ir.pipe)
    if not nodes or set(ir.duration) != nodes:
        raise ValueError('nonempty identical operation domains required')
    if any(type(u) is not int or u < 0 for u in nodes):
        raise ValueError('nonnegative integer operation IDs required')
    if any(ir.pipe[u] not in PIPES or type(ir.duration[u]) is not int
           or ir.duration[u] < 1 for u in nodes):
        raise ValueError('positive integer durations and M/V ops required')
    ts = {t.id: t for t in ir.tensors}
    if len(ts) != len(ir.tensors):
        raise ValueError('duplicate tensor ID')
    pred, succ = ({u: set() for u in nodes} for _ in range(2))
    inputs, outputs = ({u: set() for u in nodes} for _ in range(2))
    for t in ir.tensors:
        if (type(t.id) is not int or type(t.size) is not int or t.size < 0
                or t.pool not in POOLS or not set(t.consumers) <= nodes
                or (t.producer is not None and t.producer not in nodes)
                or t.producer in t.consumers
                or (t.required_output and t.producer is None)):
            raise ValueError('invalid canonical tensor incidence')
        if t.producer is not None:
            outputs[t.producer].add(t.id)
            for v in t.consumers:
                pred[v].add(t.producer)
                succ[t.producer].add(v)
        for v in t.consumers:
            inputs[v].add(t.id)
    order = topological(succ)
    return ts, inputs, outputs, pred, succ, order


def delivery_word(ir, pred, succ, order):
    """One predecessor-completing DFS from sinks; shared inputs are NOT edges."""
    head = {}
    for u in order:
        head[u] = ir.duration[u] + max((head[v] for v in pred[u]), default=0)
    key = lambda u: (-head[u], u)
    roots = sorted((u for u in order if not succ[u]), key=key)
    seen, word = set(), []
    for root in roots:
        if root in seen:
            continue
        stack = [(root, iter(sorted(pred[root], key=key)))]
        active = {root}
        while stack:
            u, predecessors = stack[-1]
            v = next(predecessors, None)
            if v is None:
                stack.pop()
                active.remove(u)
                if u not in seen:
                    seen.add(u)
                    word.append(u)
            elif v not in seen:
                if v in active:
                    raise ValueError('cycle during delivery DFS')
                active.add(v)
                stack.append((v, iter(sorted(pred[v], key=key))))
    if len(word) != len(order):
        raise AssertionError('delivery word did not cover all operations')
    return word


def copy_work(size, bandwidth):
    # Exact integer small-model definition; adapter owns executable numeric guards.
    return max(1, (size + bandwidth - 1) // bandwidth)


def packetize(ir, capacity, *, width=32, bandwidth=60, delay=500):
    """Bounded prefix scans; no candidate plan/evaluator is run at a cut point.

    Packets are consecutive, incrementally connected intervals of one topological
    word. Cut density charges produced tensor PORTS, not individual fanout edges.
    External-input hyperedges do not become computation dependencies.
    """
    if type(width) is not int or not 1 <= width <= 64:
        raise ValueError('width in [1,64] required')
    ts, inputs, outputs, pred, succ, topo = views(ir)
    word = delivery_word(ir, pred, succ, topo)
    packets, cursor = [], 0
    while cursor < len(word):
        members, touched, produced = set(), set(), set()
        consumed = Counter()
        volume = Counter()
        choices = []
        total_work = 0
        for j in range(cursor, min(cursor + width, len(word))):
            u = word[j]
            if members and not (pred[u] & members):
                break  # do not fuse independent jobs merely because of adjacency
            members.add(u)
            total_work += ir.duration[u]
            consumed.update(inputs[u])
            produced |= outputs[u]
            for tid in (inputs[u] | outputs[u]) - touched:
                volume[ts[tid].pool] += ts[tid].size
            touched |= inputs[u] | outputs[u]
            if any(volume[p] > capacity[p] for p in POOLS):
                break
            boundary_cost = 0
            for tid in touched:
                t = ts[tid]
                if t.producer is None:
                    continue  # stationary-input affinity, not a causal cut port
                incoming = t.producer not in members and consumed[tid] > 0
                outgoing = t.producer in members and consumed[tid] < len(t.consumers)
                if incoming or outgoing:
                    boundary_cost += delay + 2 * copy_work(t.size, bandwidth)
            choices.append((Fraction(boundary_cost, total_work), -(j-cursor+1), j+1))
        if not choices:
            raise NoCandidate('single-operation incident-footprint screen failed')
        _, _, end = min(choices)
        pword = tuple(word[cursor:end])
        nodes = set(pword)
        touch = frozenset(t for u in pword for t in inputs[u] | outputs[u])
        made = frozenset(t for u in pword for t in outputs[u])
        port_ops = {ts[t].producer for t in made
                    if ts[t].required_output or not ts[t].consumers
                    or not set(ts[t].consumers) <= nodes}
        port_ops |= {u for u in pword if not succ[u]}
        assert port_ops
        packets.append(Packet(len(packets), pword, touch,
                              dict(Counter(t for u in pword for t in inputs[u])),
                              made, tuple(sorted(port_ops)),
                              {p: sum(ir.duration[u] for u in pword if ir.pipe[u] == p)
                               for p in PIPES}))
        cursor = end
    return packets, (ts, inputs, outputs, pred, succ, topo)


def quotient(packets, succ):
    number = {u: p.id for p in packets for u in p.word}
    qp, qs = ({p.id: set() for p in packets} for _ in range(2))
    for u, vs in succ.items():
        for v in vs:
            a, b = number[u], number[v]
            if a != b:
                if a >= b:
                    raise AssertionError('interval quotient lost acyclicity')
                qs[a].add(b)
                qp[b].add(a)
    return qp, qs


def exact_bytes(ir, owner):
    categories = Counter()
    for t in ir.tensors:
        targets = {owner[u] for u in t.consumers}
        if t.producer is None:
            categories['external'] += t.size * len(targets)
        else:
            categories['cross_out_plus_in'] += 2 * t.size * len(targets - {owner[t.producer]})
            if t.required_output or not t.consumers:
                categories['terminal'] += t.size
    return dict(categories), sum(categories.values())


def evaluate_ports(ir, packet, core, clocks, owner, finish, ts, inputs, *, bandwidth, delay):
    """Fixed-isolated-transfer arithmetic only; no COPY queues or DDR replay."""
    local_clock = dict(clocks[core])
    ends = {}
    for u in packet.word:
        arrival = local_clock[ir.pipe[u]]
        for tid in inputs[u]:
            t = ts[tid]
            if t.producer is None:
                ready = copy_work(t.size, bandwidth)
            elif t.producer in ends:
                ready = ends[t.producer]
            else:
                ready = finish[t.producer]
                if owner[t.producer] != core:
                    ready += delay + 2 * copy_work(t.size, bandwidth)
            arrival = max(arrival, ready)
        ends[u] = arrival + ir.duration[u]
        local_clock[ir.pipe[u]] = ends[u]
    return ends, local_clock



def resource_coefficients(ir, packet, pred):
    """Two max-plus resource columns; None denotes a missing (-infinity) path.

    Once the packet is quotient-ready, its boundary producer clocks are frozen
    construction values. Each output then depends on current M/V availability
    through just these two columns, rather than rescanning all tensor incidences.
    """
    members = set(packet.word)
    previous = dict.fromkeys(PIPES, None)
    h = {}
    for u in packet.word:
        parents = set(pred[u]) & members
        last = previous[ir.pipe[u]]
        if last is not None:
            parents.add(last)
        coefficients = {}
        for p in PIPES:
            paths = [h[v][p] for v in parents if h[v][p] is not None]
            if last is None and p == ir.pipe[u]:
                paths.append(0)
            coefficients[p] = ir.duration[u] + max(paths) if paths else None
        h[u] = coefficients
        previous[ir.pipe[u]] = u
    return h, previous


def profile_preview(ir, packet, base, coefficients, last, availability):
    ends = {}
    for u in packet.word:
        values = [base[u]]
        values.extend(availability[p] + coefficients[u][p] for p in PIPES
                      if coefficients[u][p] is not None)
        ends[u] = max(values)
    clocks = {p: ends[last[p]] if last[p] is not None else availability[p] for p in PIPES}
    return ends, clocks


def build(ir: IR, cores: int, capacity: Mapping[str, int], *,
          width: int = 32, bandwidth: int = 60, delay: int = 500):
    """Construct ONE whole candidate, or abstain. No backtracking/score calls.

    At most 2K currently-ready packets x K cores are considered per commitment.
    Candidate clocks are used to gate a local delivery tolerance, not to predict M.
    Within the tolerance, DFS demand order and exact marginal COPY bytes dominate.
    """
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError('cores in [1,5] required')
    if set(capacity) != set(POOLS) or any(type(capacity[p]) is not int or capacity[p] <= 0 for p in POOLS):
        raise ValueError('positive integer L1/UB capacity required')
    if type(bandwidth) is not int or bandwidth <= 0 or type(delay) is not int or delay < 0:
        raise ValueError('integer bandwidth > 0 and delay >= 0 required')
    packets, v = packetize(ir, capacity, width=width, bandwidth=bandwidth, delay=delay)
    ts, inputs, outputs, pred, succ, topo = v
    qp, qs = quotient(packets, succ)
    tails = {}
    for u in reversed(topo):
        tails[u] = max((ir.duration[v] + tails[v] for v in succ[u]), default=0)
    totals = {p: sum(ir.duration[u] for u in ir.pipe if ir.pipe[u] == p) for p in PIPES}
    caps = {p: (totals[p] + cores - 1) // cores + max(q.work[p] for q in packets) for p in PIPES}
    loads = [dict.fromkeys(PIPES, 0) for _ in range(cores)]
    clocks = [dict.fromkeys(PIPES, 0) for _ in range(cores)]
    rows, live = ([[] for _ in range(cores)], [set() for _ in range(cores)])
    live_bytes = [dict.fromkeys(POOLS, 0) for _ in range(cores)]
    peaks = [dict.fromkeys(POOLS, 0) for _ in range(cores)]
    remaining = {t.id: len(t.consumers) for t in ir.tensors}
    touched_mask = dict.fromkeys(ts, 0)
    consumer_mask = dict.fromkeys(ts, 0)
    owner, finish, commits, global_word = {}, {}, [], []
    degree = {p: len(qp[p]) for p in qp}
    ready = [p for p, d in degree.items() if not d]
    heapq.heapify(ready)
    incremental_bytes, attempts, max_ready = 0, 0, len(ready)
    # Event-updated tensor/packet incidence counters. Each tensor can enter/leave
    # each core's conservative live envelope only once; each core opening is once.
    touch_packets = {t: [] for t in ts}
    use_packets = {t: [] for t in ts}
    footprints = []
    for packet in packets:
        footprints.append({p: sum(ts[t].size for t in packet.touched if ts[t].pool == p)
                           for p in POOLS})
        for t in packet.touched:
            touch_packets[t].append(packet.id)
        for t in packet.consumed_counts:
            use_packets[t].append(packet.id)
    overlaps = [[dict.fromkeys(POOLS, 0) for _ in range(cores)] for _ in packets]
    assigned_packets = set()
    coefficients = [resource_coefficients(ir, p, pred) for p in packets]
    profiles, ready_delta = {}, {}

    def activate(pid):
        packet = packets[pid]
        members = set(packet.word)
        terminal = sum(ts[t].size for t in packet.produced
                       if ts[t].required_output or not ts[t].consumers)
        bases, deltas = [], []
        zero_clocks = [dict.fromkeys(PIPES, 0) for _ in range(cores)]
        for c in range(cores):
            delta = terminal
            for tid in packet.consumed_counts:
                t = ts[tid]
                if consumer_mask[tid] & (1 << c):
                    continue
                if t.producer is None:
                    delta += t.size
                elif t.producer not in members and owner[t.producer] != c:
                    delta += 2 * t.size
            base, _ = evaluate_ports(ir, packet, c, zero_clocks, owner, finish,
                                     ts, inputs, bandwidth=bandwidth, delay=delay)
            bases.append(base)
            deltas.append(delta)
        profiles[pid], ready_delta[pid] = bases, deltas

    def change_live(tid, core, sign):
        pool, size = ts[tid].pool, ts[tid].size
        live_bytes[core][pool] += sign * size
        for target in touch_packets[tid]:
            if target not in assigned_packets:
                overlaps[target][core][pool] += sign * size

    for pid in ready:
        activate(pid)

    while ready:
        max_ready = max(max_ready, len(ready))
        window = [heapq.heappop(ready) for _ in range(min(2*cores, len(ready)))]
        options = []
        for pid in window:
            packet = packets[pid]
            local_members = set(packet.word)
            for c in range(cores):
                attempts += 1
                if any(loads[c][p] + packet.work[p] > caps[p] for p in PIPES):
                    continue  # family work cap, not official hardware infeasibility
                peak = {p: live_bytes[c][p] + footprints[pid][p] - overlaps[pid][c][p]
                        for p in POOLS}
                if any(peak[p] > capacity[p] for p in POOLS):
                    continue
                delta = ready_delta[pid][c]
                h, last = coefficients[pid]
                ends, clock = profile_preview(ir, packet, profiles[pid][c], h, last, clocks[c])
                first = min(ends[u] for u in packet.ports)
                urgent_tail = max(ends[u] + tails[u] for u in packet.ports)
                options.append({'pid': pid, 'core': c, 'delta': delta, 'ends': ends,
                                'clock': clock, 'first': first, 'tail': urgent_tail,
                                'peak': peak})
        if not options:
            raise NoCandidate('bounded ready window has no memory/work-admissible pair')
        first_min = min(o['first'] for o in options)
        admitted = [o for o in options if o['first'] <= first_min + delay]
        chosen = min(admitted, key=lambda o: (o['pid'], o['delta'], o['tail'], o['core']))
        pid, c = chosen['pid'], chosen['core']
        packet = packets[pid]
        for other in window:
            if other != pid:
                heapq.heappush(ready, other)
        rows[c].extend(packet.word)
        global_word.extend(packet.word)
        owner.update({u: c for u in packet.word})
        finish.update(chosen['ends'])
        clocks[c] = chosen['clock']
        assigned_packets.add(pid)
        del profiles[pid]
        del ready_delta[pid]
        for p in PIPES:
            loads[c][p] += packet.work[p]
        for p in POOLS:
            peaks[c][p] = max(peaks[c][p], chosen['peak'][p])
        for tid in packet.touched:
            touched_mask[tid] |= 1 << c
            if tid not in live[c]:
                live[c].add(tid)
                change_live(tid, c, +1)
        for tid, count in packet.consumed_counts.items():
            if not (consumer_mask[tid] & (1 << c)):
                t = ts[tid]
                for other in use_packets[tid]:
                    if other in ready_delta:
                        charge = t.size if t.producer is None else (
                            2*t.size if owner[t.producer] != c else 0)
                        ready_delta[other][c] -= charge
                        assert ready_delta[other][c] >= 0
                consumer_mask[tid] |= 1 << c
            remaining[tid] -= count
            assert remaining[tid] >= 0
        for tid in packet.touched:
            if remaining[tid] == 0:
                for other in range(cores):
                    if tid in live[other]:
                        live[other].remove(tid)
                        change_live(tid, other, -1)
        incremental_bytes += chosen['delta']
        commits.append({'packet': pid, 'core': c,
                        'first_port_priority_clock': chosen['first'],
                        'tail_priority_clock': chosen['tail'],
                        'marginal_pre_step2_copy_bytes': chosen['delta']})
        for target in sorted(qs[pid]):
            degree[target] -= 1
            if not degree[target]:
                activate(target)
                heapq.heappush(ready, target)
    if len(owner) != len(ir.pipe) or any(live) or any(remaining.values()):
        raise AssertionError('coverage or memory-envelope lifetime did not close')
    combined = {u: set(vs) for u, vs in succ.items()}
    for row in rows:
        for a, b in zip(row, row[1:]):
            combined[a].add(b)
    topological(combined)
    categories, exact = exact_bytes(ir, owner)
    if exact != incremental_bytes:
        raise AssertionError('incremental tensor/core ledger disagrees with full byte identity')
    return rows, {'packet_count': len(packets), 'packets': [list(p.word) for p in packets],
                  'packet_ports': [list(p.ports) for p in packets],
                  'global_priority_word': global_word, 'commits': commits,
                  'per_core_compute_work': loads, 'family_work_caps': caps,
                  'prefix_envelope_peaks_bytes': peaks,
                  'boundary_replica_counts': {str(t.id): consumer_mask[t.id].bit_count()
                                              for t in ir.tensors if t.producer is None},
                  'pre_step2_copy_categories': categories, 'pre_step2_copy_bytes': exact,
                  'arithmetic_pair_checks': attempts,
                  'pair_check_bound': 2*cores*cores*len(packets),
                  'observed_quotient_ready_frontier': max_ready,
                  'scope': 'canonical-IR construction only; clocks are priorities, no official M claim',
                  'pending': ['guarded original-graph adapter', 'official structural validation',
                              'physical zero-spill check', 'official E0 acceptance'],
                  'official_evaluator_calls': 0}


def emit_singletons(mapping, rows):
    """The adapter supplies the existing singleton operation-to-subgraph mapping."""
    flat = [u for row in rows for u in row]
    if (len(flat) != len(set(flat)) or set(mapping) != {str(u) for u in flat}
            or len(set(mapping.values())) != len(mapping)):
        raise ValueError('exact original string-key singleton coverage required')
    return {'node_to_subgraph': dict(mapping),
            'core_schedules': [[mapping[str(u)] for u in row] for row in rows]}
