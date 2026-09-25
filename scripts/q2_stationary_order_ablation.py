"""Freeze same-owner stage-major and job-major plans without any evaluator call.

This isolates the submitted priority word from the capacity-aware stage partition.
It does not predict either plan's official Makespan.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))

from evaluation_validation import read_evaluation_config  # noqa: E402
from multicore_cut_evaluate_problem_2 import read_scene_b_config  # noqa: E402
from src.q2_nikolastarx.dag_direct import DAGIndex  # noqa: E402
from src.q2_nikolastarx.direct import derive_multicore_plan  # noqa: E402
from src.q2_nikolastarx.shared_input_wave import _recognize  # noqa: E402
from src.q2_nikolastarx.shared_stationary_pipeline import build_from_index  # noqa: E402
from src.q2_nikolastarx.shared_stationary_wave import _stages  # noqa: E402
from src.q2_nikolastarx.zero_spill_intervals import certify  # noqa: E402


def main() -> None:
    case, cores = "044", 5
    zpath = ROOT / "data/raw/a/official-cases.zip"
    config_path = ROOT / "data/raw/a/official/data/config.txt"
    out = ROOT / "results/a/q2-nikolastarx/stationary-order-ablation-044-20260926"
    with zipfile.ZipFile(zpath) as archive:
        graph_bytes = archive.read(f"data/case_{case}.json")
    graph = json.loads(graph_bytes)
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    index = DAGIndex(graph)
    job_major, detail = build_from_index(index, cores, config)
    by_job, waves, anchor = _recognize(index)
    stages = _stages(index, by_job, waves, anchor)
    bounds = detail["core_stage_bounds"]
    mapping = job_major["node_to_subgraph"]
    rows = [[mapping[str(u)] for stage in stages[a:b] for u in stage]
            for a, b in zip(bounds, bounds[1:])]
    rows.extend([] for _ in range(cores - len(rows)))
    stage_major = {"node_to_subgraph": mapping, "core_schedules": rows}

    def owner(plan):
        return {u: core for core, row in enumerate(plan["core_schedules"])
                for u in row}

    if owner(job_major) != owner(stage_major):
        raise AssertionError("ablation changed core assignment")
    for plan in (job_major, stage_major):
        view = derive_multicore_plan(graph, plan)
        if len(view["mapping"]) != len(index.ops):
            raise AssertionError("structural validation changed coverage")
    out.mkdir(parents=True, exist_ok=True)
    plans = {}
    for label, plan in (("job-major", job_major), ("stage-major-same-owner", stage_major)):
        raw = (json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        path = out / f"{label}-plan.json"
        path.write_bytes(raw)
        plans[label] = {"path": path.relative_to(ROOT).as_posix(),
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "canonical_plan_sha256": hashlib.sha256(
                            json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                        "zero_spill_certificate": certify(graph, plan, config)}
    result = {
        "scope": "Static same-owner priority ablation; no E0/E1/E2, Makespan, or DDR score.",
        "case": case, "cores": cores,
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "same_owner": True, "same_singleton_mapping": True,
        "core_stage_bounds": bounds, "plans": plans,
    }
    (out / "summary.json").write_text(json.dumps(result, ensure_ascii=False,
                                                indent=2, allow_nan=False) + "\n")
    print(json.dumps({"same_owner": True,
                      "job_major_zero_spill": plans["job-major"]["zero_spill_certificate"]["zero_spill_certificate"],
                      "stage_major_zero_spill": plans["stage-major-same-owner"]["zero_spill_certificate"]["zero_spill_certificate"]}))


if __name__ == "__main__":
    main()
