"""P2 C02 / s-8ee: exit-sealed regional recoloring and priority recovery.

Pure construction kernel. NO evaluator, original-graph evaluation, Step1/2/3,
native runtime, solver package, or network access. Tested only on synthetic DAGs.

Caller must supply the guarded eligible operation graph: validation and retained
execution adjacency coincide; each physical tensor has <=1 eligible producer;
no logical aliases. Include every operation that has a mandatory DDR output in
`escapes`. A source whose output also feeds other consumers is NOT duplicable.

This is not a complete P2 solver. The adapter must retain original singleton IDs,
validate the full plan, call the existing zero_spill_intervals.certify and safe
fixed-FIFO lower-bound filter, and use the existing native/E0 acceptance gate.
No clock returned here is a Makespan prediction or an official lower bound.
"""
from __future__ import annotations
from dataclasses import dataclass
import heapq
from typing import Mapping, Iterable

PIPES = ('PIPE_M', 'PIPE_V')
ROOT = -1


@dataclass(frozen=True)
class Problem:
    pipe: Mapping[int, str]
    duration: Mapping[int, int]
    succ: Mapping[int, frozenset[int]]
    escapes: frozenset[int] = frozenset()

    def checked(self) -> 'Problem':
        nodes = set(self.pipe)
        if not nodes or set(self.duration) != nodes or set(self.succ) != nodes:
            raise ValueError('nonempty, identical operation domains required')
        if any(type(u) is not int or u < 0 for u in nodes):
            raise ValueError('nonnegative integer operation IDs required')
        if any(self.pipe[u] not in PIPES for u in nodes):
            raise ValueError('kernel supports non-COPY M/V operations only')
        if any(type(self.duration[u]) is not int or self.duration[u] < 1 for u in nodes):
            raise ValueError('use positive integer max(1, cycles) durations')
        if not set(self.escapes) <= nodes:
            raise ValueError('unknown mandatory-output producer')
        if any(not set(vs) <= nodes or u in vs for u, vs in self.succ.items()):
            raise ValueError('unknown successor or self edge')
        topo(self.succ)
        return self


@dataclass(frozen=True)
class Seed:
    tensor_id: int
    producer: int
    # ALL eligible consumers, not only consumers on one old destination core.
    consumers: tuple[int, ...]
    exposed_delay: int


