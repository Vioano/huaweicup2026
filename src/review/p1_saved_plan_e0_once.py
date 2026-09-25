"""One guarded official E0 on the frozen coalesced 008/K5 plan.

This deliberately has no solver path. The remote caller supplies a monotonic
deadline created on the same host and must pass --execute to dispatch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from unittest.mock import patch

from src.q1_benchmarks import bounded_probe_e0

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
EXPECTED = {
    "graph": "c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d",
    "plan": "e9327269bc95a81d17ca907a617aed896fd6fdde2a3174044d975f746569f9ce",
    "config": "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9",
    "evaluator": "2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f",
    "official_code": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
    "helper": "08f86b1e95dbed9f0c3d82c4005cbf85d81e0164493fc4fc51542ced9035011c",
}
EVALUATOR = OFFICIAL / "code/multicore_cut_evaluate_problem_1.py"
CONFIG = OFFICIAL / "data/config.txt"
HELPER = ROOT / "src/q1_benchmarks/bounded_probe_e0.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write(path: Path, obj: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temp.replace(path)


def _artifacts(folder: Path) -> dict:
    names = ("result.json", "trace.json", "official.log", "E0.stdout.txt",
             "E0.stderr.txt", "E0.stdout.raw.txt", "E0.stderr.raw.txt")
    return {name: {"path": name, "sha256": _sha(folder / name)}
            for name in names if (folder / name).is_file()}


def _verify(graph: Path, plan: Path) -> dict:
    if sys.version_info[:3] != (3, 12, 13):
        raise RuntimeError("requires Python 3.12.13")
    if _sha(graph) != EXPECTED["graph"] or _sha(plan) != EXPECTED["plan"]:
        raise RuntimeError("frozen graph or plan SHA mismatch")
    if set(json.loads(plan.read_text())) != {"node_to_subgraph", "core_schedules"}:
        raise RuntimeError("plan keys mismatch")
    if _sha(CONFIG) != EXPECTED["config"] or _sha(EVALUATOR) != EXPECTED["evaluator"]:
        raise RuntimeError("official evaluator/config SHA mismatch")
    if _sha(HELPER) != EXPECTED["helper"]:
        raise RuntimeError("bounded E0 helper SHA mismatch")
    manifest_path = ROOT / "docs/a/source-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    rows = {row["path"]: row for row in manifest["files"]}
    code_rows = sorted((row for row in rows.values() if row["path"].startswith("code/")),
                       key=lambda row: row["path"])
    aggregate = hashlib.sha256()
    for row in code_rows:
        source = OFFICIAL / row["path"]
        if _sha(source) != row["sha256"] or source.stat().st_size != row["bytes"]:
            raise RuntimeError(f"official source SHA mismatch: {row['path']}")
        aggregate.update(f"{row['path']}\t{row['sha256']}\n".encode())
    if aggregate.hexdigest() != EXPECTED["official_code"] or manifest["official_code_hash"] != EXPECTED["official_code"]:
        raise RuntimeError("official code aggregate mismatch")
    return {"graph_sha256": _sha(graph), "plan_sha256": _sha(plan),
            "config_sha256": _sha(CONFIG), "evaluator_sha256": _sha(EVALUATOR),
            "official_code_sha256": aggregate.hexdigest(), "helper_sha256": _sha(HELPER),
            "manifest_sha256": _sha(manifest_path)}


def run_once(graph: Path, plan: Path, output_dir: Path, deadline_monotonic: float,
             *, execute: bool, process_fn=None) -> dict:
    graph, plan, output_dir = (Path(p).resolve() for p in (graph, plan, output_dir))
    if not execute:
        raise RuntimeError("dispatch requires explicit --execute")
    identity = _verify(graph, plan)
    if output_dir.exists() or not output_dir.is_relative_to(ROOT):
        raise RuntimeError("output directory must be new and inside project")
    if time.monotonic() >= deadline_monotonic:
        raise TimeoutError("deadline expired before E0 dispatch")
    output_dir.mkdir(parents=True)
    result, trace, log = (output_dir / n for n in ("result.json", "trace.json", "official.log"))
    attempt_path = output_dir / "attempt.json"
    attempt = {"state": "prepared", "started_at": _utc(), "deadline_monotonic": deadline_monotonic,
               "workers": 1, "timeout_seconds": 60, "calls": {"constructor": 0, "E0": 0, "E1": 0, "E2": 0, "retry": 0},
               "identity": identity, "runtime": sys.version, "platform": platform.platform(),
               "process_identity": None}
    _write(attempt_path, attempt)
    if time.monotonic() >= deadline_monotonic:
        attempt["state"] = "expired_before_dispatch"
        _write(attempt_path, attempt)
        raise TimeoutError("deadline expired before E0 dispatch")

    argv = [sys.executable, "-B", str(EVALUATOR), str(graph), str(plan), "--config", str(CONFIG),
            "--output", str(result), "--trace-output", str(trace), "--log-output", str(log)]
    original_popen = subprocess.Popen

    class TrackedChild:
        """Expose helper's Popen surface and copy byte logs after wait/reap."""
        def __init__(self, child, streams):
            self._child, self.pid = child, child.pid
            self._streams, self._copied = streams, False

        @property
        def returncode(self):
            return self._child.returncode

        def poll(self):
            return self._child.poll()

        def wait(self, *args, **kwargs):
            result = self._child.wait(*args, **kwargs)
            if not self._copied:
                for src, dest in self._streams:
                    if src and src.is_file():
                        dest.write_bytes(src.read_bytes())
                self._copied = True
            return result

    def observed_popen(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        try:
            pgid = os.getpgid(child.pid)
        except OSError:
            pgid = None
        start_ticks = None
        try:
            fields = Path(f"/proc/{child.pid}/stat").read_text().rsplit(") ", 1)[-1].split()
            start_ticks = int(fields[19]) if len(fields) > 19 else None  # field 22: starttime
        except OSError:  # a very short process may exit between spawn and /proc read
            pass
        attempt["process_identity"] = {"pid": child.pid, "pgid": pgid,
                                       "linux_proc_start_ticks": start_ticks,
                                       "argv": [str(x) for x in args[0]]}
        try:
            _write(attempt_path, attempt)
        except Exception:
            # If durable identity publication fails before the helper receives
            # the handle, reap only this Popen's new process group.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # already exited; wait below still confirms/reaps our child
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("cannot confirm owned child cleanup after identity-write failure") from exc
            raise
        streams = []
        for key, raw_name in (("stdout", "E0.stdout.raw.txt"), ("stderr", "E0.stderr.raw.txt")):
            stream = kwargs.get(key)
            streams.append((Path(stream.name) if hasattr(stream, "name") else None,
                            output_dir / raw_name))
        return TrackedChild(child, streams)

    attempt["calls"]["E0"] = 1
    attempt["state"] = "dispatching"
    attempt["dispatch_started_at"] = _utc()
    _write(attempt_path, attempt)  # durable before helper can spawn the child
    if time.monotonic() >= deadline_monotonic:
        attempt["calls"]["E0"] = 0
        attempt["state"] = "expired_before_dispatch"
        _write(attempt_path, attempt)
        raise TimeoutError("deadline expired before E0 dispatch")
    process_fn = process_fn or bounded_probe_e0.process
    try:
        with patch.object(bounded_probe_e0.subprocess, "Popen", observed_popen):
            process = process_fn(argv, output_dir, "E0", 60, graph.parent)
        attempt.update(state=process["status"], process=process, finished_at=_utc())
        attempt["cleanup_confirmed"] = process.get("cleanup_confirmed")
        if process["status"] != "ok":
            raise RuntimeError(f"E0 process status {process['status']}")
        obj = json.loads(result.read_text())
        if obj.get("scene") != "A" or obj.get("num_cores") != 5:
            raise RuntimeError("E0 result identity mismatch")
        attempt["metrics"] = {"makespan_cycles": obj.get("makespan"),
                               "data_movement_bytes": obj.get("data_movement_bytes")}
        attempt["artifacts"] = _artifacts(output_dir)
        _write(attempt_path, attempt)
        return attempt
    except Exception as exc:
        attempt.update(state="failed", finished_at=_utc(), failure=f"{type(exc).__name__}: {exc}",
                       artifacts=_artifacts(output_dir))
        _write(attempt_path, attempt)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--deadline-monotonic", required=True, type=float)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    run_once(args.graph, args.plan, args.output_dir, args.deadline_monotonic, execute=args.execute)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
