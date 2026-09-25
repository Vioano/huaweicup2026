"""Graph-derived return-cut hypothesis; construction only, never a score."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.q1.capacity_return import author
from src.review.p1_return_cut_resource_bound import graph_resources, relaxation


def construct(graph, cores, bandwidth):
    """Return (two-key plan, diagnostics); x is a resource-relaxation proposal."""
    resources = graph_resources(graph, cores, bandwidth)
    bound = relaxation(**resources)
    _, chains, _, _, _ = author.recognize(graph)
    bins = [chains[k::cores] for k in range(cores)]
    cuts = bound["minimum_required_cut_counts_at_bound"]
    if len(cuts) != cores or any(not 0 <= x <= len(line)
                                 for x, line in zip(cuts, bins)):
        raise ValueError("resource relaxation returned invalid cut counts")
    mapping = {}
    schedules = []
    next_task = 0
    for line, cut_count in zip(bins, cuts):
        if not line:
            schedules.append([])
            continue
        whole = line[:-cut_count] if cut_count else line
        cut = line[-cut_count:] if cut_count else []
        first = [u for chain in whole for u in chain]
        first += [u for chain in cut for u in chain[:-1]]
        if not first:
            raise ValueError("Task0 would be empty")
        task0 = next_task
        next_task += 1
        for u in first:
            if str(u) in mapping:
                raise ValueError("duplicate compute node")
            mapping[str(u)] = task0
        order = [task0]
        if cut:
            task1 = next_task
            next_task += 1
            for chain in cut:
                u = chain[-1]
                if str(u) in mapping:
                    raise ValueError("duplicate compute node")
                mapping[str(u)] = task1
            order.append(task1)
        schedules.append(order)
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    author.validate_plan_structure(graph, plan)
    return plan, {
        "algorithm_id": "p1-resource-return-cut-hypothesis-v1",
        "scope": "Fixed private-chain bins; resource x is a falsifiable proposal, not an optimality or capacity certificate",
        "resources": resources, "relaxation": bound,
        "cut_counts": cuts, "per_core_chain_counts": list(map(len, bins)),
        "tasks": next_task,
        "calls": {"Task_compile": 0, "response": 0, "E0": 0, "E1": 0, "E2": 0},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--bandwidth", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("output paths must be distinct and new")
    started = time.perf_counter()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores, args.bandwidth)
    info["constructor_including_read_seconds"] = time.perf_counter() - started
    for path, value in ((args.output, plan), (args.diagnostics, info)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