def topo(succ: Mapping[int, Iterable[int]], priority=None) -> list[int]:
    pred_count = {u: 0 for u in succ}
    for row in succ.values():
        for v in row:
            if v not in pred_count:
                raise ValueError('unknown graph endpoint')
            pred_count[v] += 1
    if priority is None:
        priority = lambda u: (u,)
    ready = [(priority(u), u) for u, deg in pred_count.items() if deg == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            pred_count[v] -= 1
            if pred_count[v] == 0:
                heapq.heappush(ready, (priority(v), v))
    if len(order) != len(succ):
        raise ValueError('priority graph is cyclic')
    return order


def with_row_edges(problem: Problem, rows: list[list[int]], excluded=frozenset()):
    graph = {u: set(vs) for u, vs in problem.succ.items()}
    for row in rows:
        outside = [u for u in row if u not in excluded]
        for u, v in zip(outside, outside[1:]):
            graph[u].add(v)
    return graph


class Postdominators:
    """DAG postdominator tree, reverse topological insertion + binary-lifting LCA.

    Each dead end and mandatory-output producer has an extra edge to ROOT.
    Construction O((N+E) log N), space O(N log N); no full N-by-N closure.
    """
    def __init__(self, problem: Problem):
        self.problem = problem
        self.height = max(1, (len(problem.pipe) + 1).bit_length())
        self.parent = {ROOT: ROOT}
        self.depth = {ROOT: 0}
        self.up = {ROOT: [ROOT] * self.height}
        self.order = topo(problem.succ)
        for u in reversed(self.order):
            successors = sorted(problem.succ[u])
            if not successors or u in problem.escapes:
                successors.append(ROOT)
            p = self.common(successors)
            self.parent[u] = p
            self.depth[u] = self.depth[p] + 1
            table = [p]
            for j in range(1, self.height):
                table.append(self.up[table[-1]][j - 1])
            self.up[u] = table

    def lca(self, a: int, b: int) -> int:
        if self.depth[a] < self.depth[b]:
            a, b = b, a
        difference = self.depth[a] - self.depth[b]
        for j in range(self.height):
            if difference & (1 << j):
                a = self.up[a][j]
        if a == b:
            return a
        for j in range(self.height - 1, -1, -1):
            if self.up[a][j] != self.up[b][j]:
                a, b = self.up[a][j], self.up[b][j]
        return self.parent[a]

    def common(self, values: Iterable[int]) -> int:
        values = list(values)
        if not values:
            raise ValueError('nonempty postdominator query required')
        p = values[0]
        for q in values[1:]:
            p = self.lca(p, q)
        return p


def sealed_region(problem: Problem, postdom: Postdominators, consumers: Iterable[int],
                  *, max_ops=64, max_work=1000):
    """Close all downstream arms to their common exit, then whole reverse layers.

    Budgets limit a constructor family, not feasible schedules. When an entire
    next layer does not fit, stop; never score layer prefixes or truncate an arm.
    """
    if type(max_ops) is not int or max_ops < 1 or type(max_work) is not int or max_work < 1:
        raise ValueError('positive structural budgets required')
    targets = sorted(set(consumers))
    if not targets or not set(targets) <= set(problem.pipe):
        raise ValueError('complete known eligible consumer set required')
    exit_op = postdom.common(targets)
    if exit_op == ROOT:
        return None, 'no_real_common_postdominator'
    region, stack = set(), list(reversed(targets))
    work = 0
    while stack:
        u = stack.pop()
        if u in region:
            continue
        region.add(u)
        work += problem.duration[u]
        if len(region) > max_ops or work > max_work:
            return None, 'complete_downstream_closure_exceeds_family_budget'
        if u == exit_op:
            continue
        if u in problem.escapes or not problem.succ[u]:
            raise AssertionError('postdominator failed to seal an escape')
        stack.extend(sorted(problem.succ[u], reverse=True))
    if exit_op not in region:
        raise AssertionError('exit was not reached')
    predecessors = {u: set() for u in problem.pipe}
    for u, vs in problem.succ.items():
        for v in vs:
            predecessors[v].add(u)
    layers = []
    while True:
        boundary = set().union(*(predecessors[v] for v in region)) - region
        layer = {u for u in boundary if u not in problem.escapes
                 and problem.succ[u] and set(problem.succ[u]) <= region}
        if not layer:
            break
        extra = sum(problem.duration[u] for u in layer)
        if len(region) + len(layer) > max_ops or work + extra > max_work:
            break
        layers.append(sorted(layer))
        region |= layer
        work += extra
    for u in region - {exit_op}:
        if u in problem.escapes or not set(problem.succ[u]) <= region:
            raise AssertionError('region has an unsealed output')
    return {'exit': exit_op, 'ops': sorted(region), 'reverse_layers': layers,
            'compute_volume': work}, None


def projected_region_predecessors(graph, region):
    """Exact R-to-R reachability, including paths via the retained outside chains.

    This is a PRIORITY interface, not a recovered prepared memory/FIFO graph.
    Bit masks have <= |R| bits. Python big-integer OR cost must be counted.
    """
    r = sorted(region)
    number = {u: j for j, u in enumerate(r)}
    mask = {u: 0 for u in graph}
    for u in topo(graph):
        outgoing = mask[u] | ((1 << number[u]) if u in number else 0)
        for v in graph[u]:
            mask[v] |= outgoing
    return {v: {u for u in r if mask[v] & (1 << number[u])} for v in r}


def fresh_two_pipe_word(problem: Problem, region, priority_preds, ingress_hint=None):
    """Generate ONE regional priority word. Virtual clocks are tie-breaking only.

    Data predecessors control virtual completion; paths introduced only by the
    outside priority interface control dispatch order, NOT completion time.
    Boundary hints may be stale and have no scheduling/bandwidth guarantee.
    """
    region = set(region)
    hint = {u: 0 for u in region} if ingress_hint is None else {u: ingress_hint[u] for u in region}
    if any(type(v) is not int or v < 0 for v in hint.values()):
        raise ValueError('nonnegative integer construction hints required')
    inner_succ = {u: set(problem.succ[u]) & region for u in region}
    inner_pred = {u: set() for u in region}
    for u, vs in inner_succ.items():
        for v in vs:
            inner_pred[v].add(u)
    tail = {}
    for u in reversed(topo(inner_succ)):
        tail[u] = problem.duration[u] + max((tail[v] for v in inner_succ[u]), default=0)
    done, word, virtual_end = set(), [], {}
    pipe_clock = dict.fromkeys(PIPES, 0)
    while len(word) < len(region):
        ready = [u for u in region - done if priority_preds[u] <= done]
        if not ready:
            raise ValueError('regional priority interface has no extension')
        def begin(u):
            return max(pipe_clock[problem.pipe[u]], hint[u],
                       max((virtual_end[v] for v in inner_pred[u]), default=0))
        u = min(ready, key=lambda v: (begin(v), -tail[v], v))
        end = begin(u) + problem.duration[u]
        pipe_clock[problem.pipe[u]] = end
        virtual_end[u] = end
        word.append(u)
        done.add(u)
    return word, {'virtual_end_for_priority_only': virtual_end,
                  'not_an_official_score_or_bound': True}


def recover(problem: Problem, rows: list[list[int]], region: set[int], host: int,
            *, ingress_hint=None):
    """Erase old R priorities, construct a new word, lift to complete core rows.

    The outside per-core subsequences are exactly preserved. Operations in R
    receive the fixed exit's core. Start/end timestamps are never submitted.
    """
    flat = [u for row in rows for u in row]
    if len(flat) != len(set(flat)) or set(flat) != set(problem.pipe):
        raise ValueError('rows must cover original operations exactly once')
    if not 0 <= host < len(rows) or not region <= set(flat):
        raise ValueError('host or region outside domain')
    baseline_graph = with_row_edges(problem, rows)
    baseline_order = topo(baseline_graph)
    baseline_rank = {u: j for j, u in enumerate(baseline_order)}
    outside_graph = with_row_edges(problem, rows, region)
    interface = projected_region_predecessors(outside_graph, region)
    word, clocks = fresh_two_pipe_word(problem, region, interface, ingress_hint)
    lifted_graph = {u: set(vs) for u, vs in outside_graph.items()}
    for u, v in zip(word, word[1:]):
        lifted_graph[u].add(v)
    # Regional ready ops are preferred. No old start minus delay sort is used.
    lifted = topo(lifted_graph, lambda u: (u not in region, baseline_rank[u], u))
    owner = {u: c for c, row in enumerate(rows) for u in row}
    new_owner = {u: host if u in region else owner[u] for u in owner}
    output = [[u for u in lifted if new_owner[u] == c] for c in range(len(rows))]
    for c in range(len(rows)):
        if [u for u in output[c] if u not in region] != [u for u in rows[c] if u not in region]:
            raise AssertionError('outside priority changed')
    topo(with_row_edges(problem, output))
    return output, {'regional_word': word,
                    'global_priority_order': lifted,
                    'regional_priority_predecessors': {u: sorted(v) for u, v in interface.items()},
                    'moved': [[u, owner[u], host] for u in sorted(region) if owner[u] != host],
                    **clocks}


def propose(problem: Problem, rows: list[list[int]], seeds: list[Seed], *,
            incumbent_makespan: int, cross_delay=500, max_ops=64,
            max_regions=8, max_candidates=2, hint_factory=None):
    """At most 8 structural roots and 2 full proposals. No score-based iteration.

    Mandatory pending checks: full physical reconstruction guard, zero-spill
    certificate, a SAFE fixed-FIFO rejection only (never score ranking), then
    the existing native replay and independent official E0 acceptance.
    """
    problem.checked()
    if (type(incumbent_makespan) is not int or incumbent_makespan <= 0
        or type(cross_delay) is not int or cross_delay <= 0
        or not 1 <= max_regions <= 8 or not 1 <= max_candidates <= 2):
        raise ValueError('positive makespan/delay and fixed bounded budgets required')
    flat = [u for row in rows for u in row]
    if len(flat) != len(set(flat)) or set(flat) != set(problem.pipe):
        raise ValueError('bad baseline coverage')
    topo(with_row_edges(problem, rows))
    owner = {u: c for c, row in enumerate(rows) for u in row}
    pd = Postdominators(problem)
    unique = {}
    for s in seeds:
        if (s.producer not in owner or not s.consumers
            or not set(s.consumers) <= set(owner) or s.exposed_delay <= 0):
            raise ValueError('invalid supplied witness seed')
        # The graph/tensor adapter must additionally establish exact consumers.
        if not set(s.consumers) <= set(problem.succ[s.producer]):
            raise ValueError('seed consumer is not a direct retained data successor')
        old = unique.get(s.tensor_id)
        if old is not None and (old.producer != s.producer or set(old.consumers) != set(s.consumers)):
            raise ValueError('one physical tensor has inconsistent seed views')
        if old is None or s.exposed_delay > old.exposed_delay:
            unique[s.tensor_id] = s
    ordered_seeds = sorted(unique.values(), key=lambda s: (
        -len({owner[v] for v in s.consumers}), -s.exposed_delay, s.tensor_id))[:max_regions]
    rejected, regions = [], {}
    for seed in ordered_seeds:
        info, reason = sealed_region(problem, pd, seed.consumers,
                                     max_ops=max_ops, max_work=2 * cross_delay)
        if reason:
            rejected.append({'tensor_id': seed.tensor_id, 'reason': reason})
            continue
        r = frozenset(info['ops']); host = owner[info['exit']]
        moved = {u for u in r if owner[u] != host}
        if not moved:
            rejected.append({'tensor_id': seed.tensor_id, 'reason': 'no_regional_recoloring'})
            continue
        new_owner = {u: host if u in r else owner[u] for u in owner}
        load = {c: {p: 0 for p in PIPES} for c in range(len(rows))}
        for u in owner:
            load[new_owner[u]][problem.pipe[u]] += problem.duration[u]
        if max(v for row in load.values() for v in row.values()) >= incumbent_makespan:
            rejected.append({'tensor_id': seed.tensor_id, 'reason': 'certified_work_no_strict_gain'})
            continue
        eliminated = [s.tensor_id for s in unique.values()
                      if any(owner[v] != owner[s.producer] for v in s.consumers)
                      and all(new_owner[v] == new_owner[s.producer] for v in s.consumers)]
        info.update(host=host, eliminated_witness_tensor_ids=sorted(eliminated),
                    moved_compute_volume=sum(problem.duration[u] for u in moved))
        regions[(r, host)] = info
    # WITNESS COVERAGE IS ONLY A HEURISTIC ALLOCATION OF A SMALL PROPOSAL BUDGET.
    # No all-tight-path coverage test is a safe rejection under shared DDR.
    selected = sorted(regions.items(), key=lambda x: (
        -len(x[1]['eliminated_witness_tensor_ids']), x[1]['moved_compute_volume'],
        x[1]['exit'], tuple(x[1]['ops'])))[:max_candidates]
    proposals = []
    for (r, host), info in selected:
        hints = None if hint_factory is None else hint_factory(set(r), host)
        new_rows, detail = recover(problem, rows, set(r), host, ingress_hint=hints)
        if new_rows != rows:
            proposals.append({'rows': new_rows, 'region': info, 'priority': detail,
                              'official_quality': 'unmeasured',
                              'pending': ['physical guard', 'zero-spill', 'fixed-FIFO rejection', 'native', 'E0']})
    return proposals, {'rejections': rejected, 'structural_roots': len(ordered_seeds),
                       'unique_regions': len(regions), 'proposals': len(proposals),
                       'calls': {'E0': 0, 'E1': 0, 'E2': 0, 'prepare': 0},
                       'score_guarantee': False}


def emit_plan(baseline_plan: dict, rows: list[list[int]]) -> dict:
    """Preserve original singleton subgraph IDs; emit only the two official keys."""
    mapping = baseline_plan['node_to_subgraph']
    if set(mapping) != {str(u) for row in rows for u in row} or len(set(mapping.values())) != len(mapping):
        raise ValueError('original string-key singleton mapping required')
    flat = [u for row in rows for u in row]
    if len(flat) != len(set(flat)):
        raise ValueError('duplicate operation in output')
    return {'node_to_subgraph': dict(mapping),
            'core_schedules': [[mapping[str(u)] for u in row] for row in rows]}
