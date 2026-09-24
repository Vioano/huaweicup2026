"""Graph-driven intact PIPE_V fork/join candidates; no scoring.

Paced and root-heavy fusion derive from Fang Stage K
08e5cbf96c57bbfb603ec9661ee591e2adb8c26f, H
4f1b9f8be4bbcc98759a19451c108e62e80abb17, and J
aa3f18a71b117ebd0476c8d714c97d8d366d74d7.
This module generalizes their structural scope, not quality.
"""
from __future__ import annotations

from src.q1.component_pack import _build_op_adjacency, _contract_excluded_copy_nodes
from src.q1.fork_frontier import topo
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


class UnsupportedStructure(ValueError):
    pass


def recognize(graph):
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    if not ops or any(o["pipe"] != "PIPE_V" for o in ops.values()):
        raise UnsupportedStructure("nonempty all-PIPE_V compute graph required")
    full_pred, full_succ = _build_op_adjacency(graph)
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    cp, cs = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    if pred != cp or succ != cs:
        raise UnsupportedStructure("COPY-contracted dependencies differ")
    starts = sorted(u for u in ops if not pred[u])
    previous, seen, rounds = None, set(), []
    while starts:
        if len(starts) < 2 or any(pred[u] != ({previous} if previous is not None else set()) for u in starts):
            raise UnsupportedStructure("invalid fork boundary")
        chains = []
        for start in starts:
            chain, chain_seen, u = [], set(), start
            while True:
                if u in seen or u in chain_seen or len(succ[u]) != 1:
                    raise UnsupportedStructure("nonserial or repeated chain")
                chain.append(u)
                chain_seen.add(u)
                v = next(iter(succ[u]))
                if len(pred[v]) == 2:
                    break
                if pred[v] != {u}:
                    raise UnsupportedStructure("cross-chain or branching edge")
                u = v
            chains.append(chain)
            seen.update(chain)
        descriptors = [tuple((ops[u]["op"], ops[u]["pipe"], ops[u]["cycles"]) for u in c) for c in chains]
        if len(set(descriptors)) != 1 or not descriptors[0]:
            raise UnsupportedStructure("chains differ within a round")
        leaves = {c[-1] for c in chains}
        tail = set()
        pending = {v for u in leaves for v in succ[u]}
        while pending:
            u = pending.pop()
            if u in tail:
                continue
            if u in seen or u not in ops or ops[u]["op"] != "ADD" or len(pred[u]) != 2:
                raise UnsupportedStructure("tail is not binary ADD")
            tail.add(u)
            pending.update(v for v in succ[u] if len(pred[v]) == 2)
        roots = [u for u in tail if not (succ[u] & tail)]
        if len(tail) != len(chains) - 1 or len(roots) != 1:
            raise UnsupportedStructure("tail is not one binary reduction tree")
        root = roots[0]
        stage_inputs = tail | leaves
        if any(not pred[u] <= stage_inputs or
               (u != root and (len(succ[u]) != 1 or not succ[u] <= tail)) for u in tail):
            raise UnsupportedStructure("tail has external or branching edge")
        if seen & tail:
            raise UnsupportedStructure("rounds overlap")
        seen.update(tail)
        next_starts = sorted(succ[root])
        if any(v in seen or pred[v] != {root} for v in next_starts):
            raise UnsupportedStructure("root does not fork to fresh starts")
        rounds.append(dict(chains=chains, tail=topo(tail, {u: succ[u] & tail for u in tail}), root=root))
        previous, starts = root, next_starts
    if seen != ops.keys():
        raise UnsupportedStructure("uncovered compute operations")
    return rounds, pred


def construct(graph, cores, mode="paced"):
    if type(cores) is not int or not 2 <= cores <= 5 or mode not in ("paced", "root-heavy-fused"):
        raise ValueError("cores must be 2..5 and mode paced or root-heavy-fused")
    rounds, pred = recognize(graph)
    mapping, orders, tasks = {}, [[] for _ in range(cores)], []

    def add(core, nodes, stage, phase, chain_indices=(), fused=()):
        if not nodes or any(u in mapping for u in nodes):
            raise AssertionError("empty or duplicate Task")
        tid = len(tasks)
        mapping.update((u, tid) for u in nodes)
        orders[core].append(tid)
        tasks.append(dict(id=tid, core=core, stage=stage, phase=phase,
                          chain_indices=list(chain_indices), fused_reductions=list(fused)))

    for stage, entry in enumerate(rounds):
        chains, tail = entry["chains"], entry["tail"]
        width = len(chains)
        if mode == "paced":
            active = min(cores, width)
            counts = [width // active + int(c < width % active) for c in range(active)]
        elif stage == 0:
            active = min(cores - 1, width)
            counts = [width // active + int(c < width % active) for c in range(active)]
        else:
            foreign = width // cores
            counts = [width - foreign * (cores - 1)] + [foreign] * (cores - 1)
        offset, fused_all = 0, set()
        for core, count in enumerate(counts):
            if not count:
                continue
            indices = list(range(offset, offset + count))
            offset += count
            nodes = [u for i in indices for u in chains[i]]
            if mode == "paced":
                if core == 0 and stage and count >= 2:
                    add(core, chains[indices[0]], stage, 0, indices[:1])
                    add(core, [u for i in indices[1:] for u in chains[i]], stage, 1, indices[1:])
                else:
                    add(core, nodes, stage, 0, indices)
            else:
                members, fused = set(nodes), []
                for u in tail:
                    if u not in fused_all and pred[u] <= members:
                        nodes.append(u)
                        members.add(u)
                        fused.append(u)
                fused_all.update(fused)
                add(core, nodes, stage, 0, indices, fused)
        if offset != width:
            raise AssertionError("chain allocation incomplete")
        residual = [u for u in tail if u not in fused_all] if mode == "root-heavy-fused" else tail
        if residual:
            add(0, residual, stage, 2 if mode == "paced" else 1)
    if set(mapping) != {o["id"] for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}:
        raise AssertionError("compute coverage incomplete")
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)}, "core_schedules": orders}
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    rank = {t["id"]: (t["stage"], t["phase"]) for t in tasks}
    edges = list(view["dependency_pairs"]) + [(a, b) for order in orders for a, b in zip(order, order[1:])]
    if any(rank[a] >= rank[b] for a, b in edges):
        raise AssertionError("joint Task/core order does not advance")
    for entry in rounds:
        for chain in entry["chains"]:
            if len({mapping[u] for u in chain}) != 1:
                raise AssertionError("chain was split")
    return plan, dict(algorithm_id="q1-intact-frontier-research", mode=mode,
                      rounds=len(rounds), widths=[len(e["chains"]) for e in rounds],
                      task_count=len(tasks), tasks=tasks,
                      scope="Structural candidate only; official E0 quality unknown")


def main():
    import argparse
    import json
    import time
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--mode", choices=("paced", "root-heavy-fused"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    began = time.perf_counter()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores, args.mode)
    info["cli_body_through_construction_seconds"] = time.perf_counter() - began
    info["timing_scope"] = "External process wall includes startup and output writes"
    info["source"] = "Fang Stage K/H/J commits documented in module docstring"
    for path, value in ((args.output, plan), (args.diagnostics, info)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as out:
            json.dump(value, out, separators=(",", ":"))
            out.write("\n")


if __name__ == "__main__":
    main()
