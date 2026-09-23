"""Round-1 gap probe: spill / capacity criticality (F-LOCAL).

Sweeps the per-position capacity given to Step2 and records, for each capacity,
whether the run completes and how many SPILL records it produced.

Design of the graph: the live UB set grows one tensor per step, and at the step
where capacity is exceeded there is at least one tensor that is NOT consumed by
that step - otherwise Step2 has no legal Belady victim and raises.

No E0 call, no makespan, no quality claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data" / "raw" / "a" / "official" / "code"
OUT_DIR = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))
import multicore_cut_evaluate_problem_1 as p1  # noqa: E402
from schedule_step2 import step2_spill_insertion  # noqa: E402

BANDWIDTH = 60
CAP_L1 = 524288
CAP_UB_FULL = 131072
SIZE = 64


def graph():
    """op2 makes 102 and 103; op3 consumes both and makes 104.
    op4..op7 keep 104 alive and each produce one more live UB tensor.
    op8 consumes 104,105,106 and produces 109 -> at step 8 the tensors 107 and 108
    are live but idle, so they are legal Belady victims.
    op9 (COPY_OUT) finally consumes 107,108,109.
    """
    ops = [{"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0}]
    for i in range(2, 10):
        ops.append({"id": i, "op": "VADD", "pipe": "PIPE_V", "cycles": 4})
    ops.append({"id": 10, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0})
    tensors = [{"id": 100, "pos": "DDR", "size": SIZE}, {"id": 101, "pos": "L1", "size": SIZE}]
    for t in range(102, 110):
        tensors.append({"id": t, "pos": "UB", "size": SIZE})
    tensors.append({"id": 110, "pos": "DDR", "size": SIZE})
    edges = [{"source": 100, "target": 1}, {"source": 1, "target": 101},
             {"source": 101, "target": 2},
             {"source": 2, "target": 102}, {"source": 2, "target": 103},
             {"source": 102, "target": 3}, {"source": 103, "target": 3},
             {"source": 3, "target": 104}]
    for i in range(4, 8):                      # op4..op7 produce 105..108
        edges.append({"source": 104, "target": i})
        edges.append({"source": i, "target": 101 + i})
    for t in (104, 105, 106):                  # op8
        edges.append({"source": t, "target": 8})
    edges.append({"source": 8, "target": 109})
    for t in (107, 108, 109):                  # op10 (COPY_OUT)
        edges.append({"source": t, "target": 10})
    edges.append({"source": 10, "target": 110})
    return {"ops": ops, "tensors": tensors, "edges": edges}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    g = graph()
    plan = {"node_to_subgraph": {str(i): 0 for i in range(2, 10)}, "core_schedules": [[0]]}
    tasks, _cross, _traffic, _view = p1._build_scene_a_tasks(
        g, plan, BANDWIDTH, {"L1": CAP_L1, "UB": CAP_UB_FULL})
    t0 = tasks[0]
    local_graph, seq = t0["graph"], t0["seq"]
    ub = [t for t in local_graph["tensors"] if t.get("pos") == "UB"]
    total_ub = sum(t["size"] for t in ub)

    records = []
    for cap in (CAP_UB_FULL, 512, 448, 384, 320, 256, 192):
        try:
            res = step2_spill_insertion(local_graph, seq, capacity={"L1": CAP_L1, "UB": cap})
            recs = res["spill_records"]
            records.append({
                "capacity_ub": cap, "outcome": "completed",
                "n_spills": len(recs),
                "victims": sorted({r.get("tid") for r in recs}),
                "spilled_sizes": sorted({r.get("size") for r in recs}),
                "reload_copies_data": sorted({bool(r.get("spill_out_copies_data")) for r in recs}),
                "n_new_ops": len(res.get("new_ops", [])),
            })
        except Exception as exc:  # noqa: BLE001
            records.append({"capacity_ub": cap, "outcome": "raised",
                            "error": "{}: {}".format(type(exc).__name__, exc)[:400]})

    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "scope": "F-LOCAL gap probe: Step2 spill vs per-position capacity",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "seed": None,
        "task_local_graph": {"n_ops": len(local_graph["ops"]), "n_tensors": len(local_graph["tensors"])},
        "ub_tensor_count": len(ub), "ub_bytes_total": total_ub, "seq_len": len(seq),
        "note": ("Counts and victim ids only. A capacity below the peak live set that has no "
                 "idle tensor at the triggering step raises Step2SchedulingError instead of "
                 "spilling - that is an observed behaviour, not a claimed defect."),
        "records": records,
    }
    out = OUT_DIR / "spill-observations.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("UB tensors:", len(ub), "total bytes:", total_ub, "seq len:", len(seq),
          "local ops:", len(local_graph["ops"]))
    for r in records:
        if r["outcome"] == "completed":
            print("  capUB={:<7} completed spills={:<3} victims={} new_ops={}".format(
                r["capacity_ub"], r["n_spills"], r["victims"], r["n_new_ops"]))
        else:
            print("  capUB={:<7} RAISED".format(r["capacity_ub"]))
    print("\nwritten:", out)


if __name__ == "__main__":
    main()
