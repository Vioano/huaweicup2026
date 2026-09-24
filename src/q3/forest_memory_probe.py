"""Two preregistered tree-frontier probes; <=4 external E0, no retry/search."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .construct import ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--construct", choices=("058", "079"))
    parser.add_argument("--method", choices=("frontier", "reuse-grid"), default="frontier")
    args = parser.parse_args()
    if args.construct:
        from .construct import Index
        if args.method == "reuse-grid":
            from .forest_reuse_grid import construct
        else:
            from .forest_memory_order import construct
        graph = ROOT / f"data/raw/a/official/data/case_{args.construct}.json"
        plan, metadata = construct(Index(json.loads(graph.read_bytes())), 5)
        args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n")
        print(json.dumps(metadata))
        return
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output_rel = output.relative_to(ROOT)
    started = time.perf_counter()
    state = {"status": "running", "method": args.method,
             "start_utc": datetime.now(timezone.utc).isoformat(),
             "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "python": sys.version, "platform": platform.platform(), "cores": 5,
             "budget": {"constructors": 2, "E0": 4, "workers": 1, "retry": 0,
                        "per_process_seconds": 90, "batch_seconds": 300},
             "command": ["python", "-m", "src.q3.forest_memory_probe", str(output_rel),
                         "--method", args.method],
             "attempts": [], "constructors": [], "results": [],
             "timing_scope": "External whole-child construction wall and subsequent E0 wall separately. No online selection or scored solver invoked. Shared host; OS cache uncontrolled."}
    paths = list((ROOT / "src/q3").glob("*.py"))
    paths += list((ROOT / "data/raw/a/official/code").glob("*.py"))
    paths += [ROOT / "uv.lock", ROOT / "data/raw/a/official/data/config.txt"]
    paths += [ROOT / f"data/raw/a/official/data/case_{cid}.json" for cid in ("058", "079")]
    state["source_input_sha256"] = {str(path.relative_to(ROOT)): sha(path) for path in paths}

    def save():
        state["elapsed_seconds"] = time.perf_counter() - started
        (output / "run.json").write_text(json.dumps(state, indent=2) + "\n")

    def run(command, label, kind):
        remaining = 300 - (time.perf_counter() - started)
        if remaining <= 0:
            raise TimeoutError("batch budget exhausted")
        item = {"kind": kind, "label": label, "argv": ["python", *command], "status": "started"}
        state["attempts"].append(item)
        save()
        t0 = time.perf_counter()
        try:
            child = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True,
                                   text=True, timeout=min(90, remaining))
        except subprocess.TimeoutExpired as error:
            (output / f"{label}.stdout.txt").write_bytes(error.stdout or b"")
            (output / f"{label}.stderr.txt").write_bytes(error.stderr or b"")
            item.update(status="timeout", wall_seconds=time.perf_counter() - t0)
            raise
        item["wall_seconds"] = time.perf_counter() - t0
        (output / f"{label}.stdout.txt").write_text(child.stdout)
        (output / f"{label}.stderr.txt").write_text(child.stderr)
        if child.returncode:
            item["status"] = "failed"
            raise RuntimeError(f"{label} exit {child.returncode}")
        item["status"] = "ok"
        save()
        return json.loads(child.stdout), item["wall_seconds"]

    save()
    try:
        for cid in ("058", "079"):
            graph = Path(f"data/raw/a/official/data/case_{cid}.json")
            plan = output_rel / f"case_{cid}_multicore_res.json"
            metadata, wall = run(["-m", "src.q3.forest_memory_probe", str(plan),
                                  "--construct", cid, "--method", args.method],
                                 f"{cid}-construct", "constructor")
            plan_sha = sha(ROOT / plan)
            state["constructors"].append({"case_id": cid, "metadata": metadata,
                                           "plan_sha256": plan_sha, "wall_seconds": wall})
            save()
            for problem in (3, 2):
                result_path = output_rel / f"{cid}-p{problem}.json.gz"
                require_hash = sha(ROOT / plan)
                if require_hash != plan_sha:
                    raise ValueError("plan changed between paired evaluations")
                summary, wall = run(["-m", "src.q3.oracle", str(graph), str(plan), str(problem),
                                     str(result_path)], f"{cid}-p{problem}", "E0")
                state["results"].append({"case_id": cid, "cores": 5, "problem": problem,
                                         "plan_sha256": plan_sha, "result_path": str(result_path),
                                         "result_sha256": sha(ROOT / result_path),
                                         "child_wall_seconds": wall, **summary})
                save()
        state["status"] = "complete"
    except Exception as error:
        state.update(status="stopped_on_failure", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        state["calls"] = {kind: sum(a["kind"] == kind for a in state["attempts"])
                          for kind in ("constructor", "E0")}
        save()
    print(json.dumps({"status": state["status"], "calls": state["calls"],
                      "elapsed_seconds": state["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
