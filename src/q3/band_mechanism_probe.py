"""Frozen two-graph owner/order experiment, not an online solver benchmark."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .construct import ROOT, Index
from .feedback_benchmark import digest, read, utc, verify_source, write
from .forest_band_dp import construct
from .safe_solve import encoded

CASES = ("058", "079")
MODES = ("component_id", "pair_cache_model")
BUDGET = {"max_e0_calls": 8, "workers": 1, "retries": 0,
          "per_job_seconds": 90, "batch_seconds": 360, "solver_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    start = time.monotonic()
    official, hashes = verify_source(args.source, set(CASES))
    proposals = []
    for case in CASES:
        index = Index(read(ROOT / f"data/raw/a/official/data/case_{case}.json"))
        owners = None
        for mode in MODES:
            before = time.monotonic()
            plan, metadata = construct(index, 5, order_mode=mode)
            current = [sorted(x) for x in metadata["components_by_core"]]
            if owners is not None and owners != current:
                raise ValueError("order comparison changed ownership")
            owners = current
            proposals.append((case, mode, encoded(plan), metadata, time.monotonic() - before))
    if args.preflight:
        print(json.dumps({"valid": True, "plans": len(proposals), "e0_calls": 0,
                          "seconds": time.monotonic() - start,
                          "coverage_bytes": [p[3]["coverage_bytes"] for p in proposals]}))
        return
    out = args.output.resolve()
    out.relative_to(ROOT / "results/a/q3-nikolastarx")
    out.mkdir(parents=True, exist_ok=False)
    state = {"schema": "q3-band-mechanism-v1", "source_commit": args.source,
             "started_at": utc(), "status": "running", "budget": BUDGET,
             "official_code_sha256": official, "source_input_sha256": hashes,
             "platform": platform.platform(), "python": platform.python_version(),
             "scope": "two seen graphs, same new owner with two tree orders and same-plan P2/P3; no fresh full500 or solver wall",
             "plans": [], "results": [], "e0_calls": 0}

    def save():
        state["elapsed_seconds"] = time.monotonic() - start
        write(out / "run.json", state)

    save()
    try:
        # Persist every deterministic proposal before launching any evaluator.
        for case, mode, raw, metadata, construct_seconds in proposals:
            folder = out / f"{case}-k5-{mode}"
            folder.mkdir()
            plan_path = folder / "plan.json"
            plan_path.write_bytes(raw)
            state["plans"].append({"case_id": case, "cores": 5, "order_mode": mode,
                                   "plan_path": str(plan_path.relative_to(ROOT)),
                                   "plan_sha256": digest(plan_path), "metadata": metadata,
                                   "construct_seconds": construct_seconds})
        save()
        for proposal in state["plans"]:
            folder = ROOT / Path(proposal["plan_path"]).parent
            for problem in (2, 3):
                remaining = BUDGET["batch_seconds"] - (time.monotonic() - start)
                if remaining <= 0 or state["e0_calls"] >= BUDGET["max_e0_calls"]:
                    raise TimeoutError("frozen probe budget reached")
                result_path = folder / f"p{problem}.json.gz"
                command = ["-m", "src.q3.oracle",
                           f"data/raw/a/official/data/case_{proposal['case_id']}.json",
                           proposal["plan_path"], str(problem), str(result_path.relative_to(ROOT))]
                record = {k: proposal[k] for k in ("case_id", "cores", "order_mode", "plan_sha256")}
                record.update(problem=problem, status="reserved", command=["python", *command])
                state["results"].append(record)
                state["e0_calls"] += 1
                save()
                before = time.monotonic()
                with (folder / f"p{problem}.stdout.json").open("xb") as stdout, (folder / f"p{problem}.stderr.txt").open("xb") as stderr:
                    subprocess.run([sys.executable, *command], cwd=ROOT, stdout=stdout,
                                   stderr=stderr, timeout=min(BUDGET["per_job_seconds"], remaining), check=True)
                record["external_e0_wall_seconds"] = time.monotonic() - before
                result = read(result_path)
                if result.get("num_cores") != 5:
                    raise ValueError("result core count mismatch")
                if problem == 3 and result.get("problem") != 3:
                    raise ValueError("expected P3 result identity")
                if problem == 2 and "cache_stats" in result:
                    raise ValueError("P2 result unexpectedly contains Cache statistics")
                if digest(ROOT / proposal["plan_path"]) != proposal["plan_sha256"]:
                    raise ValueError("plan mutated during official evaluation")
                record.update(status="ok", result_path=str(result_path.relative_to(ROOT)),
                              result_sha256=digest(result_path), makespan=result["makespan"],
                              data_movement_bytes=result["data_movement_bytes"],
                              cache_stats=result.get("cache_stats"))
                save()
        if any(digest(ROOT / path) != sha for path, sha in hashes.items()):
            raise ValueError("source/input changed during the frozen probe")
        state["status"] = "complete"
    except Exception as error:
        state.update(status="stopped_on_failure", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        state["finished_at"] = utc()
        save()
    print(json.dumps({k: state[k] for k in ("status", "e0_calls", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
