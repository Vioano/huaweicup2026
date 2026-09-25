"""One current-input heavy baseline plus one R6 structural candidate.

No scorer or Task compiler runs here. A saved reference plan is used only as
an exact byte-identity gate for any later reuse of its official evaluation.
The caller's supervisor owns the hard timeout and resource budget.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.heavy_suffix import construct as heavy_construct
from src.q1.branch_aid import construct as branch_construct
from src.q1.unified import plan_bytes


CONFIG = ROOT / "data/raw/a/official/data/config.txt"
SOURCES = (
    "src/review/p1_r6_candidate_probe.py",
    "src/q1/branch_aid.py",
    "src/q1/heavy_suffix.py",
    "src/q1/sink_peel.py",
    "src/q1/unified.py",
    "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
    "data/raw/a/official/code/evaluation_validation.py",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_bytes_new(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)


def write_json_new(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    write_bytes_new(path, raw)


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe(graph_path, reference_path, output_dir):
    """Prepare evidence for one candidate; output_dir must not exist."""
    started = time.perf_counter()  # Internal probe time; imports are excluded.
    output_dir.mkdir(parents=True, exist_ok=False)
    record = {
        "status": "started", "started_utc": utc(),
        "scope": "one heavy baseline and one R6 structural candidate; no evaluation",
        "calls": {"heavy_construct": 0, "branch_construct": 0,
                  "solver": 0, "E1": 0, "E0": 0, "E2": 0},
        "later_gate": "Official E0 with spill checks remains necessary; this is not a unified solver result",
        "timing_scope": "Internal probe excludes imports and final receipt write; use supervisor process wall for end-to-end timing",
    }
    try:
        record["source_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        record["source_sha256"] = {
            name: sha((ROOT / name).read_bytes()) for name in SOURCES
        }
        graph_raw = graph_path.read_bytes()
        config_raw = CONFIG.read_bytes()
        write_bytes_new(output_dir / "graph.raw.json", graph_raw)
        write_bytes_new(output_dir / "config.txt", config_raw)
        record["input"] = {
            "graph_sha256": sha(graph_raw), "graph_bytes": len(graph_raw),
            "config_sha256": sha(config_raw), "config_bytes": len(config_raw),
        }
        graph = json.loads(graph_raw)

        # The reference is intentionally read after the current-input base
        # construction and never participates in heavy or branch selection.
        record["calls"]["heavy_construct"] += 1
        base_plan, base_diag = heavy_construct(graph, 5)
        base_raw = plan_bytes(base_plan)
        write_bytes_new(output_dir / "base.raw.json", base_raw)
        write_json_new(output_dir / "base.diagnostics.json", base_diag)
        record["base"] = {"plan_sha256": sha(base_raw),
                          "plan_bytes": len(base_raw),
                          "selected": base_diag.get("selected")}

        reference_raw = reference_path.read_bytes()
        write_bytes_new(output_dir / "reference.raw.json", reference_raw)
        record["reference"] = {
            "plan_sha256": sha(reference_raw), "plan_bytes": len(reference_raw),
            "byte_identical_to_current_base": reference_raw == base_raw,
        }
        if reference_raw != base_raw:
            record["status"] = "reference-byte-mismatch"
            record["reason"] = (
                "Current heavy baseline differs from reference raw bytes; "
                "old official E0 cannot be reused by this gate"
            )
            return record

        record["calls"]["branch_construct"] += 1
        candidate_plan, candidate_diag = branch_construct(graph, 5, base_plan)
        candidate_raw = plan_bytes(candidate_plan)
        write_bytes_new(output_dir / "candidate.raw.json", candidate_raw)
        write_json_new(output_dir / "candidate.diagnostics.json", candidate_diag)
        record["candidate"] = {
            "plan_sha256": sha(candidate_raw), "plan_bytes": len(candidate_raw),
            "selected": candidate_diag.get("selected"),
            "structural_status": candidate_diag.get("status"),
        }
        record["status"] = (
            "candidate-unscored" if candidate_diag.get("status") == "candidate-unscored"
            else "structural-unsupported"
        )
        if record["status"] == "structural-unsupported":
            record["reason"] = candidate_diag.get("reason", "no structural candidate")
        return record
    except Exception as exc:
        record["status"] = "failed"
        record["reason"] = f"{type(exc).__name__}: {exc}"
        return record
    finally:
        record["finished_utc"] = utc()
        record["internal_probe_wall_seconds"] = time.perf_counter() - started
        write_json_new(output_dir / "receipt.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--reference-plan", type=Path, required=True)
    parser.add_argument("--output-dir", "--output", dest="output_dir",
                        type=Path, required=True)
    args = parser.parse_args()
    receipt = probe(args.graph, args.reference_plan, args.output_dir)
    print(json.dumps({"status": receipt["status"],
                      "receipt": str(args.output_dir / "receipt.json")}))
    return 0 if receipt["status"] == "candidate-unscored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
