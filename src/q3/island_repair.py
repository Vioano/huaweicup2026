"""One-pass original-tree island repair in a compute-only frozen environment.

The certificate concerns M/V dependencies, per-pipe FIFO and a supplied remote
lag only. It neither models COPY service/Cache nor proves allocation or E0
nonregression. No evaluator is called. See docs/a/q3/ISLAND_REPAIR.md.
"""
from __future__ import annotations

from .attention_islands import extract
from .attention_rows import _ports, _recognize
from .construct import UnsupportedStructure, derive_multicore_plan, topo
from .gap_calendar import empty, earliest, release, reserve
from .pipe_bound import analyze


def _anchor(index, view, delay):
    """ASAP schedule of original dependencies and the anchor's pipe words."""
    owner = {u: view["core_by_subgraph"][sg] for u, sg in view["mapping"].items()}
    succ = {u: set(index.succ[u]) for u in index.ops}
    for core in range(view["num_cores"]):
        previous = {}
        for sg in view["core_orders"][core]:
            u = view["nodes_by_subgraph"][sg][0]
            pipe = index.ops[u]["pipe"]
            if pipe in previous:
                succ[previous[pipe]].add(u)
            previous[pipe] = u
    starts, finish = dict.fromkeys(index.ops, 0), {}
    for u in topo(index.ops, succ):
        finish[u] = starts[u] + index.duration(u)
        for v in succ[u]:
            lag = delay if v in index.succ[u] and owner[u] != owner[v] else 0
            starts[v] = max(starts[v], finish[u] + lag)
    return owner, starts, finish


def _exit_ports(index, ports, members):
    """Every external destination separately, plus graph outputs/dead sinks."""
    exits = []
    for u in sorted(members):
        for tensor in sorted(ports.outputs[u]):
            outside = ports.consumers[tensor] - members
            for consumer in sorted(outside):
                exits.append((u, tensor, consumer if consumer in index.ops else None))
            if not ports.consumers[tensor]:
                exits.append((u, tensor, None))
        if not ports.outputs[u]:
            exits.append((u, None, None))
    return exits


def _arrivals(exits, end, owners, external_owner, delay):
    return tuple(end[u] + (delay if v is not None and owners[u] != external_owner[v] else 0)
                 for u, _, v in exits)


