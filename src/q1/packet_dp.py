"""Conditional packet DP for private homogeneous M -> V+ -> M chains.

This generates one legal P1 candidate using rational response costs. It does
not claim official E0/global optimality and is not wired into the portfolio.
The actual final plan is recompiled by the frozen official compiler and checked
against every profiled signature; no archived Step1 transcription is used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.q1.capacity_return import author
from src.q1.response_compile import UnsupportedResponse, compile_plan
from src.q1.response_oracle import quotient, simulate


def shortest_packet_path(states, normal, drains):
    """Lexicographic (cycles, COPY bytes, synchronous Task groups) shortest path.

    A drain clears pending returns without consuming a block. Only one drain
    closure is needed per layer because no other zero-block transition exists.
    Costs include one gate per Task; the caller removes the initial gate.
    """
    def plus(a, b):
        return tuple(x + y for x, y in zip(a, b))

    def close(layer, table):
        answer = dict(table)
        for pending, (cost, path) in table.items():
            if pending and pending in drains[layer]:
                candidate = plus(cost, drains[layer][pending])
                if 0 not in answer or candidate < answer[0][0]:
                    answer[0] = (candidate, (path, ("drain", layer, pending, 0)))
        return answer

    current = {0: ((0, 0, 0), None)}
    for layer, edges in enumerate(normal):
        following = {}
        for pending, (cost, path) in close(layer, current).items():
            for next_pending in states:
                if (pending, next_pending) not in edges:
                    continue
                candidate = plus(cost, edges[pending, next_pending])
                if next_pending not in following or candidate < following[next_pending][0]:
                    following[next_pending] = (
                        candidate, (path, ("normal", layer, pending, next_pending)))
        current = following
    current = close(len(normal), current)
    if 0 not in current:
        raise UnsupportedResponse("no accepted synchronous packet path")
    cost, path = current[0]
    actions = []
    while path is not None:
        path, action = path
        actions.append(action)
    return cost, list(reversed(actions))


class _TaskProjection:
    """Preserve a Task's exact boundary predicates in a small original graph.

    Tensors with both local consumers and outside consumers need an excluded
    COPY_OUT marker: otherwise removing outside consumers would erase a required
    output boundary. Original compute IDs/attributes and direct edges survive.
    Full-plan signature/byte checks below audit this projection before return.
    """
    def __init__(self, graph, view):
        self.view = view
        self.eligible = {u for u, op in view.ops.items() if op["op"] not in author.COPY}
        self.next_id = max(set(view.ops) | set(view.tensors), default=0) + 1
        self.direct = {u: [] for u in self.eligible}
        for edge in graph["edges"]:
            if edge["source"] in self.eligible and edge["target"] in self.eligible:
                self.direct[edge["source"]].append(edge)

    def graph(self, nodes):
        ns = set(nodes)
        v = self.view
        touched = set().union(*(v.in_t[u] | v.out_t[u] for u in ns))
        ops = [dict(v.ops[u]) for u in sorted(ns)]
        tensors = [dict(v.tensors[t]) for t in sorted(touched)]
        edges = []
        extra = self.next_id
        for tid in sorted(touched):
            producers = v.producers[tid] & ns
            consumers = v.consumers[tid] & ns
            edges.extend(dict(source=u, target=tid) for u in sorted(producers))
            edges.extend(dict(source=tid, target=u) for u in sorted(consumers))
            outside = (v.consumers[tid] & self.eligible) - ns
            original_output = any(v.ops[u]["op"] == "COPY_OUT" for u in v.consumers[tid])
            if producers and consumers and (outside or original_output):
                ops.append(dict(id=extra, op="COPY_OUT", pipe="PIPE_MTE3", cycles=1))
                tensors.append(dict(id=extra + 1, pos="DDR", size=v.tensors[tid]["size"]))
                edges.extend((dict(source=tid, target=extra),
                              dict(source=extra, target=extra + 1)))
                extra += 2
        for u in sorted(ns):
            edges.extend(dict(edge) for edge in self.direct[u] if edge["target"] in ns)
        return dict(ops=ops, tensors=tensors, edges=edges)


def construct(graph, cores, capacity=None, bandwidth=60, gate=100,
              max_task_compiles=10000, state_mode="auto", profile_cache="none"):
    if type(cores) is not int or not 2 <= cores <= 5:
        raise ValueError("packet DP requires an integer core count in 2..5")
    capacity = {"L1": 524288, "UB": 131072} if capacity is None else dict(capacity)
    if set(capacity) != {"L1", "UB"} or any(type(v) is not int or v <= 0 for v in capacity.values()):
        raise ValueError("positive L1 and UB capacity required")
    if type(gate) is not int or gate < 0 or type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("invalid gate or bandwidth")
    if type(max_task_compiles) is not int or max_task_compiles < 1:
        raise ValueError("invalid static compilation budget")
    if state_mode not in ("three", "full", "auto"):
        raise ValueError("state_mode must be three, full, or auto")
    if profile_cache not in ("none", "ordered-graph"):
        raise ValueError("profile_cache must be none or ordered-graph")
    began = time.perf_counter()
    view, chains, _, _, _ = author.recognize(graph)

    def footprint(nodes):
        tids = set().union(*(view.in_t[u] | view.out_t[u] for u in nodes))
        return {pos: sum(view.tensors[t]["size"] for t in tids
                         if ("UB" if view.tensors[t]["pos"] == "DDR"
                             else view.tensors[t]["pos"]) == pos) for pos in capacity}

    prefix, returning = footprint(chains[0][:-1]), footprint(chains[0][-1:])
    mixed = {pos: prefix[pos] + returning[pos] for pos in capacity}
    # Largest complete symmetric block fitting the conservative mixed footprint.
    # Floor(N/K) also permits a remainder when N is not a multiple of K.
    packet = min([len(chains) // cores] +
                 [capacity[pos] // used for pos, used in mixed.items() if used])
    if packet < 1:
        raise UnsupportedResponse("no complete capacity-feasible symmetric block")
    blocks_count = len(chains) // (cores * packet)
    bins = [chains[core::cores] for core in range(cores)]
    blocks = [[line[j * packet:(j + 1) * packet] for j in range(blocks_count)]
              for line in bins]
    tail_task_bound = sum(bool(line[blocks_count * packet:]) for line in bins)

    def estimate(states):
        count = len(states)
        normal_profiles = count + (blocks_count - 1) * count * count
        drain_profiles = blocks_count * (count - 1)
        transition_compiles = cores * (normal_profiles + drain_profiles)
        # At most one drain after each of B normal blocks, then one tail per
        # core with leftover chains. Final official recompilation covers every
        # generated Task, not merely one representative per transition.
        final_task_bound = cores * 2 * blocks_count + tail_task_bound
        return dict(normal_profiles=normal_profiles, drain_profiles=drain_profiles,
                    transition_task_compiles=transition_compiles,
                    tail_task_compiles=tail_task_bound,
                    final_plan_task_compiles_bound=final_task_bound,
                    total_task_compiles_bound=(transition_compiles + tail_task_bound +
                                               final_task_bound))

    candidates = {"three": tuple(sorted({0, packet - 1, packet})),
                  "full": tuple(range(packet + 1))}
    estimates = {mode: estimate(states) for mode, states in candidates.items()}
    chosen = ("full" if estimates["full"]["total_task_compiles_bound"] <= max_task_compiles
              else "three") if state_mode == "auto" else state_mode
    if estimates[chosen]["total_task_compiles_bound"] > max_task_compiles:
        raise UnsupportedResponse(
            f"{chosen} state Task compilation upper bound "
            f"{estimates[chosen]['total_task_compiles_bound']} exceeds budget "
            f"{max_task_compiles} before compilation")
    states = candidates[chosen]
    projection = _TaskProjection(graph, view)
    compiled_count = 0
    response_cache, signatures, rejected = {}, {}, []
    profile_entries = {}
    profile_requests = profile_hits = 0

    def ordered_graph_key(local, nodes):
        """Candidate key only; equivalence for unselected edges is unproved.

        Normalize the joint original op/tensor ID space, but preserve each
        list's order and every other attribute. The compute member set is a
        separate part of the key because the projected graph may contain an
        excluded COPY_OUT marker not submitted as a compute member.
        """
        ids = sorted({item["id"] for item in local["ops"] + local["tensors"]})
        ranks = {ident: rank for rank, ident in enumerate(ids)}
        normalized = {
            "ops": [{**op, "id": ranks[op["id"]]} for op in local["ops"]],
            "tensors": [{**tensor, "id": ranks[tensor["id"]]}
                        for tensor in local["tensors"]],
            "edges": [{**edge, "source": ranks[edge["source"]],
                       "target": ranks[edge["target"]]}
                      for edge in local["edges"]],
        }
        return (json.dumps(normalized, sort_keys=True, separators=(",", ":")),
                tuple(sorted(ranks[u] for u in nodes)))

    def members(core, j, pending, following, drain=False):
        old = blocks[core][j - 1][-pending:] if pending else []
        if drain:
            return [chain[-1] for chain in old]
        new = blocks[core][j]
        whole = new[:packet - following]
        cut = new[packet - following:] if following else []
        return ([u for chain in whole for u in chain] +
                [u for chain in cut for u in chain[:-1]] +
                [chain[-1] for chain in old])

    def compile_members(nodes):
        nonlocal compiled_count, profile_requests, profile_hits
        profile_requests += 1
        local = projection.graph(nodes)
        key = ordered_graph_key(local, nodes) if profile_cache == "ordered-graph" else None
        if key is not None and key in profile_entries:
            profile_hits += 1
            # Cached original_id belongs to the representative projected
            # Task. It is never used for a final-plan trace or validation.
            return profile_entries[key]
        if compiled_count >= max_task_compiles:
            raise RuntimeError("static Task compilation budget exhausted")
        compiled_count += 1
        plan = dict(node_to_subgraph={str(u): 0 for u in nodes}, core_schedules=[[0]])
        lines, certificate = compile_plan(local, plan, capacity, bandwidth)
        result = lines[0][0], certificate["traffic"]["scheduled_copy_bytes"]
        if key is not None:
            profile_entries[key] = result
        return result

    def profile(j, pending, following, drain=False):
        tasks, traffic = [], 0
        key = (j, pending, following, drain)
        try:
            for core in range(cores):
                task, count = compile_members(members(core, j, pending, following, drain))
                tasks.append(task)
                traffic += count
        except UnsupportedResponse as error:
            rejected.append(dict(transition=key, reason=str(error)))
            return None
        signature = tasks[0].signature()
        if any(task.signature() != signature for task in tasks[1:]):
            rejected.append(dict(transition=key, reason="different compiled signatures"))
            return None
        signatures[key] = signature
        if signature not in response_cache:
            response_cache[signature] = simulate([[tasks[0].scaled_ddr(cores)]], gate)["makespan"]
        return response_cache[signature] + gate, traffic, 1

    normal, drains = [], []
    for j in range(blocks_count + 1):
        drain_cost = {}
        if j:
            for pending in states:
                if pending:
                    value = profile(j, pending, 0, True)
                    if value is not None:
                        drain_cost[pending] = value
        drains.append(drain_cost)
        if j == blocks_count:
            break
        edges = {}
        for pending in states if j else (0,):
            for following in states:
                value = profile(j, pending, following)
                if value is not None:
                    edges[pending, following] = value
        normal.append(edges)
    score, actions = shortest_packet_path(states, normal, drains)
    tail_nodes = [[u for chain in line[blocks_count * packet:] for u in chain] for line in bins]
    tails, tail_traffic = [], 0
    for nodes in tail_nodes:
        if nodes:
            task, count = compile_members(nodes)
            tails.append([task])
            tail_traffic += count
        else:
            tails.append([])
    tail_response = simulate(tails, gate)["makespan"] if any(tails) else 0
    predicted = score[0] - gate + (gate + tail_response if any(tails) else 0)

    mapping, orders, next_task = {}, [[] for _ in range(cores)], 0
    for core in range(cores):
        for kind, j, pending, following in actions:
            nodes = members(core, j, pending, following, kind == "drain")
            orders[core].append(next_task)
            for u in nodes:
                if u in mapping:
                    raise AssertionError("duplicate compute membership")
                mapping[u] = next_task
            next_task += 1
        if tail_nodes[core]:
            orders[core].append(next_task)
            mapping.update({u: next_task for u in tail_nodes[core]})
            next_task += 1
    plan = dict(node_to_subgraph={str(op["id"]): mapping[op["id"]]
                                 for op in graph["ops"] if op["op"] not in author.COPY},
                core_schedules=orders)
    author.validate_plan_structure(graph, plan)
    if compiled_count + next_task > max_task_compiles:
        raise RuntimeError("final-plan static compilation exceeds budget")
    actual_lines, certificate = compile_plan(graph, plan, capacity, bandwidth)
    compiled_count += next_task
    for core, line in enumerate(actual_lines):
        for i, (kind, j, pending, following) in enumerate(actions):
            if line[i].signature() != signatures[j, pending, following, kind == "drain"]:
                raise UnsupportedResponse("full-plan signature differs from projected transition")
        if tail_nodes[core] and line[-1].signature() != tails[core][0].signature():
            raise UnsupportedResponse("full-plan tail signature differs from projection")
    actual_response = quotient(actual_lines, gate)
    if actual_response["makespan"] != predicted:
        raise AssertionError("DP response does not match recompiled full plan")
    scheduled_bytes = certificate["traffic"]["scheduled_copy_bytes"]
    if scheduled_bytes != score[1] + tail_traffic:
        raise UnsupportedResponse("full-plan boundary bytes differ from projected costs")
    return plan, dict(algorithm_id="q1-packet-response-dp",
                     variant=f"{chosen}-state-rational-v3-{profile_cache}",
                     chains=len(chains), cores=cores, packet=packet, states=states,
                     state_mode_requested=state_mode, state_mode_chosen=chosen,
                     state_compile_estimates=estimates,
                     profile_cache=profile_cache, profile_requests=profile_requests,
                     profile_hits=profile_hits, profile_entries=len(profile_entries),
                     complete_rounds=blocks_count, actions=actions, tasks=next_task,
                     profiled_transitions=len(signatures), unique_responses=len(response_cache),
                     static_task_compiles=compiled_count, max_task_compiles=max_task_compiles,
                     rejected_transitions=rejected, model_makespan=predicted,
                     model_scheduled_copy_bytes=scheduled_bytes, response=actual_response,
                     compilation_certificate=certificate,
                     construction_seconds=time.perf_counter() - began,
                     official_scoring_calls={"E0": 0, "E1": 0, "E2": 0},
                     scope=("Candidate ordered-graph cache agreement checked on the selected "
                            "final plan; equivalence for all unselected edges is unproved; "
                            "not E0 or global optimality" if profile_cache != "none" else
                            "Conditional rational-model template optimum; not E0 or global optimum"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--state-mode", choices=("auto", "three", "full"), default="auto")
    parser.add_argument("--max-task-compiles", type=int, default=10000)
    parser.add_argument("--profile-cache", choices=("none", "ordered-graph"),
                        default="none")
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite outputs")
    started = time.perf_counter()
    plan, details = construct(json.loads(args.graph.read_bytes()), args.cores,
                              max_task_compiles=args.max_task_compiles,
                              state_mode=args.state_mode,
                              profile_cache=args.profile_cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(plan, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    details["read_to_plan_fsync_seconds"] = time.perf_counter() - started
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.diagnostics.open("x") as stream:
        json.dump(details, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
