"""Research variant: keep all requested cores for the shared-input window split.

This is a graph-domain structural candidate, not an E0 makespan prediction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from src.q1.shared_input_budget import _view, _size, _refine, bounded_construct
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

INPUT_BUDGET_BYTES = 262144
ACTIVATION_BYTES = 524288
MAX_PHASES = 32


class UnsupportedStructure(ValueError):
    pass


def construct(graph, cores):
    if type(cores) is not int or not 2 <= cores <= 5:
        raise ValueError("cores must be an integer in 2..5")
    view = _view(graph)
    external_bytes = _size(view["external"], view)
    if len(view["components"]) < cores or external_bytes <= ACTIVATION_BYTES:
        raise UnsupportedStructure("requires at least K components and >524288 external input bytes")
    base, base_info = bounded_construct(graph, cores)
    plan, details = _refine(base, view, INPUT_BUDGET_BYTES, MAX_PHASES, cores)
    result = derive_multicore_plan(graph, plan)
    validate_task_order(result)
    owner = result["core_by_subgraph"]
    if len(plan["core_schedules"]) != cores or any(not order for order in plan["core_schedules"]):
        raise AssertionError("full-core policy did not activate every requested core")
    if any(owner[a] != owner[b] for a, b in result["dependency_pairs"]):
        raise AssertionError("remote Task dependency introduced")
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    for nodes, _, _ in view["components"]:
        if len({owner[mapping[u]] for u in nodes}) != 1:
            raise AssertionError("component spans cores")
    return plan, dict(algorithm_id="q1-shared-input-full-core-research",
                      variant="force-requested-cores-local-windows-v1",
                      selected="shared-input-full-core", requested_cores=cores,
                      active_cores=cores, components=len(view["components"]),
                      external_input_bytes=external_bytes,
                      input_budget_bytes=INPUT_BUDGET_BYTES,
                      activation_bytes=ACTIVATION_BYTES, max_phases=MAX_PHASES,
                      base=base_info, task_refinements=details,
                      tasks=len(result["subgraph_ids"]),
                      scope="Structural construction only; DDR/FIFO/memory behavior and E0 quality unmodeled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    began = time.perf_counter()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores)
    info["cli_body_through_construction_seconds"] = time.perf_counter() - began
    info["timing_scope"] = "External process wall includes startup and output writes"
    for path, data in ((args.output, plan), (args.diagnostics, info)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as out:
            json.dump(data, out, separators=(",", ":"))
            out.write("\n")


if __name__ == "__main__":
    main()
