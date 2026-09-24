"""Export the fixed historical 13-call P2 pilot; never import/run a solver."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY = "results/a/q2-nikolastarx/joint-20260924"
ARCHIVE = "74c46372faf5910b9b3cce6ad9a61a7e040b17aa"
AS_RUN = "73e40f6ddcb8fd6a8f45a3120dbc7f82875ec628"
SEED = "0b58c123cccf02fc993b741d79dcd8511e4dd38f"
SEED_DIR = "results/a/q2-yuanzhifang/stage-b-20260924-042906/plans"
REPO = "huaweibei123/huaweicup2026"
SESSION = "nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_bytes(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def historical(path):
    """The local export inputs must be the unchanged fixed archive bytes."""
    relative = f"{HISTORY}/{path}"
    raw = (ROOT / relative).read_bytes()
    if raw != git_bytes(ARCHIVE, relative):
        raise ValueError(f"Changed historical input: {relative}")
    return raw


def source(commit, path, entrypoint):
    git_bytes(commit, path)  # Verify source references without executing them.
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def artifact(path):
    raw = historical(path)
    return {"path": f"{HISTORY}/{path}", "sha256": digest(raw)}


def export():
    protocol = json.loads(historical("protocol.json"))
    ledger = json.loads(historical("ledger.json"))
    rows = json.loads(historical("rows.json"))
    summary = json.loads(historical("summary.json"))
    completion = json.loads(historical("completion.json"))
    manifest = json.loads(historical("manifest.json"))
    if protocol["as_run_commit"] != AS_RUN or protocol["seed_commit"] != SEED:
        raise ValueError("Unexpected historical implementation or seed")
    if len(rows) != 13 or len(ledger["calls"]) != 13 or summary["status"] != "complete":
        raise ValueError("Incomplete historical pilot")
    for name, item in manifest.items():
        raw = historical(name)
        if digest(raw) != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError(f"Historical manifest mismatch: {name}")
    for path, expected in protocol["source_sha256"].items():
        if digest(git_bytes(AS_RUN, path)) != expected:
            raise ValueError(f"As-run source mismatch: {path}")
    official = json.loads((ROOT / "docs/a/source-manifest.json").read_bytes())
    for item in official["files"]:
        if item["path"].startswith("code/"):
            expected = protocol["source_sha256"]["data/raw/a/official/" + item["path"]]
            if expected != item["sha256"]:
                raise ValueError("Historical official code differs from frozen board identity")
    for name, expected in protocol["input_sha256"].items():
        if digest(historical("inputs/" + name)) != expected:
            raise ValueError(f"Historical input mismatch: {name}")

    records = []
    methods = {
        "id": "最小ID就绪优先",
        "critical32": "ID最小32个就绪项内按剩余计算关键路径优先",
        "critical": "全就绪集按剩余计算关键路径优先",
        "earliest_start": "按逐核逐Pipe计算代理的最早开始时刻优先",
    }
    for position, (row, call) in enumerate(zip(rows, ledger["calls"], strict=True)):
        label, case = row["candidate_id"], row["case"]
        if call["candidate_id"] != label or call["state"] != "success" or call["returncode"] != 0:
            raise ValueError("Rows and original call ledger disagree")
        if row["cli_seconds"] != call["cli_seconds"]:
            raise ValueError("Per-call timer mismatch")
        confirmed = label.endswith("-confirm")
        original = summary["winners"][case]["candidate_id"] if confirmed else label
        policy = original.split("-", 1)[1]
        frozen_seed = policy in ("M1", "M2")
        plan = artifact(label + "/plan.json")
        raw_result = gzip.decompress(historical(label + "/result.json.gz"))
        result = json.loads(raw_result)
        if plan["sha256"] != row["plan_sha256"] or plan["sha256"] != call["plan_sha256"]:
            raise ValueError("Plan hash mismatch")
        if digest(raw_result) != row["result_sha256"]:
            raise ValueError("Uncompressed official result hash mismatch")
        if result["makespan"] != row["cycles"] or type(result["makespan"]) is not type(row["cycles"]):
            raise ValueError("Makespan value/type mismatch")
        if result["num_cores"] != 4 or result["scene"] != "B" or result.get("problem") == 3:
            raise ValueError("Wrong problem/core official result")
        if result["data_movement_bytes"] != row["data_movement_bytes"]:
            raise ValueError("Movement mismatch")
        if confirmed and (historical(label + "/plan.json") != historical(original + "/plan.json")
                          or raw_result != gzip.decompress(historical(original + "/result.json.gz"))):
            raise ValueError("Final repeat no longer matches the selected prior result")

        parent_label = original if frozen_seed else f"{case}-M1"
        parent_source = source(SEED, f"{SEED_DIR}/{parent_label}.json", None)
        if historical("inputs/" + parent_label + ".json") != git_bytes(SEED, parent_source["path"]):
            raise ValueError("Historical Fang seed mismatch")
        solver_source = parent_source if frozen_seed else source(
            AS_RUN, "src/q2_nikolastarx/joint.py", "FixedAssignment.build")
        algorithm = "q2-fang-stage-b-frozen" if frozen_seed else "q2-fixed-assignment-priority"
        variant = policy.lower().replace("_", "-")
        provenance = {
            "producer_session": SESSION,
            "task_url": f"https://github.com/{REPO}/issues/33",
            "solver": {
                "source": solver_source,
                "authors": ["yuanzhifang30-sudo"] if frozen_seed else ["NikolaStarx"],
                "method": (f"Fang Stage B {policy}固定历史计划；本批只读取并评价，不重建原搜索。"
                           if frozen_seed else "保留M1逐操作核分配和mapping键序，转singleton并采用" + methods[policy] + "；计算代理不计DDR/spill。"),
                "references": [f"https://github.com/{REPO}/pull/59"],
                "upstream": [] if frozen_seed else [parent_source],
                "selected_algorithm_id": None, "selected_solver_commit": None,
            },
            "runner": {
                "source": source(AS_RUN, "src/q2_nikolastarx/pilot.py", "main"),
                "argv": call["argv"], "working_directory": ".",
            },
            "environment": {
                "os": protocol["platform"], "cpu": None, "gpu": None,
                "ram_bytes": None, "python": protocol["python"],
                "dependencies": "uv.lock sha256=" + protocol["uv_lock_sha256"],
                "threads": None, "workers": protocol["workers"], "peak_rss_bytes": None,
            },
            "measurement": {
                "started_at": None, "finished_at": None, "seed": None,
                "repeat_index": 1 if confirmed else 0, "cold_start": None,
                "solver_scope": "未测从图冷启动完整求解；仅历史强seed复用/局部构造。生成与共享索引的局部计时见parameters，不等于solver wall。",
                "evaluation_scope": "本次独立官方P2 CLI的subprocess.run前后perf_counter差；含进程启动和等待，不含调用前预留/plan落盘及事后结果压缩。",
                "budget": {"wall_seconds": 30, "candidate_limit": None,
                           "stop_reason": "本次CLI成功退出；共享批次完成13/13后停止，无重试。"},
                "calls": {"solver": 0 if (frozen_seed or confirmed) else 1,
                          "E0": 1, "E1": 0, "E2": 0},
                "offline_costs": "复用Fang固定0b58c123历史seed；其生产搜索时间/调用未计入本批且未在本批复记。无训练；未新增编译记录。此处0/1 solver仅为本次构造调用，不含历史成本。",
                "failure": None,
            },
            "missing_reasons": {
                **{f"provenance.environment.{key}": "旧运行收据未记录，未用当前机器观测补填。"
                   for key in ("cpu", "gpu", "ram_bytes", "threads", "peak_rss_bytes")},
                "provenance.measurement.started_at": "仅有共享批T0与预留相对秒，无逐次实际CLI开始UTC；不将预留时间冒充开始。",
                "provenance.measurement.finished_at": "未记录逐次结束UTC，不用mtime或导出时间猜测。",
                "provenance.measurement.seed": "本批策略确定性、无随机seed参数；上游历史搜索seed本批未复记。",
                "provenance.measurement.cold_start": "每次E0新进程，但历史seed已复用，未测从图solver冷热启动。",
                "provenance.measurement.budget.candidate_limit": "上限13是全批共享E0额度，不是本条单独solver候选预算。",
            },
        }
        if frozen_seed:
            provenance["missing_reasons"]["provenance.solver.source.entrypoint"] = "源是固定历史计划文件；本条未运行其原始生成器。"
        movement = result["data_movement_bytes"]
        records.append({
            "attempt_id": "nikolastarx-q2-joint-20260924-p2-" + label.replace("_", "-") + "-k4",
            "revision": 1, "run_id": "nikolastarx-q2-joint-20260924-" + variant,
            "algorithm_id": algorithm,
            "algorithm_name": "Fang Stage B 固定历史方案" if frozen_seed else "固定强核分配的就绪优先级构造",
            "variant": variant, "solver_commit": solver_source["commit"],
            "parameters": {
                "policy": policy, "stage": "final-confirm" if confirmed else "baseline" if frozen_seed else "candidate",
                "historical_batch_id": "joint-20260924", "ledger_entry_index": position,
                "parent_plan_source": parent_source, "selected_prior_attempt": original if confirmed else None,
                "generation_seconds": row["generation_seconds"], "shared_index_seconds": row.get("index_seconds"),
                "batch_budget": {"E0": 13, "workers": 1, "wall_seconds": 180, "stop_launch_seconds": 120},
                "batch_measured_wall_seconds": completion["elapsed_seconds"],
                "batch_extraction_seconds": protocol["preparation_seconds"],
                "batch_T0_utc": ledger["T0_utc"], "reservation_offset_seconds": call["reserved_at_seconds"],
            },
            "problem": "P2", "case_id": case, "cores": 4, "status": "ok",
            "metrics": {"makespan_cycles": result["makespan"], "solver_wall_seconds": None,
                        "evaluation_wall_seconds": row["cli_seconds"],
                        "ddr_bytes": movement["scheduled_copy_bytes"], "extra_ddr_bytes": movement["added_copy_bytes"],
                        "spill_bytes": movement["spill_added_copy_bytes"], "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": AS_RUN,
                          "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py"},
            "identity": {"graph_sha256": protocol["input_sha256"][f"case_{case}.json"],
                         "config_sha256": protocol["input_sha256"]["config.txt"],
                         "official_sha256": official["official_code_hash"], "plan_sha256": plan["sha256"]},
            "artifacts": {"plan": plan, "result": artifact(label + "/result.json.gz"),
                          "run": artifact("ledger.json"), "trace": artifact(label + "/trace.json.gz"),
                          "log": artifact(label + "/evaluation.txt"), "manifest": artifact("manifest.json")},
            "runtime_id": "nikolastarx-p2-pilot-20260924-macos27-arm64-py31213",
            "observed_at": None,
            "timing": {"solver_includes_evaluation": None,
                       "evaluation_precision": "Python time.perf_counter seconds; preserve original float",
                       "utc": "Only batch T0 has UTC; per-attempt timestamps unknown."},
            "provenance": provenance,
            "notes": [
                f"零新评价历史导出；原件固定{ARCHIVE}，实际运行{AS_RUN}；run原件是整批ledger，本条见candidate_id=" + label,
                "solver_wall_seconds=null：缺少历史seed生产与从进程启动到最终合法落盘的完整计时；整批2.831822542秒不能代替逐例solver wall。",
                "observed_at=null：未记录逐次UTC。timing.solver_includes_evaluation=null：没有可比solver wall。P2无Cache命中率。",
                "上游seed生成参数/成本未在本批完整复记；argv中的PYTHON是原账本占位，Python版本见environment。",
                "13个真实E0调用均保留；相同plan或最终重复确认不合并为独立方案，也不删除真实消耗。",
                "成功表示官方执行成功，退化候选仍为ok；不是宣布算法优于基线。未附单核分母，可由接收端匹配已核分母。",
            ],
            "source_url": f"https://github.com/{REPO}/issues/33#issuecomment-5805201838",
        })
    return {"schema_version": 1, "submission_version": 1, "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New feed path within this repository")
    args = parser.parse_args()
    path = args.output.resolve()
    if not path.is_relative_to(ROOT / "results/a/q2-nikolastarx"):
        raise ValueError("Export must remain in the owner's results directory")
    feed = export()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(feed, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"records": len(feed["records"]), "new_solver_or_evaluator_calls": 0,
                      "path": str(path.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
