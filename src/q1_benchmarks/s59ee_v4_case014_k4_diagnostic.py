"""One frozen, isolated E0 diagnostic of the existing P1 014/k4 plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h
from src.q1_benchmarks import unified_smoke as smoke

SCRIPT = "src/q1_benchmarks/s59ee_v4_case014_k4_diagnostic.py"
MANIFEST = "src/q1_benchmarks/s59ee_v4_case014_k4_diagnostic.json"
SOURCE = ROOT / "output/p1-v4-full500-s59ee/20260924T1929Z-s59ee/cells/014/k4"
OUTPUT = ROOT / "output/p1-v4-014k4-diagnostic-s59ee"


def check(runner_commit):
    spec = json.loads((ROOT / MANIFEST).read_text())
    for path in (SCRIPT, MANIFEST, "src/q1_benchmarks/unified_smoke.py",
                 "src/q1_benchmarks/bounded_full4_e0.py"):
        if (ROOT / path).read_bytes() != h.git("show", f"{runner_commit}:{path}"):
            raise RuntimeError(f"runner differs from fixed commit: {path}")
    assert spec["maximum_calls"] == {"solver": 0, "external_E0": 1,
                                     "internal_E1": 0, "E2": 0, "retries": 0}
    assert spec["workers"] == 1 and spec["rss_limit_bytes"] == 4 * 1024**3
    assert spec["e0_timeout_including_cleanup_seconds"] == 600
    assert spec["window_seconds"] == 660 and spec["cleanup_reserve_seconds"] == 2
    old = h.read(SOURCE / "run.json")
    if old["status"] != "timeout" or old["graph_sha256"] != spec["graph_sha256"]:
        raise RuntimeError("original failure receipt changed")
    if h.sha(SOURCE / "plan.json") != spec["plan_sha256"]:
        raise RuntimeError("original plan differs")
    official = ROOT / "data/raw/a/official"
    if h.sha(official / "code/multicore_cut_evaluate_problem_1.py") != spec["official_e0_sha256"]:
        raise RuntimeError("official E0 differs")
    if h.sha(official / "data/config.txt") != spec["config_sha256"]:
        raise RuntimeError("config differs")
    source_manifest = h.read(ROOT / "docs/a/source-manifest.json")
    archive = ROOT / source_manifest["case_archive"]["path"]
    if h.sha(archive) != source_manifest["case_archive"]["sha256"]:
        raise RuntimeError("official case archive differs")
    with zipfile.ZipFile(archive) as z:
        graph = z.read("data/case_014.json")
    if h.digest(graph) != spec["graph_sha256"]:
        raise RuntimeError("official graph differs")
    return spec, graph, (SOURCE / "plan.json").read_bytes(), official


def run(run_id, runner_commit):
    began = time.perf_counter()
    spec, graph, plan, official = check(runner_commit)
    if OUTPUT.joinpath(run_id).exists():
        raise RuntimeError("diagnostic run ID already exists; no automatic retry")
    folder = OUTPUT / run_id
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "case_014.json").write_bytes(graph)
    (folder / "plan.json").write_bytes(plan)
    if h.sha(folder / "case_014.json") != spec["graph_sha256"] or h.sha(folder / "plan.json") != spec["plan_sha256"]:
        raise RuntimeError("isolated input copy failed hash check")
    row = {"schema": spec["schema"], "run_id": run_id, "runner_commit": runner_commit,
           "source_run_id": spec["source_run_id"], "case": "014", "cores": 4,
           "status": "running", "started_at": h.utc(),
           "calls": {"solver": 0, "external_E0": 0, "internal_E1": 0, "E2": 0, "retries": 0},
           "input_hashes": {"graph": spec["graph_sha256"], "plan": spec["plan_sha256"],
                            "e0": spec["official_e0_sha256"], "config": spec["config_sha256"]}}
    h.write(folder / "run.json", row)
    try:
        row["evaluation"] = smoke.process(
            [sys.executable, "-B", official / "code/multicore_cut_evaluate_problem_1.py",
             folder / "case_014.json", folder / "plan.json", "--config", official / "data/config.txt",
             "--output", folder / "result.json", "--trace-output", folder / "trace.json",
             "--log-output", folder / "official.log"],
            folder, "e0", 600, began + 660,
            lambda: row["calls"].__setitem__("external_E0", 1), rss_limit=4 * 1024**3)
        if row["evaluation"]["status"] != "ok":
            raise RuntimeError("external E0 " + row["evaluation"]["status"])
        result = h.read(folder / "result.json")
        if result["scene"] != "A" or result["num_cores"] != 4 or result["makespan"] <= 0:
            raise RuntimeError("invalid official result identity/value")
        row.update(status="ok", makespan_cycles=result["makespan"])
    except BaseException as exc:
        row.update(status="timeout" if row.get("evaluation", {}).get("status") == "timeout" else "failed",
                   reason=f"{type(exc).__name__}: {exc}")
    finally:
        row["finished_at"] = h.utc()
        row["wall_seconds"] = time.perf_counter() - began
        row["cleanup_confirmed"] = row.get("evaluation", {}).get("cleanup_confirmed", False)
        row["artifacts"] = {p.name: h.artifact(p) for p in folder.iterdir()
                            if p.is_file() and p.name != "run.json"}
        h.write(folder / "run.json", row)
        print(json.dumps({k: row.get(k) for k in ("run_id", "status", "makespan_cycles", "calls", "wall_seconds", "cleanup_confirmed", "reason")}), flush=True)
    return 0 if row["status"] == "ok" and row["cleanup_confirmed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--runner-commit", required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in (".", ".."):
        parser.error("invalid run ID")
    if args.preflight:
        spec, graph, plan, official = check(args.runner_commit)
        print(json.dumps({"preflight": "ok", "case": "014", "cores": 4,
                          "calls": spec["maximum_calls"], "graph_bytes": len(graph),
                          "plan_bytes": len(plan), "official": str(official)}))
    else:
        raise SystemExit(run(args.run_id, args.runner_commit))
