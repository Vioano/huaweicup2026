"""C03 / s-7d28: exterior-slack reservation and priority-realizable FIFO lifting.

PURE fixed-service construction kernel. No imports from official code, no DDR
simulation, no Step1/2/3, no search over complete plans. Run only on synthetics
in this research response. At integration, call ONCE for each of at most two
already selected C02 regions; keep region, host and regional word unchanged.

A returned witness is sufficient ONLY in the supplied fixed-service model.
It is NOT an official P2 non-regression certificate. Official adapters must
retain C02 physical guards, full plan validation, zero-spill checks and E0.

For a compute-only P2 ordering heuristic, use retained original edges with
lag 500 when candidate owners differ, otherwise 0, and zero exogenous releases.
That is an optimistic model, not a reconstructed prepared graph. Never use an
old observed COPY duration as a new fixed edge duration. Other fixed-service
models can be supplied explicitly, but are not alternate candidates to scan.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Mapping, Sequence


class NoCandidate(ValueError):
    """Failure in this deterministic constructor family, not infeasibility."""
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


@dataclass(frozen=True)
class FixedModel:
    duration: Mapping[int, int]
    pipe: Mapping[int, str]
    # finish(u) + lag <= start(v), for the CANDIDATE placement.
    lags: Mapping[tuple[int, int], int]
    release: Mapping[int, int]

    def validate(self) -> None:
        nodes = set(self.duration)
        if not nodes or set(self.pipe) != nodes or set(self.release) != nodes:
            raise ValueError("duration, pipe and release require identical nonempty domains")
        for u in nodes:
            if type(u) is not int or u < 0:
                raise ValueError("operation IDs must be nonnegative integers")
            if type(self.duration[u]) is not int or self.duration[u] <= 0:
                raise ValueError("positive integer services required")
            if type(self.release[u]) is not int or self.release[u] < 0:
                raise ValueError("nonnegative integer releases required")
            if self.pipe[u] not in ("M", "V", "PIPE_M", "PIPE_V"):
                raise ValueError("two compute Pipes only")
        if {self.pipe[u] for u in nodes} & {"M", "V"} and {self.pipe[u] for u in nodes} & {"PIPE_M", "PIPE_V"}:
            raise ValueError("do not mix Pipe naming conventions")
        for (u, v), lag in self.lags.items():
            if u not in nodes or v not in nodes or u == v or type(lag) is not int or lag < 0:
                raise ValueError("invalid fixed lag")
        topological(_adj(nodes, self.lags))


def _adj(nodes, edges):
    result = {u: set() for u in nodes}
    for u, v in edges:
        result[u].add(v)
    return result


def topological(succ, priority=None):
    degree = {u: 0 for u in succ}
    for u in succ:
        for v in succ[u]:
            if v not in degree:
                raise ValueError("unknown edge endpoint")
            degree[v] += 1
    key = priority or (lambda u: u)
    ready = [(key(u), u) for u in degree if not degree[u]]
    heapq.heapify(ready)
    result = []
    while ready:
        _, u = heapq.heappop(ready)
        result.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, (key(v), v))
    if len(result) != len(succ):
        raise NoCandidate("priority_lift_cycle")
    return result


def _owners(rows, nodes):
    flat = [u for row in rows for u in row]
    if len(flat) != len(set(flat)) or set(flat) != set(nodes):
        raise ValueError("rows must cover all operations exactly once")
    return {u: c for c, row in enumerate(rows) for u in row}


def _pipe_orders(rows, pipe, excluded=frozenset()):
    result = {}
    for c, row in enumerate(rows):
        for u in row:
            if u not in excluded:
                result.setdefault((c, pipe[u]), []).append(u)
    return result


def lift_priority(model: FixedModel, old_rows, region_word, new_owner, witness):
    """Realize witness FIFO order AND retained full exterior priority subsequences.

    Full cross-Pipe priority edges enter this TOPOSORT ONLY. They are never
    misinterpreted as finish-to-start constraints in the fixed-service model.
    A feasible temporal witness need not pass this additional lift test.
    """
    nodes, region = set(model.duration), set(region_word)
    graph = _adj(nodes, model.lags)
    for row in old_rows:
        outside = [u for u in row if u not in region]
        for u, v in zip(outside, outside[1:]):
            graph[u].add(v)
    for u, v in zip(region_word, region_word[1:]):
        graph[u].add(v)
    buckets = {}
    for u in nodes:
        buckets.setdefault((new_owner[u], model.pipe[u]), []).append(u)
    for resource, row in buckets.items():
        row.sort(key=lambda u: (witness[u], u))
        for u, v in zip(row, row[1:]):
            if witness[u] + model.duration[u] > witness[v]:
                raise ValueError("overlapping witness on " + str(resource))
            graph[u].add(v)
    # Stable tie breaking is irrelevant to FIFO once the resource arcs exist.
    base_graph = _adj(nodes, model.lags)
    for row in old_rows:
        for u, v in zip(row, row[1:]):
            base_graph[u].add(v)
    rank = {u: j for j, u in enumerate(topological(base_graph))}
    order = topological(graph, lambda u: (rank[u], u))
    rows = [[] for _ in old_rows]
    for u in order:
        rows[new_owner[u]].append(u)
    actual = _pipe_orders(rows, model.pipe)
    if actual != buckets:
        raise AssertionError("lift changed a witnessed resource order")
    for before, after in zip(old_rows, rows):
        if [u for u in before if u not in region] != [u for u in after if u not in region]:
            raise AssertionError("lift changed exterior priority")
    host = new_owner[region_word[0]]
    if [u for u in rows[host] if u in region] != list(region_word):
        raise AssertionError("lift changed the chosen regional word")
    return rows, order, buckets


def recover(model: FixedModel, old_rows: Sequence[Sequence[int]],
            old_start: Mapping[int, int], region_word: Sequence[int], host: int,
            horizon: int) -> dict:
    """One deterministic recovery. Fixed joint midpoint, no positional scanning.

    1. Compute a latest-start envelope on the exterior fixed-service skeleton.
    2. Reserve every exterior interval at floor((old_start + latest)/2).
    3. Put the given regional word in the earliest compatible free intervals,
       using separate M/V cursors and true data dependencies.
    4. Check the complete witness and lift every witnessed Pipe order to JSON
       priorities. Failure does not trigger another word, region or midpoint.

    The free-interval traversal has a monotone cursor per Pipe: O(N + |R|),
    NOT an enumeration/evaluation of all complete insertion choices.
    """
    model.validate()
    nodes = set(model.duration)
    rows = [list(row) for row in old_rows]
    owner = _owners(rows, nodes)
    if type(horizon) is not int or horizon <= 0 or not 0 <= host < len(rows):
        raise ValueError("positive horizon and known host required")
    if set(old_start) != nodes or any(type(t) is not int or t < 0 for t in old_start.values()):
        raise ValueError("complete nonnegative integer reference starts required")
    word = list(region_word)
    region = set(word)
    if not word or len(region) != len(word) or not region <= nodes or len(word) > 64:
        raise ValueError("one complete, unique regional word of at most 64 operations required")
    position = {u: i for i, u in enumerate(word)}
    for (u, v) in model.lags:
        if u in region and v in region and position[u] >= position[v]:
            raise ValueError("regional word violates true data precedence")
    outside = nodes - region
    if not outside:
        raise NoCandidate("no_exterior_to_protect")
    new_owner = {u: host if u in region else owner[u] for u in nodes}
    # The exterior skeleton preserves ONLY same-resource execution constraints.
    exlags = {(u, v): lag for (u, v), lag in model.lags.items()
              if u in outside and v in outside}
    for row in _pipe_orders(rows, model.pipe, region).values():
        for u, v in zip(row, row[1:]):
            exlags[u, v] = max(exlags.get((u, v), 0), 0)
    exsucc = _adj(outside, exlags)
    exorder = topological(exsucc)
    for u in outside:
        if old_start[u] < model.release[u] or old_start[u] + model.duration[u] > horizon:
            raise NoCandidate("exterior_reference_not_feasible", str(u))
    for (u, v), lag in exlags.items():
        if old_start[u] + model.duration[u] + lag > old_start[v]:
            raise NoCandidate("exterior_reference_not_feasible", str((u, v)))
    latest = {}
    for u in reversed(exorder):
        latest[u] = min([horizon - model.duration[u]] + [
            latest[v] - model.duration[u] - exlags[u, v] for v in exsucc[u]])
        if latest[u] < old_start[u]:
            raise AssertionError("latest envelope violated a checked feasible reference")
    reserve = {u: (old_start[u] + latest[u]) // 2 for u in outside}
    # One common scalar interpolation is essential; arbitrary independent slack
    # consumption would not necessarily preserve exterior dependencies.
    calendars = {}
    for u in outside:
        calendars.setdefault((owner[u], model.pipe[u]), []).append(
            (reserve[u], reserve[u] + model.duration[u], u))
    for row in calendars.values():
        row.sort()
        if any(a[1] > b[0] for a, b in zip(row, row[1:])):
            raise AssertionError("joint exterior envelope overlaps a Pipe")
    pred = {u: [] for u in nodes}
    for (u, v), lag in model.lags.items():
        pred[v].append((u, lag))
    # Absolute regional completion deadlines, propagated through data and the
    # chosen same-Pipe regional order. The full word is NOT a serial task.
    inner = {(u, v): lag for (u, v), lag in model.lags.items()
             if u in region and v in region}
    bypipe = {}
    for u in word:
        bypipe.setdefault(model.pipe[u], []).append(u)
    for row in bypipe.values():
        for u, v in zip(row, row[1:]):
            inner[u, v] = max(inner.get((u, v), 0), 0)
    rsucc = _adj(region, inner)
    due = {u: horizon for u in region}
    for (u, v), lag in model.lags.items():
        if u in region and v in outside:
            due[u] = min(due[u], reserve[v] - lag)
    for u in reversed(topological(rsucc)):
        for v in rsucc[u]:
            due[u] = min(due[u], due[v] - model.duration[v] - inner[u, v])
    witness = dict(reserve)
    cursor = dict.fromkeys(bypipe, 0)
    last_end = dict.fromkeys(bypipe, 0)
    scanned = 0
    for u in word:
        p, duration = model.pipe[u], model.duration[u]
        begin = max([model.release[u], last_end[p]] + [
            witness[v] + model.duration[v] + lag for v, lag in pred[u]])
        occupied = calendars.get((host, p), [])
        j = cursor[p]
        while j < len(occupied):
            left, right, _ = occupied[j]
            if right <= begin:
                j += 1; scanned += 1
            elif begin + duration <= left:
                break
            else:
                begin = right
                j += 1; scanned += 1
        cursor[p] = j
        if begin + duration > due[u]:
            raise NoCandidate("no_fit_for_frozen_midpoint_and_word",
                              f"op={u}; earliest_end={begin+duration}; deadline={due[u]}")
        witness[u] = begin
        last_end[p] = begin + duration
    for u in nodes:
        if witness[u] < model.release[u] or witness[u] + model.duration[u] > horizon:
            raise AssertionError("witness release/horizon failure")
    for (u, v), lag in model.lags.items():
        if witness[u] + model.duration[u] + lag > witness[v]:
            raise AssertionError("witness data constraint failure")
    result_rows, global_word, pipes = lift_priority(model, rows, word, new_owner, witness)
    return {
        'rows': result_rows,
        'global_priority_order': global_word,
        'regional_word': word,
        'witness_start': witness,
        'exterior_latest_start': latest,
        'exterior_reserved_start': reserve,
        'regional_completion_deadline': due,
        'pipe_orders': {f'{c}:{p}': row for (c, p), row in sorted(pipes.items())},
        'calendar_intervals_visited': scanned,
        'fixed_service_witness_valid': True,
        'official_nonregression_certified': False,
        'official_scoring_calls': 0,
        'scope': 'Feasible fixed-service witness and priority lift only. No official Makespan prediction.',
    }


def emit_plan(baseline_plan: dict, recovered: dict) -> dict:
    mapping = baseline_plan['node_to_subgraph']
    rows = recovered['rows']
    flat = [u for row in rows for u in row]
    if set(mapping) != {str(u) for u in flat} or len(flat) != len(set(flat)):
        raise ValueError("original operation coverage differs")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("singleton subgraphs required")
    return {'node_to_subgraph': dict(mapping),
            'core_schedules': [[mapping[str(u)] for u in row] for row in rows]}
