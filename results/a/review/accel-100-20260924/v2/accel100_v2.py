"""Q1 加速比批量流水线 v2：进程内 propose（省子进程启动/重复 import）+ 冻结官方 E0 CLI 评价。

候选生成逻辑逐字复用仓库最新 `src/q1/search.py` 的 propose 子命令（4dff90ef）；
评价用冻结官方 `multicore_cut_evaluate_problem_1.py`（不用 E1/E2）。
预算口径与仓库一致：<=32 候选、60s 搜索预算、提议即生成（进程内）、E0 30s timeout。
断点续跑：已有 best_plan.json 的 (case, cores) 跳过。
"""
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src" / "q1"))
sys.path.insert(0, str(ROOT / "data" / "raw" / "a" / "official" / "code"))

from prototype import (OFFICIAL, fixed_blocks, place_by_local_duration,  # noqa: E402
                       read_evaluation_config, read_scene_a_config,
                       generate_multicore_plan)
from structure import structural_partition, fuse_covers, topological  # noqa: E402
from stub_multicore_cut_and_schedule import (derive_multicore_plan,  # noqa: E402
                                             _build_op_adjacency,
                                             _contract_excluded_copy_nodes)
from evaluation_validation import validate_task_order  # noqa: E402

DATA = ROOT / "data/raw/a/official/data"
OUT = ROOT / "results/a/review/accel-100-20260924"
EVAL = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
CANDIDATES = 32
BUDGET = 60.0
EVAL_TIMEOUT = 30
CORES = (1, 2, 3, 4, 5)

SETTINGS = None
WAITS = None


def make_plan(kind, graph, cores, seed, parent):
    """逐字复用 search.py propose 子命令的候选生成逻辑（进程内版）。"""
    if kind == "official_stub":
        return generate_multicore_plan(graph, num_cores=cores, seed=seed)
    if kind == "single":
        nodes = [op["id"] for op in graph["ops"]
                 if op["op"] not in {"COPY_IN", "COPY_OUT"}]
        return {"node_to_subgraph": {v: 0 for v in nodes},
                "core_schedules": [[0]] + [[] for _ in range(cores - 1)]}
    if kind in ("chain", "component", "fixed64"):
        plan = (fixed_blocks(graph, cores, seed, 64) if kind == "fixed64"
                else structural_partition(graph, cores, kind))
        return place_by_local_duration(graph, plan, SETTINGS, WAITS)
    plan = json.loads(json.dumps(parent))  # incumbent plan dict
    if kind.startswith("fuse"):
        plan, _ = fuse_covers(graph, plan, 128, kind == "fuse_protected")
        return plan
    rng = random.Random(seed)
    orders = plan["core_schedules"]
    if kind == "move":
        source = rng.choice([k for k, order in enumerate(orders) if order])
        task = rng.choice(orders[source])
        destination = rng.randrange(cores)
        orders[source].remove(task)
        orders[destination].insert(rng.randrange(len(orders[destination]) + 1), task)
    elif kind == "swap":
        choices = [k for k, order in enumerate(orders) if len(order) >= 2]
        if not choices:
            raise ValueError("No adjacent pair to swap")
        order = orders[rng.choice(choices)]
        i = rng.randrange(len(order) - 1)
        order[i], order[i + 1] = order[i + 1], order[i]
    elif kind == "split":
        view = derive_multicore_plan(graph, plan)
        choices = [t for t, nodes in view["nodes_by_subgraph"].items() if len(nodes) >= 2]
        if not choices:
            raise ValueError("No splittable Task")
        task = rng.choice(choices)
        nodes = view["nodes_by_subgraph"][task]
        eligible = sorted(view["mapping"])
        _, full = _build_op_adjacency(graph)
        _, successors = _contract_excluded_copy_nodes(eligible, full)
        local = {v: successors[v] & set(nodes) for v in nodes}
        order = topological(nodes, local)
        cut = rng.randrange(1, len(order))
        new_task = max(view["subgraph_ids"]) + 1
        for v in order[cut:]:
            plan["node_to_subgraph"][str(v)] = new_task
        for core in orders:
            if task in core:
                core.insert(core.index(task) + 1, new_task)
                break
    return plan