def construct(index, plan, cross_delay=500):
    """Repair co-located rows/FFNs once, trying <=2 islands x (k-1) helpers.

    Each operation retains its original identity, tensors, and dependencies.
    Releasing only the current block's intervals leaves all outside operations
    frozen. Input releases are individual producer completions. The full exit
    vector must not worsen the current witness, even if a new home control is
    worse. Returned plans are still singleton submissions.
    """
    if type(cross_delay) is not int or cross_delay < 0:
        raise ValueError("cross_delay must be a nonnegative integer")
    ports = _ports(index)
    initial_bound = analyze(index.graph, plan, cross_delay)["with_cross_core_delay"]["lower_bound_cycles"]
    view = derive_multicore_plan(index.graph, plan)
    try:
        rows = _recognize(index, ports)
    except UnsupportedStructure as error:
        if str(error) != "no closed attention query row matched":
            raise
        rows = []  # Pure FFN graphs have no attention row to recognize.
    blocks = extract(index, ports, rows)
    if not blocks:
        raise UnsupportedStructure("no original attention/FFN island matched")
    owner, starts, finish = _anchor(index, view, cross_delay)
    initial_makespan = max(finish.values())
    if initial_makespan != initial_bound:
        raise AssertionError("anchor disagrees with independent pipe bound")
    cores = view["num_cores"]
    roots = {(c, pipe): empty() for c in range(cores) for pipe in ("PIPE_M", "PIPE_V")}
    for u in sorted(index.ops, key=lambda u: (starts[u], u)):
        resource = owner[u], index.ops[u]["pipe"]
        roots[resource] = reserve(roots[resource], starts[u], index.duration(u))
    records = []
    trials = 0

    for block in blocks:
        members = set(block["nodes"])
        homes = {owner[u] for u in members}
        if len(homes) != 1:
            records.append({"sink": block["sink"], "status": "already_split"})
            continue
        home = next(iter(homes))
        word = sorted(members, key=lambda u: (starts[u], u))
        exits = _exit_ports(index, ports, members)
        if not exits:
            raise AssertionError("a finite block must have an exit")
        current = _arrivals(exits, finish, owner, owner, cross_delay)
        current_peak = max(finish[u] for u in members)
        free_roots = dict(roots)
        for u in word:
            resource = owner[u], index.ops[u]["pipe"]
            free_roots[resource] = release(free_roots[resource], starts[u], index.duration(u))

        def trial(island, helper):
            nonlocal trials
            trials += 1
            local_owner = {u: helper if u in island else home for u in members}
            local_start, local_end = {}, {}
            trial_roots = dict(free_roots)  # 2k persistent root pointers, not V intervals.
            for u in word:
                at = 0
                for p in index.pred[u]:
                    done = local_end[p] if p in members else finish[p]
                    source = local_owner[p] if p in members else owner[p]
                    at = max(at, done + (cross_delay if source != local_owner[u] else 0))
                resource = local_owner[u], index.ops[u]["pipe"]
                local_start[u] = earliest(trial_roots[resource], at, index.duration(u))
                local_end[u] = local_start[u] + index.duration(u)
                trial_roots[resource] = reserve(trial_roots[resource], local_start[u], index.duration(u))
            vector = _arrivals(exits, local_end, local_owner, owner, cross_delay)
            peak = max(local_end.values())
            return (vector, peak, local_owner, local_start, local_end, trial_roots)

        control = trial(frozenset(), home)
        safe_control = (all(a <= b for a, b in zip(control[0], current))
                        and control[1] <= initial_makespan)
        if not safe_control:
            records.append({"sink": block["sink"], "status": "home_control_rejected"})
            continue
        best, selected = control, None
        def key(candidate):
            return max(candidate[0]), sum(candidate[0]), candidate[1]
        for number, island_nodes in enumerate(block["islands"]):
            island = frozenset(island_nodes)
            for helper in range(cores):
                if helper == home:
                    continue
                candidate = trial(island, helper)
                if (all(a <= b for a, b in zip(candidate[0], control[0]))
                        and candidate[1] <= initial_makespan and key(candidate) < key(best)):
                    best, selected = candidate, (number, helper)
        if key(best) >= (max(current), sum(current), current_peak):
            records.append({"sink": block["sink"], "status": "unchanged"})
            continue
        vector, _, new_owner, new_start, new_end, roots = best
        owner.update(new_owner)
        starts.update(new_start)
        finish.update(new_end)
        records.append({"sink": block["sink"], "kind": block["kind"],
                        "status": "island" if selected is not None else "home_control",
                        "island_helper": selected,
                        "exits": [{"producer": u, "tensor": t, "consumer": v,
                                   "before": before, "after": after}
                                  for (u, t, v), before, after in zip(exits, current, vector)]})

    mapping = plan["node_to_subgraph"]
    word = sorted(index.ops, key=lambda u: (starts[u], u))
    schedules = [[] for _ in range(cores)]
    for u in word:
        schedules[owner[u]].append(view["mapping"][u])
    candidate = {"node_to_subgraph": dict(mapping), "core_schedules": schedules}
    derive_multicore_plan(index.graph, candidate)
    bound = analyze(index.graph, candidate, cross_delay)["with_cross_core_delay"]["lower_bound_cycles"]
    witness = max(finish.values())
    if not bound <= witness <= initial_makespan:
        raise AssertionError("final FIFO certificate does not preserve the compute witness")
    improved = bound < initial_makespan
    return (candidate if improved else plan), {
        "schema": "q3-original-island-repair-v1", "official_evaluations": 0,
        "official_nonregression_proved": False, "memory_feasibility_proved": False,
        "initial_compute_bound": initial_bound, "candidate_compute_bound": bound,
        "stitched_compute_witness": witness, "returned_candidate": improved,
        "local_trials": trials, "blocks": records,
    }
