"""One-worker, four-cell R6 transfer controller. Requires separate scheduler admission."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from src.review import p1_r6_pilot_once as supervisor


ROOT = Path(__file__).resolve().parents[2]
ORDER = ("082", "075", "047", "005")
INPUT_NAMES = ("graph.json", "reference-plan.json", "reference-result.json.gz")
MIN_DISK = 10 * 1024 ** 3
TOTAL = 720.0
CELL = 180.0


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read_command(argv):
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=True)
    return proc.stdout


def resource_snapshot():
    """Only machine-level counters; no process inventory or physical-free gate."""
    mem_raw = _read_command(["sysctl", "-n", "hw.memsize"])
    pressure_raw = _read_command(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"])
    vm_raw = _read_command(["vm_stat"])
    swap_lines = [line for line in vm_raw.splitlines() if line.startswith("Swapouts:")]
    if len(swap_lines) != 1:
        raise ValueError("vm_stat Swapouts field missing/ambiguous")
    disk = shutil.disk_usage(ROOT).free
    return {"mem_bytes": int(mem_raw.strip()), "pressure_level": int(pressure_raw.strip()),
            "swapouts": int(swap_lines[0].split(":", 1)[1].strip().rstrip(".")),
            "disk_free_bytes": disk,
            "raw": {"hw.memsize": mem_raw, "pressure_level": pressure_raw,
                    "vm_stat": vm_raw}}


class ResourceGuard:
    def __init__(self, snapshot=resource_snapshot):
        self.snapshot = snapshot
        self.last_swapouts = None
        self.samples = []

    def check(self):
        try:
            item = self.snapshot()
            reasons = []
            if item["mem_bytes"] < 48 * 1024 ** 3:
                reasons.append("host memory below 48 GiB")
            if item["pressure_level"] != 1:
                reasons.append("memory pressure not normal")
            if item["disk_free_bytes"] < MIN_DISK:
                reasons.append("disk below 10 GiB")
            if self.last_swapouts is not None and item["swapouts"] > self.last_swapouts:
                reasons.append("swapouts increased")
            self.last_swapouts = item["swapouts"]
            result = {**item, "ok": not reasons, "reason": "; ".join(reasons) or None}
        except Exception as exc:
            result = {"ok": False, "reason": f"resource read failed: {type(exc).__name__}: {exc}"}
        self.samples.append(result)
        return result


def verify_inputs(manifest, inputs_root, expected_head, prior_path, admission_path):
    if tuple(manifest.get("frozen_order", ())) != ORDER:
        raise ValueError("frozen order mismatch")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("four manifest rows required")
    if manifest.get("budget", {}).get("workers") != 1 or any(
            manifest.get("budget", {}).get(k) != v for k, v in {
                "heavy_construct_max": 4, "branch_construct_max": 4,
                "E0_max": 4, "E1": 0, "E2": 0, "retries": 0,
                "new_structure_tests": 0, "per_cell_total_seconds": 180,
                "all_cells_total_seconds": 720}.items()):
        raise ValueError("budget manifest mismatch")
    head = _read_command(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    if head != expected_head:
        raise ValueError("source HEAD mismatch")
    hashes = manifest.get("source_sha256")
    required_sources = set(supervisor.SOURCE_FILES) | {"src/review/p1_r6_transfer_batch.py"}
    if not isinstance(hashes, dict) or not required_sources.issubset(hashes):
        raise ValueError("source hashes missing")
    for name, expected in hashes.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or file_sha(path) != expected:
            raise ValueError(f"source hash mismatch: {name}")
    if (not prior_path.is_file() or file_sha(prior_path) != manifest.get("prior_test_receipt_sha256")):
        raise ValueError("prior test receipt hash mismatch")
    supervisor.validated_prior_structure_tests(prior_path)
    if not admission_path.is_file():
        raise ValueError("freshps admission evidence missing")
    for case, row in zip(ORDER, rows):
        if row.get("case") != case or row.get("cores") != 5:
            raise ValueError(f"manifest row mismatch: {case}")
        files = row.get("files", {})
        for name in INPUT_NAMES:
            path = inputs_root / case / name
            spec = files.get(name)
            if (not isinstance(spec, dict) or not path.is_file()
                    or path.stat().st_size != spec.get("bytes")
                    or file_sha(path) != spec.get("sha256")):
                raise ValueError(f"input hash/size mismatch: {case}/{name}")
    return {"source_head": head, "freshps_admission": str(admission_path.resolve()),
            "freshps_admission_sha256": file_sha(admission_path)}


def _clean_stage(stage, reason, rc):
    return (isinstance(stage, dict) and stage.get("reason") == reason
            and stage.get("returncode") == rc
            and stage.get("same_pgid_residual") == []
            and stage.get("same_pgid_residual_error") is None
            and (reason == "complete" or stage.get("cleanup", {}).get("confirmed") is True))


def classify(cell_dir, pilot_receipt):
    """Fail closed on missing worker/call/cleanup evidence."""
    stages = pilot_receipt.get("stages")
    calls = pilot_receipt.get("calls")
    probe_calls = pilot_receipt.get("probe_calls")
    if not isinstance(stages, list) or not isinstance(calls, dict) or not isinstance(probe_calls, dict):
        raise ValueError("stage or call evidence missing")
    if (calls.get("test_process") != 0 or calls.get("probe_process") != 1
            or any(calls.get(k) != 0 for k in ("E1", "E2", "retry", "baseline_E0"))):
        raise ValueError("unexpected pilot process calls")
    heavy = probe_calls.get("heavy_construct")
    branch = probe_calls.get("branch_construct")
    if type(heavy) is not int or heavy != 1 or type(branch) is not int or branch not in (0, 1):
        raise ValueError("unknown probe constructor counts")
    if any(probe_calls.get(name) != 0 for name in ("solver", "E0", "E1", "E2")):
        raise ValueError("unexpected probe scoring calls")
    probe_path = cell_dir / "probe" / "receipt.json"
    probe = json.loads(probe_path.read_text())
    if probe.get("calls") != probe_calls:
        raise ValueError("probe receipt calls differ from pilot")
    if pilot_receipt.get("status") == "candidate-E0-collected":
        if (len(stages) != 2 or [s.get("name") for s in stages] != ["probe", "E0"]
                or not all(_clean_stage(s, "complete", 0) for s in stages)
                or calls.get("E0_process") != 1 or probe.get("status") != "candidate-unscored"):
            raise ValueError("candidate stage evidence incomplete")
        status = "candidate-E0-collected"
    elif (pilot_receipt.get("status") == "stopped"
          and pilot_receipt.get("reason") == "probe: child returned 1"
          and probe.get("status") in ("structural-unsupported", "reference-byte-mismatch")
          and len(stages) == 1 and stages[0].get("name") == "probe"
          and _clean_stage(stages[0], "child returned 1", 1)
          and calls.get("E0_process") == 0):
        status = "normal-no-candidate"
    else:
        raise ValueError(f"pilot stopped abnormally: {pilot_receipt.get('reason')}")
    return {"status": status, "probe_status": probe.get("status"),
            "heavy_construct": heavy, "branch_construct": branch,
            "E0_process": calls["E0_process"],
            "pilot_receipt_sha256": file_sha(cell_dir / "receipt.json"),
            "probe_receipt_sha256": file_sha(probe_path)}


def failed_calls(cell_dir, returned_receipt):
    """Retain raw failure evidence and count only independently readable calls."""
    path = cell_dir / "receipt.json"
    result = {"pilot_receipt_path": str(path), "pilot_receipt_sha256": None,
              "raw_pilot_calls": None, "raw_probe_calls": None,
              "exact_calls": {"heavy_construct": None, "branch_construct": None, "E0": None}}
    try:
        if path.is_file():
            result["pilot_receipt_sha256"] = file_sha(path)
            pilot = json.loads(path.read_text())
        else:
            pilot = returned_receipt if isinstance(returned_receipt, dict) else {}
        calls = pilot.get("calls")
        result["raw_pilot_calls"] = calls
        probe_calls = pilot.get("probe_calls")
        probe_path = cell_dir / "probe" / "receipt.json"
        if probe_path.is_file():
            raw_probe = json.loads(probe_path.read_text()).get("calls")
            result["probe_receipt_path"] = str(probe_path)
            result["probe_receipt_sha256"] = file_sha(probe_path)
            if probe_calls == raw_probe:
                result["raw_probe_calls"] = raw_probe
        if isinstance(calls, dict) and type(calls.get("E0_process")) is int:
            result["exact_calls"]["E0"] = calls["E0_process"]
        if isinstance(result["raw_probe_calls"], dict):
            for name in ("heavy_construct", "branch_construct"):
                value = result["raw_probe_calls"].get(name)
                if type(value) is int:
                    result["exact_calls"][name] = value
    except (OSError, ValueError, TypeError) as exc:
        result["evidence_error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_batch(manifest_path, inputs_root, output, expected_head, admission_path,
              *, pilot_fn=supervisor.pilot, verify_fn=verify_inputs,
              guard=None, clock=time.monotonic, sleep=time.sleep):
    start = clock()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "started", "order": list(ORDER), "cells": [],
               "limits": {"total_seconds": TOTAL, "per_cell_seconds": CELL,
                          "heavy_construct": 4, "branch_construct": 4, "E0": 4,
                          "E1": 0, "E2": 0, "retry": 0},
               "successful_cell_subtotal": {"heavy_construct": 0,
                                            "branch_construct": 0, "E0": 0},
               "overall_exact_calls": {"heavy_construct": 0,
                                       "branch_construct": 0, "E0": 0}}
    guard = guard or ResourceGuard()
    try:
        manifest = json.loads(manifest_path.read_text())
        prior_path = ROOT / manifest["prior_test_receipt"]
        receipt["manifest_sha256"] = file_sha(manifest_path)
        receipt["admission"] = verify_fn(manifest, inputs_root, expected_head,
                                          prior_path, admission_path)
        receipt["prior_test_receipt_sha256"] = file_sha(prior_path)
        t0 = guard.check()
        sleep(1.0)
        t1 = guard.check()
        if not t0["ok"] or not t1["ok"]:
            raise RuntimeError("T0 resource guard failed")
        for case in ORDER:
            if TOTAL - (clock() - start) < CELL:
                receipt["status"] = "stopped"
                receipt["reason"] = "less than 180 seconds remain before next cell"
                break
            between = guard.check()
            if not between["ok"]:
                receipt["status"] = "stopped"
                receipt["reason"] = f"resource guard before {case}: {between['reason']}"
                break
            cell_dir = output / case
            graph = inputs_root / case / "graph.json"
            reference = inputs_root / case / "reference-plan.json"
            pilot_receipt = None
            try:
                def runtime_check():
                    sample = guard.check()
                    if clock() - start >= TOTAL - 4.0:
                        sample = {**sample, "ok": False,
                                  "reason": "batch budget reached cleanup reserve"}
                    return sample

                pilot_receipt = pilot_fn(graph, reference, cell_dir, expected_head,
                                         prior_structure_test_receipt=prior_path,
                                         resource_check=runtime_check)
                result = classify(cell_dir, pilot_receipt)
                increments = {"heavy_construct": result["heavy_construct"],
                              "branch_construct": result["branch_construct"],
                              "E0": result["E0_process"]}
                for key, increment in increments.items():
                    if receipt["successful_cell_subtotal"][key] + increment > 4:
                        raise ValueError(f"cumulative {key} cap exceeded")
                for key, increment in increments.items():
                    receipt["successful_cell_subtotal"][key] += increment
                    receipt["overall_exact_calls"][key] += increment
                receipt["cells"].append({"case": case, **result})
            except Exception as exc:
                failure = failed_calls(cell_dir, pilot_receipt)
                for key, value in failure["exact_calls"].items():
                    receipt["overall_exact_calls"][key] = (
                        receipt["overall_exact_calls"][key] + value
                        if value is not None else None)
                receipt["cells"].append({"case": case, "status": "failed",
                                         "reason": f"{type(exc).__name__}: {exc}",
                                         **failure})
                receipt["status"] = "stopped"
                receipt["reason"] = f"{case}: {type(exc).__name__}: {exc}"
                break
        else:
            receipt["status"] = "complete"
            receipt["reason"] = "four bounded cells classified"
    except Exception as exc:
        receipt["status"] = "stopped"
        receipt["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        seen = {item["case"] for item in receipt["cells"]}
        receipt["cells"].extend({"case": case, "status": "not-run"} for case in ORDER if case not in seen)
        receipt["resource_samples"] = guard.samples
        receipt["total_wall_seconds"] = clock() - start
        with (output / "receipt.json").open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            import os
            os.fsync(stream.fileno())
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inputs-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--freshps-admission", type=Path, required=True)
    args = parser.parse_args()
    result = run_batch(args.manifest, args.inputs_root, args.output_dir,
                       args.expected_head, args.freshps_admission)
    print(json.dumps({"status": result["status"], "reason": result.get("reason"),
                      "receipt": str(args.output_dir / "receipt.json")}))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