def evaluate(graph_path, plan, prefix):
    plan_path = prefix + "-plan.json"
    Path(plan_path).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    cmd = [sys.executable, "-B", str(EVAL), str(graph_path), plan_path,
           "--config", str(CONFIG), "-o", prefix + "-result.json",
           "--trace-output", prefix + "-trace.json",
           "--log-output", prefix + ".log"]
    try:
        p = subprocess.run(cmd, capture_output=True, shell=False, timeout=EVAL_TIMEOUT)
        rc = p.returncode
        out = p.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        rc, out = 124, (exc.stdout or b"").decode("utf-8", errors="replace")
    if rc != 0:
        return None, None
    try:
        result = json.loads(Path(prefix + "-result.json").read_text(encoding="utf-8"))
    except Exception:
        return None, None
    ms = result.get("makespan")
    return (ms, plan_path) if isinstance(ms, int) else (None, None)


def best_of_case(case_id, cores):
    d = OUT / f"case{case_id}" / f"c{cores}"
    best = d / "best_plan.json"
    if best.exists():
        r = json.loads((d / "best-result.json").read_text(encoding="utf-8"))
        return r["makespan"], -1, -1.0
    d.mkdir(parents=True, exist_ok=True)
    graph_path = DATA / f"case_{case_id}.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    methods = (["official_stub"] if cores == 1 else
               ["official_stub", "single", "chain", "component", "fixed64",
                "fuse_protected", "fuse_free"])
    inc = None
    seen = set()
    evaluations = attempts = 0
    t0 = time.monotonic()
    while evaluations < CANDIDATES and attempts < CANDIDATES * 4:
        if time.monotonic() - t0 > BUDGET:
            break
        kind = methods.pop(0) if methods else ("split" if attempts % 8 == 0 else
                                               ("move" if attempts % 2 else "swap"))
        attempts += 1
        seed = attempts * 7919
        try:
            plan = make_plan(kind, graph, cores, seed,
                             inc[2] if inc else None)
            validate_task_order(derive_multicore_plan(graph, plan))
        except Exception:
            continue
        key = json.dumps(plan, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        evaluations += 1
        ms, path = evaluate(graph_path, plan, str(d / f"{attempts:03d}_{kind}"))
        if ms is None:
            continue
        if inc is None or ms < inc[0]:
            inc = (ms, path, plan)
            best.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            (d / "best-result.json").write_bytes(
                Path(prefix_result(d, attempts)).read_bytes())
    elapsed = time.monotonic() - t0
    if inc is None:
        return None, evaluations, elapsed
    (d / "summary.json").write_text(json.dumps(
        {"case": case_id, "cores": cores, "makespan": inc[0],
         "evaluations": evaluations, "attempts": attempts,
         "elapsed_s": round(elapsed, 2)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return inc[0], evaluations, elapsed


def prefix_result(d, attempts):
    cands = sorted(d.glob(f"{attempts:03d}_*-result.json"))
    return str(cands[-1]) if cands else str(d / "missing.json")


def main():
    global SETTINGS, WAITS
    SETTINGS = read_evaluation_config(str(OFFICIAL / "data/config.txt"))
    WAITS = read_scene_a_config(str(OFFICIAL / "data/config.txt"))
    OUT.mkdir(parents=True, exist_ok=True)
    ids = sys.argv[1:]
    if ids == ["all"]:
        ids = sorted(p.stem.replace("case_", "") for p in DATA.glob("case_*.json"))
    for case_id in ids:
        row = {"case": case_id}
        for cores in CORES:
            ms, n, el = best_of_case(case_id, cores)
            row[f"c{cores}"] = ms
            print(f"case{case_id} c{cores}: makespan={ms} evals={n} elapsed={round(el,1)}",
                  flush=True)
        base = row["c1"]
        for cores in CORES:
            if cores != 1 and row[f"c{cores}"] and base:
                row[f"speedup{cores}"] = round(base / row[f"c{cores}"], 4)
        (OUT / f"case{case_id}-summary.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("ROW:", json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
