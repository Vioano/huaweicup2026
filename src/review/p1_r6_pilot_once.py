"""Mac-only, single-worker supervisor for one bounded R6 P1 pilot.

Run only after the frozen source HEAD and inputs have been approved. This
script constructs no plan and scores nothing in its own process. Each child
gets a fresh session; group signals require the recorded leader identity.
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


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
SOURCE_FILES = (
    "src/review/p1_r6_pilot_once.py",
    "src/review/p1_r6_candidate_probe.py",
    "tests/q1/test_branch_aid.py",
    "src/q1/branch_aid.py",
    "src/q1/heavy_suffix.py",
    "src/q1/sink_peel.py",
    "src/q1/unified.py",
    "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
    "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
    "data/raw/a/official/code/evaluation_validation.py",
    "data/raw/a/official/data/config.txt",
)
STAGES = (("tests", 10.0), ("probe", 30.0), ("E0", 120.0))
TOTAL_SECONDS = 180.0
SAMPLE_SECONDS = 0.25
RSS_LIMIT_KIB = 1536 * 1024
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ps_value(pid, field):
    proc = subprocess.run(["ps", "-p", str(pid), "-o", f"{field}="],
                          capture_output=True, text=True, timeout=2, check=False)
    if proc.returncode:
        return None
    return proc.stdout.strip() or None


def group_table(pgid):
    """Read current group member PID/RSS; never infer ownership from it alone."""
    proc = subprocess.run(["ps", "-axo", "pid=,pgid=,rss="],
                          capture_output=True, text=True, timeout=3, check=True)
    members = []
    for line in proc.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            pid, group, rss = map(int, fields)
        except ValueError:
            continue
        if group == pgid:
            members.append({"pid": pid, "rss_kib": rss})
    return members


def leader_identity(pid, expected_start, expected_pgid):
    """Strict identity check before a group signal or while a child is live."""
    start = ps_value(pid, "lstart")
    group = ps_value(pid, "pgid")
    return start == expected_start and group == str(expected_pgid)


def settled_exit(child, expected_pgid):
    """Accept a fast exit only after reaping and two empty group snapshots."""
    rc = child.poll()
    if rc is None:
        return False, None
    if group_table(expected_pgid) or group_table(expected_pgid):
        return False, rc
    return True, rc


def cleanup_group(child, identity):
    """TERM, wait up to 2s, then KILL only while the leader still matches."""
    result = {"confirmed": False, "signals": [], "reason": None}
    if identity is None:
        result["reason"] = "no confirmed Popen leader identity; no group signal"
        return result
    pid, pgid, start = identity["pid"], identity["pgid"], identity["lstart"]
    try:
        if not leader_identity(pid, start, pgid):
            result["reason"] = "leader identity unavailable/changed; no group signal"
            return result
        os.killpg(pgid, signal.SIGTERM)
        result["signals"].append("SIGTERM")
        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            if child.poll() is not None and not group_table(pgid):
                result["confirmed"] = True
                return result
            time.sleep(min(SAMPLE_SECONDS, max(0.0, end - time.monotonic())))
        if group_table(pgid):
            if not leader_identity(pid, start, pgid):
                result["reason"] = "leader gone before KILL; residual group not signalled"
                return result
            os.killpg(pgid, signal.SIGKILL)
            result["signals"].append("SIGKILL")
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            result["reason"] = "leader did not exit after bounded cleanup"
            return result
        result["confirmed"] = not group_table(pgid)
        if not result["confirmed"]:
            result["reason"] = "same-PGID residual after cleanup"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        result["reason"] = f"cleanup error: {type(exc).__name__}: {exc}"
    return result


def run_stage(name, argv, cap, output, overall_start):
    stdout_path = output / f"{name}.stdout.raw"
    stderr_path = output / f"{name}.stderr.raw"
    stage = {"name": name, "argv": argv, "timeout_seconds": cap,
             "sample_interval_seconds": SAMPLE_SECONDS, "peak_group_rss_kib": 0,
             "started_utc": utc(), "reason": None, "returncode": None}
    env = dict(os.environ)
    env.update({key: "1" for key in THREAD_ENV})
    started = time.monotonic()
    child = None
    identity = None
    with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        try:
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out,
                                     stderr=err, start_new_session=True)
            stage["pid"] = child.pid
            stage["expected_pgid"] = child.pid
            try:
                stage["pgid"] = os.getpgid(child.pid)
                stage["ps_lstart"] = ps_value(child.pid, "lstart")
                if stage["pgid"] == child.pid and stage["ps_lstart"] and leader_identity(
                        child.pid, stage["ps_lstart"], stage["pgid"]):
                    identity = {"pid": child.pid, "pgid": stage["pgid"],
                                "lstart": stage["ps_lstart"]}
                else:
                    stage["reason"] = "new group identity could not be confirmed"
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                stage["identity_error"] = f"{type(exc).__name__}: {exc}"
                stage["reason"] = "new group identity acquisition failed"
            if stage["reason"] is not None:
                settled, rc = settled_exit(child, child.pid)
                if settled:
                    stage["returncode"] = rc
                    stage["reason"] = "complete" if rc == 0 else f"child returned {rc}"
                    stage["fast_exit_after_identity_failure"] = True
            while stage["reason"] is None:
                # A completed leader does not prove its process group is gone.
                rc = child.poll()
                members = group_table(identity["pgid"])
                stage["peak_group_rss_kib"] = max(
                    stage["peak_group_rss_kib"], sum(m["rss_kib"] for m in members))
                if stage["peak_group_rss_kib"] > RSS_LIMIT_KIB:
                    stage["reason"] = "group RSS exceeded 1536 MiB"
                    break
                if time.monotonic() - overall_start >= TOTAL_SECONDS - 4.0:
                    stage["reason"] = "total budget reached cleanup reserve"
                    break
                if rc is not None:
                    stage["returncode"] = rc
                    if members:
                        stage["reason"] = "leader exited with same-PGID residual"
                    elif rc:
                        stage["reason"] = f"child returned {rc}"
                    else:
                        stage["reason"] = "complete"
                    break
                if not leader_identity(identity["pid"], identity["lstart"], identity["pgid"]):
                    settled, final_rc = settled_exit(child, child.pid)
                    if settled:
                        stage["returncode"] = final_rc
                        stage["reason"] = ("complete" if final_rc == 0
                                           else f"child returned {final_rc}")
                        stage["fast_exit_during_identity_check"] = True
                    else:
                        stage["reason"] = "leader identity changed during execution"
                    break
                if time.monotonic() - started >= cap:
                    stage["reason"] = "stage timeout"
                    break
                time.sleep(SAMPLE_SECONDS)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            stage["reason"] = f"supervision error: {type(exc).__name__}: {exc}"
        finally:
            if child is not None:
                stage["returncode"] = child.poll()
                if stage["reason"] != "complete":
                    try:
                        settled, _ = settled_exit(child, child.pid)
                    except (OSError, subprocess.SubprocessError, ValueError) as exc:
                        settled = False
                        stage["settled_exit_error"] = f"{type(exc).__name__}: {exc}"
                    stage["cleanup"] = (
                        {"confirmed": True, "signals": [], "reason": "already exited and group empty"}
                        if settled else cleanup_group(child, identity))
                    stage["returncode"] = child.poll()
                try:
                    stage["same_pgid_residual"] = group_table(child.pid)
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    stage["same_pgid_residual_error"] = str(exc)
                    stage["same_pgid_residual"] = None
            stage["wall_seconds"] = time.monotonic() - started
            stage["finished_utc"] = utc()
    return stage


def preflight(expected_head):
    if platform.system() != "Darwin":
        raise RuntimeError("Mac ps/lstart supervisor requires Darwin")
    current = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                      cwd=ROOT, text=True).strip()
    if current != expected_head:
        raise RuntimeError(f"source HEAD mismatch: {current} != {expected_head}")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", *SOURCE_FILES],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    if tracked.returncode or len(tracked.stdout.splitlines()) != len(SOURCE_FILES):
        raise RuntimeError("participating source/config files are not all tracked")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCE_FILES],
                                    cwd=ROOT, text=True)
    if dirty.strip():
        raise RuntimeError("participating source/config files are not clean")
    dependency_diff = subprocess.check_output(
        ["git", "diff", "HEAD", "--name-only", "--", "src/q1", "src/eval_exact",
         "data/raw/a/official", "uv.lock"], cwd=ROOT, text=True)
    if dependency_diff.strip():
        raise RuntimeError("tracked algorithm/evaluator dependencies differ from HEAD")
    return current


def artifact_hashes(output):
    return {p.relative_to(output).as_posix():
            {"bytes": p.stat().st_size, "sha256": file_sha(p)}
            for p in sorted(output.rglob("*")) if p.is_file() and p.name != "receipt.json"}


def pilot(graph, reference_plan, output, expected_head):
    begun = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "started", "started_utc": utc(),
               "expected_head": expected_head, "budget_seconds": TOTAL_SECONDS,
               "worker_limit": 1, "rss_limit_kib": RSS_LIMIT_KIB,
               "stage_timeouts_seconds": dict(STAGES), "stages": [],
               "calls": {"test_process": 0, "probe_process": 0,
                         "E0_process": 0, "E1": 0, "E2": 0, "retry": 0,
                         "baseline_E0": 0}}
    try:
        receipt["graph_sha256"] = file_sha(graph)
        receipt["reference_plan_sha256"] = file_sha(reference_plan)
        receipt["source_head"] = preflight(expected_head)
        receipt["source_sha256"] = {name: file_sha(ROOT / name) for name in SOURCE_FILES}
        receipt["environment"] = {"platform": platform.platform(),
                                  "python_version": platform.python_version(),
                                  "threads": {key: "1" for key in THREAD_ENV},
                                  "rss_scope": "Sampled process-group sum; not a continuous memory cap"}
        test_argv = [sys.executable, "-B", "-m", "unittest", "discover",
                     "-s", "tests/q1", "-p", "test_branch_aid.py"]
        probe_dir = output / "probe"
        probe_argv = [sys.executable, "-B", "-m", "src.review.p1_r6_candidate_probe",
                      "--graph", str(graph.resolve()),
                      "--reference-plan", str(reference_plan.resolve()),
                      "--output-dir", str(probe_dir)]
        e0_dir = output / "e0"
        e0_argv = [sys.executable, "-B",
                   str(OFFICIAL / "code/multicore_cut_evaluate_problem_1.py"),
                   str(graph.resolve()), str(probe_dir / "candidate.raw.json"),
                   "--config", str(OFFICIAL / "data/config.txt"),
                   "--output", str(e0_dir / "result.json"),
                   "--trace-output", str(e0_dir / "trace.json"),
                   "--log-output", str(e0_dir / "official.log")]
        for name, argv, timeout in (("tests", test_argv, 10.0),
                                    ("probe", probe_argv, 30.0),
                                    ("E0", e0_argv, 120.0)):
            if time.monotonic() - begun >= TOTAL_SECONDS - 4.0:
                receipt["status"] = "stopped"
                receipt["reason"] = "total budget reached cleanup reserve before stage"
                break
            if name == "E0":
                probe_receipt = json.loads((probe_dir / "receipt.json").read_text())
                base = (probe_dir / "base.raw.json").read_bytes()
                candidate = (probe_dir / "candidate.raw.json").read_bytes()
                if (probe_receipt.get("status") != "candidate-unscored"
                        or base == candidate):
                    receipt["status"] = "stopped"
                    receipt["reason"] = "no distinct unscored candidate for E0"
                    break
                e0_dir.mkdir(exist_ok=False)
            stage = run_stage(name, argv, timeout, output, begun)
            receipt["stages"].append(stage)
            if "pid" in stage:
                receipt["calls"][{"tests": "test_process", "probe": "probe_process",
                                  "E0": "E0_process"}[name]] += 1
            if stage["reason"] != "complete" or stage.get("same_pgid_residual") != []:
                receipt["status"] = "stopped"
                receipt["reason"] = f"{name}: {stage['reason']}"
                break
        else:
            receipt["status"] = "candidate-E0-collected"
            receipt["reason"] = "one candidate E0 process exited cleanly; inspect result"
        if (probe_dir / "receipt.json").exists():
            receipt["probe_calls"] = json.loads((probe_dir / "receipt.json").read_text()).get("calls")
    except Exception as exc:
        receipt["status"] = "stopped"
        receipt["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            receipt["artifact_hashes"] = artifact_hashes(output)
        except (OSError, ValueError) as exc:
            receipt["status"] = "stopped"
            receipt["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"
        receipt["total_wall_seconds"] = time.monotonic() - begun
        receipt["finished_utc"] = utc()
        with (output / "receipt.json").open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--reference-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    record = pilot(args.graph, args.reference_plan, args.output_dir,
                   args.expected_head)
    print(json.dumps({"status": record["status"], "reason": record.get("reason"),
                      "receipt": str(args.output_dir / "receipt.json")}))
    return 0 if record["status"] == "candidate-E0-collected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
