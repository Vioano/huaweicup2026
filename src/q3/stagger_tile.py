"""Guarded static staggered tiling of original left-deep reduction trees.

The service expression ranks finite shapes. It is not an official time bound.
No Task, Step2, Step3, or evaluator is called.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from heapq import heappop, heappush

from .construct import UnsupportedStructure, derive_multicore_plan
from .forest_reuse_grid import recognize
from .leaf_tile import _capacity, _chains, _tiles


def _ceil(a, b):
    return (a + b - 1) // b


def _ports(index, words):
    """Check the exact original boundary and return tensor ports and sizes."""
    graph = index.graph
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    ins, outs, readers, producers = (defaultdict(set) for _ in range(4))
    for e in graph["edges"]:
        x, y = e["source"], e["target"]
        if x in tensors and y in ops:
            ins[y].add(x)
            readers[x].add(y)
        elif x in ops and y in tensors:
            outs[x].add(y)
            producers[y].add(x)
        else:
            raise UnsupportedStructure("requires original tensor-mediated ports")
    external, expected_copies = set(), set()
    for leaves, adds in words.values():
        for u in leaves:
            if len(ins[u]) != 2 or len(outs[u]) != 1:
                raise UnsupportedStructure("exact MATMUL ports required")
            for tid in ins[u]:
                if len(producers[tid]) != 1:
                    raise UnsupportedStructure("external input needs unique producer")
                cp = next(iter(producers[tid]))
                if ops[cp]["op"] != "COPY_IN" or len(ins[cp]) != 1 or len(outs[cp]) != 1:
                    raise UnsupportedStructure("exact boundary COPY_IN required")
                source = next(iter(ins[cp]))
                if (tensors[source]["pos"] != "DDR" or
                        tensors[source]["size"] != tensors[tid]["size"] or
                        producers[source] or
                        readers[source] != {cp}):
                    raise UnsupportedStructure("COPY_IN backing differs")
                external.add(tid)
                expected_copies.add(cp)
        for u in adds:
            if len(ins[u]) != 2 or len(outs[u]) != 1:
                raise UnsupportedStructure("exact ADD ports required")
        for u in leaves + adds:
            tid = next(iter(outs[u]))
            if producers[tid] != {u}:
                raise UnsupportedStructure("compute output has another producer")
            if u == adds[-1]:
                if len(readers[tid]) != 1:
                    raise UnsupportedStructure("root needs one COPY_OUT")
                cp = next(iter(readers[tid]))
                if (ops[cp]["op"] != "COPY_OUT" or len(ins[cp]) != 1 or len(outs[cp]) != 1):
                    raise UnsupportedStructure("root needs exact COPY_OUT")
                target = next(iter(outs[cp]))
                if (tensors[target]["pos"] != "DDR" or
                        tensors[target]["size"] != tensors[tid]["size"] or
                        producers[target] != {cp} or readers[target]):
                    raise UnsupportedStructure("COPY_OUT backing differs")
                expected_copies.add(cp)
            elif len(readers[tid]) != 1 or next(iter(readers[tid])) not in adds:
                raise UnsupportedStructure("internal output has another reader")
    if {u for u in ops if u not in index.ops} != expected_copies:
        raise UnsupportedStructure("unrecognized boundary COPY")
    if any(readers[t] - set(index.ops) for t in external):
        raise UnsupportedStructure("external input has another reader")
    return {u: tuple(sorted(ins[u])) for u in index.ops}, {
        u: next(iter(outs[u])) for u in index.ops}, external, {
        tid: t["size"] for tid, t in tensors.items()}


def _word(words, cells, length):
    pending = None
    out = []
    for t in range(length):
        for _, _, cid in sorted(cells):
            leaves, adds = words[cid]
            out.append(leaves[t])
            if pending is not None:
                out.append(pending)
            pending = adds[t - 1] if t else None
    if pending is not None:
        out.append(pending)
    return out


def _envelope(word, ins, outs, external, sizes):
    """Exact closed-window future-input mass plus live original outputs."""
    first, last = {}, {}
    for j, u in enumerate(word):
        for tid in (*ins[u], outs[u]):
            first.setdefault(tid, j)
            last[tid] = j
    starts = defaultdict(list)
    ends = defaultdict(list)
    for tid, j in first.items():
        starts[j].append(tid)
        ends[last[tid]].append(tid)
    live_outputs = input_bytes = right = peak = 0
    right = -1
    heap = []
    counts = Counter()
    witness = None
    for j, u in enumerate(word):
        for tid in starts[j]:
            heappush(heap, (-last[tid], tid))
            if tid not in external:
                live_outputs += sizes[tid]
        while heap and -heap[0][0] < j:
            heappop(heap)
        horizon = max(j, -heap[0][0])
        while right < horizon:
            right += 1
            for tid in ins[word[right]]:
                if tid in external:
                    if not counts[tid]:
                        input_bytes += sizes[tid]
                    counts[tid] += 1
        total = live_outputs + input_bytes
        if total > peak:
            peak = total
            witness = {"position": j, "horizon": horizon,
                       "output_bytes": live_outputs, "future_input_bytes": input_bytes}
        for tid in ins[u]:
            if tid in external:
                counts[tid] -= 1
                if not counts[tid]:
                    input_bytes -= sizes[tid]
        for tid in ends[j]:
            if tid not in external:
                live_outputs -= sizes[tid]
    if live_outputs or input_bytes:
        raise AssertionError("future-use window did not close")
    return peak, witness


def transform(index, plan, capacity, bandwidth=60):
    """Return a two-field singleton plan and static, conditional metadata."""
    c = _capacity(capacity)
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("positive integer bandwidth required")
    view = derive_multicore_plan(index.graph, plan)
    if any(len(nodes) != 1 for nodes in view["nodes_by_subgraph"].values()):
        raise UnsupportedStructure("requires singleton subgraphs")
    model = recognize(index)
    words, a, b, s, length = _chains(index, model)
    ins, outs, external, sizes = _ports(index, words)
    m_cycles = {index.ops[u]["cycles"] for leaves, _ in words.values() for u in leaves}
    add_cycles = {index.ops[u]["cycles"] for _, adds in words.values() for u in adds}
    if (len(m_cycles) != 1 or len(add_cycles) != 1 or
            next(iter(m_cycles)) <= 0 or next(iter(add_cycles)) <= 0):
        raise UnsupportedStructure("uniform positive MATMUL and ADD cycles required")
    mu = next(iter(m_cycles))
    nu = next(iter(add_cycles))
    if mu < nu:
        raise UnsupportedStructure("stagger service template requires M cycles >= ADD cycles")
    owner = {}
    for cid, component in enumerate(index.components):
        cores = {view["core_by_subgraph"][view["mapping"][u]] for u in component}
        if len(cores) != 1:
            raise UnsupportedStructure("an original tree is split across cores")
        owner[cid] = next(iter(cores))
    k = view["num_cores"]
    m, n = map(len, model["axes"])
    work = [sum(owner[cid] == core for cid in owner) * length * mu for core in range(k)]
    best = None
    feasible = 0
    for p in range(1, m + 1):
        for q in range(1, n + 1):
            tiles = _tiles(model, owner, p, q)
            read = [0] * k
            units = [0] * k
            count = [0] * k
            peak = [0] * k
            fits = True
            for (core, _, _), cells in tiles.items():
                d = len(cells)
                rows = len({i for i, _, _ in cells})
                cols = len({j for _, j, _ in cells})
                envelope, _ = _envelope(_word(words, cells, length), ins, outs, external, sizes)
                coexist = (d + 3) * s + rows * a + cols * b + a + b
                if envelope > c or coexist > c:
                    fits = False
                    break
                read[core] += length * (rows * a + cols * b)
                units[core] += length * (rows * _ceil(a, bandwidth) + cols * _ceil(b, bandwidth))
                count[core] += 1
                peak[core] = max(peak[core], envelope)
            if not fits:
                continue
            feasible += 1
            service = [work[core] + 2 * k *
                       (units[core] + sum(owner[cid] == core for cid in owner) * _ceil(s, bandwidth)) +
                       count[core] * nu for core in range(k)]
            key = (max(service), sum(read), max(peak), p, q)
            if best is None or key < best[0]:
                best = (key, tiles, read, peak, service)
    if best is None:
        raise UnsupportedStructure("no stagger tile satisfies both static capacity guards")
    (_, _, _, p, q), tiles, read, peak, service = best
    per_core = [[] for _ in range(k)]
    for (core, _, _), cells in sorted(tiles.items(), key=lambda x: (x[0][1], x[0][2], x[0][0])):
        per_core[core].extend(_word(words, cells, length))
    for sequence in per_core:
        position = {u: j for j, u in enumerate(sequence)}
        for u in sequence:
            if any(pred not in position or position[pred] >= position[u] for pred in index.pred[u]):
                raise AssertionError("original precedence changed")
    if len({u for seq in per_core for u in seq}) != len(index.ops) or sum(map(len, per_core)) != len(index.ops):
        raise AssertionError("compute operation cover changed")
    candidate = {"node_to_subgraph": dict(plan["node_to_subgraph"]),
                 "core_schedules": [[view["mapping"][u] for u in seq] for seq in per_core]}
    updated = derive_multicore_plan(index.graph, candidate)
    if updated["mapping"] != view["mapping"] or updated["core_by_subgraph"] != view["core_by_subgraph"]:
        raise AssertionError("mapping or original owner changed")
    return candidate, {"strategy": "stagger_tile", "tile_shape": [p, q],
                       "axis_sizes": [m, n], "leaf_count": length,
                       "feasible_shapes": feasible, "protected_bound_bytes_by_core": peak,
                       "conditional_input_copy_bound_bytes_by_core": read,
                       "conditional_service_proxy_by_core": service,
                       "tiles_by_core": [sum(key[0] == core for key in tiles) for core in range(k)],
                       "selection": "min(max conditional service proxy, total input bound, max future-use envelope, p, q)",
                       "scope": "static guarded shape ranking; no official Makespan or total-spill guarantee",
                       "official_evaluations": 0}
