"""Opt-in synthetic Task-cache contract probe; never calls E0/E1/E2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.review.p1_memory_key_contract import FIXTURE_HASHES, sha, source_scope


class CompileBudget:
    def __init__(self, limit=8):
        self.limit = limit
        self.attempts_reserved = 0
        self.confirmed_completed = 0

    def reserve(self):
        if self.attempts_reserved >= self.limit:
            raise RuntimeError("synthetic Task compile budget exhausted before call")
        self.attempts_reserved += 1


def create_output(path, *, execute):
    if not execute:
        raise ValueError("explicit --execute required")
    path.mkdir(parents=False, exist_ok=False)


def _load_fixture(directory, output):
    paths = {name: directory / name for name in FIXTURE_HASHES}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError(f"frozen synthetic fixture missing or changed: {name}")
        shutil.copyfile(path, output / name)  # preserve exact source bytes
    for name, path in paths.items():
        if sha(path) != FIXTURE_HASHES[name]:
            raise ValueError(f"frozen synthetic fixture missing or changed: {name}")
    return json.loads(paths["graph.json"].read_text()), paths


def run(directory, output):
    from src.q1.variable_packet import Family
    from src.q1.packet_dp import _TaskProjection
    from src.q1.response_compile import _official_modules
    from src.q1.compiled_memory_response import _check_original, _task
    from src.review.p1_memory_response_cache import DomainContract, MemoryResponseCache

    began = time.perf_counter()
    budget = CompileBudget()
    report = {"kind": "synthetic-cache-contract-NOT-E0", "status": "started",
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}
    try:
        graph, paths = _load_fixture(directory, output)
        capacity, bandwidth = {"L1": 80, "UB": 80}, 60
        scope = source_scope(capacity, bandwidth)
        report.update(fixture_sha256={name: sha(path) for name, path in paths.items()},
                      source_scope=repr(scope), synthetic_capacity=capacity,
                      synthetic_bandwidth=bandwidth)
        family = Family(graph, 1, capacity, bandwidth)
        if len(family.chains) != 2 or any(len(chain) != 4 for chain in family.chains):
            raise ValueError("expected two four-compute private chains")
        scene, plans, step3, validation = _official_modules()
        projection = _TaskProjection(graph, family.view)

        def compile_nodes(nodes):
            if source_scope(capacity, bandwidth) != scope:
                raise ValueError("source/config/runtime drift before independent Task compile")
            local = projection.graph(nodes)
            plan = {"node_to_subgraph": {str(u): 0 for u in nodes},
                    "core_schedules": [[0]]}
            validation.validate_graph(local)
            _check_original(local, capacity)
            view = plans.derive_multicore_plan(local, plan)
            validation.validate_task_order(view)
            budget.reserve()  # before the official Task compiler call
            tasks, _, traffic, _ = scene._build_scene_a_tasks(
                local, plan, bandwidth, capacity)
            budget.confirmed_completed += len(tasks)
            if len(tasks) != 1 or traffic["spill_added_copy_bytes"] != 0:
                raise ValueError("expected exactly one no-spill official Task")
            prepared = next(iter(tasks.values()))
            task, _ = _task(prepared["task_id"], prepared, capacity, bandwidth, step3)
            if source_scope(capacity, bandwidth) != scope:
                raise ValueError("source/config/runtime drift after Task compile")
            return task, traffic, prepared

        cache = MemoryResponseCache(
            family,
            domain_contract=DomainContract(MemoryResponseCache.DOMAIN, reviewed=True),
            compiler=compile_nodes, max_task_compiles=4)
        groups = [tuple(chain) for chain in family.chains]
        groups += [(chain[-1],) for chain in family.chains]
        cached = []
        for nodes in groups + groups:
            start = time.perf_counter()
            item = cache.get(nodes)
            cached.append(item)
            report.setdefault("request_times_seconds", []).append(time.perf_counter() - start)
        if cached[0]["cache_hit"] or cached[1]["cache_hit"]:
            raise ValueError("distinct full-chain release words unexpectedly shared a cache entry")
        checks = []
        for nodes, item in zip(groups, cached[:4]):
            task, traffic, _ = compile_nodes(nodes)  # independent, no cache
            checks.append({"actual_nodes": nodes, "key_digest": item["key_digest"],
                           "signature_equal": item["task"].signature() == task.signature(),
                           "traffic_equal": item["traffic"] == traffic})
        if not all(row["signature_equal"] and row["traffic_equal"] for row in checks):
            raise ValueError("cached Task response differs from independent compilation")
        report.update(status="success", checks=checks,
                      terminal_cross_id_hit=cached[3]["cache_hit"],
                      terminal_key_equal=cached[2]["key_digest"] == cached[3]["key_digest"])
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}",
                      traceback=traceback.format_exc())
        raise
    finally:
        report["task_compile_attempts_reserved"] = budget.attempts_reserved
        report["task_compiles_confirmed_completed"] = budget.confirmed_completed
        report["elapsed_seconds"] = time.perf_counter() - began
        if "cache" in locals():
            report["cache"] = {"requests": cache.requests,
                               "hits": cache.hits, "misses": cache.misses,
                               "compile_attempts": cache.compile_attempts,
                               "compiles_confirmed": cache.compiles_confirmed}
        (output / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=ROOT / "results/a/p1-memory-cache-counterexample-20260925")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    create_output(args.output, execute=args.execute)
    run(args.fixture_dir, args.output)


if __name__ == "__main__":
    main()
