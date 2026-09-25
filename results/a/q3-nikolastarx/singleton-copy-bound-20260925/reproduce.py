"""Audit new lower bounds against TWO saved results; zero new official calls."""
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q3.singleton_copy_bound import analyze
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_required_settings

RUN = ROOT / "results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925"
EXPECTED = {
    "044": ("e959272c4330eb75e524190eadaee382c85263896c82dfc910ecffc31bb40c44",
            "506a8d65c65b7bcd2957e2b20f31ba117fb3a244b9c366ff2342c421df626cd5"),
    "046": ("5c05041646e382308d8bfe6a2a5a641b7cbbfb9e75e278dd0c20ef492ce564bd",
            "b84451d14a60de6589da5b4fa778607a7c82758acb058c13d015efce97e30023"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((RUN / "manifest.json").read_text())
    for relative, expected in manifest["source_input_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    cfg = ROOT / "data/raw/a/official/data/config.txt"
    settings = {
        "ddr_bandwidth": read_required_settings(cfg, "bandwidth", ("bandwidth",))["bandwidth"],
        "cache_bandwidth": read_required_settings(cfg, "problem_3", ("cache_capacity_bytes", "cache_bandwidth_bytes_per_cycle"))["cache_bandwidth_bytes_per_cycle"],
        "cross_core_delay_cycles": read_required_settings(cfg, "multicore_scene_b", ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"],
    }
    # Config parser may use floats for exact integers. No inferred bandwidth.
    assert all(int(value) == value for value in settings.values())
    settings = {key: int(value) for key, value in settings.items()}
    records = []
    for case, hashes in EXPECTED.items():
        graph_path = ROOT / f"data/raw/a/official/data/case_{case}.json"
        plan_path = RUN / f"case_{case}_multicore_res.json"
        result_path = RUN / f"evaluation/{case}/result.json.gz"
        assert (sha(plan_path), sha(result_path)) == hashes
        graph, plan = json.loads(graph_path.read_text()), json.loads(plan_path.read_text())
        result = json.loads(gzip.decompress(result_path.read_bytes()))
        assert result["problem"] == 3 and result["cache_mode"] == "read_only"
        bound = analyze(graph, plan, **settings)
        assert bound["compute_only_lower_bound_cycles"] <= bound["lower_bound_cycles"] <= result["makespan"]
        timeline = {c["core_id"]: c["ops"] for c in result["per_core_timeline"]}
        observed_compute = {x["op_id"]: x for ops in timeline.values() for x in ops
                            if str(x["op_id"]) in plan["node_to_subgraph"]}
        producers, consumers, _ = _original_tensor_views(graph)
        core_by_sg = {sg: core for core, seq in enumerate(plan["core_schedules"]) for sg in seq}
        owner = {int(u): core_by_sg[sg] for u, sg in plan["node_to_subgraph"].items()}
        checks, groups = [], defaultdict(lambda: defaultdict(list))
        for copy in bound["copies"]:
            tid, core = copy["tensor_id"], copy["core"]
            candidates = [x for x in timeline[core] if x["op"] == "COPY_IN"
                          and x.get("cache_tensor_id") == tid]
            assert candidates, copy
            actual = min(candidates, key=lambda x: x["start"])
            assert actual["subgraph_id"] == plan["core_schedules"][core][copy["bucket_rank"]]
            assert actual["duration"] >= copy["duration_lower_bound"]
            if copy["first_copy_proved_cold"]:
                assert actual["memory_path"] == "DDR" and not actual["cache_hit"]
            for u in consumers[tid]:
                if owner.get(u) == core:
                    assert actual["end"] <= observed_compute[u]["start"]
            if copy["kind"] == "cross_activation":
                producer, = [u for u in producers[tid] if u in owner]
                assert actual["start"] >= observed_compute[producer]["end"] + settings["cross_core_delay_cycles"]
            groups[core][copy["bucket_rank"]].append(actual)
            checks.append({"node": copy["node"], "official_op_id": actual["op_id"],
                           "start": actual["start"], "end": actual["end"],
                           "observed_duration": actual["duration"],
                           "duration_lower_bound": copy["duration_lower_bound"],
                           "cold_check_required": copy["first_copy_proved_cold"]})
        bucket_checks = 0
        for buckets in groups.values():
            previous_end = 0
            for _, copies in sorted(buckets.items()):
                assert all(x["start"] >= previous_end for x in copies)
                previous_end = max(x["end"] for x in copies)
                bucket_checks += 1
        records.append({"case_id": case, "cores": 5,
                        "graph_sha256": sha(graph_path), "plan_sha256": hashes[0],
                        "result_sha256": hashes[1], "official_makespan": result["makespan"],
                        "bound": bound, "copy_witness_checks": checks,
                        "bucket_barriers_checked": bucket_checks,
                        "remaining_fixed_plan_gap_cycles": result["makespan"] - bound["lower_bound_cycles"]})
    output = {"schema": "q3-copy-bound-existing-evidence-v1", "new_e0": 0,
              "task_builds": 0, "local_step3_simulations": 0, "settings": settings,
              "code_sha256": sha(ROOT / "src/q3/singleton_copy_bound.py"),
              "reproducer_sha256": sha(Path(__file__)), "records": records}
    Path(__file__).with_name("summary.json").write_text(json.dumps(output, indent=2) + "\n")
    for row in records:
        print(json.dumps({"case": row["case_id"], "lower_bound": row["bound"]["lower_bound_cycles"],
                          "actual": row["official_makespan"], "copy_checks": len(row["copy_witness_checks"]),
                          "gap": row["remaining_fixed_plan_gap_cycles"]}))


if __name__ == "__main__":
    main()
