"""Frozen three-case P1 response contract probe; prepare never calls E0.

`run` is an explicit, later operation: at most three official E0 CLI calls,
one worker, 10 seconds each, a 90-second batch admission budget, no retries.
Cleanup and evidence finalization are timed separately; 90 seconds is not a
hard watchdog over the Python parent. Results
are diagnostic and never submitted to the benchmark board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import platform
import sys
import time

from src.q1.response_compile import compile_plan
from src.q1.response_oracle import quotient, simulate


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
SOURCE_MANIFEST = ROOT / "docs/a/source-manifest.json"
SOURCE_FILES = (
    "src/q1_benchmarks/response_contract_probe.py",
    "src/q1_benchmarks/bounded_probe_e0.py",
    "src/q1/response_compile.py", "src/q1/response_oracle.py",
)
NAMES = ("symmetric-k2", "symmetric-k3", "divergent-k3")
LIMITS = {"workers": 1, "e0_calls": 3, "per_e0_seconds": 10,
          "batch_admission_seconds": 90, "retries": 0}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True,
                       allow_nan=False) + "\n").encode()


def _write_new(path, obj):
    with Path(path).open("xb") as stream:
        stream.write(_json_bytes(obj))


def _read(path):
    return json.loads(Path(path).read_text())


def _verify_official():
    manifest = _read(SOURCE_MANIFEST)
    files = {item["path"]: item for item in manifest["files"]}
    relevant = {path: files[path]["sha256"] for path in files
                if path.startswith("code/") or path == "data/config.txt"}
    for path, expected in relevant.items():
        if _sha(OFFICIAL / path) != expected:
            raise RuntimeError(f"official source hash mismatch: {path}")
    code_list = "".join(f"{p}\t{files[p]['sha256']}\n"
                        for p in sorted(files) if p.startswith("code/"))
    if hashlib.sha256(code_list.encode()).hexdigest() != manifest["official_code_hash"]:
        raise RuntimeError("official code aggregate hash mismatch")
    return {"manifest_sha256": _sha(SOURCE_MANIFEST),
            "official_code_hash": manifest["official_code_hash"],
            "file_sha256": relevant}


def _config():
    # Official reader, with the exact three required settings from config.txt.
    from src.q1.response_compile import _official_modules
    scene, _, _, validation = _official_modules()
    path = OFFICIAL / "data/config.txt"
    common = validation.read_evaluation_config(path)
    waits = scene.read_scene_a_config(path)
    return common["capacity"], common["bandwidth"], waits


def fixture(name):
    """One of exactly three deterministic, independent two-round micrographs."""
    if name not in NAMES:
        raise ValueError("unknown fixture")
    cores = 2 if name == "symmetric-k2" else 3
    divergent = name == "divergent-k3"
    ops, tensors, edges, mapping = [], [], [], {}
    for round_index in range(2):
        for core in range(cores):
            task_id = round_index * cores + core
            m_id, v_id = 2 * task_id + 1, 2 * task_id + 2
            input_tid, early_tid = (10001 + 2 * task_id + i for i in range(2))
            m_cycles = 8 if divergent and round_index == 1 and core == 2 else 1
            ops.extend([
                {"id": m_id, "op": "COMPUTE", "pipe": "PIPE_M", "cycles": m_cycles},
                {"id": v_id, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 4},
            ])
            tensors.extend([
                {"id": input_tid, "size": 121, "pos": "UB"},
                {"id": early_tid, "size": 61, "pos": "UB"},
            ])
            edges.extend([
                {"source": input_tid, "target": v_id},
                {"source": m_id, "target": early_tid},
            ])
            mapping[str(m_id)] = task_id
            mapping[str(v_id)] = task_id
    graph = {"ops": ops, "tensors": tensors, "edges": edges}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[core, cores + core] for core in range(cores)]}
    return graph, plan


def _model(graph, plan, capacity, bandwidth, gate):
    lines, certificate = compile_plan(graph, plan, capacity, bandwidth)
    full = simulate(lines, gate=gate, keep_trace=True)
    folded = quotient(lines, gate=gate)
    expected_rounds = 1 if len(lines) == 3 and any(
        line[0].signature() != line[1].signature() for line in lines) else 2
    if folded["equal_rounds"] != expected_rounds:
        raise RuntimeError("fixture failed intended quotient coverage")
    # Compare the complete model operation timeline to the official result in run.
    # Keep the original labelled trace, not only a projected aggregate.
    return {"compile_certificate": certificate, "full": full,
            "quotient": folded}


def prepare(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"prepared directory already exists: {output}")
    official = _verify_official()
    capacity, bandwidth, waits = _config()
    sources = {path: _sha(ROOT / path) for path in SOURCE_FILES}
    output.mkdir(parents=True, exist_ok=False)
    for path in SOURCE_FILES:
        snapshot = output / "source" / path
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open("xb") as stream:
            stream.write((ROOT / path).read_bytes())
    entries = {}
    for name in NAMES:
        graph, plan = fixture(name)
        folder = output / name
        folder.mkdir()
        graph_path, plan_path = folder / "graph.json", folder / "plan.json"
        _write_new(graph_path, graph)
        _write_new(plan_path, plan)
        model = _model(graph, plan, capacity, bandwidth,
                       waits["task_same_core_wait_cycles"])
        _write_new(folder / "prepared_model.json", model)
        entries[name] = {filename: _sha(folder / filename)
                         for filename in ("graph.json", "plan.json",
                                          "prepared_model.json")}
    manifest = {
        "kind": "P1-response-contract-prepared-inputs-NOT-E0",
        "names": list(NAMES), "limits": LIMITS,
        "official": official, "source_sha256": sources,
        "config": {"capacity": capacity, "bandwidth": bandwidth, **waits},
        "files": entries, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
        "comparison_scope": "diagnostic synthetic cases; full per-op timelines and Makespan; no board submission",
    }
    _write_new(output / "prepare.json", manifest)
    return output


def _verify_prepared(prepared):
    manifest = _read(prepared / "prepare.json")
    if manifest["names"] != list(NAMES) or manifest["limits"] != LIMITS:
        raise RuntimeError("prepared coverage or budget differs")
    if manifest["official"] != _verify_official():
        raise RuntimeError("official source changed since prepare")
    if manifest["source_sha256"] != {
            path: _sha(ROOT / path) for path in SOURCE_FILES}:
        raise RuntimeError("response probe source changed since prepare")
    for path, expected in manifest["source_sha256"].items():
        if _sha(prepared / "source" / path) != expected:
            raise RuntimeError(f"prepared source snapshot changed: {path}")
    capacity, bandwidth, waits = _config()
    if manifest["config"] != {"capacity": capacity, "bandwidth": bandwidth, **waits}:
        raise RuntimeError("official config changed since prepare")
    if set(manifest["files"]) != set(NAMES):
        raise RuntimeError("prepared case set changed")
    for name in NAMES:
        folder = prepared / name
        if set(manifest["files"][name]) != {
                "graph.json", "plan.json", "prepared_model.json"}:
            raise RuntimeError("prepared file set changed")
        for filename, expected in manifest["files"][name].items():
            if _sha(folder / filename) != expected:
                raise RuntimeError(f"prepared file changed: {name}/{filename}")
        graph, plan = _read(folder / "graph.json"), _read(folder / "plan.json")
        if set(plan) != {"node_to_subgraph", "core_schedules"}:
            raise RuntimeError("plan has unexpected keys")
        if (graph, plan) != fixture(name):
            raise RuntimeError(f"prepared fixture changed: {name}")
    return manifest


def _timeline_map(entries):
    result = {}
    for entry in entries:
        key = (entry["core"], entry["task"], entry["op_id"])
        if key in result:
            raise RuntimeError(f"duplicate operation timeline entry: {key}")
        result[key] = (entry["start"], entry["end"])
    return result


def _compare(official, model):
    official_entries = [
        {"core": core["core_id"], "task": op["task_id"],
         "op_id": op["op_id"], "start": op["start"], "end": op["end"]}
        for core in official["per_core_timeline"] for op in core["ops"]]
    model_entries = model["full"]["trace"]
    expected_traffic = model["compile_certificate"]["traffic"]
    left, right = _timeline_map(official_entries), _timeline_map(model_entries)
    keys = sorted(set(left) | set(right))
    mismatches = [
        {"core": key[0], "task": key[1], "op_id": key[2],
         "official": left.get(key), "model": right.get(key)}
        for key in keys if left.get(key) != right.get(key)]
    return {"label": "synthetic diagnostic, response model NOT E0",
            "official_makespan": official["makespan"],
            "full_model_makespan": model["full"]["makespan"],
            "quotient_makespan": model["quotient"]["makespan"],
            "full_makespan_equal": official["makespan"] == model["full"]["makespan"],
            "quotient_makespan_equal": official["makespan"] == model["quotient"]["makespan"],
            "traffic_equal": official.get("data_movement_bytes") == expected_traffic,
            "official_traffic": official.get("data_movement_bytes"),
            "compiled_traffic": expected_traffic,
            "cross_task_bytes_equal": official.get("cross_task_traffic") ==
                model["compile_certificate"]["cross_task_tensor_bytes"],
            "official_op_count": len(left), "model_op_count": len(right),
            "all_op_timelines_equal": not mismatches,
            "op_timeline_mismatches": mismatches}


def run(prepared, output):
    """Execute frozen E0 CLI calls only when explicitly invoked later."""
    from src.q1_benchmarks.bounded_probe_e0 import process

    prepared, output = Path(prepared).resolve(), Path(output).resolve()
    manifest = _verify_prepared(prepared)
    if output.exists():
        raise FileExistsError(f"run directory already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    deadline = began + LIMITS["batch_admission_seconds"]
    ledger = {"kind": "synthetic-P1-response-diagnostic-NOT-board",
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "runtime": {"python": sys.version, "platform": platform.platform()},
              "prepared_sha256": _sha(prepared / "prepare.json"),
              "official_code_hash": manifest["official"]["official_code_hash"],
              "limits": LIMITS, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "cases": {}}
    for name in NAMES:
        folder = output / name
        folder.mkdir()
        record = {"status": "not_run", "calls": {"E0": 0}}
        ledger["cases"][name] = record
        if time.monotonic() + LIMITS["per_e0_seconds"] > deadline:
            record["reason"] = "batch budget insufficient"
            break
        command = [sys.executable, "-B", OFFICIAL / "code/multicore_cut_evaluate_problem_1.py",
                   prepared / name / "graph.json", prepared / name / "plan.json",
                   "--config", OFFICIAL / "data/config.txt", "--output", folder / "result.json",
                   "--trace-output", folder / "trace.json",
                   "--log-output", folder / "official.log"]
        model = _read(prepared / name / "prepared_model.json")
        _write_new(folder / "model.json", model)
        ledger["calls"]["E0"] += 1
        record["calls"]["E0"] = 1
        try:
            record["process"] = process(command, folder, "E0", 10, prepared)
            record["status"] = record["process"]["status"]
            if record["status"] != "ok":
                break
            official = _read(folder / "result.json")
            if official.get("scene") != "A" or official.get("num_cores") != len(
                    _read(prepared / name / "plan.json")["core_schedules"]):
                raise RuntimeError("official result identity mismatch")
            comparison = _compare(official, model)
            _write_new(folder / "comparison.json", comparison)
            record["artifacts"] = {item.name: _sha(item) for item in folder.iterdir()
                                   if item.is_file()}
            if not (comparison["full_makespan_equal"] and
                    comparison["quotient_makespan_equal"] and
                    comparison["all_op_timelines_equal"] and
                    comparison["traffic_equal"] and
                    comparison["cross_task_bytes_equal"]):
                record["status"] = "mismatch"
                break
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            break
        finally:
            record["artifacts"] = {item.name: _sha(item) for item in folder.iterdir()
                                   if item.is_file() and item.name != "receipt.json"}
            _write_new(folder / "receipt.json", record)
            (output / "ledger.json").write_bytes(_json_bytes(ledger))
    for name in NAMES:
        if name not in ledger["cases"]:
            ledger["cases"][name] = {"status": "not_run", "calls": {"E0": 0},
                                     "reason": "earlier case stopped batch"}
    ledger["elapsed_seconds_before_final_ledger"] = time.monotonic() - began
    ledger["admission_budget_exceeded"] = time.monotonic() > deadline
    (output / "ledger.json").write_bytes(_json_bytes(ledger))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    first = sub.add_parser("prepare")
    first.add_argument("output", type=Path)
    second = sub.add_parser("run")
    second.add_argument("prepared", type=Path)
    second.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.phase == "prepare":
        result = prepare(args.output)
    else:
        result = run(args.prepared, args.output)
    print(result)


if __name__ == "__main__":
    main()
